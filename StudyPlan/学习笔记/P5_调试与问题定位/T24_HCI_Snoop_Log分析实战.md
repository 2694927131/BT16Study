# T24 HCI Snoop Log分析实战

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：btsnoop文件格式(signature 8B+version+datalink) | Wireshark 11个蓝牙过滤器 | A2DP AVDT五步信令分析 | HFP RFCOMM+AT+SCO完整序列 | BLE 7步连接序列 | 4大常见协议问题
> 待回顾问题：无

---

## 1. Snoop Log基础

### 1.1 文件格式

Snoop Log使用标准的 **btsnoop** 格式，文件头 + 包记录序列。

**文件头结构**（[snoop_logger_common.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/snoop_logger_common.h)）：

```
Offset  Size  Field
0       8     Identification Pattern: {'b','t','s','n','o','o','p',0x00}
8       4     Version Number: 1
12      4     Datalink Type: 1002 (HCI UART H4)
```

**包记录结构**（[snoop_logger_file.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/snoop_logger_file.h)）：

```
每个数据包：
Offset  Size  Field
0       4     Original Length（原始包长度）
4       4     Included Length（实际包含的数据长度）
8       4     Packet Flags（方向标志）
12      4     Cumulative Drops（累计丢弃数）
16      8     Timestamp Microseconds（微秒时间戳）
24      N     Packet Data
```

**包类型**（[snoop_logger.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/snoop_logger.h)）：

| 类型值 | 名称 | HCI类型 | 说明 |
|--------|------|---------|------|
| 1 | CMD | HCI Command | Host→Controller命令 |
| 2 | ACL | ACL Data | 异步无连接数据 |
| 3 | SCO | SCO Data | 同步面向连接数据 |
| 4 | EVT | HCI Event | Controller→Host事件 |
| 5 | ISO | ISO Data | LE Audio等时数据 |

**方向标志**：

| Direction | 含义 |
|-----------|------|
| OUTGOING (0) | Host → Controller（发送） |
| INCOMING (1) | Controller → Host（接收） |

### 1.2 开启/关闭Snoop Log

```bash
# 方法一：系统属性（推荐）
adb shell setprop persist.bluetooth.btsnooplogmode full
adb shell setprop persist.bluetooth.btsnooplogmode filtered
adb shell setprop persist.bluetooth.btsnooplogmode disabled

# 方法二：开发者选项
设置 → 开发者选项 → 启用蓝牙HCI信息收集日志

# 方法三：Java API
# 通过BluetoothManagerService.setBtHciSnoopLogMode()调用
```

### 1.3 存储位置

```bash
# 主Snoop文件
/data/misc/bluetooth/logs/btsnoop_hci.log

# Snooz（压缩格式，内存环形缓冲区数据dump）
/data/misc/bluetooth/logs/btsnooz_hci.log

# 拉取
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log ./
```

### 1.4 四种Snoop模式详解

| 模式 | System Property | 内容 | 文件大小 | 适用范围 |
|------|-----------------|------|----------|----------|
| `full` | `persist.bluetooth.btsnooplogmode=full` | 全部HCI包（含ACL数据payload） | GB级 | **音频数据分析** |
| `filtered` | `persist.bluetooth.btsnooplogmode=filtered` | HCI包+选择性ACL数据 | 中等（MB级） | **日常调试推荐** |
| `disabled` | `persist.bluetooth.btsnooplogmode=disabled` | 不记录 | 0 | 生产环境 |
| `kernel` | `persist.bluetooth.btsnooplogmode=kernel` | 由内核驱动记录 | 取决于内核 | 内核级调试 |

**Filtered模式过滤机制**（[snoop_logger.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/snoop_logger.h)）：

```cpp
// filtered模式 = 只保留acceptlist中的L2CAP和RFCOMM通道
class FilterTracker {
    std::unordered_set<uint16_t> l2c_local_cid = {1};     // 1 = L2CAP signaling
    std::unordered_set<uint16_t> l2c_remote_cid = {1};
    uint16_t rfcomm_local_cid = 0;
    uint16_t rfcomm_remote_cid = 0;
    std::unordered_set<uint16_t> rfcomm_channels = {0};   // 0 = RFCOMM control
};
```

