# A.5 调试工具一览

> **速通摘要**：本附录汇总车机蓝牙开发常用的 **8 大类调试工具**：① logcat tag 速查；② dumpsys 子模块；③ btsnoop / Wireshark；④ adb shell 命令；⑤ device_config / aconfig；⑥ Bumble PTS 自动化；⑦ GD shim 与 fuzzer；⑧ 厂商专用工具。每个工具给出"打开方法 + 输出位置 + 典型用法"。

---

## 一、logcat tag 速查（按层分组）

### 1.1 Java/Kotlin 上层

```bash
# BluetoothManagerService（开关、状态机）
adb logcat -s BluetoothManagerService:V BluetoothService:V AdapterState:V

# AdapterService（Profile 管理、状态广播）
adb logcat -s bt_btservice_AdapterService:V

# 配对/绑定
adb logcat -s bt_btif_dm:V BondStateMachine:V

# Profile：HFP
adb logcat -s bt_btif_hf:V HeadsetService:V
adb logcat -s bt_btif_hfp_client:V HeadsetClientService:V

# Profile：A2DP
adb logcat -s bt_btif_a2dp:V A2dpService:V A2dpStateMachine:V
adb logcat -s bt_btif_a2dp_source:V bt_btif_a2dp_sink:V

# Profile：AVRCP
adb logcat -s bt_btif_avrcp:V AvrcpControllerService:V AvrcpTargetService:V

# Profile：BLE / GATT
adb logcat -s bt_btif_gatt:V BluetoothGattService:V BluetoothLeScanner:V

# Profile：PBAP / MAP
adb logcat -s bt_btif_pbap:V BluetoothPbap:V
adb logcat -s bt_btif_map:V BluetoothMap:V

# Active Device 管理
adb logcat -s BtActiveDeviceManager:V

# Distance Measurement
adb logcat -s bt_gatt_distance_measurement:V
```

### 1.2 Native（GD 模块化栈）

```bash
# HCI
adb logcat -s bt_gd_hci:V

# L2CAP
adb logcat -s bt_gd_l2cap:V

# SMP（安全）
adb logcat -s bt_gd_smp:V bt_gd_security:V

# Channel Sounding
adb logcat -s bt_gd_channel_sounding:V
```

### 1.3 一键全局

```bash
# 所有蓝牙相关日志（噪音大，仅排查复杂问题用）
adb logcat | grep -iE "bluetooth|bt_|gatt|hci|a2dp|hfp"

# 仅错误
adb logcat *:E | grep -iE "bluetooth|bt_"
```

---

## 二、dumpsys 子模块

```bash
# 蓝牙管理服务（开关状态、Adapter 信息）
adb shell dumpsys bluetooth_manager

# 完整蓝牙栈状态（最详细，输出非常长）
adb shell dumpsys bluetooth_manager | tee bt_dump.txt

# 仅 A2DP 状态
adb shell dumpsys bluetooth_manager | grep -A 50 "A2dpService"

# Active Device
adb shell dumpsys bluetooth_manager | grep -A 20 "ActiveDeviceManager"

# 多设备共存策略
adb shell dumpsys bluetooth_manager | grep -A 30 "PhonePolicy"

# Profile Manager
adb shell dumpsys bluetooth_manager | grep -A 20 "ProfileService"

# BLE 扫描状态
adb shell dumpsys bluetooth_manager | grep -A 20 "ScanController"

# Metrics / 统计
adb shell dumpsys bluetooth_manager | grep -A 50 "Metrics"

# 距离测量
adb shell dumpsys bluetooth_manager | grep -A 20 "DistanceMeasurement"

# Audio 路由
adb shell dumpsys audio | grep -A 10 -i bluetooth
adb shell dumpsys media.audio_policy
```

---

## 三、btsnoop + Wireshark

### 3.1 开启 btsnoop

```bash
# 启用完整 snoop（含 Snoop Header）
adb shell setprop persist.bluetooth.btsnooplogmode full

# 必须重启蓝牙才生效
adb shell svc bluetooth disable && adb shell svc bluetooth enable

# 验证已开启
adb shell getprop persist.bluetooth.btsnooplogmode    # 期望 "full"
```

### 3.2 导出与查看

```bash
# 默认路径（OEM 可能改）
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log

# 用 Wireshark 打开（拖入即可，自动识别为 BT HCI H4）
wireshark btsnoop_hci.log

# 或命令行预览
tshark -r btsnoop_hci.log -V | head -100
```

