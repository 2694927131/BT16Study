# 命名空间与类型别名 —— 基于蓝牙协议栈真实代码

> **目标读者**：C++ 刚入门、基础薄弱的初学者
> **特色**：所有示例均来自 Android 蓝牙协议栈（Bluetooth Stack）真实代码，标注来源文件与行号

---

## 目录

1. [命名空间 (namespace)](#1-命名空间-namespace)
2. [匿名命名空间](#2-匿名命名空间)
3. [using 类型别名](#3-using-类型别名)
4. [typedef（C 风格类型别名）](#4-typedefc-风格类型别名)
5. [using 声明](#5-using-声明)
6. [命名空间与头文件组织](#6-命名空间与头文件组织)

---

> 📎 关联教材：01(基础语法), 04(模板), 15(阅读导航)

## 1. 命名空间 (namespace)

### 1.1 为什么需要命名空间？

想象一个大型项目中有多个开发者同时工作。开发者 A 写了一个 `Controller` 类来管理蓝牙控制器，开发者 B 也写了一个 `Controller` 类来管理网络控制器。当两个代码合并时，编译器会报错：

```
error: redefinition of 'Controller'
```

这就是**名称冲突**（name collision）。命名空间就是 C++ 解决这个问题的机制——它给名称加了一层"姓氏"，让不同模块中的同名类可以和平共处。

在蓝牙协议栈这种**数十万行代码**的大型项目中，命名空间更是必不可少。协议栈中存在大量通用名称：`Handler`、`Queue`、`Callback`、`Device`……如果没有命名空间隔离，整个项目将无法编译。

### 1.2 定义命名空间

命名空间的基本语法：

```cpp
namespace 命名空间名 {
    // 在这里放置类、函数、变量等声明
}
```

**蓝牙协议栈的顶层命名空间**：

```cpp
// 来源: system/gd/hci/controller.h:25-26
namespace bluetooth {
namespace hci {

class Controller {
public:
  // ...
};

}  // namespace hci
}  // namespace bluetooth
```

这里定义了一个 `bluetooth` 命名空间，在其中又定义了 `hci` 命名空间，`Controller` 类的全名是 `bluetooth::hci::Controller`。

### 1.3 嵌套命名空间

蓝牙协议栈使用了**多层嵌套命名空间**来组织代码，层级结构如下：

```
bluetooth/                    ← 顶层命名空间
├── hci/                      ← HCI（Host Controller Interface）层
│   ├── Controller
│   ├── Octet16, Octet32
│   └── acl_manager/
├── common/                   ← 通用工具
│   ├── BidiQueue
│   ├── Callback
│   └── OnceClosure
├── os/                       ← OS 抽象层
│   ├── Handler
│   ├── Thread
│   ├── Queue
│   └── Alarm
├── storage/                  ← 存储模块
│   ├── MutationEntry
│   ├── ConfigCache
│   └── Device
├── eatt/                     ← EATT（Enhanced ATT）协议
│   ├── EattChannel
│   └── EattExtension
├── shim/                     ← Shim 桥接层（新旧架构过渡）
│   ├── DumpsysFunction
│   └── GetAclManagerLe()
├── legacy/                   ← 遗留代码
│   ├── hci/
│   └── stack/
│       └── sdp/
├── a2dp/                     ← A2DP 音频协议
└── metrics/                  ← 度量统计
```

**嵌套命名空间的两种写法**：

```cpp
// 写法1：传统嵌套（C++98 起支持）
namespace bluetooth {
namespace hci {
class Controller { /* ... */ };
}  // namespace hci
}  // namespace bluetooth

// 写法2：C++17 嵌套命名空间简写
namespace bluetooth::hci {
class Controller { /* ... */ };
}  // namespace bluetooth::hci
```

**协议栈中的 C++17 简写示例**：

```cpp
// 来源: system/gd/hci/octets.h:22-28
namespace bluetooth::hci {

constexpr int kOctet16Length = 16;
using Octet16 = std::array<uint8_t, kOctet16Length>;

constexpr int kOctet32Length = 32;
using Octet32 = std::array<uint8_t, kOctet32Length>;
}  // namespace bluetooth::hci
```

```cpp
// 来源: system/stack/arbiter/acl_arbiter.h:33
namespace bluetooth::shim::arbiter {

enum class InterceptAction {
  FORWARD,
  DROP
};

}  // namespace bluetooth::shim::arbiter
```

```cpp
// 来源: system/stack/include/hcimsgs.h:43-55
namespace bluetooth::legacy::hci {
class Interface {
public:
  virtual void Disconnect(uint16_t handle, uint8_t reason) const = 0;
  virtual void ChangeConnectionPacketType(uint16_t handle, uint16_t packet_types) const = 0;
  virtual void StartRoleSwitch(const RawAddress& bd_addr, uint8_t role) const = 0;
  virtual ~Interface() = default;
};

const Interface& GetInterface();
}  // namespace bluetooth::legacy::hci
```

> **初学者提示**：C++17 的 `namespace A::B::C` 写法更简洁，但要注意——如果你需要在 `A` 命名空间中放一些不属于 `B` 的东西，就必须用传统嵌套写法分开声明。

### 1.4 使用命名空间中的名称

有三种方式引用命名空间中的名称：

**方式 1：完全限定名（最安全，推荐在头文件中使用）**

```cpp
// 每次使用都写完整的命名空间路径
bluetooth::hci::Controller* ctrl;
bluetooth::os::Handler* handler;
bluetooth::common::OnceClosure closure;
```

**方式 2：using 声明（引入单个名称）**

```cpp
using bluetooth::hci::Controller;  // 只引入 Controller 这一个名称
Controller* ctrl;                   // 之后可以直接使用 Controller
```

**方式 3：using namespace 指令（引入整个命名空间）**

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:51
using namespace bluetooth;

// 之后可以直接使用 bluetooth 命名空间下的所有名称
hci::Controller* ctrl;
shim::GetAclManagerLe();
```

### 1.5 命名空间别名

当一个命名空间路径很长时，可以用别名简化：

```cpp
// 给长命名空间起一个短别名
namespace legacy_hci = bluetooth::legacy::hci;
namespace legacy_sdp = bluetooth::legacy::stack::sdp;

// 使用别名
legacy_hci::GetInterface();
```

**协议栈中的真实使用**：

```cpp
// 来源: system/stack/pan/pan_utils.cc:44
using namespace bluetooth::legacy::stack::sdp;
// 这样就可以直接使用 sdp 命名空间下的函数，而不需要写完整路径
```

### 1.6 蓝牙协议栈命名空间全景

下面是协议栈中各模块的命名空间与对应的源码路径：

| 命名空间 | 源码路径 | 职责 |
|----------|---------|------|
| `bluetooth::hci` | `system/gd/hci/` | HCI 层，与蓝牙控制器通信 |
| `bluetooth::common` | `system/gd/common/` | 通用工具：回调、队列、绑定 |
| `bluetooth::os` | `system/gd/os/` | OS 抽象：线程、Handler、闹钟 |
| `bluetooth::storage` | `system/gd/storage/` | 配置存储 |
| `bluetooth::eatt` | `system/stack/eatt/` | EATT 增强属性协议通道 |
| `bluetooth::shim` | `system/main/shim/` | 新旧架构桥接层 |
| `bluetooth::shim::arbiter` | `system/stack/arbiter/` | 数据包拦截仲裁 |
| `bluetooth::legacy::hci` | `system/stack/hcic/` | 遗留 HCI 命令接口 |
| `bluetooth::legacy::stack::sdp` | (多个源文件) | 遗留 SDP 服务发现 |
| `bluetooth::a2dp` | `system/stack/include/a2dp_constants.h` | A2DP 音频协议常量 |
| `bluetooth::metrics` | `system/metrics/` | 度量与统计 |
| `connection_manager` | `system/stack/connection_manager/` | LE 连接管理 |

> **注意**：`connection_manager` 是一个独立的命名空间，不在 `bluetooth` 内部。这体现了命名空间的灵活性——不同模块可以选择自己的命名空间策略。

### ☕ Java 类比

C++ 的 `namespace` 对应 Java 的 `package`，两者都用于组织代码和避免名称冲突：

| 对比项 | C++ `namespace` | Java `package` |
|--------|-----------------|----------------|
| 声明方式 | `namespace name { ... }` | `package com.example.name;`（文件顶部声明） |
| 嵌套 | `namespace A::B::C { }` | `package com.example.a.b.c;`（用 `.` 分隔） |
| 跨文件定义 | 同一命名空间可在多个文件中扩展 | 一个包对应一个目录 |
| 完全限定名 | `bluetooth::hci::Controller` | `bluetooth.hci.Controller` |
| 命名空间别名 | `namespace short = long::ns;` | `import bluetooth.hci.Controller;`（导入单个类） |
| 匿名命名空间 | `namespace { ... }` | 包私有（无 `public` 修饰符） |

**C++ 命名空间示例：**

```cpp
namespace bluetooth::hci {
class Controller { /* ... */ };
}
// 使用
bluetooth::hci::Controller* ctrl;
```

**Java 包示例：**

```java
package bluetooth.hci;
public class Controller { /* ... */ }
// 使用
bluetooth.hci.Controller ctrl;
// 或
import bluetooth.hci.Controller;
Controller ctrl;
```

> **关键区别**：C++ 的命名空间是代码块级别的，可以在任意文件中多次扩展。Java 的包是文件/目录级别的，一个 `.java` 文件只能属于一个包。C++ 的嵌套命名空间用 `::` 分隔，Java 用 `.` 分隔。

### 📌 本节小结

- 命名空间给名称加"姓氏"，解决大型项目中的名称冲突问题
- 蓝牙协议栈使用`bluetooth::hci`、`bluetooth::os`等多层嵌套命名空间组织代码
- C++17起`namespace A::B::C`简写更简洁，但需在A中放非B内容时仍用传统嵌套
- 三种引用方式：完全限定名（最安全）、using声明（引入单个）、using namespace（引入全部）

---

## 2. 匿名命名空间

### 2.1 什么是匿名命名空间？

匿名命名空间（unnamed namespace）是没有名字的命名空间：

```cpp
namespace {
    // 这里的内容只在当前编译单元（.cc 文件）可见
    int helper_count = 0;
    void internal_function() { /* ... */ }
}  // namespace
```

### 2.2 为什么需要匿名命名空间？

在 C 语言中，我们用 `static` 关键字限制函数或变量的作用域在当前文件内：

```c
// C 语言做法
static void helper_function() { /* ... */ }
static int internal_counter = 0;
```

C++ 推荐使用匿名命名空间替代 `static`，原因如下：

| 特性 | `static` | 匿名命名空间 |
|------|----------|-------------|
| 限制函数可见性 | ✅ | ✅ |
| 限制变量可见性 | ✅ | ✅ |
| 限制类/模板可见性 | ❌ | ✅ |
| 限制类型别名可见性 | ❌ | ✅ |
| C++ 推荐程度 | 历史遗留 | **推荐** |

匿名命名空间比 `static` 更强大，因为它可以封装任何实体（包括类、模板、类型别名），而 `static` 只能作用于函数和变量。

### 2.3 真实代码示例

**示例 1：connection_manager.cc 中的辅助函数**

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:77-91
namespace {
static void ACL_AcceptLeConnectionFrom(const tBLE_BD_ADDR& legacy_address_with_type,
                                       bool is_direct, bool prefer_relax_mode) {
  BTM_LogHistory(kBtmLogTagACL, legacy_address_with_type, "Allow connection from", "Le");
  bluetooth::shim::GetAclManagerLe()->CreateLeConnection(
          bluetooth::ToAddressWithTypeFromLegacy(legacy_address_with_type),
          is_direct, prefer_relax_mode);
}

static void ACL_IgnoreLeConnectionFrom(const tBLE_BD_ADDR& legacy_address_with_type) {
  BTM_LogHistory(kBtmLogTagACL, legacy_address_with_type, "Ignore connection from", "Le");
  bluetooth::shim::GetAclManagerLe()->CancelLeConnect(
          bluetooth::ToAddressWithTypeFromLegacy(legacy_address_with_type));
}
}  // namespace
```

> **注意**：这里同时使用了匿名命名空间和 `static`。虽然从技术上说有些冗余（匿名命名空间已经限制了可见性），但在协议栈这种历史悠久的代码中，同时使用两者是常见的防御性编程习惯。

**示例 2：connection_manager.cc 中更深的匿名命名空间**

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:105-149
namespace connection_manager {

namespace {
// Maps address to apps trying to connect to it
std::map<RawAddress, tAPPS_CONNECTING> bgconn_dev;  // Guarded by bgconn_dev_mutex
std::recursive_mutex bgconn_dev_mutex;

int num_of_targeted_announcements_users(void) {
  std::lock_guard<std::recursive_mutex> lock(bgconn_dev_mutex);
  return std::count_if(bgconn_dev.begin(), bgconn_dev.end(), [](const auto& pair) {
    return !pair.second.is_in_accept_list &&
           !pair.second.doing_targeted_announcements_conn.empty();
  });
}

bool is_anyone_interested_to_use_accept_list(
        const std::map<RawAddress, tAPPS_CONNECTING>::iterator it) {
  if (!it->second.doing_targeted_announcements_conn.empty()) {
    return !it->second.doing_direct_conn.empty();
  }
  return !it->second.doing_bg_conn.empty() || !it->second.doing_direct_conn.empty();
}

static bool accept_list_is_full() {
  uint8_t accept_list_size = shim::GetController()->GetLeFilterAcceptListSize();
  // ...
}
}  // namespace

}  // namespace connection_manager
```

这个例子展示了匿名命名空间可以嵌套在命名命名空间内部——`bgconn_dev`、`bgconn_dev_mutex` 等变量和函数只在 `connection_manager.cc` 这个编译单元中可见，不会污染全局命名空间。

### 2.4 匿名命名空间的工作原理

编译器会为每个匿名命名空间生成一个唯一的内部名称，效果类似于：

```cpp
// 你写的代码
namespace { void foo() {} }

// 编译器内部等价于
namespace __unique_name_12345 { void foo() {} }
using namespace __unique_name_12345;  // 当前编译单元自动 using
```

由于每个编译单元的 `__unique_name` 不同，其他 `.cc` 文件无法访问这些符号，从而实现了编译单元级别的封装。

### ☕ Java 类比

C++ 的匿名命名空间对应 Java 的**包私有访问**（不写访问修饰符）：

| 对比项 | C++ 匿名命名空间 | Java 包私有 |
|--------|-----------------|------------|
| 可见范围 | 当前编译单元（.cc 文件） | 当前包（package） |
| 限制函数 | ✅ | ✅（不加 `public`/`protected`/`private`） |
| 限制变量 | ✅ | ✅ |
| 限制类 | ✅ | ✅ |
| 限制模板 | ✅ | 不适用（Java 无模板） |
| 粒度 | 文件级别 | 包级别（更粗） |

**C++ 匿名命名空间示例：**

```cpp
namespace {
void internal_helper() { /* 只在当前 .cc 文件可见 */ }
std::map<RawAddress, tAPPS_CONNECTING> bgconn_dev;
}
```

**Java 包私有示例：**

```java
// 不加 public 修饰符 → 包私有
class InternalHelper { /* 只在当前包可见 */ }
// 注意：Java 的包私有是包级别的，不是文件级别的
// 同一包中的其他类也可以访问
```

> **关键区别**：C++ 匿名命名空间的可见范围是**单个编译单元**（.cc 文件），粒度更细。Java 的包私有可见范围是**整个包**，粒度更粗。如果 Java 需要文件级别的封装，只能通过内部类或嵌套类实现。

### 📌 本节小结

- 匿名命名空间将符号限制在当前编译单元(.cc文件)内可见，替代`static`
- 比`static`更强大：可封装类、模板、类型别名，`static`只能作用于函数和变量
- 可嵌套在命名命名空间内部，实现模块内部的编译单元级封装
- 编译器为每个匿名命名空间生成唯一内部名称，其他编译单元无法访问

---

## 3. using 类型别名

### 3.1 基本语法

C++11 引入了 `using` 别名声明，语法为：

```cpp
using 新名称 = 原类型;
```

这比 C 风格的 `typedef` 更直观，尤其是对于复杂类型和模板别名。

### 3.2 简化复杂类型名

在蓝牙协议栈中，很多类型名非常长，使用 `using` 可以大幅提高代码可读性。

**示例 1：时间点类型别名**

```cpp
// 来源: system/gd/os/handler.h:36-37
namespace bluetooth {

using TimePoint = os::boottime_clock::time_point;
using DelayedTask = std::pair<TimePoint, common::OnceClosure>;

}  // namespace bluetooth
```

如果不使用别名，每次都要写 `os::boottime_clock::time_point`，既冗长又容易出错。有了 `TimePoint`，代码变得简洁：

```cpp
// 来源: system/gd/os/handler.h:40-44
inline auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
  return a.first > b.first;
};
```

**示例 2：回调类型别名**

```cpp
// 来源: system/gd/common/bidi_queue.h:35-36
template <typename TENQUEUE, typename TDEQUEUE>
class BidiQueueEnd {
public:
  using EnqueueCallback = Callback<std::unique_ptr<TENQUEUE>()>;
  using DequeueCallback = Callback<void()>;
  // ...
};
```

这里 `EnqueueCallback` 和 `DequeueCallback` 是在类内部定义的类型别名，它们依赖模板参数 `TENQUEUE`。之后在类中使用 `EnqueueCallback` 就比写完整的 `Callback<std::unique_ptr<TENQUEUE>()>` 简洁得多。

**示例 3：ACL 完成回调**

```cpp
// 来源: system/gd/hci/controller.h:42-43
class Controller {
public:
  using CompletedAclPacketsCallback =
          common::ContextualCallback<void(uint16_t /* handle */, uint16_t /* num_packets */)>;
  virtual void RegisterCompletedAclPacketsCallback(CompletedAclPacketsCallback cb) = 0;
  // ...
};
```

`CompletedAclPacketsCallback` 是一个回调类型，表示"当 ACL 数据包传输完成时通知上层"。如果不使用别名，每次声明这个回调参数都要写一长串类型，非常不便。

**示例 4：主线程闭包类型**

```cpp
// 来源: system/stack/include/main_thread.h:26
using BtMainClosure = std::function<void()>;
```

`BtMainClosure` 表示一个无参数无返回值的闭包，专门用于主线程任务调度。

**示例 5：BLE 同步回调**

```cpp
// 来源: system/stack/include/btm_ble_api.h:373-380
using StartSyncCb = base::Callback<void(
        uint8_t /*status*/, uint16_t /*sync_handle*/, uint8_t /*advertising_sid*/,
        uint8_t /*address_type*/, RawAddress /*address*/, uint8_t /*phy*/, uint16_t /*interval*/)>;
using SyncReportCb =
        base::Callback<void(uint16_t /*sync_handle*/, int8_t /*tx_power*/, int8_t /*rssi*/,
                            uint8_t /*status*/, std::vector<uint8_t> /*data*/)>;
using SyncLostCb = base::Callback<void(uint16_t /*sync_handle*/)>;
using BigInfoReportCb = base::Callback<void(uint16_t /*sync_handle*/, bool /*encrypted*/)>;
```

`StartSyncCb` 的原始类型长达 7 个参数！使用别名后，函数声明变得清晰：

```cpp
void SomeFunction(StartSyncCb start_cb, SyncReportCb report_cb, SyncLostCb lost_cb);
```

**示例 6：智能指针类型别名**

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:75
using unique_alarm_ptr = std::unique_ptr<alarm_t, decltype(&alarm_free)>;
```

这是一个带自定义删除器的 `unique_ptr`，用于自动释放蓝牙闹钟资源。`decltype(&alarm_free)` 自动推导删除器函数的类型。之后使用 `unique_alarm_ptr` 就像普通类型一样：

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:102
std::map<tAPP_ID, unique_alarm_ptr> doing_direct_conn;

// 来源: system/stack/connection_manager/connection_manager.cc:594
bgconn_dev[address].doing_direct_conn.emplace(app_id, unique_alarm_ptr(timeout, &alarm_free));
```

**示例 7：固定长度字节数组别名**

```cpp
// 来源: system/gd/hci/octets.h:22-28
namespace bluetooth::hci {

constexpr int kOctet16Length = 16;
using Octet16 = std::array<uint8_t, kOctet16Length>;

constexpr int kOctet32Length = 32;
using Octet32 = std::array<uint8_t, kOctet32Length>;
}  // namespace bluetooth::hci
```

蓝牙协议中经常使用 16 字节或 32 字节的固定长度数组（如加密密钥），`Octet16` 比 `std::array<uint8_t, 16>` 更直观。

**示例 8：Dumpsys 函数类型别名**

```cpp
// 来源: system/main/shim/dumpsys.h:45
namespace bluetooth {
namespace shim {

using DumpsysFunction = std::function<void(int fd)>;

void RegisterDumpsysFunction(const void* token, DumpsysFunction func);
void UnregisterDumpsysFunction(const void* token);

}  // namespace shim
}  // namespace bluetooth
```

**示例 9：连接管理器中的应用 ID 别名**

```cpp
// 来源: system/stack/connection_manager/connection_manager.h:41
namespace connection_manager {

using tAPP_ID = uint8_t;

bool background_connect_add(tAPP_ID app_id, const RawAddress& address);
bool direct_connect_add(tAPP_ID app_id, const RawAddress& address,
                        tBLE_ADDR_TYPE addr_type = BLE_ADDR_PUBLIC, bool prefer_relax_mode = false);
// ...
}  // namespace connection_manager
```

`tAPP_ID` 是 `uint8_t` 的别名，语义上表示"应用标识符"，比直接使用 `uint8_t` 更具可读性。

### 3.3 using 与 typedef 的对比

| 特性 | `typedef` | `using` |
|------|----------|---------|
| 基本类型别名 | `typedef int MyInt;` | `using MyInt = int;` |
| 指针类型 | `typedef void (*FuncPtr)();` | `using FuncPtr = void(*)();` |
| **模板别名** | ❌ 不支持 | ✅ 支持 |
| 可读性 | 新名称在后面 | 新名称在前面，更直观 |
| C++ 标准推荐 | 历史遗留 | **C++11 起推荐** |

**模板别名是 using 的杀手级特性**：

```cpp
// typedef 无法做到这一点！
template <typename T>
using VecPtr = std::unique_ptr<std::vector<T>>;

VecPtr<int> p1;    // OK
VecPtr<char> p2;   // OK
```

### 3.4 类内部的 using 类型别名

类型别名也可以定义在类内部，作为类的成员类型。这在协议栈中很常见：

```cpp
// 来源: system/gd/os/queue.h:36-42
template <typename T>
class IQueueEnqueue {
public:
  using EnqueueCallback = common::Callback<std::unique_ptr<T>()>;
  virtual ~IQueueEnqueue() = default;
  virtual void RegisterEnqueue(Handler* handler, EnqueueCallback callback) = 0;
  virtual void UnregisterEnqueue() = 0;
};
```

```cpp
// 来源: system/gd/os/queue.h:45-53
template <typename T>
class IQueueDequeue {
public:
  using DequeueCallback = common::Callback<void()>;
  virtual ~IQueueDequeue() = default;
  virtual void RegisterDequeue(Handler* handler, DequeueCallback callback) = 0;
  virtual void UnregisterDequeue() = 0;
  virtual std::unique_ptr<T> TryDequeue() = 0;
};
```

```cpp
// 来源: system/gd/os/boottime_clock.h:32-36
class boottime_clock {
public:
  using duration = std::chrono::nanoseconds;
  using time_point = std::chrono::time_point<std::chrono::nanoseconds>;
  static constexpr bool is_steady = true;
  static time_point now() noexcept;
};
```

`boottime_clock` 遵循 C++ 标准库 Clock 的约定——必须提供 `duration`、`time_point` 和 `is_steady` 成员类型。这种模式在标准库的 `std::chrono::system_clock`、`std::chrono::steady_clock` 中也能看到。

### ☕ Java 类比

Java **没有**与 C++ `using` 类型别名等价的机制。Java 不支持为类型创建别名。

| 对比项 | C++ `using` 类型别名 | Java |
|--------|---------------------|------|
| 基本类型别名 | `using MyInt = int;` | 无等价 |
| 复杂类型别名 | `using Callback = std::function<void(int)>;` | 无等价 |
| 模板别名 | `template<T> using VecPtr = unique_ptr<vector<T>>;` | 无等价 |
| 类内部类型别名 | `using UUID128Bit = std::array<uint8_t, 16>;` | 无等价 |
| 替代方案 | — | 继承（`class CallbackList extends ArrayList<Callback>`）、委托模式 |

**C++ using 类型别名示例：**

```cpp
using TimePoint = os::boottime_clock::time_point;
using CompletedAclPacketsCallback = common::ContextualCallback<void(uint16_t, uint16_t)>;
using Octet16 = std::array<uint8_t, 16>;
```

**Java 的替代方案：**

```java
// Java 没有类型别名，只能用具体类或接口
// 方式 1：直接使用完整类型（最常见）
ContextualCallback<Integer, Integer> callback;

// 方式 2：定义子类（不推荐，语义不同）
// class CompletedAclPacketsCallback extends ContextualCallback<Integer, Integer> {}

// 方式 3：定义接口（推荐用于回调类型）
@FunctionalInterface
interface CompletedAclPacketsCallback {
    void onCompleted(int handle, int numPackets);
}
```

> **关键区别**：C++ 的 `using` 类型别名不创建新类型，只是给现有类型起一个短名，零运行时开销。Java 没有这个功能，只能使用完整类型名或通过继承/接口间接实现，后者会引入新的类型层次。

---

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:46
class Uuid {
public:
  using UUID128Bit = std::array<uint8_t, kNumBytes128>;
  // ...
};
```

```cpp
// 来源: system/profile/avrcp/device.h:349
class Device {
public:
  using Notification = std::pair<bool, uint8_t>;
  // ...
};
```

### 📌 本节小结

- `using 新名称 = 原类型;`比`typedef`更直观，新名称在前面
- 模板别名是`using`的杀手级特性，`typedef`无法做到
- 蓝牙协议栈中大量使用`using`简化回调类型、时间点类型、字节数组类型
- 类内部的`using`类型别名可作为成员类型，遵循标准库Clock等约定

---

## 4. typedef（C 风格类型别名）

### 4.1 基本语法

`typedef` 是 C 语言时代的类型别名机制，语法为：

```cpp
typedef 原类型 新名称;
```

### 4.2 协议栈中的 typedef 示例

蓝牙协议栈有 20 多年的历史，大量代码从 C 时代遗留下来，因此 `typedef` 随处可见。

**示例 1：基本类型别名**

```cpp
// 来源: system/types/include/bluetooth/types/ble_address_with_type.h:30
typedef uint8_t tBLE_ADDR_TYPE;
```

`tBLE_ADDR_TYPE` 是 BLE 地址类型的别名。蓝牙规范定义了 Public、Random、Public Identity、Random Identity 等地址类型，用 `uint8_t` 存储，但 `tBLE_ADDR_TYPE` 比 `uint8_t` 更具语义。

**示例 2：数组类型别名**

```cpp
// 来源: system/types/include/bluetooth/types/ble_address_with_type.h:92
typedef std::array<uint8_t, RawAddress::kLength + 1> tBLE_BD_ADDR_SERIALIZED;
```

**示例 3：枚举类型别名**

```cpp
// 来源: system/types/include/bluetooth/types/hci_role.h:50
typedef tHCI_ROLE hci_role_t;         // LEGACY
```

注释中的 `LEGACY` 明确标注这是历史遗留代码。

**示例 4：函数指针类型别名**

```cpp
// 来源: system/stack/srvc/srvc_eng.cc:52
typedef void (*tSRVC_ENG_C_CMPL_ACTION)(tSRVC_CLCB* p_clcb, tGATTC_OPTYPE op,
                                         tGATT_STATUS status, uint16_t conn_id);
```

```cpp
// 来源: system/stack/smp/smp_utils.cc:105
typedef bool (*tSMP_CMD_LEN_VALID)(tSMP_CB* p_cb);
```

函数指针的 `typedef` 语法特别反直觉——新名称夹在返回类型和参数列表之间。这是 `typedef` 最大的痛点之一，也是 `using` 更优的原因。

**示例 5：结构体类型别名**

```cpp
// 来源: system/stack/smp/smp_int.h:244
typedef struct {
  // ...
} tSMP_ASSO;

// 来源: system/stack/smp/smp_int.h:249
typedef union {
  // ...
} tSMP_INT_DATA;
```

**示例 6：回调函数类型别名**

```cpp
// 来源: system/udrv/include/uipc.h:55
typedef void(tUIPC_RCV_CBACK)(tUIPC_CH_ID ch_id, /* ... */);
```

### 4.3 typedef 的痛点

对比 `typedef` 和 `using` 定义函数指针的写法：

```cpp
// typedef 写法——新名称藏在中间，不直观
typedef void (*CallbackType)(int, double);

// using 写法——新名称在前面，一目了然
using CallbackType = void(*)(int, double);
```

**typedef 无法定义模板别名**：

```cpp
// ❌ 编译错误！typedef 不支持模板
template <typename T>
typedef std::vector<T> MyVec;   // 错误！

// ✅ using 支持模板别名
template <typename T>
using MyVec = std::vector<T>;   // 正确！
```

### 4.4 协议栈中的 typedef 命名规范

蓝牙协议栈的 `typedef` 遵循一套命名规范：

| 前缀 | 含义 | 示例 |
|------|------|------|
| `t` | type（类型） | `tBLE_ADDR_TYPE`、`tAPP_ID` |
| `tBTM_` | Bluetooth Manager 类型 | `tBTM_BLE_VSC_CB` |
| `tGATT_` | GATT 层类型 | `tGATT_SR_CMD` |
| `tSMP_` | SMP（安全管理）类型 | `tSMP_CB`、`tSMP_EVENT` |
| `tHCI_` | HCI 层类型 | `tHCI_ROLE` |
| `tUIPC_` | UIPC 通道类型 | `tUIPC_CH_ID` |

> **初学者提示**：在新代码中，应该使用 `using` 而不是 `typedef`。但阅读旧代码时，你必须能读懂 `typedef`。协议栈正在逐步将 `typedef` 迁移为 `using`，但这是一个漫长的过程。

### ☕ Java 类比

Java **没有** `typedef`，也没有任何类型别名机制。

| 对比项 | C++ `typedef` | Java |
|--------|--------------|------|
| 基本类型别名 | `typedef int MyInt;` | 无等价 |
| 函数指针类型 | `typedef void (*Callback)(int);` | 无等价（Java 用函数式接口） |
| 结构体类型 | `typedef struct { int x; } Point;` | 无等价（Java 用 `class`/`record`） |
| 与 `using` 的关系 | 旧语法，功能等价 | 不适用 |

**C++ typedef 示例：**

```cpp
typedef void (*tBTM_RLEROLE_CHG_CBACK)(uint8_t new_role, tHCI_STATUS hci_status);
typedef uint8_t tBLE_ADDR_TYPE;
```

**Java 的替代方案：**

```java
// 函数指针 → 函数式接口
@FunctionalInterface
interface RleRoleChangeCallback {
    void onRoleChange(byte newRole, byte hciStatus);
}

// 基本类型别名 → 无等价，直接使用原始类型
byte bleAddressType;  // 无法起别名
```

> **关键区别**：C++ 的 `typedef` 是纯编译期别名，零运行时开销。Java 的替代方案（接口、类）会创建新的类型。Java 选择不支持类型别名，是为了保持类型系统的简洁性。

### 📌 本节小结

- `typedef 原类型 新名称;`是C风格类型别名，新名称藏在中间，不直观
- 函数指针的`typedef`语法特别反直觉，`using`更清晰
- `typedef`不支持模板别名，这是`using`的杀手级优势
- 新代码应使用`using`，但阅读旧代码时必须能读懂`typedef`

---

## 5. using 声明

### 5.1 引入单个名称

```cpp
using 命名空间::名称;  // 只引入这一个名称
```

**协议栈示例**：

```cpp
// 来源: system/gd/common/callback.h:24-27
namespace bluetooth {
namespace common {

using base::Callback;
using base::Closure;
using base::OnceCallback;
using base::OnceClosure;

}  // namespace common
}  // namespace bluetooth
```

这里 `bluetooth::common` 命名空间将 `base::Callback` 等类型"重新导出"为自己的成员。之后在 `bluetooth::common` 命名空间内，可以直接使用 `Callback`、`OnceClosure` 等名称，而不需要写 `base::` 前缀。

这种模式在协议栈中非常实用——它创建了一个**统一的类型入口**，上层代码只需依赖 `bluetooth::common::Callback`，而不需要知道底层用的是 `base::Callback` 还是其他实现。

### 5.2 引入整个命名空间

```cpp
using namespace 命名空间;  // 引入该命名空间下的所有名称
```

**协议栈示例**：

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:51
using namespace bluetooth;
```

这行代码让 `connection_manager.cc` 中可以直接使用 `hci::Controller`、`shim::GetAclManagerLe()` 等名称，而不需要每次都写 `bluetooth::` 前缀。

```cpp
// 来源: system/stack/btm/security_event_parser.cc:34
using namespace bluetooth::hci;
```

```cpp
// 来源: system/stack/pan/pan_utils.cc:44
using namespace bluetooth::legacy::stack::sdp;
```

### 5.3 ⚠️ 慎用 using namespace

`using namespace` 虽然方便，但可能带来严重问题：

**问题 1：名称冲突**

```cpp
using namespace bluetooth::hci;
using namespace bluetooth::storage;

// 如果两个命名空间都有 Device 类，编译器无法确定你指的是哪个
Device* d;  // ❌ 歧义！
```

**问题 2：破坏命名空间的隔离性**

```cpp
// 头文件中写 using namespace 是灾难性的！
// header.h
using namespace bluetooth;  // ❌ 所有包含此头文件的代码都会被污染

// 其他文件
#include "header.h"
// 意外引入了 bluetooth 命名空间的所有名称
```

**协议栈中的最佳实践**：

| 场景 | 推荐做法 |
|------|---------|
| **头文件 (.h)** | ❌ 绝对不要使用 `using namespace` |
| **源文件 (.cc)** | ✅ 可以在文件顶部使用 `using namespace` |
| **函数内部** | ✅ 可以在小范围内使用 `using namespace` |
| **类定义内部** | ✅ 可以使用 `using` 声明引入基类成员 |

**为什么头文件中不能用 `using namespace`？**

因为头文件会被其他文件 `#include`，如果头文件中有 `using namespace`，所有包含该头文件的代码都会被强制引入整个命名空间，可能导致意外的名称冲突，而且这种冲突很难追踪。

### ☕ Java 类比

C++ 的 `using` 声明和 `using namespace` 对应 Java 的 `import` 机制：

| 对比项 | C++ `using` 声明 | Java `import` |
|--------|-----------------|---------------|
| 引入单个名称 | `using base::Callback;` | `import bluetooth.common.Callback;` |
| 引入整个命名空间 | `using namespace bluetooth;` | `import bluetooth.hci.*;`（通配符导入） |
| 引入静态成员 | `using std::move;` | `import static java.util.Collections.sort;` |
| 重新导出 | `using base::Callback;`（在命名空间内） | 无等价（Java 无法重新导出） |
| 头文件中禁用 | ❌ 头文件中不能用 `using namespace` | ✅ 任何地方都可以 `import` |

**C++ using 声明示例：**

```cpp
using base::Callback;       // 引入单个名称
using namespace bluetooth;  // 引入整个命名空间
```

**Java import 示例：**

```java
import bluetooth.common.Callback;    // 引入单个类
import bluetooth.hci.*;              // 通配符导入
import static java.util.Collections.sort;  // 静态导入
```

> **关键区别**：C++ 的 `using namespace` 比 Java 的通配符 `import` 更危险——C++ 的 `using namespace` 会影响当前编译单元的所有后续代码，且头文件中的 `using namespace` 会"泄漏"给所有包含该头文件的代码。Java 的 `import` 只影响当前文件，不会传播给其他类。C++ 的 `using` 声明可以在命名空间内"重新导出"名称，Java 没有这个功能。

### 📌 本节小结

- `using 命名空间::名称;`只引入一个名称，比`using namespace`更安全
- 派生类中`using Base::func;`可恢复被隐藏的重载函数
- `using`声明比`using namespace`更推荐，精确控制引入的名称
- 蓝牙协议栈中常见`using ::bluetooth::ToResult;`引入特定函数

---

## 6. 命名空间与头文件组织

### 6.1 头文件中的命名空间

头文件中的声明必须放在命名空间中，这是协议栈的基本规范：

```cpp
// system/gd/hci/controller.h
#pragma once

#include "common/contextual_callback.h"
// ... 其他 include

namespace bluetooth {
namespace hci {

class Controller {
public:
  using CompletedAclPacketsCallback =
          common::ContextualCallback<void(uint16_t, uint16_t)>;
  // ... 成员声明
};

}  // namespace hci
}  // namespace bluetooth
```

```cpp
// system/gd/storage/mutation_entry.h
#pragma once

#include <string>
// ... 其他 include

namespace bluetooth {
namespace storage {

class MutationEntry {
public:
  enum EntryType { SET, REMOVE_PROPERTY, REMOVE_SECTION };
  // ... 成员声明
};

}  // namespace storage
}  // namespace bluetooth
```

### 6.2 #include 与命名空间的关系

`#include` 和命名空间是两个独立的概念：

- `#include` 是**预处理指令**，将头文件的内容原样插入到当前位置
- `namespace` 是**语言特性**，控制名称的作用域和可见性

它们的协作关系如下：

```
头文件 A.h                    源文件 B.cc
┌─────────────────────┐      ┌─────────────────────────────┐
│ namespace A {       │      │ #include "A.h"              │
│   class Foo { };    │ ───→ │ #include "C.h"              │
│ }                   │      │                             │
└─────────────────────┘      │ // A::Foo 和 C::Bar 都可用  │
                             │ A::Foo foo;                 │
头文件 C.h                    │ C::Bar bar;                 │
┌─────────────────────┐      └─────────────────────────────┘
│ namespace C {       │
│   class Bar { };    │
│ }                   │
└─────────────────────┘
```

**关键规则**：`#include` 只负责文本替换，不改变命名空间。你必须用命名空间限定名来引用不同命名空间中的类型。

### 6.3 跨命名空间引用

在蓝牙协议栈中，不同模块之间经常需要互相引用。跨命名空间引用的典型模式：

**模式 1：使用完全限定名（最常见）**

```cpp
// 在 bluetooth::os 命名空间中引用 bluetooth::common 的类型
namespace bluetooth {
namespace os {

class Handler : public common::PostableContext {  // 跨命名空间继承
  // ...
  std::queue<common::OnceClosure>* tasks_;        // 跨命名空间使用类型
};

}  // namespace os
}  // namespace bluetooth
```

**模式 2：通过 using 声明重新导出**

```cpp
// bluetooth::common 重新导出 base 命名空间的类型
namespace bluetooth {
namespace common {
using base::Callback;
using base::OnceClosure;
}  // namespace common
}  // namespace bluetooth
```

之后其他命名空间可以通过 `common::Callback` 间接使用 `base::Callback`，无需知道底层实现。

**模式 3：在 .cc 文件中使用 using namespace**

```cpp
// system/stack/connection_manager/connection_manager.cc
using namespace bluetooth;

// 之后可以直接使用 hci::Controller, shim::GetAclManagerLe() 等
// 但仅限此 .cc 文件，不会影响其他编译单元
```

### 6.4 命名空间与目录结构的对应

蓝牙协议栈的命名空间与源码目录有良好的对应关系：

```
目录结构                              命名空间
─────────────────────────────────    ─────────────────────────
system/gd/hci/                   →  bluetooth::hci
system/gd/common/                →  bluetooth::common
system/gd/os/                    →  bluetooth::os
system/gd/storage/               →  bluetooth::storage
system/stack/eatt/               →  bluetooth::eatt
system/main/shim/                →  bluetooth::shim
system/stack/arbiter/            →  bluetooth::shim::arbiter
system/stack/connection_manager/ →  connection_manager
```

> **初学者提示**：这种"目录结构 = 命名空间"的约定不是 C++ 语言强制的，但它是大型项目的最佳实践。遵循这个约定，看到目录名就能猜到命名空间名，反之亦然。

### 6.5 头文件保护与命名空间

每个头文件都应该有包含保护（include guard），并且命名空间声明在保护内部：

```cpp
// 方式1：传统 #ifndef 保护
#ifndef BTM_BLE_API_H
#define BTM_BLE_API_H

namespace bluetooth {
// ...
}  // namespace bluetooth

#endif  // BTM_BLE_API_H

// 方式2：#pragma once（协议栈 GD 模块常用）
#pragma once

namespace bluetooth {
namespace hci {
// ...
}  // namespace hci
}  // namespace bluetooth
```

两种方式都能防止头文件重复包含。`#pragma once` 更简洁，但不是 C++ 标准的一部分；`#ifndef` 方式更通用。协议栈中两种都有使用。

### ☕ Java 类比

C++ 的头文件组织与 Java 的包/模块系统差异很大：

| 对比项 | C++ 头文件 + 命名空间 | Java 包 + import |
|--------|----------------------|-----------------|
| 声明与实现分离 | `.h` 声明 + `.cc` 实现 | 不分离（一个 `.java` 文件包含全部） |
| 包含保护 | `#pragma once` / `#ifndef` | 不需要（Java 自动处理） |
| 声明依赖 | `#include "header.h"` | `import package.Class;` |
| 命名空间与目录 | 约定对应（非强制） | **强制对应**（包名 = 目录路径） |
| 循环依赖 | 可以（前向声明） | 不可以（编译器检测） |
| 跨模块引用 | 完全限定名或 `using` | `import` 或完全限定名 |

> **关键区别**：Java 的包系统比 C++ 的命名空间更严格——Java 强制要求包名与目录结构对应，且一个文件只能属于一个包。C++ 的命名空间是纯逻辑分组，与文件/目录无关。Java 不需要头文件保护，因为 Java 编译器自动处理重复声明问题。

### 📌 本节小结

- 头文件中声明必须放在命名空间中，实现文件中用`namespace`包裹定义
- 头文件中禁止`using namespace`，会污染所有包含该头文件的代码
- 源文件(.cc)中可适度使用`using namespace`，但尽量缩小范围
- 命名空间与目录结构保持一致，便于代码导航

---

## 总结

| 概念 | 语法 | 用途 | 推荐程度 |
|------|------|------|---------|
| 命名空间 | `namespace X { }` | 避免名称冲突 | ⭐⭐⭐⭐⭐ |
| 嵌套命名空间 | `namespace A::B { }` | 组织层级结构 | ⭐⭐⭐⭐⭐ |
| 匿名命名空间 | `namespace { }` | 限制符号在编译单元内可见 | ⭐⭐⭐⭐⭐ |
| using 类型别名 | `using X = Y;` | 简化类型名 | ⭐⭐⭐⭐⭐ |
| typedef | `typedef Y X;` | C 风格类型别名（历史遗留） | ⭐⭐（新代码不用） |
| using 声明 | `using ns::name;` | 引入单个名称 | ⭐⭐⭐⭐ |
| using namespace | `using namespace ns;` | 引入整个命名空间 | ⭐⭐（慎用） |
| 命名空间别名 | `namespace short = long::ns;` | 简化长命名空间 | ⭐⭐⭐⭐ |

**核心原则**：
1. **新代码用 `using`，不用 `typedef`**——`using` 更直观，且支持模板别名
2. **头文件中不用 `using namespace`**——避免污染其他代码的命名空间
3. **源文件中可以适度使用 `using namespace`**——减少冗余前缀，提高可读性
4. **匿名命名空间替代 `static`**——更符合 C++ 风格，功能更强大
5. **命名空间与目录结构保持一致**——便于代码导航和维护

---

## 常见错误

### 1. using namespace 污染全局命名空间

```cpp
// ❌ 在.cc文件顶部
using namespace std;
using namespace bluetooth::hci;
// 之后所有名称冲突风险大增，如distance()、find()等
// ✅ 正确做法：使用完全限定名或using声明
using bluetooth::hci::Channel;  // 只引入需要的名称
```

`using namespace`将整个命名空间的名称引入当前作用域，极易造成名称冲突。尤其在大型项目中，不同命名空间可能有同名符号。

### 2. 头文件中使用 using namespace

```cpp
// ❌ header.h
#pragma once
using namespace std;  // 这会污染所有包含此头文件的代码！
namespace bluetooth {
class Foo { /* ... */ };
}
// ✅ 正确做法：头文件中始终使用完全限定名
namespace bluetooth {
class Foo {
    std::string name_;  // 写全std::string
};
}
```

头文件中的`using namespace`会"泄漏"给所有包含该头文件的源文件，这是最危险的命名空间错误。源文件中可以适度使用，但头文件中绝对禁止。

### 3. 匿名命名空间中定义外部需要的符号

```cpp
// ❌ 在.h文件中使用匿名命名空间
#pragma once
namespace {
    class Helper { /* ... */ };  // 每个包含此头文件的.cc都有独立的Helper类！
}
// ✅ 正确做法：使用命名命名空间
namespace bluetooth {
namespace internal {
    class Helper { /* ... */ };  // 所有编译单元共享同一个Helper
}
}
```

匿名命名空间中的符号在每个编译单元中都是独立的副本。如果在头文件中使用，会导致每个包含该头文件的.cc文件各有一份独立副本，可能造成链接错误或行为不一致。

### 4. typedef 和 using 混用

```cpp
// ❌ 同一项目中混用两种风格
typedef std::shared_ptr<Channel> ChannelPtr;  // 旧风格
using HandlerPtr = std::shared_ptr<Handler>;  // 新风格
// ✅ 统一使用using
using ChannelPtr = std::shared_ptr<Channel>;
using HandlerPtr = std::shared_ptr<Handler>;
```

同一项目中混用`typedef`和`using`会让代码风格不一致，增加阅读负担。新代码应统一使用`using`，更直观且支持模板别名。

---

## 速查卡

| 语法 | 用途 | 示例 | Java类比 |
|------|------|------|---------|
| `namespace` | 避免名称冲突 | `namespace bluetooth { }` | `package bluetooth;` |
| 嵌套命名空间 | 层级组织 | `namespace bluetooth::hci { }` | `package bluetooth.hci;` |
| 匿名命名空间 | 编译单元内可见 | `namespace { void helper(); }` | `private`类成员 |
| `using`别名 | 类型别名 | `using Callback = base::OnceClosure;` | `type Callback = base.OnceClosure;` |
| `typedef` | C风格类型别名 | `typedef base::OnceClosure Callback;` | 无等价 |
| `using`声明 | 引入单个名称 | `using bluetooth::hci::Channel;` | `import bluetooth.hci.Channel;` |
| `using namespace` | 引入整个命名空间 | `using namespace std;` | `import java.util.*;` |
