# A.4 AVDTP / AVCTP / OBEX 帧参考

> **速通摘要**：本附录给出 **A2DP（AVDTP 信令）**、**AVRCP（AVCTP 信令）**、**PBAP/MAP（OBEX）**三个常用协议的帧格式与命令码速查。所有常量从本仓库 `system/stack/avdt/avdt_defs.h`、`system/stack/include/avct_api.h` 等头文件验证。

---

## 一、AVDTP（A2DP 信令）

### 1.1 信令包格式

```
Byte0:  ┌────────────────────┬──────┬────────┐
        │ Transaction Label  │ PKT  │ MSG    │
        │ (4 bits)           │ (2)  │ (2)    │
        └────────────────────┴──────┴────────┘
Byte1:  ┌────────────────────────────────────┐
        │ Signal Identifier                   │
        └────────────────────────────────────┘
Byte2+: Parameters (信令具体参数)

PKT = Packet Type:
  0=AVDT_PKT_TYPE_SINGLE  单包
  1=AVDT_PKT_TYPE_START   分片首包
  2=AVDT_PKT_TYPE_CONT    续包
  3=AVDT_PKT_TYPE_END     末包

MSG = Message Type:
  0=AVDT_MSG_TYPE_CMD     命令
  1=AVDT_MSG_TYPE_GRJ     通用拒绝
  2=AVDT_MSG_TYPE_RSP     回应
  3=AVDT_MSG_TYPE_REJ     拒绝
```

来源：`system/stack/avdt/avdt_defs.h:33-42`

### 1.2 AVDTP Signal ID（Signal Identifier）

| ID | 名称 | 用途 | avdt_defs.h:line |
|----|------|------|------------------|
| 1 | AVDT_SIG_DISCOVER | 发现 SEP（Stream End Point）| :45 |
| 2 | AVDT_SIG_GETCAP | 查询 SEP 能力 | :46 |
| 3 | AVDT_SIG_SETCONFIG | 配置 SEP（选 Codec、采样率）| :47 |
| 4 | AVDT_SIG_GETCONFIG | 查询配置 | :48 |
| 5 | AVDT_SIG_RECONFIG | 重新配置（切换 Codec）| :49 |
| 6 | AVDT_SIG_OPEN | 打开流（建立 L2CAP 媒体通道）| :50 |
| 7 | AVDT_SIG_START | 开始播放 | :51 |
| 8 | AVDT_SIG_CLOSE | 关闭流 | :52 |
| 9 | AVDT_SIG_SUSPEND | 暂停 | :53 |
| 10 | AVDT_SIG_ABORT | 异常终止 | :54 |
| 11 | AVDT_SIG_SECURITY | 安全控制 | :55 |
| 12 | AVDT_SIG_GET_ALLCAP | 查询所有能力（A2DP 1.3+）| :56 |
| 13 | AVDT_SIG_DELAY_RPT | 延迟上报（音视频同步）| :57 |

### 1.3 Service Capability Category

| Cat | 名称 | 用途 | avdt_defs.h:line |
|-----|------|------|------------------|
| 1 | AVDT_CAT_TRANS | Media Transport | :66 |
| 2 | AVDT_CAT_REPORT | RTCP-like 报告 | :67 |
| 3 | AVDT_CAT_RECOV | 恢复（很少用）| :68 |
| 4 | AVDT_CAT_PROTECT | 内容保护（DRM）| :69 |
| 5 | AVDT_CAT_HDRCMP | 头压缩 | :70 |
| 6 | AVDT_CAT_MUX | 复用 | :71 |
| 7 | AVDT_CAT_CODEC | **Codec（必填）** | :72 |
| 8 | AVDT_CAT_DELAY_RPT | 延迟上报能力 | :73 |

### 1.4 典型 A2DP 信令流

```
车机（Sink）              手机（Source）
   │◄── DISCOVER ───────────│  (查询本地有哪些 SEP)
   │── DISCOVER RSP ────►│
   │◄── GETCAP/GET_ALLCAP ─│  (查询某个 SEP 能力)
   │── GETCAP RSP ──────►│  (返回 Codec 列表：SBC/AAC/aptX/LDAC)
   │◄── SETCONFIG ─────────│  (选定 SBC，参数 44.1kHz/16bit)
   │── SETCONFIG RSP ───►│
   │◄── OPEN ──────────────│  (建立 L2CAP 媒体通道，PSM=0x0019)
   │── OPEN RSP ────────►│
   │◄── START ─────────────│  (开始流)
   │── START RSP ───────►│
   │═══ Media Packets ════►│  (RTP 包，含 SBC frames)
   │◄── SUSPEND ───────────│  (暂停)
   │── SUSPEND RSP ─────►│
```

### 1.5 PSM 速查（A2DP/AVRCP）

| PSM | 协议 | 用途 |
|-----|------|------|
| 0x0001 | SDP | 服务发现 |
| 0x0017 | AVCTP | AVRCP 信令（Control）|
| 0x001B | AVCTP_BROWSE | AVRCP 浏览通道（Browsing）|
| 0x0019 | AVDTP | A2DP 信令 + 媒体 |
| 0x001F | ATT | GATT 通道（BLE）|

