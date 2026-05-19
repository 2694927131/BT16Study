# 第15课：如何阅读与导航蓝牙协议栈代码

> **目标读者**：刚接手 Android 蓝牙协议栈模块的开发者，C++ 基础薄弱
> **前置知识**：本系列教材 01-13 课的 C++ 基础知识
> **学习目标**：掌握协议栈代码的整体架构、代码风格差异、阅读技巧和调试方法，能够独立追踪和定位代码

---

## 1. 协议栈代码整体架构

### 1.1 目录结构与模块划分

Android 蓝牙协议栈源码位于 `system/` 目录下，核心模块如下：

```
system/
├── gd/          # GD 新架构（Gabeldorsche，现代 C++17）
│   ├── common/  # 通用工具（BidiQueue, Callback, LruCache）
│   ├── hci/     # HCI 层（Controller, AclManager, LeScanningManager）
│   ├── hal/     # 硬件抽象（HciHal, SnoopLogger）
│   ├── os/      # OS 抽象（Handler, Thread, Queue, Alarm, Reactor）
│   ├── packet/  # 数据包解析与构建
│   └── storage/ # 持久化存储（ConfigCache, Device, Mutation）
├── stack/       # 传统协议栈（C 风格 + 现代 C++ 混合）
│   ├── a2dp/    # A2DP 编解码器
│   ├── btm/     # 蓝牙管理（安全/扫描/ISO/SCO）
│   ├── gatt/    # GATT 协议
│   ├── l2cap/   # L2CAP 协议
│   ├── smp/     # 安全管理协议
│   ├── eatt/    # EATT 增强属性协议
│   ├── rfcomm/  # RFCOMM 协议
│   ├── sdp/     # SDP 服务发现
│   └── acl/     # ACL 连接管理
├── btif/        # 蓝牙接口层（JNI 到 Stack 的桥接）
├── bta/         # 蓝牙应用层（AG/AV/GATT/DM/HFP/LE Audio）
├── osi/         # OS 抽象层（alarm/thread/reactor/mutex/future）
├── types/       # 基础类型（UUID/Address）
├── main/        # 主入口及 Shim 层
├── hci/         # HCI 层（数据分片/缓冲区）
├── packet/      # 数据包定义
└── include/     # 公共头文件
```

### 1.2 各模块职责详解

| 模块 | 职责 | 代码风格 | 关键类/结构体 |
|------|------|---------|-------------|
| `gd/` | GD 新架构，用现代 C++17 重写的协议栈核心 | 现代 C++17 | `Controller`, `AclManager`, `Handler`, `Queue` |
| `stack/` | 传统协议栈实现，各协议的核心逻辑 | C 风格 + 逐步现代化 | `tBTM_SEC_DEV_REC`, `EattExtension`, `tGATT_TCB` |
| `btif/` | JNI 层与协议栈之间的桥接层 | C 风格 | `btgattInterface`, `btif_gatt_init` |
| `bta/` | 蓝牙应用层，管理各 Profile 的状态机 | C 风格 | `BTA_GATTC_Open`, `bta_dm_act` |
| `osi/` | 旧 OS 抽象层，提供线程/定时器/队列等 | C 风格 | `alarm_t`, `fixed_queue_t`, `thread_t` |
| `types/` | 基础数据类型定义 | 现代 C++ | `RawAddress`, `Uuid` |
| `main/shim/` | Shim 层，桥接传统栈和 GD 架构 | 混合 | `Stack`, `GetController()`, `GetScanning()` |

### 1.3 新旧架构的关系与过渡

Android 蓝牙协议栈正在经历从传统 C 风格代码向 GD（Gabeldorsche）现代 C++ 架构的迁移：

```
┌─────────────────────────────────────────────────────────┐
│                    Java Framework                        │
│              (android.bluetooth.*)                       │
├─────────────────────────────────────────────────────────┤
│                    JNI 层                                │
│           (com_android_bluetooth_*)                      │
├─────────────────────────────────────────────────────────┤
│                    btif 层                               │
│          (btif_gatt.cc, btif_dm.cc, ...)                │
├──────────────────────┬──────────────────────────────────┤
│   传统 stack/        │       GD gd/                     │
│   (C 风格)           │    (现代 C++17)                   │
│   - btm/             │    - hci/                        │
│   - gatt/            │    - hal/                        │
│   - l2cap/           │    - os/                         │
│   - smp/             │    - storage/                    │
│   - eatt/            │    - common/                     │
├──────────────────────┴──────────────────────────────────┤
│                    Shim 层 (main/shim/)                  │
│     桥接传统栈 API 和 GD 实现                             │
├─────────────────────────────────────────────────────────┤
│                    HCI 层                                │
│           (gd/hal/ → 硬件)                               │
└─────────────────────────────────────────────────────────┘
```

**迁移趋势**：
- **底层先行**：`gd/hci/`、`gd/hal/`、`gd/os/` 已经完全替代了旧实现
- **逐步上移**：`gd/storage/`、`gd/hci/acl_manager/` 正在替代传统 `stack/btm/` 中的对应功能
- **混合运行**：当前代码库中，传统栈和 GD 架构同时运行，通过 Shim 层协调

### 1.4 Shim 层的作用

Shim 层（`main/shim/`）是新旧架构之间的适配器，它的核心作用是：

1. **桥接传统 API 到 GD 实现**：传统代码调用 `btm_*` 函数时，Shim 层将调用转发到 GD 的对应实现
2. **提供统一的 GD 模块访问入口**：通过 `GetController()`、`GetScanning()` 等函数获取 GD 模块实例
3. **管理 GD 栈的生命周期**：控制 GD 栈的启动和停止

实际代码示例（`main/shim/entry.cc`）：

```cpp
namespace bluetooth {
namespace shim {

// 获取 GD Handler，用于向 GD 线程投递任务
os::Handler* GetGdShimHandler() { return Stack::GetInstance()->GetHandler(); }

// 获取 GD Controller 实例
hci::Controller* GetController() { return Stack::GetInstance()->GetController(); }

// 获取 GD 扫描管理器
hci::LeScanningManager* GetScanning() { return Stack::GetInstance()->GetLeScanningManager(); }

// 获取 GD 广告管理器
hci::LeAdvertisingManager* GetAdvertising() {
  return Stack::GetInstance()->GetLeAdvertisingManager();
}

// 检查 GD 栈是否已启动
bool is_gd_stack_started_up() { return Stack::GetInstance()->IsRunning(); }

}  // namespace shim
}  // namespace bluetooth
```

**Shim 层的关键文件**：

| 文件 | 作用 |
|------|------|
| `main/shim/entry.cc` | GD 模块的统一访问入口 |
| `main/shim/stack.cc` | GD 栈的生命周期管理 |
| `main/shim/acl.cc` | ACL 连接的 Shim 适配 |
| `main/shim/btm_api.cc` | BTM API 的 Shim 适配 |
| `main/shim/le_scanning_manager.cc` | 扫描管理的 Shim 适配 |

### ☕ Java 类比

Android 蓝牙协议栈的代码架构与 Java Framework 层有直接对应关系：

| C++ 层 | Java 层 | 说明 |
|--------|---------|------|
| `system/gd/` | `android.bluetooth.*` (AIDL/HIDL) | GD 新架构对应 Java 接口 |
| `system/stack/` | 无直接对应（内部实现） | 传统协议栈，Java 层不可见 |
| `system/btif/` | `com.android.bluetooth.*` | JNI 桥接层 |
| `system/bta/` | Profile Service 类 | 蓝牙应用层 |
| `system/gd/os/Handler` | `android.os.Handler` | 消息处理 |
| `system/gd/os/Thread` | `android.os.HandlerThread` | 线程抽象 |
| `system/types/RawAddress` | `android.bluetooth.BluetoothDevice` | 设备地址 |
| `system/types/Uuid` | `java.util.UUID` | UUID 类型 |

```
Java Framework (android.bluetooth.BluetoothAdapter)
    ↓ AIDL
Bluetooth Service (com.android.bluetooth.btservice.AdapterService)
    ↓ JNI
btif 层 (system/btif/)
    ↓
Shim 层 (system/main/shim/) ←→ GD 架构 (system/gd/)
    ↓
HCI 层 → 控制器硬件
```

**关键洞察**：Java 开发者熟悉的 `BluetoothAdapter`、`BluetoothGatt` 等 API，最终都通过 JNI 调用到 C++ 协议栈。理解这个分层架构，就能知道 Java 层的 Bug 可能需要到 C++ 层排查。

---

## 2. 代码风格差异

协议栈中存在两种截然不同的代码风格，理解它们的差异是阅读代码的关键。

### 2.1 GD 架构：现代 C++17 风格

**命名空间**：
```cpp
namespace bluetooth {
namespace hci {       // HCI 层
namespace os {        // OS 抽象层
namespace hal {       // 硬件抽象层
namespace storage {   // 存储层
namespace common {    // 通用工具
```

