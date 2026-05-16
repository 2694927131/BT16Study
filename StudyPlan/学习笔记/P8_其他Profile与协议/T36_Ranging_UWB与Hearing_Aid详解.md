# T36 Ranging/UWB与Hearing Aid详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：
> 1. Channel Sounding (UWB)基于LE链路实现Phase-based Ranging，通过IQ采样+ToA/ToD计算距离，支持SW/HW两种数据处理模式
> 2. Ranging Service (RAS)通过GATT提供实时/按需测距数据，5种Opcode+3种EventCode实现完整的测距请求/响应协议
> 3. Hearing Aid (ASHA)支持双耳助听器，通过HiSyncId配对同一套设备，Capability位指示左右耳/单双耳模式
> 4. TBS/MCP/VCP/CSIS/HAS组成完整的LE Audio辅助服务生态，覆盖通话控制、媒体控制、音量管理、设备协调集、听力辅助

---

## 一、Channel Sounding / UWB Ranging（信道测距）

### 1.1 技术背景

Channel Sounding 是蓝牙 6.0 (BT Core Spec v6.0) 引入的**高精度测距**技术，使用 BLE PHY 实现 Phase-based Ranging (PBR) 和 Round-Trip Timing (RTT)：

- **PBR (Phase-based Ranging)**：通过多个频率的 Radio Tone Exchange 测量相位差 → 计算距离
- **RTT (Round-Trip Timing)**：测量无线信号在 Initiator ↔ Reflector 间来回时间 → 计算距离
- **精度**：亚米级 (10-30cm)，远优于传统 RSSI 测距 (5-10m)

**LE CS (Channel Sounding) 工作在**：由蓝牙 6.0 规范 `Vol 4, Part E 7.7.65.44` 定义

### 1.2 架构分层

```
┌──────────────────────────────────────────────────┐
│  应用场景                                          │
│  数字钥匙 (CCC DK) / 资产追踪 / 精确找物          │
├──────────────────────────────────────────────────┤
│  RAS (Ranging Service) - GATT Service 0x185B      │
│  bta/ras/ras_server.cc (Server)                   │
│  bta/ras/ras_client.cc (Client)                   │
│  bta/include/bta_ras_api.h (API)                  │
├──────────────────────────────────────────────────┤
│  Bluetooth LE CS (Channel Sounding) HCI Commands  │
│  Creator/Acceptor 角色                             │
│  ┌─────────────────────────────────────────┐     │
│  │ HCI LE CS Subevent Result               │     │
│  │  ├─ Mode 0: Frequency Offset + RSSI     │     │
│  │  ├─ Mode 2: IQ Samples (PBR)            │     │
│  │  └─ Mode 3: TOA/TOD (RTT)               │     │
│  └─────────────────────────────────────────┘     │
├──────────────────────────────────────────────────┤
│  Ranging HAL (Hardware Abstraction)               │
│  gd/hal/ranging_hal.h                             │
│  gd/hal/ranging_hal_impl_android.h/cc (AIDL)     │
│  ┌─────────────────────────────────────────┐     │
│  │ RangingHalImpl (Android)                 │     │
│  │  ├─ 与IBluetoothChannelSounding AIDL交互 │     │
│  │  ├─ Session管理 (SW/HW offload)          │     │
│  │  ├─ RawData写入 / Config更新             │     │
│  │  └─ ProcedureData下发                   │     │
│  └─────────────────────────────────────────┘     │
├──────────────────────────────────────────────────┤
│  Bluetooth Controller (支持CS的硬件)              │
└──────────────────────────────────────────────────┘
```

**核心源码文件**：

| 文件 | 路径 |
|------|------|
| ranging_hal.h (HAL接口) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal.h) |
| ranging_hal_impl_android.h (Android实现) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal_impl_android.h) |
| ranging_hal_impl_android.cc (实现590行) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal_impl_android.cc) |
| ras_types.h (RAS类型) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/ras/ras_types.h) |
| ras_client.cc (RAS客户端997行) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/ras/ras_client.cc) |
| ras_server.cc (RAS服务端806行) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/ras/ras_server.cc) |
| bta_ras_api.h (RAS API) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/include/bta_ras_api.h) |
| ranging.aconfig (特性开关) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/ranging.aconfig) |

