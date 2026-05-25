# B.2 Bluetooth SIG Qualification 流程

> **速通摘要**：**Bluetooth Qualification（蓝牙合格认证）**是 Bluetooth SIG 规定的产品上市前必经流程。任何贴有"Bluetooth"商标的产品都必须先通过 Qualification 拿到 **QDID（Qualified Design ID）**，并在 SIG 网站登记 **Product Declaration**。本附录梳理：① QDID 的本质；② 三种 Qualification 路径（End Product / Component / Profile Subsystem）；③ Listing 流程（声明、年费、违规罚则）；④ 车机蓝牙的常见 Qualification 策略；⑤ 与 PTS（Profile Tuning Suite）测试的关系。

---

## 一、为什么需要 Qualification

```
┌─────────────────────────────────────────────────┐
│ 任何产品标注"Bluetooth"商标 / 用蓝牙射频       │
│              │                                  │
│              ▼  必须先做                         │
│ ┌─────────────────────────────────────────────┐ │
│ │ Bluetooth SIG Qualification（合格认证）      │ │
│ │   ├── 通过 PTS 测试（功能符合 spec）         │ │
│ │   ├── 在 SIG 网站登记 QDID                   │ │
│ │   └── 缴纳 Listing 费                        │ │
│ └─────────────────────────────────────────────┘ │
│              │                                  │
│              ▼ 否则                              │
│ ┌─────────────────────────────────────────────┐ │
│ │ 违反 SIG 商标使用条款                        │ │
│ │   - 失去蓝牙商标使用权                       │ │
│ │   - 可能面临法律诉讼与高额赔款              │ │
│ │   - Apple/Google 等大厂会拒绝该产品集成     │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

官方入口：`https://www.bluetooth.com/develop-with-bluetooth/qualification-listing/`

---

## 二、Qualification 三层结构

蓝牙 Qualification 允许"分层认证、复用 QDID"，避免每个产品都从零开始测一遍。

### 2.1 End Product（终端产品）
- 最终消费品（车机、手机、耳机、智能锁）
- 必须有 EPL（End Product Listing），可复用下层组件 QDID
- 例：某车机 EPL = 高通芯片 QDID + AOSP 主机栈 QDID + 自家 Profile 测试

### 2.2 Component（组件/子系统）
- 蓝牙芯片（高通 QCA, MTK, Cypress）+ 控制器固件
- 主机栈（AOSP Bluetooth、自研 Stack）
- 一个 Component 可被多个 End Product 引用

### 2.3 Profile Subsystem（Profile 子系统）
- 某个 Profile 的独立实现，如 A2DP Source、HFP HF
- 用于"我们只做 Profile 卖给客户"的中间方案商

```
车机 End Product Listing（QDID = E_xxx）
   │
   ├── 引用：高通 QCA6595 蓝牙芯片 QDID = C_yyy
   ├── 引用：AOSP Android 16 蓝牙主机栈 QDID = C_zzz
   └── 自测 + 声明 Profile 实现（A2DP Sink / HFP HF / GATT 等）
```

---

## 三、Qualification 完整流程（end-to-end）

### Step 1：选定 SIG 会员等级
- **Adopter**（免费）：可使用 SIG 规范、贴蓝牙商标，但**不能投票**
- **Associate**（约 $7,500/年）：参与工作组，影响规范制定
- **Promoter**（最高级，仅 SIG 创始成员）

车机 OEM 通常是 Associate。

### Step 2：选择 Qualification 路径
- 全自己做（Component + EPL 都自己）
- 复用现成 Component（更省时间和钱）
- 仅做 EPL（最常见，复用芯片商和 AOSP 的 QDID）

### Step 3：注册 QDID 项目
登录 `launchstudio.bluetooth.com`：
1. 选择 ICS（Implementation Conformance Statement）—— 自己实现了哪些 Profile/特性
2. 系统据此生成测试套件清单

### Step 4：执行 PTS 测试
- **PTS（Profile Tuning Suite）**：SIG 官方测试工具，运行在 Windows
- 工具会模拟手机/耳机/电脑对车机发各种合法/非法报文，检查实现是否符合 spec
- 通过率 100%（不允许漏测）

