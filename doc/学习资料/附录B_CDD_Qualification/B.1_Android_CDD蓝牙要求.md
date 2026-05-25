# B.1 Android CDD 蓝牙要求

> **速通摘要**：**CDD（Compatibility Definition Document）**是 Google 发布的 Android 兼容性规范，要求所有 Android 设备出货前必须满足。蓝牙章节（§7.4.3）规定了：① 必须支持的 Profile；② 各 API level 的最低硬件要求；③ Telephony 设备（车机）的特殊要求；④ BLE Audio / Channel Sounding 等新特性的可选要求。本附录梳理 Android 16（CDD 16）对蓝牙的硬件/软件强制要求，以及车机厂商额外的合规要点。

---

## 一、CDD 蓝牙节定位

```
CDD 16（针对 Android 16 / API 36）
  └── 7. Hardware Compatibility
        └── 7.4 Data Connectivity
              └── 7.4.3 Bluetooth     ← 本附录覆盖
                    ├── 7.4.3.1 Bluetooth Classic（BR/EDR）
                    ├── 7.4.3.2 Bluetooth Low Energy（BLE）
                    ├── 7.4.3.3 Bluetooth LE Audio
                    └── 7.4.3.5 Bluetooth Channel Sounding
```

CDD 官方文档：`https://source.android.com/docs/compatibility/16/android-16-cdd`

> **注**：本附录基于 CDD 公开版本概要，具体条款以官方 PDF 为准。

---

## 二、强制（MUST）要求总结

### 2.1 任何 Handheld 设备（车机也适用）

| 项 | 要求 | Android 版本 |
|----|------|------------|
| 蓝牙开关 | 必须实现 `BluetoothAdapter` API 并可用户切换 | 全部 |
| 配对 | 必须支持 SSP（Secure Simple Pairing）| API 9+ |
| HID Host | 必须支持 HID Host 配对蓝牙键盘鼠标 | API 21+ |
| BLE 扫描 | 必须支持 BLE Scanner | API 21+ |
| BLE Advertise | 必须支持 BLE Peripheral 模式广播（若硬件能力允许）| API 21+ |
| LE Privacy | RPA 支持（IRK/Resolvable Private Address）| API 22+ |
| BLE Mainline | 必须使用 com.android.bt APEX 蓝牙模块 | API 33+ |
| HFP AG | 任何带电话的设备必须支持 HFP AG（手机做 AG）| 全部 |

### 2.2 Automotive（车机专属，CDD §2.5）

| 项 | 要求 | 说明 |
|----|------|------|
| HFP HF | **必须**支持 HFP HF（车机做 Hands-Free）| 解决"车内打电话"基本场景 |
| A2DP Sink | **必须**支持 A2DP Sink + AVRCP CT | 蓝牙音乐 |
| PBAP PCE | **必须**支持 PBAP Client | 同步手机电话簿 |
| MAP MCE | **强烈推荐**支持 MAP Client | 显示/朗读短信 |
| 多设备并发 | **必须**支持至少 2 台手机同时配对 | 蓝牙钥匙 + 主驾手机 |
| 主动选择音源 | **必须**支持手动选择 ActiveDevice | 多手机时切换 |
| Codec 协商 | A2DP 必须支持 SBC、AAC；HFP 必须支持 CVSD、mSBC | 基础语音/音乐质量 |

### 2.3 通用版本演进

| API 等级 | Android 版本 | 新增 MUST |
|---------|------------|----------|
| 33 | Android 13 | LE Audio APIs 可选；蓝牙 Mainline 启用 |
| 34 | Android 14 | LE Audio MUST（仅旗舰），AdvertisingSet API |
| 35 | Android 15 | BluetoothSocketSettings 可选；MAP 1.4 通知 |
| 36 | Android 16 | DistanceMeasurement API 可选；Channel Sounding 可选；HCI Vendor 自动启用 |

---

## 三、Bluetooth Classic（CDD 7.4.3.1）核心条款

### 3.1 硬件
- 必须实现 Bluetooth Core Specification 4.1 或更新版本
- 必须暴露给应用 `BluetoothAdapter` 与 `BluetoothDevice` API
- 必须保留 `android.bluetooth` 包名（不能改）

### 3.2 设备名与可发现
- 用户可在 Settings 修改 Friendly Name
- 必须支持设置可发现时间（120s 默认）

### 3.3 Profile 选择
车机（Automotive）默认启用：

```
config/config.xml（厂商定制）
  └── config_supported_bluetooth_profiles:
        - HFP_HF
        - A2DP_SINK
        - AVRCP_CONTROLLER
        - PBAP_CLIENT
        - MAP_CLIENT
        - HID_HOST
        - GATT
```

源码参考：`android/app/src/com/android/bluetooth/btservice/Config.java`

---

## 四、Bluetooth LE（CDD 7.4.3.2）

### 4.1 硬件能力
- 必须实现 Bluetooth LE 4.0 或更新版本
- 必须支持 LE Coexistence（双模设备同时跑 Classic + LE）
- API 22+ 必须支持 LE Privacy（Random Address）

### 4.2 BLE Peripheral（广播）
- 必须支持多 AdvertisingSet（API 26+）
- 必须暴露 `BluetoothLeAdvertiser` API

### 4.3 BLE Scanner（扫描）
- 必须实现 Filtered Scan（API 21+）
- 必须支持 Batch Scan（节省功耗，API 21+）
- Background Scan 必须工作（车机后台扫蓝牙钥匙）

### 4.4 GATT
- 必须支持 Server + Client 角色
- Notify/Indicate 必须可用
- ATT MTU 协商必须支持至少 23（默认）、推荐 256

