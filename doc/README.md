# Android 16 车载蓝牙学习资料 · 总入口

> 一套面向车载 Android 工程师的 Android 16 Bluetooth 模块学习教材。
> 起点：会 Android 应用开发、C++ 入门、蓝牙协议零基础。
> 终点：能独立修改 / 调试 Android 蓝牙 Framework + Native 协议栈。

---

## 速通路线

按下列优先级阅读（每章末尾有"上路任务"）：

### P0 必读骨架
1. [00 总览与架构](学习资料/00_总览与架构/) — 蓝牙七层楼模型 + 仓库目录 + 术语速查
2. [02 Framework API 导读](学习资料/02_Framework_API导读/) — `BluetoothAdapter` / `BluetoothDevice` / `BluetoothProfile` / AIDL Binder
3. [03 核心流程](学习资料/03_核心流程/) — 开关 / 扫描 / 配对 / 连接 / 解绑
4. [04 JNI 桥接机制](学习资料/04_JNI桥接机制/) — Java↔Native 双向通路

### P1 车载重点
5. [01 开发与调试准备](学习资料/01_开发与调试准备/) — 编译 / 日志 / adb 速查
6. [06 A2DP 与 AVRCP](学习资料/06_A2DP与AVRCP/) — 蓝牙音乐 + 遥控 + 绝对音量 + 卡顿排查
7. [07 HFP](学习资料/07_HFP/) — 免提电话 + SCO + 通话状态 + Telecom
8. [08 BLE / GATT](学习资料/08_BLE_GATT/) — 扫描 + 连接 + 服务发现 + 车载 AIoT + OTA

### P2 协议栈纵深
9. [05 Native 栈基础](学习资料/05_Native栈基础/) — BTIF / BTA / Stack / GD / HCI / L2CAP / SDP / RFCOMM / SCO

### P3 专题与附录
10. [09 车机互联专题](学习资料/09_车机互联专题/) — HiCar / CarLink / CarPlay 中蓝牙的角色
11. [10 C++ 补课附录](学习资料/10_C++补课附录/) — 智能指针 / RAII / Lambda / 模板 / 状态机 / 消息循环（含 Java 对照）
12. [11 故障排查手册](学习资料/11_故障排查手册/) — 5 步通用方法论 + 典型 case 速查

---

## 配套文档

| 文档 | 用途 |
|------|------|
| [需求.md](需求.md) | 任务定义、读者画像、内容质量与验收标准 |
| [开发计划.md](开发计划.md) | 里程碑、章节拆分、优先级 |
| [开发跟踪记录.md](开发跟踪记录.md) | 当前进度、风险、决策日志 |
| [源码索引.md](源码索引.md) | 顶层目录与各模块入口的"地图" |
| [../CLAUDE.md](../CLAUDE.md) | 长期协作约定，便于任意 AI/人类会话接续 |

---

## 阅读建议

- **每章九段式**：学习目标 → 前置知识 → 场景故事 → 分层调用链 → 源码导读 → 简化代码 → Mermaid 图 → 调试方法 → FAQ。
- **C++ 处必有 Java 对照**：方便 Android 工程师无缝切换思维。
- **车载场景优先**：每个 Profile 章节都会回答"在车机上长什么样、出问题时怎么找"。
- **章末有上路任务**：跑一遍，能力即落地。

---

## 全局术语速记

| 缩写 | 全称 | 一句话 |
|------|------|--------|
| ACL | Asynchronous Connection-Less | 数据链路 |
| SCO/eSCO | Synchronous Connection-Oriented | 语音链路 |
| HCI | Host Controller Interface | Host↔芯片接口 |
| L2CAP | Logical Link Control & Adaptation Protocol | 通道复用 |
| SDP | Service Discovery Protocol | Classic 服务发现 |
| RFCOMM | RF Communication | 串口仿真 |
| GATT | Generic Attribute Profile | BLE 属性/服务模型 |
| SMP | Security Manager Protocol | BLE 配对协议 |
| SSP | Secure Simple Pairing | Classic 现代配对 |
| BTIF / BTA / Stack / GD | — | Native 四层（适配 / 业务 / 协议 / 模块化新栈） |

完整术语见 [00.3 车载场景全景与术语速查](学习资料/00_总览与架构/00.3_车载场景全景与术语速查.md)。

---

## 仓库七处关键入口

读源码从这七个文件入手（详见 [源码索引.md](源码索引.md)）：

1. `framework/java/android/bluetooth/BluetoothAdapter.java` — App Java 入口
2. `android/app/src/com/android/bluetooth/btservice/AdapterService.java` — 蓝牙 App 主进程中枢
3. `android/app/src/com/android/bluetooth/btservice/AdapterNativeInterface.java` — Java→Native 跳板
4. `android/app/jni/com_android_bluetooth_btservice_AdapterService.cpp` — JNI 落点
5. `system/btif/src/btif_dm.cc` — 设备管理入栈点
6. `system/bta/dm/` — 设备管理状态机
7. `system/stack/btm/` — Inquiry / Bond / SCO 底层
