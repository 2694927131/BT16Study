# CLAUDE.md — Android 16 车载蓝牙学习资料项目长期协作约定

> 本文件供任何新启动的 Claude 会话快速接续本仓库的工作。请在动手前先读完。

---

## 1. 项目本质

本仓库是 **Android 16 Bluetooth 模块（packages/modules/Bluetooth 的本地切片）**，用作"源码学习对象"。我们的任务**不是开发蓝牙功能本身，而是生成一套源码学习资料**，让车载 Android 工程师能从零基础成长为可独立修改/调试蓝牙 Framework + Native 协议栈的专家。

读者画像（永远对齐这个）：
- 会写 Java/Kotlin Android 应用；
- C++ 仅入门（认识语法，不熟 RAII / 智能指针 / 模板 / Lambda / 状态机）；
- 蓝牙协议零基础；
- 工作场景为车载 IVI（A2DP 蓝牙音乐、HFP 蓝牙电话、BLE 外设、HiCar/CarLink/CarPlay 蓝牙辅助链路）。

---

## 2. 关键文档（动手前必看）

| 文档 | 用途 |
|------|------|
| `doc/需求.md`（v1.1） | 任务定义、读者画像、内容质量与验收标准 |
| `doc/开发计划.md` | 章节拆分、里程碑、优先级 P0→P3、章节交付清单 |
| `doc/开发跟踪记录.md` | 当前进度、风险、决策日志、下一步 |
| `doc/源码索引.md` | 顶层目录与各模块入口的"地图" |
| `doc/学习资料/` | 主交付物，按章节拆分的 Markdown 教材 |

**每次开工的第一步**：读 `doc/开发跟踪记录.md` "进行中" 和 "下一步"，确认起点。

---

## 3. 目录约定

```
Bluetooth/
├── doc/
│   ├── 需求.md
│   ├── 开发计划.md
│   ├── 开发跟踪记录.md
│   ├── 源码索引.md
│   └── 学习资料/
│       ├── 00_总览与架构/
│       ├── 01_开发与调试准备/
│       ├── 02_Framework_API导读/
│       ├── 03_核心流程/
│       ├── 04_JNI桥接机制/
│       ├── 05_Native栈基础/
│       ├── 06_A2DP与AVRCP/
│       ├── 07_HFP/
│       ├── 08_BLE_GATT/
│       ├── 09_车机互联专题/
│       ├── 10_C++补课附录/
│       └── 11_故障排查手册/
├── framework/   # Java 公开 API（只读，不能改）
├── service/     # Kotlin 系统服务（只读）
├── android/     # 蓝牙 App + JNI（只读）
├── system/      # Native 栈（btif / bta / stack / gd 等，只读）
├── flags/       # aconfig flag（只读）
├── sysprop/     # 系统属性（只读）
└── CLAUDE.md    # 本文件
```

**重要：除 `doc/` 外，其余目录是被学习的源码，禁止修改。**

---

## 4. 工作流约定（强制）

### 4.1 章节九段式模板（不可省略任何一段）
1. 学习目标
2. 前置知识
3. 场景故事（车载视角）
4. 分层调用链（API → Service → JNI → BTIF → BTA → Stack）
5. 源码导读（真实 `path:line` + 阅读顺序）
6. 简化代码片段（保留行号、附通俗注释）
7. Mermaid 流程图/时序图
8. 调试方法（日志 tag、adb、dumpsys、btsnoop）
9. FAQ + 上路任务

### 4.2 事实纪律
- **不得伪造**任何源码路径、行号、函数名。引用前先 `Grep`/`Read` 验证。
- 外部依赖（system_server、Settings App、HAL、厂商互联实现等）必须明确标"外部依赖"并尽量给 AOSP 官方路径。
- 涉及 aconfig flag 的行为差异：必须列出 flag 名与默认值。

### 4.3 C++/Java 双语对照（凡涉及必给）
讲到这些 C++ 概念时，必须给出 Java/Kotlin 类比：
- 智能指针 ↔ Java 强引用 / `AutoCloseable`
- RAII / 析构 ↔ `try-with-resources` / `finally`
- Lambda + `std::function` ↔ Java Lambda + `Runnable`/`Consumer`
- `std::mutex` / `std::lock_guard` ↔ `synchronized` / `ReentrantLock`
- template ↔ Java 泛型（含差异）
- 状态机 ↔ Android `StateMachine`

