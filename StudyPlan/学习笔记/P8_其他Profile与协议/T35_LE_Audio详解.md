# T35 LE Audio详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：
> 1. LE Audio是蓝牙5.2引入的全新音频架构，核心是**LC3编解码器**+**等时通道(ISO)**,彻底替换SBC+A2DP/ACL传统方案
> 2. 等时通道分两类: **CIS**(Connected Isochronous Stream，单播)+**BIS**(Broadcast Isochronous Stream，Auracast广播)
> 3. BAP通过**ASE**(Audio Stream Endpoint)状态机控制音频流,通过**PAC**(Published Audio Capabilities)发布设备能力
> 4. LE Audio完整服务生态包括TMAP(角色定义)、CSIS(协调集)、HAS(助听器)、VCS(音量控制)、GMAP(游戏音频)

---

## 一、LE Audio vs 经典蓝牙音频

### 1.1 核心差异对比

| 维度 | 经典蓝牙音频 (BR/EDR) | LE Audio (BLE) |
|------|----------------------|----------------|
| **传输层** | ACL + AVDTP/AVCTP | ISO (等时通道) + 直接GATT |
| **编解码器** | **SBC** (强制) + AAC/aptX/LDAC (可选) | **LC3** (强制) + Opus/Vendor (可选) |
| **典型延迟** | 100-200ms | **20-40ms** (LC3 7.5ms帧) |
| **功耗** | 较高 (持续ACL活动) | **低50%+** (ISO调度+长连接间隔) |
| **音频通道** | 最多2通道(立体声) | **最多31通道** (真环绕/空间音频) |
| **广播能力** | ❌ 不支持 | ✅ **Auracast** 一对多广播 |
| **同传信道** | SCO/eSCO (HFP语音) | CIS (LE Audio语音) |
| **连接架构** | 点对点 | 点对点 + 点对多(广播) |
| **设备角色** | Source/Sink | Unicast Server(耳机)/Client(手机) + Broadcast Source/Sink |
| **上层协议** | AVDTP/AVCTP | **BAP** (Basic Audio Profile)直接 |

### 1.2 LE Audio 协议栈完整架构

```
┌──────────────────────────────────────────────────────────┐
│  Application Framework                                    │
│  BluetoothLeAudio.java (Framework API)                    │
│  LeAudioService.java / LeAudioStateMachine.java           │
├──────────────────────────────────────────────────────────┤
│  BTIF Layer  (btif_le_audio.cc / .h)                     │
│  btif_le_audio_get_interface()                            │
├──────────────────────────────────────────────────────────┤
│  BTA Layer   (bta_le_audio_api.h + client.cc)             │
│  ┌──────────────────────────────────────────────────┐    │
│  │ LeAudioClient (Unicast Client)                    │    │
│  │ LeAudioBroadcaster (Auracast Source)              │    │
│  │ LeAudioDevice / LeAudioDeviceGroup                │    │
│  │ LeAudioGroupStateMachine                          │    │
│  │ CodecManager                                      │    │
│  ├──────────────────────────────────────────────────┤    │
│  │ 支持服务:                                          │    │
│  │  CSIS (Coordinated Set)   - bta/csis/             │    │
│  │  HAS  (Hearing Access)    - bta/has/              │    │
│  │  VCS  (Volume Control)    - bta/vc/               │    │
│  │  GMAP (Gaming Audio)      - bta/gmap/             │    │
│  │  TMAS (Telephony & Media) - bta/le_audio/         │    │
│  └──────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────┤
│  ISO Manager  (btm_iso_api.h / btm_iso_impl.h)          │
│  ┌──────────────────────────────────────────────────┐    │
│  │ CIG (Connected Isochronous Group)                 │    │
│  │  ├── CIS #1 (左声道)                               │    │
│  │  └── CIS #2 (右声道)                               │    │
│  │ BIG (Broadcast Isochronous Group)                 │    │
│  │  ├── BIS #1 (立体声左)                             │    │
│  │  └── BIS #2 (立体声右)                             │    │
│  └──────────────────────────────────────────────────┘    │
├──────────────────────────────────────────────────────────┤
│  GD HCI  (le_iso_interface.h)                             │
│  LE ISO HCI Commands + Events                              │
├──────────────────────────────────────────────────────────┤
│  Bluetooth LE Controller + LC3 Codec                     │
└──────────────────────────────────────────────────────────┘
```