参考工具：
- PTS 软件：从 SIG 网站下载
- USB Dongle：CSR Dev Kit、Nordic dev kit
- 自动化：Pandora（本仓库 `pandora/server/` 有 Android 接口）

### Step 5：提交报告
- PTS 输出 `.pts.zip` 报告
- 上传到 Launch Studio
- 缴纳 Listing 费（约 $4,000-$8,000 / QDID，与会员等级和产品类型相关）

### Step 6：审核与公示
- SIG 审核 1-4 周
- 通过后获得 QDID
- 信息在 `https://launchstudio.bluetooth.com/Listings/Search` 公开

### Step 7：贴蓝牙商标 + 出货

---

## 四、车机典型 Qualification 策略

```
车机厂商                           QDID 来源
────────────────────────────────────────────────
高通 QCA6595 芯片  ──────►        高通自有 QDID
                                        │ Component
                                        ▼
AOSP Android 16 主机栈 ──────►   Google QDID（公开复用）
                                        │ Component
                                        ▼
车机自有定制：                    自家 EPL（QDID）
  - A2DP Sink + AVRCP CT          - 引用上面两个 Component
  - HFP HF                        - 测自家 Profile 实现
  - PBAP/MAP Client               - 测端到端集成
  - BLE Scanner                   - 通过 PTS
  - Channel Sounding（若有）
```

**好处**：
- 主机栈复用 Google QDID，省时间（车机 OEM 只需测自家 Profile 集成）
- 一个 EPL 可对应多款车型（同芯片同栈复用同 EPL）

---

## 五、Listing 公开搜索

`https://launchstudio.bluetooth.com/Listings/Search` 可以查任何已通过的 QDID。

例：搜索 "Android 16" 可以看到 Google 提交的主机栈 QDID。

公开字段：
- QDID 编号
- 厂商名称
- 产品名/型号
- 蓝牙规范版本（4.2 / 5.0 / 5.3 / 5.4 / 6.0）
- 支持的 Profile 列表
- Listing 日期

---

## 六、年费与维护

- **Annual Listing Fee**：每 QDID 每年约 $4,000-$8,000
- **Spec 升级**：BLE 5.4 出新时，旧 QDID 仍有效但不能声称新特性。新加特性需要 Re-Qualification
- **退市**：产品停产后可申请退市，停止年费

---

## 七、PTS 测试的实操要点

### 7.1 PTS 环境

```
┌─────────────────────────┐         ┌─────────────────────────┐
│ Windows PC（PTS Host）  │         │ DUT（被测车机）          │
│  ┌─────────────────┐   │  USB    │                         │
│  │ PTS Software    │◄──┼─────────┤ 蓝牙芯片                │
│  │  + Test Cases   │   │ Dongle  │                         │
│  └─────────────────┘   │         └─────────────────────────┘
│            │            │
│            ▼            │
│  生成测试报告 .pts.zip   │
└─────────────────────────┘
```

### 7.2 PTS 常见测试用例

- **A2DP Sink TC**：发送各种 SBC 帧（合法/非法/边界）测车机解码
- **AVRCP CT TC**：发送 PASS_THROUGH 命令，测响应
- **HFP HF TC**：发送各种 AT 命令，测车机解析（包括异常情况）
- **GATT Client TC**：模拟 GATT Server 发各种 ATT 错误码
- **SMP TC**：模拟各种配对密钥的攻击场景

### 7.3 自动化集成

车机 CI 中跑 Bumble + Pandora 模拟 PTS 部分测试，提前发现问题（详见 [20.3 Bumble + 自动化](../20_测试与CTS/20.3_Bumble与自动化.md)）。Bumble 不能替代 PTS，但能极大降低正式 PTS 测试的迭代次数。

---

## 八、Qualification 与 CDD/CCC 的关系

