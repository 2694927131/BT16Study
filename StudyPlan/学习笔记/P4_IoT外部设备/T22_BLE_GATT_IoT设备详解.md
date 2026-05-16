# T22 BLE GATT IoT设备详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：TPMS/传感器 GATT Service设计 | 控制类IoT(座椅/空调) GATT Write+Notify | 数字钥匙 BLE+Channel Sounding方案 | RangingHal架构(4Mode/6Callback) | BLE Mesh车载场景
> 待回顾问题：无

---

## 1. BLE GATT IoT架构

```
车机 (GATT Client, 中央设备)
  │ 同时连接多个BLE IoT设备
  │
  ├── TPMS 胎压传感器 → 读取胎压/温度 (Notification)
  ├── 温湿度传感器    → 读取环境数据 (Notification)
  ├── 健康监测设备    → 读取心率/血氧   (Notification)
  ├── 座椅控制器      → 写入调节指令    (Write) + 读取状态 (Read)
  ├── 空调控制器      → 写入温度/风速   (Write) + 读取状态 (Read)
  └── 数字钥匙        → GATT认证 + Ranging测距
```

**BLE连接能力**：
- 理论上支持多连接（Android 8+支持最多7个同时BLE连接）
- 每个连接有独立的 GATT Client 实例 + Connection Handle

---

## 2. BLE 传感器设备

### 2.1 TPMS 胎压监测

**GATT Service设计**：

```
Primary Service: Tire Pressure Service (自定义UUID)

Characteristic: Tire Pressure (Read | Notify)
  Descriptor: CCCD (0x2902) → 启用Notification
  Value格式:
    Byte 0-1: Tire ID (左前=0, 右前=1, 左后=2, 右后=3)
    Byte 2-3: Pressure (kPa, uint16, 例: 235kPa)
    Byte 4: Temperature (°C, int8, 偏移+40)
    Byte 5: Battery Level (%)
    Byte 6: Alarm Flags (bit0=低压, bit1=高温, bit2=快漏气)

Characteristic: Sensor Location (Read)
  Value: 4字节, 每个字节代表传感器安装位置
    0x00=左前, 0x01=右前, 0x02=左后, 0x03=右后

Characteristic: Alarm Threshold (Read | Write)
  Value:
    Byte 0-1: Low Pressure Threshold (kPa)
    Byte 2-3: High Temperature Threshold (°C+40)
```

**车载连接流程**：

```
1. 车机上电 → BLE扫描 → 过滤TPMS Service UUID
2. 发现传感器 → GATT连接 → 服务发现
3. 订阅Tire Pressure Characteristic Notification (写CCCD=0x0001)
4. 设置Alarm Threshold (Write)
5. 传感器定期上报 (如每30秒或压力变化时)
6. 车机接收Notification → 解析胎压值 → 显示/报警
```

**典型数据上报频率**：
```
正常模式: 每30-60秒 (省电)
运动模式: 压力变化>10kPa时立即上报
报警模式: 低于阈值时持续上报(每1-2秒)
```

### 2.2 温湿度传感器

**GATT Service设计**：

```
Primary Service: Environmental Sensing Service (0x181A)
  ├── Temperature Characteristic (0x2A6E) → int16, °C×100
  ├── Humidity Characteristic (0x2A6F) → uint16, %×100
  └── 可选: Pressure (0x2A6D), PM2.5 (自定义UUID)

车载场景: 车内/车外温度检测, 自动空调控制
```

### 2.3 车载健康监测设备

```
Primary Service: Health Thermometer (0x1809)
  ├── Temperature Measurement (0x2A1C) → Indicate (需确认)
  └── Measurement Interval (0x2A21) → Write

Primary Service: Heart Rate (0x180D)
  ├── Heart Rate Measurement (0x2A37) → Notify
  ├── Body Sensor Location (0x2A38) → Read
  └── Heart Rate Control Point (0x2A39) → Write

车载场景: 驾驶员健康监测(疲劳驾驶/突发疾病预警)
```

---

## 3. BLE 控制设备

### 3.1 座椅调节

**GATT Service设计**：

```
Primary Service: Seat Control Service (自定义UUID)

Characteristic: Seat Position (Read | Write | Notify)
  由App作为GATT Client发起Write写入控制指令
  Value (控制指令格式):
    Byte 0: Seat ID (0=主驾, 1=副驾, 2=后排左, 3=后排右)
    Byte 1: Command (0x01=前后, 0x02=高度, 0x03=靠背, 0x04=腰托, 0x05=记忆)
    Byte 2-3: Value (前后位置mm, 高度mm, 角度°, 腰托强度%)
    
Characteristic: Seat Status (Read | Notify)
  Value (状态回读):
    Byte 0-1: Current Front/Back Position (mm)
    Byte 2-3: Current Height (mm)
    Byte 4-5: Current Backrest Angle (°/10)
    Byte 6: Heating Level (0-3)
    Byte 7: Ventilation Level (0-3)

Characteristic: Seat Memory (Write)
  Value: Memory Slot (1-3), Command (0x01=Save, 0x02=Recall)
```

