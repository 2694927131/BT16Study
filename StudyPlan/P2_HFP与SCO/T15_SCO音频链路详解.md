# T15_SCO音频链路详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. SCO(64kbps,CVSD,无重传) vs eSCO(可变速率,T2参数,3次重传窗口) → 车载几乎都用eSCO
2. bta_ag_sco.cc 状态机: OPENING→OPENED→CLOSING→SHUTTING→SHUTDOWN，通过BTM_ESCO 建链
3. 音频路由: HCI(CVSD over HCI→CPU) vs I2S/PCM(直接DSP)→车载走I2S降低延迟+CPU负担
4. WBS/SWB协商: mSBC(16kHz,60字节/帧,3.75ms)→LC3(32kHz,喜帧)→aptX Voice SWB→esco_parameters由codec决定
5. SCO质量: BQR监控重传率+eSCO_dtx参数配置+可能需要ADC/回声消除调整

## 详细笔记

### 一、SCO vs eSCO

| 参数 | SCO | eSCO(常用, T2参数) |
|------|-----|-------------------|
| 速率 | 固定 64kbps | 可变(可通过 BT 写) |
| 编码 | CVSD(窄带8kHz) | CVSD/mSBC/LC3/aptX |
| 间隔(Tesco) | 由厂商决定 | 协商决定，典型 12/16/ |
| 窗口(Wesco) | SCO无窗口概念 | 重传窗口，如 4/6/ |
| 重传 | 无 | 1-3次重传(latency要求) |
| 空包(no data) | CVSD silence | 包含 DTX 支持 |
| 双方支持 | 旧设备 | BT 2.1+ (推荐) |

### 二、SCO建链流程 (bta_ag_sco.cc)

**状态机状态**:
```
BTA_AG_SCO_SHUTDOWN_ST → BTA_AG_SCO_LISTEN_ST → BTA_AG_SCO_OPENING_ST
→ BTA_AG_SCO_OPEN_ST → BTA_AG_SCO_CLOSING_ST → BTA_AG_SCO_SHUTTING_ST
```

**建链流程**:
```
1. bta_ag_sco_open(bd_addr, codec=CVSD/mSBC/LC3/aptX)
   → esco_parameters.h 查表选择参数: T2_CVSD / T2_MSBC / T2_SWB_LC3
2. BTM_CreateSco(bd_addr, is_orig=true, p_esco_params)
   → 投递到 BTM 线程
3. btm_esco_conn_rsp → 调用 bluetooth::shim 层发送 HCI Setup Synchronous Connection
   → HCI: Setup_Synchronous_Connection
     - Transmit_Bandwidth
     - Receive_Bandwidth
     - Max_Latency
     - Voice_Setting (编码格式+CVSD/Transparent)
     - Retransmission_Effort (none/power/quality/don't care)
     - Packet_Type (2-EV3/3-EV3/2-EV5/3-EV5)
4. HCI: Synchronous_Connection_Complete_Event
   → esco 建立 → BTA_AG_SCO_OPEN_ST
5. bta_ag_sco_open() → 音频 HAL 打通
```

**建链失败回退策略**:
```
eSCO T2 失败 → 检查重试次数
  → 降级到 SCO (无重传) → 重试 n 次
  → 仍失败 → BTA_AG_SCO_SHUTDOWN_ST
```

### 三、SCO 音频路由 (车载关键)

**两种路由方式对比**:

| 路由方式 | 路径 | 延迟 | CPU占用 | 车载使用 |
|----------|------|------|---------|----------|
| HCI 路由 | BT→HCI→CPU→AudioFlinger→DAC→扬声器 | 高(~30ms) | 高 | 少 |
| I2S/PCM | BT→I2S→DSP→DAC→扬声器 | 低(~2ms) | 0 | 几乎都用 |

**I2S路由配置**:
- 硬件层面: BT芯片I2S输出→车载DSP输入→Codec
- 软件层面: vendor.sco.i2s=true 或厂商 persist 属性
- bta_ag_sco.cc 发现成功→ HfpClientInterface::update_esco_parameters

### 四、WBS (Wideband Speech)

**mSBC 参数**:
- 16kHz 采样率 → 输出 60 bytes/帧 (3.75ms)
- 双边对称 3-EV3 packet type (retransmission)

**协商流程**:
```
AT+BAC: 1(CVSD),2(mSBC)
→ but_AT+BCC → bta_ag_setcodec(mSBC)
→ +BCS: 2 → codec selected
→ esco_parameters: T2 setting → use MSBC
→ bta_ag_sco_open(codec=mSBC)
```

### 五、SWB (Super Wideband Speech)

**bta_ag_swb_aptx.cc**:
```
AT+BAC: 1(CVSD),2(mSBC),3(LC3),vendor(aptX-voice)
→ BCC → bta_ag_setcodec(LC3/aptx)
→ +BCS → eSCO T2 SWB 参数
→ esco_parameters: T2_SWB_LC3 / T2_aptx
```

| 编解码 | 采样率 | 帧长 | 延迟 | 优势 |
|--------|--------|------|------|------|
| LC3 | 32kHz | 可配置 | 7.5ms | 蓝牙5.2 标准 |
| aptX Voice | 32kHz | 固定 | 低 | 高音质+低延迟 |

### 六、SCO 音频质量

**影响因素**:
- 干扰 (环境微波/电磁)
- 距离 (RSSI 降低增加重传)
- eSCO 参数 (重传窗口不够)
- 编码器实现 (HW vs SW)

**eSCO 重传率**:
```
BTM 统计: num_rx_pkt / num_tx_pkt / retransmission_count
BQR: adb dumpsys bluetooth_manager | grep "quality"
```

**NREC/EC 配置**:
- AT+NREC=0/1 → 关闭/开启降噪
- bthf_nrec_t [bt_hf.h L47]: BTHF_NREC_STOP / BTHF_NREC_START
- 车载: 回声消除在 DSP 完成 → DSP 报告状态给蓝牙栈

### 七、常见问题

| 问题 | 定位 | 解决 |
|------|------|------|
| 通话对方听不到 | SCO路由→I2S配置→MIC通路 | 检查 vendor.sco.i2s / mac_mute |
| 噪音/回声 | NREC状态 / AEC延迟 | adb shell tinymix 查看 codec 寄存器 |
| SCO建链失败 | HCI SetupSyncConnection → 错误码 | 降级回退到 SCO / 检查eSCO参数 |
| WBS降级混音 | AT+BAC/BCC序列; codec mismatch | 强制 codec / interop 配置 |