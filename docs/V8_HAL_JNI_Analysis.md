# V8 定向代码阅读报告：HAL / JNI / Native 边界

> **优先级**: 7/12 | **专题**: 跨层调用边界深度分析
> **代码基准**: Android 16 Fluoride | **阅读日期**: 2026-05

---

## 1. 调用链全景图

### 1.1 JNI 边界架构

```mermaid
graph TB
    subgraph "Java 层 (com.android.bluetooth)"
        ANI["AdapterNativeInterface.java<br/>{static native initNative()}"]
        SNI["ScanNativeInterface.java<br/>{static native registerScannerNative()}"]
        GNF["GattNativeInterface.java<br/>{static native gattClientConnect()}"]
        AHCI["AudioHalInterface.java"]
    end

    subgraph "JNI C++ (libbluetooth_jni.so)"
        JNI_ADAPTER["com_android_bluetooth_adapter.cpp<br/>JNI_OnLoad → registerNatives"]
        JNI_SCAN["com_android_bluetooth_scan.cpp<br/>JniScanningCallbacks"]
        JNI_GATT["com_android_bluetooth_gatt.cpp<br/>GattClientCallbacks"]
    end

    subgraph "Native BTIF 层"
        BTIF_CORE["btif_core.cc<br/>btif_init_bluetooth()"]
        BTIF_DM["btif_dm.cc<br/>btif_dm_create_bond()"]
        BTIF_GATTC["btif_gatt_client.cc<br/>btif_gattc_open()"]
        BTIF_AV["btif_av.cc<br/>btif_av_init()"]
        BTIF_HF["btif_hf.cc<br/>btif_hf_init()"]
    end

    subgraph "Legacy Stack"
        BTM["btm_sec.cc"]
        L2CAP["l2c_main.cc"]
        GATT["gatt_main.cc"]
        SDP["sdp_main.cc"]
        RFCOMM["port_api.cc"]
    end

    subgraph "GD Stack"
        LE_SCAN["le_scanning_manager_impl.cc"]
        LE_ADV["le_advertising_manager_impl.cc"]
        ACL["acl_manager.cc"]
        HCI_LAYER["hci_layer.cc"]
    end

    subgraph "HAL (Hardware Abstraction)"
        HCI_HAL["HCI HAL (HIDL/AIDL)"]
        AUDIO_HAL["Audio HAL (HIDL/AIDL)"]
    end

    ANI --> JNI_ADAPTER
    SNI --> JNI_SCAN
    GNF --> JNI_GATT
    
    JNI_ADAPTER --> BTIF_CORE
    JNI_ADAPTER --> BTIF_DM
    JNI_SCAN --> BTIF_SHIM["BleScannerInterfaceImpl"]
    JNI_GATT --> BTIF_GATTC
    
    BTIF_CORE -->|btm_init| BTM
    BTIF_CORE -->|l2c_init| L2CAP
    BTIF_CORE -->|gatt_init| GATT
    BTIF_CORE -->|sdp_init| SDP
    BTIF_CORE -->|RFCOMM_Init| RFCOMM
    
    BTIF_SHIM --> LE_SCAN
    LE_ADV --> HCI_LAYER
    ACL --> HCI_LAYER
    L2CAP --> HCI_LAYER
    
    HCI_LAYER --> HCI_HAL
    BTIF_AV --> AUDIO_HAL
    BTIF_HF --> AUDIO_HAL
```

### 1.2 JNI 注册与调用流程

```mermaid
sequenceDiagram
    participant Java as Java (AdapterNativeInterface)
    participant JNI as JNI lib (bluetooth_jni.so)
    participant BTIF as btif_
    participant STACK as Stack

    Note over Java: System.loadLibrary("bluetooth_jni")
    JNI->>JNI: JNI_OnLoad()
    JNI->>JNI: register_com_android_bluetooth_adapter()
    JNI->>JNI: register_com_android_bluetooth_gatt()
    JNI->>JNI: register_com_android_bluetooth_scan()

    Java->>JNI: initNative(this, ...)
    JNI->>JT: jni_thread_startup()
    JNI->>BTIF: btif_init_bluetooth()
    BTIF->>STACK: 模块初始化

    Java->>JNI: enableNative()
    JNI->>BTIF: btif_enable_bluetooth()
    BTIF->>STACK: bta_dm_enable()
    
    STACK-->>BTIF: 完成回调
    BTIF-->>JNI: do_in_jni_thread(callback)
    JNI-->>Java: onNativeEnabled()
```

---

## 2. 关键类清单

### 2.1 JNI 接口层

| Java 文件 | JNI C++ 文件 | 注册函数 |
|-----------|-------------|---------|
| `AdapterNativeInterface.java` | `com_android_bluetooth_adapter.cpp` | `register_com_android_bluetooth_adapter()` |
| `ScanNativeInterface.java` | `com_android_bluetooth_scan.cpp` | `register_com_android_bluetooth_scan()` |
| `GattNativeInterface.java` | `com_android_bluetooth_gatt.cpp` | `register_com_android_bluetooth_gatt()` |
| `BleAdvertiserNativeInterface.java` | `com_android_bluetooth_ble_adv.cpp` | `register_com_android_bluetooth_ble_adv()` |

### 2.2 JNI 回调类

| C++ 回调类 | Java 回调目标 | 说明 |
|-----------|-------------|------|
| `JniScanningCallbacks` (cpp:142) | `ScanNativeInterface.onScanResult()` | 扫描结果 |
| `GattClientCallbacks` | `GattNativeInterface.onConnected()` | GATT 连接 |
| `JniCallbacks` (Adapter) | `AdapterNativeInterface.onNativeEnabled()` | 栈状态 |
| `BleAdvertiserCallbacks` | `BleAdvertiserNativeInterface` | 广播状态 |

