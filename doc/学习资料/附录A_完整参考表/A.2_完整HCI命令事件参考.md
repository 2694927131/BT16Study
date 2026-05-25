# A.2 完整 HCI 命令 / 事件参考

> **速通摘要**：**HCI（Host Controller Interface）**是 Host（蓝牙协议栈，运行在 Android）与 Controller（蓝牙芯片）之间的命令/事件接口。命令 16-bit Opcode = **OGF（高 6 位）+ OCF（低 10 位）**，事件用 1-byte Event Code。本附录按 OGF 分组列出 Android 16 实际使用的 HCI 命令与事件（全部从 `system/stack/include/hcidefs.h` 验证），并给出 Wireshark 过滤示例。

---

## 一、OGF 分组速查

| OGF | 名称 | Opcode 前缀 | 说明 | hcidefs.h 行号 |
|-----|------|-----------|------|---------------|
| 0x01 | Link Control | 0x0400 | Inquiry / 连接 / 配对 / SCO | :38 |
| 0x02 | Link Policy | 0x0800 | Sniff/Park/Role Switch | :39 |
| 0x03 | Host Controller & Baseband | 0x0C00 | Reset / 扫描使能 / Class of Device | :40 |
| 0x04 | Informational Parameters | 0x1000 | Local Version / BD_ADDR | :41 |
| 0x05 | Status Parameters | 0x1400 | Read RSSI / Failed Contact Counter | :42 |
| 0x06 | Testing | 0x1800 | Loopback / DUT Mode | :43 |
| 0x08 | LE Controller | 0x2000 | 所有 LE/BLE 命令 | :44 |
| 0x3F | Vendor Specific | 0xFC00 | 厂商自定义 | :46 |

---

## 二、Link Control（OGF=0x01）—— 最常用 Classic 命令

| Opcode | 名称 | 用途 | hcidefs.h:line |
|--------|------|------|----------------|
| 0x0401 | HCI_INQUIRY | 启动设备扫描 | :55 |
| 0x0402 | HCI_INQUIRY_CANCEL | 取消扫描 | :56 |
| 0x0405 | HCI_CREATE_CONNECTION | Classic ACL 连接 | :59 |
| 0x0406 | HCI_DISCONNECT | 断开连接 | :60 |
| 0x0407 | HCI_ADD_SCO_CONNECTION | 旧版 SCO 建立 | :61 |
| 0x0409 | HCI_ACCEPT_CONNECTION_REQUEST | 接受入站连接 | :63 |
| 0x040A | HCI_REJECT_CONNECTION_REQUEST | 拒绝入站连接 | :64 |
| 0x040B | HCI_LINK_KEY_REQUEST_REPLY | 返回 Link Key | :65 |
| 0x040C | HCI_LINK_KEY_REQUEST_NEG_REPLY | 无 Link Key（触发新配对）| :66 |
| 0x040D | HCI_PIN_CODE_REQUEST_REPLY | 旧 PIN 配对回复 | :67 |
| 0x0411 | HCI_AUTHENTICATION_REQUESTED | 触发认证 | :70 |
| 0x0413 | HCI_SET_CONN_ENCRYPTION | 启用 ACL 加密 | :71 |
| 0x0419 | HCI_RMT_NAME_REQUEST | 查远端 Friendly Name | :74 |
| 0x041B | HCI_READ_RMT_FEATURES | 查远端特性 | :76 |
| 0x041D | HCI_READ_RMT_VERSION_INFO | 远端版本（LMP）| :78 |
| 0x0428 | HCI_SETUP_ESCO_CONNECTION | eSCO 建立（HFP < 1.7）| :81 |
| 0x042B | HCI_IO_CAPABILITY_REQUEST_REPLY | SSP IO Capability | :84 |
| 0x042C | HCI_USER_CONF_REQUEST_REPLY | SSP 数字比对确认 | :85 |
| 0x043D | HCI_ENH_SETUP_ESCO_CONNECTION | mSBC/LC3-SWB 用的增强 eSCO | :103 |

