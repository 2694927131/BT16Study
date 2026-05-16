# T31 GD HCI层与HAL层详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：HciLayer命令队列(credit流控1命令) | HAL事件→HciLayer事件分发链 | AIDL vs HIDL HAL后端 | ACL分片重组+轮询调度 | LE地址4类型隐私管理 | Snoop Capture时机
> 待回顾问题：无

---

## 1. HciLayer核心架构

### 1.1 类层次结构

源码：[hci_layer.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hci/hci_layer.h)

```cpp
class HciLayer : public HciInterface {
    HciLayer(os::Handler* handler,          // GD栈线程Handler
             hal::HciHal* hci_hal,           // HAL层接口
             storage::StorageModule* storage); // 存储
private:
    struct impl;  // PIMPL隐藏实现细节
};
```

**HciInterface 接口定义**（[hci_interface.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hci/hci_interface.h)）：

```cpp
class HciInterface : public CommandInterface<CommandBuilder> {
public:
    // 命令队列（三种回调模式）
    void EnqueueCommand(unique_ptr<CommandBuilder>,
        ContextualOnceCallback<void(CommandCompleteView)>);
    void EnqueueCommand(unique_ptr<CommandBuilder>,
        ContextualOnceCallback<void(CommandStatusView)>);
    void EnqueueCommand(unique_ptr<CommandBuilder>,
        ContextualOnceCallback<void(CommandStatusOrCompleteView)>);

    // 数据队列（三种HCI包类型）
    BidiQueueEnd<AclBuilder, AclView>* GetAclQueueEnd();
    BidiQueueEnd<ScoBuilder, ScoView>* GetScoQueueEnd();
    BidiQueueEnd<IsoBuilder, IsoView>* GetIsoQueueEnd();

    // 事件注册
    void RegisterEventHandler(EventCode, ContextualCallback<void(EventView)>);
    void RegisterLeEventHandler(SubeventCode, ContextualCallback<void(LeMetaEventView)>);

    // 子接口工厂
    SecurityInterface*          GetSecurityInterface(handler);
    LeSecurityInterface*        GetLeSecurityInterface(handler);
    AclConnectionInterface*     GetAclConnectionInterface(handler, on_disconnect, ...);
    LeAclConnectionInterface*   GetLeAclConnectionInterface(handler, on_disconnect, ...);
    LeAdvertisingInterface*     GetLeAdvertisingInterface(handler);
    LeScanningInterface*        GetLeScanningInterface(handler);
    LeIsoInterface*             GetLeIsoInterface(handler);
    DistanceMeasurementInterface* GetDistanceMeasurementInterface(handler);
    unique_ptr<InquiryInterface> GetInquiryInterface(handler);
};
```

### 1.2 命令队列（Credit流控）

```
命令队列 = 单命令窗口制 (1个outstanding命令)

EnqueueCommand(cmd, callback)
  ↓
commands_ 链表尾部加入 {cmd, callback, timeout}
  ↓
command_credits_ > 0？
  YES → dequeue发送 (从链表头取)
  NO  → 等待当前命令完成

CommandComplete/CommandStatus事件到达:
  ↓
on_command_complete/on_command_status
  ↓ command_credits_++
  ↓ 从commands_头部移除已完成命令
  ↓ 调用对应callback
  ↓ 如果commands_非空 → 继续dequeue下一个

HCI超时保护:
  kHciTimeoutMs = 2000ms      → 单命令超时
  kHciTimeoutRestartMs = 5000ms → 整体重启超时
```

### 1.3 事件分发链路

```
HAL线程                     GD栈线程 (gd_stack_thread)
┌──────────────┐          ┌────────────────────────────────┐
│ HciHalImpl   │          │ HciLayer::impl                 │
│              │          │                                │
│ hal_callbacks│  Post    │ on_hci_event(event_view)       │
│  .hciEvent ──┼─────────→│   ├─ COMMAND_COMPLETE          │
│  Received()  │  via     │   │   → on_command_complete    │
│              │  Handler │   ├─ COMMAND_STATUS            │
│  .aclData ───┼─────────→│   │   → on_command_status      │
│  Received()  │  CallOn  │   ├─ LE_META_EVENT             │
│              │          │   │   → on_le_meta_event       │
│  .scoData ───┼─────────→│   │   → 查le_event_handlers_   │
│  Received()  │          │   ├─ VENDOR_SPECIFIC           │
│              │          │   │   → on_vs_event            │
└──────────────┘          │   ├─ HARDWARE_ERROR            │
                          │   │   → on_hardware_error      │
                          │   └─ 其他 → event_handlers_    │
                          │                                 │
                          │ ACL/SCO/ISO数据:               │
                          │  → 入对应的BidiQueue            │
                          └────────────────────────────────┘
```

关键：**HAL回调运行在HAL线程，通过Handler::CallOn投递到gd_stack_thread执行**。这保证了单线程模型，避免了锁的复杂性。

---

## 2. ACL管理器

