# Chromium 基础库（base::Callback / Bind / WeakPtr）—— 蓝牙协议栈中的回调安全机制

> **基于 Android 蓝牙协议栈 (Fluoride) 真实代码的 C++ 教材**
>
> 目标读者：需要理解蓝牙协议栈中大量使用的 Chromium 回调机制的 C++ 初学者

---

## 目录

1. [为什么蓝牙协议栈使用 Chromium 基础库](#1-为什么蓝牙协议栈使用-chromium-基础库)
2. [base::OnceCallback 与 base::RepeatingCallback](#2-baseoncecallback-与-baserepeatingcallback)
3. [base::BindOnce 与 base::Bind](#3-basebindonce-与-basebind)
4. [base::WeakPtr 与 base::WeakPtrFactory](#4-baseweakptr-与-baseweakptrfactory)
5. [common::Unretained](#5-commonunretained)
6. [common::BindOnce（GD 架构版本）](#6-commonbindoncegd-架构版本)
7. [common::OnceClosure](#7-commononceclosure)
8. [do_in_main_thread / do_in_main_thread_delayed](#8-do_in_main_thread--do_in_main_thread_delayed)
9. [回调安全模式总结](#9-回调安全模式总结)
10. [常见错误与调试](#10-常见错误与调试)

---

## 1. 为什么蓝牙协议栈使用 Chromium 基础库

### 1.1 Android 框架的 Chromium 依赖

Android 系统本身就内置了 Chromium 的基础库（`base` 命名空间）。蓝牙协议栈作为 Android 框架的一部分，自然也使用这些基础设施。你在代码中看到的头文件引用就说明了这一点：

```cpp
// system/stack/include/btm_ble_api.h:28
#include <base/functional/callback_forward.h>

// system/stack/connection_manager/connection_manager.cc:21-22
#include <base/functional/bind.h>
#include <base/functional/callback.h>
```

这些不是第三方库，而是 Android 系统自带的、经过大规模生产验证的基础设施。

### 1.2 替代裸函数指针的必要性

在早期的 C 代码中，异步回调通常用裸函数指针 + `void*` 上下文来实现：

```cpp
// 旧式回调：裸函数指针 + void* 上下文
typedef void (*tBTM_CMPL_CB)(void* p_data);

// 使用时
void some_function(void* context) {
    MyObject* obj = (MyObject*)context;  // 危险！类型不安全
    obj->do_something();                  // 如果 obj 已被销毁？崩溃！
}
```

这种方式有严重问题：
- **类型不安全**：`void*` 可以传入任何类型，编译器无法检查
- **生命周期无法管理**：如果回调执行时对象已被销毁，就会访问已释放的内存（use-after-free）
- **无法绑定参数**：调用者必须自己管理额外的参数传递

Chromium 的 `base::Callback` + `base::Bind` 组合完美解决了这些问题。

### 1.3 异步编程的核心需求

蓝牙协议栈是一个高度异步的系统。考虑以下场景：

1. **发起连接请求** → 等待远端响应 → **收到回调通知连接结果**
2. **读取 GATT 特征值** → 等待硬件返回 → **收到回调通知读取结果**
3. **设置定时器** → 等待超时 → **收到回调执行超时处理**

这些场景都需要"把一段代码投递到未来某个时刻执行"，这正是回调机制的核心用途。

---

## 2. base::OnceCallback 与 base::RepeatingCallback

### 2.1 核心概念

Chromium 提供了两种回调类型，它们代表了两种不同的使用语义：

| 类型 | 含义 | 可调用次数 | 移动语义 |
|------|------|-----------|---------|
| `base::OnceCallback<Signature>` | 一次性回调 | **只能调用一次** | 只能移动，不能拷贝 |
| `base::RepeatingCallback<Signature>` | 可重复回调 | **可以多次调用** | 可以拷贝 |

`Signature` 是函数签名，例如 `void(int, std::string)` 表示参数为 `int` 和 `std::string`，返回值为 `void`。

### 2.2 OnceCallback：只能调用一次

```cpp
base::OnceCallback<void(int status, const RawAddress& addr)> callback;

// 调用方式：必须用 std::move 转移所有权
std::move(callback).Run(0, some_address);

// 调用后 callback 变为空，再次调用是未定义行为！
```

为什么需要"只能调用一次"的回调？因为在异步编程中，很多操作天然就是一次性的：

- 连接请求的结果只会来一次
- GATT 读取的响应只会来一次
- 定时器触发的回调只需执行一次

用 `OnceCallback` 可以在**编译期和运行时**防止回调被意外调用多次，这是一种安全保证。

### 2.3 RepeatingCallback：可以多次调用

```cpp
base::RepeatingCallback<void(uint16_t sync_handle, int8_t rssi)> callback;

// 可以直接调用，无需 std::move
callback.Run(handle1, rssi1);
callback.Run(handle2, rssi2);  // 再次调用，完全合法
```

### 2.4 蓝牙协议栈中的真实示例

#### 示例 1：RepeatingCallback 用于周期性同步报告

```cpp
// system/stack/include/btm_ble_api.h:373-380
using StartSyncCb = base::Callback<void(
    uint8_t /*status*/, uint16_t /*sync_handle*/, uint8_t /*advertising_sid*/,
    uint8_t /*address_type*/, RawAddress /*address*/, uint8_t /*phy*/, uint16_t /*interval*/)>;

using SyncReportCb =
    base::Callback<void(uint16_t /*sync_handle*/, int8_t /*tx_power*/, int8_t /*rssi*/,
                        uint8_t /*status*/, std::vector<uint8_t> /*data*/)>;

using SyncLostCb = base::Callback<void(uint16_t /*sync_handle*/)>;
using BigInfoReportCb = base::Callback<void(uint16_t /*sync_handle*/, bool /*encrypted*/)>;
```

> **注意**：这里的 `base::Callback` 实际上是 `base::RepeatingCallback` 的别名。在 Chromium 的早期版本中，`base::Callback` 就是可重复回调。后来为了语义清晰，引入了 `OnceCallback` 和 `RepeatingCallback` 的区分，但 `base::Callback` 仍作为 `RepeatingCallback` 的别名保留。

为什么 `SyncReportCb` 用 RepeatingCallback？因为周期性同步报告会**持续不断地到来**，回调会被多次调用。

#### 示例 2：OnceCallback 用于一次性操作

```cpp
// system/stack/include/main_thread.h:31
bt_status_t do_in_main_thread(base::OnceClosure task);
```

`do_in_main_thread` 接受一个 `base::OnceClosure`（即 `base::OnceCallback<void()>`），因为投递到主线程的任务只需要执行一次。

#### 示例 3：std::function 与 base::Callback 的混用

```cpp
// system/stack/include/main_thread.h:26
using BtMainClosure = std::function<void()>;
```

在蓝牙协议栈中，你也会看到 `std::function` 的使用。这通常出现在不需要 Chromium 回调的特殊生命周期管理、或者与旧代码兼容的场景中。`std::function` 更通用，但不提供 `OnceCallback` 的"只调用一次"语义保证。

### 2.5 与 std::function 的区别

| 特性 | `base::OnceCallback` | `base::RepeatingCallback` | `std::function` |
|------|---------------------|--------------------------|----------------|
| 调用次数 | 只能一次 | 可以多次 | 可以多次 |
| 拷贝 | 禁止 | 允许 | 允许 |
| 移动 | 允许 | 允许 | 允许 |
| 空状态检查 | `is_null()` | `is_null()` | `operator bool()` |
| 生命周期辅助 | 配合 WeakPtr/Unretained | 配合 WeakPtr/Unretained | 无（需手动管理） |
| 调用方式 | `std::move(cb).Run()` | `cb.Run()` | `cb()` |

**关键区别**：`base::Callback` 系列配合 `base::Bind` 提供了 `WeakPtr` 和 `Unretained` 等生命周期管理辅助工具，而 `std::function` + `std::bind` 没有这些安全机制。这就是蓝牙协议栈选择 Chromium 回调体系的核心原因。

---

## 3. base::BindOnce 与 base::Bind

### 3.1 核心概念

`Bind` 的作用是**把一个函数和它的部分（或全部）参数"打包"成一个回调对象**。你可以在绑定时就确定部分参数，剩下的参数在回调被调用时再传入。

```
函数 + 已知参数 ──Bind──▶ 回调对象（等待剩余参数）
回调对象 + 剩余参数 ──Run──▶ 执行函数
```

| 函数 | 产生的回调类型 |
|------|--------------|
| `base::BindOnce(...)` | `base::OnceCallback` |
| `base::Bind(...)` | `base::RepeatingCallback` |

### 3.2 绑定自由函数

```cpp
// 自由函数（不属于任何类）
void schedule_direct_connect_add(uint8_t app_id, const RawAddress& address);

// 绑定所有参数，生成一个无参回调
auto callback = base::BindOnce(schedule_direct_connect_add, app_id, addr);

// 等价于：调用 schedule_direct_connect_add(app_id, addr)
std::move(callback).Run();
```

**真实代码**：

```cpp
// system/stack/connection_manager/connection_manager.cc:237
do_in_main_thread(base::BindOnce(schedule_direct_connect_add, app_id, addr));
```

这里 `schedule_direct_connect_add` 是一个自由函数（静态函数），`app_id` 和 `addr` 在绑定时就确定了。投递到主线程后，主线程只需调用 `Run()` 即可执行。

### 3.3 绑定成员函数

绑定成员函数时，**第一个参数必须是对象的指针或弱指针**，表示"在哪个对象上调用这个方法"：

```cpp
// 成员函数
void eatt_impl::upper_tester_delay_connect_cb(const RawAddress& bda);

// 绑定成员函数 + 弱指针 + 额外参数
auto callback = base::BindOnce(
    &eatt_impl::upper_tester_delay_connect_cb,  // 成员函数指针
    weak_factory_.GetWeakPtr(),                   // 对象的弱指针
    bda                                           // 额外参数
);
```

**真实代码**：

```cpp
// system/stack/eatt/eatt_impl.h:251-254
bt_status_t status = do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::upper_tester_delay_connect_cb,
                   weak_factory_.GetWeakPtr(), bda),
    std::chrono::milliseconds(timeout_ms));
```

### 3.4 更多真实示例

#### 示例 1：延迟重配置

```cpp
// system/stack/eatt/eatt_impl.h:293-295
bt_status_t status = do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::reconfigure_all, weak_factory_.GetWeakPtr(), bda, 300),
    std::chrono::seconds(4));
```

解读：
- 函数：`eatt_impl::reconfigure_all`
- 对象：`weak_factory_.GetWeakPtr()`（弱指针，见第 4 节）
- 参数：`bda`（设备地址），`300`（新 MTU 值）
- 延迟：4 秒后执行

#### 示例 2：GATT 特征读取回调

```cpp
// system/stack/eatt/eatt_impl.h:947-948
gatt_cl_read_sr_supp_feat_req(bd_addr,
    base::BindOnce(&eatt_impl::supported_features_cb, weak_factory_.GetWeakPtr(), role));
```

解读：
- 发起 GATT 读取请求，同时注册一个一次性回调
- 当读取完成时，回调会被调用，传入读取结果
- `role` 参数在绑定时就确定了，读取结果会在 `Run()` 时作为额外参数传入

#### 示例 3：定时器超时回调

```cpp
// system/stack/connection_manager/connection_manager.cc:591-592
alarm_set_closure(timeout, DIRECT_CONNECT_TIMEOUT,
    base::BindOnce(&wl_direct_connect_timeout_cb, app_id, address));
```

解读：
- `wl_direct_connect_timeout_cb` 是一个静态函数
- 30 秒后如果连接未完成，定时器触发，执行该回调
- `app_id` 和 `address` 在绑定时确定

### 3.5 BindOnce vs Bind 的选择原则

```
你需要这个回调被调用几次？
│
├─ 只调用一次 ──▶ base::BindOnce → base::OnceCallback
│   （绝大多数异步操作：连接结果、读取结果、超时处理...）
│
└─ 可能多次调用 ──▶ base::Bind → base::RepeatingCallback
    （周期性报告、事件监听、可重复注册的通知...）
```

在蓝牙协议栈中，**绝大多数场景使用 `BindOnce`**，因为大部分异步操作都是一次性的。

---

## 4. base::WeakPtr 与 base::WeakPtrFactory

### 4.1 为什么需要弱指针

考虑这个场景：

```cpp
// 在主线程上注册了一个延迟回调
do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::reconfigure_all, ???, bda, 300),
    std::chrono::seconds(4));

// 问题：4 秒后回调执行时，eatt_impl 对象还存在吗？
```

如果 `eatt_impl` 对象在 4 秒内被销毁了，而回调中仍然持有指向它的裸指针，调用成员函数就会导致 **use-after-free**——访问已释放的内存，造成崩溃或安全漏洞。

`base::WeakPtr` 就是解决这个问题的：

- **如果对象还活着**：弱指针有效，回调正常执行
- **如果对象已被销毁**：弱指针变为空，回调被安全忽略（不执行）

### 4.2 WeakPtrFactory 的使用模式

```cpp
struct eatt_impl {
    // ... 其他成员变量 ...

    // WeakPtrFactory 必须是最后一个成员变量！
    base::WeakPtrFactory<eatt_impl> weak_factory_{this};
};
```

**真实代码**：

```cpp
// system/stack/eatt/eatt_impl.h:72
base::WeakPtrFactory<eatt_impl> weak_factory_{this};
```

### 4.3 GetWeakPtr() 获取弱指针

```cpp
// 获取弱指针
base::WeakPtr<eatt_impl> weak_ptr = weak_factory_.GetWeakPtr();

// 传递给回调
base::BindOnce(&eatt_impl::some_method, weak_factory_.GetWeakPtr(), arg1, arg2);
```

`GetWeakPtr()` 每次调用都返回一个新的弱指针对象，但它们都指向同一个原始对象。当原始对象被销毁时，`WeakPtrFactory` 的析构函数会使所有弱指针失效。

### 4.4 弱指针在回调中的工作原理

当你把 `WeakPtr` 传给 `base::BindOnce` 绑定成员函数时，回调的执行逻辑如下：

```
回调被调用 (Run())
│
├─ 检查 WeakPtr 是否有效
│   │
│   ├─ 有效（对象还活着）──▶ 调用成员函数
│   │
│   └─ 无效（对象已销毁）──▶ 什么都不做，安全返回
│
└─ 不会崩溃！
```

### 4.5 核心真实示例详解

#### 示例 1：声明 WeakPtrFactory

```cpp
// system/stack/eatt/eatt_impl.h:65-72
struct eatt_impl {
    std::vector<eatt_device> devices_;
    uint16_t psm_;
    uint16_t default_mtu_;
    uint16_t max_mps_;
    tL2CAP_APPL_INFO reg_info_;

    base::WeakPtrFactory<eatt_impl> weak_factory_{this};  // 最后一个成员！
};
```

#### 示例 2：绑定成员函数 + 弱指针（延迟回调）

```cpp
// system/stack/eatt/eatt_impl.h:251-254
bt_status_t status = do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::upper_tester_delay_connect_cb,
                   weak_factory_.GetWeakPtr(), bda),
    std::chrono::milliseconds(timeout_ms));
```

**执行流程**：
1. `base::BindOnce` 将 `&eatt_impl::upper_tester_delay_connect_cb`、弱指针和 `bda` 打包成回调
2. `do_in_main_thread_delayed` 将回调投递到主线程，延迟 `timeout_ms` 毫秒执行
3. 延迟到期时，主线程尝试执行回调
4. 如果 `eatt_impl` 对象仍然存在 → 调用 `upper_tester_delay_connect_cb(bda)`
5. 如果 `eatt_impl` 对象已被销毁 → 弱指针无效，回调被忽略

#### 示例 3：延迟重配置 + 弱指针

```cpp
// system/stack/eatt/eatt_impl.h:293-295
bt_status_t status = do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::reconfigure_all, weak_factory_.GetWeakPtr(), bda, 300),
    std::chrono::seconds(4));
```

4 秒后尝试重配置所有通道。如果 `eatt_impl` 在这 4 秒内被销毁（比如蓝牙关闭），回调会被安全忽略。

#### 示例 4：GATT 读取回调 + 弱指针

```cpp
// system/stack/eatt/eatt_impl.h:947-948
gatt_cl_read_sr_supp_feat_req(bd_addr,
    base::BindOnce(&eatt_impl::supported_features_cb, weak_factory_.GetWeakPtr(), role));
```

GATT 读取是异步操作，结果可能很久才回来。如果期间 `eatt_impl` 被销毁，回调安全忽略。

#### 示例 5：重配置完成后的延迟数据发送

```cpp
// system/stack/eatt/eatt_impl.h:443-446
do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::upper_tester_send_data_if_needed,
                   weak_factory_.GetWeakPtr(), bda, lcid),
    std::chrono::seconds(1));
```

### 4.6 为什么 WeakPtrFactory 必须是最后一个成员变量

这是 C++ 对象析构顺序决定的：

```
构造顺序：按成员声明顺序（先声明的先构造）
析构顺序：与构造顺序相反（后声明的先析构）
```

如果 `WeakPtrFactory` 不是最后一个成员：

```cpp
struct BadExample {
    base::WeakPtrFactory<BadExample> weak_factory_{this};  // 第一个成员
    std::vector<BigData> data_;                             // 后面的成员
};
```

析构时：
1. `data_` 先析构（后声明，先析构）
2. `weak_factory_` 后析构

问题在于：在 `data_` 析构之后、`weak_factory_` 析构之前，如果有回调尝试通过弱指针访问对象，弱指针仍然显示"有效"（因为 `weak_factory_` 还没析构），但 `data_` 已经被销毁了！这会导致访问已析构的成员。

**正确做法**：`WeakPtrFactory` 放在最后，确保它最先析构。析构时 `WeakPtrFactory` 会立即使所有弱指针失效，这样在后续成员析构期间，不会有任何回调能通过弱指针访问对象。

```cpp
struct GoodExample {
    std::vector<BigData> data_;                             // 先声明
    OtherMembers members_;                                   // 中间声明
    base::WeakPtrFactory<GoodExample> weak_factory_{this};  // 最后声明！
};
```

### 4.7 弱指针可以跨线程传递

`GetWeakPtr()` 返回的弱指针可以安全地传递给其他线程。这是 `base::WeakPtr` 的重要特性：

```cpp
// 在线程 A 上获取弱指针
auto weak_ptr = weak_factory_.GetWeakPtr();

// 传递给线程 B 的回调
do_in_main_thread(
    base::BindOnce(&MyClass::on_complete, weak_ptr, result));
```

当回调在线程 B 上执行时，会检查弱指针是否有效。但请注意：**弱指针的失效检查和回调执行应该在同一个线程上**，以避免竞态条件。在蓝牙协议栈中，回调通常在主线程上执行，而 `WeakPtrFactory` 的析构也在主线程上，所以是安全的。

---

## 5. common::Unretained

### 5.1 什么是 Unretained

`Unretained` 是一个**不管理生命周期的裸指针包装器**。它告诉 `base::Bind`："我知道这个对象的生命周期，不需要你来管理。"

```cpp
// Unretained 的本质：就是裸指针，不做任何生命周期管理
template <typename T>
base::UnretainedWrapper<T> Unretained(T* ptr) {
    return base::UnretainedWrapper<T>(ptr);
}
```

### 5.2 Unretained vs WeakPtr

| 特性 | `WeakPtr` | `Unretained` |
|------|-----------|-------------|
| 生命周期管理 | 自动检测对象是否存活 | 不管理，完全靠开发者保证 |
| 对象销毁后 | 回调被安全忽略 | **未定义行为（崩溃）** |
| 性能开销 | 有轻微开销（检查引用计数） | 几乎无开销 |
| 适用场景 | 对象可能被销毁的异步回调 | 对象生命周期由其他机制保证 |

### 5.3 什么时候使用 Unretained

使用 `Unretained` 的前提是：**你能确保在回调执行时，对象一定还活着。**

常见的安全场景：
1. **对象的生命周期由 Handler 管理**：Handler 在析构时会清除所有待处理的任务
2. **对象是全局单例**：程序运行期间始终存在
3. **同步调用**：回调在当前调用栈内执行，对象不可能被销毁

### 5.4 真实示例

#### 示例 1：Handler::CallOn — Handler 保证对象生命周期

```cpp
// system/gd/os/handler.h:83-87
template <typename T, typename Functor, typename... Args>
void CallOn(T* obj, Functor&& functor, Args&&... args) {
    Post(common::BindOnce(std::forward<Functor>(functor), common::Unretained(obj),
                          std::forward<Args>(args)...));
}
```

**为什么这里用 `Unretained` 是安全的？**

`Handler::CallOn` 的设计契约是：调用者必须确保 `obj` 的生命周期覆盖 Handler 的生命周期。Handler 在析构时会调用 `Clear()` 清除所有待处理任务，所以当回调执行时，Handler 还活着，而 `obj` 的生命周期又覆盖 Handler，因此 `obj` 也一定还活着。

#### 示例 2：Synchronize — promise 在当前栈上

```cpp
// system/gd/os/handler.h:98-103
bool Synchronize(std::chrono::milliseconds timeout) {
    std::promise<void> promise;
    auto future = promise.get_future();
    Post(common::BindOnce(&std::promise<void>::set_value, common::Unretained(&promise)));
    return future.wait_for(timeout) == std::future_status::ready;
}
```

**为什么安全？** `promise` 是栈上的局部变量，`Synchronize` 函数会阻塞等待 `future`，所以 `promise` 在回调执行时一定还活着。

#### 示例 3：GD 架构中大量的 Unretained 使用

```cpp
// system/gd/hci/acl_manager/le_impl.h:162
common::Bind(&le_impl::enqueue_command, common::Unretained(this))

// system/gd/hci/acl_manager/le_impl.h:356-357
le_client_handler_->Post(common::BindOnce(
    &LeConnectionCallbacks::OnLeConnectFail,
    common::Unretained(le_client_callbacks_), address, status);

// system/gd/hci/le_advertising_manager_impl.cc:407-408
common::BindOnce(&impl::set_advertising_set_random_address_on_timer,
                 common::Unretained(this), advertiser_id)
```

在 GD 架构中，`Unretained` 被大量使用，因为 GD 的 `Handler` 机制保证了：当对象被销毁时，Handler 会被先清除，所有待处理的回调都会被丢弃，不会执行。

### 5.5 Unretained 的风险

```cpp
// 危险！如果 my_object 在回调执行前被销毁，就会崩溃
do_in_main_thread_delayed(
    base::BindOnce(&MyClass::on_timeout, base::Unretained(my_object)),
    std::chrono::seconds(5));
```

如果你不确定对象是否会在回调执行时存活，**一定要用 `WeakPtr`**，不要用 `Unretained`。

---

## 6. common::BindOnce（GD 架构版本）

### 6.1 GD 架构的回调命名空间

蓝牙协议栈有两套并存的架构：

- **传统架构**（`system/stack/`）：直接使用 `base::BindOnce`、`base::Bind` 等
- **GD 架构**（`system/gd/`）：使用 `common::BindOnce`、`common::Bind` 等

GD 架构通过别名机制将 `base` 命名空间的类型重新导出到 `common` 命名空间：

```cpp
// system/gd/common/bind.h:24-30
namespace bluetooth {
namespace common {

using base::Bind;
using base::BindOnce;
using base::IgnoreResult;
using base::Owned;
using base::Passed;
using base::RetainedRef;
using base::Unretained;

}  // namespace common
}  // namespace bluetooth
```

```cpp
// system/gd/common/callback.h:24-27
namespace bluetooth {
namespace common {

using base::Callback;
using base::Closure;
using base::OnceCallback;
using base::OnceClosure;

}  // namespace common
}  // namespace bluetooth
```

所以 `common::BindOnce` 和 `base::BindOnce` **是完全相同的东西**，只是命名空间不同。GD 架构使用 `common` 命名空间是为了解耦——如果将来要替换底层实现，只需修改 `common/bind.h` 中的别名即可。

### 6.2 GD 架构中的额外工具：BindOn

GD 架构在 `common` 命名空间中额外提供了 `BindOn`，这是一个便捷的"绑定成员函数 + Unretained"的组合：

```cpp
// system/gd/common/bind.h:32-36
template <typename T, typename Functor, typename... Args>
inline auto BindOn(T* obj, Functor&& functor, Args&&... args) {
    return common::Bind(std::forward<Functor>(functor), common::Unretained(obj),
                        std::forward<Args>(args)...);
}
```

使用示例：

```cpp
// 等价于 common::Bind(&MyClass::method, common::Unretained(obj), arg1)
auto callback = common::BindOn(obj, &MyClass::method, arg1);
```

### 6.3 PostableContext 中的 BindOnceOn

`PostableContext` 进一步封装了"绑定 + 投递"的模式：

```cpp
// system/gd/common/postable_context.h:35-41
template <typename Functor, typename T, typename... Args>
auto BindOnceOn(T* obj, Functor&& functor, Args&&... args) {
    return common::ContextualOnceCallback(
            common::BindOnce(std::forward<Functor>(functor), common::Unretained(obj),
                             std::forward<Args>(args)...),
            this);
}
```

这会创建一个"上下文回调"——回调不仅绑定了函数和参数，还绑定了执行上下文（哪个 Handler），调用时会自动投递到对应的 Handler 上执行。

### 6.4 GD 架构中 Handler 的使用模式

```cpp
// system/gd/os/handler.h:78-81
template <typename Functor, typename... Args>
void Call(Functor&& functor, Args&&... args) {
    Post(common::BindOnce(std::forward<Functor>(functor), std::forward<Args>(args)...));
}

// system/gd/os/handler.h:83-87
template <typename T, typename Functor, typename... Args>
void CallOn(T* obj, Functor&& functor, Args&&... args) {
    Post(common::BindOnce(std::forward<Functor>(functor), common::Unretained(obj),
                          std::forward<Args>(args)...));
}
```

- `Call(functor, args...)`：投递一个自由函数/lambda 到 Handler
- `CallOn(obj, functor, args...)`：投递一个成员函数调用到 Handler，用 `Unretained` 绑定对象

---

## 7. common::OnceClosure

### 7.1 什么是 Closure

**Closure** 是"无参数、无返回值的回调"的简称：

```cpp
// OnceClosure 等价于
using OnceClosure = base::OnceCallback<void()>;

// RepeatingClosure 等价于
using RepeatingClosure = base::RepeatingCallback<void()>;
```

### 7.2 真实示例

#### 示例 1：Handler 的任务队列

```cpp
// system/gd/os/handler.h:37
using DelayedTask = std::pair<TimePoint, common::OnceClosure>;
```

`DelayedTask` 是一个时间点 + 闭包的配对，表示"在某个时刻执行一个无参回调"。

#### 示例 2：Handler::Post 接口

```cpp
// system/gd/os/handler.h:70
virtual void Post(common::OnceClosure closure) override;
```

`Post` 方法接受一个 `OnceClosure`，将其放入 Handler 的任务队列中等待执行。

#### 示例 3：Handler 内部的任务队列

```cpp
// system/gd/os/handler.h:120
std::queue<common::OnceClosure>* tasks_ GUARDED_BY(mutex_);
```

Handler 内部维护一个 `OnceClosure` 队列，所有投递的任务都存储在这里。

#### 示例 4：连接管理器中的闭包包装

```cpp
// system/stack/connection_manager/connection_manager.cc:56-58
struct closure_data {
    base::OnceClosure user_task;
};
```

`closure_data` 将 `OnceClosure` 包装起来，因为旧式的定时器 API 只接受 `void*` 上下文：

```cpp
// system/stack/connection_manager/connection_manager.cc:62-66
static void alarm_closure_cb(void* p) {
    closure_data* data = (closure_data*)p;
    std::move(data->user_task).Run();
    delete data;
}

// system/stack/connection_manager/connection_manager.cc:69-73
static void alarm_set_closure(alarm_t* alarm, uint64_t interval_ms, base::OnceClosure user_task) {
    closure_data* data = new closure_data;
    data->user_task = std::move(user_task);
    alarm_set_on_mloop(alarm, interval_ms, alarm_closure_cb, data);
}
```

这是一个经典的"桥接"模式：将现代的 `base::OnceClosure` 适配到旧式的 `void*` 回调接口中。

#### 示例 5：队列的空回调通知

```cpp
// system/gd/os/queue.h:151
void NotifyOnEmpty(common::OnceClosure callback) { ... }

// system/gd/os/queue.h:175
common::OnceClosure callback_on_empty_;
```

当队列变为空时，执行一个一次性回调通知。

---

## 8. do_in_main_thread / do_in_main_thread_delayed

### 8.1 蓝牙主线程模型

蓝牙协议栈使用单主线程模型：所有协议栈操作都必须在主线程上执行。如果当前不在主线程，就需要通过 `do_in_main_thread` 将任务投递过去。

```cpp
// system/stack/include/main_thread.h:31-32
bt_status_t do_in_main_thread(base::OnceClosure task);
bt_status_t do_in_main_thread_delayed(base::OnceClosure task, std::chrono::microseconds delay);
```

- `do_in_main_thread`：立即投递到主线程
- `do_in_main_thread_delayed`：延迟投递到主线程

### 8.2 真实示例详解

#### 示例 1：立即投递 — 从扫描回调切换到主线程

```cpp
// system/stack/connection_manager/connection_manager.cc:237
do_in_main_thread(base::BindOnce(schedule_direct_connect_add, app_id, addr));
```

**场景**：扫描回调 `target_announcement_observe_results_cb` 可能在扫描线程上执行，但直接连接操作必须在主线程上进行。所以通过 `do_in_main_thread` 将任务投递过去。

#### 示例 2：延迟投递 — EATT 延迟连接

```cpp
// system/stack/eatt/eatt_impl.h:251-254
bt_status_t status = do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::upper_tester_delay_connect_cb,
                   weak_factory_.GetWeakPtr(), bda),
    std::chrono::milliseconds(timeout_ms));
```

**场景**：在 L2CAP 碰撞后，延迟一段时间再尝试建立 EATT 连接，避免冲突。

#### 示例 3：延迟投递 — EATT 重配置

```cpp
// system/stack/eatt/eatt_impl.h:293-295
bt_status_t status = do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::reconfigure_all, weak_factory_.GetWeakPtr(), bda, 300),
    std::chrono::seconds(4));
```

**场景**：EATT 通道建立后 4 秒，发起重配置请求（将 MTU 改为 300）。

#### 示例 4：定时器超时 — 直接连接超时

```cpp
// system/stack/connection_manager/connection_manager.cc:589-592
alarm_t* timeout = alarm_new("wl_conn_params_30s");
alarm_set_closure(timeout, DIRECT_CONNECT_TIMEOUT,
    base::BindOnce(&wl_direct_connect_timeout_cb, app_id, address));
```

**场景**：发起直接连接后，设置 30 秒超时定时器。如果 30 秒内连接未完成，执行超时回调，将连接模式从直接连接降级为后台连接。

### 8.3 do_in_main_thread 与 Handler::Post 的对比

| 特性 | `do_in_main_thread` | `Handler::Post` |
|------|-------------------|----------------|
| 所属架构 | 传统架构 | GD 架构 |
| 线程目标 | 固定为主线程 | Handler 绑定的线程 |
| 回调类型 | `base::OnceClosure` | `common::OnceClosure` |
| 延迟支持 | `do_in_main_thread_delayed` | `PostWithDelay` |
| 生命周期安全 | 需要手动使用 WeakPtr | Handler 清除时丢弃待处理任务 |

---

## 9. 回调安全模式总结

### 9.1 决策流程图

```
你需要注册一个异步回调
│
├─ 回调执行时，对象可能已被销毁吗？
│   │
│   ├─ 可能 ──▶ 使用 WeakPtr + GetWeakPtr()
│   │           （绝大多数异步回调场景）
│   │
│   └─ 不可能 ──▶ 使用 Unretained
│                （Handler 管理生命周期、全局单例、同步调用）
│
├─ 回调会被调用几次？
│   │
│   ├─ 只一次 ──▶ BindOnce + OnceCallback
│   │
│   └─ 多次 ──▶ Bind + RepeatingCallback
│
└─ 回调需要投递到哪个线程？
    │
    ├─ 主线程 ──▶ do_in_main_thread / do_in_main_thread_delayed
    │
    └─ Handler 绑定的线程 ──▶ Handler::Post / Handler::Call / Handler::CallOn
```

### 9.2 模式速查表

| 场景 | 推荐方式 | 示例 |
|------|---------|------|
| 异步回调到可能被销毁的对象 | `WeakPtr` + `GetWeakPtr()` | `BindOnce(&Cls::method, weak_factory_.GetWeakPtr(), args...)` |
| 同步调用或对象生命周期确定 | `Unretained` | `BindOnce(&Cls::method, Unretained(obj), args...)` |
| 一次性操作 | `BindOnce` + `OnceCallback` | `BindOnce(&Cls::on_complete, weak_ptr, result)` |
| 重复操作 | `Bind` + `RepeatingCallback` | `Bind(&Cls::on_report, weak_ptr)` |
| 投递到主线程 | `do_in_main_thread` | `do_in_main_thread(BindOnce(func, args...))` |
| 延迟投递到主线程 | `do_in_main_thread_delayed` | `do_in_main_thread_delayed(BindOnce(...), delay)` |
| GD 架构投递任务 | `Handler::Post` / `Call` / `CallOn` | `handler->CallOn(obj, &Cls::method, args...)` |
| 无参无返回值回调 | `OnceClosure` | `Post(OnceClosure)` |

### 9.3 蓝牙协议栈中的典型模式

#### 模式 1：WeakPtr + BindOnce + do_in_main_thread_delayed（最常见）

```cpp
// 1. 类中声明 WeakPtrFactory（最后一个成员）
struct MyManager {
    // ... 其他成员 ...
    base::WeakPtrFactory<MyManager> weak_factory_{this};
};

// 2. 延迟投递回调
do_in_main_thread_delayed(
    base::BindOnce(&MyManager::on_timeout,
                   weak_factory_.GetWeakPtr(), device_addr),
    std::chrono::seconds(5));
```

#### 模式 2：Unretained + Handler::CallOn（GD 架构常见）

```cpp
// Handler 保证对象生命周期
handler_->CallOn(this, &MyClass::handle_event, event_data);
```

#### 模式 3：自由函数 + BindOnce（无对象生命周期问题）

```cpp
do_in_main_thread(
    base::BindOnce(schedule_direct_connect_add, app_id, addr));
```

---

## 10. 常见错误与调试

### 10.1 忘记用 WeakPtr 导致的 use-after-free

**错误代码**：

```cpp
do_in_main_thread_delayed(
    base::BindOnce(&MyManager::on_timeout,
                   base::Unretained(this), device_addr),  // 危险！
    std::chrono::seconds(5));

// 如果 MyManager 在 5 秒内被销毁，回调执行时访问已释放的内存
```

**正确代码**：

```cpp
do_in_main_thread_delayed(
    base::BindOnce(&MyManager::on_timeout,
                   weak_factory_.GetWeakPtr(), device_addr),  // 安全！
    std::chrono::seconds(5));

// 如果 MyManager 被销毁，弱指针失效，回调被忽略
```

**调试方法**：
- 使用 AddressSanitizer (ASan) 检测 use-after-free
- 在析构函数中加日志，确认对象是否在回调之前被销毁
- 检查所有 `Unretained` 的使用，确认对象生命周期是否真的有保证

### 10.2 OnceCallback 被调用两次

**错误代码**：

```cpp
base::OnceCallback<void(int)> callback = base::BindOnce(&on_result);
callback.Run(0);       // 第一次调用，OK
std::move(callback).Run(1);  // 第二次调用，未定义行为！
```

**正确理解**：
- `OnceCallback` 设计为只能调用一次
- 调用后必须通过 `std::move` 转移所有权
- 调用后回调对象变为空（`is_null()` 返回 `true`）
- 在蓝牙协议栈中，`OnceCallback` 通常通过 `std::move` 传递给异步操作，调用者不再持有引用

**调试方法**：
- 在 Debug 构建中，Chromium 会对 `OnceCallback` 的重复调用进行断言检查
- 检查是否有代码路径导致同一个回调被传递给多个接收者

### 10.3 在错误线程调用回调

**错误场景**：

```cpp
// 在非主线程上直接调用协议栈函数
void some_callback_on_wrong_thread() {
    // 危险！蓝牙协议栈要求在主线程上操作
    direct_connect_add(app_id, address);
}
```

**正确做法**：

```cpp
void some_callback_on_wrong_thread() {
    // 投递到主线程执行
    do_in_main_thread(base::BindOnce(direct_connect_add, app_id, address));
}
```

**调试方法**：
- 在关键函数入口添加线程检查断言
- 使用 `get_main_thread()->IsRunningOnCurrentThread()` 检查当前是否在主线程
- 蓝牙协议栈中很多函数在 Debug 模式下会自动检查线程

### 10.4 WeakPtrFactory 不是最后一个成员

**错误代码**：

```cpp
struct BadExample {
    base::WeakPtrFactory<BadExample> weak_factory_{this};  // 第一个成员
    std::vector<Channel> channels_;                         // 后面的成员可能已被析构
};
```

**正确代码**：

```cpp
struct GoodExample {
    std::vector<Channel> channels_;                         // 先声明
    base::WeakPtrFactory<GoodExample> weak_factory_{this};  // 最后声明！
};
```

### 10.5 混淆 base:: 和 common:: 命名空间

虽然 `common::BindOnce` 和 `base::BindOnce` 本质相同，但在同一文件中混用会导致代码不一致，增加维护成本。

**建议**：
- 在传统架构代码（`system/stack/`）中使用 `base::` 命名空间
- 在 GD 架构代码（`system/gd/`）中使用 `common::` 命名空间
- 不要在同一个文件中混用两种命名空间

### 10.6 忘记 std::move 传递 OnceCallback

**错误代码**：

```cpp
void process_callback(base::OnceClosure task) {
    // 错误！OnceCallback 不能拷贝
    do_in_main_thread(task);  // 编译错误
}
```

**正确代码**：

```cpp
void process_callback(base::OnceClosure task) {
    do_in_main_thread(std::move(task));  // 必须用 std::move
}
```

### 10.7 调试技巧总结

| 问题 | 调试方法 |
|------|---------|
| use-after-free | ASan + 检查所有 Unretained 使用 |
| 回调未执行 | 检查 WeakPtr 是否失效（对象是否已析构） |
| 回调执行两次 | 检查 OnceCallback 是否被重复调用 |
| 线程错误 | 添加线程断言检查 |
| 回调参数错误 | 检查 Bind 时的参数类型和数量是否匹配 |
| 内存泄漏 | 检查 closure_data 等包装结构是否正确释放 |

---

## 附录：关键源文件索引

| 文件 | 内容 |
|------|------|
| `system/stack/eatt/eatt_impl.h` | WeakPtrFactory + BindOnce + do_in_main_thread_delayed 的典型使用 |
| `system/stack/connection_manager/connection_manager.cc` | OnceClosure + alarm_set_closure + BindOnce 自由函数 |
| `system/stack/include/btm_ble_api.h` | RepeatingCallback 类型别名定义 |
| `system/stack/include/main_thread.h` | do_in_main_thread 接口声明 |
| `system/gd/os/handler.h` | Handler::Post / Call / CallOn + Unretained 使用 |
| `system/gd/common/bind.h` | common 命名空间的 Bind/BindOnce/Unretained 别名 |
| `system/gd/common/callback.h` | common 命名空间的 OnceClosure/OnceCallback 别名 |
| `system/gd/common/postable_context.h` | PostableContext 的 BindOnceOn/BindOn 封装 |