**特征一览**：

| 特征 | 示例 |
|------|------|
| 智能指针 | `std::unique_ptr<impl> pimpl_` |
| 模板 | `template <typename T> class Queue` |
| `constexpr` | `static constexpr uint64_t kDefaultEventMask = 0x3dbfffffffffffff;` |
| `enum class` | `enum class EattChannelState : uint8_t { ... }` |
| `override` | `void RegisterEnqueue(...) override` |
| `= default` / `= delete` | `Controller() = default; Controller(const Controller&) = delete;` |
| `std::optional` | `std::optional<std::string> GetProperty(...)` |
| `base::Callback` / `base::BindOnce` | `common::Callback<std::unique_ptr<T>()>` |
| RAII 资源管理 | 构造函数获取资源，析构函数释放资源 |
| Pimpl 惯用法 | `struct impl; std::unique_ptr<impl> pimpl_;` |

**典型代码片段**（`gd/hci/controller.h`）：

```cpp
namespace bluetooth {
namespace hci {

class Controller {
public:
  static constexpr uint64_t kDefaultEventMask = 0x3dbfffffffffffff;

  Controller() = default;
  virtual ~Controller() = default;

  // 纯虚函数定义接口
  virtual void RegisterCompletedAclPacketsCallback(CompletedAclPacketsCallback cb) = 0;
  virtual std::string GetLocalName() const = 0;
  virtual bool SupportsBle() const = 0;
  virtual Address GetMacAddress() const = 0;
  virtual void Reset() = 0;
  // ... 更多纯虚函数
};

}  // namespace hci
}  // namespace bluetooth
```

**关键观察**：
- 所有方法都是纯虚函数（`= 0`），这是**接口类**的标志
- 实际实现在 `controller_impl.h` / `controller_impl.cc` 中
- 使用 `constexpr` 定义常量，而非 `#define`
- 命名空间清晰，不会污染全局

### 2.2 传统栈：C 风格 + 逐步现代化

**特征一览**：

| 特征 | 示例 |
|------|------|
| `t` 前缀结构体 | `tBTM_SEC_DEV_REC`, `tGATT_TCB`, `tL2CAP_APPL_INFO` |
| 函数指针回调 | `tBTM_CMPL_CB`, `reg_info_.pL2CA_CreditBasedConnectInd_Cb` |
| 全局变量 | `bt_gatt_callbacks = NULL;` |
| `#define` 常量 | `#define EATT_MIN_MTU_MPS (64)` |
| `typedef` 定义 | `typedef struct { ... } tBTM_CFG;` |
| `void*` 参数 | `static void eatt_ind_ack_timeout(void* data)` |
| 逐步引入 `enum class` | `enum tBTM_PAIRING_STATE : uint8_t { ... }` |
| 逐步引入 `std::unique_ptr` | `std::unique_ptr<eatt_impl> eatt_impl_;` |

**典型代码片段**（`stack/btm/btm_sec_int_types.h`）：

```cpp
// 传统 C 风格：typedef struct
typedef struct {
  BD_NAME bd_name;      /* local Bluetooth device name */
  bool pin_type;        /* true if PIN type is fixed */
  uint8_t pin_code_len; /* Bonding information */
  PIN_CODE pin_code;    /* PIN CODE if pin type is fixed */
} tBTM_CFG;

// 过渡风格：enum with underlying type but still typedef
enum tBTM_PAIRING_STATE : uint8_t {
  BTM_PAIR_STATE_IDLE,
  BTM_PAIR_STATE_GET_REM_NAME,
  BTM_PAIR_STATE_WAIT_PIN_REQ,
  // ...
};

// 传统 C 风格：#define 位标志
#define BTM_PAIR_FLAGS_WE_STARTED_DD 0x01
#define BTM_PAIR_FLAGS_PEER_STARTED_DD 0x02
#define BTM_PAIR_FLAGS_DISC_WHEN_DONE 0x04
```

**典型代码片段**（`btif/src/btif_gatt.cc`）：

```cpp
// 传统 C 风格：全局变量
const btgatt_callbacks_t* bt_gatt_callbacks = NULL;

// 传统 C 风格：函数指针表（类似虚函数表）
static btgatt_interface_t btgattInterface = {
    .size = sizeof(btgattInterface),
    .init = btif_gatt_init,
    .cleanup = btif_gatt_cleanup,
    // ...
};
```

### 2.3 两种风格的对比速查

| 维度 | GD 架构 | 传统栈 |
|------|---------|--------|
| 命名空间 | `bluetooth::hci`, `bluetooth::os` | 全局或 `bluetooth::eatt` |
| 类定义 | `class Controller { ... };` | `typedef struct { ... } tXXX;` |
| 常量 | `constexpr` / `const` | `#define` |
| 回调 | `base::Callback` / `base::BindOnce` | 函数指针 |
| 资源管理 | RAII（智能指针） | 手动 `osi_malloc` / `osi_free` |
| 空指针 | `nullptr` | `NULL` |
| 字符串 | `std::string` | `char[]` / `BD_NAME` |
| 容器 | `std::vector`, `std::map` | 手动链表 / `fixed_queue_t` |
| 错误处理 | `log::assert_that` | `log::assert_that`（统一） |
| 日志 | `log::info`, `log::warn`, `log::error` | 同左（已统一） |

### 2.4 EATT 模块：新旧风格混合的典型案例

EATT（`stack/eatt/`）是一个极好的学习案例，它同时展现了两种风格：

```cpp
// eatt.h - 对外接口使用现代 C++ 风格
namespace bluetooth {
namespace eatt {

enum class EattChannelState : uint8_t {          // ← enum class（现代）
  EATT_CHANNEL_PENDING = 0x00,
  EATT_CHANNEL_OPENED,
  EATT_CHANNEL_RECONFIGURING,
};

class EattExtension {
public:
  static EattExtension* GetInstance() {           // ← 单例模式
    static EattExtension* instance = new EattExtension();
    return instance;
  }
  virtual void Connect(const RawAddress& bd_addr); // ← 虚函数接口
private:
  struct impl;                                     // ← Pimpl 惯用法
  std::unique_ptr<impl> pimpl_;                    // ← 智能指针
};

}  // namespace eatt
}  // namespace bluetooth
```

```cpp
// eatt_impl.h - 内部实现混合使用两种风格
struct eatt_impl {
  std::vector<eatt_device> devices_;               // ← STL 容器（现代）
  base::WeakPtrFactory<eatt_impl> weak_factory_{this}; // ← WeakPtr（现代）

  // 但回调注册使用传统函数指针
  tL2CAP_APPL_INFO reg_info_;                      // ← 传统 C 结构体

  // 定时器使用传统 osi 接口
  alarm_set_on_mloop(channel->ind_confirmation_timer_,
                     GATT_WAIT_FOR_RSP_TIMEOUT_MS,
                     eatt_ind_confirmation_timeout,  // ← 函数指针回调
                     channel);                       // ← void* 数据
};
```

### ☕ Java 类比

C++ 协议栈的两种代码风格在 Java 中有直接对应：

| C++ 风格 | Java 对应 | 说明 |
|----------|----------|------|
| GD 架构（现代 C++17） | Java 标准写法 | 面向对象、泛型、lambda |
| 传统栈（C 风格） | 无直接对应 | Java 没有这种风格 |
| `typedef struct { ... } tXXX;` | `class XXX { ... }` | Java 只有类 |
| 函数指针回调 | 接口回调 / Lambda | Java 用接口替代 |
| `#define` 常量 | `static final` 常量 | Java 用 `final` |
| `void*` 参数 | 泛型 `<T>` | Java 用泛型保证类型安全 |
| `NULL` | `null` | Java 统一用 `null` |
| `std::unique_ptr<impl> pimpl_` | 接口 + 实现类分离 | Java 用接口隐藏实现 |

```cpp
// C++ 传统栈：C 风格
typedef struct {
  BD_NAME bd_name;
  bool pin_type;
} tBTM_CFG;

#define BTM_PAIR_FLAGS_WE_STARTED_DD 0x01
```

```java
// Java：面向对象风格
public class BtmConfig {
    private String bdName;
    private boolean pinType;

    public static final int PAIR_FLAGS_WE_STARTED_DD = 0x01;
}
```

**关键洞察**：Java 开发者在阅读 GD 架构代码时会感到熟悉（面向对象、智能指针、lambda），但阅读传统栈代码时需要适应 C 风格的写法（函数指针、`void*`、全局变量）。

---

## 3. 如何阅读一个头文件

阅读头文件是理解协议栈代码最重要的技能。以下是系统化的五步法。

### 3.1 五步阅读法

#### 步骤 1：看类名和注释

类名通常直接反映模块的职责。注释（如果有）会告诉你这个类做什么。

```
EattExtension  →  EATT（Enhanced ATT）的扩展管理类
Controller     →  蓝牙控制器的抽象接口
HciHal         →  HCI 硬件抽象层
```