**核心源码文件**：

| 文件 | 路径 |
|------|------|
| bta_le_audio_api.h (BTA API) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/include/bta_le_audio_api.h) |
| le_audio_types.h (类型定义) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/le_audio_types.h) |
| client.cc (Client实现) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/client.cc) |
| state_machine.h (状态机) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/state_machine.h) |
| codec_manager.h (编解码器) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/codec_manager.h) |
| devices.h (设备模型) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/devices.h) |
| btm_iso_api.h (ISO管理) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/btm_iso_api.h) |
| btm_iso_api_types.h (ISO类型) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/btm_iso_api_types.h) |
| bt_le_audio.h (HAL接口) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_le_audio.h) |
| broadcaster.cc (广播源) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/broadcaster/broadcaster.cc) |

---

## 二、LC3 编解码器

### 2.1 LC3概述

LC3 (Low Complexity Communication Codec) 是LE Audio的**强制编解码器**，替代经典蓝牙的SBC。

**LC3关键特性**：
- 超低延迟：7.5ms / 10ms 帧时长
- 高音质：相同码率下显著优于SBC
- 低复杂度：设计用于DSP/硬件加速
- 宽采样率：8kHz ~ 48kHz (可扩展至384kHz)

### 2.2 LC3 配置参数 (LTV编码)