**Filtered模式子过滤选项**：

| Property | 功能 | 默认值 |
|----------|------|--------|
| `persist.bluetooth.snooplogfilter.headers.enabled` | 截断ACL到仅包头 | false |
| `persist.bluetooth.snooplogfilter.profiles.a2dp.enabled` | 过滤A2DP媒体数据包 | false |
| `persist.bluetooth.snooplogfilter.profiles.pbap` | PBAP/HFP过滤模式 | disabled |
| `persist.bluetooth.snooplogfilter.profiles.map` | MAP过滤模式 | disabled |
| `persist.bluetooth.snooplogfilter.profiles.rfcomm.enabled` | 截断RFCOMM UIH payload | false |

---

## 2. Wireshark使用

### 2.1 蓝牙显示过滤器完整列表

```
# === 协议层过滤器 ===

btavdtp              -- AVDT信令（A2DP连接建立/配置/启动）
btavctp              -- AVCTP信令（AVRCP控制命令）
btrfcomm             -- RFCOMM帧（HFP AT命令/SPP数据）
btsdp                -- SDP服务发现（查询/响应/Service Record）
btl2cap              -- L2CAP层（连接/配置/数据）
btsmp                -- SMP配对（LE Secure Connections）
btatt                -- ATT/GATT协议（BLE读写操作）
btle                 -- BLE链路层（ADV/SCAN/CONNECT）

# === HCI层过滤器 ===

bthci_acl            -- ACL数据包
bthci_cmd            -- HCI命令包
bthci_evt            -- HCI事件包
bthci_sco            -- SCO/eSCO数据包
hci_h4               -- H4传输层

# === 组合过滤器 ===

# 过滤特定设备
bt.addr == XX:XX:XX:XX:XX:XX

# A2DP完整连接分析
btavdtp || (btl2cap && btl2cap.cid == 0x0001)

# HFP完整连接分析
btrfcomm || btsdp || (btl2cap && btl2cap.cid == 0x0001)

# BLE连接分析
btle || btatt || btsmp

# 配对过程
btsmp || (bthci_evt && hci_evt.code == 0x06)  # 0x06 = PIN Code Request

# 特定设备 + A2DP
(btavdtp || btl2cap) && bt.addr == XX:XX:XX:XX:XX:XX
```

### 2.2 "跟踪流"的蓝牙等价操作

在TCP中有"Follow TCP Stream"，在蓝牙中等价操作是"**过滤同一ACL连接的CID**"：

```
# 找到目标设备的ACL连接句柄(connection_handle)
# 在Wireshark中右键ACL包 → "Apply as Filter" → "...and Selected"

# 或手动输入：
bthci_acl.connection_handle == 0x0001
```

### 2.3 Wireshark分析技巧

**技巧1：按时间排序 + 显示列配置**
```
启用列：Time、Source、Destination、Protocol、Info
蓝牙列：bt.addr、btl2cap.cid、btl2cap.psm
```

**技巧2：着色规则**
```
btavdtp → 蓝色（A2DP信令）
btrfcomm → 绿色（HFP命令）
btsdp → 黄色（服务发现）
btatt → 紫色（GATT操作）
```

**技巧3：统计**
```
Statistics → Protocol Hierarchy → 查看蓝牙协议占比
Statistics → IO Graph → 绘制ACL/SCO数据速率图
Telephony → Bluetooth → 设备时序图
```

---

## 3. A2DP连接过程分析

### 3.1 完整HCI消息序列

A2DP Source连接的标准协议序列（用Wireshark过滤器 `btavdtp || btl2cap`）：

