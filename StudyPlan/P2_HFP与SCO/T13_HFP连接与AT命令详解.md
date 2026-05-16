# T13_HFP连接与AT命令详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. connect→RFCOMM→AT+BRSF/BAC/BCC→SLC_CONNECTED：连接需经SDP→RFCOMM建链→AT五步协商
2. bta_ag_at.cc AT解析器：table驱动，arg_type支持NONE/READ/TEST/SET/FREE五种参数类型，循环匹配命令表
3. BRSF特性协商: 12定义比特+32位扩展，bit通过后影响编解码/HF Indicator等后续操作
4. WBS: AT+BAC(mSBC=2)→AT+BCC→bta_ag_setcodec→eSCO T2参数；SWB: LC3(=1)或aptX Voice(=2)同样流程
5. 车载HF角色: btif_hf_cb[] 多slot管理→AG端在手机→车机HF通过 bt_hf_callbacks 回调收听；SLC_EXCEPTION_TIMEOUT=10s

## 详细笔记

### 一、HFP连接流程

```
App: BluetoothHeadset.connect(device)
→ HeadsetService.connect() → JNI → btif_hf.cc: connect()
→ btif_queue_connect(UUID_HANDSFREE, ...)
→ connect_int() → BTA_AgOpen(bd_addr, BTA_HFP_SERVICE_MASK)
→ bta_ag_act.cc: bta_ag_open_act() → bta_ag_open_do_open()

1. SDP查询: 查询远端 HFP 服务 → UUID 0x111E(HF) / 0x1131(AG)
   源码: bta_ag_uuid[] = {UUID_SERVCLASS_HEADSET_AUDIO_GATEWAY, UUID_SERVCLASS_AG_HANDSFREE}

2. RFCOMM连接: Port打开→RFCOMM SABM/DISC→L2CAP通道(PSM=0x0003)

3. SLC协商序列:
   AT+BRSF=<features>        → 双方上报支持特性
   AT+CIND=?                 → 查询支持的指示器(call/callsetup/service/signal/roam/battchg/callheld)
   AT+CIND?                  → 读取当前指示器值
   AT+CMER=3,0,0,1           → 配置指示器事件上报
   AT+CHLD=?                 → 查询三方通话能力
   AT+BIND=<indicators>      → HFP 1.7 HF Indicators
   AT+BAC=<codecs>           → 编解码器能力(1=CVSD, 2=mSBC, ...)
   AT+BCC                    → 编解码器协商开始

4. 连接回调:
   btif_hf_cb[idx].state = BTHF_CONNECTION_STATE_CONNECTED [L473]
   → bt_hf_callbacks->ConnectionStateCallback(CONNECTED, bd_addr, SUCCESS) [L476]

5. SLC完成:
   btif_hf_cb[idx].state = BTHF_CONNECTION_STATE_SLC_CONNECTED
   → bt_hf_callbacks->ConnectionStateCallback(SLC_CONNECTED, ...)
```

### 二、AT命令机制 (bta_ag_at.cc)

**解析器架构** [L89]:
```cpp
bta_ag_process_at(tBTA_AG_AT_CB* p_cb, char* p_end)
  → for (idx = 0; p_at_tbl[idx].p_cmd[0] != 0; idx++)
    → utl_strucmp(p_cmd, p_cmd_buf) 匹配命令
    → 验证 arg_type: NONE/READ("AT+CMD?")/TEST("AT+CMD=?")/SET("AT+CMD=val")/FREE
    → 调用 p_at_tbl[idx].p_cback(arg_type, int_arg, ...)
```

**tBTA_AG_AT_CB 控制块**: p_cmd_buf(当前命令)、cmd_pos(当前解析位置)、p_at_tbl(命令表)、p_err_cback/p_cback(回调)

**命令/响应/URC 格式**:
- Command: `AT+CMD[?=?][=value]\r` → 解析 → 执行 → OK/ERROR
- Response: `\r\n+CMD: value\r\n` → 被远端解析
- URC (Unsolicited): `\r\n+CIEV: <ind>,<value>\r\n` → 主动通知

### 三、BRSF特性协商

**HFP BRSF 关键特性位** (12 bits, bta_ag_int.h):
| Bit | 特性 | 含义 |
|-----|------|------|
| 0 | EC/NR | 回声消除+降噪 |
| 1 | Three-way calling | 三方通话 |
| 2 | CLI Presentation | 来电显示 |
| 3 | Voice Recognition | 语音识别激活 |
| 4 | Remote Volume Control | 远程音量控制 |
| 5 | Enhanced Call Status | HFP 1.6 ECS |
| 6 | Enhanced Call Control | HFP 1.6 ECC |
| 7 | Codec Negotiation | WBS/SWB协商 |
| 8 | HF Indicators | HFP 1.7 |
| 9 | eSCO S4 (T2) Settings | eSCO T2参数支持 |
| 10 | Enhanced Voice Recognition | HFP 1.7 EVR status |
| 11 | Voice Recognition Text | 语音识别文本 |

协商后在 bta_ag_act.cc 中根据 `peer_features` 决定后续行为(如启用WBS/SWB/EVRS等)

### 四、编解码器协商

**WBS (Wideband Speech) 协商**:
```
AT+BAC=1,2   (HF上报: 1=CVSD窄带, 2=mSBC宽带)
AT+BCC       (AG触发: 开始协商)
→ bta_ag_setcodec(BTA_AG_CODEC_MSBC) → 切换eSCO参数为T2
→ +BCS=<codec_id> 返回: 2=mSBC使用中
→ BTA_AG_SCO_OPEN_EVT → eSCO建链
```

**SWB (Super Wideband Speech) 协商**:
```
AT+BAC=1,2,3   (HF上报: 3=LC3, 或vendor特定codec)
→ bta_ag_swb_aptx.cc / LC3相关 → +BCS
→ eSCO T2 SWB参数
→ BTA_AG_SCO_OPEN_EVT
```

### 五、HFP 1.7+ 新特性

- **HF Indicators** [bt_hf.h L74]: BTHF_HF_IND_ENHANCED_DRIVER_SAFETY(驾驶安全) / BATTERY_LEVEL_STATUS(电池)
- **Enhanced Call Status**: 来电详情(号码+姓名+类型)
- **Voice Recognition with Text**: AT+BVRA=1 配合文本输入

### 六、车载 HFP HF 角色

车机作为 HF(Hands-Free) 时的代码路径:
- btif_hf_cb[] 数组支持 BTA_AG_MAX_NUM_CLIENTS 个HF连接 [btif_hf.cc L80]
- 车机接收AG(手机)发来的 +CIEV/+CLIP/+RING 通知
- bt_hf_callbacks.PhoneStateChangeCallback / CallStateCallback 传递给上层
- 车机特有的 AT 扩展: AT+BLDN(最后一号重拨)、AT+NREC(降噪控制)

**HF 连接冲突处理** [L439-L459]:
- btif_hf.cc 中检测 incoming/outgoing 连接碰撞
- 同类设备→忽略失败；不同类设备→断开旧连接→上报 disconnect
- Metrics: HFP_COLLISON_AT_AG_OPEN / HFP_COLLISON_AT_CONNECTING 计数器