#### 步骤 2：看 public 方法（接口）

public 方法定义了这个类能做什么，是理解其功能的最快途径。重点关注：
- **动词开头的方法**：`Connect()`, `Disconnect()`, `Start()`, `Stop()`
- **查询方法**：`IsEattSupportedByPeer()`, `FindEattChannelByCid()`
- **注册方法**：`RegisterCompletedAclPacketsCallback()`

#### 步骤 3：看 private 成员（状态）

private 成员揭示了类的内部状态和数据结构：
- `std::unique_ptr<impl> pimpl_` → 使用了 Pimpl 惯用法，实现在 .cc 文件中
- `std::map<uint16_t, std::shared_ptr<EattChannel>>` → 通道映射表
- `alarm_t*` → 使用了传统 osi 定时器

#### 步骤 4：看继承关系

继承关系告诉你这个类在层次结构中的位置：
- 继承自纯虚类 → 这是一个接口的实现
- 被其他类继承 → 这是一个基类或接口定义
- `final` 关键字 → 不能被继承

#### 步骤 5：看构造函数和析构函数

- `= default` → 使用编译器默认实现
- `= delete` → 禁止拷贝/赋值（单例模式常见）
- `virtual ~XXX() = default` → 多态基类，允许通过基类指针释放
- `explicit` → 禁止隐式转换

### 3.2 实战：逐行阅读 EattExtension（eatt.h:109-286）

让我们用五步法来阅读 `EattExtension` 类：

```
第 109 行: class EattExtension {
           ↑ 步骤1：这是 EATT 扩展的管理类

第 111 行: EattExtension();
           ↑ 步骤5：有自定义构造函数

第 112 行: EattExtension(const EattExtension&) = delete;
第 113 行: EattExtension& operator=(const EattExtension&) = delete;
           ↑ 步骤5：禁止拷贝和赋值 → 单例模式常见做法

第 115 行: virtual ~EattExtension();
           ↑ 步骤5：虚析构函数 → 可能被继承

第 117-120 行: static EattExtension* GetInstance() {
                 static EattExtension* instance = new EattExtension();
                 return instance;
               }
           ↑ 步骤2：单例模式入口！全局唯一实例
           ↑ 注意：这里使用 new 而非 make_unique，实例永不销毁

第 122 行: static void AddFromStorage(const RawAddress& bd_addr);
           ↑ 步骤2：从持久化存储恢复设备

第 129 行: virtual bool IsEattSupportedByPeer(const RawAddress& bd_addr);
           ↑ 步骤2：查询远端是否支持 EATT

第 136 行: virtual void Connect(const RawAddress& bd_addr);
           ↑ 步骤2：发起 EATT 连接

第 144 行: virtual void Disconnect(const RawAddress& bd_addr, uint16_t cid = EATT_ALL_CIDS);
           ↑ 步骤2：断开 EATT 连接，默认断开所有通道

第 153 行: virtual void Reconfigure(const RawAddress& bd_addr, uint16_t cid, uint16_t mtu);
第 161 行: virtual void ReconfigureAll(const RawAddress& bd_addr, uint16_t mtu);
           ↑ 步骤2：重配置通道参数

第 173-271 行: FindEattChannelByCid, FindEattChannelByTransId,
               IsIndicationPending, GetChannelAvailableForIndication,
               FreeGattResources, IsOutstandingMsgInSendQueue,
               GetChannelWithQueuedDataToSend, GetChannelAvailableForClientRequest,
               StartIndicationConfirmationTimer, StopIndicationConfirmationTimer,
               StartAppIndicationTimer, StopAppIndicationTimer
           ↑ 步骤2：这些是 GATT 实现所需的辅助方法
           ↑ 方法名非常自解释，如"查找通道"、"启动定时器"

第 276-281 行: void Start(); void Stop();
           ↑ 步骤2：模块生命周期管理

第 283-285 行: private:
                struct impl;
                std::unique_ptr<impl> pimpl_;
           ↑ 步骤3：Pimpl 惯用法！
           ↑ 实际数据成员隐藏在 impl 结构中（定义在 eatt.cc 里）
           ↑ 好处：修改内部实现不需要重新编译引用头文件的代码
```

**阅读结论**：

`EattExtension` 是 EATT 模块的单例管理类，提供 EATT 通道的创建、查找、重配置和销毁功能。它使用 Pimpl 惯用法隐藏实现细节，所有 public 方法都是虚函数（便于测试时 mock）。内部实现委托给 `eatt_impl` 结构体。

### ☕ Java 类比

C++ 的头文件阅读方法在 Java 中有对应，但 Java 的类结构更简单：

| C++ 头文件阅读 | Java 类阅读 | 说明 |
|---------------|------------|------|
| 看类名和注释 | 看类名和 Javadoc | 相同 |
| 看 public 方法 | 看 public 方法 | 相同 |
| 看 private 成员 | 看 private 字段 | 相同 |
| 看继承关系 | 看 `extends`/`implements` | Java 更明确 |
| 看构造/析构函数 | 看构造函数 | Java 无析构函数 |
| 看 `friend` 声明 | 无等价 | Java 无友元 |
| 看 `= delete` | 无等价 | Java 引用赋值天然安全 |
| 看 Pimpl (`unique_ptr<impl>`) | 看接口 + Impl 类 | Java 用接口隐藏实现 |
| 头文件 `.h` + 实现文件 `.cc` | 一个 `.java` 文件 | Java 更简洁 |

```cpp
// C++：头文件声明 + Pimpl 隐藏实现
class EattExtension {
public:
  virtual void Connect(const RawAddress& bd_addr);
private:
  struct impl;
  std::unique_ptr<impl> pimpl_;  // 实现细节在 .cc 文件
};
```

```java
// Java：接口 + 实现类分离
public interface EattExtension {
    void connect(BluetoothDevice device);
}

public class EattExtensionImpl implements EattExtension {
    @Override
    public void connect(BluetoothDevice device) {
        // 实现细节
    }
}
```

**关键差异**：C++ 的头文件/实现文件分离和 Pimpl 惯用法，在 Java 中通常用接口/实现类分离来替代。Java 开发者阅读 C++ 头文件时，可以将 `.h` 文件类比为 Java 的接口，将 `.cc` 文件类比为 Java 的实现类。

---

## 4. 如何跟踪函数调用链

### 4.1 从 Java 层到协议栈的完整路径

Android 蓝牙的调用链通常遵循以下路径：

```
Java API (android.bluetooth.*)
    ↓ JNI 调用
JNI 层 (packages/apps/Bluetooth/jni/)
    ↓ C 函数调用
btif 层 (system/btif/src/)
    ↓ 通过 Shim 或直接调用
stack/ 或 gd/ 层
    ↓ 通过 HAL
HCI 命令发送到控制器
```

### 4.2 使用 IDE 的导航功能

| 操作 | 快捷键（VS Code） | 用途 |
|------|-------------------|------|
| Go to Definition | F12 | 跳转到函数/类的定义 |
| Find Usages | Shift+F12 | 查找函数/类的所有使用位置 |
| Go to Implementation | Ctrl+F12 | 跳转到接口的实现类 |
| Go to Declaration | 无默认 | 查看前向声明 |
| Find in Files | Ctrl+Shift+F | 全局搜索 |

### 4.3 使用 grep 搜索函数名

当 IDE 索引不完整时，grep 是最可靠的搜索方式：

```bash
# 搜索函数定义
grep -rn "EattExtension::Connect" system/

# 搜索类定义
grep -rn "class EattExtension" system/

# 搜索回调注册
grep -rn "RegisterCompletedAclPacketsCallback" system/

# 搜索枚举值
grep -rn "EATT_CHANNEL_OPENED" system/

# 搜索接口实现（override 关键字）
grep -rn "void OnLeConnectSuccess.*override" system/
```

### 4.4 实战：跟踪一次 BLE 连接请求的完整路径

以下是从 Java 层发起 BLE 连接的完整调用链：

```
1. Java: BluetoothGatt.connect()
   ↓
2. JNI: sGattClientConnectNative()
   ↓
3. btif: btif_gattc_open_impl()
   文件: system/btif/src/btif_gatt.cc
   ↓
4. BTA: BTA_GATTC_Open()
   文件: system/bta/gatt/bta_gattc_api.cc
   ↓
5. GATT: GATT_Connect()
   文件: system/stack/gatt/gatt_api.cc
   ↓
6. BTM: BTM_CreateLeConnection()
   文件: system/stack/btm/btm_ble.cc
   ↓
7. Shim: 通过 shim::GetAclManagerLe() 获取 GD AclManager
   文件: system/main/shim/entry.cc
   ↓
8. GD: AclManagerLe::CreateLeConnection()
   文件: system/gd/hci/acl_manager/acl_manager_le.h
   ↓
9. GD: 发送 HCI LE Create Connection 命令
   文件: system/gd/hci/acl_manager/acl_manager_le_impl.cc
   ↓
10. HAL: HciHal::sendHciCommand()
    文件: system/gd/hal/hci_hal.h
    ↓
11. 控制器硬件
```