```
阶段1: ACL连接建立
  HCI CMD: Create Connection (0x0405)
  HCI EVT: Connection Complete (status=0x00, handle=0x0001)
  
阶段2: L2CAP信令通道
  L2CAP CMD: Information Request (Extended Features)
  L2CAP CMD: Information Response
  L2CAP CMD: Connection Request (PSM=0x0019 → AVDT)
  L2CAP CMD: Connection Response (Result=0x0000 success)
  L2CAP CMD: Configuration Request (MTU)
  L2CAP CMD: Configuration Response

阶段3: SDP查询（可选，L2CAP PSM=0x0001）
  SDP: Service Search Request (UUID=0x110B → A2DP Sink)
  SDP: Service Search Response (handle list)
  SDP: Service Attribute Request (A2DP SDP record attributes)
  SDP: Service Attribute Response (Supported Features, SEP list)

阶段4: AVDT信令（5步信令）
  AVDT: DISCOVER (Discover SEPs)
    → 设备回复自己的SEP列表（类型+能力）
  AVDT: GET_CAPABILITIES (获取SEP能力)
    → 返回支持的编解码器capability（SBC/AAC/aptX/LDAC等）
  AVDT: SET_CONFIGURATION (设置编解码参数)
    → 选择匹配的编解码器及参数（采样率/比特率等）
  AVDT: OPEN (打开流通道)
    → L2CAP Connection Request (PSM=0x0019, 媒体通道)
  AVDT: START (开始播放)
    → 音频数据开始通过媒体通道传输

阶段5: 音频流传输
  ACL: AVDTP Media Packet (RTP header + encoded audio)
  
阶段6: 停止和断开
  AVDT: SUSPEND (暂停)
  AVDT: CLOSE (关闭流)
  AVDT: DISCONNECT (断开信令通道)
  HCI CMD: Disconnect (0x0406)
```

### 3.2 编解码器协商的参数解读

**GET_CAPABILITIES响应示例（SBC）**：
```
AVDT Service Capabilities:
  Media Transport
  Media Codec - SBC:
    Sampling Frequency: 48000/44100/32000/16000
    Channel Mode: JOINT_STEREO/STEREO/DUAL/MONO
    Block Length: 16/12/8/4
    Subbands: 8/4
    Allocation Method: LOUDNESS/SNR
    Bitpool Range: Min=2, Max=53
```

**SET_CONFIGURATION确定参数**：
```
AVDT Set Configuration:
  Media Codec - SBC:
    Sampling Frequency: 44100      ← 选定44.1kHz
    Channel Mode: JOINT_STEREO     ← 联合立体声
    Block Length: 16               ← 16块
    Subbands: 8                    ← 8子带
    Allocation: LOUDNESS           ← 响度分配
    Bitpool: Min=2, Max=53 → 最终用35
```

**关键排查点**：
- CAPABILITIES中是否有双方支持的codec → 若没有交集则连接失败
- SET_CONFIGURATION参数是否在CAPABILITIES允许范围内 → 超出范围会被拒绝
- Offload模式需确认双方DSP支持 → 查看Vendor Specific CAP

---

## 4. HFP连接过程分析

### 4.1 完整HCI消息序列

HFP AG(车机) 连接的协议序列（过滤器：`btrfcomm || btsdp || btl2cap`）：

