# A.1 完整 AT 命令参考

> **速通摘要**：HFP（Hands-Free Profile）使用 ASCII 文本 **AT 命令**在 AG（车机）与 HF（手机/耳机）之间交换电话状态、铃声、CLIP、通话控制、Codec 协商等信息。AT 命令通过 RFCOMM 通道传输。本附录按照"功能分组"列出 HFP 1.9 中实际使用的 AT 命令，每条给出方向（AG→HF / HF→AG）、含义、典型示例、本仓库对应处理函数（`bta_hf_client_handle_*` 或 `bta_ag_*`）。

---

## 一、连接初始化（必经流程）

| AT 命令 | 方向 | 作用 | 示例 |
|---------|------|------|------|
| `AT+BRSF=<feat>` | HF→AG | HF 报告自身支持的特性位图（Bluetooth Retrieve Supported Features）| `AT+BRSF=4095` |
| `+BRSF: <feat>` | AG→HF | AG 回报自身特性位图 | `+BRSF: 1023` |
| `AT+CIND=?` | HF→AG | 查询 indicator 列表（call/callsetup/service/signal/roam/battchg）| `AT+CIND=?` |
| `+CIND: (...)` | AG→HF | AG 返回 indicator 定义 | `+CIND: ("call",(0,1)),("service",(0,1)),...` |
| `AT+CIND?` | HF→AG | 查询当前 indicator 取值 | `AT+CIND?` |
| `+CIND: <vals>` | AG→HF | 返回各 indicator 当前值 | `+CIND: 0,0,1,5,0,3` |
| `AT+CMER=3,0,0,1` | HF→AG | 启用 indicator 事件通知 | 固定形式 |
| `AT+CHLD=?` | HF→AG | 查询通话保持/多方通话能力 | — |
| `+CHLD: (0,1,2,3)` | AG→HF | 返回支持的 CHLD 子功能 | — |

> **处理入口（HF Client 侧）**：
> - `bta_hf_client_handle_brsf` — `system/bta/hf_client/bta_hf_client_at.cc:357`
> - `bta_hf_client_handle_cind_list_item` — `system/bta/hf_client/bta_hf_client_at.cc:364`
> - `bta_hf_client_handle_cind_value` — `system/bta/hf_client/bta_hf_client_at.cc:397`
> - `bta_hf_client_handle_chld` — `system/bta/hf_client/bta_hf_client_at.cc:428`

---

## 二、Indicator 状态变化

| AT 命令 | 方向 | 作用 | 示例 |
|---------|------|------|------|
| `+CIEV: <idx>,<val>` | AG→HF | indicator 取值变化通知（来电时 call=1，铃响时 callsetup=1）| `+CIEV: 1,1` |
| `+CIEV: <idx>,<val>` | AG→HF | 信号强度变化 | `+CIEV: 4,3` |

> **处理**：`bta_hf_client_handle_ciev` — `system/bta/hf_client/bta_hf_client_at.cc:452`

---

## 三、来电号码（CLIP / CCWA / CLCC）

| AT 命令 | 方向 | 作用 | 示例 |
|---------|------|------|------|
| `AT+CLIP=1` | HF→AG | 启用 CLIP（来电号码显示）| — |
| `+CLIP: "<num>",<type>` | AG→HF | 来电时通知号码 | `+CLIP: "13800138000",129` |
| `AT+CCWA=1` | HF→AG | 启用 Call Waiting 通知 | — |
| `+CCWA: "<num>",<type>` | AG→HF | 三方来电号码 | `+CCWA: "13900139000",129` |
| `AT+CLCC` | HF→AG | 查询当前通话列表 | — |
| `+CLCC: <idx>,<dir>,<state>,<mode>,<mpty>,<num>,<type>` | AG→HF | 通话条目 | `+CLCC: 1,1,0,0,0,"13800138000",129` |

> **处理**：`bta_hf_client_handle_clip` — `system/bta/hf_client/bta_hf_client_at.cc:553`

---

## 四、通话控制（HF 主动）

| AT 命令 | 方向 | 作用 |
|---------|------|------|
| `ATA` | HF→AG | 接听来电 |
| `AT+CHUP` | HF→AG | 挂断电话 |
| `ATD<num>;` | HF→AG | 拨号（注意末尾分号表示语音呼叫）|
| `ATD>1;` | HF→AG | 拨打内存第 1 条（语音拨号 memory）|
| `AT+BLDN` | HF→AG | 重拨上次号码（Last Dialed Number）|
| `AT+CHLD=<n>` | HF→AG | 通话保持/切换/合并（0=挂断保持的、1=挂断当前接听保持、2=切换、3=合并三方）|

---

## 五、音量同步（HSP/HFP）

| AT 命令 | 方向 | 作用 | 示例 |
|---------|------|------|------|
| `AT+VGS=<n>` | 双向 | Speaker Gain（0-15）| `AT+VGS=7` |
| `AT+VGM=<n>` | 双向 | Mic Gain（0-15）| `AT+VGM=10` |

---

## 六、Codec 协商（HFP 1.6+，mSBC / LC3-SWB）

| AT 命令 | 方向 | 作用 | 示例 |
|---------|------|------|------|
| `AT+BAC=<list>` | HF→AG | HF 支持的 Codec 列表（1=CVSD, 2=mSBC, 3=LC3-SWB）| `AT+BAC=1,2,3` |
| `+BCS: <id>` | AG→HF | AG 选定的 Codec | `+BCS: 2` |
| `AT+BCS=<id>` | HF→AG | 确认接受 Codec | `AT+BCS=2` |
| `AT+BCC` | HF→AG | HF 请求 Codec Connection（即触发 SCO 建立）| — |