**关键跟踪技巧**：
- 每一层的函数名通常遵循该层的命名规范（如 `BTA_GATTC_*`、`GATT_*`、`BTM_*`）
- `btif` 层是 Java 和 C++ 之间的桥梁，所有 Java 调用都经过这里
- `BTA` 层管理 Profile 状态机，是业务逻辑的核心
- `stack` 层是协议实现，`gd/` 是正在替换的新实现

### ☕ Java 类比

从 Java 层到 C++ 协议栈的调用链是 Android 蓝牙开发的核心知识：

| 调用层 | Java 侧 | C++ 侧 | 桥接方式 |
|--------|---------|---------|---------|
| Java API | `BluetoothGatt.connect()` | — | — |
| JNI 层 | `sGattClientConnectNative()` | `btif_gattc_open_impl()` | JNI `native` 方法 |
| btif 层 | — | `btif_gattc_open_impl()` | C 函数调用 |
| BTA 层 | — | `BTA_GATTC_Open()` | C 函数调用 |
| Stack 层 | — | `GATT_Connect()` → `BTM_CreateLeConnection()` | C 函数调用 |
| Shim 层 | — | `shim::GetAclManagerLe()` | C++ 函数调用 |
| GD 层 | — | `AclManagerLe::CreateLeConnection()` | C++ 方法调用 |
| HAL 层 | — | `HciHal::sendHciCommand()` | C++ 方法调用 |

```java
// Java 层：BluetoothGatt.connect()
public class BluetoothGatt {
    public boolean connect() {
        // 调用 JNI 层
        mService.clientConnect(mClientIf, mDevice.getAddress(),
                               mDevice.getType(), false);  // → AIDL
    }
}

// JNI 层：com_android_bluetooth_gatt.cpp
static void gattClientConnectNative(JNIEnv* env, jobject obj, ...) {
    // 调用 btif 层
    btif_gattc_open_impl(client_if, bdaddr, transport, initiating);  // → C++
}
```

**关键洞察**：Java 开发者追踪 Bug 时，可以从 Java API 入手，通过 JNI 桥接追踪到 C++ 层。Android Studio 可以调试 Java 层，C++ 层需要用 GDB/LLDB。

---

## 5. 如何理解回调机制

回调是蓝牙协议栈中最核心的异步通信机制。理解回调的注册和触发是追踪代码流程的关键。

### 5.1 传统栈的函数指针回调

传统栈使用 `tL2CAP_APPL_INFO` 结构体注册一组回调函数：

```cpp
// eatt.cc 中的回调注册
memset(&reg_info_, 0, sizeof(reg_info_));
reg_info_.pL2CA_CreditBasedConnectInd_Cb = eatt_connect_ind;     // 连接指示
reg_info_.pL2CA_CreditBasedConnectCfm_Cb = eatt_connect_cfm;     // 连接确认
reg_info_.pL2CA_CreditBasedReconfigCompleted_Cb = eatt_reconfig_completed; // 重配置完成
reg_info_.pL2CA_DisconnectInd_Cb = eatt_disconnect_ind;          // 断开指示
reg_info_.pL2CA_Error_Cb = eatt_error_cb;                        // 错误回调
reg_info_.pL2CA_DataInd_Cb = eatt_data_ind;                      // 数据到达
reg_info_.pL2CA_CreditBasedCollisionInd_Cb = eatt_collision_ind; // 碰撞指示

// 注册到 L2CAP 层
stack::l2cap::get_interface().L2CA_RegisterLECoc(BT_PSM_EATT, reg_info_, ...);
```

**回调函数的签名模式**：

```cpp
// 连接指示回调：远端发起连接时触发
static void eatt_connect_ind(const RawAddress& bda, std::vector<uint16_t>& lcids,
                             uint16_t psm, uint16_t peer_mtu, uint8_t identifier);

// 连接确认回调：本地发起连接的结果
static void eatt_connect_cfm(const RawAddress& bda, uint16_t lcid,
                             uint16_t peer_mtu, tL2CAP_LE_RESULT_CODE result);

// 数据到达回调
static void eatt_data_ind(uint16_t lcid, BT_HDR* data_p);

// 定时器回调（最原始的 C 风格）
static void eatt_ind_confirmation_timeout(void* data);  // void* 指向 EattChannel
```

**传统回调的问题**：
- `void*` 参数缺乏类型安全
- 静态函数需要通过 `GetInstance()` 获取单例来访问成员
- 回调注册和触发分散在不同文件中

### 5.2 GD 架构的 base::Callback / BindOnce

GD 架构使用 Chromium 的 callback 机制，提供类型安全和生命周期管理：

```cpp
// callback.h 中的类型别名
namespace bluetooth {
namespace common {
using base::Callback;       // 可重复调用的回调
using base::OnceCallback;   // 只能调用一次的回调
using base::OnceClosure;    // 无参数的一次性回调
}  // namespace common
}  // namespace bluetooth
```

**GD 中的回调使用模式**：

```cpp
// 1. 定义回调类型
using CompletedAclPacketsCallback =
    common::ContextualCallback<void(uint16_t handle, uint16_t num_packets)>;

// 2. 注册回调
virtual void RegisterCompletedAclPacketsCallback(CompletedAclPacketsCallback cb) = 0;

// 3. 使用 BindOnce 绑定成员函数
handler->CallOn(this, &MyClass::OnConnectionComplete);

// 4. 使用 Bind 绑定可重复回调
queue->RegisterEnqueue(handler,
    common::Bind(&EnqueueBuffer<T>::enqueue_callback, common::Unretained(this)));
```

**`BindOnce` vs `Bind` 的区别**：

| 特性 | `BindOnce` | `Bind` |
|------|-----------|--------|
| 调用次数 | 只能调用一次 | 可以重复调用 |
| 所有权 | 转移（move 语义） | 共享 |
| 使用场景 | 一次性事件（连接结果） | 持续事件（数据就绪） |

**指针包装器的选择**：

| 包装器 | 含义 | 使用场景 |
|--------|------|---------|
| `common::Unretained(ptr)` | 裸指针，不管理生命周期 | 回调在同一个对象生命周期内执行 |
| `base::Owned(ptr)` | 回调执行后自动 delete | 转移所有权给回调 |
| `weak_factory_.GetWeakPtr()` | 弱指针，对象销毁后回调不执行 | 异步回调，对象可能提前销毁 |

### 5.3 回调注册与触发的对应关系

理解回调的关键是找到"注册"和"触发"的对应关系：

```
注册端（谁在监听）                    触发端（谁在通知）
─────────────────                    ─────────────────
L2CA_RegisterLECoc(reg_info_)   ←→   L2CAP 层在事件发生时调用 reg_info_ 中的回调
RegisterCompletedAclPacketsCallback  ←→   HCI 层在 ACL 包完成时调用回调
RegisterDequeue(handler, cb)    ←→   Queue 有数据时通过 Reactor 唤醒 handler
```

### 5.4 实战：跟踪 EATT 连接回调

让我们追踪 EATT 连接成功后的回调链：

```
1. L2CAP 层收到连接确认事件
   ↓
2. L2CAP 调用 reg_info_.pL2CA_CreditBasedConnectCfm_Cb
   即 EattExtension::impl::eatt_connect_cfm()
   文件: system/stack/eatt/eatt.cc:89
   ↓
3. eatt_connect_cfm() 通过 GetImplInstance() 获取 eatt_impl
   ↓
4. 调用 eatt_impl->eatt_l2cap_connect_cfm()
   文件: system/stack/eatt/eatt_impl.h:372
   ↓
5. 更新通道状态:
   channel->EattChannelSetState(EattChannelState::EATT_CHANNEL_OPENED)
   channel->EattChannelSetTxMTU(peer_mtu)
   ↓
6. 通知 GATT 层:
   eatt_dev->eatt_tcb_->eatt++  // 增加 EATT 通道计数
```

**关键发现**：
- 静态函数 `eatt_connect_cfm` 是中间跳板，它通过 `GetImplInstance()` 获取实例
- 这是因为传统 C 函数指针无法直接绑定到 C++ 成员函数
- GD 架构通过 `base::Bind` 解决了这个问题

### ☕ Java 类比

C++ 协议栈的回调机制与 Java 的接口回调有直接对应：

| C++ 回调机制 | Java 对应 | 说明 |
|-------------|----------|------|
| 函数指针 + `void*` | 接口回调 | Java 用接口替代函数指针 |
| `tL2CAP_APPL_INFO` 结构体 | `L2capCallback` 接口 | Java 用接口封装回调组 |
| `base::Callback` / `BindOnce` | Lambda / 方法引用 | Java 更简洁 |
| `base::WeakPtr` | `WeakReference` | 防止 use-after-free |
| `common::Unretained` | 直接引用 | Java 引用天然安全 |
| 静态函数 + `GetInstance()` | 实例方法 | Java 直接用实例方法 |