**通信流程**：
```
用户按"座椅前移"按钮
  ↓
车机App → GATT Write (Seat Position) 
  → Command=0x01(前后), Value=+10mm
  ↓
座椅ECU收到Write → 执行移动 
  ↓
移动完成 → ECU发送GATT Notification (Seat Status)
  ↓
车机App收到Notification → 更新UI显示
```

### 3.2 空调控制

**GATT Service设计**：

```
Primary Service: Climate Control Service (自定义UUID)

Characteristic: Climate Settings (Write)
  Value:
    Byte 0: Mode (0=OFF, 1=COOL, 2=HEAT, 3=AUTO, 4=FAN)
    Byte 1: Target Temperature (°C+40, 例: 24°C=64)
    Byte 2: Fan Speed (0=AUTO, 1-7=手动档位)
    Byte 3: Zone (0=ALL, 1=LEFT, 2=RIGHT, 3=REAR)
    Byte 4: AC On/Off + Recirculate (bit0=AC, bit1=Recirc)

Characteristic: Climate Status (Read | Notify)
  Value:
    Byte 0-1: Interior Temperature (°C×100)
    Byte 2-3: Exterior Temperature (°C×100)
    Byte 4: Current Fan Speed
    Byte 5: Current Mode
```

### 3.3 车窗/天窗控制

```
Primary Service: Window Control Service (自定义UUID)

Characteristic: Window Command (Write)
  Value:
    Byte 0: Window ID (0=FL, 1=FR, 2=RL, 3=RR, 4=Sunroof)
    Byte 1: Command (0x01=UP, 0x02=DOWN, 0x03=STOP, 0x04=AUTO_UP, 0x05=AUTO_DOWN)
    Byte 2: Position % (0-100, 用于设置到指定位置)

Characteristic: Window Status (Read | Notify)
  Value:
    Byte 0: Position % (0=全关, 100=全开)
    Byte 1: Flags (bit0=防夹触发, bit1=学习中, bit2=故障)
```

---

## 4. 蓝牙数字钥匙 (Bluetooth Digital Key)

### 4.1 方案架构

新一代数字钥匙采用 **BLE + Channel Sounding (CS)** 组合方案：

```
蓝牙数字钥匙 = BLE 通信 + CS测距 + 安全认证

BLE → 通信通道:
  ├── 密钥交换 (SMP LE Secure Connections)
  ├── 设备发现 (Advertising + Scan)
  └── 数据交互 (GATT读写)

Channel Sounding → 精确定位:
  ├── 测量手机与车机的精确距离 (cm级别)
  ├── 判断用户是否在车内/车外
  └── 防止中继攻击(Relay Attack)

安全认证 → 数字钥匙协议 (CCC Digital Key规范):
  ├── 车主钥匙 → 完全权限
  ├── 朋友钥匙 → 限制权限(时间/功能)
  └── 代驾钥匙 → 临时权限
```

### 4.2 BLE GATT Service设计（数字钥匙）

```
Primary Service: Digital Key Service (自定义UUID)

Characteristic: Key Authentication (Write | Indicate)
  → 证书交换 + 挑战-响应认证
  Value: ECDSA签名 + 证书链

Characteristic: Key Status (Read | Notify)
  → 当前授权状态
  Value: 权限级别 + 有效期 + 功能掩码

Characteristic: Vehicle Command (Write | Indicate)
  → 解锁/上锁/启动命令
  Value: 命令码 + AES-CCM加密载荷 + 序列号(防重放)
```

### 4.3 Channel Sounding 测距

**RangingHal核心接口**（[ranging_hal.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal.h)）：

```cpp
// Channel Sounding 测量模式
enum class RangingMode {
    MODE_1 = 1,  // 单向测距(One-way RTT)
    MODE_2 = 2,  // 双向测距(Two-way RTT)
    MODE_3 = 3,  // 相位测距(Phase-based, PBR) ← 精度最高
};

// 测量结果
struct RangingResult {
    double result_meters_;              // 距离(米), 精度可达cm级
    double error_meters_;              // 误差(米)
    int8_t confidence_level_;          // 置信度(0-100, -1不可用)
    double delay_spread_meters_;       // 时延扩散
    uint8_t detected_attack_level_;    // 攻击检测级别(中继攻击)
    double velocity_meters_per_second_; // 相对速度(m/s)
    int64_t elapsed_timestamp_nanos_;  // 时间戳
};

// RangingHal主要接口
class RangingHal {
    void OpenSession(connection_handle, mode, duration, interval, ...);
    void RegisterCallback(RangingHalCallback* callback);
    std::vector<RangingSessionType> GetSupportedSessionTypes();
};

class RangingHalCallback {
    void OnOpened(...);
    void OnResult(connection_handle, const RangingResult& result);
    void OnClosed(connection_handle, Reason reason);
};
```