```
阶段1: ACL + L2CAP
  HCI CMD: Create Connection
  HCI EVT: Connection Complete
  L2CAP: Connection Request (PSM=0x0003 → RFCOMM)
  L2CAP: Configuration Request/Response

阶段2: RFCOMM建链（GSM 07.10）
  RFCOMM: SABM (DLCI=0)    → 控制通道建立
  RFCOMM: UA (DLCI=0)      → 确认
  RFCOMM: PN Request (DLCI=XX)  → 协商新DLCI通道
  RFCOMM: PN Response
  RFCOMM: SABM (DLCI=XX)   → 数据通道建立
  RFCOMM: UA (DLCI=XX)     → 数据通道就绪

阶段3: SDP查询（可选，部分设备先SDP再RFCOMM）
  SDP: Service Search Request (UUID=0x111E/0x1131 HFP)
  SDP: Service Attribute Request (获取RFCOMM Channel Number)
  SDP: Service Attribute Response (channel=XX)

阶段4: AT命令SLC协商（在RFCOMM数据通道上）
  → HF → AG: AT+BRSF=<HF_features>         (HF功能)
  → AG → HF: +BRSF:<AG_features>            (AG功能)
  → AG → HF: +CIND:("call",(0,1)),...       (指示器列表)
  → AG → HF: +CIND:?                        (指示器状态查询)
  → HF → AG: AT+CIND?                       (读取指示器)
  → AG → HF: +CIND:0,0,1,0,0,0,0           (指示器当前值)
  → AG → HF: +CMER:3,0,0,1                  (设置事件报告)
  → HF → AG: AT+CMER=3,0,0,1
  → AG → HF: OK
  → HF → AG: AT+CHLD=?                      (查询呼叫保持能力)
  → AG → HF: +CHLD:(0,1,2,3)               (支持的功能列表)
  → AG → HF: OK
  → HF → AG: AT+BIND=<HF_indicators>        (HF指示器)
  → AG → HF: OK
  → HF → AG: AT+BIND?                        (查询AG指示器)
  → AG → HF: +BIND:<AG_indicators>
  → AG → HF: OK
  → HF → AG: AT+BAC=<codecs>                (支持的codec)
  → AG → HF: OK
  → HF → AG: AT+BCS=<selected_codec>        (选择codec)
  → AG → HF: OK
  → 至此SLC建立完毕

阶段5: SCO/eSCO建链（通话时）
  HCI CMD: Setup Synchronous Connection
    → 参数：Transmit Bandwidth/Receive Bandwidth/
            Max Latency/Voice Settings/Retransmission/Packet Type
  HCI EVT: Synchronous Connection Complete (status, handle)
  
阶段6: 通话和挂断
  RFCOMM: AT+CLCC → +CLCC: ...              (通话状态更新)
  RFCOMM: AT+CHUP → OK                       (挂断)
  HCI CMD: Disconnect (SCO handle)
```

### 4.2 AT命令交互解读

**关键AT命令速查**：

| 方向 | AT命令 | 含义 | HFP版本 |
|------|--------|------|---------|
| HF→AG | `AT+BRSF=...` | HF声明支持的功能 | 1.5+ |
| AG→HF | `+BRSF:...` | AG声明支持的功能 | 1.5+ |
| AG→HF | `+CIND:...` | 指示器定义（call/signal/battery等） | 1.5+ |
| AG→HF | `+CMER:...` | 指示器事件上报模式 | 1.5+ |
| HF→AG | `AT+CHLD=?` | 查询呼叫保持能力 | 1.5+ |
| HF→AG | `AT+BIND=...` | HF指示器状态通知 | 1.7+ |
| HF→AG | `AT+BAC=...` | 声明支持的Codec | 1.6+ WBS |
| AG→HF | `+BCS:...` | 选择Codec | 1.6+ WBS |
| AG→HF | `+BCC` | Codec确认 | 1.6+ WBS |
| AG→HF | `+CLIP:...` | 来电号码 | 1.5+ |
| HF→AG | `ATA` | 接听 | 1.5+ |
| HF→AG | `AT+CHUP` | 挂断 | 1.5+ |
| HF→AG | `ATD...` | 拨号 | 1.5+ |
| HF→AG | `AT+CLCC` | 查询通话列表 | 1.5+ |
| AG→HF | `+CLCC:...` | 通话列表响应 | 1.5+ |
| AG→HF | `+CIEV:...` | 指示器变更通知 | 1.5+ |

---

## 5. BLE连接过程分析

### 5.1 完整HCI消息序列

BLE GATT连接的协议序列（过滤器：`btle || btatt || btsmp`）：