```cpp
// C++：传统栈的函数指针回调
reg_info_.pL2CA_CreditBasedConnectInd_Cb = eatt_connect_ind;
// eatt_connect_ind 是静态函数，需要通过 GetInstance() 获取实例
static void eatt_connect_ind(const RawAddress& bda, ...) {
    GetImplInstance()->eatt_l2cap_connect_ind(bda, ...);
}
```

```java
// Java：接口回调
public interface L2capCallback {
    void onConnectInd(BluetoothDevice device, int[] lcids, int psm, int peerMtu);
}

// 注册回调
l2capManager.registerCallback(new L2capCallback() {
    @Override
    public void onConnectInd(BluetoothDevice device, int[] lcids, ...) {
        // 直接访问实例方法，无需 GetInstance()
        handleConnectInd(device, lcids, ...);
    }
});

// 或用 Lambda
l2capManager.registerCallback((device, lcids, psm, peerMtu) ->
    handleConnectInd(device, lcids, ...));
```

**关键差异**：C++ 的函数指针无法直接绑定到成员函数，需要通过静态函数 + `GetInstance()` 中转；Java 的接口回调和 Lambda 天然支持实例方法引用，代码更简洁。

---

## 6. 常用搜索模式

### 6.1 搜索类定义

```bash
# 搜索类定义
grep -rn "class EattExtension" system/
grep -rn "class Controller" system/gd/

# 搜索结构体定义
grep -rn "struct eatt_impl" system/
grep -rn "typedef struct" system/stack/btm/
```

### 6.2 搜索函数实现

```bash
# 搜索成员函数实现（类名::函数名）
grep -rn "EattExtension::Connect" system/
grep -rn "Controller::Reset" system/gd/

# 搜索自由函数实现
grep -rn "^void BTM_CreateLeConnection" system/
grep -rn "^bool BTA_GATTC_Open" system/
```

### 6.3 搜索回调注册

```bash
# 搜索回调注册函数
grep -rn "RegisterCompletedAclPacketsCallback" system/
grep -rn "RegisterIncomingPacketCallback" system/
grep -rn "L2CA_RegisterLECoc" system/

# 搜索回调结构体赋值
grep -rn "pL2CA_CreditBasedConnectInd_Cb" system/
grep -rn "pL2CA_DataInd_Cb" system/
```

### 6.4 搜索接口实现

```bash
# 搜索 override 关键字（找到接口的实现）
grep -rn "void OnLeConnectSuccess.*override" system/gd/
grep -rn "void hciEventReceived.*override" system/gd/

# 搜索纯虚函数的实现类
grep -rn "class.*: public Controller" system/gd/
grep -rn "class.*: public HciHal" system/gd/
```

### 6.5 搜索枚举值

```bash
# 搜索枚举值的使用位置
grep -rn "EATT_CHANNEL_OPENED" system/
grep -rn "L2CAP_LE_RESULT_CONN_OK" system/
grep -rn "HCI_ROLE_CENTRAL" system/
```

### 6.6 搜索模式速查表

| 目的 | 搜索模式 | 示例 |
|------|---------|------|
| 找类定义 | `class ClassName` | `class EattExtension` |
| 找函数实现 | `ClassName::MethodName` | `EattExtension::Connect` |
| 找回调注册 | `RegisterXxxCallback` | `RegisterCompletedAclPacketsCallback` |
| 找接口实现 | `override` | `OnLeConnectSuccess.*override` |
| 找枚举值 | `ENUM_VALUE` | `EATT_CHANNEL_OPENED` |
| 找宏定义 | `#define MACRO_NAME` | `#define EATT_MIN_MTU_MPS` |
| 找全局变量 | `变量名.*=` | `bt_gatt_callbacks` |
| 找头文件包含 | `#include.*filename` | `#include.*eatt.h` |

### ☕ Java 类比

C++ 的代码搜索模式在 Java 中有对应，但 Java IDE 的支持更强大：

| C++ 搜索方式 | Java 对应 | 说明 |
|-------------|----------|------|
| `grep -rn "class EattExtension"` | IDE: Find Class | Java IDE 直接支持 |
| `grep -rn "EattExtension::Connect"` | IDE: Go to Implementation | Ctrl+Click |
| `grep -rn "RegisterXxxCallback"` | IDE: Find Usages | Shift+F12 |
| `grep -rn "override"` | IDE: Go to Implementation | Ctrl+F12 |
| `grep -rn "EATT_CHANNEL_OPENED"` | IDE: Find Usages | Alt+F7 |
| grep（命令行） | IDE 搜索 / `jd-gui` | Java 更依赖 IDE |

```bash
# C++：grep 搜索函数定义
grep -rn "EattExtension::Connect" system/
grep -rn "class EattExtension" system/
```

```java
// Java：IDE 直接导航
// 1. Ctrl+Click 方法名 → 跳转到定义
// 2. Ctrl+Alt+B → 跳转到接口的实现
// 3. Alt+F7 → 查找所有使用位置
// 4. Ctrl+Shift+F → 全局搜索
```

**关键差异**：C++ 项目中 grep 是最可靠的搜索方式（IDE 索引可能不完整），Java 项目中 IDE 的导航功能更强大。但在 Android 蓝牙这种跨语言项目中，grep 仍然是追踪 JNI 边界的必备工具。

---

## 7. 关键设计模式速查

### 7.1 设计模式总览

| 模式 | 在协议栈中的体现 | 代码位置 |
|------|-----------------|---------|
| **单例** | `EattExtension::GetInstance()` | `stack/eatt/eatt.h:117` |
| **Pimpl** | `EattExtension::pimpl_` | `stack/eatt/eatt.h:284-285` |
| **接口抽象** | `Controller`（纯虚类） | `gd/hci/controller.h` |
| **观察者** | `ScanningCallback` 回调注册/通知 | `gd/hci/le_scanning_callback.h` |
| **状态机** | `EattChannelState` | `stack/eatt/eatt.h:37-41` |
| **生产者-消费者** | `Queue` + `Handler` | `gd/os/queue.h` |
| **Reactor** | `os::Reactor` + `Handler` | `gd/os/reactor.h` |
| **桥接（Bridge/Shim）** | `main/shim/` 层 | `main/shim/entry.cc` |
| **弱引用** | `base::WeakPtrFactory` | `stack/eatt/eatt_impl.h:72` |
| **工厂方法** | `Stack::GetInstance()->GetController()` | `main/shim/entry.cc` |

### 7.2 单例模式

协议栈中大量使用单例模式来管理全局状态：

```cpp
// 经典单例 - EattExtension
static EattExtension* GetInstance() {
  static EattExtension* instance = new EattExtension();
  return instance;
}

// 通过 Stack 单例获取子模块 - entry.cc
hci::Controller* GetController() {
  return Stack::GetInstance()->GetController();
}
```

**注意**：`new` 出的单例不会被 `delete`，这是有意为之——协议栈的生命周期与进程相同。

### 7.3 Pimpl 惯用法

Pimpl（Pointer to Implementation）用于隐藏实现细节，减少头文件依赖：

```cpp
// eatt.h - 头文件只声明 impl 结构体
class EattExtension {
private:
  struct impl;                      // 前向声明
  std::unique_ptr<impl> pimpl_;     // 智能指针管理
};

// eatt.cc - 在 .cc 文件中定义 impl
struct EattExtension::impl {
  std::unique_ptr<eatt_impl> eatt_impl_;
  tL2CAP_APPL_INFO reg_info_;
  // ... 所有内部状态
};
```

**好处**：
- 修改 `impl` 不需要重新编译引用 `eatt.h` 的代码
- 头文件更简洁，只暴露公共接口
- 编译时间缩短

### 7.4 接口抽象

GD 架构广泛使用纯虚类定义接口：

```cpp
// controller.h - 纯虚接口
class Controller {
public:
  virtual ~Controller() = default;
  virtual std::string GetLocalName() const = 0;
  virtual bool SupportsBle() const = 0;
  virtual void Reset() = 0;
};

// controller_impl.h - 具体实现
class ControllerImpl : public Controller {
public:
  std::string GetLocalName() const override;
  bool SupportsBle() const override;
  void Reset() override;
};
```

**识别方法**：
- 头文件中全是 `virtual ... = 0` → 这是接口定义
- 文件名带 `_impl` → 这是接口的实现
- 文件名带 `_fake` → 这是测试用的假实现

### 7.5 观察者模式

GD 架构通过虚函数回调实现观察者模式：

```cpp
// 定义观察者接口
class LeConnectionCallbacks {
public:
  virtual ~LeConnectionCallbacks() = default;
  virtual void OnLeConnectSuccess(AddressWithType, std::unique_ptr<LeAclConnection>) = 0;
  virtual void OnLeConnectFail(AddressWithType, ErrorCode reason) = 0;
};

// 注册观察者
void RegisterCallbacks(LeConnectionCallbacks* callbacks);

// 通知观察者（在实现类中）
callbacks_->OnLeConnectSuccess(address, std::move(connection));
```