### 3.3 常用过滤表达式

```
# HCI 命令
hci_cmd
hci_cmd.opcode == 0x0405          # CREATE_CONNECTION

# HCI 事件
hci_evt
hci_evt.code == 0x03              # CONNECTION_COMPLETE
hci_evt.code == 0x3e              # LE_META

# 协议层
btl2cap                            # L2CAP
btsdp                              # SDP
btrfcomm                           # RFCOMM
btavdtp                            # AVDTP（A2DP 信令）
btavctp                            # AVCTP（AVRCP）
btavrcp                            # AVRCP 高层
btatt                              # ATT
btgatt                             # GATT
btsmp                              # SMP（配对）
obex                               # OBEX
btmesh                             # Mesh
btvendor                           # Vendor Specific

# 设备地址过滤
bthci_acl.src.bd_addr == aa:bb:cc:dd:ee:ff
```

### 3.4 关闭 btsnoop（防止 log 占满分区）

```bash
adb shell setprop persist.bluetooth.btsnooplogmode disabled
adb shell svc bluetooth disable && adb shell svc bluetooth enable
```

---

## 四、adb shell 常用命令

### 4.1 蓝牙开关

```bash
adb shell svc bluetooth enable
adb shell svc bluetooth disable

# 状态查询
adb shell settings get global bluetooth_on
```

### 4.2 已配对/已连接设备

```bash
adb shell dumpsys bluetooth_manager | grep -i "bonded\|connected"

# 详细一些
adb shell dumpsys bluetooth_manager | grep -B 1 -A 5 "BondState"
```

### 4.3 配置文件位置

```bash
# 配对 LinkKey/Profile 持久化
adb shell ls /data/misc/bluedroid/
adb shell cat /data/misc/bluedroid/bt_config.conf

# btsnoop 日志
adb shell ls /data/misc/bluetooth/logs/
```

### 4.4 重启蓝牙模块（不重启系统）

```bash
adb shell svc bluetooth disable
sleep 1
adb shell svc bluetooth enable
```

---

## 五、device_config / aconfig flag

### 5.1 查看 flag

```bash
# 查看蓝牙下所有 flag
adb shell device_config list bluetooth

# 查看单个
adb shell device_config get bluetooth channel_sounding
adb shell device_config get bluetooth socket_settings_api
adb shell device_config get bluetooth hci_instance_name_use_injected

# 查看哪些 namespace
adb shell device_config list_namespaces
```

### 5.2 临时覆盖 flag（仅在 userdebug/eng build 有效）

```bash
adb shell device_config put bluetooth channel_sounding true
adb shell svc bluetooth disable && adb shell svc bluetooth enable

# 删除覆盖
adb shell device_config delete bluetooth channel_sounding
```

### 5.3 永久覆盖 flag（重启不丢）

```bash
adb shell device_config set_sync_disabled_for_tests persistent
adb shell device_config put bluetooth <flag> true
```

---

## 六、Bumble + PTS 自动化

### 6.1 Bumble

- **位置**：本仓库 `pandora/server/` 与 `system/blueberry/`，外部仓库 `https://github.com/google/bumble`
- **用途**：纯 Python 实现的蓝牙栈，可与 Android 蓝牙栈对接做端到端测试
- **典型用法**：CI 中以 Bumble 模拟手机/耳机，验证车机蓝牙行为

```bash
# 安装
pip install bumble

# 运行一个简单的 LE Scanner
python3 -m bumble.apps.scanner usb:0
```

详见 [20.3 Bumble + 自动化](../20_测试与CTS/20.3_Bumble与自动化.md)。

### 6.2 PTS（Profile Tuning Suite）

- 来源：Bluetooth SIG 官方认证测试
- 用途：Bluetooth Qualification 流程中必跑（详见 [B.2 Qualification 流程](../附录B_CDD_Qualification/B.2_Bluetooth_SIG_Qualification流程.md)）

---

## 七、GD shim 与 fuzzer

### 7.1 GD shim 切换

GD（Gabeldorsche）是 Android 蓝牙的新模块化栈，部分模块通过 shim 层与旧 BTA/Stack 共存。

```bash
# 查看哪些 GD 模块启用了
adb shell dumpsys bluetooth_manager | grep -i "gd shim\|GdShimModule"

# GD 日志
adb logcat -s bt_gd:V bt_gd_hci:V bt_gd_l2cap:V
```

### 7.2 Fuzzer（CI 用）