### 2.1 AclManagerClassic

```cpp
class AclManagerClassic {
public:
    // 创建BR/EDR连接
    void CreateConnection(Address remote);
    
    // 接受/拒绝连接请求
    void AcceptConnectionRequest(uint16_t handle);
    void RejectConnectionRequest(uint16_t handle);
    
    // 断开连接
    void Disconnect(uint16_t handle, tHCI_REASON reason);
    
    // 回调接口
    void RegisterCallbacks(ConnectionCallbacks*);
};
```

### 2.2 AclManagerLe

```cpp
class AclManagerLe {
public:
    enum LePhyState { IDLE, CONNECTING, CONNECTED };
    
    // LE连接
    void CreateConnection(AddressWithType addr, uint16_t interval, ...);
    
    // 断开
    void Disconnect(uint16_t handle, tHCI_REASON);
    
    // 连接参数更新
    void UpdateConnectionParameters(uint16_t handle, interval, latency, timeout);
    
    // 回调
    void RegisterCallbacks(LeConnectionCallbacks*);
    
private:
    LeAddressManager address_manager_;  // LE隐私地址管理
};
```

### 2.3 RoundRobinScheduler — 轮询调度

```cpp
class RoundRobinScheduler {
    // 从HciLayer的ACL BidiQueue获取发送权限
    // 在Classic和LE ACL之间公平轮询
    // 每个调度周期:
    //   1. 检查Classic ACL是否有待发送数据 → 发送N个
    //   2. 检查LE ACL是否有待发送数据 → 发送N个
    //   3. 循环
};
```

### 2.4 ACL分片与重组

```
发送(分片):
  L2CAP PDU (可能超过ACL MTU)
  → AclFragmenter::Fragment() 
  → 多个ACL包(每包 ≤ HCI ACL Data Packet Length)
  → HciLayer::GetAclQueueEnd() → HAL → Controller

接收(重组):
  HAL → HciLayer::GetAclQueueEnd() → AclAssembler
  → 多个ACL包 → 重组为完整L2CAP PDU
  → 上层
```

---

## 3. HAL层实现

### 3.1 HciHal抽象接口

源码：[hci_hal.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/hci_hal.h)

```cpp
using HciPacket = std::vector<uint8_t>;

class HciHalCallbacks {
public:
    virtual void hciEventReceived(HciPacket event) = 0;
    virtual void aclDataReceived(HciPacket data) = 0;
    virtual void scoDataReceived(HciPacket data) = 0;
    virtual void isoDataReceived(HciPacket data) = 0;
    virtual void controllerNeedsReset() {}  // 控制器异常恢复
};

class HciHal {
public:
    virtual void registerIncomingPacketCallback(HciHalCallbacks*) = 0;
    virtual void unregisterIncomingPacketCallback() = 0;
    virtual void sendHciCommand(HciPacket command) = 0;
    virtual void sendAclData(HciPacket data) = 0;
    virtual void sendScoData(HciPacket data) = 0;
    virtual void sendIsoData(HciPacket data) = 0;
    virtual uint16_t getMsftOpcode() { return 0; }
};
```

### 3.2 HciHalImpl — Android实现

```cpp
class HciHalImpl : public HciHal {
public:
    HciHalImpl(os::Handler* handler, LinkClocker& link_clocker,
               SnoopLogger* snoop_logger);
    // 所有 send* 方法:
    // 1. 调用 SnoopLogger::Capture() 记录包
    // 2. 调用 HciBackend 发送到芯片
    // 3. 调用 LinkClocker 更新链路时钟
private:
    shared_ptr<HciCallbacksImpl> callbacks_;
    shared_ptr<HciBackend> backend_;  // AIDL或HIDL
    LinkClocker& link_clocker_;
    SnoopLogger* snoop_logger_;
};
```

### 3.3 HciBackend — 供应商抽象

```cpp
class HciBackend {
public:
    // 工厂方法
    static shared_ptr<HciBackend> CreateAidl();        // Android 14+ AIDL
    static shared_ptr<HciBackend> CreateHidl(Handler*); // Android 13- HIDL

    virtual void initialize(shared_ptr<HciBackendCallbacks>) = 0;
    virtual void sendHciCommand(const vector<uint8_t>&) = 0;
    virtual void sendAclData(const vector<uint8_t>&) = 0;
    virtual void sendScoData(const vector<uint8_t>&) = 0;
    virtual void sendIsoData(const vector<uint8_t>&) = 0;
};
```

**AIDL vs HIDL 差异**：
```
HIDL (已弃用, Android 13-):
  IBluetoothHci.hal → 进程间通信 → vendor.bluetooth.hci
  数据: Parcel序列化

AIDL (Android 14+):
  IBluetoothHci.aidl → binder通信 → vendor.bluetooth.hci
  数据: SharedMemory + Parcel
  优势: 
    → 更高性能(零拷贝SharedMemory)
    → 支持多个HCI实例(HCI instance name)
    → 统一的AIDL binder框架
```

