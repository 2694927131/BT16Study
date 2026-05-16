# T05_Profile连接流程详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. Profile 连接通用模式：BluetoothProfile.connect→Service→JNI→BTIF→BTA，状态回调经 HAL_CBACK→JNI→Java
2. A2DP 连接：SDP 查询→AVDT DISCOVER→GET_CAP→SET_CONFIG→OPEN→START 五步信令
3. HFP 连接：RFCOMM+SDP→SLC(AT命令能力协商/WBS/SWB编解码)→SCO 音频链路
4. 自动连接按 PRIORITY_AUTO_CONNECT(1000) 排序，HFP 优先于 A2DP
5. 多设备连接每个设备独立状态机，通过音频焦点管理切换

## 详细笔记

### 一、通用调用链
```
App: BluetoothA2dp.connect(device)
→ Framework: ProfileService → Service → JNI → BTIF → BTA

Proxy 获取: getProfileProxy(context, listener, PROFILE_A2DP)
→ listener.onServiceConnected(profile, proxy)

连接状态: DISCONNECTED(0)→CONNECTING(1)→CONNECTED(2)→DISCONNECTING(3)
HFP 额外状态: SLC_CONNECTED(3)

优先级: PRIORITY_OFF(0)/PRIORITY_ON(100)/PRIORITY_AUTO_CONNECT(1000)
```

### 二、A2DP 连接
```
btif_av.cc: btif_av_source_connect()
→ BTA_AvOpen() → bta_av_act.cc BTA_AV_CONNECT_REQ
→ SDP 查询 UUID 0x110B
→ AVDT: DISCOVER→GET_CAPABILITIES→SET_CONFIGURATION→OPEN→START
→ btif_report_connection_state(OPENED) → HAL_CBACK → Java: CONNECTED
→ AVDT_START → btif_av Started → AUDIO_STATE_STARTED
```

### 三、HFP 连接
```
btif_hf.cc: connect() → BTA_AgOpen() → bta_ag_act.cc
→ SDP UUID 0x111E/0x1131 → RFCOMM 连接
→ SLC 建立: AT+BRSF→AT+CIND→AT+CMER→AT+CHLD→AT+BIND→AT+BAC→AT+BCC
→ WBS: AT+BAC → mSBC
→ SWB: AT+BAC → LC3/aptX
→ SLC_CONNECTED → SCO 可选
```

### 四、自动连接
蓝牙开启→遍历已配对设备→按 PRIORITY_AUTO_CONNECT 排序
→ HFP优先→A2DP→AVRCP→HID/PAN
→ 失败指数退避重试
→ 车载优化: 最后连接设备优先、设备数限制(≤2)、超时缩短(~5s)

### 五、多设备连接
每个设备独立状态机、主设备(优先HFP)、副设备(仅A2DP)
音频焦点: 来电暂停副设备、挂断恢复

### 六、常见问题
- 连接失败: SDP超时/无服务/PRIORITY_OFF → dumpsys bluetooth_manager
- 卡CONNECTING: AVDT/RFCOMM超时/ACL质量差 → btif_av状态机检查
- A2DP无音频: AVDT_START未成功/Offload初始化失败 → 检查 AUDIO_STATE