本仓库 `system/test/`、`android/app/tests/fuzztests/` 下有蓝牙 fuzzer，CI 跑出 crash 时会附带 reproducer。本地复现：

```bash
# 编译并运行（需要 AOSP 环境）
m bluetooth_fuzzer
adb push out/.../bluetooth_fuzzer /data/local/tmp/
adb shell /data/local/tmp/bluetooth_fuzzer /sdcard/reproducer.bin
```

---

## 八、厂商专用工具

### 8.1 高通（Qualcomm）

- **QXDM / QCAT**：抓取蓝牙芯片侧 log（HCI 之外的 LMP / LL 帧）
- **QC Tools**：高通蓝牙调试套件
- 启用方法：`adb shell setprop persist.bluetooth.btsnooplogmode full` + 厂商提供的 BT init flag

### 8.2 联发科（MTK）

- **Catcher**：MTK 蓝牙芯片侧抓取
- 与 Android btsnoop 配合使用

### 8.3 Broadcom（博通）

- **BTSnoop + BSA log**：博通有自己的扩展 snoop，包含芯片侧状态机

> 厂商工具一般要求 NDA，车机 OEM 需联系芯片代理获取。

---

## 九、车机现场调试一键脚本

```bash
#!/bin/bash
# car_bt_collect.sh — 出现异常时一键收集所有蓝牙现场

OUT=bt_dump_$(date +%Y%m%d_%H%M%S)
mkdir -p $OUT

adb logcat -d > $OUT/logcat.txt
adb shell dumpsys bluetooth_manager > $OUT/dumpsys_bluetooth.txt
adb shell dumpsys audio > $OUT/dumpsys_audio.txt
adb shell dumpsys activity service com.android.bluetooth > $OUT/bt_service.txt
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log $OUT/ 2>/dev/null
adb shell getprop | grep -i "bluetooth\|bt_" > $OUT/props.txt
adb shell device_config list bluetooth > $OUT/aconfig_flags.txt
adb shell ls /data/misc/bluedroid/ > $OUT/bluedroid_files.txt

tar czf $OUT.tar.gz $OUT/
echo "Collected: $OUT.tar.gz"
```

---

## 十、工具对照速查表

| 任务 | 首选工具 | 备选 |
|------|----------|------|
| 看代码运行流程 | logcat -s （对应 tag）| 加 Log.d 打印 |
| 看协议帧 | btsnoop + Wireshark | tshark 命令行 |
| 看蓝牙状态机 | dumpsys bluetooth_manager | logcat AdapterState:V |
| 改 flag 调试 | device_config put | 修源码 |
| 自动化测试 | Bumble | PTS（认证用）|
| 性能瓶颈分析 | systrace + perfetto | dumpsys metrics |
| 功耗分析 | batterystats + Energy Profiler | 万用表测电流 |
| 抓芯片侧 LMP | 厂商工具（QXDM/Catcher）| btsnoop（只到 HCI）|

---

## FAQ

**Q1：dumpsys bluetooth_manager 输出太长（5000+ 行），怎么快速定位？**
保存到文件 + 关键字过滤：`adb shell dumpsys bluetooth_manager > bt.txt`，然后 `less bt.txt`，输入 `/A2dp` 跳到 A2DP 段。

**Q2：btsnoop 文件多大才正常？**
默认上限 4MB 滚动覆盖。若需要长时间录制（如压力测试），用 `/system/etc/bluetooth/bt_stack.conf` 调大 `BtSnoopFileMaxSize`，或定期 pull。

**Q3：device_config 改了没生效？**
- 必须重启蓝牙：`svc bluetooth disable && svc bluetooth enable`
- 部分 flag 是编译时绑定（LAUNCHED 后再 set 无效），见 `flags/25q2_exported_api_flags.aconfig`
- 用户 build 可能禁用 device_config 覆盖，需 userdebug/eng

---

## 上路任务

1. 在车机上跑一次完整的"开机 → 配对手机 → 蓝牙音乐播放 → 来电"流程，用上面的"现场调试一键脚本"采集数据，把 `btsnoop_hci.log` 用 Wireshark 打开，按时间标出每个阶段的协议帧。
2. 用 `device_config put bluetooth <某个 flag> false` 关掉一个新特性（如 `channel_sounding`），观察行为变化，理解 flag 对运行时行为的影响。
3. 写一个自己的 logcat 过滤别名（alias）：把"蓝牙音乐"、"蓝牙电话"、"BLE 扫描"三类问题分别对应一组 logcat tag，未来排查时一键启动。
