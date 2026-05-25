# A.3 蓝牙 UUID 完整速查

> **速通摘要**：蓝牙 UUID 分为三类：① **16-bit UUID**（蓝牙 SIG 分配，最常用，节省字节）；② **32-bit UUID**（罕见）；③ **128-bit UUID**（自定义服务/Vendor 用）。Android 用 `ParcelUuid` 表示，底层 native 使用 `bluetooth::Uuid`（`system/types/include/bluetooth/types/uuid.h`）。本附录列出本仓库 `system/stack/include/bt_uuid16.h` 中所有 16-bit UUID 常量，以及 GATT 常用 128-bit UUID 模板。

---

## 一、UUID 三种长度的转换

```
16-bit UUID:  0x110B (A2DP Sink)
                 │
                 ▼
128-bit UUID: 0000110B-0000-1000-8000-00805F9B34FB
                 ^^^^
                 占用高 32 位的低 16 位

通用 Base UUID: 00000000-0000-1000-8000-00805F9B34FB
                          ─────────────────────────
                          这部分是 SIG 规定的固定后缀
```

Android 转换 API：
```java
ParcelUuid uuid = BluetoothUuid.parseUuidFrom(new byte[]{0x0B, 0x11});  // little-endian
// → 0000110B-0000-1000-8000-00805F9B34FB
```

---

## 二、Protocol UUID（16-bit）

| UUID | 名称 | 含义 | bt_uuid16.h:line |
|------|------|------|------------------|
| 0x0003 | RFCOMM | 串口仿真 | :21 |
| 0x0007 | ATT | Attribute Protocol（GATT 基础）| :28 |
| 0x0008 | OBEX | Object Exchange（PBAP/MAP/OPP）| :22 |
| 0x000F | BNEP | Bluetooth Network Encapsulation（PAN）| :23 |
| 0x0011 | HIDP | HID Profile | :24 |
| 0x0017 | AVCTP | AV Control Transport（AVRCP）| :25 |
| 0x0019 | AVDTP | AV Distribution Transport（A2DP）| :26 |
| 0x0100 | L2CAP | 逻辑链路控制 | :27 |

---

## 三、Classic 服务类 UUID（16-bit，最常用）

| UUID | 名称 | Profile | bt_uuid16.h:line |
|------|------|---------|------------------|
| 0x1000 | Service Discovery Server | SDP | :32 |
| 0x1101 | Serial Port | SPP（蓝牙串口）| :35 |
| 0x1105 | OBEX Object Push | OPP（文件推送）| :39 |
| 0x1108 | Headset | HSP | :42 |
| 0x110A | Audio Source | A2DP（手机方）| :44 |
| 0x110B | Audio Sink | A2DP（车机方）| :45 |
| 0x110C | AV Remote Control Target | AVRCP TG | :47 |
| 0x110D | Advanced Audio Distribution | A2DP（通用）| :49 |
| 0x110E | AV Remote Control | AVRCP CT/TG | :51 |
| 0x110F | AV Remote Control Controller | AVRCP CT | :53 |
| 0x1112 | Headset Audio Gateway | HSP AG | :56 |
| 0x1115 | PANU | PAN User | :59 |
| 0x1116 | NAP | PAN Network Access Point | :60 |
| 0x1117 | GN | PAN Group Network | :61 |
| 0x111E | Handsfree | HFP HF | :68 |
| 0x111F | Handsfree Audio Gateway | HFP AG | :69 |
| 0x1124 | Human Interface Device | HID | :74 |
| 0x112D | SIM Access | SAP | :87 |
| 0x112E | Phonebook Access PCE | PBAP Client（车机）| :88 |
| 0x112F | Phonebook Access PSE | PBAP Server（手机）| :89 |
| 0x1130 | Phonebook Access | PBAP 通用 | :90 |
| 0x1131 | Headset HS | HSP 1.2 HS 角色 | :91 |
| 0x1132 | Message Access | MAP MAS | :114 |
| 0x1133 | Message Notification | MAP MNS | :115 |
| 0x1134 | MAP Profile | MAP（通用）| :113 |
| 0x113A | Multi-Profile Specification - Profile | MPS | :92 |
| 0x113B | Multi-Profile Specification - SC | MPS | :93 |
| 0x1200 | PnP Information | Device Identification（DID）| :94 |

---

## 四、GATT 服务类 UUID（16-bit，BLE 端）

| UUID | 名称 | 含义 | bt_uuid16.h:line |
|------|------|------|------------------|
| 0x1800 | GAP Server | 通用接入（设备名等）| :117 |
| 0x1801 | GATT Server | GATT 框架自身 | :118 |
| 0x180A | Device Information | 设备信息服务 | :119 |
| 0x1812 | HID over LE | BLE HID（如键盘）| :120 |
| 0x1813 | Scan Parameter | 扫描参数 | :121 |
| 0x1844 | Volume Control Server | LE Audio VCP | :123 |
| 0x1849 | Generic Media Control Service | LE Audio GMCS | :124 |
| 0x184C | Generic Telephony Bearer Service | LE Audio GTBS | :125 |
| 0x1855 | TMAS Server | Telephone/Media Audio Service | :128 |
| 0x1858 | GMAS Server | Gaming Audio Service | :130 |
| 0x185B | RAS | Ranging Service（CS 测距上层）| :129 |

