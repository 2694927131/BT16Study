# T12_A2DP_AVRCP问题定位实战

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. 日志分析三板斧: logcat按Tag过滤(bt_btif_av/bt_bta_av/bt_btif_avrc)→dumpsys bluetooth_manager→HCI Snoop Wireshark分析
2. AVDT信令可在snoop中完整追踪: DISCOVER→GET_CAP→SET_CONFIG→OPEN→START→SUSPEND→CLOSE
3. 五大典型问题各有定位路径: 无音频→检查编解码+AUDIO_STATE+Offload；卡顿→RSSI+重传+Bitpool；AVRCP不更新→通知注册+VTG/passthrough
4. dumpsys输出是快速诊断利器: 可一键查看连接状态/编解码器/A2DP配置/音频状态/BQR报告
5. Offload降级定位: ro.bluetooth.a2dp_offload.supported→dumpsys查看Offload状态→dumpsys media.audio_flinger→disable Offload对比

## 详细笔记

### 一、日志分析技巧

**A2DP日志Tag**:
```bash
# 完整A2DP连接日志
adb logcat -s bt_btif_av bt_bta_av | grep -i "peer\|state\|connect\|open\|codec"

# 状态转换
bt_btif_av: Idle→Opening→Opened→Started

# 编解码器协商
bt_btif_av: codec_config

# 音频状态
bt_btif_av: AUDIO_STATE_STARTED/STOPPED/SUSPENDED
```

**AVRCP日志Tag**:
```bash
adb logcat -s bt_btif_avrc | grep -i "vol\|metadata\|track\|play\|passthru\|register"

# 音量变化
bt_btif_avrc: abs_vol / set_volume_rsp / volume_change_notification_rsp

# 元数据
bt_btif_avrc: parse_metadata / track_change / AVRC_EVT_TRACK_CHANGE
```

### 二、HCI Snoop Log分析

**A2DP连接抓包分析**(Wireshark):
```
Wireshark过滤器:
- btavdtp          → 只看AVDT信令
- btl2cap          → L2CAP通道建立
- btsdp            → SDP查询
- bt.addr == XX:XX → 过滤特定设备

AVDT信令完整序列:
1. DISCOVER_CMD/Discover_Response → 找到SEP
2. GET_CAPABILITIES_CMD/GetCapabilities_Response → 看支持哪些编解码器
3. SET_CONFIGURATION_CMD/SetConfiguration_Response → 看最终协商的编解码参数
4. OPEN_CMD/Open_Response → 通道建立完成
5. START_CMD/Start_Response → 开始传输音频
6. SUSPEND_CMD → 暂停
7. CLOSE_CMD → 断开
```

**终端命令**:
```bash
# 拉取Snoop
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log

# 开启/关闭
adb shell setprop persist.bluetooth.btsnooplogfilter 0  # 0=full
adb shell setprop persist.bluetooth.btsnooplogformat btsnoop
```

### 三、五大典型案例

**案例1: A2DP 连接成功但无音频**
```
问题: CONNECTION_STATE=CONNECTED 但无声音
步骤:
1. dumpsys → 检查 mAudioState → 是否为 STATE_STARTED
   - 如果 STATE_STOPPED → AVDT_START 未成功 → snoop检查START_CMD
2. dumpsys → 检查 Codec Config → 确认编解码器一致
3. Offload模式: 检查 audio_hal_interface 日志
   - dumpsys media.audio_flinger | grep a2dp → 检查Output是否活跃
4. 强制降级到Software:
   adb shell setprop persist.bluetooth.a2dp_offload.disabled true
   重新连接→验证→排除Offload问题
5. Software模式: 检查 AudioTrack 创建日志
   - btif_a2dp_audio_interface: start_audio_datapath
```