### 7.6 状态机模式

协议栈中大量使用状态机管理连接和通道的生命周期：

```cpp
// EATT 通道状态
enum class EattChannelState : uint8_t {
  EATT_CHANNEL_PENDING = 0x00,      // 连接中
  EATT_CHANNEL_OPENED,              // 已连接
  EATT_CHANNEL_RECONFIGURING,       // 重配置中
};

// 状态转换逻辑
void EattChannelSetState(EattChannelState state) {
  if (state_ == EattChannelState::EATT_CHANNEL_PENDING) {
    if (state == EattChannelState::EATT_CHANNEL_OPENED) {
      // PENDING → OPENED：初始化定时器等资源
      ind_ack_timer_ = alarm_new("eatt_ind_ack_timer_...");
      ind_confirmation_timer_ = alarm_new("eatt_ind_conf_timer_...");
    }
  }
  state_ = state;
}
```

### 7.7 生产者-消费者模式

`Queue` + `Handler` 实现了线程安全的生产者-消费者模式：

```cpp
// 生产者端：注册 Enqueue 回调
queue->RegisterEnqueue(handler,
    common::Bind(&MyClass::produce_data, common::Unretained(this)));

// 消费者端：注册 Dequeue 回调
queue->RegisterDequeue(handler,
    common::Bind(&MyClass::consume_data, common::Unretained(this)));

// 取消注册
queue->UnregisterEnqueue();
queue->UnregisterDequeue();
```

**BidiQueue** 是双向队列，用于上下层之间的双向数据传输：

```cpp
// BidiQueue 连接两个层
BidiQueue<AclPacket, AclPacket> acl_queue_(10);

// 上层使用 UpEnd
auto* up_end = acl_queue_.GetUpEnd();
up_end->RegisterDequeue(handler, ...);  // 接收来自下层的数据
up_end->RegisterEnqueue(handler, ...);  // 发送数据到下层

// 下层使用 DownEnd
auto* down_end = acl_queue_.GetDownEnd();
down_end->RegisterDequeue(handler, ...);  // 接收来自上层的数据
down_end->RegisterEnqueue(handler, ...);  // 发送数据到上层
```

### 7.8 Reactor 模式

Reactor 是 GD 架构的事件驱动核心：

```
┌──────────────────────────────────────────┐
│              Thread                       │
│  ┌────────────────────────────────────┐  │
│  │           Reactor                  │  │
│  │                                    │  │
│  │  epoll_wait() ──┬─→ on_read_ready │  │
│  │                 ├─→ on_read_ready │  │
│  │                 └─→ on_read_ready │  │
│  │                                    │  │
│  │  Reactable 1: Handler (event fd)   │  │
│  │  Reactable 2: Queue (semaphore)    │  │
│  │  Reactable 3: Alarm (timer fd)     │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

```cpp
// Handler 向 Reactor 注册事件
class Handler {
  // 构造时注册 reactable
  explicit Handler(Thread* thread) {
    reactable_ = thread->GetReactor()->Register(
        event_->Id(),                    // 监听的 fd
        base::Bind(&Handler::handle_next_event, base::Unretained(this)),  // 读就绪回调
        base::Closure()                  // 写就绪回调（空）
    );
  }
};

// Post 任务到 Handler
handler->Post(common::BindOnce(&MyClass::DoSomething, common::Unretained(this)));
// → 写入 event fd → Reactor 被唤醒 → handle_next_event → 执行任务
```

### ☕ Java 类比

C++ 协议栈中的设计模式在 Java 中有直接对应：

| C++ 设计模式 | Java 对应 | 说明 |
|-------------|----------|------|
| 单例 `GetInstance()` | `static getInstance()` | 相同模式 |
| Pimpl `unique_ptr<impl>` | 接口 + Impl 类 | Java 用接口隐藏实现 |
| 纯虚接口 `= 0` | `interface` | Java 接口更标准 |
| 观察者 `ScanningCallback` | `Listener` / `Callback` 接口 | 相同模式 |
| 状态机 `EattChannelState` | `enum` + `switch` | 相同模式 |
| 生产者-消费者 `Queue<T>` | `BlockingQueue<T>` | Java 有标准实现 |
| Reactor `epoll + Handler` | `Looper + Handler` | Android 核心机制 |
| 桥接/Shim | `Adapter` / `Wrapper` 模式 | 相同模式 |
| 弱引用 `WeakPtrFactory` | `WeakReference<T>` | 相同概念 |

```cpp
// C++：Pimpl 惯用法
class EattExtension {
private:
  struct impl;
  std::unique_ptr<impl> pimpl_;
};
```

```java
// Java：接口 + Impl 类
public interface EattExtension {
    void connect(BluetoothDevice device);
}

class EattExtensionImpl implements EattExtension {
    // 实现细节
}
```

**关键洞察**：设计模式是语言无关的。Java 开发者已经熟悉这些模式，只是 C++ 的实现方式不同（如 Pimpl vs 接口/Impl 分离）。理解了模式，就能快速理解 C++ 代码的意图。

---

## 8. 调试技巧

### 8.1 使用日志跟踪执行流程

协议栈使用统一的日志系统：

```cpp
#include <bluetooth/log.h>

// 四个级别
log::info("Channel connected CID 0x{:x}", cid);
log::warn("Channel for cid: 0x{:x} is not established", lcid);
log::error("Unknown cid: 0x{:x}", lcid);
log::assert_that(condition, "assert failed: condition");
```

**日志标签**：每个模块有自己的 LOG_TAG，如 `"bt_btif_gatt"`、`"bt_eatt"`

**格式化**：使用 C++20 风格的 `fmt::format` 语法：
- `{:x}` → 十六进制
- `{}` → 默认格式
- `{:c}` → 字符

**在代码中添加临时日志**：

```cpp
// 在你想追踪的函数入口添加
log::info(">>> ENTER: MyFunction, addr={}, cid={:#x}", bd_addr, cid);

// 在关键分支添加
log::info(">>> BRANCH: state={}, result={}", (int)state, (int)result);
```

### 8.2 使用 SnoopLogger 抓取 HCI 日志

SnoopLogger 记录所有 HCI 通信，是调试蓝牙问题的利器：

```cpp
// gd/hal/snoop_logger.h
// SnoopLogger 自动记录所有通过 HciHal 的 HCI 包

// 在设备上启用
adb shell setprop persist.bluetooth.btsnoopenable true

// 抓取日志
adb pull /data/misc/bluetooth/logs/btsnoop_hci.log

// 使用 Wireshark 分析
wireshark btsnoop_hci.log
```

### 8.3 使用 GDB/LLDB 断点调试

```bash
# 附加到蓝牙进程
adb shell gdbserver :5039 --attach $(pidof com.android.bluetooth)

# 端口转发
adb forward tcp:5039 tcp:5039

# GDB 命令
gdb
(gdb) target remote :5039
(gdb) break bluetooth::eatt::EattExtension::Connect
(gdb) break eatt_l2cap_connect_cfm
(gdb) continue
```

**常用断点设置**：

```gdb
# 在 EATT 连接处断点
break bluetooth::eatt::EattExtension::Connect

# 在 L2CAP 回调处断点
break bluetooth::eatt::EattExtension::impl::eatt_connect_cfm

# 在状态变更处断点
break bluetooth::eatt::EattChannel::EattChannelSetState

# 条件断点
break eatt_l2cap_connect_cfm if cid == 0x0040
```

### 8.4 常用 dumpsys 命令

```bash
# 蓝牙整体状态
adb shell dumpsys bluetooth_manager

# 蓝牙适配器信息
adb shell dumpsys bluetooth_manager adapter

# GATT 连接信息
adb shell dumpsys bluetooth_manager gatt

# ACL 连接信息
adb shell dumpsys bluetooth_manager acl

# 配对设备信息
adb shell dumpsys bluetooth_manager bond

# Profile 连接状态
adb shell dumpsys bluetooth_manager profile
```

### ☕ Java 类比

C++ 协议栈的调试方法与 Java 层的调试有对应关系：

| C++ 调试方式 | Java 对应 | 说明 |
|-------------|----------|------|
| `log::info("msg {}", val)` | `Log.i(TAG, "msg " + val)` | 日志输出 |
| `LOG(INFO) << uuid` | `Log.i(TAG, uuid.toString())` | 格式化日志 |
| GDB/LLDB 断点 | Android Studio 断点 | Java 层用 AS，C++ 层用 GDB |
| `adb pull btsnoop_hci.log` | 同左 | HCI 日志跨语言通用 |
| `adb shell dumpsys bluetooth_manager` | 同左 | dumpsys 跨语言通用 |
| `static_assert` | 运行时 `assert` | C++ 编译期 vs Java 运行时 |
| AddressSanitizer (ASan) | 无直接等价 | Java 有 GC 不会 use-after-free |

```cpp
// C++：GDB 断点调试
break bluetooth::eatt::EattExtension::Connect
break eatt_l2cap_connect_cfm
continue
```

```java
// Java：Android Studio 断点调试
// 1. 在 EattExtension.connect() 设置断点
// 2. Debug 模式运行应用
// 3. 触发连接操作
// 4. 查看变量值和调用栈
```

**关键差异**：
- Java 层用 Android Studio 调试，C++ 层用 GDB/LLDB
- HCI Snoop 日志和 `dumpsys` 是跨语言通用的调试工具
- Java 的 GC 消除了 use-after-free 等内存错误，C++ 需要 ASan 检测
- 跨 JNI 边界的 Bug 需要同时调试 Java 和 C++ 层

---

## 9. 推荐学习路径

### 9.1 从基础到高级的五步学习路径

```
第一步：基础类型 (types/)
  ↓