> **更多 LE Audio UUID**：CAS=0x1853、ASCS=0x184E、PACS=0x1850、BASS=0x184F、CSIS=0x1846 等不在本仓库 `bt_uuid16.h` 中（由 `system/bta/le_audio/` 直接用 128-bit 形式定义），见各 Profile 源码。

---

## 五、常用 GATT Characteristic UUID

| UUID | 名称 | 含义 |
|------|------|------|
| 0x2A00 | Device Name | 设备名 |
| 0x2A01 | Appearance | 外观（耳机/手表等图标）|
| 0x2A04 | Peripheral Preferred Connection Parameters | 偏好连接参数 |
| 0x2A19 | Battery Level | 电量百分比（0-100）|
| 0x2A29 | Manufacturer Name String | 厂商名 |
| 0x2A24 | Model Number String | 型号 |
| 0x2A25 | Serial Number String | 序列号 |
| 0x2A50 | PnP ID | PnP 信息 |

---

## 六、GATT Descriptor UUID

| UUID | 名称 | 含义 |
|------|------|------|
| 0x2900 | Characteristic Extended Properties | 扩展属性 |
| 0x2901 | Characteristic User Description | 文字描述 |
| **0x2902** | **Client Characteristic Configuration (CCC)** | **写 0x0001 启用 Notify，0x0002 启用 Indicate**（车机最常用）|
| 0x2903 | Server Characteristic Configuration | Server 端配置 |
| 0x2904 | Characteristic Presentation Format | 格式描述 |

---

## 七、Android 自定义 128-bit UUID 写法

```java
// Java：UUID.randomUUID() 生成新 UUID
UUID myService = UUID.fromString("E9F00001-EFB3-4F6E-A60B-DBBABD53D8C8");
ParcelUuid pUuid = new ParcelUuid(myService);

// 在 SDP 中注册
BluetoothServerSocket server = adapter.listenUsingRfcommWithServiceRecord(
    "MyService", myService);

// 在 BLE 广播中加入
AdvertiseData data = new AdvertiseData.Builder()
    .addServiceUuid(pUuid)
    .build();
```

```cpp
// Native（system/types/include/bluetooth/types/uuid.h）
#include <bluetooth/uuid.h>
using bluetooth::Uuid;

Uuid svc = Uuid::FromString("e9f00001-efb3-4f6e-a60b-dbbabd53d8c8").value();
```

---

## 八、车机典型 UUID 组合（用于 SDP/EIR 过滤）

| 车机功能 | SDP/EIR 中应包含的 UUID |
|----------|------------------------|
| 蓝牙音乐 | 0x110B (A2DP Sink) + 0x110E (AVRCP) |
| 蓝牙电话 | 0x111E (HFP HF) |
| 电话簿同步 | 0x112E (PBAP PCE) |
| 短信同步 | 0x1133 (MAP MNS) |
| 数字车钥匙 | 0x185B (RAS) + 自定义 128-bit UUID |
| HiCar/CarLink | 厂商自定义 128-bit UUID（不进 SIG）|

---

## 九、调试方法

```bash
# 查看已配对设备的 UUID 列表
adb shell dumpsys bluetooth_manager | grep -A 5 "Bonded devices"

# 抓 SDP 响应查看远端服务列表
# Wireshark filter: btsdp

# 查询 BLE 广播中的 UUID
adb logcat -s BluetoothLeScanner:V | grep -i "uuid"

# 解析 16-bit UUID 到名字
# 在 system/stack/include/bt_uuid16.h 中查 0x110B → AUDIO_SINK
```

---

## FAQ

**Q1：UUID 0x110D 和 0x110B 都和 A2DP 有关，差异？**
0x110D（Advanced Audio Distribution）是 A2DP **通用**类，表示设备支持 A2DP 但角色未定；0x110A（Audio Source）和 0x110B（Audio Sink）分别表示发送/接收方。SDP 记录中通常会同时声明 0x110D + 0x110B（车机）或 0x110D + 0x110A（手机）。

**Q2：BLE 广播包里 UUID 占用多少字节？**
- 16-bit UUID：2 字节（一个广播包能放 14 个左右）
- 128-bit UUID：16 字节（一个 31 字节 ADV 包只能放 1-2 个）
所以车机自定义服务广播时，要么用 16-bit（SIG 分配，昂贵），要么用 128-bit + Service Data 短数据。

**Q3：UUID 0x2902（CCC）为什么这么常见？**
所有支持 Notify 或 Indicate 的 Characteristic 必须配一个 CCC 描述符。客户端不写 CCC（0x0001）就不会收到 Notify。漏写是 BLE 调试最常见的 bug。

---

## 上路任务

1. 阅读完整的 `system/stack/include/bt_uuid16.h`，挑出"车机端必须支持"的 6 个 UUID（蓝牙音乐 + 电话 + 电话簿 + 短信）。
2. 用 `adb shell dumpsys bluetooth_manager | grep Uuids` 查看已配对的某台手机 SDP 暴露了哪些服务，把每个 UUID 翻译成名字。
3. 用 BLE 调试工具（nRF Connect）连一台 BLE 外设，查看它有哪些 GATT 服务和特征，找 0x2902 CCC，理解写入 0x0001 后 Notify 才生效的现象。
