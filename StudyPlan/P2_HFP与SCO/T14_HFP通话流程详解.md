# T14_HFP通话流程详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. 来电: +RING/+CLIP→车机显示→ATA→SCO建链→BTA_AG_SCO_OPENING_ST→通话建立
2. 拨号: ATD<number>;→手机拨号→+CLCC更新→SCO→bta_ag_sco_open()→通话建立
3. 挂断: AT+CHUP→SCO断开→BTA_AG_SCO_CLOSING_ST→通话结束
4. CHLD操作: 0释放保持/1释放活动接保持/2保持活动接保持/3合并会议，bt_hf.h 定义 bthf_chld_type_t
5. 通话状态同步: +CIEV(call=1/callsetup=1-3/callheld=0-2)→phoneStateChanged+callStateChanged 两个回调

## 详细笔记

### 一、来电流程

```
AT命令交互时序:

AG(手机)                         HF(车机)
  │                                │
  │ ─── +CIEV: callsetup=1 ────→ │  来电(未振铃)
  │ ─── +CLIP: "13800138000" ──→ │  来电号码
  │ ─── +RING ──────────────────→ │  振铃指示
  │                                │  ATA (接听命令)
  │ ←──  ATA ────────────────────│
  │ ───  OK ─────────────────────→ │  接听确认
  │                                │  SCO 建链开始
  │ ─── +CIEV: callsetup=0 ─────→ │  来电结束
  │ ─── +CIEV: call=1 ──────────→ │  通话中
  │ ─── +CIEV: callsetup=0 ─────→ │
  │     [BTA_AG_SCO_OPEN_EVT]      │  eSCO/SCO 建立
  │                                │  音频通路建立
  │ ───  Audio ───────────────────│  通话音频
```

**代码追踪 [btif_hf.cc → bta_ag_act.cc]**:
```
btif_hf_handle_event(BTA_AG_AT_CIEV_EVT)
→ bta_ag_at_cind_result() → 解析 +CIEV: <ind>,<val>
→ bta_ag_call_state_change() → 更新 call/callsetup/callheld
→ 触发 bt_hf_callbacks.PhoneStateChangeCallback(call_state)
→ bt_hf_callbacks.CallStateCallback(call_type, ...)
```

**ATA 链路**: App→btif_hf.answercall()→BTA_AgAnswer()→RFCOMM发送ATA→AG接听→SCO建链

### 二、拨号流程

```
HF(车机)                         AG(手机)
  │ ─── ATD13800138000; ───────→ │  拨号命令
  │ ←── OK ───────────────────── │  确认
  │ ─── +CIEV: callsetup=2 ────→ │  拨号中
  │ ─── +CIEV: callsetup=3 ────→ │  被叫振铃
  │ ─── +CIEV: call=1 ─────────→ │  通话开始
  │     SCO 建链                   │
  │ ─── Audio ─────────────────── │  通话音频
```

**代码链路**: btif_hf.dialcall()→BTA_AgResult(BTA_AG_SPK_RES)→RFCOMM发送ATD→解析OK

### 三、挂断流程

```
HF(车机)                         AG(手机)
  │ ─── AT+CHUP ─────────────→ │
  │ ←── OK ───────────────────── │
  │ ─── +CIEV: call=0 ─────────→ │  通话结束
  │ ─── +CIEV: callsetup=0 ────→ │
  │     SCO 断开                   │
  │  BTA_AG_SCO_CLOSING_ST
  │ → BTA_AG_SCO_SHUTTING_ST
  │ → BTA_AG_SCO_SHUTDOWN_ST
```

**代码链路**: btif_hf.hangupcall()→BTA_AgResult(BTA_AG_END_RES)→AT+CHUP

### 四、三方通话 (CHLD)

**bthf_chld_type_t** [bt_hf.h L63-L71]:
```
BTHF_CHLD_TYPE_RELEASEHELD = 0               // AT+CHLD=0: 释放所有保持的呼叫
BTHF_CHLD_TYPE_RELEASEACTIVE_ACCEPTHELD = 1  // AT+CHLD=1: 释放活动呼叫，接保持呼叫
BTHF_CHLD_TYPE_HOLDACTIVE_ACCEPTHELD = 2     // AT+CHLD=2: 保持活动呼叫，接保持呼叫
BTHF_CHLD_TYPE_ADDHELDTOCONF = 3             // AT+CHLD=3: 将所有保持呼叫加入会议
```

**典型三方通话场景**:
```
初始: 通话A进行中(call=1, callheld=0)
来电B: +CCWA: "caller_B"→callsetup=1(call_waiting)
→ AT+CHLD=2 → 通话A保持(callheld=1)+接通B(call=1)
→ AT+CHLD=3 → 三人会议(call=1, callheld=0)
→ AT+CHLD=1 → 结束当前会议，恢复A
```

### 五、语音识别

**AT+BVRA 命令**:
- `AT+BVRA=1` → 启动语音识别 → AG返回+BVRA:1→bt_hf_callbacks.VrStateCallback(STARTED)
- `AT+BVRA=0` → 停止语音识别 → +BVRA:0→VrStateCallback(STOPPED)
- VR_ENHANCED: 支持文本识别结果的增强语音识别
- 集成车载语音助手需要 HFP 与 AudioManager/MIC 权限协调

### 六、通话状态管理

**+CIEV 指示器映射** [bt_hf.h L100+]:
| 指示器ID | 含义 | 可能值 | 回调 |
|----------|------|--------|------|
| call(1) | 是否有通话 | 0/1 | PhoneStateChangeCallback |
| callsetup(2) | 呼叫建立状态 | 0(none)/1(incoming)/2(dialing)/3(alerting) | PhoneStateChangeCallback |
| callheld(3) | 呼叫保持 | 0/1/2 | PhoneStateChangeCallback |
| service(4) | 服务可用 | 0/1 | NetworkStateCallback |
| signal(5) | 信号强度 | 0-5 | NetworkStateCallback |
| roam(6) | 漫游 | 0/1 | NetworkStateCallback |
| battchg(7) | 电池 | 0-5 | hf_indicator_callback |

**+CLCC 查询**:
- AT+CLCC → 返回当前通话列表
- 每行: +CLCC: <idx>,<dir>,<status>,<mode>,<mpty>,<number>,<type>[,<alpha>]
- 车机据此显示精确通话列表