第二步：OS 抽象 (osi/)
  ↓
第三步：GD OS 抽象 (gd/os/)
  ↓
第四步：HCI 层 (gd/hci/)
  ↓
第五步：协议实现 (stack/)
```

### 9.2 第一步：基础类型（types/）

**为什么从这里开始**：基础类型是整个协议栈的基石，代码量小、逻辑简单、无依赖。

| 文件 | 关注重点 |
|------|---------|
| `types/include/bluetooth/types/address.h` | `RawAddress` 类：6 字节蓝牙地址，比较运算符，`ToString()`，`FromString()` |
| `types/include/bluetooth/types/uuid.h` | `Uuid` 类：128 位 UUID，各种构造方式 |
| `types/include/bluetooth/types/hci_role.h` | `HCI_ROLE` 枚举：Central vs Peripheral |
| `types/include/bluetooth/types/bt_transport.h` | `BT_TRANSPORT` 枚举：BR/EDR vs LE |
| `types/include/bluetooth/types/ble_address_with_type.h` | BLE 地址类型组合 |

**学习要点**：
- `RawAddress` 是如何用 `std::array<uint8_t, 6>` 替代 C 风格数组的
- `constexpr` 构造函数如何实现编译期常量
- `std::hash` 特化如何让自定义类型可用于 `std::unordered_map`
- `std::formatter` 特化如何支持 `std::format` 格式化输出

### 9.3 第二步：OS 抽象层（osi/）

**为什么第二步**：osi 提供了协议栈运行的基础设施，理解它才能理解上层代码的运行环境。

| 文件 | 关注重点 |
|------|---------|
| `osi/include/alarm.h` | 定时器接口：`alarm_new()`, `alarm_set_on_mloop()`, `alarm_cancel()` |
| `osi/include/thread.h` | 线程接口：`thread_new()`, `thread_post()` |
| `osi/include/reactor.h` | 反应器接口：事件驱动的基础 |
| `osi/include/fixed_queue.h` | 固定大小队列：线程安全的生产者-消费者 |
| `osi/include/future.h` | Future/Promise：线程间同步 |
| `osi/include/mutex.h` | 互斥锁封装 |
| `osi/include/config.h` | INI 风格配置文件读写 |

**学习要点**：
- `alarm_set_on_mloop()` 如何在主线程上执行定时器回调
- `fixed_queue_t` 如何与 `reactor_t` 配合实现事件驱动
- 传统 C 风格 API 的使用模式（`osi_malloc`/`osi_free`）

### 9.4 第三步：GD OS 抽象（gd/os/）

**为什么第三步**：GD 的 OS 抽象是现代 C++ 版本的 osi，对比学习可以理解新旧架构的差异。

| 文件 | 关注重点 |
|------|---------|
| `gd/os/handler.h` | 消息处理器：`Post()`, `Call()`, `CallOn()` |
| `gd/os/thread.h` | 基于 Reactor 的线程：`Priority::REAL_TIME` vs `NORMAL` |
| `gd/os/reactor.h` | epoll 驱动的事件循环：`Register()`, `Unregister()` |
| `gd/os/queue.h` | 模板队列：`RegisterEnqueue()`, `RegisterDequeue()`, `TryDequeue()` |
| `gd/os/alarm.h` | 定时器：基于 Handler 的延迟执行 |
| `gd/os/repeating_alarm.h` | 重复定时器 |

**对比学习**：

| 概念 | osi（旧） | gd/os（新） |
|------|----------|-----------|
| 线程 | `thread_t*` + `reactor_t*` | `Thread` + 内嵌 `Reactor` |
| 任务投递 | `thread_post(thread, callback, context)` | `handler->Post(OnceClosure)` |
| 定时器 | `alarm_t*` + `alarm_set_on_mloop()` | `Alarm` + `handler->PostWithDelay()` |
| 队列 | `fixed_queue_t*` + 回调 | `Queue<T>` + `RegisterDequeue/Enqueue` |
| 同步 | `future_t*` | `std::promise` / `std::future` |

### 9.5 第四步：HCI 层（gd/hci/）

**为什么第四步**：HCI 是协议栈与硬件的接口层，理解它是理解数据流的基础。

| 文件 | 关注重点 |
|------|---------|
| `gd/hci/controller.h` | 控制器能力查询接口：所有 `Supports*()` 方法 |
| `gd/hci/hci_layer.h` | HCI 层入口：命令发送、事件接收 |
| `gd/hci/acl_manager/acl_manager_le.h` | LE ACL 连接管理 |
| `gd/hci/acl_manager/le_connection_callbacks.h` | LE 连接回调接口 |
| `gd/hci/le_scanning_manager.h` | LE 扫描管理 |
| `gd/hci/le_advertising_manager.h` | LE 广告管理 |
| `gd/hci/hci_interface.h` | HCI 命令接口 |

**学习要点**：
- `Controller` 的纯虚接口设计：为什么需要接口与实现分离
- `LeConnectionCallbacks` 的观察者模式：如何注册和接收连接事件
- `AclManagerLe` 如何管理 LE 连接的创建和生命周期

### 9.6 第五步：协议实现（stack/）

**为什么最后**：协议实现依赖前面所有层次，需要先理解基础设施。

| 子目录 | 关注重点 |
|--------|---------|
| `stack/eatt/` | EATT 通道管理：Pimpl、单例、状态机 |
| `stack/gatt/` | GATT 协议：属性协议、服务发现、通知 |
| `stack/l2cap/` | L2CAP 协议：通道复用、分段重组 |
| `stack/btm/` | 蓝牙管理：安全、扫描、ISO、SCO |
| `stack/smp/` | 安全管理：配对、密钥生成 |
| `stack/rfcomm/` | RFCOMM：串口仿真 |
| `stack/sdp/` | SDP：服务发现协议 |
| `stack/a2dp/` | A2DP：高级音频分发 |

### ☕ Java 类比

C++ 协议栈的学习路径与 Java 开发者的知识体系有对应关系：

| 学习步骤 | C++ 协议栈 | Java 对应知识 | 说明 |
|----------|-----------|-------------|------|
| 1. 基础类型 | `RawAddress`, `Uuid` | `BluetoothDevice`, `UUID` | 直接对应 |
| 2. OS 抽象 (osi) | `alarm_t`, `thread_t` | `Handler`, `HandlerThread` | 概念相同 |
| 3. GD OS 抽象 | `Handler`, `Thread`, `Queue` | `Handler`, `Looper`, `BlockingQueue` | 几乎一一对应 |
| 4. HCI 层 | `Controller`, `HciHal` | `BluetoothHci` AIDL | Java 层通过 AIDL 访问 |
| 5. 协议实现 | `stack/eatt/`, `stack/gatt/` | `EattExtension`, `BluetoothGatt` | Java 层是接口，C++ 是实现 |

**Java 开发者的推荐学习路径**：

```
第一步：从 Java 层入手
  → 熟悉 android.bluetooth.* API
  → 理解 BluetoothAdapter、BluetoothGatt 的用法

第二步：追踪 JNI 边界
  → 找到 Java native 方法对应的 C++ 实现
  → 理解 btif 层的桥接作用

第三步：深入 C++ 协议栈
  → 从 types/ 开始（最简单）
  → 逐步深入 gd/os/、gd/hci/、stack/

第四步：理解回调链
  → 从 Java 接口回调追踪到 C++ base::Callback
  → 理解异步操作的完整生命周期

第五步：实战调试
  → 用 HCI Snoop 日志分析实际问题
  → 用 dumpsys 查看协议栈状态
  → 尝试在 C++ 层添加日志追踪 Bug