---

## 五、LE Audio（CDD 7.4.3.3，Android 14+ 部分强制）

### 5.1 旗舰 Handheld（MUST）
- LC3 编解码必须支持
- Unicast（CIS）必须支持
- VCP / MCP / CCP / TBS 必须支持
- TMAP 必须支持

### 5.2 Automotive（推荐 SHOULD，未强制 MUST）
- 推荐支持 LE Audio Unicast
- 推荐支持 Auracast Broadcast Source（车内多耳机分享）
- 推荐支持 ASHA 助听器

车机厂商目前大多还在 A2DP + HFP 路线，LE Audio 是 2026-2027 重点演进方向。

---

## 六、Channel Sounding（CDD 7.4.3.5，Android 16 新增）

### 6.1 当前状态
- **可选（SHOULD）**：CDD 16 仅推荐，未强制 MUST
- 硬件需要 BLE 5.4 CS 能力
- API：`DistanceMeasurementManager` + `ChannelSoundingParams`

### 6.2 数字车钥匙合规
- 若声称支持"基于蓝牙的车钥匙"，必须满足 **CCC Digital Key v3** 规范
- CS Security Level 3 是 CCC 推荐最低级
- Level 4（NADM）是金融级要求

详见 [24.2 Channel Sounding](../24_测距与定位/24.2_Channel_Sounding_HADM.md)。

---

## 七、CDD Test：CTS / GTS

CDD 要求的功能必须通过对应的测试：

| 测试套件 | 覆盖 | 来源 |
|---------|------|------|
| **CTS（Compatibility Test Suite）** | CDD MUST 项 | 开源，Google 提供 |
| **CTS Verifier** | 人工辅助测试（蓝牙配对、HID、A2DP）| `cts/apps/CtsVerifier/` |
| **GTS（Google Test Suite）** | GMS 设备额外要求 | 仅 GMS 授权厂商 |
| **VTS（Vendor Test Suite）** | HAL 层接口 | 开源 |
| **PTS** | Bluetooth SIG Qualification | SIG 官方 |

详见 [20.2 CTS Verifier / GTS / VTS](../20_测试与CTS/20.2_CTS_Verifier_GTS_VTS.md)。

---

## 八、合规检查清单（车机交付前）

```
□ 蓝牙开关功能：可在 Settings 切换，状态广播正确
□ 蓝牙名称：默认值合理，用户可修改
□ 配对：SSP（PIN/数字比对）正常
□ A2DP Sink + AVRCP CT：可播放手机音乐，可切歌
□ HFP HF：可拨打/接听电话，CVSD + mSBC 协商
□ PBAP Client：可同步手机电话簿
□ MAP Client（推荐）：可显示短信通知
□ BLE Scanner：可扫描蓝牙钥匙广播
□ BLE Privacy：本机以 RPA 广播，对端 IRK 解析正确
□ 多设备：可同时配对 2+ 台手机
□ Codec 协商：A2DP SBC/AAC、HFP CVSD/mSBC 全部测试通过
□ 主动断开/重连：稳定无 crash
□ CTS Verifier 全 PASS
□ Bluetooth SIG QDID 已注册（见 B.2）
□ 厂商合规：CCC（若数字车钥匙）、HiCar/CarPlay/CarLink 各自合规
```

---

## 九、CDD 与 Bluetooth SIG 规范的关系

```
Bluetooth SIG Core Specification（最底层物理协议）
        │
        ▼
Profile Specifications（A2DP 1.4 / HFP 1.9 / PBAP 1.2 等）
        │
        ▼
Bluetooth SIG Qualification（QDID 认证，必经）
        │
        ▼
Android CDD（在 SIG 之上额外的 Android 集成要求）
        │
        ▼
Google GMS 要求（GMS 设备额外的要求，如 Mainline）
        │
        ▼
车机 OEM 自有规范（如华为 HiCar 蓝牙接入规范）
```

车机出货前必须**层层通过**：先 SIG Qualification → 再 Android CDD → 再 GMS（若有）→ 再 OEM 自验。

---

## FAQ

**Q1：车机不强制支持 BLE 广播吗？**
CDD 7.4.3.2 要求 Handheld 必须支持 BLE Advertise（API 21+）。Automotive 类别基本沿用同样要求，但**实际实现广播功能**取决于硬件（部分车机蓝牙模块只做扫描，因此 OEM 在 features 里关掉 `FEATURE_BLUETOOTH_LE`）。

**Q2：A2DP 必须支持哪些 Codec？**
SIG 强制：SBC（兜底）。CDD 强制：SBC + AAC。可选：aptX、aptX HD、LDAC、LC3（LE Audio）。车机若声称 Hi-Fi 音质，通常加入 LDAC 或 aptX HD。

**Q3：CDD 违规会怎样？**
- 普通 OEM：通不过 CTS，无法上 GMS
- GMS 设备：失去 Google 认证，无法预装 Play Store
- 海外 carriers：拒收
- SIG QDID：未通过会被 SIG 撤销 Bluetooth 商标使用权

---

## 上路任务

1. 下载 [Android 16 CDD 官方 PDF](https://source.android.com/docs/compatibility/16/android-16-cdd)，找 §7.4.3 章节，仔细对照本附录列出的要求看是否一致，找出可能的差异（CDD 可能在车机品类有特殊豁免）。
2. 在你的车机原型机上跑一次 CTS Verifier 的蓝牙测试用例，记录哪几条 FAIL，分析原因。
3. 检查车机 OEM 自身的"蓝牙合规清单"，看是否覆盖 CDD 所有 MUST 项，补全遗漏。