---

## 三、Link Policy（OGF=0x02）

| Opcode | 名称 | 用途 | hcidefs.h:line |
|--------|------|------|----------------|
| 0x0803 | HCI_SNIFF_MODE | 进入低功耗 Sniff | :119 |
| 0x0804 | HCI_EXIT_SNIFF_MODE | 退出 Sniff（音乐播放前必要）| :120 |
| 0x0807 | HCI_QOS_SETUP | 设置链路 QoS | :123 |
| 0x080B | HCI_SWITCH_ROLE | 切换主从角色 | :125 |
| 0x080D | HCI_WRITE_POLICY_SETTINGS | 写策略（允许 Sniff/Switch）| :127 |
| 0x0811 | HCI_SNIFF_SUB_RATE | 配置 Sniff 子速率 | :131 |

---

## 四、Host Controller & Baseband（OGF=0x03）

| Opcode | 名称 | 用途 | hcidefs.h:line |
|--------|------|------|----------------|
| 0x0C01 | HCI_SET_EVENT_MASK | 启用事件类型 | :137 |
| 0x0C03 | HCI_RESET | 控制器复位（启动必发）| :138 |
| 0x0C13 | HCI_WRITE_LOCAL_NAME | 设置本机蓝牙名 | — |
| 0x0C14 | HCI_READ_LOCAL_NAME | 读取本机蓝牙名 | :147 |
| 0x0C18 | HCI_WRITE_PAGE_TOUT | 设置 Page Timeout | :151 |
| 0x0C1A | HCI_WRITE_SCAN_ENABLE | 启用 Inquiry/Page Scan | :153 |
| 0x0C24 | HCI_WRITE_CLASS_OF_DEVICE | 写 CoD（影响图标）| — |
| 0x0C45 | HCI_WRITE_INQUIRY_MODE | 写 Inquiry 模式（RSSI/Extended）| — |
| 0x0C56 | HCI_WRITE_SIMPLE_PAIRING_MODE | 启用 SSP | — |

---

## 五、Informational Parameters（OGF=0x04）

| Opcode | 名称 | 用途 | hcidefs.h:line |
|--------|------|------|----------------|
| 0x1001 | HCI_READ_LOCAL_VERSION_INFO | 读 HCI/LMP 版本 | :248 |
| 0x1003 | HCI_READ_LOCAL_SUPPORTED_FEATURES | 读本地特性 | — |
| 0x1009 | HCI_READ_BD_ADDR | 读本机 BD_ADDR | :254 |

---

## 六、Status Parameters（OGF=0x05）

| Opcode | 名称 | 用途 |
|--------|------|------|
| 0x1405 | HCI_READ_RSSI | 读连接 RSSI |
| 0x1408 | HCI_GET_LINK_QUALITY | 读链路质量 |

---

## 七、LE Controller（OGF=0x08）—— BLE 全部命令

| Opcode | 名称 | 用途 | hcidefs.h:line |
|--------|------|------|----------------|
| 0x2003 | HCI_BLE_READ_LOCAL_SPT_FEAT | 读本地 LE 特性 | :301 |
| 0x200A | HCI_BLE_SET_ADV_DATA | 设置广播数据 | — |
| 0x200B | HCI_BLE_SET_SCAN_RSP_DATA | 设置扫描响应数据 | — |
| 0x200C | HCI_BLE_WRITE_ADV_ENABLE | 启动/停止广播 | — |
| 0x200D | HCI_BLE_CREATE_CONN | 发起 LE 连接 | — |
| 0x200E | HCI_BLE_CREATE_CONN_CANCEL | 取消 LE 连接 | :309 |
| 0x2017 | HCI_BLE_ENCRYPT | LE 加密 | :318 |
| 0x201A | HCI_BLE_LTK_REQ_REPLY | LTK 请求回复 | :321 |
| 0x201B | HCI_BLE_LTK_REQ_NEG_REPLY | LTK 拒绝（触发新 SMP）| :322 |
| 0x2040 | HCI_LE_SET_EXT_ADV_PARAMS | 5.0 扩展广播参数 | — |
| 0x2043 | HCI_LE_SET_EXT_SCAN_PARAMS | 扩展扫描参数 | — |
| 0x205E | HCI_LE_SET_ISO_DATA_PATH | LE Audio CIS/BIS 路径 | — |
| 0x2082 | LE_CS_Read_Local_Supported_Capabilities | Channel Sounding 本地能力 | — |
| 0x2083 | LE_CS_Read_Remote_Supported_Capabilities | CS 远端能力 | — |
| 0x2090 | LE_CS_Procedure_Enable | CS 测量启停 | — |