> **处理**：`bta_hf_client_handle_bcs` — `system/bta/hf_client/bta_hf_client_at.cc:490`

---

## 七、HF Indicator 扩展（HFP 1.7+）

| AT 命令 | 方向 | 作用 |
|---------|------|------|
| `AT+BIND=<list>` | HF→AG | HF 报告支持的 HF Indicator 列表（1=Enhanced Safety, 2=Battery）|
| `AT+BIND=?` | HF→AG | 查询 AG 支持的 indicator |
| `+BIND: <id>,<state>` | AG→HF | AG 返回 indicator 启用状态 |
| `AT+BIEV=<id>,<val>` | HF→AG | HF 上报 indicator 值（如电池电量 0-100）| `AT+BIEV=2,75` |

> **处理**：`bta_hf_client_handle_bind_read_supported_ind` — `system/bta/hf_client/bta_hf_client_at.cc:434`
> `bta_hf_client_handle_bind_read_enabled_ind` — `bta_hf_client_at.cc:441`

---

## 八、语音识别（VR / BVRA）

| AT 命令 | 方向 | 作用 | 示例 |
|---------|------|------|------|
| `AT+BVRA=1` | HF→AG | HF 请求开启语音识别（按下方向盘"小爱同学"键）| — |
| `+BVRA: <state>` | AG→HF | AG 通知 VR 状态变化 | `+BVRA: 1` |

> **处理**：`bta_hf_client_handle_bvra` — `system/bta/hf_client/bta_hf_client_at.cc:543`

---

## 九、网络运营商与 SIM

| AT 命令 | 方向 | 作用 |
|---------|------|------|
| `AT+COPS=3,0` | HF→AG | 选择运营商名称显示格式（长名称）|
| `AT+COPS?` | HF→AG | 查询当前运营商 |
| `+COPS: 0,0,"<name>"` | AG→HF | 返回运营商名 |
| `AT+CNUM` | HF→AG | 查询本机号码 |
| `+CNUM: ,,"<num>",<type>,,4` | AG→HF | 返回本机号码 |

---

## 十、错误与回应

| 响应 | 含义 |
|------|------|
| `OK` | 成功 |
| `ERROR` | 通用错误 |
| `+CME ERROR: <code>` | 扩展错误（0=AG failure, 1=no connection to phone, 3=operation not allowed, 4=operation not supported, …）|
| `RING` | 来电响铃（AG→HF）|

---

## 十一、车机调试常用 logcat 过滤

```bash
# AG 侧（车机大多是 HF 角色，但若车机做 AG 用这些）
adb logcat -s bt_btif_hf:V bt_bta_ag:V

# HF Client 侧（车机更常见）
adb logcat -s bt_btif_hfp_client:V bt_bta_hf_client:V

# 抓 RFCOMM 帧内的 AT 文本（btsnoop 转 Wireshark）
# filter: rfcomm.dlci == <hf_dlci> && data.text contains "AT+"
```

---

## 十二、车机典型 AT 流水（来电场景）

```
HF (车机)                          AG (手机)
   ──── ATA ───────────────────────►       (接听)
   ◄─── OK ──────────────────────────
   ◄─── +CIEV: 1,1 ──────────────────       (call=1)
   ◄─── +CIEV: 2,0 ──────────────────       (callsetup=0)
   ─── AT+BCC ──────────────────────►       (请求 SCO)
   ◄─── OK ──────────────────────────
   ◄─── +BCS: 2 ────────────────────         (AG 选 mSBC)
   ─── AT+BCS=2 ─────────────────────►       (确认)
   ◄─── OK ──────────────────────────
   ◄═══ SCO 通道建立（HCI Setup_Synch_Conn）═══►

通话进行中 …

   ─── AT+CHUP ─────────────────────►       (挂断)
   ◄─── OK ──────────────────────────
   ◄─── +CIEV: 1,0 ──────────────────       (call=0)
```

---

## FAQ

**Q1：为什么 `AT+CMER=3,0,0,1` 是固定形式？**
HFP 规格强制：mode=3（连续上报）、keyp=0、disp=0、ind=1（启用 indicator 事件）。其他 mode 在 HFP 上下文里没有意义，所以约定俗成。

**Q2：AT 命令是文本协议，如果半包/粘包怎么办？**
RFCOMM 是基于流的，AT 命令以 `\r\n` 分隔。`bta_hf_client_at.cc` 内部维护一个解析缓冲，每次 RFCOMM 数据到达后扫描完整的 `\r\n` 分隔的命令再解析。

**Q3：mSBC 与 CVSD 在 AT 层是怎么协商的？**
AG 通过 `+BCS: 2`（2=mSBC）发起；HF 用 `AT+BCS=2` 确认；之后 AG 发起 SCO 建立时用 mSBC 编码参数（HCI Enhanced Setup Synchronous Connection 命令）。CVSD（id=1）是兜底，所有 HFP 设备必须支持。

---

## 上路任务

1. 在车机端开启 HFP Client 调试日志（`bt_bta_hf_client:V`），打一次来电并接听，把所有 AT 命令按时间顺序整理一份完整流程图。
2. 阅读 `bta_hf_client_at.cc` 中三个核心处理函数（`brsf`、`cind`、`ciev`），理解它们是如何把 ASCII 字符串解析成内部状态机事件的。
3. 思考：如果某款手机不支持 `AT+BIND`（HF Indicator），车机会怎么 fallback？查看 `bta_hf_client_handle_bind_read_supported_ind` 中的 fallback 路径。
