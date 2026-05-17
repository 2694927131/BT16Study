# V8 定向代码阅读报告：dumpsys 输出解读

> **优先级**: 11/12 | **专题**: dumpsys 输出和分析方法
> **代码基准**: Android 16 Fluoride | **阅读日期**: 2026-05

---

## 1. dumpsys 架构总览

```mermaid
graph TD
    subgraph "adb shell dumpsys bluetooth_manager"
        BMS["BluetoothManagerService<br/>system_server 进程"]
        BM_OUTPUT["输出:<br/>Enabled/State/Address/Name<br/>ActiveLogs/CrashTimestamps<br/>BleAppRegistrations"]
        BMS --> BM_OUTPUT
    end

    subgraph "adb shell dumpsys bluetooth"
        AS["AdapterService<br/>com.android.bluetooth 进程"]
        AS -->|遍历所有 Profile| PROFILES["Profile Services<br/>A2dp/Headset/HID/..."]
        AS -->|堆叠| SC["ScanController"]
        AS -->|堆叠| GATT["GattService"]
        AS -->|堆叠| DB["DatabaseManager"]
    end

    subgraph "Native dumpsys (GD)"
        GD["bluetooth::shim::Dump()"]
        GD_S["dumpsys.cc"]
        GD -->|stack_handler_->Call| CTRL["Controller Dump"]
        GD -->|stack_handler_->Call| ACL["ACL History Dump"]
        GD -->|stack_handler_->Call| ADV["Advertising Dump"]
        GD -->|stack_handler_->Call| WAKELOCK["Wakelock Dump"]
        GD -->|stack_handler_->Call| SNOOP["Snoop Log Dump"]
    end

    BM_OUTPUT -->|system_server 控制| AS
    PROFILES -->|每个 Profile 的 dump()| PD["Profile 详情"]
```

## 2. dumpsys 命令一览

```bash
# 最常用的 2 个命令
adb shell dumpsys bluetooth_manager   # system_server 侧状态
adb shell dumpsys bluetooth            # com.android.bluetooth 侧状态

# 过滤特定模块
adb shell dumpsys bluetooth | grep -A 30 "ScanController"
adb shell dumpsys bluetooth | grep -A 20 "HeadsetService"
adb shell dumpsys bluetooth | grep -A 20 "A2dpService"
adb shell dumpsys bluetooth | grep -A 50 "GattService"

# 查看连接的设备
adb shell dumpsys bluetooth | grep -E "Device:|Connected|State"

# 查看扫描统计
adb shell dumpsys bluetooth | grep -A 30 "AppScanStats"
```

---

## 2. 主要输出模块

### 3.1 `dumpsys bluetooth_manager` 输出

| 字段 | 说明 | 源码位置 |
|------|------|---------|
| `Enabled:` | 是否启用 | `BluetoothManagerService.java:2170` |
| `State:` | 当前状态 (ON/OFF/BLE_ON...) | `AdapterState.kt` |
| `Address:` | 蓝牙地址 | `AdapterProperties` |
| `Name:` | 蓝牙名称 | `AdapterProperties` |
| `Time since enabled:` | 启动计时 | `BluetoothManagerService` |
| `Active Logs:` | 最近 20 次状态变化 | `ActiveLogs.kt:83` |
| `Crash timestamps:` | 崩溃时间戳 | `BluetoothManagerService` |
| `Ble App Registrations:` | BLE 应用注册 | `BleAppManager.kt` |

### 3.2 `dumpsys bluetooth` 模块