> **完整 LE 命令列表**：见 `system/stack/include/hcidefs.h:298-499`。Android 16 的 BLE 5.4 全部命令都在此区段。

---

## 八、常用 HCI 事件

| Event Code | 名称 | 含义 | hcidefs.h:line |
|-----------|------|------|----------------|
| 0x01 | HCI_INQUIRY_COMP_EVT | Inquiry 完成 | :510 |
| 0x02 | HCI_INQUIRY_RESULT_EVT | Inquiry 发现结果 | :511 |
| 0x03 | HCI_CONNECTION_COMP_EVT | Classic 连接建立完成 | — |
| 0x05 | HCI_DISCONNECTION_COMP_EVT | 断开完成 | :514 |
| 0x07 | HCI_RMT_NAME_REQUEST_COMP_EVT | 名称查询完成 | — |
| 0x08 | HCI_ENCRYPTION_CHANGE_EVT | 加密状态变化 | — |
| 0x0E | HCI_COMMAND_COMPLETE_EVT | 命令完成（带状态）| — |
| 0x0F | HCI_COMMAND_STATUS_EVT | 命令已收到 | — |
| 0x13 | HCI_NUM_COMPL_DATA_PKTS_EVT | Number of Completed Packets（流控）| — |
| 0x22 | HCI_INQUIRY_RSSI_RESULT_EVT | 带 RSSI 的 Inquiry 结果 | :543 |
| 0x2C | HCI_SYNCHRONOUS_CONNECTION_COMP_EVT | SCO/eSCO 建立完成 | — |
| 0x3E | HCI_BLE_EVENT | LE Meta Event（子事件见下表）| — |

### 8.1 LE Meta Sub-Events（HCI_BLE_EVENT 0x3E 的 Sub）

| Sub-Code | 名称 | 含义 |
|---------|------|------|
| 0x01 | LE_CONN_COMPLETE | LE 连接建立 |
| 0x02 | LE_ADVERTISING_REPORT | 扫描到广播 |
| 0x05 | HCI_BLE_LTK_REQ_EVT | LTK 请求（见 hcidefs.h:570）|
| 0x0A | LE_ENHANCED_CONN_COMPLETE | 增强连接完成（含 RPA）|
| 0x11 | HCI_BLE_SCAN_TIMEOUT_EVT | 扫描超时（hcidefs.h:580）|
| 0x13 | HCI_BLE_SCAN_REQ_RX_EVT | 收到 Scan Request（hcidefs.h:582）|
| 0x18 | LE_CS_Read_Remote_Supported_Capabilities_Complete | CS 能力查询完成 |
| 0x1F | LE_CS_Subevent_Result_Event | CS 测量结果 |

---

## 九、Wireshark 过滤示例

