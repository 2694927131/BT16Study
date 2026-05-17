# 蓝牙 Framework 架构地图与定向代码阅读计划

日期：2026-05-17

## 1. 是否有必要新增

有必要新增，但需要精简执行。

现有资料已经覆盖开关、JNI、Native、A2DP、HFP、BLE/GATT、故障排查和成长路线，适合入门和专题学习；但用户新增的两个需求更偏“源码作战地图”和“定向代码阅读报告”，目标是让读者在真实定制或故障现场可以快速回答：

- 入口在哪里。
- Binder 边界在哪里。
- Java 到 JNI、Native、Vendor 的链路在哪里断。
- 哪个线程处理，哪个回调分发，哪里可能被权限、AppOps、状态机或锁挡住。
- 看 logcat、dumpsys、bugreport 时应该先看什么。

因此新增内容不应替代原章节，而应作为更高密度的源码地图层，反向服务 `02-基础功能链路.md`、`03-JNI桥接与回调.md`、`07-BLE_GATT与AIoT.md`、`10-故障排查手册.md` 和 `96-成长路线与实战任务.md`。

## 2. 精简后的交付范围

### 2.1 保留的核心交付

1. 新增 `11-蓝牙Framework架构地图.md`。
   - 覆盖从开机到 `BluetoothAdapter` 可用的启动链路。
   - 覆盖 App API -> Framework -> Service -> JNI -> Native -> Vendor 的分层调用路径。
   - 覆盖 BLE Scan/Connect/GATT、Pairing、Profile 的关键类图、状态机、线程模型、dumpsys 和高频坑。

2. 新增定向代码阅读报告系列，按用户优先级执行。
   - `12-定向代码阅读报告-BLE-Scan.md`
   - `13-定向代码阅读报告-BLE-Connect.md`
   - `14-定向代码阅读报告-Pairing-Bonding.md`
   - `15-定向代码阅读报告-GATT-Client.md`
   - `16-定向代码阅读报告-Enable-Disable.md`
   - `17-定向代码阅读报告-Profile-Service生命周期.md`
   - `18-定向代码阅读报告-HAL-JNI-Native边界.md`
   - `19-定向代码阅读报告-Permission-AppOps.md`
   - `20-定向代码阅读报告-GATT-Server.md`
   - `21-定向代码阅读报告-Classic-Discovery.md`
   - `22-定向代码阅读报告-dumpsys输出解读.md`
   - `23-定向代码阅读报告-Log与Bugreport分析.md`

3. 更新索引类文档。
   - `源码索引.md` 增加新报告入口。
   - `98-术语表与阅读路线.md` 增加“源码作战地图阅读路线”。
   - `96-成长路线与实战任务.md` 增加对新报告的实战引用。

### 2.2 不展开或合并的内容

- 不单独生成 Vendor 专章；当前仓库只能写到 JNI/Native/HCI HAL 边界，Vendor 私有实现必须标注为仓库外。
- 不把所有 Profile 都展开成独立报告；先写 Profile Service 生命周期总报告，再在 A2DP/HFP/LeAudio/PBAP/MAP 等章节中引用。
- 不重复已有章节的基础讲解；新报告只写源码入口、状态机、线程、权限、失败点和排查路径。

## 3. 新文档质量标准

每篇架构地图或定向代码阅读报告必须满足以下标准：

1. 调用链必须至少覆盖两层，重点专题必须覆盖到 JNI 或 Native 边界。
2. 必须列出关键源码路径、类名、函数名；行号只能作为辅助锚点。
3. 必须画出 Mermaid 调用链图或状态机图。
4. 必须明确 Binder 边界、线程/Handler、回调分发点和关键状态对象。
5. 必须列出权限检查点，无法在当前仓库确认的权限链路要标注“仓库边界”。
6. 必须列出可能失败点，按 Framework、Service、JNI、Native、Controller/Vendor 分层。
7. 必须给出 logcat tag、dumpsys 入口、bugreport/snoop 观察点。
8. 必须给出“最容易踩的坑”，并能映射到 `97-真实案例库.md` 或后续案例卡。
9. 不能把 Settings、厂商私有协议、设备固件行为写成当前仓库确定实现。
10. 必须为小白提供阅读顺序，为定制开发者提供修改点、风险和验证建议。

## 4. 定向报告统一模板

每篇专题报告采用固定结构：

1. 阅读目标
2. 适用场景
3. 调用链全景图
4. 关键类与源码入口
5. 状态机或生命周期
6. 线程模型与回调分发
7. 权限检查点与 Binder 边界
8. JNI/Native/Vendor 边界
9. 可能失败点
10. dumpsys、logcat、bugreport 观察点
11. 定制修改思路
12. 最容易踩的坑
13. 练习题与参考答案

## 5. 执行优先级

第一轮优先完成“能立刻指导 BLE 定制和排查”的内容：

1. 架构地图总章
2. BLE Scan
3. BLE Connect
4. Pairing/Bonding
5. GATT Client

第二轮补齐“系统能力与边界”：

6. Enable/Disable
7. Profile Service 生命周期
8. HAL/JNI/Native 边界
9. Permission/AppOps

第三轮补齐“扩展专题与排障入口”：

10. GATT Server
11. Classic Discovery
12. dumpsys 输出解读
13. Log 与 Bugreport 分析

## 6. 验收标准

完成本轮优化后，读者应能做到：

- 画出从 App 到 Vendor 边界的蓝牙调用链。
- 说明 `BluetoothAdapter` 可用、蓝牙真正 enabled、Profile connected、业务可用之间的差异。
- 对 BLE Scan、BLE Connect、Pairing、GATT 各写出一条可回到源码的主链路。
- 解释 Binder 线程、HandlerThread、Native main thread、JNI callback thread 的分工。
- 使用 `dumpsys bluetooth_manager`、`dumpsys bluetooth`、logcat、bugreport、snoop 建立分层证据链。
- 针对一个 BLE/GATT 或配对问题，写出修改点、风险点和验证方案。