**数字钥匙距离区域**：

```
手机与车机距离判断:
  > 10m: 远距离区域 → BLE Advertising扫描(低频轮询)
  3-10m: 接近区域 → BLE连接 + 低频CS测距(每5秒)
  1-3m: 靠近区域 → 高频CS测距(每500ms), 准备解锁
  < 1m: 车门区域 → 持续CS测距, 自动解锁
  -0.5~0.5m: 车内/外判断 → 允许启动发动机
```

### 4.4 安全认证流程

```
1. BLE Advertising: 手机广播 包含数字钥匙Service UUID

2. 车机扫描 → 发现手机 → BLE连接

3. LE Secure Connections (LE SC) 配对:
   ECDH密钥交换 → LTK生成 → 加密链路

4. GATT 服务发现 → 找到 Digital Key Service

5. 认证挑战-响应:
   车机 → Write (Key Authentication): 随机Challenge + 车主公钥
   手机 → Indication: ECDSA签名(challenge) + 证书
   车机验证签名 → 确认身份

6. 权限确认:
   车机 → Read (Key Status) → 确认权限级别和有效期

7. 持续测距(Ranging):
   车机 → OpenSession → 启动CS测距
   根据距离判断解锁/启动时机

8. 功能命令:
   车机 → Write (Vehicle Command): 加密的"解锁"命令
   手机 → Indication: 确认执行
```

---

## 5. BLE Mesh 车载场景

### 5.1 BLE Mesh概述

BLE Mesh基于BLE Advertising承载，**不需要BLE连接**，通过洪泛(Flooding)或路由(Routing)在节点间转发消息。

```
传统BLE: 星型拓扑 (1个Central连接多个Peripheral)
BLE Mesh: 网状拓扑 (节点间直接通信, 无需Central)

节点类型:
  Relay Node   → 转发消息(扩展覆盖范围)
  Proxy Node   → GATT Proxy → 手机App通过GATT接入Mesh网络
  Friend Node  → 为低功耗节点(LPN)缓存消息
  Low Power Node (LPN) → 电池供电, 定期唤醒查询消息
```

### 5.2 车载BLE Mesh应用场景

```
1. 车内灯光控制:
   Mesh节点: 每个氛围灯模块
   Model: Generic OnOff + Generic Level (亮度)
   → 手机/车机通过Proxy Node控制全车氛围灯

2. 传感器网络:
   Mesh节点: 温度/湿度/CO2传感器分布全车
   Model: Sensor Server → Sensor Client 读取
   → 车机收集各区域数据, 优化空调策略

3. 胎压组网:
   Mesh节点: 4个轮胎TPMS传感器
   → 通过Mesh转发解决金属车身遮挡问题

4. 座椅/后视镜/车窗联动:
   Mesh节点: 座椅模块/后视镜/车窗
   → 一键场景联动(记忆座椅+后视镜+方向盘)
```

### 5.3 Mesh消息模型

```
Foundation Models (规范定义):
  Configuration Server: 管理节点/AppKey/Publication/Subscription
  Health Server: 节点健康状态/故障上报

Standard Models:
  Generic OnOff Server/Client: 开关控制
  Generic Level Server/Client:  数值控制(0-65535)
  Sensor Server/Client:         传感器数据

Vendor Models:
  自定义模型, 用于车载特有功能
  如: Seat Position Model, Window Control Model
```

---

## 6. GATT Server端实现（车机作为Peripheral）

### 6.1 add_service流程

源码：[btif_gatt_server.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_gatt_server.cc)

```cpp
// GATT Server接口表
const btgatt_server_interface_t btgattServerInterface = {
    btif_gatts_register_app,      // 注册Server应用
    btif_gatts_unregister_app,    // 注销
    btif_gatts_open,              // 打开连接
    btif_gatts_close,             // 关闭连接
    btif_gatts_add_service,       // 添加GATT Service ← 核心
    btif_gatts_stop_service,      // 停止Service
    btif_gatts_delete_service,    // 删除Service
    btif_gatts_send_indication,   // 发送Indication(需要确认)
    btif_gatts_send_response      // 响应Read/Write请求
};

// add_service内部实现
static void add_service_impl(int server_if, vector<btgatt_db_element_t> service) {
    // 安全检查: 禁止注册GATT_SERVER和GAP_SERVER内置服务
    if (service[0].uuid == Uuid::From16Bit(UUID_SERVCLASS_GATT_SERVER) ||
        service[0].uuid == Uuid::From16Bit(UUID_SERVCLASS_GAP_SERVER)) {
        // 拒绝: BT_STATUS_AUTH_REJECTED
        return;
    }
    BTA_GATTS_AddService(server_if, service, on_service_added_cb);
}
```