```
# 所有 HCI 命令
hci_cmd

# 特定 OGF
hci_cmd.opcode.ogf == 0x01     # Link Control
hci_cmd.opcode.ogf == 0x08     # LE
hci_cmd.opcode.ogf == 0x3F     # Vendor

# 特定命令
hci_cmd.opcode == 0x0405       # CREATE_CONNECTION
hci_cmd.opcode == 0x041B       # READ_RMT_FEATURES
hci_cmd.opcode == 0x200D       # LE_CREATE_CONNECTION

# 所有 HCI 事件
hci_evt

# 特定事件
hci_evt.code == 0x05           # DISCONNECTION_COMPLETE
hci_evt.code == 0x3E && bthci_evt.le_meta_subevent == 0x01   # LE_CONN_COMPLETE

# ACL 数据
bthci_acl
```

---

## 十、抓 btsnoop 的方法

```bash
# 启用 btsnoop 完整模式
adb shell setprop persist.bluetooth.btsnooplogmode full
adb shell svc bluetooth disable && adb shell svc bluetooth enable

# 复现问题后导出
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log ./

# 用 Wireshark 打开（识别为 BT HCI H4 格式）
wireshark btsnoop_hci.log
```

---

## 十一、车机常用诊断序列

| 现象 | 期望看到的 HCI 流 |
|------|------------------|
| 蓝牙开机失败 | `0x0C03 RESET` → `0x0E CommandComplete(0x00)` → `0x1001 READ_LOCAL_VERSION` |
| 扫描启动 | `0x0401 INQUIRY` → `0x0E CommandStatus` → 多个 `0x22 Inquiry_RSSI_Result` |
| Classic 连接 | `0x0405 CREATE_CONNECTION` → `0x0E CommandStatus` → `0x03 ConnectionComplete` |
| 配对 | `0x042B IO_Cap_Req_Reply` → `0x33 IO_Cap_Resp` → `0x34 User_Conf_Req` → `0x042C User_Conf_Reply` |
| SCO 建立（HFP）| `0x043D ENH_SETUP_ESCO` → `0x2C Synchronous_Connection_Complete` |
| LE 扫描 | `0x200B SET_SCAN_PARAMS` → `0x200C SET_SCAN_ENABLE(1)` → 多个 `0x3E LE_Advertising_Report` |
| LE 连接 | `0x200D LE_CREATE_CONN` → `0x3E LE_Conn_Complete` |

---

## FAQ

**Q1：Opcode 0x0405 怎么算出来的？**
`OGF=0x01`（Link Control，左移 10 位 = 0x0400）+ `OCF=0x0005`（CREATE_CONNECTION），按位或 = `0x0405`。`hcidefs.h:59` 中 `HCI_CREATE_CONNECTION = (0x0005 | HCI_GRP_LINK_CONTROL_CMDS)` 就是这个意思。

**Q2：为什么 `hcidefs.h` 没列出所有 0x0C** 段的写命令？
本仓库 `hcidefs.h` 只声明 Android 实际用到的命令；完整 HCI 命令表见 Bluetooth Core 规范 Vol 4 Part E §7。所以本附录中"未列行号"的命令意味着它们不在 hcidefs.h 中（Android 直接用 packet builder 生成，见 `system/gd/hci/`）。

**Q3：Vendor Specific 命令（OGF=0x3F）怎么定义？**
见 [23.1 Vendor Specific HCI 命令体系](23_Vendor扩展_多HCI/23.1_Vendor_Specific_HCI命令体系.md)，OEM 自由定义 OCF，调用 `BTM_VendorSpecificCommand`（`system/stack/btm/btm_devctl.cc:350`）发送。

---

## 上路任务

1. 抓一次"扫描→配对→HFP 连接→来电"的完整 btsnoop，用上表的过滤表达式分别提取每个阶段的 HCI 命令/事件序列。
2. 阅读 `system/stack/include/hcidefs.h` 中 `:38-46` 的 OGF 定义，理解为何 `0x3F << 10 = 0xFC00` 是 Vendor 段。
3. 在 Wireshark 里观察一次 LE Audio 流建立（如果手机支持），找到 `0x205E HCI_LE_SET_ISO_DATA_PATH` 命令，看 CIS handle 如何对应到音频数据。