---

### 1.3 Ranging HAL 接口设计

[ranging_hal.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal.h) 定义了完整的数据结构和接口：

**两种工作模式**：

```cpp
enum class RangingSessionType : uint8_t {
  SOFTWARE_STACK_DATA_PARSING = 0,  // 软件解析: RAW数据由协议栈软件处理
  HARDWARE_OFFLOAD_DATA_PARSING      // 硬件卸载: Controller直接计算距离
};

enum RangingHalVersion {
  V_UNKNOWN = 0,
  V_1 = 1,  // 基础Channel Sounding
  V_2 = 2,  // 增强功能
};
```

**Channel Sounding 步骤数据 (4种Mode)**：

| Mode | 数据内容 | 用途 |
|------|---------|------|
| **Mode 0** | Packet Quality + RSSI + Antenna | **基础测距**：信号质量+天线信息 |
| **Mode 1** | Frequency Offset Extension | 频率补偿 |
| **Mode 2** | **IQ Samples** (复数) + Quality | **PBR测距**：I/Q复数值 → 相位差 → 距离 |
| **Mode 3** | **ToA/ToD** (Time-of-Arrival/Departure) | **RTT测距**：精确时间戳 → 往返距离 |

**模式数据示例 — Mode 0** (最基础)：

```cpp
struct Mode0Data {
  uint8_t packet_quality_ = 0;     // 0-127 包质量
  uint8_t packet_rssi_ = 0x7F;     // RSSI (-127 ~ +20 dBm)
  uint8_t packet_antenna_ = 0;     // 天线路径 (0-based)
  uint16_t initiator_measured_offset; // Init侧频率偏移 (15 bits)
};
```

**原始数据包结构**：

```cpp
struct ChannelSoundingRawData {
  uint8_t num_antenna_paths_;                              // 天线数量
  std::vector<uint8_t> step_channel_;                      // 步骤→信道映射
  std::vector<std::vector<std::complex<double>>> tone_pct_initiator_;   // I侧 IQ
  std::vector<std::vector<std::complex<double>>> tone_pct_reflector_;   // R侧 IQ
  std::vector<std::vector<uint8_t>> tone_quality_indicator_initiator_;  // I侧质量
  std::vector<std::vector<uint8_t>> tone_quality_indicator_reflector_;  // R侧质量
  std::vector<int8_t> packet_quality_initiator;             // I侧包质量
  std::vector<int8_t> packet_quality_reflector;             // R侧包质量
  std::vector<int16_t> toa_tod_initiators_;                // I侧ToA/ToD
  std::vector<int16_t> tod_toa_reflectors_;                // R侧ToD/ToA
};
```

**HAL回调接口**：

```cpp
class RangingHalCallback {
  virtual void OnOpened(uint8_t session_id) = 0;           // Session打开成功
  virtual void OnOpenFailed(Reason reason) = 0;            // 打开失败
  virtual void OnHandleVendorSpecificReplyComplete(...) = 0; // Vendor回复完成
  virtual void OnResult(uint8_t session_id, const RangingResult& result) = 0; // ⭐测距结果
  virtual void OnClosed(uint8_t session_id, Reason reason) = 0; // Session关闭
};
```

---

### 1.4 RAS (Ranging Service) — GATT服务

RAS 是将底层 CS 测距数据通过 GATT 封装的**蓝牙服务**，允许设备通过标准 GATT 接口获取测距数据。

