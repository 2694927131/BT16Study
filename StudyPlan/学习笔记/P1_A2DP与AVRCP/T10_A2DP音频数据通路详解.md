# T10_A2DP音频数据通路详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. Software模式: HCI→btif_a2dp_sink→解码器(SBC/AAC)→AudioTrack→AudioFlinger→扬声器
2. Offload模式: HCI→DSP 直接解码+播放，CPU不参与，通过 a2dp_encoding.cc 与 Audio HAL 通信
3. 音频会话: btif_a2dp_audio_interface.cc 管理 AudioTrack 创建/销毁，音频焦点记录在 gapless_audio
4. 车载 Offload: 通过 sysprop+Flag 控制，DSP 处理降低延迟(通常 <50ms)
5. 常见问题: 连接OK无音频→检查Offload开关/音频焦点/AUDIO_STATE；卡顿→检查ACL质量/编解码器参数/Offload降级

## 详细笔记

### Software 编解码模式

车机作为 A2DP Sink 接收音频:

```
蓝牙芯片 → HCI → btif_a2dp_sink.cc
  → 接收 AVDT 媒体包
  → btif_a2dp_sink_dequeue_buf() 出队音频数据
  → btif_a2dp_source_thread() 音频处理线程
    → SBC/AAC 解码器 (stack/a2dp/)
    → decoded PCM 数据
  → AudioTrack.write(pcm_data)
    → AudioFlinger mixer
    → HAL → 扬声器
```

**关键组件**:
- btif_a2dp_sink.cc: Sink数据接收和管理
- btif_a2dp_audio_interface.cc: AudioTrack 管理
- stack/a2dp/: SBC/AAC 解码器实现

### Offload 编解码模式

```
蓝牙芯片 → HCI → DSP (编解码+播放)
                (CPU 仅做控制通路)

控制路径:
btif_av.cc → audio_hal_interface/a2dp_encoding.cc
  → HAL AIDL: IBluetoothAudioProvider.aidl
  → Audio HAL: openOutputStream(A2DP_SINK)
  → DSP: 配置编解码参数 + 开始编码
  → 返回 Audio Session ID
```

**Offload 启动流程**:
```cpp
btif_av.cc: BTIF_AV_OFFLOAD_START_REQ_EVT [L138]
→ btif_a2dp_audio_start_session() [a2dp_encoding.cc]
→ HAL: 打开 Offload 音频会话
  → 配置 DSP 编解码器参数 (采样率/声道/编解码类型)
  → 为 A2DP 预留 I2S 或内部音频路径
  → DSP 开始解码并播放
→ btif_av: AUDIO_STATE_STARTED 通知 Java
```

**关键属性**:
- `ro.bluetooth.a2dp_offload.supported=true` — 是否支持 Offload
- `persist.bluetooth.a2dp_offload.disabled=false` — 是否禁用 Offload
- btif_av.cc bluetooth.cc 检查这些属性

### 音频会话管理

```
A2DP 音频会话生命周期:
1. AVDT OPEN → 准备音频会话
2. AVDT START → 创建 AudioTrack 或 Offload Session
   - btif_a2dp_audio_start_session() → 获取 session_id
   - 通知 AudioFlinger: gapless_audio=true (A2DP 特性)
3. AVDT SUSPEND → 暂停音频，保持会话
4. AVDT CLOSE → 销毁音频会话、关闭 AudioTrack
```

**音频焦点**:
- A2DP 音乐播放时获得 AudioFocus (GAIN)
- 来电 → AudioFocus 被抢占 → AVDT SUSPEND(自动)
- 挂断 → AudioFocus 恢复 → AVDT START(自动)
- 导航提示 → AudioFocus 短暂丢失 → DUCK(降低音量)而非 SUSPEND

### 音频控制

```
播放控制状态机:
AUDIO_STATE_STOPPED(0) — 音频未播放
AUDIO_STATE_STARTED(1) — 音频正在播放
AUDIO_STATE_REMOTE_SUSPEND(2) — 远端暂停(手机主动暂停)

状态转换:
AVDT START 成功 → AUDIO_STATE_STARTED
AVDT SUSPEND → AUDIO_STATE_REMOTE_SUSPEND
AVDT STOP / ACL断连 → AUDIO_STATE_STOPPED

回调:
btav_sink_callbacks_t.audio_state_cb(state, peer_address)
→ HAL_CBACK → JNI → Java: onAudioStateChanged
```

**Latency Mode** [btif_av.cc L115-L120]:
```cpp
typedef struct {
  bool use_latency_mode;  // true=低延迟, false=高音质
} btif_av_start_stream_req_t;
```

### 常见问题

**问题1: A2DP 连接成功但无音频**
- 检查 AUDIO_STATE 是否为 STARTED
- Offload 模式: 检查 audio_hal_interface 是否正常打开
- Software 模式: 检查 AudioTrack 是否创建成功
- Snoop 检查: AVDT 媒体包是否有数据传输

**问题2: 音频卡顿/断续**
- Snoop 检查: 是否有大量 AVDT 重传
- ACL 连接质量: RSSI 是否过低 (< -80dBm)
- 编解码器参数: SBC Bitpool 是否过高
- Offload 降级: 尝试 disable Offload 后验证
- BQR 检查: `adb dumpsys bluetooth_manager | grep -i quality`

**问题3: Offload 音频异常**
- 检查 `ro.bluetooth.a2dp_offload.supported` 和 DSP 状态
- 强制降级: `adb shell setprop persist.bluetooth.a2dp_offload.disabled true`
- 重新连接后走 Software 路径对比验证