### 6.2 车机作为IoT Server示例

```java
// 车机注册为TPMS数据采集Server
BluetoothGattServer server = manager.openGattServer(context, callback);

// 定义Service
BluetoothGattService tpmsService = new BluetoothGattService(
    UUID.fromString("0000XXXX-0000-1000-8000-00805F9B34FB"),
    BluetoothGattService.SERVICE_TYPE_PRIMARY);

// 添加Characteristic: Tire Pressure (Notify)
BluetoothGattCharacteristic pressureChar = new BluetoothGattCharacteristic(
    UUID.fromString("..."),
    BluetoothGattCharacteristic.PROPERTY_READ | 
    BluetoothGattCharacteristic.PROPERTY_NOTIFY,
    BluetoothGattCharacteristic.PERMISSION_READ);

// 添加CCCD Descriptor
pressureChar.addDescriptor(
    new BluetoothGattDescriptor(
        UUID.fromString("00002902-0000-1000-8000-00805F9B34FB"),
        BluetoothGattDescriptor.PERMISSION_READ | 
        BluetoothGattDescriptor.PERMISSION_WRITE));

tpmsService.addCharacteristic(pressureChar);
server.addService(tpmsService);

// 手机订阅后 → 发送胎压数据
server.notifyCharacteristicChanged(device, pressureChar, false, pressureData);
```

---

## 7. BLE IoT常见问题

### 7.1 BLE设备连接不稳定

```
原因分析:
1. Connection Interval 过大 → 响应慢
2. Supervision Timeout 过短 → 超时断连
3. Slave Latency 过大 → 丢事件
4. 金属车身遮挡 → 信号衰减

推荐参数(车载IoT):
  Connection Interval Min: 15ms
  Connection Interval Max: 30ms
  Slave Latency: 0 (不允许跳过)
  Supervision Timeout: 2000ms

定位方法:
  Snoop: HCI LE Connection Update → 查看实际协商参数
  BQR: 查看RSSI和no_rx_count
```

### 7.2 GATT操作超时

```
原因分析:
1. ATT请求未收到Response → 30秒超时
2. GATT队列拥堵 → 前一个操作未完成
3. MTU太小 → 大数据分多次传输, 效率低

解决:
  → 连接后立即请求MTU交换(建议MTU=512)
  → 避免同时发起多个GATT操作, 使用串行队列
  → 长数据使用Read Long Characteristic/Write Long Characteristic

源码:
  bta_gattc_queue.cc → GATT操作队列管理
```

### 7.3 数据解析错误

```
原因分析:
1. 字节序错误 → Little Endian vs Big Endian
2. 数据类型错误 → int16当作uint16解析
3. 偏移计算错误 → Characteristic Value中多字段的offset

解决:
  → 使用ByteBuffer并明确指定字节序
  → 参照BT SIG规范确认数据类型
  → 使用Wireshark查看原始ATT Value验证

示例:
  // 胎压值: Byte 0-1 = uint16 little-endian, 单位kPa
  int pressure = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN).getShort() & 0xFFFF;
```

### 7.4 功耗优化

```
BLE IoT电池续航优化:

1. Connection Parameter优化:
   - 适当增大Interval (如30ms→100ms, 传感器不需要高频)
   - 允许Latency (如Latency=4, 每5个Interval才必须响应一次)

2. Advertising优化:
   - 降低Advertising Interval (如100ms→1000ms)
   - 仅在数据变化时Advertising (非持续广播)

3. GATT操作优化:
   - 减少不必要Read (通过Notification感知变化)
   - 合并多个Characteristic读取 (一次Read Multiple)
```

---

## 8. IoT调试速查

### 日志TAG
```bash
# BLE IoT全栈日志
adb logcat -s bt_btif_gatt bt_bta_gattc bt_bta_gatts gatt btle
```

### Snoop过滤器
```
# BLE连接
btle || btatt

# 特定GATT Service
btatt.handle >= 0x0010 && btatt.handle <= 0x0020

# Notification/Indication数据
btatt.opcode == 0x1B  # Handle Value Notification
btatt.opcode == 0x1D  # Handle Value Indication

# 特定设备的所有BLE交互
(btle || btatt) && bt.addr == XX:XX:XX:XX:XX:XX
```

### 车载IoT命令速查
```bash
# 扫描BLE设备
adb shell cmd bluetooth_manager scan ble

# 查看已连接BLE设备
adb shell dumpsys bluetooth_manager | grep "GATT"

# 测试GATT服务发现
adb shell cmd bluetooth_manager gatt connect XX:XX:XX:XX:XX:XX
adb shell cmd bluetooth_manager gatt discover XX:XX:XX:XX:XX:XX
```