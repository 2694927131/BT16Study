# Android Bluetooth GATT 全面扫盲教材

> 面向车企蓝牙Framework开发工程师，基于Android 16源码，覆盖GATT协议基础、Framework架构、核心类详解、应用层对接方式及后排屏遥控场景分析

---

## 目录

- [第一部分：GATT协议基础](#第一部分gatt协议基础)
  - [1.1 BLE与GATT的关系](#11-ble与gatt的关系)
  - [1.2 GATT核心概念](#12-gatt核心概念)
  - [1.3 GATT角色：Client与Server](#13-gatt角色client与server)
  - [1.4 GATT数据层次结构](#14-gatt数据层次结构)
  - [1.5 ATT协议与GATT的关系](#15-att协议与gatt的关系)
  - [1.6 GATT操作类型](#16-gatt操作类型)
  - [1.7 UUID体系](#17-uuid体系)
  - [1.8 GATT连接参数](#18-gatt连接参数)
- [第二部分：Android GATT Framework架构](#第二部分android-gatt-framework架构)
  - [2.1 整体分层架构](#21-整体分层架构)
  - [2.2 各层文件清单与职责](#22-各层文件清单与职责)
  - [2.3 核心调用链路分析](#23-核心调用链路分析)
  - [2.4 AIDL接口设计](#24-aidl接口设计)
  - [2.5 JNI桥接层](#25-jni桥接层)
  - [2.6 Rust新架构](#26-rust新架构)
- [第三部分：Framework核心类详解](#第三部分framework核心类详解)
  - [3.1 BluetoothGatt（GATT客户端）](#31-bluetoothgattgatt客户端)
  - [3.2 BluetoothGattCallback（客户端回调）](#32-bluetoothgattcallback客户端回调)
  - [3.3 BluetoothGattServer（GATT服务端）](#33-bluetoothgattservergatt服务端)
  - [3.4 BluetoothGattServerCallback（服务端回调）](#34-bluetoothgattservercallback服务端回调)
  - [3.5 BluetoothGattService（服务数据模型）](#35-bluetoothgattservice服务数据模型)
  - [3.6 BluetoothGattCharacteristic（特征数据模型）](#36-bluetoothgattcharacteristic特征数据模型)
  - [3.7 BluetoothGattDescriptor（描述符数据模型）](#37-bluetoothgattdescriptor描述符数据模型)
  - [3.8 GattService（系统服务实现）](#38-gattservice系统服务实现)
  - [3.9 GattNativeInterface（JNI桥接）](#39-gattnativeinterfacejni桥接)
  - [3.10 ContextMap与HandleMap](#310-contextmap与handlemap)
- [第四部分：应用层对接GATT的方式](#第四部分应用层对接gatt的方式)
  - [4.1 GATT客户端完整对接流程](#41-gatt客户端完整对接流程)
  - [4.2 GATT服务端完整对接流程](#42-gatt服务端完整对接流程)
  - [4.3 BLE扫描对接](#43-ble扫描对接)
  - [4.4 BLE广播对接](#44-ble广播对接)
  - [4.5 权限要求](#45-权限要求)
  - [4.6 完整代码示例](#46-完整代码示例)
- [第五部分：后排屏遥控场景分析](#第五部分后排屏遥控场景分析)
  - [5.1 场景需求分析](#51-场景需求分析)
  - [5.2 架构方案设计](#52-架构方案设计)
  - [5.3 GATT服务设计](#53-gatt服务设计)
  - [5.4 多遥控器管理](#54-多遥控器管理)
  - [5.5 关键技术点](#55-关键技术点)
- [附录](#附录)

---

# 第一部分：GATT协议基础

## 1.1 BLE与GATT的关系

蓝牙低功耗（BLE，Bluetooth Low Energy）协议栈中，GATT（Generic Attribute Profile）是最核心的应用层协议之一。理解其定位需要先看BLE协议栈的整体分层：

```
┌─────────────────────────────────────────┐
│            应用层 (Application)          │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ │
│  │  GATT    │ │   SMP    │ │   GAP   │ │
│  │(属性协议)│ │(安全管理)│ │(通用访问)│ │
│  └────┬─────┘ └──────────┘ └─────────┘ │
│       │                                  │
│  ┌────▼─────┐                           │
│  │   ATT    │  (属性传输协议)            │
│  └────┬─────┘                           │
├───────┼──────────────────────────────────┤
│       │      主机层 (Host)               │
│  ┌────▼─────┐                           │
│  │   L2CAP  │  (逻辑链路控制适配协议)    │
│  └────┬─────┘                           │
│  ┌────▼─────┐                           │
│  │   HCI    │  (主机控制器接口)          │
│  └────┬─────┘                           │
├───────┼──────────────────────────────────┤
│       │      控制器层 (Controller)       │
│  ┌────▼─────┐ ┌──────────┐              │
│  │   Link   │ │    PHY   │              │
│  │  Layer   │ │ (物理层) │              │
│  └──────────┘ └──────────┘              │
└─────────────────────────────────────────┘
```

**关键关系**：
- **GATT** 建立在 **ATT**（Attribute Protocol）之上，定义了如何组织和交换数据的框架
- **ATT** 是底层传输协议，定义了属性（Attribute）的读写操作
- **GATT** 是ATT的上层封装，定义了Service/Characteristic/Descriptor的数据组织方式
- 所有BLE数据交换都通过GATT进行（除非使用ISOC通道如LE Audio）

## 1.2 GATT核心概念

GATT的核心思想是**一切皆属性（Attribute）**。每个属性由以下要素组成：

| 要素 | 说明 |
|------|------|
| **Handle** | 属性句柄，16位无符号整数，唯一标识一个属性，由协议栈自动分配 |
| **Type** | 属性类型，用UUID表示（如0x2800表示Primary Service） |
| **Value** | 属性值，最大512字节（实际受MTU限制） |
| **Permissions** | 访问权限（可读/可写/可通知等） |

GATT将这些属性按层次组织为Service → Characteristic → Descriptor的结构。

## 1.3 GATT角色：Client与Server

GATT定义了两个角色：

```
┌──────────────┐                    ┌──────────────┐
│  GATT Client │                    │  GATT Server │
│  (主动方)    │                    │  (数据提供方) │
│              │   Read/Write       │              │
│  发现服务    │ ──────────────────> │  提供服务    │
│  读写特征    │   Notification     │  存储数据    │
│  接收通知    │ <────────────────── │  发送通知    │
│              │   Indication       │              │
│              │ <────────────────── │  发送指示    │
└──────────────┘                    └──────────────┘
```

| 角色 | 职责 | 典型场景 |
|------|------|----------|
| **GATT Client** | 发起连接、发现服务、读写数据、接收通知 | 手机App连接心率带 |
| **GATT Server** | 提供服务数据、响应读写、发送通知/指示 | 心率带提供心率数据 |

**重要**：GATT角色与GAP角色是独立的！
- 一个设备可以同时是GAP Central和GATT Server
- 一个设备可以同时是GAP Peripheral和GATT Client
- 一个设备可以同时充当GATT Client和GATT Server（双角色）

**在后排屏遥控场景中**：
- 车机屏幕端 → GATT Server（提供遥控服务，接收遥控指令）
- 遥控器（物理/手机）→ GATT Client（连接车机，发送遥控指令）

## 1.4 GATT数据层次结构

GATT的数据组织遵循严格的层次结构：

```
GATT Server
│
├── Primary Service (主要服务，UUID: 0x2800)
│   │
│   ├── Characteristic (特征)
│   │   ├── Characteristic Value (特征值)
│   │   ├── Characteristic Declaration (特征声明, UUID: 0x2803)
│   │   └── Descriptor(s) (描述符)
│   │       ├── Client Characteristic Configuration (CCCD, UUID: 0x2902)
│   │       ├── Characteristic User Description (UUID: 0x2901)
│   │       └── Characteristic Presentation Format (UUID: 0x2904)
│   │
│   ├── Another Characteristic
│   │   └── ...
│   │
│   └── Included Service (包含服务, UUID: 0x2802)
│       └── (引用另一个Service)
│
├── Secondary Service (次要服务, UUID: 0x2801)
│   └── ...
│
└── Another Primary Service
    └── ...
```

### 1.4.1 Service（服务）

- **Primary Service**：对外公开的服务，可被其他设备发现
- **Secondary Service**：仅在被其他服务引用时可见，不独立对外
- 每个Service由UUID唯一标识
- Service可以包含多个Characteristic和Included Service

### 1.4.2 Characteristic（特征）

- GATT中最核心的数据单元
- 包含一个值（Value）和0到多个Descriptor
- 通过Properties字段声明支持的操作类型（读/写/通知/指示等）

**Properties位定义**：

| 位 | 名称 | 说明 |
|----|------|------|
| 0 | BROADCAST | 可广播 |
| 1 | READ | 可读 |
| 2 | WRITE_NO_RESPONSE | 可写（无响应） |
| 3 | WRITE | 可写（有响应） |
| 4 | NOTIFY | 可通知 |
| 5 | INDICATE | 可指示 |
| 6 | AUTHENTICATED_SIGNED_WRITES | 认证签名写 |
| 7 | EXTENDED_PROPERTIES | 扩展属性 |

### 1.4.3 Descriptor（描述符）

- 对Characteristic的补充描述
- 最重要的是**CCCD**（Client Characteristic Configuration Descriptor，UUID: 0x2902）
  - 写入`0x0001`开启Notification
  - 写入`0x0002`开启Indication
  - 写入`0x0000`关闭通知/指示

### 1.4.4 完整属性表示例

以一个"遥控服务"为例，其GATT属性表如下：

| Handle | Type (UUID) | Permissions | Value |
|--------|-------------|-------------|-------|
| 0x0001 | 0x2800 (Primary Service) | READ | 遥控服务UUID |
| 0x0002 | 0x2803 (Characteristic Declaration) | READ | Properties=0x1C (READ\|WRITE\|NOTIFY), Value Handle=0x0003, UUID=按键特征UUID |
| 0x0003 | 按键特征UUID | READ/WRITE/NOTIFY | 按键值 |
| 0x0004 | 0x2902 (CCCD) | READ/WRITE | 0x0000 (通知关闭) |
| 0x0005 | 0x2803 (Characteristic Declaration) | READ | Properties=0x02 (READ), Value Handle=0x0006, UUID=电量特征UUID |
| 0x0006 | 电量特征UUID | READ | 电量值 |
| 0x0007 | 0x2902 (CCCD) | READ/WRITE | 0x0000 |

## 1.5 ATT协议与GATT的关系

ATT（Attribute Protocol）是GATT的底层传输协议：

| 维度 | ATT | GATT |
|------|-----|------|
| 层级 | 传输协议 | 应用框架 |
| 数据模型 | 扁平的属性列表 | Service/Characteristic/Descriptor层次结构 |
| 操作 | Read/Write/Find/Notify/Indicate | 基于ATT操作，增加语义约束 |
| 寻址 | Handle（句柄） | UUID + Handle |
| 数据长度 | ATT MTU（默认23字节，有效载荷20字节） | 受ATT MTU限制 |

**ATT PDU类型**：

| 方向 | PDU类型 | 说明 |
|------|---------|------|
| Client→Server | Read Request | 请求读取单个属性 |
| Client→Server | Read By Type Request | 按UUID类型读取 |
| Client→Server | Read By Group Type Request | 按组类型读取（发现Service） |
| Client→Server | Write Request | 写入属性（需响应） |
| Client→Server | Write Command | 写入属性（无需响应） |
| Client→Server | Find Information Request | 查找属性信息 |
| Client→Server | Prepare Write Request | 准备写入（长值分片） |
| Client→Server | Execute Write Request | 执行准备写入 |
| Server→Client | Read Response | 读取响应 |
| Server→Client | Write Response | 写入响应 |
| Server→Client | Notification | 通知（无需确认） |
| Server→Client | Indication | 指示（需确认） |
| Server→Client | Error Response | 错误响应 |

## 1.6 GATT操作类型

### 1.6.1 服务发现

```
Client                                    Server
  │                                          │
  │── Read By Group Type Request ──────────>│  (UUID=0x2800, 发现Primary Service)
  │<── Read By Group Type Response ─────────│  (返回Service范围)
  │                                          │
  │── Find By Type Value Request ──────────>│  (按UUID值查找)
  │<── Find By Type Value Response ─────────│
  │                                          │
  │── Read By Type Request ────────────────>│  (UUID=0x2803, 发现Characteristic)
  │<── Read By Type Response ───────────────│
  │                                          │
  │── Find Information Request ─────────────>│  (发现Descriptor)
  │<── Find Information Response ────────────│
```

### 1.6.2 读写操作

```
Client                                    Server
  │                                          │
  │── Read Request (Handle=0x0003) ────────>│  (读取特征值)
  │<── Read Response ────────────────────────│  (返回值)
  │                                          │
  │── Write Request (Handle=0x0003) ────────>│  (写入特征值，需响应)
  │<── Write Response ───────────────────────│  (写入确认)
  │                                          │
  │── Write Command (Handle=0x0003) ────────>│  (写入特征值，无需响应)
  │                                          │
```

### 1.6.3 通知与指示

```
Client                                    Server
  │                                          │
  │── Write Request (CCCD=0x0001) ─────────>│  (开启Notification)
  │<── Write Response ───────────────────────│
  │                                          │
  │<── Notification (Handle=0x0003) ─────────│  (Server主动推送，无需确认)
  │                                          │
  │── Write Request (CCCD=0x0002) ─────────>│  (开启Indication)
  │<── Write Response ───────────────────────│
  │                                          │
  │<── Indication (Handle=0x0003) ──────────│  (Server主动推送，需确认)
  │── Write Request (Confirmation) ─────────>│  (隐式确认)
  │                                          │
```

**Notification vs Indication**：

| 维度 | Notification | Indication |
|------|-------------|------------|
| 可靠性 | 不确认，可能丢失 | 需确认，可靠送达 |
| 速度 | 快，无等待 | 慢，等待确认后才能发下一个 |
| 并发 | 可连续发送 | 同一时间只能有一个未确认的Indication |
| 适用场景 | 高频数据（如心率） | 重要控制指令 |

### 1.6.4 可靠写（Reliable Write）

用于需要原子性写入多个特征值的场景：

```
Client                                    Server
  │                                          │
  │── Prepare Write Request (Handle+Value) ─>│  (准备写入第1个)
  │<── Prepare Write Response ───────────────│
  │── Prepare Write Request (Handle+Value) ─>│  (准备写入第2个)
  │<── Prepare Write Response ───────────────│
  │── Execute Write Request (flag=1) ───────>│  (提交所有写入)
  │<── Execute Write Response ───────────────│
  │                                          │
  // 或者取消
  │── Execute Write Request (flag=0) ───────>│  (取消所有写入)
  │<── Execute Write Response ───────────────│
```

## 1.7 UUID体系

UUID（Universally Unique Identifier）用于标识Service和Characteristic的类型：

| 类型 | 长度 | 格式 | 示例 |
|------|------|------|------|
| **SIG标准UUID** | 16位 | 0xXXXX | 0x180F (Battery Service) |
| **SIG标准UUID完整** | 128位 | XXXXXXXX-0000-1000-8000-00805F9B34FB | 0000180F-0000-1000-8000-00805F9B34FB |
| **自定义UUID** | 128位 | 自定义格式 | 12345678-1234-5678-1234-567812345678 |

**SIG标准UUID转换规则**：16位UUID `0xXXXX` 对应128位UUID `0000XXXX-0000-1000-8000-00805F9B34FB`

**常用SIG标准UUID**：

| 16位UUID | 名称 | 说明 |
|----------|------|------|
| 0x1800 | Generic Access | 通用访问服务 |
| 0x1801 | Generic Attribute | 通用属性服务（含Service Changed特征） |
| 0x180A | Device Information | 设备信息服务 |
| 0x180F | Battery Service | 电池服务 |
| 0x1812 | HID Service | 人机接口设备服务（键盘/鼠标/遥控器） |
| 0x1813 | Scan Parameters | 扫描参数服务 |
| 0x2902 | CCCD | 客户端特征配置描述符 |

**自定义UUID建议**：为后排屏遥控功能定义专用的128位UUID，避免与标准UUID冲突。

## 1.8 GATT连接参数

### 1.8.1 连接间隔（Connection Interval）

- BLE连接是周期性的，每个周期称为一个连接事件（Connection Event）
- 连接间隔范围：7.5ms ~ 4000ms（以1.25ms为单位）
- 间隔越小，数据传输越快，但功耗越高

### 1.8.2 从设备延迟（Slave Latency）

- 从设备可以跳过的连接事件数量
- 范围：0 ~ 499（不能超过连接超时/连接间隔-1）
- 允许从设备在无数据时跳过连接事件以省电

### 1.8.3 连接超时（Supervision Timeout）

- 两次成功通信之间的最大允许时间
- 范围：100ms ~ 32s（以10ms为单位）
- 超时后连接断开

### 1.8.4 MTU（Maximum Transmission Unit）

- 单次ATT PDU可传输的最大字节数
- BLE 4.0/4.1默认：23字节（有效载荷20字节）
- BLE 4.2+支持协商更大的MTU（最大517字节）
- 通过`requestMtu()`协商

### 1.8.5 PHY（物理层）

| PHY | 速率 | 编码 | 范围 |
|-----|------|------|------|
| LE 1M | 1 Mbps | 未编码 | 标准 |
| LE 2M | 2 Mbps | 未编码 | 标准 |
| LE Coded (S=2) | 500 kbps | 编码 | 远距离 |
| LE Coded (S=8) | 125 kbps | 编码 | 更远距离 |

### 1.8.6 连接优先级

Android Framework定义的连接优先级：

| 优先级 | 连接间隔 | 从设备延迟 | 适用场景 |
|--------|----------|------------|----------|
| CONNECTION_PRIORITY_HIGH | 7.5ms~30ms | 0 | 实时控制 |
| CONNECTION_PRIORITY_BALANCED | 30ms~100ms | 0~9 | 一般数据传输 |
| CONNECTION_PRIORITY_LOW_POWER | 100ms~250ms | 0~9 | 低功耗场景 |
| CONNECTION_PRIORITY_DCK | 特定参数 | 特定参数 | Display Control for Keyboard |

---

# 第二部分：Android GATT Framework架构

## 2.1 整体分层架构

Android蓝牙GATT的完整分层架构如下：

```
┌───────────────────────────────────────────────────────────────┐
│                      应用层 (App Layer)                       │
│  BluetoothGatt / BluetoothGattServer / BluetoothLeScanner    │
│  BluetoothGattCallback / BluetoothGattServerCallback         │
├───────────────────────────────────────────────────────────────┤
│                   Framework API 层                            │
│  android.bluetooth 包下的公共API类                            │
│  源码: framework/java/android/bluetooth/                     │
├───────────────────────────────────────────────────────────────┤
│                   AIDL IPC 层                                │
│  IBluetoothGatt / IBluetoothGattCallback                    │
│  IBluetoothGattServerCallback                               │
│  源码: android/app/aidl/android/bluetooth/                  │
├───────────────────────────────────────────────────────────────┤
│                   App Service 层                             │
│  GattService / GattServiceBinder / GattNativeInterface      │
│  ScanManager / AdvertiseManager / DistanceMeasurementManager │
│  源码: android/app/src/com/android/bluetooth/gatt/          │
├───────────────────────────────────────────────────────────────┤
│                   JNI 桥接层                                 │
│  com_android_bluetooth_gatt.cpp                             │
│  源码: android/app/jni/                                     │
├───────────────────────────────────────────────────────────────┤
│                   HAL 接口层                                 │
│  bt_gatt.h / bt_gatt_client.h / bt_gatt_server.h            │
│  源码: system/include/hardware/                             │
├───────────────────────────────────────────────────────────────┤
│                   BTIF 适配层                                │
│  btif_gatt.cc / btif_gatt_client.cc / btif_gatt_server.cc  │
│  源码: system/btif/                                         │
├───────────────────────────────────────────────────────────────┤
│                   BTA 应用层                                 │
│  bta_gattc_* / bta_gatts_* / database                      │
│  源码: system/bta/gatt/                                     │
├───────────────────────────────────────────────────────────────┤
│                   Stack 协议栈层                             │
│  gatt_api / gatt_main / gatt_cl / gatt_sr / att_protocol   │
│  源码: system/stack/gatt/                                   │
├───────────────────────────────────────────────────────────────┤
│                   Rust 新实现层                              │
│  server/ (GATT服务器Rust实现) / arbiter / ffi/gatt_shim     │
│  源码: system/rust/src/gatt/                                │
└───────────────────────────────────────────────────────────────┘
```

## 2.2 各层文件清单与职责

### 2.2.1 Framework API层

> 源码路径：`framework/java/android/bluetooth/`

| 文件 | 职责 |
|------|------|
| [BluetoothGatt.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGatt.java) | GATT客户端API，应用通过此类连接GATT Server、发现服务、读写特征 |
| [BluetoothGattCallback.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattCallback.java) | GATT客户端回调抽象类，接收连接/发现/读写/通知等事件 |
| [BluetoothGattServer.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattServer.java) | GATT服务端API，创建本地GATT Server，响应远端读写请求 |
| [BluetoothGattServerCallback.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattServerCallback.java) | GATT服务端回调抽象类，接收远端设备的读写请求 |
| [BluetoothGattService.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattService.java) | GATT Service数据模型，Parcelable |
| [BluetoothGattCharacteristic.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattCharacteristic.java) | GATT Characteristic数据模型，Parcelable |
| [BluetoothGattDescriptor.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattDescriptor.java) | GATT Descriptor数据模型，Parcelable |
| [BluetoothGattIncludedService.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattIncludedService.java) | GATT IncludedService数据模型 |
| [BluetoothProfile.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothProfile.java) | 蓝牙Profile接口，定义连接状态常量和Profile ID |

BLE扫描/广播API：

| 文件 | 职责 |
|------|------|
| [BluetoothLeScanner.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/BluetoothLeScanner.java) | BLE扫描器API |
| [BluetoothLeAdvertiser.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/BluetoothLeAdvertiser.java) | BLE广播API |
| [ScanSettings.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/ScanSettings.java) | 扫描设置 |
| [ScanResult.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/ScanResult.java) | 扫描结果 |
| [ScanFilter.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/ScanFilter.java) | 扫描过滤器 |
| [ScanCallback.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/ScanCallback.java) | 扫描回调 |
| [AdvertiseSettings.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/AdvertiseSettings.java) | 广播设置 |
| [AdvertiseData.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/AdvertiseData.java) | 广播数据 |
| [AdvertiseCallback.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/le/AdvertiseCallback.java) | 广播回调 |

### 2.2.2 AIDL IPC层

> 源码路径：`android/app/aidl/android/bluetooth/`

| 文件 | 职责 |
|------|------|
| [IBluetoothGatt.aidl](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/aidl/android/bluetooth/IBluetoothGatt.aidl) | GATT服务IPC接口，同步双向调用 |
| [IBluetoothGattCallback.aidl](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/aidl/android/bluetooth/IBluetoothGattCallback.aidl) | GATT客户端回调IPC接口，单向异步 |
| [IBluetoothGattServerCallback.aidl](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/aidl/android/bluetooth/IBluetoothGattServerCallback.aidl) | GATT服务端回调IPC接口，单向异步 |
| BluetoothGattService.aidl | Service的Parcelable定义 |
| BluetoothGattCharacteristic.aidl | Characteristic的Parcelable定义 |
| BluetoothGattDescriptor.aidl | Descriptor的Parcelable定义 |

### 2.2.3 App Service层

> 源码路径：`android/app/src/com/android/bluetooth/gatt/`

| 文件 | 职责 |
|------|------|
| [GattService.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/GattService.java) | GATT Profile核心服务，继承ProfileService |
| [GattServiceBinder.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/GattServiceBinder.java) | IBluetoothGatt.Stub实现，处理IPC请求 |
| [GattNativeInterface.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/GattNativeInterface.java) | JNI桥接封装，将native回调转发给GattService |
| [ContextMap.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/ContextMap.java) | 管理客户端/服务端注册和连接上下文 |
| [HandleMap.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/HandleMap.java) | GATT句柄映射（服务端场景） |
| [GattUtil.kt](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/GattUtil.kt) | GATT工具类（UUID判断、状态码转换） |
| [AdvertiseManager.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/AdvertiseManager.java) | BLE广播管理器 |
| [DistanceMeasurementManager.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/DistanceMeasurementManager.java) | 测距管理器 |

BLE扫描服务层：

> 源码路径：`android/app/src/com/android/bluetooth/le_scan/`

| 文件 | 职责 |
|------|------|
| [ScanManager.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/le_scan/ScanManager.java) | BLE扫描管理器 |
| [ScanController.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/le_scan/ScanController.java) | 扫描控制器 |
| [ScanNativeInterface.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/le_scan/ScanNativeInterface.java) | 扫描JNI接口 |

### 2.2.4 JNI层

> 源码路径：`android/app/jni/`

| 文件 | 职责 |
|------|------|
| [com_android_bluetooth_gatt.cpp](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/jni/com_android_bluetooth_gatt.cpp) | GATT JNI桥接实现，注册native方法，连接Java和C/C++层 |

### 2.2.5 HAL接口层

> 源码路径：`system/include/hardware/`

| 文件 | 职责 |
|------|------|
| [bt_gatt.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_gatt.h) | GATT总接口，定义btgatt_callbacks_t和btgatt_interface_t |
| [bt_gatt_client.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_gatt_client.h) | GATT客户端HAL接口 |
| [bt_gatt_server.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_gatt_server.h) | GATT服务端HAL接口 |
| [bt_gatt_types.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_gatt_types.h) | GATT公共类型定义 |

### 2.2.6 BTIF适配层

> 源码路径：`system/btif/`

| 文件 | 职责 |
|------|------|
| btif_gatt.cc | GATT总入口，初始化和注册HAL接口 |
| btif_gatt_client.cc | GATT客户端BTIF实现 |
| btif_gatt_server.cc | GATT服务端BTIF实现 |
| btif_gatt_util.cc | GATT工具函数 |

### 2.2.7 BTA应用层

> 源码路径：`system/bta/gatt/`

**GATT客户端（gattc/）**：

| 文件 | 职责 |
|------|------|
| bta_gattc_api.cc | GATT客户端API |
| bta_gattc_act.cc | GATT客户端动作处理 |
| bta_gattc_main.cc | GATT客户端主循环 |
| bta_gattc_cache.cc | GATT客户端缓存 |
| bta_gattc_queue.cc | GATT客户端请求队列 |
| bta_gattc_utils.cc | GATT客户端工具函数 |

**GATT服务端（gatts/）**：

| 文件 | 职责 |
|------|------|
| bta_gatts_api.cc | GATT服务端API |
| bta_gatts_act.cc | GATT服务端动作处理 |
| bta_gatts_main.cc | GATT服务端主循环 |
| bta_gatts_queue.cc | GATT服务端请求队列 |
| bta_gatts_utils.cc | GATT服务端工具函数 |
| database.cc / database_builder.cc | GATT数据库实现 |

### 2.2.8 Stack协议栈层

> 源码路径：`system/stack/gatt/`

| 文件 | 职责 |
|------|------|
| gatt_api.cc | GATT API实现（协议栈对外接口） |
| gatt_main.cc | GATT主模块，连接管理、事件分发 |
| gatt_cl.cc | GATT客户端协议逻辑 |
| gatt_sr.cc | GATT服务端协议逻辑 |
| gatt_attr.cc | GATT属性数据库管理 |
| gatt_db.cc | GATT数据库操作 |
| gatt_utils.cc | GATT工具函数 |
| gatt_auth.cc | GATT认证/授权处理 |
| att_protocol.cc | ATT协议实现 |

### 2.2.9 Rust新实现层

> 源码路径：`system/rust/src/gatt/`

| 文件/目录 | 职责 |
|-----------|------|
| gatt.rs | Rust GATT模块入口 |
| ffi.rs | Rust FFI暴露接口 |
| ffi/gatt_shim.cc | C++ GATT Shim，桥接Rust与C++ |
| arbiter.rs | ATT数据包仲裁器 |
| server/ | GATT服务器Rust实现 |
| server/att_database.rs | ATT数据库抽象 |
| server/gatt_database.rs | GATT数据库实现 |
| server/command_handler.rs | ATT命令处理器 |
| server/transactions/ | ATT事务处理（Read/Write/Find等） |

## 2.3 核心调用链路分析

### 2.3.1 GATT客户端读操作完整链路

```
应用调用 BluetoothGatt.readCharacteristic(characteristic)
    │
    ▼
BluetoothGatt.readCharacteristic()
    ├── 检查 mDeviceBusy（同一时刻只允许一个操作）
    ├── 通过 IBluetoothGatt AIDL 代理发起 IPC
    │
    ▼
GattServiceBinder.readCharacteristic()
    │
    ▼
GattService.readCharacteristic()
    ├── 权限检查
    ├── 通过 ContextMap 查找客户端连接
    ├── 通过 GattNativeInterface 调用 JNI
    │
    ▼
com_android_bluetooth_gatt.cpp::gattClientReadCharacteristicNative()
    ├── 调用 HAL 接口 sGattClientInterface->ReadCharacteristic()
    │
    ▼
BTIF → BTA → Stack 层处理
    │
    ▼ (异步回调)
GattNativeInterface.onReadCharacteristic()
    │
    ▼
GattService.onReadCharacteristicFromNative()
    ├── 通过 ContextMap 查找回调
    ├── 通过 IBluetoothGattCallback AIDL 回调
    │
    ▼
BluetoothGatt.GattCallback.onCharacteristicRead()
    ├── 设置 mDeviceBusy = false
    ├── 调用应用层 BluetoothGattCallback.onCharacteristicRead()
```

### 2.3.2 GATT服务端写请求完整链路

```
远端设备写入特征值
    │
    ▼
Stack → BTA → BTIF → HAL 层回调
    │
    ▼
com_android_bluetooth_gatt.cpp::onServerWriteCharacteristic()
    ├── JNI 回调到 Java 层
    │
    ▼
GattNativeInterface.onServerWriteCharacteristic()
    │
    ▼
GattService.onServerWriteCharacteristicFromNative()
    ├── 通过 HandleMap 查找特征
    ├── 通过 IBluetoothGattServerCallback AIDL 回调
    │
    ▼
BluetoothGattServer 内部 Stub.onCharacteristicWriteRequest()
    ├── 调用应用层 BluetoothGattServerCallback.onCharacteristicWriteRequest()
    │
    ▼
应用层处理写入请求
    ├── 解析写入数据
    ├── 调用 BluetoothGattServer.sendResponse() 响应
    │
    ▼
BluetoothGattServer.sendResponse()
    ├── 通过 IBluetoothGatt AIDL 代理
    │
    ▼
GattService.sendResponse()
    ├── 通过 GattNativeInterface → JNI → HAL → Stack
    │
    ▼
响应发送到远端设备
```

### 2.3.3 GATT通知推送链路

```
服务端应用调用 BluetoothGattServer.notifyCharacteristicChanged()
    │
    ▼
BluetoothGattServer.notifyCharacteristicChanged()
    ├── 通过 IBluetoothGatt AIDL 代理
    │
    ▼
GattService.sendNotification()
    ├── 通过 GattNativeInterface → JNI
    │
    ▼
com_android_bluetooth_gatt.cpp::gattServerSendNotificationNative()
    ├── 调用 HAL sGattServerInterface->SendNotification()
    │
    ▼
Stack → BTA → BTIF → 空中发送
    │
    ▼
客户端收到通知
    │
    ▼
Stack → HAL → JNI → GattNativeInterface.onNotify()
    │
    ▼
GattService.onNotifyFromNative()
    ├── 通过 IBluetoothGattCallback AIDL 回调
    │
    ▼
BluetoothGatt.GattCallback.onNotify()
    ├── 调用应用层 BluetoothGattCallback.onCharacteristicChanged()
```

## 2.4 AIDL接口设计

### 2.4.1 IBluetoothGatt.aidl

这是GATT最核心的IPC接口，定义了所有GATT操作：

**客户端操作**：
```
registerClient(ParcelUuid, IBluetoothGattCallback, boolean eattSupport, int transport)
unregisterClient(IBluetoothGattCallback)
clientConnect(int clientIf, String address, boolean isDirect, int transport, boolean opportunistic, int phy, int addressType, int subrateMode, boolean mOptional)
clientDisconnect(int clientIf, String address, int connId)
clientSetPreferredPhy / clientReadPhy
refreshDevice(int clientIf, String address)
discoverServices(int clientIf, String address)
discoverServiceByUuid(int clientIf, String address, ParcelUuid uuid)
readCharacteristic(int clientIf, String address, int handle, int authReq)
readUsingCharacteristicUuid(int clientIf, String address, ParcelUuid uuid, int startHandle, int endHandle, int authReq)
writeCharacteristic(int clientIf, String address, int handle, int writeType, byte[] value)
readDescriptor / writeDescriptor
registerForNotification(int clientIf, String address, int handle, boolean enable)
beginReliableWrite / endReliableWrite
readRemoteRssi / configureMTU
connectionParameterUpdate / leConnectionUpdate
subrateModeRequest
```

**服务端操作**：
```
registerServer(ParcelUuid, IBluetoothGattServerCallback, boolean eattSupport)
unregisterServer(IBluetoothGattServerCallback)
serverConnect / serverDisconnect
serverSetPreferredPhy / serverReadPhy
addService(int serverIf, BluetoothGattService service)
removeService / clearServices
sendResponse(int serverIf, String address, int requestId, int status, int offset, byte[] value)
sendNotification(int serverIf, String address, int handle, boolean confirm, byte[] value)
```

### 2.4.2 回调接口

**IBluetoothGattCallback.aidl**（`oneway`，异步单向调用）：
```
onClientRegistered(int status, int clientIf, ParcelUuid uuid)
onClientConnectionState(int status, int clientIf, boolean connected, String address)
onPhyUpdate / onPhyRead
onSearchComplete(int status, BluetoothGattService[] services)
onCharacteristicRead / onCharacteristicWrite
onExecuteWrite
onDescriptorRead / onDescriptorWrite
onNotify(String address, int handle, byte[] value)
onReadRemoteRssi
onConfigureMTU
onConnectionUpdated
onServiceChanged
onSubrateChange
```

**IBluetoothGattServerCallback.aidl**（`oneway`，异步单向调用）：
```
onServerRegistered(int status, int serverIf, ParcelUuid uuid)
onServerConnectionState(int status, int serverIf, boolean connected, String address)
onServiceAdded(int status, BluetoothGattService service)
onCharacteristicReadRequest(String address, int requestId, int offset, boolean isLong, BluetoothGattCharacteristic characteristic)
onCharacteristicWriteRequest(String address, int requestId, BluetoothGattCharacteristic characteristic, boolean preparedWrite, boolean responseNeeded, int offset, byte[] value)
onDescriptorReadRequest / onDescriptorWriteRequest
onExecuteWrite(String address, int requestId, boolean execute)
onNotificationSent
onMtuChanged
onPhyUpdate / onPhyRead / onConnectionUpdated / onSubrateChange
```

## 2.5 JNI桥接层

JNI层文件 [com_android_bluetooth_gatt.cpp](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/jni/com_android_bluetooth_gatt.cpp) 注册了三个模块的native方法：

### 2.5.1 GattNativeInterface的JNI方法

注册到 `com/android/bluetooth/gatt/GattNativeInterface`

**Client端Native方法**：
| 方法 | 功能 |
|------|------|
| initializeNative / cleanupNative | 初始化/清理 |
| gattClientGetDeviceTypeNative | 获取设备类型 |
| gattClientRegisterAppNative / gattClientUnregisterAppNative | 注册/注销客户端 |
| gattClientConnectNative / gattClientDisconnectNative | 连接/断开 |
| gattClientSetPreferredPhyNative / gattClientReadPhyNative | PHY操作 |
| gattClientRefreshNative | 刷新缓存 |
| gattClientSearchServiceNative / gattClientDiscoverServiceByUuidNative | 服务发现 |
| gattClientReadCharacteristicNative / gattClientReadUsingCharacteristicUuidNative | 读取特征 |
| gattClientWriteCharacteristicNative | 写入特征 |
| gattClientReadDescriptorNative / gattClientWriteDescriptorNative | 读写描述符 |
| gattClientExecuteWriteNative | 执行可靠写 |
| gattClientRegisterForNotificationsNative | 注册/注销通知 |
| gattClientReadRemoteRssiNative / gattClientConfigureMTUNative | RSSI/MTU |
| gattConnectionParameterUpdateNative | 连接参数更新 |

**Server端Native方法**：
| 方法 | 功能 |
|------|------|
| gattServerRegisterAppNative / gattServerUnregisterAppNative | 注册/注销服务端 |
| gattServerConnectNative / gattServerDisconnectNative | 连接/断开 |
| gattServerSetPreferredPhyNative / gattServerReadPhyNative | PHY操作 |
| gattServerAddServiceNative / gattServerStopServiceNative / gattServerDeleteServiceNative | 服务管理 |
| gattServerSendIndicationNative / gattServerSendNotificationNative | 发送指示/通知 |
| gattServerSendResponseNative | 发送响应 |
| gattSubrateRequestNative | Subrate请求 |

### 2.5.2 JNI回调方法（C++ → Java）

**Client回调**：
| 回调方法 | 触发时机 |
|----------|----------|
| onClientRegistered | 客户端注册完成 |
| onConnected / onDisconnected | 连接/断开 |
| onReadCharacteristic / onWriteCharacteristic | 读写特征完成 |
| onReadDescriptor / onWriteDescriptor | 读写描述符完成 |
| onNotify | 收到通知 |
| onSearchComplete | 服务发现完成 |
| onGetGattDb | 获取GATT数据库 |
| onReadRemoteRssi / onConfigureMTU | RSSI/MTU回调 |
| onClientPhyUpdate / onClientPhyRead | PHY回调 |
| onClientConnUpdate | 连接参数更新回调 |
| onServiceChanged | 服务变化 |
| onClientSubrateChange | Subrate变化 |

**Server回调**：
| 回调方法 | 触发时机 |
|----------|----------|
| onServerRegistered | 服务端注册完成 |
| onClientConnected / onClientDisconnected | 远端连接/断开 |
| onServiceAdded / onServiceStopped / onServiceDeleted | 服务增删 |
| onServerReadCharacteristic / onServerReadDescriptor | 远端读取请求 |
| onServerWriteCharacteristic / onServerWriteDescriptor | 远端写入请求 |
| onExecuteWrite | 执行可靠写 |
| onNotificationSent | 通知发送完成 |
| onMtuChanged | MTU变化 |
| onServerPhyUpdate / onServerPhyRead | PHY回调 |
| onServerConnUpdate | 连接参数更新 |
| onServerSubrateChange | Subrate变化 |

## 2.6 Rust新架构

Android蓝牙协议栈正在逐步用Rust重写GATT Server部分，当前架构中Rust和C++并存：

```
┌──────────────────────────────┐
│     GattNativeInterface      │
│         (Java)               │
├──────────────────────────────┤
│   com_android_bluetooth_     │
│       gatt.cpp (JNI)         │
├──────────┬───────────────────┤
│          │                   │
│   C++路径 │    Rust路径       │
│          │                   │
│  btif →  │  gatt_shim →     │
│  bta →   │  Rust GATT       │
│  stack   │  Server          │
│          │                   │
├──────────┴───────────────────┤
│        Controller            │
└──────────────────────────────┘
```

Rust模块关键组件：
- **Arbiter**：ATT数据包仲裁器，决定数据包的拦截/放行
- **GattServer**：新的GATT服务器实现
- **AttDatabase**：ATT数据库抽象
- **CommandHandler**：ATT命令处理器
- **Transactions**：各类ATT事务处理（Read/Write/Find等）
- **IsolationManager**：隔离管理器，支持多连接隔离

---

# 第三部分：Framework核心类详解

## 3.1 BluetoothGatt（GATT客户端）

> 源码：[BluetoothGatt.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGatt.java)

### 类定义

```java
public final class BluetoothGatt implements BluetoothProfile
```

### 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| mService | IBluetoothGatt | AIDL代理，与GattService通信 |
| mCallback | BluetoothGattCallback | 应用层回调 |
| mDevice | BluetoothDevice | 远端设备 |
| mServices | CopyOnWriteArrayList<BluetoothGattService> | 已发现的服务缓存 |
| mDeviceBusy | boolean | 操作互斥标志，同一时刻只允许一个GATT操作 |

### 关键方法详解

#### 连接管理

```java
// 内部连接方法（由BluetoothDevice.connectGatt调用）
boolean connect(boolean autoConnect, BluetoothGattCallback callback, Handler handler)

// 重新连接已断开的设备
boolean connect()

// 断开连接
void disconnect()

// 关闭GATT客户端，释放资源（必须调用！）
void close()
```

**connect() vs connect(autoConnect=true)**：
- `connect(autoConnect=false)`：直接连接，速度快，但如果设备不可达会立即失败
- `connect(autoConnect=true)`：后台连接，系统会在设备可用时自动连接，功耗低

#### 服务发现

```java
// 发现远端设备的所有服务
boolean discoverServices()

// 按UUID发现特定服务
boolean discoverServiceByUuid(UUID uuid)

// 获取已发现的服务列表
List<BluetoothGattService> getServices()

// 按UUID获取特定服务
BluetoothGattService getService(UUID uuid)
```

#### 读写操作

```java
// 读取特征值
boolean readCharacteristic(BluetoothGattCharacteristic characteristic)

// 写入特征值（新API，返回int状态码）
int writeCharacteristic(BluetoothGattCharacteristic characteristic, byte[] value, int writeType)

// 读取描述符
boolean readDescriptor(BluetoothGattDescriptor descriptor)

// 写入描述符（新API）
int writeDescriptor(BluetoothGattDescriptor descriptor, byte[] value)
```

**重要**：读写操作是串行的！`mDeviceBusy`标志确保同一时刻只有一个操作在进行。必须等上一个操作的回调返回后，才能发起下一个操作。

#### 通知订阅

```java
// 开启/关闭特征通知
boolean setCharacteristicNotification(BluetoothGattCharacteristic characteristic, boolean enable)
```

**注意**：`setCharacteristicNotification()`只在本地注册通知监听，还需要写入CCCD描述符才能真正开启远端的通知：

```java
// 完整的通知开启流程
BluetoothGattDescriptor cccd = characteristic.getDescriptor(
    UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"));
gatt.setCharacteristicNotification(characteristic, true);
gatt.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
```

#### 连接参数

```java
// 请求MTU协商
boolean requestMtu(int mtu)

// 读取远端RSSI
boolean readRemoteRssi()

// 请求连接优先级
boolean requestConnectionPriority(int connectionPriority)

// 设置/读取PHY
void setPreferredPhy(int txPhy, int rxPhy, int phyOptions)
void readPhy()

// 请求LE Subrate模式（Android 16新API）
int requestSubrateMode(int subrateMode)
```

#### 可靠写

```java
boolean beginReliableWrite()
boolean executeReliableWrite()
void abortReliableWrite()
```

### 错误码常量

| 常量 | 值 | 说明 |
|------|----|------|
| GATT_SUCCESS | 0 | 成功 |
| GATT_READ_NOT_PERMITTED | 0x2 | 读取不允许 |
| GATT_WRITE_NOT_PERMITTED | 0x3 | 写入不允许 |
| GATT_INSUFFICIENT_AUTHENTICATION | 0x5 | 认证不足 |
| GATT_REQUEST_NOT_SUPPORTED | 0x6 | 请求不支持 |
| GATT_INSUFFICIENT_ENCRYPTION | 0xF | 加密不足 |
| GATT_INVALID_OFFSET | 0x7 | 无效偏移 |
| GATT_INVALID_ATTRIBUTE_LENGTH | 0xD | 无效属性长度 |
| GATT_FAILURE | 0x101 | 通用失败 |
| GATT_CONNECTION_CONGESTED | 0x143 | 连接拥塞 |

## 3.2 BluetoothGattCallback（客户端回调）

> 源码：[BluetoothGattCallback.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattCallback.java)

### 类定义

```java
public abstract class BluetoothGattCallback
```

### 回调方法详解

| 回调方法 | 触发时机 | 关键参数 |
|----------|----------|----------|
| `onConnectionStateChange(BluetoothGatt, int status, int newState)` | 连接状态变化 | status: 操作状态码; newState: STATE_CONNECTED/DISCONNECTED |
| `onServicesDiscovered(BluetoothGatt, int status)` | 服务发现完成 | status: GATT_SUCCESS表示成功 |
| `onCharacteristicRead(BluetoothGatt, BluetoothGattCharacteristic, byte[] value, int status)` | 特征读取完成 | value: 读取到的值 |
| `onCharacteristicWrite(BluetoothGatt, BluetoothGattCharacteristic, int status)` | 特征写入完成 | status: 写入结果 |
| `onCharacteristicChanged(BluetoothGatt, BluetoothGattCharacteristic, byte[] value)` | 收到通知/指示 | value: 通知值 |
| `onDescriptorRead(BluetoothGatt, BluetoothGattDescriptor, int status, byte[] value)` | 描述符读取完成 | |
| `onDescriptorWrite(BluetoothGatt, BluetoothGattDescriptor, int status)` | 描述符写入完成 | |
| `onReliableWriteCompleted(BluetoothGatt, int status)` | 可靠写完成 | |
| `onReadRemoteRssi(BluetoothGatt, int rssi, int status)` | RSSI读取完成 | rssi: 信号强度 |
| `onMtuChanged(BluetoothGatt, int mtu, int status)` | MTU协商完成 | mtu: 协商后的MTU值 |
| `onPhyUpdate(BluetoothGatt, int txPhy, int rxPhy, int status)` | PHY更新 | |
| `onPhyRead(BluetoothGatt, int txPhy, int rxPhy, int status)` | PHY读取完成 | |
| `onConnectionUpdated(BluetoothGatt, int interval, int latency, int timeout, int status)` | 连接参数更新 | |
| `onServiceChanged(BluetoothGatt)` | 远端服务变化 | 需要重新发现服务 |
| `onSubrateChange(BluetoothGatt, int subrateMode, int status)` | Subrate变化 | |

**设计特点**：所有方法都有空实现（默认no-op），应用选择性覆写需要的回调。部分方法有新旧两个版本，带`byte[] value`参数的新版本是内存安全的（旧版本通过characteristic.getValue()获取值存在并发问题）。

## 3.3 BluetoothGattServer（GATT服务端）

> 源码：[BluetoothGattServer.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattServer.java)

### 类定义

```java
public final class BluetoothGattServer implements BluetoothProfile
```

### 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| mService | IBluetoothGatt | AIDL代理 |
| mCallback | BluetoothGattServerCallback | 应用层回调 |
| mServices | List<BluetoothGattService> | 已添加的服务列表 |
| mPendingService | BluetoothGattService | 等待添加的服务 |
| mServerIfLock | Object | 注册回调同步锁（10秒超时） |

### 关键方法详解

#### 生命周期管理

```java
// 关闭GATT Server
void close()

// 服务端主动连接远端设备
boolean connect(BluetoothDevice device, boolean autoConnect)

// 断开与远端设备的连接
void cancelConnection(BluetoothDevice device)
```

#### 服务管理

```java
// 添加本地服务（异步，通过onServiceAdded回调确认）
boolean addService(BluetoothGattService service)

// 移除本地服务
boolean removeService(BluetoothGattService service)

// 清除所有本地服务
void clearServices()

// 获取已添加的服务
List<BluetoothGattService> getServices()
BluetoothGattService getService(UUID uuid)
```

**addService的异步流程**：
```
应用调用 addService(service)
    │
    ▼
设置 mPendingService = service
    │
    ▼
通过 IBluetoothGatt.addService() IPC
    │
    ▼
GattService → GattNativeInterface → JNI → Stack
    │
    ▼ (异步回调)
onServiceAdded(status, service)
    │
    ▼
mPendingService = null
mServices.add(service)
    │
    ▼
应用层 BluetoothGattServerCallback.onServiceAdded(status, service)
```

#### 响应远端请求

```java
// 响应远端读写请求（必须在onXxxReadRequest/onXxxWriteRequest回调中调用）
boolean sendResponse(BluetoothDevice device, int requestId, int status, int offset, byte[] value)
```

**重要**：对于每个远端读写请求，必须调用`sendResponse()`完成请求，否则远端会超时。

#### 发送通知/指示

```java
// 向远端发送通知/指示
boolean notifyCharacteristicChanged(BluetoothDevice device, BluetoothGattCharacteristic characteristic, boolean confirm, byte[] value)

// confirm=false: Notification（无需确认）
// confirm=true:  Indication（需要确认）
```

## 3.4 BluetoothGattServerCallback（服务端回调）

> 源码：[BluetoothGattServerCallback.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattServerCallback.java)

### 类定义

```java
public abstract class BluetoothGattServerCallback
```

### 回调方法详解

| 回调方法 | 触发时机 | 必须操作 |
|----------|----------|----------|
| `onConnectionStateChange(BluetoothDevice, int status, int newState)` | 连接状态变化 | - |
| `onServiceAdded(int status, BluetoothGattService)` | 服务添加完成 | - |
| `onCharacteristicReadRequest(BluetoothDevice, int requestId, int offset, BluetoothGattCharacteristic)` | 远端请求读取特征 | **必须调用sendResponse()** |
| `onCharacteristicWriteRequest(BluetoothDevice, int requestId, BluetoothGattCharacteristic, boolean preparedWrite, boolean responseNeeded, int offset, byte[] value)` | 远端请求写入特征 | responseNeeded时**必须调用sendResponse()** |
| `onDescriptorReadRequest(BluetoothDevice, int requestId, int offset, BluetoothGattDescriptor)` | 远端请求读取描述符 | **必须调用sendResponse()** |
| `onDescriptorWriteRequest(BluetoothDevice, int requestId, BluetoothGattDescriptor, boolean preparedWrite, boolean responseNeeded, int offset, byte[] value)` | 远端请求写入描述符 | responseNeeded时**必须调用sendResponse()** |
| `onExecuteWrite(BluetoothDevice, int requestId, boolean execute)` | 执行可靠写 | **必须调用sendResponse()** |
| `onNotificationSent(BluetoothDevice, int status)` | 通知/指示发送完成 | - |
| `onMtuChanged(BluetoothDevice, int mtu)` | MTU变化 | - |

**关键设计**：读写请求回调中，`responseNeeded`参数指示是否需要响应。对于需要响应的请求，必须调用`sendResponse()`，否则远端会超时等待。

## 3.5 BluetoothGattService（服务数据模型）

> 源码：[BluetoothGattService.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattService.java)

### 类定义

```java
public class BluetoothGattService implements Parcelable
```

### 核心字段

| 字段 | 类型 | 说明 |
|------|------|------|
| mDevice | BluetoothDevice | 关联的远端设备（客户端场景） |
| mUuid | UUID | 服务UUID |
| mInstanceId | int | 实例ID |
| mServiceType | int | 服务类型 |
| mCharacteristics | List<BluetoothGattCharacteristic> | 特征列表 |
| mIncludedServices | List<BluetoothGattService> | 包含的服务列表 |

### 服务类型常量

| 常量 | 值 | 说明 |
|------|----|------|
| SERVICE_TYPE_PRIMARY | 0 | 主要服务 |
| SERVICE_TYPE_SECONDARY | 1 | 次要服务 |

### 构建方式

```java
// 创建服务端服务
BluetoothGattService service = new BluetoothGattService(
    SERVICE_UUID,
    BluetoothGattService.SERVICE_TYPE_PRIMARY
);

// 添加特征
service.addCharacteristic(characteristic);

// 添加包含服务
service.addIncludedService(includedService);
```

## 3.6 BluetoothGattCharacteristic（特征数据模型）

> 源码：[BluetoothGattCharacteristic.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattCharacteristic.java)

### 类定义

```java
public class BluetoothGattCharacteristic implements Parcelable
```

### 属性常量（Properties）

| 常量 | 值 | 说明 |
|------|----|------|
| PROPERTY_BROADCAST | 0x01 | 可广播 |
| PROPERTY_READ | 0x02 | 可读 |
| PROPERTY_WRITE_NO_RESPONSE | 0x04 | 可写无响应 |
| PROPERTY_WRITE | 0x08 | 可写有响应 |
| PROPERTY_NOTIFY | 0x10 | 可通知 |
| PROPERTY_INDICATE | 0x20 | 可指示 |
| PROPERTY_SIGNED_WRITE | 0x40 | 签名写 |
| PROPERTY_EXTENDED_PROPS | 0x80 | 扩展属性 |

### 权限常量（Permissions）

| 常量 | 值 | 说明 |
|------|----|------|
| PERMISSION_READ | 0x01 | 可读 |
| PERMISSION_READ_ENCRYPTED | 0x02 | 加密读 |
| PERMISSION_READ_ENCRYPTED_MITM | 0x04 | 加密+MITM读 |
| PERMISSION_WRITE | 0x10 | 可写 |
| PERMISSION_WRITE_ENCRYPTED | 0x20 | 加密写 |
| PERMISSION_WRITE_ENCRYPTED_MITM | 0x40 | 加密+MITM写 |
| PERMISSION_WRITE_SIGNED | 0x80 | 签名写 |
| PERMISSION_WRITE_SIGNED_MITM | 0x100 | 签名+MITM写 |

### 写入类型常量

| 常量 | 值 | 说明 |
|------|----|------|
| WRITE_TYPE_DEFAULT | 0x02 | 写入需响应 |
| WRITE_TYPE_NO_RESPONSE | 0x01 | 写入无响应 |
| WRITE_TYPE_SIGNED | 0x04 | 签名写入 |

### 构建方式

```java
// 创建特征
BluetoothGattCharacteristic characteristic = new BluetoothGattCharacteristic(
    CHARACTERISTIC_UUID,
    BluetoothGattCharacteristic.PROPERTY_READ | BluetoothGattCharacteristic.PROPERTY_WRITE
        | BluetoothGattCharacteristic.PROPERTY_NOTIFY,
    BluetoothGattCharacteristic.PERMISSION_READ | BluetoothGattCharacteristic.PERMISSION_WRITE
);

// 添加描述符
BluetoothGattDescriptor cccd = new BluetoothGattDescriptor(
    UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"),
    BluetoothGattDescriptor.PERMISSION_READ | BluetoothGattDescriptor.PERMISSION_WRITE
);
characteristic.addDescriptor(cccd);
```

## 3.7 BluetoothGattDescriptor（描述符数据模型）

> 源码：[BluetoothGattDescriptor.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothGattDescriptor.java)

### 类定义

```java
public class BluetoothGattDescriptor implements Parcelable
```

### 关键常量

| 常量 | 值 | 说明 |
|------|----|------|
| ENABLE_NOTIFICATION_VALUE | {0x01, 0x00} | 开启Notification |
| ENABLE_INDICATION_VALUE | {0x02, 0x00} | 开启Indication |
| DISABLE_NOTIFICATION_VALUE | {0x00, 0x00} | 关闭通知/指示 |

### 权限常量

与BluetoothGattCharacteristic的权限常量类似。

## 3.8 GattService（系统服务实现）

> 源码：[GattService.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/GattService.java)

### 类定义

```java
public class GattService extends ProfileService
```

### 核心组件

| 组件 | 类型 | 说明 |
|------|------|------|
| mClientMap | ContextMap<IBluetoothGattCallback> | 客户端注册映射表 |
| mServerMap | ContextMap<IBluetoothGattServerCallback> | 服务端注册映射表 |
| mReliableQueue | Set<BluetoothDevice> | 可靠写队列 |
| mHandleMap | HandleMap | 服务端句柄映射 |
| mNativeInterface | GattNativeInterface | JNI原生接口 |
| mAdvertiseManager | AdvertiseManager | 广播管理器 |
| mDistanceMeasurementManager | DistanceMeasurementManager | 测距管理器 |

### 关键设计

1. **继承ProfileService**：Profile ID为`BluetoothProfile.GATT`
2. **通过GattNativeInterface与底层交互**：所有GATT操作最终通过JNI调用C/C++协议栈
3. **ContextMap管理注册和连接**：每个App注册后分配clientIf/serverIf，每个连接分配connId
4. **RSSI读取节流**：防止应用频繁读取RSSI
5. **受限句柄机制**：某些句柄需要BLUETOOTH_PRIVILEGED权限
6. **MTU早期交换**：在连接建立时提前协商MTU
7. **Subrate模式支持**：Android 16新增的LE Subrate功能

## 3.9 GattNativeInterface（JNI桥接）

> 源码：[GattNativeInterface.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/GattNativeInterface.java)

### 类定义

```java
class GattNativeInterface
```

### 职责

1. 定义native方法，被GattService调用
2. 接收JNI回调，转发给GattService

### 关键回调方法（由JNI层调用）

```java
// 客户端回调
void onClientRegistered(int status, int clientIf, long uuidLsb, long uuidMsb)
void onConnected(int clientIf, int connId, int transport, int status, String address)
void onDisconnected(int clientIf, int connId, int transport, int status, String address)
void onSearchComplete(int connId, BluetoothGattService[] services, int status)
void onReadCharacteristic(int connId, int status, int handle, byte[] value)
void onWriteCharacteristic(int connId, int status, int handle, byte[] value)
void onNotify(int connId, String address, int handle, byte[] value)
void onConfigureMTU(int connId, int status, int mtu)
void onReadRemoteRssi(int clientIf, String address, int rssi, int status)
void onClientPhyUpdate(int connId, int txPhy, int rxPhy, int status)
void onClientConnUpdate(int connId, int interval, int latency, int timeout, int status)
void onServiceChanged(int connId)
void onClientSubrateChange(int connId, int subrateFactor, int latency, int contNum, int timeout, int status)

// 服务端回调
void onServerRegistered(int status, int serverIf, long uuidLsb, long uuidMsb)
void onClientConnected(String address, int serverIf, boolean connected, int connId)
void onServiceAdded(int status, BluetoothGattService service)
void onServerReadCharacteristic(String address, int connId, int requestId, int offset, boolean isLong, int handle)
void onServerWriteCharacteristic(String address, int connId, int requestId, BluetoothGattCharacteristic characteristic, boolean preparedWrite, boolean responseNeeded, int offset, byte[] value)
void onServerReadDescriptor(...)
void onServerWriteDescriptor(...)
void onExecuteWrite(String address, int connId, int requestId, boolean execute)
void onNotificationSent(int connId, int status)
void onMtuChanged(int connId, int mtu)
```

## 3.10 ContextMap与HandleMap

### ContextMap

> 源码：[ContextMap.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/ContextMap.java)

泛型类`ContextMap<C extends IInterface>`，管理已注册的GATT应用和连接。

**核心数据结构**：
```
ContextMap
│
├── App (应用条目)
│   ├── uuid: ParcelUuid          // 应用UUID
│   ├── callback: C               // 回调接口
│   ├── deathRecipient: DeathRecipient  // 进程死亡监听
│   └── connections: List<Connection>   // 此应用的连接列表
│
└── Connection (连接条目)
    ├── connId: int               // 连接ID
    ├── address: String           // 设备地址
    └── serverIf: int             // 服务端ID（仅服务端场景）
```

### HandleMap

> 源码：[HandleMap.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/gatt/HandleMap.java)

管理GATT服务端的句柄映射，将Service/Characteristic/Descriptor的Handle映射到对应的Java对象。

---

# 第四部分：应用层对接GATT的方式

## 4.1 GATT客户端完整对接流程

### 流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    GATT 客户端对接流程                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 获取 BluetoothGatt 实例                                 │
│     BluetoothDevice.connectGatt()                           │
│              │                                              │
│              ▼                                              │
│  2. 等待连接回调                                            │
│     onConnectionStateChange(STATE_CONNECTED)                │
│              │                                              │
│              ▼                                              │
│  3. 发现服务                                                │
│     gatt.discoverServices()                                 │
│              │                                              │
│              ▼                                              │
│  4. 服务发现完成回调                                        │
│     onServicesDiscovered(GATT_SUCCESS)                      │
│              │                                              │
│              ▼                                              │
│  5. 请求MTU协商（可选）                                     │
│     gatt.requestMtu(517)                                    │
│              │                                              │
│              ▼                                              │
│  6. 读写特征值 / 订阅通知                                   │
│     gatt.readCharacteristic()                               │
│     gatt.writeCharacteristic()                              │
│     gatt.setCharacteristicNotification() + writeDescriptor  │
│              │                                              │
│              ▼                                              │
│  7. 接收通知回调                                            │
│     onCharacteristicChanged()                               │
│              │                                              │
│              ▼                                              │
│  8. 断开连接 / 关闭                                         │
│     gatt.disconnect() → gatt.close()                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 详细步骤

#### 步骤1：获取BluetoothGatt实例

```java
// 通过BluetoothDevice获取
BluetoothGatt gatt = device.connectGatt(
    context,
    autoConnect,          // false=直接连接, true=后台自动连接
    gattCallback,         // 回调实现
    transport             // TRANSPORT_AUTO/TRANSPORT_LE/TRANSPORT_BREDR
);

// Android 13+ 推荐使用带Handler的版本
BluetoothGatt gatt = device.connectGatt(
    context,
    autoConnect,
    gattCallback,
    transport,
    phy,                  // PHY_LE_1M_MASK / PHY_LE_2M_MASK / PHY_LE_CODED_MASK
    handler               // 指定回调执行的Handler
);
```

#### 步骤2：实现BluetoothGattCallback

```java
private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
    @Override
    public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
        if (status == BluetoothGatt.GATT_SUCCESS && newState == BluetoothProfile.STATE_CONNECTED) {
            // 连接成功，发起服务发现
            gatt.discoverServices();
        } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
            // 连接断开
            gatt.close();
        }
    }

    @Override
    public void onServicesDiscovered(BluetoothGatt gatt, int status) {
        if (status == BluetoothGatt.GATT_SUCCESS) {
            // 服务发现完成，可以开始读写操作
            BluetoothGattService service = gatt.getService(TARGET_SERVICE_UUID);
            if (service != null) {
                BluetoothGattCharacteristic characteristic =
                    service.getCharacteristic(TARGET_CHARACTERISTIC_UUID);
                // 读取特征值
                gatt.readCharacteristic(characteristic);
            }
        }
    }

    @Override
    public void onCharacteristicRead(BluetoothGatt gatt,
            BluetoothGattCharacteristic characteristic, byte[] value, int status) {
        if (status == BluetoothGatt.GATT_SUCCESS) {
            // 读取成功，处理value
        }
    }

    @Override
    public void onCharacteristicWrite(BluetoothGatt gatt,
            BluetoothGattCharacteristic characteristic, int status) {
        if (status == BluetoothGatt.GATT_SUCCESS) {
            // 写入成功
        }
    }

    @Override
    public void onCharacteristicChanged(BluetoothGatt gatt,
            BluetoothGattCharacteristic characteristic, byte[] value) {
        // 收到通知，处理value
    }

    @Override
    public void onMtuChanged(BluetoothGatt gatt, int mtu, int status) {
        if (status == BluetoothGatt.GATT_SUCCESS) {
            // MTU协商完成
        }
    }
};
```

#### 步骤3：订阅通知

```java
private void enableNotification(BluetoothGatt gatt,
        BluetoothGattCharacteristic characteristic) {
    // 1. 本地注册通知监听
    gatt.setCharacteristicNotification(characteristic, true);

    // 2. 写入CCCD开启远端通知
    BluetoothGattDescriptor cccd = characteristic.getDescriptor(
        UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"));
    if (cccd != null) {
        gatt.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
    }
}
```

#### 步骤4：写入特征值

```java
// Android 13+ 新API（推荐）
int result = gatt.writeCharacteristic(characteristic, data,
    BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
if (result != BluetoothGatt.GATT_SUCCESS) {
    // 写入失败
}

// 旧API（已废弃）
characteristic.setValue(data);
characteristic.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
gatt.writeCharacteristic(characteristic);
```

#### 步骤5：断开与关闭

```java
// 断开连接
gatt.disconnect();

// 在onConnectionStateChange回调中关闭
@Override
public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
    if (newState == BluetoothProfile.STATE_DISCONNECTED) {
        gatt.close();  // 释放资源，必须调用！
    }
}
```

**重要**：`disconnect()`只是断开连接，`close()`才是释放资源。不调用`close()`会导致GATT连接泄漏！

## 4.2 GATT服务端完整对接流程

### 流程图

```
┌─────────────────────────────────────────────────────────────┐
│                    GATT 服务端对接流程                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 获取 BluetoothGattServer 实例                           │
│     BluetoothManager.openGattServer()                       │
│              │                                              │
│              ▼                                              │
│  2. 等待注册完成回调                                        │
│     onServiceAdded(GATT_SUCCESS)                            │
│              │                                              │
│              ▼                                              │
│  3. 构建并添加服务                                          │
│     构建 Service → Characteristic → Descriptor              │
│     gattServer.addService(service)                          │
│              │                                              │
│              ▼                                              │
│  4. 等待远端设备连接                                        │
│     onConnectionStateChange(STATE_CONNECTED)                │
│              │                                              │
│              ▼                                              │
│  5. 处理远端读写请求                                        │
│     onCharacteristicReadRequest → sendResponse              │
│     onCharacteristicWriteRequest → sendResponse             │
│     onDescriptorReadRequest → sendResponse                  │
│     onDescriptorWriteRequest → sendResponse                 │
│              │                                              │
│              ▼                                              │
│  6. 主动推送通知/指示                                       │
│     gattServer.notifyCharacteristicChanged()                │
│              │                                              │
│              ▼                                              │
│  7. 关闭服务端                                              │
│     gattServer.close()                                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 详细步骤

#### 步骤1：获取BluetoothGattServer实例

```java
BluetoothManager bluetoothManager =
    (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);

BluetoothGattServer gattServer = bluetoothManager.openGattServer(
    context,
    serverCallback  // 服务端回调实现
);
```

#### 步骤2：构建GATT服务

```java
// 创建服务
BluetoothGattService service = new BluetoothGattService(
    SERVICE_UUID,
    BluetoothGattService.SERVICE_TYPE_PRIMARY
);

// 创建特征 - 按键控制特征（可写+可通知）
BluetoothGattCharacteristic controlCharacteristic = new BluetoothGattCharacteristic(
    CONTROL_CHARACTERISTIC_UUID,
    BluetoothGattCharacteristic.PROPERTY_WRITE
        | BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE
        | BluetoothGattCharacteristic.PROPERTY_NOTIFY,
    BluetoothGattCharacteristic.PERMISSION_WRITE
);

// 添加CCCD描述符（支持通知必须添加）
BluetoothGattDescriptor cccd = new BluetoothGattDescriptor(
    UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"),
    BluetoothGattDescriptor.PERMISSION_READ | BluetoothGattDescriptor.PERMISSION_WRITE
);
controlCharacteristic.addDescriptor(cccd);

// 创建特征 - 状态反馈特征（可读+可通知）
BluetoothGattCharacteristic statusCharacteristic = new BluetoothGattCharacteristic(
    STATUS_CHARACTERISTIC_UUID,
    BluetoothGattCharacteristic.PROPERTY_READ
        | BluetoothGattCharacteristic.PROPERTY_NOTIFY,
    BluetoothGattCharacteristic.PERMISSION_READ
);

BluetoothGattDescriptor statusCccd = new BluetoothGattDescriptor(
    UUID.fromString("00002902-0000-1000-8000-00805f9b34fb"),
    BluetoothGattDescriptor.PERMISSION_READ | BluetoothGattDescriptor.PERMISSION_WRITE
);
statusCharacteristic.addDescriptor(statusCccd);

// 将特征添加到服务
service.addCharacteristic(controlCharacteristic);
service.addCharacteristic(statusCharacteristic);

// 添加服务到GATT Server
gattServer.addService(service);
```

#### 步骤3：实现BluetoothGattServerCallback

```java
private final BluetoothGattServerCallback serverCallback = new BluetoothGattServerCallback() {

    @Override
    public void onConnectionStateChange(BluetoothDevice device, int status, int newState) {
        if (newState == BluetoothProfile.STATE_CONNECTED) {
            // 远端设备已连接
            // 可以主动连接回来（双向通信）
            gattServer.connect(device, false);
        } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
            // 远端设备断开
        }
    }

    @Override
    public void onServiceAdded(int status, BluetoothGattService service) {
        if (status == BluetoothGatt.GATT_SUCCESS) {
            // 服务添加成功
        }
    }

    @Override
    public void onCharacteristicReadRequest(BluetoothDevice device, int requestId,
            int offset, BluetoothGattCharacteristic characteristic) {
        // 远端请求读取特征值
        byte[] value = getCharacteristicValue(characteristic);
        gattServer.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS,
            0, value);
    }

    @Override
    public void onCharacteristicWriteRequest(BluetoothDevice device, int requestId,
            BluetoothGattCharacteristic characteristic, boolean preparedWrite,
            boolean responseNeeded, int offset, byte[] value) {
        // 远端请求写入特征值
        handleWriteRequest(characteristic, value);

        if (responseNeeded) {
            gattServer.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS,
                0, null);
        }
    }

    @Override
    public void onDescriptorReadRequest(BluetoothDevice device, int requestId,
            int offset, BluetoothGattDescriptor descriptor) {
        // 远端请求读取描述符（通常是CCCD）
        if (isCccd(descriptor)) {
            byte[] value = isNotificationEnabled(device, descriptor.getCharacteristic())
                ? BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                : BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE;
            gattServer.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS,
                0, value);
        }
    }

    @Override
    public void onDescriptorWriteRequest(BluetoothDevice device, int requestId,
            BluetoothGattDescriptor descriptor, boolean preparedWrite,
            boolean responseNeeded, int offset, byte[] value) {
        // 远端请求写入描述符（通常是开启/关闭通知）
        if (isCccd(descriptor)) {
            if (Arrays.equals(value, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)) {
                // 开启通知
                enableNotificationForDevice(device, descriptor.getCharacteristic());
            } else if (Arrays.equals(value, BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE)) {
                // 关闭通知
                disableNotificationForDevice(device, descriptor.getCharacteristic());
            }
        }

        if (responseNeeded) {
            gattServer.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS,
                0, null);
        }
    }

    @Override
    public void onNotificationSent(BluetoothDevice device, int status) {
        // 通知发送完成
    }

    @Override
    public void onMtuChanged(BluetoothDevice device, int mtu) {
        // MTU变化
    }
};
```

#### 步骤4：发送通知

```java
// 向已连接的设备发送通知
void sendNotification(BluetoothDevice device, BluetoothGattCharacteristic characteristic,
        byte[] value) {
    // confirm=false: Notification
    // confirm=true: Indication
    gattServer.notifyCharacteristicChanged(device, characteristic, false, value);
}
```

#### 步骤5：开启广播（让远端设备能扫描到）

```java
BluetoothLeAdvertiser advertiser =
    bluetoothAdapter.getBluetoothLeAdvertiser();

AdvertiseSettings settings = new AdvertiseSettings.Builder()
    .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
    .setConnectable(true)
    .setTimeout(0)  // 不超时
    .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
    .build();

AdvertiseData advertiseData = new AdvertiseData.Builder()
    .setIncludeDeviceName(true)
    .addServiceUuid(new ParcelUuid(SERVICE_UUID))
    .build();

AdvertiseData scanResponse = new AdvertiseData.Builder()
    .setIncludeDeviceName(true)
    .build();

advertiser.startAdvertising(settings, advertiseData, scanResponse, advertiseCallback);
```

## 4.3 BLE扫描对接

### 扫描流程

```java
// 获取扫描器
BluetoothLeScanner scanner = bluetoothAdapter.getBluetoothLeScanner();

// 设置扫描过滤器
List<ScanFilter> filters = new ArrayList<>();
ScanFilter filter = new ScanFilter.Builder()
    .setServiceUuid(ParcelUuid.fromString(SERVICE_UUID.toString()))
    .build();
filters.add(filter);

// 设置扫描参数
ScanSettings settings = new ScanSettings.Builder()
    .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)  // 低延迟模式
    .build();

// 开始扫描
scanner.startScan(filters, settings, scanCallback);

// 扫描回调
private final ScanCallback scanCallback = new ScanCallback() {
    @Override
    public void onScanResult(int callbackType, ScanResult result) {
        BluetoothDevice device = result.getDevice();
        int rssi = result.getRssi();
        ScanRecord scanRecord = result.getScanRecord();
        // 处理扫描结果
    }

    @Override
    public void onBatchScanResults(List<ScanResult> results) {
        // 批量扫描结果
    }

    @Override
    public void onScanFailed(int errorCode) {
        // 扫描失败
    }
};

// 停止扫描
scanner.stopScan(scanCallback);
```

### 扫描模式

| 模式 | 扫描窗口 | 扫描间隔 | 功耗 | 适用场景 |
|------|----------|----------|------|----------|
| SCAN_MODE_OPPORTUNISTIC | - | - | 最低 | 被动扫描 |
| SCAN_MODE_LOW_POWER | 30ms | 5000ms | 低 | 后台扫描 |
| SCAN_MODE_BALANCED | 30ms | 1000ms | 中 | 一般扫描 |
| SCAN_MODE_LOW_LATENCY | 30ms | 30ms | 高 | 实时扫描 |
| SCAN_MODE_AMBIENT_DISCOVERY | - | - | 低 | 环境发现 |

## 4.4 BLE广播对接

### 广播流程

```java
BluetoothLeAdvertiser advertiser = bluetoothAdapter.getBluetoothLeAdvertiser();

// 广播设置
AdvertiseSettings settings = new AdvertiseSettings.Builder()
    .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
    .setConnectable(true)
    .setTimeout(0)
    .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
    .build();

// 广播数据
AdvertiseData advertiseData = new AdvertiseData.Builder()
    .setIncludeDeviceName(true)
    .addServiceUuid(new ParcelUuid(SERVICE_UUID))
    .build();

// 扫描响应数据
AdvertiseData scanResponse = new AdvertiseData.Builder()
    .setIncludeDeviceName(true)
    .addServiceData(
        new ParcelUuid(SERVICE_UUID),
        new byte[]{0x01, 0x02}  // 自定义服务数据
    )
    .build();

// 广播回调
AdvertiseCallback advertiseCallback = new AdvertiseCallback() {
    @Override
    public void onStartSuccess(AdvertiseSettings settingsInEffect) {
        // 广播启动成功
    }

    @Override
    public void onStartFailure(int errorCode) {
        // 广播启动失败
    }
};

// 开始广播
advertiser.startAdvertising(settings, advertiseData, scanResponse, advertiseCallback);

// 停止广播
advertiser.stopAdvertising(advertiseCallback);
```

### 广播模式

| 模式 | 广播间隔 | 功耗 | 适用场景 |
|------|----------|------|----------|
| ADVERTISE_MODE_LOW_POWER | 1000ms | 低 | 后台广播 |
| ADVERTISE_MODE_BALANCED | 250ms | 中 | 一般广播 |
| ADVERTISE_MODE_LOW_LATENCY | 100ms | 高 | 实时广播 |

## 4.5 权限要求

### Android 12+ 权限模型

| 权限 | 用途 | 保护级别 |
|------|------|----------|
| BLUETOOTH_SCAN | BLE扫描 | 普通或签名 |
| BLUETOOTH_ADVERTISE | BLE广播 | 普通或签名 |
| BLUETOOTH_CONNECT | GATT连接 | 普通或签名 |
| ACCESS_FINE_LOCATION | 扫描结果需要位置权限 | 危险 |

**AndroidManifest.xml声明**：

```xml
<!-- Android 12+ -->
<uses-permission android:name="android.permission.BLUETOOTH_SCAN"
    android:usesPermissionFlags="neverForLocation" />
<uses-permission android:name="android.permission.BLUETOOTH_ADVERTISE" />
<uses-permission android:name="android.permission.BLUETOOTH_CONNECT" />

<!-- Android 11及以下 -->
<uses-permission android:name="android.permission.BLUETOOTH" />
<uses-permission android:name="android.permission.BLUETOOTH_ADMIN" />
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />

<!-- BLE特性声明 -->
<uses-feature android:name="android.hardware.bluetooth_le" android:required="true" />
```

**运行时权限请求**：

```java
// Android 12+
if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
    if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)
            != PackageManager.PERMISSION_GRANTED
        || checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)
            != PackageManager.PERMISSION_GRANTED) {
        requestPermissions(new String[]{
            Manifest.permission.BLUETOOTH_SCAN,
            Manifest.permission.BLUETOOTH_CONNECT
        }, REQUEST_CODE);
    }
}
```

## 4.6 完整代码示例

### 4.6.1 GATT客户端完整示例

```java
public class BleClientManager {
    private static final UUID REMOTE_CONTROL_SERVICE_UUID =
        UUID.fromString("12345678-1234-5678-1234-567812345678");
    private static final UUID CONTROL_CHARACTERISTIC_UUID =
        UUID.fromString("12345678-1234-5678-1234-567812345679");
    private static final UUID CCCD_UUID =
        UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    private BluetoothGatt mBluetoothGatt;
    private BluetoothGattCharacteristic mControlCharacteristic;
    private boolean mNotificationEnabled = false;

    // 连接设备
    public void connect(Context context, BluetoothDevice device) {
        mBluetoothGatt = device.connectGatt(context, false, mGattCallback,
            BluetoothDevice.TRANSPORT_LE);
    }

    // 断开连接
    public void disconnect() {
        if (mBluetoothGatt != null) {
            mBluetoothGatt.disconnect();
        }
    }

    private final BluetoothGattCallback mGattCallback = new BluetoothGattCallback() {
        @Override
        public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
            if (status == BluetoothGatt.GATT_SUCCESS
                    && newState == BluetoothProfile.STATE_CONNECTED) {
                // 连接成功，请求MTU
                gatt.requestMtu(517);
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                mBluetoothGatt.close();
                mBluetoothGatt = null;
            }
        }

        @Override
        public void onMtuChanged(BluetoothGatt gatt, int mtu, int status) {
            // MTU协商完成，发起服务发现
            gatt.discoverServices();
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt gatt, int status) {
            if (status != BluetoothGatt.GATT_SUCCESS) return;

            BluetoothGattService service = gatt.getService(REMOTE_CONTROL_SERVICE_UUID);
            if (service == null) return;

            mControlCharacteristic = service.getCharacteristic(CONTROL_CHARACTERISTIC_UUID);
            if (mControlCharacteristic == null) return;

            // 开启通知
            enableNotification(gatt, mControlCharacteristic);

            // 请求高优先级连接（降低延迟）
            gatt.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH);
        }

        @Override
        public void onDescriptorWrite(BluetoothGatt gatt,
                BluetoothGattDescriptor descriptor, int status) {
            if (status == BluetoothGatt.GATT_SUCCESS && isCccd(descriptor)) {
                mNotificationEnabled = true;
                // 通知已开启，可以开始操作
            }
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt gatt,
                BluetoothGattCharacteristic characteristic, byte[] value) {
            // 收到远端通知，处理数据
            handleNotification(characteristic, value);
        }

        @Override
        public void onCharacteristicWrite(BluetoothGatt gatt,
                BluetoothGattCharacteristic characteristic, int status) {
            // 写入完成
        }

        @Override
        public void onCharacteristicRead(BluetoothGatt gatt,
                BluetoothGattCharacteristic characteristic, byte[] value, int status) {
            // 读取完成
        }
    };

    // 开启通知
    private void enableNotification(BluetoothGatt gatt,
            BluetoothGattCharacteristic characteristic) {
        gatt.setCharacteristicNotification(characteristic, true);
        BluetoothGattDescriptor cccd = characteristic.getDescriptor(CCCD_UUID);
        if (cccd != null) {
            gatt.writeDescriptor(cccd, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
        }
    }

    // 发送控制指令
    public boolean sendCommand(byte[] command) {
        if (mBluetoothGatt == null || mControlCharacteristic == null) return false;
        int result = mBluetoothGatt.writeCharacteristic(
            mControlCharacteristic, command,
            BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
        return result == BluetoothGatt.GATT_SUCCESS;
    }

    private boolean isCccd(BluetoothGattDescriptor descriptor) {
        return descriptor.getUuid().equals(CCCD_UUID);
    }
}
```

### 4.6.2 GATT服务端完整示例

```java
public class BleServerManager {
    private static final UUID REMOTE_CONTROL_SERVICE_UUID =
        UUID.fromString("12345678-1234-5678-1234-567812345678");
    private static final UUID CONTROL_CHARACTERISTIC_UUID =
        UUID.fromString("12345678-1234-5678-1234-567812345679");
    private static final UUID STATUS_CHARACTERISTIC_UUID =
        UUID.fromString("12345678-1234-5678-1234-56781234567a");
    private static final UUID CCCD_UUID =
        UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    private BluetoothGattServer mGattServer;
    private BluetoothGattCharacteristic mControlCharacteristic;
    private BluetoothGattCharacteristic mStatusCharacteristic;
    private final Set<BluetoothDevice> mConnectedDevices = new ConcurrentHashSet<>();
    private final Map<BluetoothDevice, Boolean> mNotificationEnabled =
        new ConcurrentHashMap<>();

    // 启动GATT Server
    public void start(Context context) {
        BluetoothManager bluetoothManager =
            (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);

        mGattServer = bluetoothManager.openGattServer(context, mServerCallback);
        if (mGattServer == null) return;

        // 构建服务
        BluetoothGattService service = createRemoteControlService();
        mGattServer.addService(service);
    }

    // 构建遥控服务
    private BluetoothGattService createRemoteControlService() {
        BluetoothGattService service = new BluetoothGattService(
            REMOTE_CONTROL_SERVICE_UUID,
            BluetoothGattService.SERVICE_TYPE_PRIMARY
        );

        // 按键控制特征（可写+可通知）
        mControlCharacteristic = new BluetoothGattCharacteristic(
            CONTROL_CHARACTERISTIC_UUID,
            BluetoothGattCharacteristic.PROPERTY_WRITE
                | BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE
                | BluetoothGattCharacteristic.PROPERTY_NOTIFY,
            BluetoothGattCharacteristic.PERMISSION_WRITE
        );
        mControlCharacteristic.addDescriptor(createCccd());
        service.addCharacteristic(mControlCharacteristic);

        // 状态反馈特征（可读+可通知）
        mStatusCharacteristic = new BluetoothGattCharacteristic(
            STATUS_CHARACTERISTIC_UUID,
            BluetoothGattCharacteristic.PROPERTY_READ
                | BluetoothGattCharacteristic.PROPERTY_NOTIFY,
            BluetoothGattCharacteristic.PERMISSION_READ
        );
        mStatusCharacteristic.addDescriptor(createCccd());
        service.addCharacteristic(mStatusCharacteristic);

        return service;
    }

    private BluetoothGattDescriptor createCccd() {
        return new BluetoothGattDescriptor(
            CCCD_UUID,
            BluetoothGattDescriptor.PERMISSION_READ
                | BluetoothGattDescriptor.PERMISSION_WRITE
        );
    }

    private final BluetoothGattServerCallback mServerCallback =
        new BluetoothGattServerCallback() {

        @Override
        public void onConnectionStateChange(BluetoothDevice device, int status,
                int newState) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                mConnectedDevices.add(device);
                // 主动连接回来（建立双向通信通道）
                mGattServer.connect(device, false);
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                mConnectedDevices.remove(device);
                mNotificationEnabled.remove(device);
            }
        }

        @Override
        public void onServiceAdded(int status, BluetoothGattService service) {
            if (status == BluetoothGatt.GATT_SUCCESS) {
                // 服务添加成功，可以开始广播
                startAdvertising();
            }
        }

        @Override
        public void onCharacteristicReadRequest(BluetoothDevice device, int requestId,
                int offset, BluetoothGattCharacteristic characteristic) {
            byte[] value = null;
            if (characteristic.getUuid().equals(STATUS_CHARACTERISTIC_UUID)) {
                value = getCurrentStatus();
            }
            mGattServer.sendResponse(device, requestId,
                BluetoothGatt.GATT_SUCCESS, 0, value);
        }

        @Override
        public void onCharacteristicWriteRequest(BluetoothDevice device, int requestId,
                BluetoothGattCharacteristic characteristic, boolean preparedWrite,
                boolean responseNeeded, int offset, byte[] value) {
            if (characteristic.getUuid().equals(CONTROL_CHARACTERISTIC_UUID)) {
                // 处理遥控指令
                handleRemoteControlCommand(device, value);
            }

            if (responseNeeded) {
                mGattServer.sendResponse(device, requestId,
                    BluetoothGatt.GATT_SUCCESS, 0, null);
            }
        }

        @Override
        public void onDescriptorReadRequest(BluetoothDevice device, int requestId,
                int offset, BluetoothGattDescriptor descriptor) {
            if (descriptor.getUuid().equals(CCCD_UUID)) {
                boolean enabled = mNotificationEnabled.getOrDefault(device, false);
                byte[] value = enabled
                    ? BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                    : BluetoothGattDescriptor.DISABLE_NOTIFICATION_VALUE;
                mGattServer.sendResponse(device, requestId,
                    BluetoothGatt.GATT_SUCCESS, 0, value);
            }
        }

        @Override
        public void onDescriptorWriteRequest(BluetoothDevice device, int requestId,
                BluetoothGattDescriptor descriptor, boolean preparedWrite,
                boolean responseNeeded, int offset, byte[] value) {
            if (descriptor.getUuid().equals(CCCD_UUID)) {
                if (Arrays.equals(value, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                        || Arrays.equals(value, BluetoothGattDescriptor.ENABLE_INDICATION_VALUE)) {
                    mNotificationEnabled.put(device, true);
                } else {
                    mNotificationEnabled.put(device, false);
                }
            }

            if (responseNeeded) {
                mGattServer.sendResponse(device, requestId,
                    BluetoothGatt.GATT_SUCCESS, 0, null);
            }
        }

        @Override
        public void onNotificationSent(BluetoothDevice device, int status) {
            // 通知发送完成
        }

        @Override
        public void onMtuChanged(BluetoothDevice device, int mtu) {
            // MTU变化
        }
    };

    // 向远端设备推送状态通知
    public void notifyStatus(BluetoothDevice device, byte[] status) {
        if (mNotificationEnabled.getOrDefault(device, false)) {
            mGattServer.notifyCharacteristicChanged(
                device, mStatusCharacteristic, false, status);
        }
    }

    // 向所有已连接设备推送状态通知
    public void notifyStatusToAll(byte[] status) {
        for (BluetoothDevice device : mConnectedDevices) {
            notifyStatus(device, status);
        }
    }

    // 处理遥控指令（由子类实现）
    protected void handleRemoteControlCommand(BluetoothDevice device, byte[] command) {
        // 解析遥控指令并执行
    }

    protected byte[] getCurrentStatus() {
        // 返回当前状态
        return new byte[0];
    }

    // 开启BLE广播
    private void startAdvertising() {
        // 参见4.4节广播对接
    }

    // 关闭
    public void stop() {
        if (mGattServer != null) {
            mGattServer.close();
            mGattServer = null;
        }
    }
}
```

---

# 第五部分：后排屏遥控场景分析

## 5.1 场景需求分析

### 业务场景

车机后排屏幕需要支持多种遥控器（物理遥控器、手机App遥控器）通过BLE GATT连接来控制屏幕操作（如音量调节、频道切换、播放控制等）。

### 核心需求

| 需求 | 说明 |
|------|------|
| 多遥控器连接 | 同时支持多个遥控器连接（物理遥控器+手机遥控器） |
| 低延迟控制 | 遥控操作需要低延迟响应 |
| 双向通信 | 遥控器发送指令，屏幕反馈状态 |
| 自动重连 | 遥控器断开后自动重连 |
| 安全性 | 防止未授权设备控制屏幕 |
| 多屏幕支持 | 多个后排屏幕可被不同遥控器控制 |

### 角色分配

```
┌─────────────────────────────────────────────────────┐
│                    车机后排屏幕                       │
│                                                     │
│              GATT Server (数据提供方)                │
│              - 提供遥控服务                           │
│              - 接收遥控指令                           │
│              - 推送屏幕状态                           │
│              - BLE广播（让遥控器发现）                │
│                                                     │
└─────────────────┬───────────────────────────────────┘
                  │
        ┌─────────┼──────────┐
        │         │          │
        ▼         ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │ 物理遥控 │ │ 手机App │ │ 手机App │
   │  器 #1  │ │ 遥控 #2 │ │ 遥控 #3 │
   │         │ │         │ │         │
   │ GATT    │ │ GATT    │ │ GATT    │
   │ Client  │ │ Client  │ │ Client  │
   └─────────┘ └─────────┘ └─────────┘
```

## 5.2 架构方案设计

### 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                     应用层 (Vehicle App)                      │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ RemoteControl    │  │ ScreenManager    │                 │
│  │ Service          │  │                  │                 │
│  └────────┬─────────┘  └────────▲─────────┘                 │
│           │                     │                             │
├───────────┼─────────────────────┼─────────────────────────────┤
│           │     Framework 层    │                             │
│  ┌────────▼─────────┐  ┌───────┴──────────┐                 │
│  │ BluetoothGatt    │  │ BluetoothGatt    │                 │
│  │ Server           │  │ ServerCallback   │                 │
│  └────────┬─────────┘  └──────────────────┘                 │
│           │                                                   │
├───────────┼───────────────────────────────────────────────────┤
│           │     Bluetooth Service 层                          │
│  ┌────────▼─────────┐                                        │
│  │ GattService      │                                        │
│  │ + ScanManager    │                                        │
│  │ + AdvertiseMgr   │                                        │
│  └────────┬─────────┘                                        │
│           │                                                   │
├───────────┼───────────────────────────────────────────────────┤
│           │     Native 层                                     │
│  ┌────────▼─────────┐                                        │
│  │ GattNative       │                                        │
│  │ Interface        │                                        │
│  └──────────────────┘                                        │
└──────────────────────────────────────────────────────────────┘
```

### 模块职责

| 模块 | 职责 |
|------|------|
| RemoteControlService | 车机应用层服务，管理GATT Server生命周期，处理遥控指令，维护遥控器列表 |
| ScreenManager | 屏幕控制管理，执行遥控指令（音量、频道等），提供屏幕状态 |
| BluetoothGattServer | Framework API，提供GATT Server能力 |
| GattService | 系统服务，管理GATT连接 |

## 5.3 GATT服务设计

### 服务UUID规划

```java
// 遥控服务
public class RemoteControlUuids {
    // 服务UUID（自定义128位UUID）
    public static final UUID REMOTE_CONTROL_SERVICE =
        UUID.fromString("A1B2C3D4-E5F6-7890-ABCD-EF1234567890");

    // 遥控输入特征（遥控器→屏幕）
    // Properties: WRITE | WRITE_NO_RESPONSE | NOTIFY
    // 遥控器写入按键指令，屏幕通知遥控器按键执行结果
    public static final UUID REMOTE_INPUT_CHARACTERISTIC =
        UUID.fromString("A1B2C3D4-E5F6-7890-ABCD-EF1234567891");

    // 屏幕状态特征（屏幕→遥控器）
    // Properties: READ | NOTIFY
    // 遥控器读取当前屏幕状态，屏幕推送状态变化通知
    public static final UUID SCREEN_STATUS_CHARACTERISTIC =
        UUID.fromString("A1B2C3D4-E5F6-7890-ABCD-EF1234567892");

    // 遥控器信息特征（遥控器→屏幕）
    // Properties: READ | WRITE
    // 遥控器上报设备类型、电量等信息
    public static final UUID REMOTE_INFO_CHARACTERISTIC =
        UUID.fromString("A1B2C3D4-E5F6-7890-ABCD-EF1234567893");

    // 配对绑定特征
    // Properties: WRITE | NOTIFY
    // 用于遥控器与屏幕的配对绑定流程
    public static final UUID PAIRING_CHARACTERISTIC =
        UUID.fromString("A1B2C3D4-E5F6-7890-ABCD-EF1234567894");
}
```

### 数据协议设计

#### 遥控输入特征数据格式

```
字节偏移  长度   字段        说明
0        1     opcode     操作码
1        1     paramLen   参数长度
2~n      可变   params     参数数据

操作码定义:
0x01  KEY_PRESS       按键按下    params: [key_code]
0x02  KEY_RELEASE     按键释放    params: [key_code]
0x03  KEY_LONG_PRESS  长按        params: [key_code, duration]
0x04  TOUCH_EVENT     触摸事件    params: [action, x(2bytes), y(2bytes)]
0x05  GESTURE         手势        params: [gesture_type, ...]
0x06  VOLUME_CONTROL  音量控制    params: [direction]
0x07  CHANNEL_SWITCH  频道切换    params: [channel_id(2bytes)]
0x08  PLAYBACK_CTRL   播放控制    params: [action]

按键码定义:
0x01  KEY_UP          上
0x02  KEY_DOWN        下
0x03  KEY_LEFT        左
0x04  KEY_RIGHT       右
0x05  KEY_OK          确认
0x06  KEY_BACK        返回
0x07  KEY_HOME        主页
0x08  KEY_MENU        菜单
0x09  KEY_VOLUME_UP   音量+
0x0A  KEY_VOLUME_DOWN 音量-
0x0B  KEY_MUTE        静音
0x0C  KEY_PLAY_PAUSE  播放/暂停
```

#### 屏幕状态特征数据格式

```
字节偏移  长度   字段        说明
0        1     stateType  状态类型
1        可变   stateData  状态数据

状态类型:
0x01  CURRENT_APP     当前应用    data: [app_id]
0x02  VOLUME          音量        data: [volume_level]
0x03  PLAYBACK_STATE  播放状态    data: [state]
0x04  CHANNEL         当前频道    data: [channel_id(2bytes)]
```

### GATT属性表

| Handle | Type | Properties | 说明 |
|--------|------|------------|------|
| 0x0001 | 0x2800 | READ | Primary Service: REMOTE_CONTROL_SERVICE |
| 0x0002 | 0x2803 | READ | Char Declaration: REMOTE_INPUT (WRITE\|WRITE_NO_RESP\|NOTIFY) |
| 0x0003 | REMOTE_INPUT_UUID | WRITE/WRITE_NO_RESP/NOTIFY | 遥控输入值 |
| 0x0004 | 0x2902 | READ/WRITE | CCCD |
| 0x0005 | 0x2803 | READ | Char Declaration: SCREEN_STATUS (READ\|NOTIFY) |
| 0x0006 | SCREEN_STATUS_UUID | READ/NOTIFY | 屏幕状态值 |
| 0x0007 | 0x2902 | READ/WRITE | CCCD |
| 0x0008 | 0x2803 | READ | Char Declaration: REMOTE_INFO (READ\|WRITE) |
| 0x0009 | REMOTE_INFO_UUID | READ/WRITE | 遥控器信息值 |
| 0x000A | 0x2803 | READ | Char Declaration: PAIRING (WRITE\|NOTIFY) |
| 0x000B | PAIRING_UUID | WRITE/NOTIFY | 配对绑定值 |
| 0x000C | 0x2902 | READ/WRITE | CCCD |

## 5.4 多遥控器管理

### 连接管理架构

```
┌──────────────────────────────────────────────────────────────┐
│                   RemoteControlManager                        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 BluetoothGattServer                   │   │
│  │                                                      │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐      │   │
│  │  │ Remote #1  │ │ Remote #2  │ │ Remote #3  │      │   │
│  │  │ (物理遥控) │ │ (手机App)  │ │ (手机App)  │      │   │
│  │  │ connected  │ │ connected  │ │ connected  │      │   │
│  │  └────────────┘ └────────────┘ └────────────┘      │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              CommandDispatcher                        │   │
│  │  - 接收所有遥控器的指令                                │   │
│  │  - 指令去重/冲突解决                                  │   │
│  │  - 分发到ScreenManager                                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              StatusBroadcaster                        │   │
│  │  - 屏幕状态变化时通知所有已连接遥控器                   │   │
│  │  - 管理每个遥控器的通知订阅状态                        │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 多遥控器冲突解决

当多个遥控器同时操作时，需要冲突解决策略：

| 策略 | 说明 | 适用场景 |
|------|------|----------|
| 最后操作优先 | 最后收到的指令覆盖之前的 | 一般控制 |
| 优先级策略 | 物理遥控器 > 手机遥控器 | 安全相关操作 |
| 锁定策略 | 第一个操作的遥控器锁定控制权 | 播放控制 |
| 分区策略 | 不同遥控器控制不同区域 | 多区域屏幕 |

## 5.5 关键技术点

### 5.5.1 低延迟优化

```java
// 1. 使用高优先级连接
gatt.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH);

// 2. 使用WRITE_NO_RESPONSE减少往返
int result = gatt.writeCharacteristic(characteristic, data,
    BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);

// 3. 协商大MTU减少分包
gatt.requestMtu(517);

// 4. 使用Notification而非Indication
// Notification不需要确认，延迟更低

// 5. 使用LE 2M PHY
gatt.setPreferredPhy(BluetoothDevice.PHY_LE_2M_MASK,
    BluetoothDevice.PHY_LE_2M_MASK,
    BluetoothDevice.PHY_OPTION_NO_PREFERRED);
```

### 5.5.2 自动重连

```java
// 客户端：使用autoConnect模式
BluetoothGatt gatt = device.connectGatt(context, true, gattCallback);

// 服务端：监听断开事件，等待重连
@Override
public void onConnectionStateChange(BluetoothDevice device, int status, int newState) {
    if (newState == BluetoothProfile.STATE_DISCONNECTED) {
        // 不主动移除设备，等待自动重连
        // 设置超时清理
        handler.postDelayed(() -> {
            if (!isDeviceConnected(device)) {
                removeDevice(device);
            }
        }, RECONNECT_TIMEOUT);
    }
}
```

### 5.5.3 安全性

```java
// 1. 使用加密连接
// 在Characteristic上设置加密权限
BluetoothGattCharacteristic characteristic = new BluetoothGattCharacteristic(
    UUID,
    BluetoothGattCharacteristic.PROPERTY_WRITE,
    BluetoothGattCharacteristic.PERMISSION_WRITE_ENCRYPTED_MITM
);

// 2. 应用层配对验证
// 在PAIRING特征中实现challenge-response协议

// 3. 白名单过滤
@Override
public void onConnectionStateChange(BluetoothDevice device, int status, int newState) {
    if (newState == BluetoothProfile.STATE_CONNECTED) {
        if (!isDeviceAuthorized(device)) {
            gattServer.cancelConnection(device);
        }
    }
}
```

### 5.5.4 多连接管理

```java
// BLE支持一个GATT Server同时连接多个Client
// 每个连接独立管理通知订阅状态

// 关键：为每个设备维护独立的通知状态
private final Map<BluetoothDevice, Set<UUID>> mDeviceNotificationMap =
    new ConcurrentHashMap<>();

@Override
public void onDescriptorWriteRequest(BluetoothDevice device, int requestId,
        BluetoothGattDescriptor descriptor, boolean preparedWrite,
        boolean responseNeeded, int offset, byte[] value) {
    UUID charUuid = descriptor.getCharacteristic().getUuid();
    Set<UUID> enabledChars = mDeviceNotificationMap.computeIfAbsent(
        device, k -> new HashSet<>());

    if (Arrays.equals(value, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)) {
        enabledChars.add(charUuid);
    } else {
        enabledChars.remove(charUuid);
    }

    if (responseNeeded) {
        mGattServer.sendResponse(device, requestId,
            BluetoothGatt.GATT_SUCCESS, 0, null);
    }
}

// 推送通知时检查每个设备的订阅状态
public void notifyAllDevices(BluetoothGattCharacteristic characteristic, byte[] value) {
    for (BluetoothDevice device : mConnectedDevices) {
        Set<UUID> enabledChars = mDeviceNotificationMap.get(device);
        if (enabledChars != null && enabledChars.contains(characteristic.getUuid())) {
            mGattServer.notifyCharacteristicChanged(device, characteristic, false, value);
        }
    }
}
```

### 5.5.5 Android 16 Subrate模式

Android 16新增的LE Subrate功能可以进一步优化低延迟场景：

```java
// 请求高Subrate模式（降低延迟）
int result = gatt.requestSubrateMode(BluetoothGatt.SUBRATE_MODE_HIGH);

// Subrate模式常量
// SUBRATE_MODE_OFF     = 0  // 关闭
// SUBRATE_MODE_LOW     = 1  // 低功耗
// SUBRATE_MODE_BALANCED = 2 // 平衡
// SUBRATE_MODE_HIGH    = 3  // 高性能（低延迟）
```

### 5.5.6 Service Changed机制

当GATT Server的服务结构发生变化时（如动态添加/删除服务），需要通知已连接的Client重新发现服务：

```java
// GATT规范要求：如果Server的服务发生变化，必须通过Service Changed特征通知Client
// Service Changed特征UUID: 0x2A05
// 位于Generic Attribute Service (0x1801) 中

// 在Framework层，这通过onServiceChanged回调实现
@Override
public void onServiceChanged(BluetoothGatt gatt) {
    // 服务发生变化，需要重新发现
    gatt.discoverServices();
}
```

---

# 附录

## A. GATT错误码速查表

| 错误码 | 名称 | 说明 |
|--------|------|------|
| 0x00 | SUCCESS | 成功 |
| 0x01 | INVALID_HANDLE | 无效句柄 |
| 0x02 | READ_NOT_PERMITTED | 读取不允许 |
| 0x03 | WRITE_NOT_PERMITTED | 写入不允许 |
| 0x04 | INVALID_PDU | 无效PDU |
| 0x05 | INSUFFICIENT_AUTHENTICATION | 认证不足 |
| 0x06 | REQUEST_NOT_SUPPORTED | 请求不支持 |
| 0x07 | INVALID_OFFSET | 无效偏移 |
| 0x08 | INSUFFICIENT_AUTHORIZATION | 授权不足 |
| 0x09 | PREPARE_QUEUE_FULL | 准备队列满 |
| 0x0A | ATTRIBUTE_NOT_FOUND | 属性未找到 |
| 0x0B | ATTRIBUTE_NOT_LONG | 属性不支持长读 |
| 0x0C | INSUFFICIENT_ENCRYPTION_KEY_SIZE | 加密密钥长度不足 |
| 0x0D | INVALID_ATTRIBUTE_VALUE_LENGTH | 属性值长度无效 |
| 0x0E | UNLIKELY_ERROR | 不太可能的错误 |
| 0x0F | INSUFFICIENT_ENCRYPTION | 加密不足 |
| 0x10 | UNSUPPORTED_GROUP_TYPE | 不支持的组类型 |
| 0x11 | INSUFFICIENT_RESOURCES | 资源不足 |
| 0x101 | GATT_FAILURE | 通用失败 |
| 0x143 | CONNECTION_CONGESTED | 连接拥塞 |

## B. 常用SIG标准服务UUID

| UUID | 名称 | 说明 |
|------|------|------|
| 0x1800 | Generic Access | 通用访问 |
| 0x1801 | Generic Attribute | 通用属性（含Service Changed） |
| 0x180A | Device Information | 设备信息 |
| 0x180F | Battery Service | 电池服务 |
| 0x1812 | HID Service | 人机接口设备（键盘/鼠标/遥控器） |
| 0x1813 | Scan Parameters | 扫描参数 |
| 0x1816 | Cycling Speed and Cadence | 自行车速度与踏频 |
| 0x1818 | Cycling Power | 自行车功率 |
| 0x1819 | Location and Navigation | 位置与导航 |
| 0x181A | Environmental Sensing | 环境感知 |
| 0x181B | Body Composition | 人体成分 |
| 0x181D | Weight Scale | 体重秤 |
| 0x181E | Bond Management | 绑定管理 |
| 0x181F | Continuous Glucose Monitoring | 连续血糖监测 |
| 0x1820 | Internet Protocol Support | IP支持 |
| 0x1821 | Indoor Positioning | 室内定位 |
| 0x1822 | Pulse Oximeter | 脉搏血氧仪 |
| 0x1823 | HTTP Proxy | HTTP代理 |
| 0x1824 | Transport Discovery | 传输发现 |
| 0x1825 | Object Transfer | 对象传输 |

## C. 常用SIG标准描述符UUID

| UUID | 名称 | 说明 |
|------|------|------|
| 0x2900 | Characteristic Extended Properties | 特征扩展属性 |
| 0x2901 | Characteristic User Description | 特征用户描述 |
| 0x2902 | Client Characteristic Configuration | 客户端特征配置（CCCD） |
| 0x2903 | Server Characteristic Configuration | 服务端特征配置 |
| 0x2904 | Characteristic Presentation Format | 特征呈现格式 |
| 0x2905 | Characteristic Aggregate Format | 特征聚合格式 |
| 0x2906 | Valid Range | 有效范围 |
| 0x2907 | External Report Reference | 外部报告引用 |
| 0x2908 | Report Reference | 报告引用 |
| 0x290B | Environmental Sensing Configuration | 环境感知配置 |
| 0x290C | Environmental Sensing Measurement | 环境感知测量 |
| 0x290D | Environmental Sensing Trigger Setting | 环境感知触发设置 |

## D. Android GATT API版本演进

| Android版本 | API Level | 新增GATT特性 |
|-------------|-----------|-------------|
| 4.3 | 18 | 首次引入BLE GATT API |
| 5.0 | 21 | BluetoothLeScanner/BluetoothLeAdvertiser |
| 7.0 | 24 | PHY API（setPreferredPhy/readPhy） |
| 8.0 | 26 | CompanionDeviceManager |
| 8.1 | 27 | 写特征值返回状态码 |
| 9.0 | 28 | 后台扫描限制、ScanSettings新模式 |
| 10 | 29 | PHY LE Coded支持 |
| 11 | 30 | GATT连接超时控制 |
| 12 | 31 | 新权限模型（BLUETOOTH_SCAN/ADVERTISE/CONNECT） |
| 13 | 33 | writeCharacteristic新API（传byte[]） |
| 14 | 34 | onCharacteristicChanged新签名（含byte[]） |
| 15 | 35 | LE Subrate模式API |
| 16 | 36 | Subrate模式增强、多Bearer连接 |

## E. 调试技巧

### E.1 查看GATT连接状态

```bash
# 查看已连接的BLE设备
adb shell dumpsys bluetooth_manager | grep "LE"

# 查看GATT服务详情
adb shell dumpsys bluetooth_manager | grep -A 50 "GATT Service"

# 查看所有GATT连接
adb shell dumpsys bluetooth_manager | grep -A 20 "gatt_client"
```

### E.2 开启BLE日志

```bash
# 开启Bluetooth详细日志
adb shell setprop persist.bluetooth.btsnoopenable true
adb shell setprop persist.log.tag.bluetooth verbose

# 开启GATT日志
adb shell setprop log.tag.BtGatt.GattService VERBOSE
adb shell setprop log.tag.BtGatt.GattNativeInterface VERBOSE
```

### E.3 常见问题排查

| 问题 | 可能原因 | 排查方法 |
|------|----------|----------|
| 连接后立即断开 | MTU协商失败、权限不足 | 检查onConnectionStateChange的status码 |
| 服务发现为空 | 缓存问题 | 调用gatt.refresh()清除缓存 |
| 写入失败 | mDeviceBusy=true | 确保上一个操作的回调已返回 |
| 通知收不到 | 未写入CCCD | 确认已写入ENABLE_NOTIFICATION_VALUE |
| 133错误 | 连接资源泄漏 | 确保disconnect后调用close() |
| 257错误 | 写入长度超MTU | 先协商更大的MTU |

---

> 本文档基于Android 16源码编写，源码路径：`d:\AndroidWorkspace\claudeProject\BT16Study\Bluetooth\`