---

## 二、AVCTP（AVRCP 信令）

### 2.1 AVCTP 头部

```
Byte0:  ┌────────────────┬──────┬──┬──┬───────┐
        │Transaction Lbl │ Pkt  │CR│IPID│       │
        │ (4 bits)       │ (2)  │(1)│(1) │       │
        └────────────────┴──────┴──┴──┴───────┘
Byte1-2: PID (Profile Identifier = 0x110E 即 AVRCP)
Byte3+:  AV/C frame

CR (Command/Response):
  0=AVCT_CMD  命令
  2=AVCT_RSP  回应
```

来源：`system/stack/include/avct_api.h:89-90`

### 2.2 AV/C Frame

```
Byte0: ┌─────────┬──────────┐
       │ CTYPE   │  Subunit │
       │ (4 bits)│  (4 bits)│
       └─────────┴──────────┘
Byte1: ┌────────────────────┐
       │ Opcode             │
       └────────────────────┘

CTYPE（Command Type）：
  0=Control      控制命令（PLAY/PAUSE）
  1=Status       状态查询
  3=Notify       订阅事件
  8=Not Implemented
  9=Accepted
  10=Rejected
  13=Stable
  14=Changed

Opcode：
  0x00 = Vendor Dependent（PASS_THROUGH 之外的所有，如歌曲信息、元数据）
  0x30 = Unit Info
  0x31 = Sub Unit Info
  0x7C = Pass Through（最常用，承载所有按键）
```

### 2.3 PASS THROUGH 按键 Operation ID

| ID (hex) | 名称 | 车机用途 |
|----------|------|----------|
| 0x44 | PLAY | 播放 |
| 0x45 | STOP | 停止 |
| 0x46 | PAUSE | 暂停 |
| 0x4B | FORWARD | 下一曲 |
| 0x4C | BACKWARD | 上一曲 |
| 0x48 | REWIND | 快退 |
| 0x49 | FAST FORWARD | 快进 |
| 0x41 | VOLUME UP | 音量+（少用，车机用 AT+VGS）|
| 0x42 | VOLUME DOWN | 音量- |
| 0x40 | SELECT | 选择 |

### 2.4 AVRCP Vendor Dependent PDU ID（最常用）

| PDU | 名称 | 用途 |
|-----|------|------|
| 0x10 | GetCapabilities | 查询 EventID 列表 |
| 0x20 | GetElementAttributes | 获取歌曲元数据（标题/艺术家/时长）|
| 0x30 | GetPlayStatus | 获取播放状态（playing/paused/stopped + 位置）|
| 0x31 | RegisterNotification | 订阅事件（曲目变化/音量变化）|
| 0x50 | SetAbsoluteVolume | **绝对音量同步（车机最常用）** |
| 0x70 | SetAddressedPlayer | 选择播放器（Spotify/QQ 音乐）|
| 0x71 | GetFolderItems | 浏览文件夹（A2DP 1.4 Browsing）|
| 0x73 | PlayItem | 播放指定项 |
| 0x74 | GetTotalNumberOfItems | 文件夹总数 |

### 2.5 RegisterNotification 事件 ID（EventID）

| ID | 名称 | 触发条件 |
|----|------|----------|
| 0x01 | PLAYBACK_STATUS_CHANGED | 播放状态变化 |
| 0x02 | TRACK_CHANGED | 切歌 |
| 0x03 | TRACK_REACHED_END | 播放到末尾 |
| 0x05 | PLAYBACK_POS_CHANGED | 播放位置变化（每秒上报）|
| 0x09 | NOW_PLAYING_CONTENT_CHANGED | 当前播放列表变化 |
| 0x0A | AVAILABLE_PLAYERS_CHANGED | 可用播放器变化 |
| 0x0B | ADDRESSED_PLAYER_CHANGED | 当前播放器变化 |
| 0x0D | VOLUME_CHANGED | 音量变化 |

---

## 三、OBEX（PBAP / MAP / OPP / FTP 公用）

### 3.1 OBEX Operation Code（Request）

| Op (hex) | 名称 | 含义 |
|----------|------|------|
| 0x80 | CONNECT | 建立 OBEX 会话（带 Target UUID）|
| 0x81 | DISCONNECT | 断开会话 |
| 0x02 / 0x82 | PUT / PUT FINAL | 发送对象（OPP 推文件、MAP 发短信）|
| 0x03 / 0x83 | GET / GET FINAL | 获取对象（PBAP 拉电话簿、MAP 拉短信）|
| 0x85 | SETPATH | 切换文件夹 |
| 0xFF | ABORT | 异常终止 |

> **注**：低 7 位是真正 opcode，最高位 0x80 表示 "FINAL"（最后一包）。GET 通常分包，最后一包带 0x83。

### 3.2 OBEX Response Code（Response）

| Code | 名称 | 含义 |
|------|------|------|
| 0x10 | Continue | 继续传输 |
| 0x20 | OK / Success | 成功 |
| 0x40 | Bad Request | 请求错误 |
| 0x41 | Unauthorized | 未授权 |
| 0x44 | Not Found | 对象不存在 |
| 0x4D | Pre-condition Failed | 前置条件失败 |
| 0xC0 | Internal Server Error | 服务器错 |
| 0xC3 | Service Unavailable | 服务不可用 |

