# T08_A2DP连接流程源码追踪

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. connect_int [L3461]: get_profile_service(UUID)→btif_queue_connect→主线程ProcessEvent(BTIF_AV_CONNECT_REQ_EVT)→StateIdle→BTA_AvOpen→TransitionTo(Opening)
2. BTA_AvOpen → bta_av_act.cc: 检查能否连接 → bta_av_query_mandatory_codec_priority → BTA_AvOpen → bta_av_api_open → event BTA_AV_API_OPEN_EVT
3. StateOpening [L1748]: 状态机已有5个状态类(Idle/Opening/Opened/Started/Closing)+事件枚举(BTIF_AV_CONNECT_REQ_EVT等14种)
4. Source vs Sink 分离设计 [L411-L419]: BtifAvSource(管理Source角色)/BtifAvSink(管理Sink角色)，车机主要是Sink
5. 车载Sink路径: btif_av_sink_connect [L3545] → connect_int → BTA_AvOpen(peer, UUID_SERVCLASS_AUDIO_SOURCE)

## 详细笔记

### 完整调用链

```
App: BluetoothA2dp.connect(device)
→ A2dpService.connect(device) → JNI → connectA2dpNative()
→ btif_av.cc: btif_av_sink_connect(peer_address) [L3545]
  → btif_queue_connect(UUID_SERVCLASS_AUDIO_SOURCE, peer_address, connect_int)
→ connect_int(peer_address, UUID_SERVCLASS_AUDIO_SOURCE) [L3461]
  → btif_av_both_enable()? → btif_av_sink_dispatch_sm_event(BTIF_AV_CONNECT_REQ_EVT)
  → else → do_in_main_thread(connection_task) [L3486]
    → BtifAvPeer* peer = btif_av_sink.FindOrCreatePeer(peer_address) [L3476]
    → peer->StateMachine().ProcessEvent(BTIF_AV_CONNECT_REQ_EVT, nullptr) [L3484]
→ StateIdle::ProcessEvent(BTIF_AV_CONNECT_REQ_EVT) [L1740 语义区]
  → AllowedToConnect() 检查连接数限制
  → btif_av_query_mandatory_codec_priority(peer) [L1747]
  → BTA_AvOpen(peer, bta_handle, true, LocalUuidServiceClass) [L1748]
  → TransitionTo(kStateOpening) [L1749]
→ BTA: bta_av_api_open() → 投递 BTA_AV_API_OPEN_EVT
  → BTA事件循环 → bta_av_open_act()
    → SDP: 查询远端 A2DP Service (UUID 0x110B Sink / 0x110A Source)
    → AVDT: 路由到 AVDT_Discover → SEP 发现
      → AVDT_GetCap → 编解码器能力获取
      → AVDT_SetConfig → 编解码器协商
      → AVDT_Open → L2CAP 媒体通道建立
→ AVDT Open 成功 → BTA_AV_OPEN_EVT 回调
→ StateOpening::ProcessEvent(BTA_AV_OPEN_EVT)
  → btif_report_connection_state(OPENED)
  → TransitionTo(kStateOpened)
→ HAL_CBACK → JNI → Java: onConnectionStateChanged(CONNECTED)
```

### BtifAvStateMachine 架构

5个状态类 [L180-L264]:
- StateIdle [L181-L187] — 空闲，接收连接请求
- StateOpening [L192-L206] — AVDT OPEN 进行中
- StateOpened [L208-L217] — AVDT 通道已建立
- StateStarted [L219-L228] — 音频数据传输中
- StateClosing [L230-L239] — AVDT CLOSE 进行中

14种事件枚举 [L130-L145]:
BTIF_AV_CONNECT_REQ → DISCONNECT_REQ → START_STREAM → STOP_STREAM → SUSPEND_STREAM → SINK_CONFIG → ACL_DISCONNECTED → OFFLOAD_START → AVRCP_OPEN/CLOSE/REMOTE_PLAY → SET_LATENCY → RECONFIGURE

### BtifAvPeer [L267-L409]

每个远端设备一个 BtifAvPeer 实例:
- peer_address_: 远端地址
- peer_sep_: SEP类型 (AVDT_TSEP_SRC=Source / AVDT_TSEP_SNK=Sink)
- bta_handle_: BTA层句柄
- state_machine_: 独立的状态机实例
- flags_: 本地标志 (kFlagLocalSuspendPending / kFlagRemoteSuspend / kFlagPendingStart / kFlagPendingStop)

### Source/Sink 分离

BtifAvSource [L411]: 管理所有Source角色连接
BtifAvSink: 管理所有Sink角色连接

connect_int [L3461-L3491]:
- uuid=UUID_SERVCLASS_AUDIO_SOURCE → Source角色发起
- uuid=UUID_SERVCLASS_AUDIO_SINK → Sink角色发起
- 车机→Sink: UUID_SERVCLASS_AUDIO_SOURCE → BtifAvSource::FindOrCreatePeer → ProcessEvent

### 车载Sink连接路径

```cpp
btif_av_sink_connect → btif_queue_connect
→ UUID_SERVCLASS_AUDIO_SOURCE (车机告诉手机"我是Sink")
→ connect_int → BtifAvSource::FindOrCreatePeer
→ ProcessEvent(BTIF_AV_CONNECT_REQ_EVT)
→ BTA_AvOpen(peer, handle, true, UUID_SERVCLASS_AUDIO_SOURCE)
→ StateMachine::TransitionTo(kStateOpening)
```

### SDP查询过程

bta_av_act.cc 中:
- bta_av_open_act() → SDP查询 A2DP Sink 0x110B
- 获取AVDT参数(Channel/PSM/Version)
- 成功后进入AVDT信令序列

### AVDT信令序列

| 步骤 | 命令 | 方向 | 作用 |
|------|------|------|------|
| 1 | DISCOVER | INT→ACP | 发现远端SEP列表 |
| 2 | GET_CAPABILITIES | INT→ACP | 获取编解码能力 |
| 3 | SET_CONFIGURATION | INT→ACP | 协商编解码参数 |
| 4 | OPEN | INT→ACP | 打开媒体通道 |
| 5 | START | INT→ACP | 开始音频传输 |

信令超时: BTA_AV_SIGNALLING_TIMEOUT_MS = 8000ms

### AVRCP 先行连接优化

StateIdle 中 [L1761-L1818]:
当收到 BTA_AV_RC_OPEN_EVT 时(AVRCP先连接):
- 设置 AvOpenOnRcTimer: kTimeoutAvOpenOnRcMs = 2000ms
- 超时后调用 btif_av_sink_initiate_av_open_timer_timeout
- 触发 A2DP 连接(BTA_AvOpen)
- 解决 Jabra 等耳机"先连AVRCP后连A2DP"的问题