| 模块 | 输出内容 | 源码 |
|------|---------|------|
| `BondedDevices` | 已配对设备列表 | `AdapterService` |
| `ScanController` | 扫描状态、注册的 App、Filter | `ScanController.java:1724` |
| `AppScanStats` | 每个 App 的扫描频率统计 | `AppScanStats.java:602` |
| `ScannerMap` | 扫描注册映射 | `ScannerMap.java:228` |
| `A2dpService` | Codec、连接设备 | `A2dpService.dump()` |
| `HeadsetService` | 通话状态、SCO 连接 | `HeadsetService.java:2592` |
| `LeAudioService` | LE Audio 配置 | `LeAudioService.java:5712` |
| `GattService` | GATT 客户端连接 | `GattService.dump()` |
| `DatabaseManager` | 存储的 bonded device | `DatabaseManager.java:1243` |
| `VolumeControlService` | VCP 状态 | `VolumeControlService.java:1679` |

### 3.3 GD Stack (Native) dumpsys

| 模块 | 输出内容 | 源码 |
|------|---------|------|
| Controller | HCI 控制器信息 | `shim/stack.cc:365` |
| ACL | 连接/断开历史 | `shim/acl.cc:1190` |
| Advertising | LE 广播状态 | `le_advertising_manager` |
| Wakelock | Wakelock 状态 | `WakelockManager::Dump()` |
| Snoop Log | HCI Snoop log | `SnoopLogger::DumpSnoozLogToFile()` |

---

## 4. 常见问题分析

| 问题 | dumpsys 检查项 | 正常值 |
|------|---------------|--------|
| 蓝牙打不开 | `State:` | 应为 `STATE_ON` (12) |
| 扫描无结果 | `ScanController` → `isScanning` | 应为 true |
| 连接失败 | `GattService` → `ConnectionState` | 应无超时连接 |
| 音频问题 | `A2dpService` → codec + device | Codec 应匹配 |
| 配对失败 | `BondedDevices` | 设备应在列表中 |
| 内存泄漏 | `AppScanStats` | 扫描次数不应异常增长 |

---

## 5. adb shell 命令参考

```bash
# 启用蓝牙
adb shell cmd bluetooth_manager enable

# 禁用蓝牙
adb shell cmd bluetooth_manager disable

# 启用 BLE-only
adb shell cmd bluetooth_manager enableBle

# 等待特定状态
adb shell cmd bluetooth_manager wait-for-state:STATE_ON

# 清除蓝牙数据 (Carrier)
adb shell cmd bluetooth_manager factoryReset

# 查看蓝牙日志
adb shell dumpsys bluetooth_manager | grep -i log
```

---

> **下一篇**: [V8_Log_Analysis.md](V8_Log_Analysis.md) — Log/Bugreport 分析方法（优先级 12/12）

---

## 参考文件清单

| 文件 | 说明 |
|------|------|
| `service/src/ShellCommand.kt` | adb shell 命令实现 |
| `service/src/ActiveLogs.kt` | 启用日志缓存 |
| `service/.../BluetoothManagerService.java:2170` | `dump()` |
| `service/.../BluetoothServiceBinder.java:439` | `dump()` |
| `android/app/.../le_scan/ScanController.java:1724` | 扫描 dump |
| `android/app/.../hfp/HeadsetService.java:2592` | HFP dump |
| `android/app/.../le_audio/LeAudioService.java:5712` | LE Audio dump |
| `android/app/.../vc/VolumeControlService.java:1679` | VCP dump |
| `android/app/.../btservice/storage/DatabaseManager.java:1243` | DB dump |
| `system/main/shim/dumpsys.cc` | Native dump |

---
## 相关章节

- **第1章 Architecture Overview**：[01_Architecture_Overview.md](01_Architecture_Overview.md)
- **第2章 Environment Setup**：[02_Environment_Setup.md](02_Environment_Setup.md)
- **第5章 Service Layer**：[05_Service_Layer.md](05_Service_Layer.md)
- **第12章 BLE Stack**：[12_BLE_Stack.md](12_BLE_Stack.md)

## 车载场景

dumpsys是车载蓝牙问题排查的首选工具。bluetooth_manager的State/Enabled/CrashTimestamps字段快速定位开关问题，bluetooth的按模块grep（ScanController/GattService/HeadsetService）逐层缩小问题范围。

> **下一步**: 阅读 [第1章 Architecture Overview](01_Architecture_Overview.md)