> 所有 response code 最高位也是 0x80（表示 FINAL）。例：`0xA0 = 0x80 | 0x20` 表示"OK 且是最后一包"。

### 3.3 OBEX Header ID（最常用）

| Header (hex) | 名称 | 含义 |
|--------------|------|------|
| 0x42 | Type | MIME 类型（如 `x-bt/phonebook`）|
| 0x46 | Target | 目标 UUID（CONNECT 用，PBAP=796135f0-f0c5-11d8-0966-0800200c9a66）|
| 0x49 | Body | 数据块（中间包）|
| 0x49 | EndOfBody | 数据块（最后包，opcode 0x49 + FINAL）|
| 0x4A | Who | 谁的回应（CONNECT 回应中带 Target UUID）|
| 0x4B | ConnectionID | 会话 ID |
| 0x4F | AuthChallenge | 鉴权挑战 |
| 0x50 | AuthResponse | 鉴权响应 |
| 0xC0 | Count | 对象数量（4 字节）|
| 0xCB | NumberOfMessages | 短信数 |
| 0x01 | Name | 文件/目录名（UTF-16 BE）|

### 3.4 PBAP 拉电话簿示例

```
车机 ──── CONNECT (Target=PBAP_UUID) ──────────► 手机
车机 ◄─── 0xA0 OK (ConnID=0x01) ─────────────── 手机

车机 ──── GET (Name="telecom/pb.vcf", ConnID=0x01,
               Type="x-bt/phonebook",
               AppParams: MaxList=100) ────────► 手机
车机 ◄─── 0x90 Continue + Body[0..n] ─────────── 手机
车机 ──── GET (continuation) ──────────────────► 手机
车机 ◄─── 0xA0 OK + EndOfBody[...] ──────────── 手机

车机 ──── DISCONNECT ──────────────────────────► 手机
车机 ◄─── 0xA0 OK ──────────────────────────────手机
```

### 3.5 PBAP Application Parameters（GET phonebook 时常用）

| Tag | 名称 | 含义 |
|-----|------|------|
| 0x06 | MaxListCount | 最多返回多少条 |
| 0x07 | ListStartOffset | 起始偏移 |
| 0x14 | PhonebookSize | 总条数（响应里）|
| 0x05 | Filter | 过滤位图（哪些字段需要：NAME/TEL/EMAIL）|
| 0x04 | Format | 0=vCard 2.1, 1=vCard 3.0 |

---

## 四、Wireshark 过滤示例

```
# AVDTP
btavdtp                                 # 所有 AVDTP
btavdtp.signal_id == 0x07               # START
btavdtp.signal_id == 0x09               # SUSPEND

# AVCTP / AVRCP
btavctp                                 # 所有 AVCTP
btavrcp                                 # AVRCP 高层
btavrcp.op == 0x7c                      # Pass Through
btavrcp.pdu == 0x50                     # SetAbsoluteVolume

# OBEX
obex
obex.code == 0x80                       # CONNECT request
obex.code == 0xa0                       # OK final response
obex.req.code == 0x03 && obex.hdr.name == "telecom/pb.vcf"
```

---

## FAQ

**Q1：A2DP 媒体通道走哪个 PSM，跟信令一样吗？**
信令走 PSM=0x0019 用于 AVDTP 信令传输；媒体也走同一个 PSM 但是另一条独立的 L2CAP 通道（在 `AVDT_SIG_OPEN` 后建立）。两条通道是逻辑分离的：信令通道一直保持，媒体通道在 START/SUSPEND 间承载 RTP 音频包。

**Q2：AVRCP 1.4 Browsing 在哪条通道？**
单独的 AVCTP_BROWSE 通道，PSM=0x001B。和 Control 通道（0x0017）分开。手机 PBAP 浏览大文件夹时用 Browse 通道避免阻塞控制命令。

**Q3：OBEX 0x49 既是 Body 也是 EndOfBody？**
是的，靠 OBEX Opcode 的 FINAL 位区分：中间包 opcode = 0x03（GET，无 FINAL），里面带 0x49 Body；最后一包 opcode = 0x83（GET 带 FINAL），里面带 0x49 EndOfBody。接收方根据 opcode 的 FINAL 位判断是不是最后一包。

---

## 上路任务

1. 抓一次"车机连接手机 → A2DP 播放音乐"的 btsnoop，用 Wireshark filter `btavdtp` 查看 AVDTP 完整信令流，标出 DISCOVER → SETCONFIG → OPEN → START 各阶段。
2. 抓一次"手机切歌 → 车机显示新歌名"的过程，找 RegisterNotification (EventID=0x02 TRACK_CHANGED) 和 GetElementAttributes 的 PDU。
3. 在车机里启动 PBAP 同步电话簿，抓 btsnoop 看 OBEX CONNECT → GET telecom/pb.vcf → DISCONNECT 完整流，理解为什么大电话簿要分多包传输。