**案例2: 蓝牙音乐卡顿**
```
可能原因(按概率): 干扰>编解码参数>Offload异常
1. 环境干扰:
   - dumpsys → 查看 RSSI → < -80dBm 容易卡顿
   - Snoop → 过滤 btavdtp → 大量媒体包重传
2. 编解码参数:
   - dumpsys → CodecStatus → 检查 SampleRate/Bitpool
   - SBC Bitpool过高 >53 → 无线带宽不足 → 降bitpool
3. Offload异常:
   - 降级到Software对比 → disable Offload
4. ACL质量:
   - BQR → adb dumpsys bluetooth_manager | grep quality_report
   - 链路质量过低 → 可能的干扰或芯片问题
```

**案例3: AVRCP 歌曲信息不显示**
```
步骤:
1. logcat -s bt_btif_avrc | grep "track_changed\|AVRC_EVT_TRACK_CHANGE"
   - 检查是否收到 track change event
2. Snoop: 过滤 AVCT → 查看 AVRC_PDU_REGISTER_NOTIFICATION 是否注册 AVRC_EVT_TRACK_CHANGE
3. Snoop: 查看 AVRC_PDU_GET_ELEMENT_ATTR 命令是否发出 + 响应
4. 检查互操作性: 手机支持的AVRCP版本
   - interop_database.conf 是否需要添加特殊处理
```

**案例4: 音量不同步**
```
步骤:
1. 检查手机是否支持 Absolute Volume
   - dumpsys → mAbsoluteVolumeSupported → true/false
   - BTRC_FEAT_ABSOLUTE_VOLUME bit是否设置
2. logcat -s bt_btif_avrc | grep "register_notification.*VOLUME"
   - 车机是否注册了 AVRC_EVT_VOLUME_CHANGE
3. logcat -s bt_btif_avrc | grep "set_volume_rsp"
   - 车机是否正确响应 SetAbsoluteVolume
4. 车机音量变化 → volume_change_notification_rsp是否成功发出
5. Snoop → AVCT → AVRC_PDU_SET_ABSOLUTE_VOLUME 交互序列
```

**案例5: A2DP Offload 异常**
```
步骤:
1. 确认Offload支持:
   adb shell getprop ro.bluetooth.a2dp_offload.supported
2. 检查Offload状态:
   adb dumpsys bluetooth_manager | grep -i offload
3. 检查Audio HAL:
   adb dumpsys media.audio_flinger | grep -A 5 a2dp
4. 强制降级:
   adb shell setprop persist.bluetooth.a2dp_offload.disabled true
   关闭再打开蓝牙 → 验证是否改善
5. DSP日志: vendor日志查看芯片侧状态
```

### 四、dumpsys 输出解读

**关键信息提取**:
```bash
adb dumpsys bluetooth_manager

# 关键字段:
# mActiveDevice: XX:XX:XX:XX:XX:XX  ← 当前活跃设备
# mConnectionState: 1=CONNECTING 2=CONNECTED 0=DISCONNECTED
# mAudioState: 1=STARTED 0=STOPPED 2=REMOTE_SUSPEND
# mCodecConfig: SampleRate/ChannelMode/Bitpool  ← 关键！
# mMaxConnectedAudioDevices: 1
# mAbsoluteVolumeSupported: true/false
# mIsPlaying: true/false
# BQR quality report: RSSI/RX/TX packets
```

### 五、车载特殊定位

```bash
# 车载常见一键排障命令
adb shell dumpsys bluetooth_manager > /sdcard/bt_dump.txt
adb logcat -s bt_btif_av bt_btif_hf bt_bta_dm bt_btif_avrc -d > /sdcard/bt_log.txt
adb shell dumpsys media.audio_flinger > /sdcard/audio.txt
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log

# Offload 降级测试
adb shell setprop persist.bluetooth.a2dp_offload.disabled true
adb shell kill -9 $(pidof com.android.bluetooth)  # 重启蓝牙进程

# 强制编解码器
adb shell device_config set_sync_disabled_for_tests persistent
adb shell device_config put bluetooth a2dp_source_codec_priority <codec>
```