```
阶段1: Advertising/Scanning
  HCI CMD: LE Set Scan Parameters
  HCI CMD: LE Set Scan Enable (enable=1)
  HCI EVT: LE Advertising Report (ADV_IND)
    → addr: XX:XX:XX:XX:XX:XX, RSSI: -45dBm
    → AD Data: Flags, Complete Local Name, Service UUIDs

阶段2: BLE连接建立
  HCI CMD: LE Create Connection
    → 参数：Scan Interval=60ms, Scan Window=30ms
            Conn Interval Min=30ms, Max=50ms
            Latency=0, Supervision Timeout=2000ms
  HCI EVT: LE Connection Complete
    → status=0x00, handle=0x0040
    → role=Master, interval=45ms, latency=0, timeout=2000ms

阶段3: 连接参数更新（如需）
  HCI CMD: LE Connection Update
    → Interval Min=15ms, Max=30ms (加快数据交互)

阶段4: ATT/GATT服务发现
  ATT: Read By Group Type Request
    → Start=0x0001, End=0xFFFF, UUID=0x2800 (Primary Service)
  ATT: Read By Group Type Response
    → Service 1: Handle 0x0001-0x0005, UUID=0x1800 (GAP)
    → Service 2: Handle 0x0006-0x0009, UUID=0x1801 (GATT)
    → Service 3: Handle 0x0010-0x0020, UUID=0xXXXX (自定义)
  
  ATT: Read By Type Request
    → Handle range: 0x0010-0x0020, UUID=0x2803 (Characteristic)
  ATT: Read By Type Response
    → Char 1: Handle 0x0011, Properties=0x12(Read|Notify), Value=0x0012
    → Char 2: Handle 0x0014, Properties=0x08(Write), Value=0x0015
    → ...

阶段5: 启用通知（写CCCD）
  ATT: Write Request
    → Handle=0x0013, Value=0x0100 (0x0001→Notifications enabled)
  ATT: Write Response

阶段6: BLE配对（如需）
  SMP: Security Request
  SMP: Pairing Request (IO Cap/ Bonding/ MITM/ SC/ Keypress)
  SMP: Pairing Response
  SMP: Pairing Confirm (LE SC)
  SMP: Pairing Random
  SMP: Encryption Information (LTK分发)
  SMP: Identity Information (IRK分发)
  SMP: Identity Address Information
```

### 5.2 SMP配对过程

```
LE Secure Connections (LE SC) 配对序列:
  SMP: Pairing Request (AuthReq=SC+MITM+Bonding, IOCap=NoInputNoOutput)
  SMP: Pairing Response (AuthReq=SC+MITM+Bonding, IOCap=DisplayYesNo)
  SMP: Public Key Exchange (X, Y coordinates)
  SMP: Pairing Confirm (Commitment value)
  SMP: Pairing Random (Random value)
  SMP: Pairing DHKey Check (Key verification)
  → LTK derived from ECDH + AES-CMAC
  SMP: Encryption Information (LTK)
  SMP: Identity Information (IRK)
  SMP: Identity Address Information
```

---

## 6. 常见协议问题分析

### 6.1 AVDT重传和错误

**现象**：同一AVDT命令多次出现

```
Wireshark过滤器: btavdtp
观察: 相同的Transaction Label + Packet Type在短时间内重复出现
```

**常见原因**：
- AVDT RT_TIMEOUT（响应超时），默认RT_TIMEOUT=3秒
- 射频干扰导致包丢失
- 对端处理慢，超过应答时间

**定位方法**：
1. 查看AVDT命令的时间间隔
2. 若间隔 > 3秒 且 Transaction Label 不同 → 正常
3. 若同一 Transaction Label 重复 → 重传，排查RF

### 6.2 L2CAP连接参数更新

**现象**：连接建立后出现Connection Parameter Update

```
Wireshark过滤器: btl2cap
观察: L2CAP CONNECTION_PARAMETER_UPDATE_REQUEST/RESPONSE
或: HCI CMD LE Connection Update
```

**常见参数**：
```
Interval Min → 要求更小 = 更快响应但更高功耗
Interval Max → 要求更大 = 更省电但延迟高
Latency → 0=不允许跳过连接事件
Supervision Timeout → 超时时间(ms)
```

**车载问题**：手机端可能拒绝车机要求的连接参数更新 → 导致BLE通信响应慢

### 6.3 加密建立过程