**GATT UUID体系** [ras_types.h:L26-L52](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/ras/ras_types.h#L26-L52)：

| UUID | 名称 | 类型 | 说明 |
|------|------|------|------|
| `0x185B` | Ranging Service | Service | RAS 服务主入口 |
| `0x2C14` | RAS Features | Read | 支持的功能位图 |
| `0x2C15` | **Real-time Ranging Data** | Notify | 实时测距数据推送 |
| `0x2C16` | On-demand Data | Indicate | 按需测距数据 |
| `0x2C17` | **Control Point** | Write | 控制点 (命令) |
| `0x2C18` | Ranging Data Ready | Indicate | 数据就绪通知 |
| `0x2C19` | Ranging Data Overwritten | Indicate | 数据被覆盖通知 |

**4种 Ranging Feature**：

```cpp
namespace feature {
  static const uint32_t kRealTimeRangingData      = 0x01;  // 实时数据
  static const uint32_t kRetrieveLostRangingDataSegments = 0x02;  // 恢复丢失数据段
  static const uint32_t kAbortOperation           = 0x04;  // 中止操作
  static const uint32_t kFilterRangingData        = 0x08;  // 过滤数据
}
```

**5种 Control Point Opcode**：

| Opcode | 操作 | 说明 |
|--------|------|------|
| `0x00` | GET_RANGING_DATA | 请求获取测距数据 |
| `0x01` | ACK_RANGING_DATA | 确认收到测距数据 |
| `0x02` | RETRIEVE_LOST_RANGING_DATA_SEGMENTS | 恢复丢失的数据段 |
| `0x03` | ABORT_OPERATION | 中止当前测距操作 |
| `0x04` | FILTER | 设置测距数据过滤器 |

**9种 Response Code**：

```cpp
enum class ResponseCodeValue {
  RESERVED = 0x00, SUCCESS = 0x01, OP_CODE_NOT_SUPPORTED = 0x02,
  INVALID_PARAMETER = 0x03, PERSISTED = 0x04, ABORT_UNSUCCESSFUL = 0x05,
  PROCEDURE_NOT_COMPLETED = 0x06, SERVER_BUSY = 0x07, NO_RECORDS_FOUND = 0x08,
};
```

**3种 Event Code**：

| Event Code | 事件 | 触发时机 |
|-----------|------|---------|
| `0x00` | COMPLETE_RANGING_DATA_RESPONSE | 全体测距数据已就绪 |
| `0x01` | COMPLETE_LOST_RANGING_DATA_SEGMENT_RESPONSE | 丢失段恢复完成 |
| `0x02` | RESPONSE_CODE | 命令执行结果 |

---

### 1.5 RAS Client 工作流程

[RAS Client](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/ras/ras_client.cc) (997行) 实现完整的测距客户端：

```
Client侧流程:
1. GATT连接 → 发现 Ranging Service (0x185B)
2. Read RAS Features → 了解Server能力
3. CCC订阅:
   ├── 实时模式: Subscribe Real-time Ranging Data (0x2C15) Notify
   │   └── Server持续推送数据 → Client接收+缓存
   │
   └── 按需模式:
       ├── Write Control Point: GET_RANGING_DATA (0x00)
       ├── Server通过 On-Demand Data (0x2C16) Indicate返回数据
       ├── 如果需要更多数据: ACK_RANGING_DATA → Server继续
       └── 超时处理 (默认超时30s)
```

**连接事件回调** (`RasClientCallbacks`)：

```cpp
struct RasClientCallbacks {
  virtual void OnConnected(const RawAddress& address, uint16_t conn_id,
                           uint32_t att_mtu, uint16_t conn_interval_ms) = 0;
  virtual void OnConnIntervalUpdated(const RawAddress& address, uint16_t conn_interval_ms) = 0;
  virtual void OnDisconnected(const RawAddress& address, bool is_clean) = 0;
  virtual void OnMtuChangedFromClient(const RawAddress& address, uint16_t mtu) = 0;
  virtual void OnWriteVendorSpecificReplyComplete(const RawAddress& address, bool success) = 0;
  virtual void OnRemoteData(const RawAddress&, const std::vector<uint8_t>& data) = 0;  // ⭐数据回调
  virtual void OnRemoteDataTimeout(const RawAddress&) = 0;  // 超时回调
};
```

---

### 1.6 数字钥匙应用 (CCC DK)

UWB Channel Sounding 的**最关键应用**是数字钥匙 (CCC Digital Key):

```
    车机 (Initiator)                    手机 (Reflector)
    ────────────────                   ────────────────
    1. BLE连接 (已有配对)
    2. 发现 RAS Service (0x185B)
    3. Write Control Point: GET_RANGING_DATA
    4. HCI LE CS Procedure:
       ├── 车机发送Radio Tones
       ├── 手机反射Radio Tones
       └── 测量相位差(IQ) + 往返时间(ToA/ToD)
    5. 计算距离:
       ├── PBR距离 = Σ(phase_diff × c / (2πf))
       └── RTT距离 = (ToA - ToD) × c / 2
    6. 融合距离 + 到达角(AoA) = 精确定位 (±30cm)

    安全等级:
      - 远距离 (>10m): 车机锁门
      - 中距离 (2-10m): 车机解锁车门 (Unlock)
      - 近距离 (<2m):  允许启动引擎 (Start Engine)
```

**Feature Flags** [ranging.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/ranging.aconfig)：

```aconfig
channel_sounding        → 启用 Channel Sounding (exported, 外部可见)
channel_sounding_offload → 硬件加速卸载机制 (HW Controller直接计算距离)
```

---

## 二、Hearing Aid (ASHA) — 助听器

### 2.1 ASHA 协议概述

ASHA (Audio Streaming for Hearing Aids) 是 Android 原生支持的助听器音频流协议，通过 BLE GATT 传输音频数据。

**核心概念**：

- **HiSyncId**：8字节的配对标识，同一套助听器(左+右)共享同一HiSyncId
- **Capability**：设备能力位图 (Side + Mode + CSIP support)
- **双耳模式 (Binaural)**：左右耳独立BLE连接，通过HiSyncId关联为一组

### 2.2 架构分层

```
┌──────────────────────────────────────────────────┐
│  Framework API: BluetoothHearingAid.java          │
│  ┌────────────────────────────────────────────┐  │
│  │ getHiSyncId() / getDeviceSide() /          │  │
│  │ getDeviceMode() / setVolume()              │  │
│  │ getAdvertisementServiceData()              │  │
│  └────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────┤
│  App Service: HearingAidService.java (823行)     │
│  ┌────────────────────────────────────────────┐  │
│  │ 生命周期: start()/stop()                    │  │
│  │ 设备管理: HiSyncId→Devices 映射             │  │
│  │ ActiveDevice 管理                           │  │
│  │ 自动连接 (开机/Service发现后)                │  │
│  └────────────────────────────────────────────┘  │
│  App StateMachine: HearingAidStateMachine (570行)│
│  ┌────────────────────────────────────────────┐  │
│  │ Disconnected → Connecting → Connected →    │  │
│  │ Disconnecting → Disconnected               │  │
│  │ 超时: 30秒连接超时                          │  │
│  └────────────────────────────────────────────┘  │
│  JNI: HearingAidNativeInterface.java             │
├──────────────────────────────────────────────────┤
│  BTIF: btif_hearing_aid.h (工厂函数)             │
├──────────────────────────────────────────────────┤
│  HAL: bt_hearing_aid.h                           │
│  ┌────────────────────────────────────────────┐  │
│  │ Init() / Connect() / Disconnect()           │  │
│  │ SetVolume() / AddToAcceptlist()            │  │
│  │ Cleanup() / RemoveDevice()                 │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
```

**核心 HAL 接口** [bt_hearing_aid.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_hearing_aid.h)：

```cpp
namespace bluetooth::asha {

enum class ConnectionState { DISCONNECTED = 0, CONNECTING, CONNECTED, DISCONNECTING };

class HearingAidCallbacks {
  virtual void OnConnectionState(ConnectionState state, const RawAddress& address) = 0;
  virtual void OnDeviceAvailable(uint8_t capabilities, uint64_t hiSyncId,
                                 const RawAddress& address) = 0; // ⭐设备可用回调
};

class HearingAidInterface {
  virtual void Init(HearingAidCallbacks* callbacks) = 0;   // 初始化+注册回调
  virtual void Connect(const RawAddress& address) = 0;     // 连接
  virtual void Disconnect(const RawAddress& address) = 0;  // 断开
  virtual void AddToAcceptlist(const RawAddress& address) = 0; // 添加到白名单(快速重连)
  virtual void SetVolume(int8_t volume) = 0;               // 设置音量
  virtual void Cleanup(void) = 0;                          // 清理
  virtual void RemoveDevice(const RawAddress& address) = 0; // 解绑后移除
};

}  // namespace bluetooth::asha
```

### 2.3 广播数据解析

助听器通过 BLE 广播包携带关键设备信息 ([BluetoothHearingAid.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothHearingAid.java#L80-L120))：

```java
// AdvertisementServiceData 解析:
public static final class AdvertisementServiceData {
    private final int mCapability;           // 能力字节
    private final int mTruncatedHiSyncId;    // 截断的HiSyncId (低32位)

    // 从Capability提取模式:
    // bit 1: 0=单声道(MONAURAL) / 1=双声道(BINAURAL)
    public @DeviceMode int getDeviceMode() {
        return (mCapability >> 1) & 1;
    }

    // 从Capability提取侧:
    // bit 0: 设备佩戴侧 (LEFT=0 / RIGHT=1)
    public @DeviceSide int getDeviceSide() {
        return mCapability & 1;
    }
}
```

**Capability 位定义**：

| 位 | 含义 | 值=0 | 值=1 |
|----|------|------|------|
| 0 | Side (左右耳) | LEFT | RIGHT |
| 1 | Mode (模式) | MONAURAL | BINAURAL |
| 2 | CSIP Support | No CSIP | Has CSIP |

**设备侧枚举**：

| DeviceSide | 说明 |
|-----------|------|
| `SIDE_LEFT = 0` | 左耳 |
| `SIDE_RIGHT = 1` | 右耳 |
| `SIDE_UNKNOWN = -1` | 未知（尚未连接） |

### 2.4 连接流程

```
1. 手机扫描 BLE 广播
    ├── 解析 AdvertisementData → 识别 ASHA Service UUID + Capability
    ├── 提取 TruncatedHiSyncId (低32位)
    └── 调用 getHiSyncId() 获取完整 8字节 HiSyncId

2. 自动连接策略 (Auto-Connect)
    ├── 手机添加到 Acceptlist (白名单) → BLE自动连接
    └── 或主动 BLE Connect → GATT Service Discovery → 连接 ASHA 服务

3. HearingAidService 管理双耳配对
    ├── HiSyncId 匹配 → 同一套左右耳归组
    ├── 左右耳各自独立BLE连接
    └── 设置 ActiveDevice (当前活跃的助听器)

4. 音频流开始
    │  音频数据通过 GATT Notification 实时推送

5. 音量控制
    │  setVolume(range: -128 ~ 127)
```

**StateMachine 定义** [HearingAidStateMachine.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/hearingaid/HearingAidStateMachine.java)：

| 状态 | 说明 |
|------|------|
| **Disconnected** | 未连接 (初始/断开后) |
| **Connecting** | 正在连接 (BLE建立中，30秒超时) |
| **Connected** | 已连接 (GATT就绪，可接收音频流) |
| **Disconnecting** | 正在断开 |

### 2.5 Feature Flag

[hearing_aid.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/hearing_aid.aconfig)：

```aconfig
asha_omit_gatt_after_svc_changed:
  当收到 Service Changed 事件后, 跳过对过期 GATT handle 的操作
  作用: 避免助听器GATT服务变更后操作无效handle导致崩溃
```

---

## 三、TBS (Telephone Bearer Service) — 电话承载服务

### 3.1 概述

TBS 是 LE Audio 中处理**电话通话控制**的 GATT 服务，允许耳机/助听器通过 BLE 控制手机的电话功能。

### 3.2 GATT UUID 体系

[TbsGatt.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/tbs/TbsGatt.java#L63-L81) 定义了 TBS 完整的 UUID 体系：

| UUID | 名称 | 类型 | 说明 |
|------|------|------|------|
| `0x184B` | TBS (Bearer Service) | Service | 单个电话Bearer |
| `0x184C` | GTBS (Generic TBS) | Service | 通用TBS (聚合所有Bearer) |
| `0x2BB3` | Bearer Provider Name | Read | 运营商名称 (如"中国移动") |
| `0x2BB4` | Bearer UCI | Read | 统一呼叫标识符 |
| `0x2BB5` | Bearer Technology | Read | 承载技术 (LTE/VoLTE/CS/...) |
| `0x2BB6` | URI Schemes List | Read | 支持的URI格式 |
| `0x2BB9` | Call List | Notify | 当前通话列表 |
| `0x2BBA` | Content Control ID | Read | 关联的媒体控制ID |
| `0x2BBB` | Status Flags | Notify | 状态标志(响铃/静音) |
| `0x2BBD` | Call State | Notify | 通话状态 |
| `0x2BBE` | **Call Control Point** | Write | **呼叫控制点** |
| `0x2BBF` | Control Point Optional Opcodes | Read | 支持的可选操作码 |
| `0x2BC0` | Termination Reason | Read | 挂断原因 |
| `0x2BC1` | Incoming Call | Notify | 来电信息 |
| `0x2BC2` | Call Friendly Name | Read | 通话中好友名 |

### 3.3 呼叫控制点操作码

**基本操作码** (必支持)：

| Opcode | 操作 | 说明 |
|--------|------|------|
| `0x00` | **ACCEPT** | 接听来电 |
| `0x01` | **TERMINATE** | 挂断当前通话 |
| `0x02` | LOCAL_HOLD | 本地保持 |
| `0x03` | LOCAL_RETRIEVE | 恢复保持的通话 |
| `0x04` | **ORIGINATE** | 发起去电 (通过URI) |
| `0x05` | JOIN | 合并通话 |

**可选操作码** (通过 `0x2BBF` 特征查询是否支持)：

```java
CALL_CONTROL_POINT_OPTIONAL_OPCODE_LOCAL_HOLD = 0x0001;  // 本地保持
CALL_CONTROL_POINT_OPTIONAL_OPCODE_JOIN       = 0x0002;  // 通话合并
```

**操作结果码**：

| Result | 说明 |
|--------|------|
| 0x00 | SUCCESS |
| 0x01 | OPCODE_NOT_SUPPORTED |
| 0x02 | OPERATION_NOT_POSSIBLE |
| 0x03 | INVALID_CALL_INDEX |
| 0x04 | STATE_MISMATCH (当前状态不允许) |

### 3.4 状态标志

```java
STATUS_FLAG_INBAND_RINGTONE_ENABLED = 0x0001;  // 耳机端响铃
STATUS_FLAG_SILENT_MODE_ENABLED     = 0x0002;  // 静音模式

// Bearer 技术位图:
TECHNOLOGY_3G  = 0x01,   // 3G
TECHNOLOGY_4G  = 0x02,   // LTE/4G
TECHNOLOGY_LTE = 0x04,   // LTE
TECHNOLOGY_WiFi= 0x08,   // Wi-Fi Calling
TECHNOLOGY_5G  = 0x10,   // 5G NR
```

### 3.5 车载 TBS 应用场景

```
车机 ↔ 耳机/助听器:
  1. 耳机发现 GTBS Service (0x184C) → 获取所有可用的Bearer
  2. 来电时: Incoming Call Notify → 用户按耳机按钮
  3. 耳机 Write Call Control Point: ACCEPT (0x00) → 手机接听
  4. 通话结束: Write Call Control Point: TERMINATE (0x01) → 手机挂断

与 HFP 的区别:
  HFP: 通过 RFCOMM+SCO 的经典蓝牙通话方案
  TBS: 通过 BLE GATT 的新一代通话控制方案 (LE Audio)
  双模共存: HFP 提供音频流; TBS 提供通话控制
```

**Feature Flag** [tbs.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/tbs.aconfig)：

```aconfig
tbs_set_lea_from_btservice:
  TBS 设置活跃 LE Audio 设备时应使用 AdapterService (bugfix)
```

---

## 四、MCP (Media Control Profile) — 媒体控制服务

### 4.1 概述

MCP 是 LE Audio 中的**媒体控制服务**，允许遥控设备(耳机/手表/车机)通过 BLE GATT 控制播放设备(手机)的媒体播放。

**服务角色**：
- **MCS (Media Control Service)**：在播放设备(手机)上运行
- **GMCS (Generic Media Control Service)**：聚合的通用控制服务
- **MCP Client**：在遥控设备(耳机/车机)上运行

### 4.2 MCP 支持的媒体控制操作

[Request.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/Request.java#L51-L75) 定义了完整的 Operation 集合：

| Opcode | 操作 | 说明 |
|--------|------|------|
| `0x01` | **PLAY** | 播放 |
| `0x02` | **PAUSE** | 暂停 |
| `0x04` | FAST_REWIND | 快退 |
| `0x08` | FAST_FORWARD | 快进 |
| `0x10` | **STOP** | 停止 |
| `0x20` | MOVE_RELATIVE | 相对跳转 |
| `0x40` | PREVIOUS_SEGMENT | 上一片段 |
| `0x80` | **NEXT_SEGMENT** | 下一片段 |
| `0x0100` | FIRST_SEGMENT | 第一个片段 |
| `0x0200` | LAST_SEGMENT | 最后一个片段 |
| `0x0800` | **PREVIOUS_TRACK** | 上一曲 |
| `0x1000` | **NEXT_TRACK** | 下一曲 |
| `0x2000` | FIRST_TRACK | 第一曲 |
| `0x4000` | LAST_TRACK | 最后一曲 |
| `0x8000` | GOTO_TRACK | 选中曲目 |
| `0x010000` | PREVIOUS_GROUP | 上一组 |
| `0x020000` | NEXT_GROUP | 下一组 |

**操作结果**：

| Result | 说明 |
|--------|------|
| 0x01 | SUCCESS |
| 0x02 | OPCODE_NOT_SUPPORTED |
| 0x03 | MEDIA_PLAYER_INACTIVE (播放器未激活) |
| 0x04 | COMMAND_CANNOT_BE_COMPLETED (无法完成) |

### 4.3 MCP 架构文件

| 文件 | 说明 |
|------|------|
| [McpService.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/McpService.java) (166行) | MCP核心服务：设备授权+GMCS管理 |
| [MediaControlProfile.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/MediaControlProfile.java) (950行) | 媒体控制核心逻辑：播放状态跟踪+指令处理 |
| [MediaControlGattService.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/MediaControlGattService.java) | GATT服务实现 |
| [MediaState.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/MediaState.java) | 播放状态(Playing/Paused/...) |
| [PlayerStateField.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/PlayerStateField.java) | 播放器状态字段(曲名/歌手/专辑/时长/...) |

**与 AVRCP 的关系**：
- AVRCP: 经典蓝牙媒体控制 (AVCTP+Browsing Channel)
- MCP: LE Audio 媒体控制 (GATT)，更省电、延迟更低
- 双模共存：Android 同时支持，耳机通过任一协议都可控制媒体

---

## 五、辅助 Profile 总结

### 5.1 CSIS (Coordinated Set Identification Service)

**位置**: [csis_types.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/csis/csis_types.h)

| 项目 | 说明 |
|------|------|
| UUID | Service `0x1846` |
| 用途 | 管理协调集(如TWS耳机左右耳) |
| 关键概念 | SIRK(Set Identity Resolving Key)群组密钥、Rank(1=左,2=右)、Lock(一次锁定全组成员) |
| 车载场景 | TWS耳机组管理、多扬声器同步 |

### 5.2 HAS (Hearing Access Service)

**位置**: [has_client.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/has/has_client.cc)

| 项目 | 说明 |
|------|------|
| UUID | Service `0x1854` |
| 用途 | 助听器预设管理 |
| 关键特征 | ActivePresetIndex(0x2BDC)、PresetControlPoint(0x2BDB)、HearingAidFeatures(0x2BDA) |
| 车载场景 | 切换助听器预设(车内/室外/嘈杂环境) |

### 5.3 VCS (Volume Control Service)

**位置**: [types.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/vc/types.h)

| 项目 | 说明 |
|------|------|
| UUID | VCS `0x1844`, VOCS `0x1845`, AICS `0x1843` |
| 用途 | 标准化音量控制 |
| 操作 | VolumeDown/Up/SetAbsolute/Mute/Unmute/Gain/AutoGain |
| 通道 | Volume Offset Control → 每通道独立偏移(左耳/右耳/中置) |
| 与AVRCP关系 | LE Audio原生音量方案，替代AVRCP AbsVol |

### 5.4 车载辅助 Profile 全景

```
LE Audio 完整服务生态:

  ┌─────────────────────────────────────────────────┐
  │                  车机 (CCP)                       │
  │  ┌───────────┐ ┌──────────┐ ┌─────────────────┐ │
  │  │ LeAudioService │ TbsService│ McpService       │ │
  │  │ (音频流)   │ (通话控制)│ (媒体控制)       │ │
  │  └───────────┘ └──────────┘ └─────────────────┘ │
  └────────────────────┬────────────────────────────┘
                       │ BLE GATT
  ┌────────────────────┼────────────────────────────┐
  │                 服务清单                           │
  │  AAC (ASC + PAC) → LE Audio 音频                  │
  │  TBS (0x184B/C)  → 电话控制                       │
  │  MCP (MCS/GMCS)  → 媒体控制                       │
  │  VCS (0x1844/5/3)→ 音量控制                       │
  │  CSIS (0x1846)   → 协调集管理                     │
  │  HAS (0x1854)    → 助听器预设                     │
  │  RAS (0x185B)    → UWB测距                        │
  │  TMAS (0x1855)   → 电话+媒体角色                  │
  │  GMAS (0x1858)   → 游戏音频角色                   │
  └──────────────────────────────────────────────────┘
```

---

## 六、Feature Flags 汇总

| Flag 文件 | Flag | 功能 |
|-----------|------|------|
| [ranging.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/ranging.aconfig) | `channel_sounding` | CS主开关 (exported) |
| [ranging.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/ranging.aconfig) | `channel_sounding_offload` | HW加速卸载 |
| [hearing_aid.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/hearing_aid.aconfig) | `asha_omit_gatt_after_svc_changed` | ASHA GATT handle守卫 |
| [tbs.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/tbs.aconfig) | `tbs_set_lea_from_btservice` | TBS活跃设备Bugfix |

---

## 七、源码文件索引

### Ranging / UWB (9个文件)

| 文件 | 路径 |
|------|------|
| ranging_hal.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal.h) |
| ranging_hal_impl_android.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal_impl_android.h) |
| ranging_hal_impl_android.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal_impl_android.cc) |
| ranging_hal_impl.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal_impl.h) |
| ranging_hal_impl_host.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/ranging_hal_impl_host.h) |
| ras_types.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/ras/ras_types.h) |
| ras_client.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/ras/ras_client.cc) |
| ras_server.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/ras/ras_server.cc) |
| bta_ras_api.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/include/bta_ras_api.h) |