### 3.4 平台适配

```cpp
#ifdef __ANDROID__
#include "hal/hci_hal_impl_android.h"   // 真机: AIDL/HIDL HAL
#else
#include "hal/hci_hal_impl_host.h"       // Host: RootCanal模拟器
#endif
```

---

## 4. LE地址管理

源码：[le_address_manager.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hci/le_address_manager.h)

### 4.1 四种地址类型

```
AddressType:
  PUBLIC_DEVICE_ADDRESS    → 固定: 芯片出厂地址(IEEE分配)
  RANDOM_STATIC_ADDRESS    → 固定: 上电时随机(不可解析)
  RPA_NONRESOLVABLE       → 动态: 定时变化(不可解析)
  RPA_RESOLVABLE          → 动态: 用IRK解析出真实身份

车载典型配置:
  BR/EDR: PUBLIC_DEVICE_ADDRESS (固定, 方便手机识别)
  BLE: PUBLIC + RPA_RESOLVABLE (隐私保护+可连接)
```

### 4.2 LeAddressManager策略

```cpp
class LeAddressManager {
    // 管理不同LE策略下的地址轮换
    // 隐私模式: 使用RPA (Resolvable Private Address)
    // 兼容模式: 使用Public Address

    AddressWithType GetNextAddress(AclManagerLe::LePhyState state);
    void OnResolvingListUpdated();  // IRK white list更新
};
```

---

## 5. SnoopLogger捕获机制

源码：[snoop_logger.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/hal/snoop_logger.h)

### 5.1 Capture调用位置

```
HciHalImpl::sendHciCommand():
  1. snoop_logger_->Capture(cmd, OUTGOING, CMD) ← 出发的命令
  2. backend_->sendHciCommand(cmd)              ← 发送

hal_callbacks::hciEventReceived():
  1. snoop_logger_->Capture(event, INCOMING, EVT) ← 收到的事件
  2. handler_->CallOn(hci_layer, on_hci_event)    ← 分发

HciHalImpl::sendAclData():
  1. snoop_logger_->Capture(data, OUTGOING, ACL)

hal_callbacks::aclDataReceived():
  1. snoop_logger_->Capture(data, INCOMING, ACL)
```

**五种包类型**：
- CMD (1) = HCI Command
- ACL (2) = ACL Data
- SCO (3) = SCO Data
- EVT (4) = HCI Event
- ISO (5) = ISO Data

---

## 6. Controller控制器接口

```cpp
class Controller {
public:
    // 读取本地信息
    uint16_t GetAclDataPacketLength();     // ACL MTU
    uint8_t  GetNumAclDataPackets();       // 缓冲区数量(流控)
    uint16_t GetScoDataPacketLength();
    uint8_t  GetNumScoDataPackets();
    uint8_t  GetLeDataPacketLength();
    
    // HCI版本信息
    uint8_t  GetHciVersion();
    uint16_t GetHciRevision();
    uint8_t  GetLmpVersion();
    uint16_t GetLmpSubVersion();
    uint16_t GetManufacturerId();          // LMP MFID (Qualcomm/Broadcom...)
    
    // 特性
    bool SupportsBle();
    bool SupportsBle2mPhy();
    bool SupportsBleCodedPhy();
    bool SupportsLeIsochronousChannels();  // LE Audio
};
```

---

## 7. 车载实战

### 7.1 芯片初始化序列

```
1. HCI_RESET → 复位芯片
2. READ_LOCAL_VERSION_INFORMATION → 获取芯片版本
3. READ_LOCAL_SUPPORTED_FEATURES → 获取支持特性
4. READ_BUFFER_SIZE → ACL/SCO/ISO缓冲区大小
5. READ_BD_ADDR → 读取蓝牙地址
6. VSC: 配置TX Power / AFH / Coex / SCO PCM
7. SET_EVENT_MASK → 启用需要的事件
8. WRITE_CLASS_OF_DEVICE → 写入CoD
9. WRITE_LOCAL_NAME → 写入设备名称
```

### 7.2 HCI命令超时排查

```
现象: 蓝牙初始化卡住, 日志无响应

排查:
  logcat -s bt_btu_hcif → 查看最后发送的HCI命令
  → 如果每条命令后无CommandComplete → HCI通信断开
  
常见原因:
  1. UART连接中断 → 检查 /dev/ttyHS0
  2. 芯片固件异常 → 需要重新下载固件
  3. 时钟配置错误 → 波特率不匹配
  4. 芯片处于异常状态 → 发送HCI_RESET恢复

GD层超时保护:
  kHciTimeoutMs = 2000ms → HCI_RESET后5秒超时重启
```

### 7.3 调试命令

```bash
# 查看HCI层日志
adb logcat -s bt_btu_hcif bluetooth

# Snoop抓HCI包
adb shell setprop persist.bluetooth.btsnooplogmode full

# 查看芯片信息
adb shell dumpsys bluetooth_manager | grep -E "manufacturer|lmp_ver|hci_ver"
```