```
BR/EDR加密:
  HCI CMD: Link Key Request (Controller请求Link Key)
  HCI EVT: Link Key Request Reply (Host提供Link Key)
  HCI CMD: Set Connection Encryption (开始加密)
  HCI EVT: Encryption Change (status=0加密中, status=1加密完成)

LE加密:
  HCI CMD: LE Start Encryption
  HCI EVT: Encryption Change (LE)
```

**加密失败常见原因**：
- Link Key丢失或被清除(`pm clear`或存储损坏)
- 配对信息不完整
- 加密进行中被另一请求打断

### 6.4 LMP/LLC消息分析

LMP消息不出现在标准Snoop中（在HCI以下），但部分芯片可配置BQR VSE追踪：

```
LMP常见消息（通过BQR VSE获取）：
  LMP_host_connection_req          → 建立连接请求
  LMP_accepted                     → 接受连接
  LMP_features_req/res             → 特性交换
  LMP_version_req/res              → 版本交换
  LMP_name_req/res                 → 名称请求
  LMP_max_slot                     → 最大槽
  LMP_encryption_mode_req          → 加密模式协商
  LMP_setup_complete               → 链路建立完成
```

---

## 7. 车载实战：按问题类型的Snoop分析流程

### 7.1 A2DP无声音 - Snoop问题定位

```
步骤1: 过滤器 btavdtp
  → 检查是否有 AVDT DISCOVER → GET_CAPABILITIES → SET_CONFIGURATION 
    → OPEN → START 完整序列
  → 缺失：STOP在哪一步

步骤2: 过滤器 (btavdtp || btl2cap) && bt.addr==<phone>
  → 检查 L2CAP 连接是否成功建立
  → 检查 Configuration Response 的 Result 字段
  
步骤3: 过滤器 btavdtp.stream_endpoint_id
  → 追踪具体SEP的状态变化
  
结果解读:
  - START缺失 → 编解码协商可能失败，看SET_CONFIGURATION是否返回reject
  - OPEN缺失 → L2CAP拒绝连接，看L2CAP Connection Response的result code
  - 序列完整 → 问题可能在Audio HAL/DSP层（Offload模式下需看音频通路日志）
```

### 7.2 HFP通话异常 - Snoop问题定位

```
步骤1: 过滤器 btrfcomm
  → RFCOMM SABM/UA是否正确
  → AT+BRSF交换是否完成 → SLC是否建立

步骤2: 过滤器 bthci_sco
  → Setup Synchronous Connection命令参数
  → Synchronous Connection Complete的status
  
步骤3: 过滤器 btrfcomm 查AT命令
  → +CIEV: call=1, callsetup=1 → 来电
  → AT+CLCC → +CLCC: ... → 通话状态确认
  → AT+CHUP → OK → 挂断完成
```

### 7.3 配对失败 - Snoop问题定位

```
步骤1: 过滤器 btsmp (LE) 或 bthci_evt (BR/EDR)
  → LE: SMP Pairing Request/Response → 检查双方IO Cap是否兼容
  → BR/EDR: Link Key Request/Reply → PIN Code Request

步骤2: 过滤器 bthci_evt
  → Authentication Complete event (0x06) → status code
  → status=0x05 → 认证失败(Authentication Failure)
  → status=0x0B → 密钥丢失(Key Missing)
```

---

## 8. 快速参考卡片

### Snoop文件速查
```
文件位置: /data/misc/bluetooth/logs/btsnoop_hci.log
开启命令: adb shell setprop persist.bluetooth.btsnooplogmode full
拉取命令: adb pull /data/misc/bluetooth/logs/btsnoop_hci.log
实时分析: python btsnoop_live.py | wireshark -k -i -
```

### Wireshark过滤器速查
```
A2DP完整链路: btavdtp || btl2cap
HFP完整链路: btrfcomm || btsdp
BLE完整链路: btle || btatt || btsmp
配对过程:    btsmp || (bthci_evt.code == 0x06)
单设备跟踪:  bt.addr == XX:XX:XX:XX:XX:XX
ACL连接跟踪: bthci_acl.connection_handle == 0x0001
SCO链路跟踪: bthci_sco.connection_handle == 0x0002
```