[le_audio_types.h:L135-L158](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/le_audio_types.h#L135-L158) 定义了LC3的所有配置参数，采用**LTV (Length-Type-Value)** 编码格式：

| LTV Type | 名称 | 说明 | 可选值 |
|----------|------|------|--------|
| `0x01` | **SamplingFreq** | 采样率 | 8000/11025/16000/22050/24000/32000/44100/48000/.../384000 Hz |
| `0x02` | **FrameDuration** | 帧时长 | 7.5ms / 10ms |
| `0x03` | **AudioChannelAllocation** | 音频通道位置 | 28个位置位图(FrontLeft/FrontRight/...) |
| `0x04` | **OctetsPerCodecFrame** | 每帧字节数 | 26-155 (取决于采样率+帧长) |
| `0x05` | **CodecFrameBlocksPerSdu** | 每SDU帧块数 | 1-16 (高采样率时多个LC3帧打包) |

**扩展编解码器**：系统还支持`OPUS`和`OPUS_HI_RES` (通过Feature Flag `leaudio_add_opus_hi_res_codec_type` 控制)。

### 2.3 音频通道位置体系

[le_audio_types.h:L161-L200](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/le_audio_types.h#L161-L200) 定义了28个音频位置，支持**真空间音频**：

```
0x00000001 FrontLeft      0x00000002 FrontRight     0x00000004 FrontCenter
0x00000008 LFE1           0x00000010 BackLeft       0x00000020 BackRight
0x00000040 FrontLeftCenter  0x00000080 FrontRightCenter 0x00000100 BackCenter
0x00000200 LFE2           0x00000400 SideLeft       0x00000800 SideRight
0x00001000 TopFrontLeft   0x00002000 TopFrontRight  0x00004000 TopFrontCenter
0x00008000 TopCenter      0x00010000 TopBackLeft    0x00020000 TopBackRight
0x00040000 TopSideLeft    0x00080000 TopSideRight   0x00100000 TopBackCenter
... (共28个通道)
```

**车载场景意义**：支持5.1/7.1乃至全景声配置。28通道远超经典A2DP的2通道限制。

---

## 三、等时通道 (Isochronous Channel) — 核心传输机制

### 3.1 CIS (Connected Isochronous Stream) — 单播音频

CIS是BLE 5.2引入的**面向连接**的等时通道，用于点对点音频传输。

```
CIG (Connected Isochronous Group)
├── CIS #1: ACL Handle X + CIS Handle A (左耳机, Sink方向)
│   └── iso_data_path (Input方向: 麦克风)
│   └── iso_data_path (Output方向: 扬声器)
├── CIS #2: ACL Handle Y + CIS Handle B (右耳机, Sink方向)
│   └── iso_data_path (Output方向: 扬声器)
└── ...

CIG参数 [cig_create_params]:
  - sdu_itv_mtos:     SDU间隔(手机→耳机), μs
  - sdu_itv_stom:     SDU间隔(耳机→手机), μs
  - sca:             时钟精度 (0-20ppm ~ 251-500ppm)
  - packing:         顺序/交错
  - framing:         非帧/帧模式
  - max_trans_lat_*:  最大传输延迟
  - cis_cfgs[]:      每个CIS的配置数组
```

**CIS建立完成的HCI事件** [cis_establish_cmpl_evt](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/btm_iso_api_types.h#L109-L127)：

```cpp
struct cis_establish_cmpl_evt {
  uint8_t  status;          // 0=成功
  uint8_t  cig_id;          // CIG ID
  uint16_t cis_conn_hdl;    // CIS连接句柄
  uint32_t cig_sync_delay;  // CIG同步延迟 (μs)
  uint32_t cis_sync_delay;  // CIS同步延迟 (μs)
  uint32_t trans_lat_mtos;  // 传输延迟(手机→耳机)
  uint32_t trans_lat_stom;  // 传输延迟(耳机→手机)
  uint8_t  phy_mtos;        // PHY(1M/2M/Coded)
  uint8_t  phy_stom;
  uint16_t max_pdu_mtos;    // 最大PDU大小
  uint16_t max_pdu_stom;
  uint16_t iso_itv;         // ISO间隔 (μs)
};
```

**编码格式标识** [btm_iso_api_types.h:L28-L29](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/btm_iso_api_types.h#L28-L29)：

```cpp
constexpr uint8_t kIsoCodingFormatTransparent = 0x03;
constexpr uint8_t kIsoCodingFormatLc3 = 0x06;        // LC3编码
constexpr uint8_t kIsoCodingFormatVendorSpecific = 0xFF; // 厂商自定义
```

### 3.2 BIS (Broadcast Isochronous Stream) — Auracast广播音频

BIS是BLE Audio的**广播**音频通道，支持**无限数量**的接收设备同时收听（如公共广播、电视音频共享）。

```
BIG (Broadcast Isochronous Group)
├── BIS #1 (立体声左声道)
├── BIS #2 (立体声右声道)
├── BIS #3 (多语言轨道1)
└── ...

BIG参数 [big_create_params]:
  - adv_handle:        广播句柄
  - num_bis:          BIS数量 (1-31)
  - sdu_itv:          SDU间隔 (μs)
  - max_sdu_size:     最大SDU大小
  - max_transport_latency: 最大传输延迟
  - rtn:              重传次数
  - phy:              PHY (1M/2M/Coded)
  - packing:          顺序/交错
  - framing:          非帧/帧模式
  - enc:              加密 (0=无, 1=BIG_ENC)
  - enc_code[16]:     Broadcast Code (16字节密钥)
```

**Auracast广播架构**：

```
  广播源 (Broadcast Source - 手机/车机)
     │  EXT_ADV (周期性广播 + BIGInfo)
     │  ┌────────────────────────────┐
     ├──│ BIG (Broadcast Group)      │
     │  │  ├─ BIS #1 (立体声左)      │
     │  │  └─ BIS #2 (立体声右)      │
     │  └────────────────────────────┘
     │
     ├────────────────────→  接收者A (耳机1)
     ├────────────────────→  接收者B (耳机2)
     ├────────────────────→  接收者C (助听器)
     └────────────────────→  ... (无限数量!)
```

**广播元数据结构** [bta_le_audio_api.h]：

```cpp
struct BroadcastMetadata {
  std::vector<uint8_t> broadcast_id;         // 广播唯一ID
  std::string broadcast_name;                // 广播名称 (如"车机音乐")
  LeAudioCodecConfig codec_config;           // 编解码器配置
  LeAudioBroadcastSubgroup[] subgroups;      // 子组(每语言/声道一个)
};

struct BasicAudioAnnouncementData {
  LeAudioCodecConfig[] codec_configs;        // 支持编解码器
  AudioContextType[] available_contexts;      // 音频场景(游戏/电话/媒体)
  uint8_t broadcast_id[3];                   // 广播ID
};
```

---

## 四、BAP (Basic Audio Profile) 核心机制

### 4.1 GATT服务体系

LE Audio通过**GATT服务**来发现设备能力、建立音频流、控制音量等。

**BAP核心GATT服务** [le_audio_types.h:L68-L112](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/le_audio_types.h#L68-L112)：

| 服务 | UUID | 说明 |
|------|------|------|
| **Published Audio Capability (PAC)** | `0x1850` | 发布设备支持的音频能力 |
| **Audio Stream Control (ASCS)** | `0x184E` | 控制音频流建立/配置/开始/停止 |
| **Common Audio Service (CAS)** | `0x1853` | 公共音频服务（用于识别角色+包装CSIS） |
| **Telephony & Media Audio (TMAS)** | `0x1855` | 电话和媒体音频角色 |
| **Gaming Audio (GMAS)** | `0x1858` | 游戏音频角色 |

**PAC特征**:

| 特征 | UUID | 说明 |
|------|------|------|
| Sink PAC | `0x2BC9` | Sink端(耳机)发布的接收能力 |
| Source PAC | `0x2BCB` | Source端(麦克风)发布的发送能力 |
| Sink Audio Location | `0x2BCA` | 音频输出位置(左耳/右耳) |
| Source Audio Location | `0x2BCC` | 音频输入位置 |

**ASCS特征**:

| 特征 | UUID | 说明 |
|------|------|------|
| Sink ASE | `0x2BC4` | Sink通道端点 (Notify) |
| Source ASE | `0x2BC5` | Source通道端点 (Notify) |
| ASE Control Point | `0x2BC6` | 控制点 (Write Command→Codec Config/QoS/Enable/Disable/Release) |

**音频上下文特征**:

| 特征 | UUID | 说明 |
|------|------|------|
| Available Contexts | `0x2BCD` | 当前可用的音频上下文 (Read+Notify) |
| Supported Contexts | `0x2BCE` | 支持的音频上下文 (Read) |

### 4.2 ASE (Audio Stream Endpoint) — 音频流端点

ASE是BAP中控制单个音频通道的**状态机驱动单元**。

**Audio Contexts (音频场景)**：

| 场景 | 位 | 含义 |
|------|----|------|
| Unspecified | 0x0001 | 未指定 |
| **Media** | 0x0002 | **媒体播放 (A2DP等价)** |
| **Conversational** | 0x0004 | **通话 (HFP等价)** |
| Game | 0x0008 | 游戏音频 |
| Ringtone | 0x0010 | 铃声 |
| Instructional | 0x0020 | 教学/导航 |
| Live | 0x0040 | 现场音频 |
| Sound Effects | 0x0080 | 音效 |
| Notification | 0x0100 | 通知音 |
| Alarm | 0x0200 | 闹钟 |
| ...

**车载关键场景**：`Media` (A2DP替代) + `Conversational` (HFP替代) + `Alarm` + `Notification`

### 4.3 ASE状态转换流程

```
ASE建立音频流的典型状态转换：

[IDLE]
  │
  ├── Client写入ASE ControlPoint: "Codec Config"
  │   → ASE状态变为 [CODEC_CONFIGURED]
  │
  ├── Client写入ASE ControlPoint: "QoS Config"
  │   → ASE状态变为 [QOS_CONFIGURED]
  │
  ├── Client调用Enable (CIG创建 + CIS建立)
  │   → ASE状态变为 [ENABLING] → [STREAMING]
  │
  ├── 音频数据传输中...
  │   (数据通过CIS等时通道传输)
  │
  ├── Client调用Disable
  │   → ASE状态变为 [DISABLING] → [QOS_CONFIGURED]
  │
  └── Client写入"Release"
      → ASE状态变为 [IDLE]
```

**LeAudioGroupStateMachine** 接口定义了上述流程的核心操作：
- [state_machine.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/state_machine.h#L50-L65)：
  - `AttachToStream()` → ASE关联设备到流
  - `ConfigureStream()` → Codec + QoS配置
  - `StartStream()` → CIG创建 + CIS建立
  - `SuspendStream()` / `StopStream()` → 暂停/停止
  - `EnableStreamingDirection()` / `DisableStreamingDirection()` → 方向控制

### 4.4 完整单播连接流程

```
手机 (LE Audio Client/Initiator)        耳机 (LE Audio Server/Acceptor)
──────────────────────────────         ──────────────────────────────
1. BLE GATT连接 (通过已有配对)
    │
2. 发现PAC服务 (0x1850)
    │  ── GATT Read: SinkPAC(0x2BC9)/SourcePAC(0x2BCB) ──→
    │  ←── 返回支持的编解码器配置(采样率/帧长/通道位置) ──
    │
3. 选择最佳编解码器配置
    │  CodecManager.GetCodecConfig() 匹配双方能力
    │
4. ASE配置 (ASCS, 0x184E)
    │  ── GATT Write: ASE CP "Codec Config" ──→
    │  ←── GATT Notify: ASE State→CODEC_CONFIGURED ──
    │
    │  ── GATT Write: ASE CP "QoS Config" ──→
    │  ←── GATT Notify: ASE State→QOS_CONFIGURED ──
    │
5. CIG创建 (IsoManager::CreateCig)
    │  ── HCI LE Set CIG Parameters ──→
    │  ←── HCI LE Set CIG Complete ──
    │
6. CIS建立 (IsoManager::EstablishCis)
    │  ── HCI LE Create CIS ──→
    │  ←── HCI LE CIS Established ──
    │
7. ISO数据路径设置
    │  ── HCI Setup ISO Data Path (Output) ──→
    │
8. Enable ASE
    │  ── GATT Write: ASE CP "Enable" ──→
    │  ←── GATT Notify: ASE State→STREAMING ──
    │
9. ★ 音频流传输中 ★
    │  LC3编码数据 → CIS → 耳机DAC
    │           ← 麦克风ADC ← CIS

10. 停止流程
    │  ── GATT Write: ASE CP "Disable" ──→
    │  ── HCI Disconnect CIS ──→
    │  ── HCI Remove CIG ──→
```

---

## 五、Auracast 广播音频 — 一对多音频共享

### 5.1 Auracast 概念

**Auracast**是LE Audio的广播音频能力，允许一个发送源向无限个接收者广播音频。

**与经典蓝牙广播的关键区别**：
- 经典蓝牙：无广播音频能力，必须建立ACL连接
- Auracast：无需配对、无需连接，BIS加密保护

### 5.2 广播源架构

`LeAudioBroadcaster` 类 ([bta_le_audio_broadcaster_api.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/include/bta_le_audio_broadcaster_api.h))：

```cpp
class LeAudioBroadcaster {
  // 创建广播
  virtual void CreateAudioBroadcast(bool is_public, std::string broadcast_name,
                                    LeAudioCodecConfig codec_config, ...) = 0;
  // 开始广播
  virtual void StartAudioBroadcast(uint32_t broadcast_id) = 0;
  // 停止/更新/销毁
  virtual void StopAudioBroadcast(uint32_t broadcast_id) = 0;
  virtual void UpdateMetadata(uint32_t, std::string name, ...) = 0;
  virtual void DestroyAudioBroadcast(uint32_t broadcast_id) = 0;

  // 获取广播元数据（供扫描者发现）
  virtual BroadcastMetadata GetBroadcastMetadata(uint32_t broadcast_id) = 0;
};
```

**广播源状态机** ([broadcaster/state_machine.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/broadcaster/state_machine.h))：

```
BroadcastState枚举:
  STOPPED → CONFIGURING → CONFIGURED → ENABLING/DISABLING → STREAMING
                                                              ↓
                                                         STOPPING → STOPPED
```

### 5.3 车载Auracast应用场景

| 场景 | 车机角色 | 说明 |
|------|---------|------|
| **车内多屏共享** | Broadcast Source | 前排导航语音/后排独立音频 |
| **车外公共广播** | Broadcast Source | 露营模式对外广播音乐 |
| **多乘客收听** | Broadcast Source | 多个乘客耳机同步收听同一音源 |
| **接收外部广播** | Broadcast Sink | 车站/机场公告接收 |

---

## 六、配套服务生态

### 6.1 TMAS (Telephony & Media Audio Service)

**UUID**: `0x1855` (TMAS), `0x2B51` (TMAP Role)

**TMAP角色定义**：
- **CG** (Call Gateway): 电话网关 (车机侧)
- **CT** (Call Terminal): 电话终端 (耳机侧)
- **UGT** (Unicast Game Terminal): 游戏终端
- **UMS** (Unicast Media Sender): 媒体发送者
- **UMR** (Unicast Media Receiver): 媒体接收者
- **BMS** (Broadcast Media Sender): 广播发送者
- **BMR** (Broadcast Media Receiver): 广播接收者

### 6.2 CSIS (Coordinated Set Identification Service)

[CSIS](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/csis/csis_types.h) 管理**协调集** (coordinated set)— 一套物理上分离但逻辑上同一组的设备（如一对TWS耳机）。

```cpp
// CSIS UUID体系
CSIS Service:   0x1846
SIRK:           0x2B84  (Set Identity Resolving Key - 群组密钥)
Size:           0x2B85  (群组大小: 左+右=2)
Lock:           0x2B86  (锁定状态: 0=解锁, 1=锁定)
Rank:           0x2B87  (成员排序: 1=左, 2=右)
```

**CSIS工作流程**：
1. 发现CSIS实例 → 读取SIRK → 识别同组设备
2. 读取Rank → 确定左右声道分配
3. Lock操作 → 一次Lock可将所有组成员同时连接

**车载意义**：TWS耳机左+右需要CSIS来确保车机将其视为一个逻辑设备，统一codec配置和音量。

### 6.3 HAS (Hearing Access Service)

[HAS](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/has/has_types.h) 为助听器提供预设管理：

```cpp
// HAS UUID体系
HAS Service:           0x1854
ActivePresetIndex:     0x2BDC  (当前活跃预设)
PresetControlPoint:    0x2BDB  (预设控制点)
HearingAidFeatures:    0x2BDA  (助听器特性)
```

**HAS Client** (`has_client.cc`): 读取Preset列表 → 切换预设→ 应用于不同听力场景(车内/室内/室外)。

### 6.4 VCS (Volume Control Service)

[VCS](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/vc/types.h) 提供标准化的音量控制：

```cpp
// VCS UUID体系
VCS Service:   0x1844
VCS State:     0x2B7D  (Volume + Mute + Step)
VCP:           0x2B7E  (Control Point)
VolumeFlags:   0x2B7F
VOCS Service:  0x1845  (Volume Offset Control - 独立通道偏移)
VO State:      0x2B80  (每通道偏移量)
AICS Service:  0x1843  (Audio Input Control)
```

**与AVRCP Absolute Volume的关系**：
- AVRCP AbsVol: 经典蓝牙方案，通过AVCTP/Browsing通道
- VCS: LE Audio原生方案，通过GATT直接读写

**车载常见场景**：单独控制左耳/右耳/中置声道的音量偏移。

### 6.5 GMAP (Gaming Audio Profile)

[GMAP](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/gmap/gmap_server.cc) 针对低延迟游戏音频优化：

```cpp
// GMAP UUID
GMAS Service:        0x1858
Role Characteristic: 0x2C00  (角色: UGG/UGT)
// UGG = Unicast Game Gateway (游戏网关=手机/车机)
// UGT = Unicast Game Terminal (游戏终端=耳机)
```

**启用条件** [gmap_client.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/gmap/gmap_client.cc)：

```cpp
bool IsGmapClientEnabled() {
  return osi_property_get_bool("bluetooth.profile.gmap.enabled", false) &&
    (controller_get_interface()->supports_offloader() || is_software_data_path_configured());
}
```

---

## 七、车载 LE Audio 场景

### 7.1 LE Audio vs A2DP + HFP 对比

| 场景 | 经典方案 | LE Audio方案 | LE Audio优势 |
|------|---------|-------------|-------------|
| 音乐播放 | A2DP (SBC) | BAP Media Context (LC3) | 音质更好、延迟更低、功耗减半 |
| 语音通话 | HFP (mSBC/CVSD) | BAP Conversational Context (LC3) | 超宽带语音、双向同时高质量 |
| 多设备音频 | 需要多个A2DP连接 | CIG多CIS | 一个CIG内多设备同步，延迟可控 |
| 后排独立音频 | 无法实现(单A2DP) | BIG多BIS广播 | 前排导航+后排电影独立分流 |
| TWS耳机 | 左右各自配A2DP | CSIS+CIS双通道 | 统一管理，立体声同步更好 |
| 数字钥匙+音 | 分离的BLE+A2DP | 同一BLE连接+CIS | 减少连接数，简化天线共存 |

### 7.2 双模共存策略

```
车机同时支持 LE Audio + Classic Audio:

优先级策略:
  1. LE Audio设备优先使用LE Audio链路 (Media+Conversational)
  2. 旧设备回退到A2DP+HFP
  3. 通话切换: LE Audio CIS ⇄ HFP SCO
     (通过 LeAudioService.mHfpHandoverDevice 管理)

双模音频切换信号:
  ACTION_LE_AUDIO_CONNECTION_STATE_CHANGED (Intent广播)
  ACTION_LE_AUDIO_ACTIVE_DEVICE_CHANGED
  ACTION_BROADCAST_TO_UNICAST_FALLBACK_GROUP_CHANGED
```

### 7.3 车载LE Audio配置建议

```bash
# 属性控制
bluetooth.profile.leaudio.enabled=true         # 启用LE Audio
bluetooth.profile.gmap.enabled=true            # 启用GMAP (游戏低延迟)
bluetooth.profile.vcp.enabled=true             # 启用VCP (音量控制)
bluetooth.profile.csis.enabled=true            # 启用CSIS (协调集)

# 编解码器偏好
# 通过 LeAudioClient.SetCodecConfigPreference() API设置:
# - 首选LC3 48kHz/10ms (高音质)
# - 车载导航语音可降为16kHz/7.5ms (省功耗)
```

---

## 八、Feature Flags 关键配置

[leaudio.aconfig](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/leaudio.aconfig) 定义了31个LE Audio特性开关：

| Flag | 功能 | 类型 |
|------|------|------|
| `leaudio_broadcast_monitor_source_sync_status` | 广播源同步状态API | 导出API |
| `leaudio_broadcast_volume_control_for_connected_devices` | 已连接广播设备音量控制 | 导出API |
| `leaudio_set_codec_config_preference` | 编解码器偏好设置API | 功能 |
| `leaudio_config_profile_enabling` | Profile启用配置方式 | 功能 |
| `leaudio_connection_subrating` | 连接子速率优化 | 功能 |
| `leaudio_dynamic_direction_opening` | 按需开启音频方向 | Bugfix |
| `leaudio_add_opus_hi_res_codec_type` | OPUS Hi-Res编解码器 | Bugfix |
| `dsa_use_codec_extensibility` | DSA参数使用codec扩展性API | Bugfix |
| `leaudio_bis_sync_control` | BIS同步状态控制 | Bugfix |
| `leaudio_use_context_type_manager` | 新Context管理器 | Bugfix |
| `leaudio_improve_switching_le_audio_devices` | 设备切换优化 | Bugfix |
| `leaudio_dynamic_data_path_change` | 动态数据路径切换 | 功能 |
| `leaudio_broadcast_allow_monitoring_on_resume` | 休眠恢复后广播监听 | Bugfix |

---

## 九、LE Audio 全部源码文件索引

### BTA 核心层 (34个文件)

| 文件 | 路径 |
|------|------|
| client.cc (Client主实现) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/client.cc) |
| le_audio_types.h (类型定义) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/le_audio_types.h) |
| state_machine.h (状态机接口) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/state_machine.h) |
| codec_manager.h (编解码管理) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/codec_manager.h) |
| devices.h (设备模型) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/devices.h) |
| broadcaster/broadcaster.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/le_audio/broadcaster/broadcaster.cc) |

### BTIF/Framework 层

| 文件 | 路径 |
|------|------|
| btif_le_audio.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/include/btif_le_audio.h) |
| btif_le_audio.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_le_audio.cc) |
| bt_le_audio.h (HAL) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_le_audio.h) |
| BluetoothLeAudio.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothLeAudio.java) |
| LeAudioService.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/le_audio/LeAudioService.java) |
| LeAudioNativeInterface.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/le_audio/LeAudioNativeInterface.java) |

### ISO 传输层

| 文件 | 路径 |
|------|------|
| btm_iso_api.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/btm_iso_api.h) |
| btm_iso_api_types.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/btm_iso_api_types.h) |
| btm_iso_impl.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/btm/btm_iso_impl.h) |
| le_iso_interface.h (GD HCI) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hci/le_iso_interface.h) |

### 配套服务

| 文件 | 路径 |
|------|------|
| csis_types.h (CSIS) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/csis/csis_types.h) |
| has_client.cc (HAS) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/has/has_client.cc) |
| types.h (VCS) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/vc/types.h) |
| gmap_server.cc (GMAP) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/gmap/gmap_server.cc) |

### Feature Flags

| 文件 | 路径 |
|------|------|
| leaudio.aconfig | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/flags/leaudio.aconfig) |