### 4.4 提交粒度（强制）
**每完成一个小节的 `.md` 文件或章节级修改 → 立即 `git commit` 一次。**

提交信息格式：
```
docs(学习资料): 完成 <编号> <章节名>
```
例：
```
docs(学习资料): 完成 02.1 BluetoothAdapter 章节
docs(规划): 优化需求 v1.1，新增开发计划与跟踪记录
```

每次提交前必须更新 `doc/开发跟踪记录.md` 反映该章节状态（⬜→🟡→✅）。

### 4.5 路径规范
- 所有文档内引用源码路径必须用**仓库相对路径**（`framework/java/...`），**不写绝对 Windows 路径**。
- 文档之间用 Markdown 相对链接互引。

### 4.6 语言
- 所有对话、文档、注释一律**中文**（全局指令）。
- 代码注释中文优先，但保留必要的英文术语（HCI / L2CAP / GATT 等）。

---

## 5. 优先级（按此顺序推进）

1. **P0**：00 总览、02 Framework API、03 核心流程、04 JNI 桥接。
2. **P1**：06 A2DP/AVRCP、07 HFP、08 BLE/GATT、01 调试准备。
3. **P2**：05 Native 栈基础（BTIF→BTA→Stack→GD 顺序）。
4. **P3**：09 车机互联、10 C++ 附录、11 故障排查。

策略：**骨架先行，深度后补**。先把每章的"速通摘要 + 调用链 + Mermaid"建立起来，再回过头来逐节填充深度内容。

---

## 6. 工具使用约定

- 大范围探查（"哪里实现了 X"）：用 `Grep`、`Glob`、`Explore` 子代理。
- 精确读特定文件：直接 `Read`（不要 `cat`）。
- 编辑已有文档：用 `Edit`（不要全文重写）。
- 新建文件：`Write`。
- 路径分隔符：本机是 Windows，但 shell 是 bash → 使用 `/` 而非 `\`。

---

## 7. 学习资料质量底线（任何一条都不能破）

| 底线 | 含义 |
|------|------|
| 真实源码 | 每条 `path:line` 必须 grep 可查到 |
| 一图一链 | 每章至少 1 张 Mermaid 图、1 条端到端调用链 |
| 三层映射 | Profile 章节必须含 Java Service / JNI / Native 入口三层 |
| 双语对照 | C++ 高级特性出现处必须有 Java 类比 |
| 章末任务 | 章末必须给"上路任务"，可在源码里实际完成 |
| 小步提交 | 每小节一个 commit |

---

## 8. 接续步骤模板（新会话来了照着做）

1. 读本文件（CLAUDE.md）。
2. 读 `doc/开发跟踪记录.md`，找到"进行中"或"下一步"。
3. 读对应章节的现有内容（如有）。
4. 启动 TaskCreate 把这一小节登记为当前任务。
5. 写或改。
6. 更新 `doc/开发跟踪记录.md`。
7. `git add` 相关文件 → `git commit`，commit message 形如 `docs(学习资料): 完成 02.1 BluetoothAdapter 章节`。
8. 进入下一节。

---

## 9. 术语速查（详见 `doc/学习资料/00_总览与架构/00.3_车载场景全景与术语速查.md`）

- **Adapter**：蓝牙总控（开关、扫描、可发现、地址等）。
- **Profile**：上层应用协议族（A2DP、HFP、HID、GATT 等）。
- **ACL**：Asynchronous Connection-Less，承载数据的链路。
- **SCO/eSCO**：Synchronous Connection-Oriented，承载语音的链路（HFP 通话）。
- **HCI**：Host Controller Interface，主控 ↔ 芯片之间的命令/事件接口。
- **L2CAP**：Logical Link Control and Adaptation Protocol，逻辑通道与多路复用。
- **SDP**：Service Discovery Protocol，Classic 服务发现。
- **GATT**：Generic Attribute Profile，BLE 上的属性/服务/特征模型。
- **BTIF / BTA / Stack / GD**：Android 蓝牙 Native 四大分层（详见 `doc/源码索引.md`）。

---

## 10. 我（Claude）需要谨记

- 不夸大、不编造、不脑补不存在的函数。
- 不修改 `doc/` 以外的目录。
- 不一次性塞一个超长章节，**按小节切分**，每小节一次提交。
- 写完每节先回读自查九段式是否齐全、源码引用是否可查。
- 进度永远反映在 `doc/开发跟踪记录.md`。
