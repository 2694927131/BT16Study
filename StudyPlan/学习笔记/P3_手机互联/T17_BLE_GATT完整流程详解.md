# T17_BLE_GATT完整流程详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. BLE扫描走GD层LeScanningManager(非btif_dm传统路径)→HCI LE_Set_Scan_Params→LE_Set_Scan_Enable→Advertising Report→GD解析→Java回调
2. GATT连接: BluetoothGatt.connect→btif_gatt_open→BTA_GATTC_Open→HCI LE_Create_Connection→connection complete→bta_gattc_conn_cback
3. 服务发现: discoverServices→BTA_GATTC_Discover→ATT Read By Type/Find Info→Service/Char/Descriptor解析→缓存
4. 读写: writeChar(writeType)→BTA_GATTC_Write(bta_gattc_cmpl_cback)/readChar→BTA_GATTC_Read→ATT消息; WriteNoResponse跳过确认
5. 通知: setCharNotification→写CCC Descriptor(0x2902)→ATT Handle Value Notification→onCharacteristicChanged; Indication需CONFIRMATION回复

## 详细笔记

### 一、BLE扫描

```
App: BluetoothLeScanner.startScan(filters, settings, callback)
→ GattService → GD层: LeScanningManager (gd/hci/le_scanning_manager/)
→ HCI: LE_Set_Scan_Parameters
  - LE_Scan_Type: Active(0x01)/Passive(0x00)
  - LE_Scan_Interval: N×0.625ms → 典型: 800 (500ms)
  - LE_Scan_Window: N×0.625ms → 典型: 96 (60ms)
  - Own_Address_Type: Public/Random/Resolvable
  - Scanning_Filter_Policy: Accept All(0)/Whitelist(1)/RPA(2)/RPA+Whitelist(3)
→ HCI: LE_Set_Scan_Enable(ScanEnable=1, FilterDuplicates=1)
→ LE Advertising Report Event
→ GD: LeScanningManager 解析 ADV_IND/SCAN_RSP/ADV_SCAN_IND
→ Java: ScanCallback.onScanResult()
```

**三种模式**: SCAN_MODE_LOW_LATENCY(~10ms)/SCAN_MODE_BALANCED(~100ms)/SCAN_MODE_LOW_POWER(~1s)

### 二、BLE连接

```
App: BluetoothGatt.connect()
→ btif_gatt.cc: btif_gatt_open(server_if, bd_addr, is_direct, transport)
→ BTA_GATTC_Open() → bta_gattc_act.cc: bta_gattc_open()
→ HCI: LE_Create_Connection
  - LE_Scan_Interval × 0.625ms (扫描间隔)
  - LE_Scan_Window × 0.625ms (扫描窗口)
  - Initiator_Filter_Policy (0=peer addr)
  - Own_Address_Type / Peer_Address_Type
  - Conn_Interval_Min/Max: 典型 7.5ms-4s
  - Conn_Latency: 0-499
  - Supervision_Timeout: 100ms-32s
→ LE Connection Complete Event
→ bta_gattc_conn_cback(connected=true)
→ btif_gatt_callbacks.client.open_cb(GATT_SUCCESS)
→ Java: onConnectionStateChange(CONNECTED)→BluetoothGattCallback
```

**连接参数更新**: conn_update_cback→btif_gattc_conn_update_cback→L2CAP: Connection Parameter Update Request

### 三、GATT服务发现

```
App: BluetoothGatt.discoverServices()
→ btif_gatt_discover_services()
→ BTA_GATTC_Discover() → bta_gattc_disc_res_cback
ATT消息序列:
1. ATT Read By Group Type Request (UUID=GATT_PRIMARY_SERVICE 0x2800)
   → Response: Handle范围 + Service UUID → 每个Service
2. ATT Read By Type Request (每个Service内, UUID=GATT_CHARACTERISTIC_DECLARATION 0x2803)
   → Response: Handle/Properties/Value Handle/UUID → 每个Characteristic
3. ATT Find Information Request (每个Char后, Handle+1 ~ 下一个Service前)
   → Response: Handle/UUID → Descriptors (0x2902 CCCD, 0x2904 Format, 等)

解析: → vector<BluetoothGattService> → BluetoothDevice.ServiceListener
缓存: service_changed → 刷新GATT缓存 (by GAP Service Changed)
```

**tGATT_CBACK 回调表** [bta_gattc_act.cc L72-L80]: p_conn_cb/p_cmpl_cb/p_disc_res_cb/p_disc_cmpl_cb/p_enc_cmpl_cb/p_congestion_cb/p_phy_update_cb/p_conn_update_cb

### 四、GATT读写操作

**读**:
```
readCharacteristic(char)
→ BTA_GATTC_Read(char_handle, GATT_AUTH_REQ_NONE)
→ ATT Read Request → Handle
→ ATT Read Response → Value
→ bta_gattc_cmpl_cback(GATTC_OPTYPE_READ)→回调Java: onCharacteristicRead
```

**写**:
```
writeCharacteristic(char, value)
→ writeType:
  WRITE_TYPE_DEFAULT → BTA_GATTC_Write(char_handle, value, GATT_WRITE) → ATT Write Request → Response
  WRITE_TYPE_NO_RESPONSE → ATT Write Command → 无确认/不回
→ bta_gattc_cmpl_cback→Java: onCharacteristicWrite (ONLY for WITH_RESPONSE)

Prepared Write: ATT Prepare Write→Execute Write→原子写多字节
Reliable Write: GATT_WRITE_PREPARE 重写的可取消版本
```

### 五、GATT通知

**注册通知**:
```
setCharacteristicNotification(char, enable=true)
→ writeDescriptor(CCCD 0x2902, value=0x0001[Notification] / 0x0002[Indication])
→ BTA_GATTC_Write CCCD_Handle
```

**Notification接收**:
```
远端发 ATT Handle Value Notification → GATT层自动→bta_gattc_process_indicate→onNotify
→ Java: onCharacteristicChanged(char)
```

**Indication** (需要确认):
```
ATT Handle Value Indication → onNotify → Java
→ ATT Handle Value Confirmation → 远端确认
（比Notification多一次往返，保证可靠送达）
```

### 六、GATT Server (车机作外设)

```
BluetoothGattServer:
1. openGattServer → gattServerIf 获得
2. addService(service) → ble_gatt_addSvc → BTA_GATTS_AddService
3. startAdvertising → gd/le_advertising_manager 开始广播
4. onConnectionStateChange → 接收client连接
5. onCharacteristicReadRequest → 读取车机数据: sendResponse
6. onCharacteristicWriteRequest → 接收数据: BTA_GATTS_Write
```

### 七、手机互联 GATT 应用

**HiCar**: BLE扫描特定UUID→GATT连接→读piCharacteristic(设备信息)→写wfCharacteristic(WiFi SSID/密码)→WiFi Direct连接
**CarPlay**: iAP2协议 BLE握手→交换Apple认证证书→WiFi参数→Disconnect BLE→connect AWDL WiFi
**通用模式**: BLE发现(广播指定UUID)→GATT握手(认证+参数交换)→WiFi切换(蓝牙保底心跳)

**关键代码**: btif_gatt.c→btgattInterface{.client/server/scanner/advertiser}，scanner/advertiser由GD层填充