### 2.3 HAL 接口

| HAL | 类型 | 文件 |
|-----|------|------|
| `HCI HAL` | HIDL / AIDL | `system/hci/` |
| `Audio A2DP HAL` | HIDL / AIDL | `system/audio_hal_interface/aidl/hidl` |
| `Audio HFP HAL` | HIDL / AIDL | `system/audio_hal_interface/hfp_client_interface.cc` |
| `Audio LE Audio HAL` | AIDL | `system/audio_hal_interface/le_audio_software.cc` |

---

## 3. JNI 线程模型

```mermaid
graph TD
    subgraph "Java 线程"
        JT["任意 Java 线程"]
    end
    
    subgraph "Binder 线程池"
        BT["Binder Thread Pool"]
    end

    subgraph "JNI / bt_jni_thread"
        JNT["bt_jni_thread<br/>do_in_jni_thread()"]
    end

    subgraph "BT Main Thread"
        BMT["BT Main Thread<br/>do_in_main_thread()"]
    end

    JT -->|JNI call| JNT
    BT -->|callback result| JNT
    JNT -->|post| BMT
    BMT -->|post callback| JNT
    JNT -->|CallbackEnv| JT
```

### 3.1 JNI 线程管理

```cpp
// btif_jni_task.cc:40
static MessageLoopThread jni_thread("bt_jni_thread");

// btif_jni_task.cc:108-114
bt_status_t do_in_jni_thread(base::OnceClosure task) {
    // 确保在 bt_jni_thread 上执行回调
    if (!jni_thread.DoInThread(task)) {
        return BT_STATUS_FAIL;
    }
    return BT_STATUS_SUCCESS;
}
```

---

## 4. 回调链线程追踪

| 发起层 | 目标层 | 线程切换 | 同步方式 |
|--------|--------|---------|---------|
| Java → JNI | JNI C++ | 调用的 Java 线程 | 同步调用 |
| JNI → BTIF | btif_*.cc | `do_in_jni_thread` | 消息投递 |
| BTIF → Stack | Stack | `do_in_main_thread` | 消息投递 |
| Stack → BTIF | Stack 回调 | 内部 callback | 直接调用 |
| BTIF → JNI | Java | `do_in_jni_thread` → `CallbackEnv` | 消息投递 |
| JNI → Java | Java 回调 | `bt_jni_thread` → Handler | JNI CallVoidMethod |

---

## 5. HAL 边界

### 5.1 HCI HAL 架构

```mermaid
graph LR
    subgraph "Native"
        HCI_LAYER["HciLayer (GD)"]
    end
    
    subgraph "Vendor Process"
        HCI_HAL["HCI HAL Service"]
    end
    
    subgraph "Controller"
        BT_CHIP["Bluetooth Controller"]
    end

    HCI_LAYER -->|HIDL/AIDL IPC| HCI_HAL
    HCI_HAL -->|UART/SDIO/USB| BT_CHIP
```

---

## 6. 常见失败点

| 边界 | 失败模式 | 原因 |
|------|---------|------|
| JNI | `UnsatisfiedLinkError` | `bluetooth_jni.so` 未找到 |
| JNI | JNI crash | native 代码访问非法内存 |
| JNI | `CallbackEnv` 获取失败 | Thread 未 attach JVM |
| HAL | `HAL service not found` | 设备无蓝牙 HAL |
| HAL | HAL crash | Vendor 实现异常 |
| Binder | `DeadObjectException` | Profile 进程死亡 |

---

## 7. 调试建议

```bash
# JNI 日志
adb logcat -s bt_btif_core:* bt_btif_jni:*

# 查看 JNI 库是否加载
adb logcat | grep "System.loadLibrary"

# HCI HAL 日志
adb logcat -s bt_shim_hci:*

# 音频 HAL 日志
adb logcat -s bt_audio_hal:*
```

---

> **下一篇**: [V8_Permission_Analysis.md](V8_Permission_Analysis.md) — Permission/AppOps 分析（优先级 8/12）

---

## 参考文件清单

| 文件 | 说明 |
|------|------|
| `android/app/jni/com_android_bluetooth_adapter.cpp` | 适配器 JNI |
| `android/app/jni/com_android_bluetooth_scan.cpp` | 扫描 JNI (1039 行) |
| `android/app/jni/com_android_bluetooth_gatt.cpp` | GATT JNI |
| `system/btif/src/btif_jni_task.cc` (133 行) | JNI 线程管理 |
| `system/btif/src/btif_gatt_client.cc` | GATT 客户端 Native |
| `system/btif/src/btif_dm.cc` (4423 行) | 设备管理 Native |
| `system/audio_hal_interface/` | 音频 HAL 接口 |
| `system/audio_hal_interface/hfp_client_interface.cc` | HFP 音频 HAL |
| `system/audio_hal_interface/a2dp_encoding.cc` | A2DP 编码 |

---
## 相关章节

- **第7章 JNI Bridge**：[07_JNI_Bridge.md](07_JNI_Bridge.md)
- **第8章 BTIF Layer**：[08_BTIF_Layer.md](08_BTIF_Layer.md)
- **第15章 HCI HAL**：[15_HCI_HAL.md](15_HCI_HAL.md)
- **第1章 Architecture Overview**：[01_Architecture_Overview.md](01_Architecture_Overview.md)

## 车载场景

JNI/HAL边界是车载蓝牙最常出问题的区域。UnsatisfiedLinkError和HAL service crash在车厂集成阶段频发。bt_jni_thread的线程模型和CallbackEnv模式是理解Java-Native通信的关键。

> **下一步**: 阅读 [第7章 JNI Bridge](07_JNI_Bridge.md)