### Hearing Aid (9个文件)

| 文件 | 路径 |
|------|------|
| bt_hearing_aid.h (HAL) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_hearing_aid.h) |
| btif_hearing_aid.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/include/btif_hearing_aid.h) |
| BluetoothHearingAid.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothHearingAid.java) |
| HearingAidService.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/hearingaid/HearingAidService.java) |
| HearingAidStateMachine.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/hearingaid/HearingAidStateMachine.java) |
| HearingAidNativeInterface.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/hearingaid/HearingAidNativeInterface.java) |
| HearingAidServiceBinder.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/hearingaid/HearingAidServiceBinder.java) |
| HearingAidStackEvent.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/hearingaid/HearingAidStackEvent.java) |
| hearing_aid.aconfig | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/hearing_aid.aconfig) |

### TBS (6个文件)

| 文件 | 路径 |
|------|------|
| TbsGatt.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/tbs/TbsGatt.java) |
| TbsService.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/tbs/TbsService.java) |
| TbsGeneric.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/tbs/TbsGeneric.java) |
| TbsCall.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/tbs/TbsCall.java) |
| BluetoothGattServerProxy.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/tbs/BluetoothGattServerProxy.java) |
| tbs.aconfig | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/tbs.aconfig) |

### MCP (16个文件)

| 文件 | 路径 |
|------|------|
| McpService.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/McpService.java) |
| MediaControlProfile.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/MediaControlProfile.java) |
| MediaControlGattService.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/MediaControlGattService.java) |
| Request.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/mcp/Request.java) |

### 辅助 Profile 源码 (前面已覆盖)

| Profile | 文件 |
|---------|------|
| CSIS | [csis_types.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/csis/csis_types.h), [csis_client.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/csis/csis_client.cc) |
| HAS | [has_client.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/has/has_client.cc), [has_types.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/has/has_types.h) |
| VCS | [types.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/vc/types.h), [vc.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/vc/vc.cc) |
| Feature Flags | [ranging.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/ranging.aconfig), [hearing_aid.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/hearing_aid.aconfig), [tbs.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/tbs.aconfig) |