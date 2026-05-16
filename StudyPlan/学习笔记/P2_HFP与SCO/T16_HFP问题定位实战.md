# T16_HFP问题定位实战

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. HFP日志四板斧: bt_btif_hf(连接/状态)+bt_bta_ag(AG行为)+bt_bta_ag_at(AT命令)+bt_bta_ag_sco(SCO音频)
2. Snoop分析: btrfcomm(AT命令流)→HFP Profile(btsdp)→btsco/btl2cap SCO数据
3. 五大典型问题: HFP连接失败(SDP/RFCOMM/AT)→静音(SCO路由/mic通路/NREC)→回声(AEC配置)→WBS降级→通话中断(SCO断开信号)
4. dumpsys解读: mConnectionState/SLC/mAudioState/mCodec/mScoState/mNREC/mCallState全线覆盖
5. 车载特殊: vendor.sco.i2s + BQR + NREC配置是排障重点

## 详细笔记

### 一、日志分析

**HFP 核心 Tag + 含义**:
```bash
# 连接层
adb logcat -s bt_btif_hf
→ "ConnectionStateCallback" = 连接状态变化
→ "SLC" / "Service Level Connection" = SLC已建立
→ "open status" = BTA_AgOpen结果
→ "reset_control_block" = HF控制块重置

# AG行为层
adb logcat -s bt_bta_ag
→ "state" / "event" = AG状态机转换
→ "AT+CMER=" = 指示器事件配置
→ "setcodec" = 编解码器设置

# AT命令
adb logcat -s bta_ag_at
→ "BRSF" = 特性协商(检查reserved bits)
→ "ATD" / "AT+CHUP" / "ATA" = 通话操作

# SCO音频
adb logcat -s bt_bta_ag_sco
→ "SCO_OPENING" / "SCO_CLOSING" = SCO状态
→ "esco codec" = eSCO codec选择
→ "CreateSco" / "Setup_Synchronous_Connection" = HCI建链
```

**连接冲突日志** (btif_hf.cc L413-459):
```
"possible connection collision" → 忽略失败或断开旧连接
Metrics: HFP_COLLISON_AT_AG_OPEN / HFP_COLLISON_AT_CONNECTING
```

### 二、HCI Snoop Log分析

**RFCOMM 连接** (Wireshark):
```
过滤器: btrfcomm
SABM → UA → 多次SABM → RFCOMM 建立
AT Command: RFCOMM data → 右键 Follow RFCOMM stream
AT 命令序列: BRSF → CIND → CMER → CHLD → BIND → BAC → BCC → BCS
```

**SCO 建链** (Wireshark):
```
过滤器: btsco 或 单独查看 HCI
HCI Command: Setup Synchronous Connection
→ Voice_Setting: 0x0060(CVSD) 或 0x0003(Transparent/mSBC)
→ Tx/Rx Bandwidth: 8000(CVSD) / 16000(mSBC)
→ Max Latency: 10-20ms
HCI Event: Synchronous Connection Complete → Status=0x00(成功)
SCO Data: CVSD/mSBC 编码音频
```

### 三、五大典型案例

**案例1: HFP 连接失败**
```
可能原因(按概率): 射频干扰>RFCOMM超时>SDP失败>AT协商失败
定位:
1. logcat bt_btif_hf → "open status" → 错误码
2. Snoop btrfcomm → 是否收到 RFCOMM UA 确认
3. Snoop btsdp → 是否找到 HFP Service UUID 0x111E
4. Snoop → AT+BRSF 是否收到响应
修复:
- RFCOMM超时: 增加RFCOMM timeout (bta_ag_rfc.cc)
- SDP失败: 检查 interop_database.conf "disable_hfp_sdp_after_collision"
- AT协商: 检查远端 BRSF bit → 可能需要 interop 配置
```

**案例2: 通话对方听不到声音**
```
定位:
1. logcat bt_bta_ag_sco → "SCO_OPEN_ST" 是否到达
   - 未到达: SCO建链失败
2. 车载检查: tinymix → MIC route
3. vendor.sco.i2s → I2S路由是否正确
4. NREC: AT+NREC=0? → 检查 DSP 配置
修复:
- SCO 没有建链 → 检查 eSCO参数 → 降级到 SCO
- I2S → PCM 配置错误 → 查看 BT_BOARD 配置
- NREC → 检查 BT Audio HAL interchange
```

**案例3: 通话有回声**
```
定位:
1. 回声类型:
   A. 近端回声(本车回声返回到本车)→本车EC问题
   B. 远端回声(对方听到自己声音)→对方EC+本车AC问题
2. tinymix: 检查EC寄存器 → EC bypass? → enable
3. AEC延迟对齐: DSP decoder→speaker→mic→AEC必须不超过 100ms
修复:
- 增加 EC 增益 (DSP 调整)
- 降低 speaker→mic 声学隔离 (硬件)
- 请求对方也检查 NREC: AT+NREC=1
```

**案例4: WBS 协商失败**
```
定位:
1. logcat bta_ag_at → AT+BAC 是否包含 2(mSBC)
2. logcat bt_bta_ag → "setcodec" 是否成功
3. Snoop → AT+BCC / +BCS codec_id
4. 手机是否支持 WBS:
   adb logcat | grep -E "BAC|BCC|BCS|codec"
修复:
- 检查 interop → 可能需 "disable_hfp_wbs" interop
- 强制 CVSD: disable codec(2) → 使用 CVSD
```

**案例5: 通话中断**
```
定位:
1. logcat bt_bta_ag_sco → 断开原因
   - "SCO_CLOSING" 正常
   - "SCO_SHUTTING"(异常)
2. eSCO 重传率:
   BQR or BTM log → retransmission_rate
3. RSSI: dumpsys → BTM log → -dBm值
4. HCI: 是否有 Disconnection Complete → Reason code
修复:
- 干扰→ 移动设备靠近车载BT天线
- 重传过高→ 调整eSCO参数(Tesco)
- 距离→ 检查天线位置
```

### 四、dumpsys 输出解读

```bash
adb dumpsys bluetooth_manager
```

**HFP 关键字段提取**:
```
mConnectionState → DISCONNECTED/CONNECTED/SLC_CONNECTED
mAudioState → DISCONNECTED/CONNECTING/CONNECTED
mCodec → 1=CVSD 2=mSBC 3=LC3
mIsNoiseReductionOn → true/false
mIsEchoCancellationOn → true/false
mIncomingCallDevice → XX:XX:XX:XX:XX:XX (当前来电设备)
mActiveDevice → XX:XX:XX:XX:XX:XX (当前活跃通话设备)
mMultiHFPending → true/false (多HF冲突pending)
mScoState → 0=Idle 1=Opening 2=Opened 3=Closing
```

**车载专用命令**:
```bash
# I2S 路由验证
adb shell tinymix  # 查看所有 mixer control
adb shell tinymix "Bluetooth SCO" 1  # 手动路由

# eSCO 参数
adb shell getprop | grep -i sco

# 强制 WBS 开关
adb shell setprop persist.bluetooth.hfp_wbs_enable true/false

# 重启蓝牙进程
adb shell kill -9 $(pidof com.android.bluetooth)
```