```
┌───────────────────────────────────────────┐
│ Bluetooth SIG Qualification               │ ← 全球任何蓝牙产品都必经
│   - QDID 注册                              │
│   - 通过 PTS                               │
└───────────────────────────────────────────┘
              │  (必经)
              ▼
┌───────────────────────────────────────────┐
│ Android CDD（见 B.1）                     │ ← Android 设备额外
│   - 通过 CTS                              │
│   - 满足 7.4.3 蓝牙要求                   │
└───────────────────────────────────────────┘
              │  (Android 设备必经)
              ▼
┌───────────────────────────────────────────┐
│ CCC Digital Key（若做数字车钥匙）         │ ← 车机特有
│   - 通过 CCC 测试                          │
│   - 加入 Car Connectivity Consortium      │
└───────────────────────────────────────────┘
              │  (车钥匙场景必经)
              ▼
出货
```

---

## 九、违规案例与教训

### 案例 1：贴蓝牙 logo 但未注册 QDID
- **2019 年某 IoT 厂商**：在卖出 50 万台智能插座后被 SIG 警告，最终补登 QDID 并支付滞纳金
- **后果**：补缴年费 + 法律费用，约 $50,000

### 案例 2：声称支持但实际未通过 PTS
- **某车机厂商**：声称支持 A2DP 1.4 Browsing，但 PTS 未通过该项
- **后果**：SIG 撤销 QDID，必须重新测试

### 案例 3：芯片 QDID 与 EPL 不匹配
- 车机使用了未列在自家 EPL 引用清单的芯片版本（如固件升级后没更新 EPL）
- **后果**：EPL 失效，需要重新提交

---

## 十、关键资源

| 资源 | 链接 |
|------|------|
| SIG Qualification 入口 | `https://www.bluetooth.com/develop-with-bluetooth/qualification-listing/` |
| Launch Studio（提交 QDID）| `https://launchstudio.bluetooth.com/` |
| 已注册 QDID 公开查询 | `https://launchstudio.bluetooth.com/Listings/Search` |
| Bluetooth Core Spec 下载 | `https://www.bluetooth.com/specifications/specs/` |
| PTS 下载与使用 | `https://www.bluetooth.com/develop-with-bluetooth/qualification-listing/qualification-test-tools/profile-tuning-suite/` |
| Bumble（开源 PTS 替代）| `https://github.com/google/bumble` |
| Pandora（Android 蓝牙测试桥）| `https://github.com/google/bt-test-interfaces` |

---

## FAQ

**Q1：每款新车型都要重新 Qualification 吗？**
**不一定**。如果芯片、主机栈、Profile 实现都相同（只是外观/品牌不同），可以共用一个 EPL。但只要任一组件（芯片、栈版本、Profile 行为）变化，就要新 EPL。车机集团（如丰田下面多个品牌）常用此策略。

**Q2：AOSP 蓝牙栈有 QDID 吗？**
**有**。Google 为每个 Android 版本提交了主机栈 QDID（如 Android 16），车机 OEM 可以**直接引用**这个 QDID 而不用自己重测主机栈核心功能。但**自家定制的 Profile 行为**（如车机 PBAP Client 的解析逻辑）仍需通过 PTS。

**Q3：Channel Sounding 是单独的 Qualification 项吗？**
是的，**BLE 5.4 Channel Sounding**作为 Core 6.0 新增特性，有独立的 PTS 测试集。声称支持 CS 的产品必须通过这部分 PTS。CDD（B.1）只是"推荐"，但 SIG 是"必通过 PTS 才能贴 BLE 5.4 商标"。

**Q4：Qualification 费用大约多少？**
- 会员年费（Associate）：$7,500
- Listing 费：$4,000-$8,000/QDID
- PTS 工具：免费（SIG 会员可下载）
- 第三方测试服务（如 Bureau Veritas）：$15,000-$30,000/项目
- 总成本：一款车机首次 Qualification 约 **$30,000-$80,000**

---

## 上路任务

1. 在 `https://launchstudio.bluetooth.com/Listings/Search` 搜索自家芯片商（如"Qualcomm QCA6595"），看其 QDID 引用了哪些 Component，理解整个引用链。
2. 下载 Bumble，跑一次 A2DP Source 模拟测试，让车机做 Sink，模拟"PTS 测试预演"的过程。
3. 整理一份"自家车机 Qualification 状态报告"：当前用的芯片 QDID、主机栈 QDID（Google 的 Android 16）、自家 EPL QDID，列出有效期与到期时间。