```

---

## 10. 推荐阅读顺序

### 10.1 从简单到复杂的文件列表

以下按照难度递增排列，建议按顺序阅读：

#### 入门级（1-2 天）

| 序号 | 文件 | 行数 | 关注重点 |
|------|------|------|---------|
| 1 | `types/include/bluetooth/types/address.h` | ~105 | `RawAddress` 类：现代 C++ 封装 |
| 2 | `gd/common/callback.h` | ~30 | Callback 类型别名：理解回调基础 |
| 3 | `gd/hci/acl_manager/le_connection_callbacks.h` | ~42 | 纯虚回调接口：观察者模式 |
| 4 | `gd/hci/le_scanning_callback.h` | ~120 | 复杂回调接口：多种事件类型 |
| 5 | `gd/hal/hci_hal.h` | ~107 | HAL 接口：HCI 包收发 |

#### 基础级（3-5 天）

| 序号 | 文件 | 行数 | 关注重点 |
|------|------|------|---------|
| 6 | `gd/os/reactor.h` | ~115 | Reactor 模式：事件驱动核心 |
| 7 | `gd/os/thread.h` | ~80 | 基于 Reactor 的线程 |
| 8 | `gd/os/handler.h` | ~140 | 消息处理器：任务投递 |
| 9 | `gd/os/queue.h` | ~287 | 模板队列：生产者-消费者 |
| 10 | `gd/common/bidi_queue.h` | ~98 | 双向队列：层间数据传输 |
| 11 | `gd/hci/controller.h` | ~229 | 控制器接口：能力查询 |

#### 进阶级（1-2 周）

| 序号 | 文件 | 行数 | 关注重点 |
|------|------|------|---------|
| 12 | `stack/eatt/eatt.h` | ~289 | EATT 接口：Pimpl + 单例 + 状态机 |
| 13 | `stack/eatt/eatt.cc` | ~220 | EATT 实现：Pimpl 实现、回调注册 |
| 14 | `stack/eatt/eatt_impl.h` | ~1015 | EATT 内部实现：完整业务逻辑 |
| 15 | `main/shim/entry.cc` | ~77 | Shim 入口：GD 模块访问 |
| 16 | `main/shim/shim.h` | ~42 | Shim 接口：新旧架构桥接 |
| 17 | `gd/hal/snoop_logger.h` | ~80+ | Snoop 日志：HCI 抓包 |
| 18 | `gd/storage/config_cache.h` | ~80+ | 配置缓存：持久化存储 |

#### 高级（2-4 周）

| 序号 | 文件 | 关注重点 |
|------|------|---------|
| 19 | `stack/gatt/gatt_int.h` | GATT 内部数据结构 |
| 20 | `stack/l2cap/l2c_int.h` | L2CAP 内部数据结构 |
| 21 | `stack/btm/btm_sec_int_types.h` | BTM 安全内部类型 |
| 22 | `gd/hci/acl_manager/acl_manager_le_impl.cc` | LE ACL 连接管理实现 |
| 23 | `gd/hci/le_scanning_manager_impl.cc` | LE 扫描管理实现 |
| 24 | `btif/src/btif_gatt.cc` | GATT JNI 桥接 |
| 25 | `bta/gatt/bta_gattc_act.cc` | BTA GATT Client 状态机 |

### 10.2 每个文件需要关注的重点

#### `types/include/bluetooth/types/address.h`

- **`RawAddress` 类**：6 字节数组 `std::array<uint8_t, 6>` 的封装
- **比较运算符**：`operator<`, `operator==`，使 `RawAddress` 可用于 `std::map` 的键
- **`std::hash` 特化**：使 `RawAddress` 可用于 `std::unordered_map` 的键
- **`std::formatter` 特化**：支持 `std::format` 和 `log::info` 的格式化输出
- **`BDADDR_TO_STREAM` / `STREAM_TO_BDADDR`**：字节序转换宏（蓝牙地址是小端序）

#### `gd/os/handler.h`

- **`Post(OnceClosure)`**：向 Handler 投递任务，任务在 Handler 所属线程执行
- **`Call(functor, args...)`**：模板方法，自动绑定参数并 Post
- **`CallOn(obj, functor, args...)`**：在对象上调用成员函数
- **`Synchronize(timeout)`**：同步等待，用于跨线程同步
- **`DelayedTaskQueue`**：延迟任务队列，使用优先队列实现

#### `gd/os/queue.h`

- **`IQueueEnqueue<T>` / `IQueueDequeue<T>`**：队列的接口抽象
- **`Queue<T>`**：基于信号量的流控队列
- **`EnqueueBuffer<T>`**：带缓冲的入队辅助类
- **`RegisterEnqueue` / `RegisterDequeue`**：注册回调，当队列可操作时自动调用
- **`TryDequeue`**：非阻塞出队

#### `stack/eatt/eatt.h`

- **`EattChannelState`**：通道状态枚举（`enum class`）
- **`EattChannel`**：通道数据类，包含 CID、MTU、状态、定时器
- **`EattExtension`**：EATT 管理类，单例 + Pimpl
- **所有 `virtual` 方法**：接口定义，便于测试 mock

#### `stack/eatt/eatt_impl.h`

- **`eatt_device`**：设备信息类，包含通道映射
- **`eatt_impl`**：核心实现，包含设备列表、L2CAP 回调、连接逻辑
- **`base::WeakPtrFactory`**：弱引用工厂，防止异步回调访问已销毁对象
- **`connect_eatt()`**：EATT 连接的完整流程
- **`eatt_l2cap_connect_ind/cfm`**：L2CAP 回调处理

---

## 附录 A：命名规范速查

### GD 架构命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 类名 | PascalCase | `Controller`, `AclManager`, `LeAclConnection` |
| 方法名 | PascalCase | `GetLocalName()`, `SupportsBle()`, `Reset()` |
| 常量 | kPascalCase | `kDefaultEventMask`, `kDefaultLeEventMask` |
| 成员变量 | snake_case_（尾部下划线） | `pimpl_`, `eatt_impl_`, `mutex_` |
| 命名空间 | snake_case | `bluetooth::hci`, `bluetooth::os` |
| 模板参数 | PascalCase 或 T | `TENQUEUE`, `TDEQUEUE`, `T` |
| 枚举值 | ALL_CAPS 或 PascalCase | `EATT_CHANNEL_OPENED`, `SUCCESS` |

### 传统栈命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 结构体 | t前缀PascalCase | `tBTM_SEC_DEV_REC`, `tGATT_TCB` |
| 函数 | MODULE_VerbObject | `BTM_CreateLeConnection`, `BTA_GATTC_Open` |
| 宏/常量 | ALL_CAPS | `EATT_MIN_MTU_MPS`, `BTM_PAIR_STATE_IDLE` |
| 全局变量 | snake_case | `bt_gatt_callbacks` |
| 回调类型 | t前缀 + _CB 后缀 | `tBTM_CMPL_CB`, `tBTM_PAIRING_STATE` |

## 附录 B：常见缩写对照表

| 缩写 | 全称 | 含义 |
|------|------|------|
| ACL | Asynchronous Connection-Less | 异步无连接链路 |
| A2DP | Advanced Audio Distribution Profile | 高级音频分发配置 |
| ATT | Attribute Protocol | 属性协议 |
| BTA | Bluetooth Application | 蓝牙应用层 |
| BTIF | Bluetooth Interface | 蓝牙接口层 |
| BTM | Bluetooth Manager | 蓝牙管理模块 |
| EATT | Enhanced ATT | 增强属性协议 |
| GATT | Generic Attribute Profile | 通用属性配置 |
| GD | Gabeldorsche | 新架构代号 |
| HCI | Host Controller Interface | 主机控制器接口 |
| HAL | Hardware Abstraction Layer | 硬件抽象层 |
| ISO | Isochronous | 等时通道 |
| L2CAP | Logical Link Control and Adaptation Protocol | 逻辑链路控制与适配协议 |
| LE | Low Energy | 低功耗蓝牙 |
| MTU | Maximum Transmission Unit | 最大传输单元 |
| RFCOMM | Radio Frequency Communication | 射频通信协议 |
| SCO | Synchronous Connection-Oriented | 同步面向连接链路 |
| SDP | Service Discovery Protocol | 服务发现协议 |
| SMP | Security Manager Protocol | 安全管理协议 |
| Pimpl | Pointer to Implementation | 指向实现的指针 |

## 附录 C：线程模型速查

| 线程 | 用途 | 关键类 |
|------|------|--------|
| Main Thread | 协议栈主线程，处理大部分协议逻辑 | `btu_task`, `do_in_main_thread` |
| GD Thread | GD 架构的专用线程 | `gd::os::Thread`, `gd::os::Handler` |
| JNI Thread | Java JNI 调用线程 | `btif_jni_task` |
| Alarm Thread | 定时器线程 | `alarm_thread` |
| Reactor Thread | 事件驱动线程 | `gd::os::Reactor` |

**线程间通信**：
- 传统栈：`do_in_main_thread()` / `do_in_main_thread_delayed()`
- GD 栈：`handler->Post()` / `handler->Call()` / `handler->CallOn()`

---

> **下一步建议**：完成本教材后，建议选择一个具体的协议模块（如 EATT 或 GATT），按照第 10 节的阅读顺序，从头到尾阅读其完整代码，将本教材中的技巧付诸实践。
