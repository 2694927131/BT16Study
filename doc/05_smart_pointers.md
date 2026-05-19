# 智能指针与内存管理 —— 从裸指针到现代 C++ 的进化之路

> **基于 Android 蓝牙协议栈 (Fluoride) 真实代码的 C++ 教材**
>
> 目标读者：了解基本指针但不懂智能指针的 C++ 初学者

---

## 目录

1. [为什么需要智能指针](#1-为什么需要智能指针)
2. [std::unique_ptr（独占所有权）](#2-stdunique_ptr独占所有权)
3. [std::shared_ptr（共享所有权）](#3-stdshared_ptr共享所有权)
4. [std::enable_shared_from_this](#4-stdenable_shared_from_this)
5. [std::weak_ptr（弱引用）](#5-stdweak_ptr弱引用)
6. [Pimpl 惯用法详解](#6-pimpl-惯用法详解pointer-to-implementation)
7. [智能指针选择指南](#7-智能指针选择指南)
8. [常见陷阱与最佳实践](#8-常见陷阱与最佳实践)

---

> 📎 关联教材：02(类与对象), 08(移动语义), 14(Chromium基础库)

## 1. 为什么需要智能指针

### 1.1 裸指针的内存泄漏风险

在传统 C++ 中，我们用 `new` 分配内存，用 `delete` 释放内存。这看似简单，但在实际工程中极易出错：

```cpp
// 裸指针的典型问题
void process_device() {
    EattChannel* channel = new EattChannel(bda, cid, mtu, rx_mtu);
    // ... 使用 channel ...

    // 如果这里提前 return，channel 就泄漏了！
    if (some_error) {
        return;  // 忘记 delete channel → 内存泄漏！
    }

    // 如果这里抛出异常，channel 也泄漏了！
    do_something_risky();  // 可能抛异常 → 内存泄漏！

    delete channel;  // 只有正常流程才能走到这里
}
```

**内存泄漏**意味着这块内存永远无法被回收，程序运行越久，占用的内存越多，最终可能导致系统崩溃。

在蓝牙协议栈这种长时间运行的系统服务中，内存泄漏的危害尤其严重——蓝牙守护进程可能运行数天甚至数周不重启，即使每次只泄漏几个字节，累积起来也会耗尽内存。

### 1.2 异常安全问题

即使你很小心地在每个 `return` 前写了 `delete`，异常仍然会让你措手不及：

```cpp
void dangerous_function() {
    EattChannel* ch1 = new EattChannel(...);
    EattChannel* ch2 = new EattChannel(...);  // 如果这里抛出 bad_alloc？

    // ch2 分配失败抛异常 → ch1 永远不会被 delete！
    process(ch1, ch2);

    delete ch1;
    delete ch2;
}
```

在蓝牙协议栈中，L2CAP 连接回调、GATT 操作等都可能因为各种原因失败。如果用裸指针管理资源，每次都需要小心翼翼地处理所有错误路径。

### 1.3 蓝牙协议栈中大量使用智能指针的原因

浏览 Android 蓝牙协议栈代码，你会发现智能指针无处不在。核心原因有三个：

1. **生命周期复杂**：蓝牙连接涉及多个模块（L2CAP、GATT、EATT、HCI），一个通道对象可能被多处引用，手动管理极易出错。

2. **异步回调多**：蓝牙操作大量使用异步回调（连接完成回调、超时回调等），回调执行时原始对象可能已被销毁，智能指针 + 弱引用可以安全处理这种情况。

3. **编译隔离需求**：协议栈模块间需要减少编译依赖，Pimpl 惯用法（配合 `unique_ptr`）是标准解决方案。

```cpp
// 蓝牙协议栈中的真实场景：一个 EATT 通道可能被多方持有
// - eatt_device 的 eatt_channels map 持有它
// - 查找函数返回它的裸指针给调用者
// - 定时器回调可能引用它
// → 用 shared_ptr 管理，所有持有者共享所有权
std::map<uint16_t, std::shared_ptr<EattChannel>> eatt_channels;
```

### ☕ Java 类比

| 特性 | C++ 智能指针 | Java |
|------|-----------|------|
| 内存管理 | 手动 + 智能指针辅助 | **自动垃圾回收（GC）** |
| 内存泄漏风险 | ✅ 存在（循环引用、裸指针误用） | ⚠️ 较低（GC 处理大部分情况） |
| 析构函数确定性 | ✅ 确定的时间点调用 | ❌ GC 决定，不可预测 |
| 需要 `delete` | ✅ 手动或通过智能指针 | ❌ 不需要 |

**Java 为什么不需要智能指针？**

Java 有**垃圾回收器（Garbage Collector）**，自动追踪对象引用关系，当对象不再被任何引用指向时自动回收内存。C++ 智能指针本质上是在手动模拟 GC 的引用计数功能：

| C++ 概念 | Java 等价 |
|---------|----------|
| `new` + 手动 `delete` | ❌ 不存在（GC 自动回收） |
| `unique_ptr` | ❌ 不需要（GC 管理） |
| `shared_ptr`（引用计数） | GC 的可达性分析（更强大） |
| `weak_ptr`（弱引用） | `WeakReference<T>` |
| RAII | `try-with-resources` + `AutoCloseable` |

```cpp
// C++: 必须用智能指针避免内存泄漏
void process_device() {
    auto channel = std::make_unique<EattChannel>(bda, cid, mtu, rx_mtu);
    if (some_error) {
        return;  // unique_ptr 自动释放，不会泄漏
    }
    // channel 离开作用域自动释放
}
```

```java
// Java: GC 自动管理，不需要智能指针
void processDevice() {
    EattChannel channel = new EattChannel(bda, cid, mtu, rxMtu);
    if (someError) {
        return;  // GC 会在合适时机回收 channel，不会泄漏
    }
    // channel 不再被引用时，GC 自动回收
}
```

**关键差异**：
- Java 的 GC 比 C++ 的 `shared_ptr` 引用计数**更强大**：GC 可以处理循环引用（通过可达性分析），而 `shared_ptr` 的循环引用会导致内存泄漏
- C++ 的 RAII 提供了**确定性的资源释放**（析构函数在确定的时间点调用），Java 的 `finalize()` 不可预测，所以 Java 用 `try-with-resources` 替代
- C++ 的智能指针是**零开销抽象**（`unique_ptr` 无额外开销），Java 的 GC 有运行时开销（STW 停顿等）

### 📌 本节小结

- 裸指针 + 手动 `delete` 在异常和提前返回时极易导致内存泄漏
- 智能指针通过 RAII 自动管理生命周期，协议栈因生命周期复杂、异步回调多而大量使用
- Java 有 GC 自动管理，不需要智能指针；C++ 的 RAII 提供确定性资源释放

---

## 2. std::unique_ptr（独占所有权）

`std::unique_ptr` 是最常用的智能指针，它**独占**所指向对象的所有权——同一时刻只能有一个 `unique_ptr` 指向该对象。当 `unique_ptr` 被销毁时，它所指向的对象会被自动删除。

### 2.1 创建 unique_ptr

#### 方式一：std::make_unique（推荐，C++14 起）

```cpp
#include <memory>

// 推荐方式：使用 std::make_unique
auto channel = std::make_unique<EattChannel>(bda, cid, tx_mtu, rx_mtu);
```

`make_unique` 的优点：
- 更简洁，一行代码完成分配和构造
- 异常安全：不会出现 `new` 成功但构造 `unique_ptr` 前抛异常导致的泄漏
- 性能更好：单次分配（某些实现可将控制块和对象合并分配）

#### 方式二：直接从裸指针构造（不推荐）

```cpp
// 不推荐：裸指针和 unique_ptr 混用，容易出错
std::unique_ptr<EattChannel> channel(new EattChannel(bda, cid, tx_mtu, rx_mtu));
```

#### 蓝牙协议栈真实示例

在 `eatt.cc` 中，`EattExtension` 构造函数使用 `make_unique` 创建 Pimpl 对象：

```cpp
// eatt.cc:144
EattExtension::EattExtension() : pimpl_(std::make_unique<impl>()) {}
```

在 `eatt.cc` 的 `impl::Start()` 方法中，使用 `make_unique` 创建 `eatt_impl` 实例：

```cpp
// eatt.cc:61
eatt_impl_ = std::make_unique<eatt_impl>();
```

### 2.2 使用 -> 操作符访问成员

`unique_ptr` 重载了 `->` 操作符，你可以像使用裸指针一样访问成员：

```cpp
auto channel = std::make_unique<EattChannel>(bda, cid, tx_mtu, rx_mtu);

// 就像裸指针一样使用 ->
channel->EattChannelSetState(EattChannelState::EATT_CHANNEL_OPENED);
channel->EattChannelSetTxMTU(256);

// 也支持 * 解引用
EattChannel& ref = *channel;
```

#### 蓝牙协议栈真实示例

在 `eatt.cc` 中，通过 `pimpl_->` 访问 impl 的成员：

```cpp
// eatt.cc:150
void EattExtension::Connect(const RawAddress& bd_addr) {
    pimpl_->eatt_impl_->connect(bd_addr);
}

// eatt.cc:213
void EattExtension::Start() { pimpl_->Start(); }
```

### 2.3 .get() 获取裸指针

有时你需要将裸指针传递给旧接口（如 C 语言风格的蓝牙 API），这时可以使用 `.get()`：

```cpp
auto channel = std::make_unique<EattChannel>(bda, cid, tx_mtu, rx_mtu);

// .get() 返回裸指针，但不转移所有权
EattChannel* raw_ptr = channel.get();

// 可以传递给需要裸指针的旧接口
some_legacy_api(raw_ptr);

// 注意：get() 返回的指针不要 delete！
// delete raw_ptr;  // 错误！unique_ptr 会再次 delete，导致 double free
```

#### 蓝牙协议栈真实示例

在 `eatt_impl.h` 中，`find_channel_by_cid` 函数从 `shared_ptr` 中获取裸指针返回给调用者：

```cpp
// eatt_impl.h:93-101
EattChannel* find_channel_by_cid(uint16_t lcid) {
    eatt_device* eatt_dev = find_device_by_cid(lcid);
    if (!eatt_dev) {
        return nullptr;
    }

    auto it = eatt_dev->eatt_channels.find(lcid);
    // .get() 获取裸指针，不转移所有权
    return (it == eatt_dev->eatt_channels.end()) ? nullptr : it->second.get();
}
```

> **关键理解**：`.get()` 返回的裸指针**不拥有对象**。调用者不应该 `delete` 这个指针，也不应该持有它超过 `unique_ptr` 的生命周期。

### 2.4 .reset() 释放或替换对象

`reset()` 有两种用法：

```cpp
auto channel = std::make_unique<EattChannel>(bda, cid, tx_mtu, rx_mtu);

// 用法1：释放当前对象，置为 nullptr
channel.reset();       // 删除 EattChannel，channel 变为 nullptr
channel.reset(nullptr); // 等价写法

// 用法2：释放当前对象，接管新对象
channel.reset(new EattChannel(bda, cid2, tx_mtu2, rx_mtu2));
```

#### 蓝牙协议栈真实示例

在 `eatt.cc` 的 `impl::Stop()` 方法中，使用 `reset(nullptr)` 显式释放 `eatt_impl_`：

```cpp
// eatt.cc:65-72
void Stop() {
    if (!eatt_impl_) {
        log::error("Eatt not started");
        return;
    }
    eatt_impl_.reset(nullptr);  // 显式释放 eatt_impl_ 对象
    stack::l2cap::get_interface().L2CA_DeregisterLECoc(BT_PSM_EATT);
}
```

### 2.5 移动语义（unique_ptr 不能拷贝）

`unique_ptr` 是**不可拷贝**的，因为独占所有权意味着不能有两个 `unique_ptr` 指向同一个对象。但你可以**移动**它：

```cpp
auto ptr1 = std::make_unique<EattChannel>(bda, cid, tx_mtu, rx_mtu);

// auto ptr2 = ptr1;              // 编译错误！unique_ptr 不能拷贝
auto ptr2 = std::move(ptr1);      // 正确：移动所有权，ptr1 变为 nullptr

// 现在 ptr2 拥有对象，ptr1 == nullptr
```

**为什么不能拷贝？** 如果允许拷贝，两个 `unique_ptr` 都会在析构时 `delete` 同一个对象，导致 double free。

**移动的含义**：`std::move(ptr1)` 将所有权从 `ptr1` 转移给 `ptr2`，`ptr1` 变为 `nullptr`，对象不会被删除。

#### 函数返回 unique_ptr

```cpp
// 工厂函数返回 unique_ptr 是常见模式
std::unique_ptr<EattChannel> create_channel(RawAddress bda, uint16_t cid) {
    return std::make_unique<EattChannel>(bda, cid, 256, 64);
}

// 调用方
auto channel = create_channel(bda, cid);  // 所有权转移给调用方
```

### 2.6 核心真实示例：Pimpl 惯用法

Pimpl（Pointer to Implementation）是 `unique_ptr` 最经典的应用之一。蓝牙协议栈大量使用了这个模式：

```cpp
// eatt.h:283-286
class EattExtension {
private:
    struct impl;           // 前向声明，不定义 impl 的内容
    std::unique_ptr<impl> pimpl_;  // 通过 unique_ptr 持有实现
};
```

**为什么这样做？**

1. **减少编译依赖**：头文件不需要 `#include` impl 需要的所有头文件。只有 `.cc` 文件才需要知道 `impl` 的完整定义。
2. **稳定 ABI**：修改 `impl` 的内部结构不需要重新编译使用了 `EattExtension` 头文件的其他代码。
3. **隐藏实现细节**：用户只能看到公开接口，无法依赖内部实现。

我们会在[第5节](#5-pimpl-惯用法详解pointer-to-implementation)详细展开 Pimpl。

### 2.7 真实示例：自定义删除器的 unique_ptr

有时候，对象不是用 `delete` 释放的，而是需要调用特定的释放函数。`unique_ptr` 支持自定义删除器：

```cpp
// connection_manager.cc:75
using unique_alarm_ptr = std::unique_ptr<alarm_t, decltype(&alarm_free)>;
```

**逐行解析**：

```cpp
// 1. 定义类型别名
//    - 第一个模板参数 alarm_t：被管理的对象类型
//    - 第二个模板参数 decltype(&alarm_free)：删除器类型
//      decltype(&alarm_free) 会推导为 void(*)(alarm_t*)
using unique_alarm_ptr = std::unique_ptr<alarm_t, decltype(&alarm_free)>;

// 2. 创建带自定义删除器的 unique_ptr
//    - 第一个参数：alarm_new() 返回的裸指针
//    - 第二个参数：删除器函数指针 &alarm_free
alarm_t* timeout = alarm_new("wl_conn_params_30s");
unique_alarm_ptr alarm_ptr(timeout, &alarm_free);

// 3. 当 alarm_ptr 被销毁或 reset 时，会调用 alarm_free(timeout) 而不是 delete
```

#### 完整使用场景

在 `connection_manager.cc` 中，`unique_alarm_ptr` 被存储在 map 中，管理蓝牙直接连接的超时定时器：

```cpp
// connection_manager.cc:95-103
struct tAPPS_CONNECTING {
    std::set<tAPP_ID> doing_bg_conn;
    std::set<tAPP_ID> doing_targeted_announcements_conn;
    bool is_in_accept_list;

    // 每个直接连接的 app 都有一个超时定时器
    // 当 map 条目被删除时，unique_alarm_ptr 自动调用 alarm_free
    std::map<tAPP_ID, unique_alarm_ptr> doing_direct_conn;
};

// connection_manager.cc:590-594
// 创建定时器并用 unique_alarm_ptr 管理
alarm_t* timeout = alarm_new("wl_conn_params_30s");
alarm_set_closure(timeout, DIRECT_CONNECT_TIMEOUT,
                  base::BindOnce(&wl_direct_connect_timeout_cb, app_id, address));

bgconn_dev[address].doing_direct_conn.emplace(app_id, unique_alarm_ptr(timeout, &alarm_free));
```

**为什么需要自定义删除器？** 因为 `alarm_t` 是 C 风格的蓝牙定时器，必须用 `alarm_free()` 释放，而不是 `delete`。如果用默认删除器 `delete`，会调用 `alarm_t` 的析构函数，但 `alarm_t` 可能没有合适的析构函数，或者 `alarm_free` 需要执行额外的清理逻辑。

### 2.8 真实示例：Handler 中的 unique_ptr

在 GD（Graphite Daemon）模块的事件处理器中，`unique_ptr` 用于管理 Reactor 事件对象：

```cpp
// handler.h:123
class Handler : public common::PostableContext {
private:
    std::unique_ptr<Reactor::Event> event_;  // 独占拥有事件对象
    // ...
};
```

`Event` 对象的生命周期与 `Handler` 完全绑定——Handler 存在时 Event 存在，Handler 销毁时 Event 自动销毁。这正是 `unique_ptr` 独占所有权的典型场景。

### 2.9 真实示例：Queue 中的 TryDequeue 返回 unique_ptr

在 GD 模块的队列实现中，`TryDequeue` 返回 `unique_ptr`，明确表示出队操作**转移了数据的所有权**：

```cpp
// queue.h:52
template <typename T>
class IQueueDequeue {
public:
    // 返回 unique_ptr，表示所有权转移给调用者
    virtual std::unique_ptr<T> TryDequeue() = 0;
};

// queue.h:98
template <typename T>
class Queue : public IQueueEnqueue<T>, public IQueueDequeue<T> {
public:
    std::unique_ptr<T> TryDequeue() override;
};

// queue.h:259-274 — 实现细节
template <typename T>
std::unique_ptr<T> Queue<T>::TryDequeue() {
    std::lock_guard<std::mutex> lock(mutex_);

    if (queue_.empty()) {
        return nullptr;  // 队列为空，返回空 unique_ptr
    }

    dequeue_.reactive_semaphore_.Decrease();

    // 从队列中取出数据，转移所有权
    std::unique_ptr<T> data = std::move(queue_.front());
    queue_.pop();

    enqueue_.reactive_semaphore_.Increase();

    return data;  // 所有权转移给调用者
}
```

**为什么返回 `unique_ptr` 而不是裸指针？**

1. **语义清晰**：返回 `unique_ptr` 明确表示"调用者获得了数据的所有权"
2. **不会忘记释放**：调用者用完数据后，`unique_ptr` 自动释放
3. **不会悬空**：如果队列为空，返回 `nullptr`，调用者可以检查

队列内部也用 `std::queue<std::unique_ptr<T>>` 存储数据，确保数据在队列中时也有明确的所有权：

```cpp
// queue.h:103
std::queue<std::unique_ptr<T>> queue_;  // 队列拥有所有数据
```

### ☕ Java 类比

| 特性 | C++ `unique_ptr` | Java |
|------|-----------------|------|
| 独占所有权 | ✅ 不可拷贝，只能移动 | ❌ 不需要（GC 管理） |
| 所有权转移 | `std::move(ptr)` | 直接赋值引用（GC 不关心所有权） |
| 自动释放 | 离开作用域自动 `delete` | GC 自动回收 |
| 自定义删除器 | `unique_ptr<T, Deleter>` | `Cleaner`（Java 9+）/ `PhantomReference` |
| Pimpl 惯用法 | ✅ 核心用途 | ❌ 不需要（Java 天然隔离） |

**对比代码**：

```cpp
// C++: unique_ptr 独占所有权
auto channel = std::make_unique<EattChannel>(bda, cid, tx_mtu, rx_mtu);
channel->EattChannelSetTxMTU(256);  // 像裸指针一样使用
// auto ch2 = channel;              // 编译错误！不能拷贝
auto ch2 = std::move(channel);       // 所有权转移，channel 变 nullptr
```

```java
// Java: 不需要 unique_ptr，GC 自动管理
EattChannel channel = new EattChannel(bda, cid, txMtu, rxMtu);
channel.setTxMTU(256);  // 直接使用
EattChannel ch2 = channel;  // 只是复制引用，GC 管理生命周期
// 没有所有权概念，不需要 move
```

**对比代码——自定义删除器**：

```cpp
// C++: unique_ptr + 自定义删除器管理 C 风格资源
using unique_alarm_ptr = std::unique_ptr<alarm_t, decltype(&alarm_free)>;
alarm_t* timeout = alarm_new("name");
unique_alarm_ptr alarm(timeout, &alarm_free);
// alarm 离开作用域时自动调用 alarm_free(timeout)
```

```java
// Java: 用 Cleaner（Java 9+）管理本地资源
Cleaner cleaner = Cleaner.create();
AlarmT timeout = AlarmT.newAlarm("name");
cleaner.register(timeout, () -> AlarmT.alarmFree(timeout));  // 注册清理动作
// timeout 变为不可达时，cleaner 自动调用 alarmFree
```

**关键差异**：
- Java **不需要 `unique_ptr`**，因为 GC 自动管理所有对象的生命周期
- C++ 的 `unique_ptr` 明确表达"独占所有权"的设计意图，Java 中没有等价概念——所有引用都是共享的
- C++ 的自定义删除器模式（如 `unique_alarm_ptr`）在 Java 中用 `Cleaner` 或 `PhantomReference` 替代，但不如 C++ 优雅

### 📌 本节小结

- `unique_ptr` 独占所有权，不可拷贝，只能通过 `std::move()` 转移所有权
- `make_unique` 是推荐的创建方式，`.get()` 获取裸指针但不转移所有权
- 自定义删除器 `unique_ptr<T, Deleter>` 用于管理 C 风格资源（如 `alarm_free`）
- Pimpl 惯用法是 `unique_ptr` 最经典的应用

---

## 3. std::shared_ptr（共享所有权）

`std::shared_ptr` 允许多个 `shared_ptr` 共享同一个对象的所有权。内部通过**引用计数**跟踪有多少个 `shared_ptr` 指向该对象。当最后一个 `shared_ptr` 被销毁时，对象才会被删除。

### 3.1 创建 shared_ptr

#### 方式一：std::make_shared（推荐）

```cpp
#include <memory>

// 推荐方式：使用 std::make_shared
auto channel = std::make_shared<EattChannel>(bda, cid, tx_mtu, rx_mtu);
```

`make_shared` 的优点：
- **单次分配**：将控制块（引用计数等）和对象合并为一次内存分配，比 `new` + `shared_ptr` 构造更高效
- **异常安全**：不会出现分配成功但构造 `shared_ptr` 前抛异常的问题
- **缓存友好**：控制块和对象在连续内存中

#### 方式二：从裸指针构造

```cpp
// 不推荐：两次分配，且容易出错
std::shared_ptr<EattChannel> channel(new EattChannel(bda, cid, tx_mtu, rx_mtu));
```

### 3.2 引用计数原理

```
创建第一个 shared_ptr:
  对象: EattChannel  引用计数: 1

拷贝 shared_ptr:
  对象: EattChannel  引用计数: 2

再拷贝一份:
  对象: EattChannel  引用计数: 3

一个 shared_ptr 被销毁:
  对象: EattChannel  引用计数: 2

最后一个 shared_ptr 被销毁:
  引用计数: 0 → 自动 delete 对象
```

```cpp
auto ch1 = std::make_shared<EattChannel>(bda, cid, 256, 64);  // 引用计数 = 1
auto ch2 = ch1;   // 拷贝，引用计数 = 2
auto ch3 = ch1;   // 拷贝，引用计数 = 3

ch1.reset();      // ch1 不再指向对象，引用计数 = 2
ch2.reset();      // ch2 不再指向对象，引用计数 = 1
// ch3 离开作用域时，引用计数 = 0，EattChannel 被自动删除
```

### 3.3 多个 shared_ptr 共享同一对象

与 `unique_ptr` 不同，`shared_ptr` 可以自由拷贝：

```cpp
auto ch1 = std::make_shared<EattChannel>(bda, cid, 256, 64);
auto ch2 = ch1;  // 合法！两个 shared_ptr 共享同一个对象

// ch1 和 ch2 指向同一个 EattChannel
// 任何一个被销毁都不会影响另一个
// 只有两者都被销毁后，EattChannel 才会被删除
```

### 3.4 核心真实示例：EATT 通道管理

在 EATT（Enhanced ATTribute Protocol）实现中，`shared_ptr` 用于管理通道对象，因为通道可能被多处引用：

```cpp
// eatt_impl.h:49-63
class eatt_device {
public:
    RawAddress bda_;
    uint16_t rx_mtu_;
    uint16_t rx_mps_;
    tGATT_TCB* eatt_tcb_;

    // 核心数据结构：用 map 存储 shared_ptr<EattChannel>
    // key 是通道 ID (CID)，value 是通道对象的 shared_ptr
    std::map<uint16_t, std::shared_ptr<EattChannel>> eatt_channels;

    bool collision;
    eatt_device(const RawAddress& bd_addr, uint16_t mtu, uint16_t mps)
        : rx_mtu_(mtu), rx_mps_(mps), eatt_tcb_(nullptr), collision(false) {
        bda_ = bd_addr;
    }
};
```

**为什么用 `shared_ptr` 而不是 `unique_ptr`？**

1. **查找结果可能被多处持有**：`find_channel_by_cid()` 返回裸指针，但如果直接返回 `shared_ptr`，调用者可以安全地持有通道引用
2. **回调可能引用通道**：异步操作（如定时器回调）可能需要访问通道，`shared_ptr` 确保通道在回调执行时仍然有效
3. **map 的 erase 不会导致其他持有者悬空**：从 map 中移除通道时，如果其他地方还持有 `shared_ptr`，通道不会被删除

### 3.5 真实示例：创建 shared_ptr 并插入 map

在 `eatt_impl.h` 中，当 L2CAP 连接指示到来时，创建新的 EATT 通道并存入 map：

```cpp
// eatt_impl.h:183-191
for (uint16_t cid : lcids) {
    EattChannel* channel = find_eatt_channel_by_cid(bda, cid);
    log::assert_that(channel == nullptr, "assert failed: channel == nullptr");

    // 创建 shared_ptr 并插入 map
    auto chan = std::make_shared<EattChannel>(eatt_dev->bda_, cid, peer_mtu, eatt_dev->rx_mtu_);
    eatt_dev->eatt_channels.insert({cid, chan});

    chan->EattChannelSetState(EattChannelState::EATT_CHANNEL_OPENED);
    eatt_dev->eatt_tcb_->eatt++;

    log::info("Channel connected CID 0x{:x}", cid);
}
```

同样的模式在主动连接时也使用：

```cpp
// eatt_impl.h:575-579
for (uint16_t cid : connecting_cids) {
    log::info("\t cid: 0x{:x}", cid);

    auto chan = std::make_shared<EattChannel>(eatt_dev->bda_, cid, 0, eatt_dev->rx_mtu_);
    eatt_dev->eatt_channels.insert({cid, chan});
}
```

### 3.6 真实示例：从 shared_ptr 获取裸指针

当需要将通道指针传递给不需要所有权的旧接口时，使用 `.get()` 获取裸指针：

```cpp
// eatt_impl.h:592-604
EattChannel* find_eatt_channel_by_cid(const RawAddress& bd_addr, uint16_t cid) {
    eatt_device* eatt_dev = find_device_by_address(bd_addr);
    if (!eatt_dev) {
        return nullptr;
    }

    auto iter = find_if(eatt_dev->eatt_channels.begin(), eatt_dev->eatt_channels.end(),
                        [&cid](const std::pair<uint16_t, std::shared_ptr<EattChannel>>& el) {
                            return el.first == cid;
                        });

    // .get() 从 shared_ptr 获取裸指针
    // 调用者不获得所有权，不应 delete 返回的指针
    return iter == eatt_dev->eatt_channels.end() ? nullptr : iter->second.get();
}
```

### 3.7 真实示例：GATT 中的 shared_ptr

在 GATT 层中，`shared_ptr` 用于共享服务列表信息：

```cpp
// gatt_int.h:413
std::shared_ptr<std::list<tGATT_SRV_LIST_ELEM>> srv_list_info;

// gatt_int.h:691
Octet16 gatts_calculate_database_hash(
    std::shared_ptr<std::list<tGATT_SRV_LIST_ELEM>> lst_ptr);
```

这里 `shared_ptr` 包装了一个 `std::list`，因为服务列表可能被多个模块同时引用（如数据库哈希计算、服务发现等），用 `shared_ptr` 可以安全地共享列表所有权。

在 BTM（Baseband Manager）层中，`shared_ptr` 用于管理日志环形缓冲区：

```cpp
// btm_int_types.h:110
std::shared_ptr<TimestampedStringCircularBuffer> history_{nullptr};
```

### ☕ Java 类比

| 特性 | C++ `shared_ptr` | Java 引用 |
|------|-----------------|----------|
| 共享所有权 | ✅ 引用计数 | ✅ GC 可达性分析（更强大） |
| 引用计数 | 显式（`use_count()`） | 隐式（GC 内部追踪） |
| 循环引用问题 | ⚠️ 会导致内存泄漏 | ❌ GC 自动处理 |
| 所有权语义 | 明确（共享所有权） | 隐式（所有引用等价） |

**对比代码**：

```cpp
// C++: shared_ptr 管理共享对象
auto channel = std::make_shared<EattChannel>(bda, cid, 256, 64);
auto ch2 = channel;   // 引用计数 +1
auto ch3 = channel;   // 引用计数 +1
// 三者共享所有权，最后一个销毁时对象被删除
```

```java
// Java: 所有对象引用天然共享
EattChannel channel = new EattChannel(bda, cid, 256, 64);
EattChannel ch2 = channel;  // 复制引用
EattChannel ch3 = channel;  // 复制引用
// 三者指向同一对象，GC 在所有引用消失后回收
```

**关键差异**：
- Java 的引用**天然就是共享的**，不需要 `shared_ptr`。GC 通过可达性分析自动判断对象是否还在使用
- C++ 的 `shared_ptr` 有**循环引用问题**（两个对象互相持有 `shared_ptr` 导致内存泄漏），Java 的 GC 没有这个问题
- C++ 的 `shared_ptr` 有**引用计数开销**（原子操作），Java 的引用赋值无额外开销
- C++ 的 `shared_ptr` 提供了**明确的所有权语义**，Java 的引用不区分"拥有"和"借用"

### 📌 本节小结

- `shared_ptr` 通过引用计数共享所有权，可自由拷贝，最后一个持有者销毁时对象被删除
- `make_shared` 是推荐的创建方式（单次分配，更高效）
- `shared_ptr` 有循环引用问题，需配合 `weak_ptr` 打破循环

---

## 4. std::enable_shared_from_this

### 4.1 问题：在成员函数中返回自身的 shared_ptr

有时候，一个对象的成员函数需要返回指向自身的 `shared_ptr`。你可能会想直接用 `this` 构造：

```cpp
class Channel {
public:
    std::shared_ptr<Channel> GetSelf() {
        return std::shared_ptr<Channel>(this);  // ❌ 危险！
    }
};
```

**为什么危险？** 因为这会创建一个**全新的、独立的**引用计数，与原有的 `shared_ptr` 互不关联：

```cpp
auto sp1 = std::make_shared<Channel>();  // 引用计数 = 1
auto sp2 = sp1->GetSelf();               // 新的引用计数 = 1（不是 2！）
// sp1 和 sp2 各自引用计数为 1
// sp1 销毁 → Channel 被删除（引用计数 0）
// sp2 销毁 → 再次 delete 同一个对象 → double free！崩溃！
```

### 4.2 解决方案：std::enable_shared_from_this

`std::enable_shared_from_this` 是一个 CRTP 基类，让对象能够安全地获取指向自身的 `shared_ptr`：

```cpp
#include <memory>

class Channel : public std::enable_shared_from_this<Channel> {
public:
    std::shared_ptr<Channel> GetSelf() {
        return shared_from_this();  // ✅ 安全！返回与现有 shared_ptr 共享引用计数的 shared_ptr
    }
};
```

**原理**：`enable_shared_from_this` 内部持有一个 `weak_ptr`，当第一个 `shared_ptr` 管理该对象时，这个 `weak_ptr` 也被初始化。`shared_from_this()` 通过 `weak_ptr::lock()` 提升为 `shared_ptr`，因此与原有的 `shared_ptr` 共享同一个引用计数。

```cpp
auto sp1 = std::make_shared<Channel>();  // 引用计数 = 1
auto sp2 = sp1->GetSelf();               // 引用计数 = 2 ✅
// sp1 和 sp2 共享引用计数
// sp1 销毁 → 引用计数 = 1
// sp2 销毁 → 引用计数 = 0 → Channel 被正确删除
```

### 4.3 真实代码示例：Packet 类

```cpp
// 来源: system/packet/base/packet.h:30
class Packet : public std::enable_shared_from_this<Packet> {
  // 在成员函数中可以调用 shared_from_this() 返回自身的 shared_ptr
};
```

**解读**：
- `Packet` 是蓝牙协议栈中数据包的基类
- 继承 `std::enable_shared_from_this<Packet>` 后，`Packet` 的成员函数可以安全地调用 `shared_from_this()`
- 这在数据包需要将自身传递给异步回调时特别有用——回调需要持有 `shared_ptr<Packet>` 确保数据包在回调执行时仍然存活

### 4.4 使用注意事项

| 注意事项 | 说明 |
|---------|------|
| 必须通过 `shared_ptr` 管理对象 | 对象必须已经被 `shared_ptr` 持有，否则 `shared_from_this()` 会抛 `std::bad_weak_ptr` 异常 |
| 不能在构造函数中调用 | 构造函数执行时 `shared_ptr` 尚未创建，`shared_from_this()` 会失败 |
| 继承时模板参数是自身 | `class Foo : public std::enable_shared_from_this<Foo>`（CRTP 模式） |
| 线程安全 | `shared_from_this()` 是线程安全的（引用计数是原子操作） |

**错误示例——在构造函数中调用**：

```cpp
class Channel : public std::enable_shared_from_this<Channel> {
public:
    Channel() {
        auto self = shared_from_this();  // ❌ 异常！shared_ptr 还没创建
    }
};
```

**正确做法**：在构造完成、被 `shared_ptr` 管理后再调用：

```cpp
class Channel : public std::enable_shared_from_this<Channel> {
public:
    void Start() {
        auto self = shared_from_this();  // ✅ 此时已被 shared_ptr 管理
        register_callback([self]() { /* 安全使用 self */ });
    }
};

auto ch = std::make_shared<Channel>();  // shared_ptr 管理 Channel
ch->Start();                            // 此时可以安全调用 shared_from_this()
```

### ☕ Java 类比

| 特性 | C++ `enable_shared_from_this` | Java |
|------|------------------------------|------|
| 返回自身的智能引用 | `shared_from_this()` | ❌ **不需要** |
| 原因 | C++ 需要手动管理引用计数 | Java 引用天然安全，`this` 就是对象引用 |

Java **不需要** `enable_shared_from_this`，因为 Java 的 `this` 引用天然就是安全的——它直接指向堆上的对象，GC 自动管理生命周期。在 Java 中，如果需要将自身传给回调，直接用 `this` 即可：

```cpp
// C++: 需要 enable_shared_from_this 安全传递自身
class Channel : public std::enable_shared_from_this<Channel> {
    void Start() {
        auto self = shared_from_this();  // 获取 shared_ptr
        register_callback([self]() { self->Process(); });
    }
};
```

```java
// Java: 直接用 this，GC 保证安全
public class Channel {
    void start() {
        registerCallback(() -> this.process());  // 直接用 this
        // 或者
        registerCallback(this::process);         // 方法引用
    }
}
```

**关键差异**：
- C++ 中 `this` 是裸指针，不参与引用计数。如果对象被 `shared_ptr` 管理，直接用 `this` 构造新的 `shared_ptr` 会导致 double free
- Java 中 `this` 就是对象引用，GC 自动追踪所有引用，不存在"独立引用计数"的问题
- `enable_shared_from_this` 是 C++ 智能指针体系特有的需求，Java 完全不需要

### 📌 本节小结

- `enable_shared_from_this` 让对象的成员函数能安全返回指向自身的 `shared_ptr`
- 核心方法 `shared_from_this()` 返回与现有 `shared_ptr` 共享引用计数的 `shared_ptr`
- 不能在构造函数中调用，对象必须已被 `shared_ptr` 管理后才能使用
- Java 不需要此模式，因为 Java 的 `this` 引用天然安全

---

## 5. std::weak_ptr（弱引用）

`std::weak_ptr` 是一种"观察者"——它可以观察 `shared_ptr` 管理的对象，但**不增加引用计数**。它主要用于解决 `shared_ptr` 的循环引用问题，以及安全地观察可能已被销毁的对象。

### 5.1 解决循环引用问题

考虑以下场景：

```cpp
struct Device {
    std::shared_ptr<Channel> channel;
};

struct Channel {
    std::shared_ptr<Device> device;  // 循环引用！
};

auto dev = std::make_shared<Device>();
auto ch = std::make_shared<Channel>();

dev->channel = ch;  // Device 引用 Channel，引用计数 = 2
ch->device = dev;   // Channel 引用 Device，引用计数 = 2

// dev 和 ch 离开作用域时，引用计数各减 1，但都还剩 1
// → 两个对象永远不会被删除！内存泄漏！
```

用 `weak_ptr` 打破循环：

```cpp
struct Device {
    std::shared_ptr<Channel> channel;
};

struct Channel {
    std::weak_ptr<Device> device;  // 弱引用，不增加引用计数
};

auto dev = std::make_shared<Device>();
auto ch = std::make_shared<Channel>();

dev->channel = ch;  // Channel 引用计数 = 2
ch->device = dev;   // Device 引用计数仍然是 1（weak_ptr 不增加）

// dev 离开作用域 → Device 引用计数 = 0 → Device 被删除
// ch 离开作用域 → Channel 引用计数 = 1（dev 的析构释放了 dev->channel）
// → Channel 引用计数 = 0 → Channel 被删除
```

### 5.2 不增加引用计数

```cpp
auto shared = std::make_shared<EattChannel>(bda, cid, 256, 64);
// 引用计数 = 1

std::weak_ptr<EattChannel> weak = shared;
// 引用计数仍然是 1！weak_ptr 不增加引用计数

shared.reset();
// 引用计数 = 0 → EattChannel 被删除
// weak 现在是"过期"状态
```

### 5.3 lock() 获取 shared_ptr（可能为空）

`weak_ptr` 不能直接访问对象，必须通过 `lock()` 提升为 `shared_ptr`：

```cpp
auto shared = std::make_shared<EattChannel>(bda, cid, 256, 64);
std::weak_ptr<EattChannel> weak = shared;

// lock() 尝试获取 shared_ptr
if (auto locked = weak.lock()) {
    // 对象仍然存在，可以安全使用 locked
    locked->EattChannelSetState(EattChannelState::EATT_CHANNEL_OPENED);
} else {
    // 对象已被销毁，weak 已过期
    std::cout << "对象已不存在" << std::endl;
}
```

**为什么不能直接用 `weak_ptr` 访问对象？** 因为 `weak_ptr` 不拥有对象，对象可能在任何时候被其他 `shared_ptr` 销毁。`lock()` 会原子地检查对象是否存在，如果存在则返回一个新的 `shared_ptr`（引用计数 +1），确保在使用期间对象不会被删除。

### 5.4 base::WeakPtr（Chromium 版本）在协议栈中的使用

Android 蓝牙协议栈使用的是 Chromium 的 `base::WeakPtr` 而非标准库的 `std::weak_ptr`。两者理念相似但实现不同：

| 特性 | std::weak_ptr | base::WeakPtr |
|------|--------------|---------------|
| 配合使用 | std::shared_ptr | 不需要 shared_ptr |
| 引用计数 | 是 | 否 |
| 线程安全 | lock() 是原子操作 | 必须在同一线程使用 |
| 典型场景 | 打破循环引用 | 防止悬空回调 |

`base::WeakPtr` 的核心优势：**不需要 `shared_ptr` 的引用计数开销**，直接与对象的生命周期绑定。对象被销毁时，所有 `WeakPtr` 自动失效。

### 5.5 真实示例：WeakPtrFactory 防止悬空回调

这是蓝牙协议栈中 `WeakPtr` 最重要的应用场景——**防止异步回调访问已销毁的对象**：

```cpp
// eatt_impl.h:65-72
struct eatt_impl {
    std::vector<eatt_device> devices_;
    uint16_t psm_;
    uint16_t default_mtu_;
    uint16_t max_mps_;
    tL2CAP_APPL_INFO reg_info_;

    // WeakPtrFactory 必须是最后一个成员变量！
    base::WeakPtrFactory<eatt_impl> weak_factory_{this};
    // ...
};
```

**为什么必须是最后一个成员？** 因为 `WeakPtrFactory` 的析构会使所有 `WeakPtr` 失效。如果它不是最后一个析构的成员，其他成员的析构过程中可能还在使用 `WeakPtr`，导致访问已部分析构的对象。

#### 在异步回调中使用 WeakPtr

```cpp
// eatt_impl.h:947-949
// 读取 GATT 服务器支持特性，注册异步回调
if (gatt_cl_read_sr_supp_feat_req(
        bd_addr,
        base::BindOnce(&eatt_impl::supported_features_cb,
                       weak_factory_.GetWeakPtr(),  // 传入 WeakPtr
                       role)) == false) {
    log::info("Read server supported features failed for device {}", bd_addr);
}
```

**详细解释这段代码的执行流程**：

1. `gatt_cl_read_sr_supp_feat_req()` 发起一个异步 GATT 读取请求
2. `base::BindOnce(&eatt_impl::supported_features_cb, weak_factory_.GetWeakPtr(), role)` 创建一个回调：
   - 回调绑定了 `eatt_impl::supported_features_cb` 成员函数
   - 绑定了 `weak_factory_.GetWeakPtr()` 作为对象的弱引用
   - 绑定了 `role` 作为额外参数
3. 当 GATT 读取完成时，回调被触发：
   - **如果 `eatt_impl` 对象仍然存在**：`WeakPtr` 有效，回调正常执行 `supported_features_cb`
   - **如果 `eatt_impl` 对象已被销毁**：`WeakPtr` 失效，回调被忽略，不会访问已销毁的对象

#### 更多使用 WeakPtr 的回调示例

```cpp
// eatt_impl.h:252-254 — 延迟执行连接
bt_status_t status =
    do_in_main_thread_delayed(
        base::BindOnce(&eatt_impl::upper_tester_delay_connect_cb,
                       weak_factory_.GetWeakPtr(),  // 安全的弱引用
                       bda),
        std::chrono::milliseconds(timeout_ms));

// eatt_impl.h:443-445 — 延迟重新配置
do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::upper_tester_send_data_if_needed,
                   weak_factory_.GetWeakPtr(),  // 安全的弱引用
                   bda, lcid),
    std::chrono::seconds(1));

// eatt_impl.h:293-296 — 延迟重新配置所有通道
bt_status_t status = do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::reconfigure_all,
                   weak_factory_.GetWeakPtr(),  // 安全的弱引用
                   bda, 300),
    std::chrono::seconds(4));
```

**如果没有 WeakPtr 会怎样？**

```cpp
// 危险！如果 eatt_impl 在回调执行前被销毁，回调会访问已释放的内存
do_in_main_thread_delayed(
    base::BindOnce(&eatt_impl::upper_tester_delay_connect_cb,
                   base::Unretained(this),  // 不安全！裸指针
                   bda),
    std::chrono::milliseconds(timeout_ms));
// → 如果 this 被销毁，回调执行时访问悬空指针 → 崩溃！
```

### ☕ Java 类比

| 特性 | C++ `weak_ptr` | Java `WeakReference<T>` |
|------|---------------|------------------------|
| 不增加引用计数 | ✅ | ✅（不影响 GC 可达性） |
| 获取强引用 | `weak.lock()` 返回 `shared_ptr` | `weak.get()` 返回 `T`（可能为 null） |
| 检查是否过期 | `weak.expired()` | `weak.get() == null` |
| 典型用途 | 打破 `shared_ptr` 循环引用 | 缓存、防止内存泄漏 |
| 线程安全 | `lock()` 是原子操作 | `get()` 非原子 |

**对比代码**：

```cpp
// C++: weak_ptr 打破循环引用
struct Channel {
    std::weak_ptr<Device> device;  // 弱引用，不增加引用计数
};

auto locked = device_weak.lock();  // 尝试提升为 shared_ptr
if (locked) {
    locked->DoSomething();  // 对象仍存在
} else {
    // 对象已被销毁
}
```

```java
// Java: WeakReference 观察可能被 GC 的对象
import java.lang.ref.WeakReference;

WeakReference<Device> deviceRef = new WeakReference<>(device);

Device dev = deviceRef.get();  // 尝试获取强引用
if (dev != null) {
    dev.doSomething();  // 对象仍存在
} else {
    // 对象已被 GC 回收
}
```

**关键差异**：
- C++ 的 `weak_ptr` 必须配合 `shared_ptr` 使用，Java 的 `WeakReference` 可以配合任何对象引用使用
- C++ 的 `weak_ptr::lock()` 是**原子操作**（线程安全），Java 的 `WeakReference::get()` 不是原子的
- Java 还有 `SoftReference`（内存不足时才回收）和 `PhantomReference`（对象 finalize 后通知），C++ 没有这些区分
- 蓝牙协议栈中使用的 `base::WeakPtr`（Chromium 版本）更接近 Java 的 `WeakReference`——不需要 `shared_ptr`，直接与对象生命周期绑定

### 📌 本节小结

- `weak_ptr` 不增加引用计数，用于打破 `shared_ptr` 循环引用
- 必须通过 `lock()` 提升为 `shared_ptr` 才能访问对象，`lock()` 是原子操作
- 协议栈使用 `base::WeakPtrFactory` 防止异步回调访问已销毁对象

---

## 6. Pimpl 惯用法详解（Pointer to Implementation）

### 6.1 什么是 Pimpl

Pimpl（Pointer to Implementation，又称"编译防火墙"或"Cheshire Cat 技术"）是一种将类的实现细节从头文件中移到源文件的设计模式。核心思想是：

- **头文件**：只声明公开接口和一个指向实现结构的不透明指针
- **源文件**：定义实现结构的完整内容

### 6.2 为什么蓝牙协议栈大量使用 Pimpl

1. **减少编译时间**：修改实现不需要重新编译所有依赖该头文件的代码。在大型项目（如整个 Android 蓝牙协议栈）中，这可以节省大量编译时间。

2. **稳定 ABI**：添加、删除或修改私有成员不会改变类的二进制布局，不需要重新编译使用方。

3. **隐藏内部依赖**：实现可能依赖很多内部头文件，这些依赖不会"泄漏"到公共头文件中。

4. **线程安全考虑**：可以将互斥锁等同步原语放在 impl 中，避免在头文件中暴露。

### 6.3 实现步骤

#### 步骤 1：头文件中前向声明 `struct impl;`

```cpp
// eatt.h
#pragma once

#include <memory>  // 需要 #include <memory> 因为用了 unique_ptr

class EattExtension {
public:
    EattExtension();
    virtual ~EattExtension();

    // 公开接口...
    virtual void Connect(const RawAddress& bd_addr);
    virtual void Disconnect(const RawAddress& bd_addr, uint16_t cid);

private:
    struct impl;                    // 前向声明，不定义内容
    std::unique_ptr<impl> pimpl_;   // 用 unique_ptr 持有 impl
};
```

**注意**：
- 头文件只需要 `#include <memory>`，不需要 `#include` impl 需要的任何头文件
- `struct impl` 是前向声明，编译器知道 `impl` 是一个类型，但不知道它的大小和成员
- 因为 `unique_ptr` 只存储指针（固定大小），不需要知道 `impl` 的完整定义

#### 步骤 2：用 `std::unique_ptr<impl>` 作为成员

```cpp
// 在类定义中
std::unique_ptr<impl> pimpl_;
```

**为什么用 `unique_ptr` 而不是 `shared_ptr`？**

- `impl` 的所有权是独占的——只有 `EattExtension` 拥有它
- `unique_ptr` 零开销（没有引用计数的开销）
- 语义更清晰：独占所有权

#### 步骤 3：cc 文件中定义 impl 的完整结构

```cpp
// eatt.cc
#include "stack/eatt/eatt.h"
#include "stack/eatt/eatt_impl.h"  // impl 需要的头文件

namespace bluetooth {
namespace eatt {

// 定义 impl 的完整结构——只有 cc 文件能看到
struct EattExtension::impl {
    impl() = default;
    ~impl() = default;

    void Start() {
        if (eatt_impl_) {
            log::error("Eatt already started");
            return;
        }
        // ... 注册 L2CAP 回调 ...
        eatt_impl_ = std::make_unique<eatt_impl>();
    }

    void Stop() {
        if (!eatt_impl_) {
            log::error("Eatt not started");
            return;
        }
        eatt_impl_.reset(nullptr);
        stack::l2cap::get_interface().L2CA_DeregisterLECoc(BT_PSM_EATT);
    }

    bool IsRunning() { return eatt_impl_ ? true : false; }

    // impl 内部可以持有任意复杂的数据
    std::unique_ptr<eatt_impl> eatt_impl_;
    tL2CAP_APPL_INFO reg_info_;
};

// 构造函数：创建 impl
EattExtension::EattExtension() : pimpl_(std::make_unique<impl>()) {}

// 析构函数：需要定义在 cc 文件中（因为 impl 在这里才完整）
EattExtension::~EattExtension() = default;

// 公开接口通过 pimpl_ 委托给 impl
void EattExtension::Connect(const RawAddress& bd_addr) {
    pimpl_->eatt_impl_->connect(bd_addr);
}

void EattExtension::Start() { pimpl_->Start(); }
void EattExtension::Stop() { pimpl_->Stop(); }

}  // namespace eatt
}  // namespace bluetooth
```

**关键点**：
- 析构函数必须在 `.cc` 文件中定义（哪怕是 `= default`），因为头文件中 `impl` 是不完整类型
- 所有公开方法都通过 `pimpl_->` 委托给 `impl` 实现
- `impl` 内部可以自由使用任何头文件，不影响头文件的使用者

### 6.4 真实示例：EattExtension (eatt.h + eatt.cc)

完整的 Pimpl 使用流程：

**头文件** (`eatt.h:108-286`)：

```cpp
class EattExtension {
public:
    EattExtension();
    EattExtension(const EattExtension&) = delete;             // 禁止拷贝
    EattExtension& operator=(const EattExtension&) = delete;  // 禁止赋值
    virtual ~EattExtension();

    static EattExtension* GetInstance() {
        static EattExtension* instance = new EattExtension();
        return instance;
    }

    virtual void Connect(const RawAddress& bd_addr);
    virtual void Disconnect(const RawAddress& bd_addr, uint16_t cid = EATT_ALL_CIDS);
    virtual void Reconfigure(const RawAddress& bd_addr, uint16_t cid, uint16_t mtu);
    virtual void ReconfigureAll(const RawAddress& bd_addr, uint16_t mtu);
    // ... 更多公开方法 ...

    void Start();
    void Stop();

private:
    struct impl;                    // 前向声明
    std::unique_ptr<impl> pimpl_;   // Pimpl 指针
};
```

**源文件** (`eatt.cc:37-135`)：

```cpp
// impl 的完整定义——只有这个 cc 文件能看到
struct EattExtension::impl {
    impl() = default;
    ~impl() = default;

    void Start() { /* ... */ }
    void Stop() { /* ... */ }
    bool IsRunning() { /* ... */ }

    // 静态回调函数，作为 L2CAP 回调的桥接
    static eatt_impl* GetImplInstance(void) {
        auto* instance = EattExtension::GetInstance();
        return instance->pimpl_->eatt_impl_.get();
    }

    static void eatt_connect_ind(...) { /* ... */ }
    static void eatt_connect_cfm(...) { /* ... */ }
    // ... 更多回调 ...

    std::unique_ptr<eatt_impl> eatt_impl_;
    tL2CAP_APPL_INFO reg_info_;
};

// 构造函数
EattExtension::EattExtension() : pimpl_(std::make_unique<impl>()) {}

// 析构函数（必须在 cc 文件中定义）
EattExtension::~EattExtension() = default;

// 公开方法委托给 impl
void EattExtension::Connect(const RawAddress& bd_addr) {
    pimpl_->eatt_impl_->connect(bd_addr);
}
void EattExtension::Start() { pimpl_->Start(); }
void EattExtension::Stop() { pimpl_->Stop(); }
```

### 6.5 真实示例：IsoManager (btm_iso_api.h)

ISO（Isochronous）管理器也使用了 Pimpl 模式：

```cpp
// btm_iso_api.h:52-240
class IsoManager {
public:
    IsoManager();
    IsoManager(const IsoManager&) = delete;
    IsoManager& operator=(const IsoManager&) = delete;

    virtual ~IsoManager();

    static IsoManager* GetInstance();

    virtual void RegisterCigCallbacks(iso_manager::CigCallbacks* callbacks) const;
    virtual void RegisterBigCallbacks(iso_manager::BigCallbacks* callbacks) const;
    virtual void CreateCig(uint8_t cig_id, struct iso_manager::cig_create_params cig_params);
    virtual void ReconfigureCig(uint8_t cig_id, struct iso_manager::cig_create_params cig_params);
    virtual void RemoveCig(uint8_t cig_id, bool force = false);
    virtual void EstablishCis(struct iso_manager::cis_establish_params conn_params);
    virtual void DisconnectCis(uint16_t conn_handle, uint8_t reason);
    // ... 更多方法 ...

    void Start();
    void Stop();
    void Dump(int fd);

private:
    struct impl;                    // 前向声明
    std::unique_ptr<impl> pimpl_;   // Pimpl 指针
};
```

**与 EattExtension 的模式完全一致**：
1. 头文件前向声明 `struct impl`
2. 用 `std::unique_ptr<impl>` 持有
3. 禁止拷贝和赋值
4. 析构函数在 `.cc` 文件中定义
5. 公开方法委托给 `pimpl_`

### 6.6 Pimpl 的注意事项

1. **析构函数必须在 `.cc` 文件中定义**：因为头文件中 `impl` 是不完整类型，编译器不知道如何销毁它。如果析构函数在头文件中内联，编译器会报错。

2. **禁止拷贝和赋值**：`unique_ptr` 不可拷贝，包含 `unique_ptr` 的类默认也不可拷贝。应该显式 `= delete` 拷贝构造和赋值运算符。

3. **额外的指针间接访问**：每次访问 impl 成员都多了一次指针解引用，在极端性能敏感的场景中可能有影响。但在蓝牙协议栈中，这个开销可以忽略不计。

4. **调试稍困难**：impl 的内容在调试器中可能需要多一层间接才能查看。

### ☕ Java 类比

| 特性 | C++ Pimpl | Java |
|------|----------|------|
| 目的 | 隐藏实现细节、减少编译依赖 | ❌ **不需要** |
| 原因 | C++ 头文件暴露实现细节，修改会触发重编译 | Java 天然隔离接口和实现 |
| 替代方案 | — | `private` 成员 + 接口 |

**Java 为什么不需要 Pimpl？**

Pimpl 解决的是 C++ 独有的**头文件依赖问题**。在 C++ 中：
- 头文件（`.h`）包含类的完整定义，包括所有私有成员
- 修改私有成员（如添加一个变量）会导致所有 `#include` 该头文件的源文件重新编译
- Pimpl 通过将私有成员移到 `.cc` 文件来避免这个问题

Java **天然不存在这个问题**：
- Java 没有"头文件/源文件"的分离
- `.java` 编译为 `.class` 字节码，使用者只能看到 `public` 成员
- 修改 `private` 成员不需要重新编译使用方——只需替换 `.class` 文件
- Java 的 `private` 访问控制已经实现了 Pimpl 想要达到的隔离效果

```cpp
// C++: 需要 Pimpl 隐藏实现
// eatt.h（头文件）
class EattExtension {
public:
    void Connect(const RawAddress& bd_addr);
private:
    struct impl;                    // 前向声明，隐藏实现
    std::unique_ptr<impl> pimpl_;   // 不透明指针
};

// eatt.cc（源文件）
struct EattExtension::impl {
    std::unique_ptr<eatt_impl> eatt_impl_;  // 真正的实现
    tL2CAP_APPL_INFO reg_info_;
    // 修改这里不需要重新编译其他文件
};
```

```java
// Java: 不需要 Pimpl，private 天然隔离
public class EattExtension {
    public void connect(RawAddress bdAddr) {
        impl.connect(bdAddr);
    }

    // 直接持有实现类，不需要隐藏
    // 修改 Impl 的内部结构不影响使用方
    private Impl impl = new Impl();

    // Impl 可以是内部类，也可以是独立类
    private static class Impl {
        private EattImpl eattImpl;
        private RegInfo regInfo;
        // 修改这里不需要重新编译使用方
    }
}
```

**关键差异**：
- Java 的 `private` 访问控制 + 字节码编译模型**天然实现了 Pimpl 的目标**，不需要额外的设计模式
- C++ 的 Pimpl 是为了解决**编译模型**的问题（头文件暴露实现），不是面向对象设计的问题
- Java 程序员永远不需要考虑"修改私有成员会导致其他文件重新编译"的问题

### 📌 本节小结

- Pimpl 用 `struct impl;` 前置声明 + `unique_ptr<impl>` 隐藏实现细节
- 好处：减少编译依赖、稳定 ABI、隐藏内部依赖
- 析构函数必须在 `.cc` 文件中定义，禁止拷贝和赋值

---

## 7. 智能指针选择指南

### 7.1 决策表

| 场景 | 推荐指针 | 理由 |
|------|---------|------|
| 独占所有权，只有一个持有者 | `unique_ptr` | 零开销，语义最清晰 |
| 共享所有权，多个持有者 | `shared_ptr` | 引用计数自动管理生命周期 |
| 可能悬空的对象（观察者） | `weak_ptr` | 不增加引用计数，可安全检测对象是否存在 |
| 不拥有对象，只是借用 | 裸指针 `T*` 或引用 `T&` | 不参与生命周期管理，语义明确 |
| Pimpl 惯用法 | `unique_ptr` | 独占所有权，零开销 |
| C 风格资源（需要自定义释放） | `unique_ptr<T, Deleter>` | 自定义删除器确保正确释放 |
| 工厂函数返回值 | `unique_ptr`（优先）或 `shared_ptr` | 明确转移所有权给调用者 |

### 7.2 详细选择流程

```
开始
  │
  ├─ 是否需要拥有对象？
  │   │
  │   ├─ 否 → 使用裸指针 T* 或引用 T&
  │   │        （不参与生命周期管理，如函数参数、查找结果返回）
  │   │
  │   └─ 是 → 是否只有一个拥有者？
  │            │
  │            ├─ 是 → 使用 unique_ptr
  │            │        （独占所有权，零开销）
  │            │
  │            └─ 否 → 是否有多个拥有者？
  │                     │
  │                     ├─ 是 → 使用 shared_ptr
  │                     │        （共享所有权，引用计数）
  │                     │
  │                     └─ 是否需要观察可能被销毁的对象？
  │                              │
  │                              ├─ 是 → 使用 weak_ptr
  │                              │        （弱引用，不增加引用计数）
  │                              │
  │                              └─ 否 → 重新审视设计
```

### 7.3 蓝牙协议栈中的实际应用对照

| 代码位置 | 使用的指针类型 | 原因 |
|---------|-------------|------|
| `EattExtension::pimpl_` | `unique_ptr<impl>` | 独占所有权，Pimpl 惯用法 |
| `IsoManager::pimpl_` | `unique_ptr<impl>` | 独占所有权，Pimpl 惯用法 |
| `Handler::event_` | `unique_ptr<Reactor::Event>` | 独占所有权，生命周期与 Handler 绑定 |
| `impl::eatt_impl_` | `unique_ptr<eatt_impl>` | 独占所有权，Start/Stop 控制生命周期 |
| `eatt_device::eatt_channels` | `map<uint16_t, shared_ptr<EattChannel>>` | 共享所有权，多处可能持有通道引用 |
| `tAPPS_CONNECTING::doing_direct_conn` | `map<tAPP_ID, unique_alarm_ptr>` | 独占所有权 + 自定义删除器 |
| `Queue::queue_` | `queue<unique_ptr<T>>` | 独占所有权，出队转移所有权 |
| `eatt_impl::weak_factory_` | `WeakPtrFactory` | 弱引用，防止悬空回调 |

### 📌 本节小结

- 独占所有权用 `unique_ptr`，共享所有权用 `shared_ptr`，观察可能被销毁的对象用 `weak_ptr`
- 不拥有对象就用裸指针或引用，Pimpl 用 `unique_ptr`
- C 风格资源用 `unique_ptr<T, Deleter>` 自定义删除器

---

## 8. 常见陷阱与最佳实践

### 8.1 不要用裸指针 new/delete

```cpp
// ❌ 错误：手动管理内存
EattChannel* ch = new EattChannel(bda, cid, mtu, rx_mtu);
// ... 使用 ch ...
delete ch;  // 容易忘记，或者异常时跳过

// ✅ 正确：使用智能指针
auto ch = std::make_unique<EattChannel>(bda, cid, mtu, rx_mtu);
// 自动释放，异常安全
```

### 8.2 避免循环引用

```cpp
// ❌ 错误：循环引用导致内存泄漏
struct A {
    std::shared_ptr<B> b_ptr;
};
struct B {
    std::shared_ptr<A> a_ptr;  // 应该用 weak_ptr<A>
};

// ✅ 正确：用 weak_ptr 打破循环
struct A {
    std::shared_ptr<B> b_ptr;
};
struct B {
    std::weak_ptr<A> a_ptr;  // 弱引用，不增加引用计数
};
```

### 8.3 get() 返回的指针不要 delete

```cpp
auto ch = std::make_shared<EattChannel>(bda, cid, mtu, rx_mtu);
EattChannel* raw = ch.get();

// ❌ 错误：不要 delete get() 返回的指针
delete raw;  // double free！智能指针也会 delete

// ✅ 正确：让智能指针自己管理
ch.reset();  // 或者等 ch 离开作用域自动释放
```

### 8.4 工厂函数返回 smart pointer

```cpp
// ❌ 错误：返回裸指针，调用者容易忘记释放
EattChannel* create_channel() {
    return new EattChannel(...);
}

// ✅ 正确：返回 unique_ptr，所有权明确转移
std::unique_ptr<EattChannel> create_channel() {
    return std::make_unique<EattChannel>(...);
}
```

蓝牙协议栈中的 `TryDequeue` 就是这个模式的典型应用：

```cpp
// queue.h:98 — 返回 unique_ptr，明确表示所有权转移
std::unique_ptr<T> TryDequeue() override;
```

### 8.5 不要用同一个裸指针创建多个 shared_ptr

```cpp
// ❌ 错误：两个独立的 shared_ptr 管理同一个对象
EattChannel* raw = new EattChannel(...);
std::shared_ptr<EattChannel> sp1(raw);
std::shared_ptr<EattChannel> sp2(raw);  // 两个独立的引用计数！
// sp1 和 sp2 都会 delete raw → double free！

// ✅ 正确：通过拷贝 shared_ptr 共享所有权
auto sp1 = std::make_shared<EattChannel>(...);
auto sp2 = sp1;  // 引用计数正确递增
```

### 8.6 注意 unique_ptr 与不完整类型

```cpp
// 头文件中
class Foo {
    struct impl;  // 前向声明
    std::unique_ptr<impl> pimpl_;
public:
    Foo();
    ~Foo();  // 必须声明，不能 = default（在头文件中）
};

// 源文件中
Foo::~Foo() = default;  // 在这里 impl 是完整类型，可以正确析构
```

如果析构函数在头文件中内联（包括 `= default`），编译器会在头文件中生成析构代码，但此时 `impl` 是不完整类型，编译器不知道如何销毁它，会报错。

### 8.7 自定义删除器时注意函数签名匹配

```cpp
// alarm_free 的签名是 void alarm_free(alarm_t*)
using unique_alarm_ptr = std::unique_ptr<alarm_t, decltype(&alarm_free)>;

// 创建时必须传入删除器
alarm_t* timeout = alarm_new("name");
unique_alarm_ptr ptr(timeout, &alarm_free);  // 传入 &alarm_free

// 如果删除器签名不匹配，编译会报错
// 例如：alarm_free 的签名是 void alarm_free(alarm_t*)
// 但你传入了 void (*)(int*)，类型不匹配
```

### 8.8 weak_ptr 必须通过 lock() 使用

```cpp
auto shared = std::make_shared<EattChannel>(...);
std::weak_ptr<EattChannel> weak = shared;

// ❌ 错误：weak_ptr 不能直接访问成员
// weak->EattChannelSetState(...);  // 编译错误！

// ✅ 正确：先 lock() 获取 shared_ptr
if (auto locked = weak.lock()) {
    locked->EattChannelSetState(EattChannelState::EATT_CHANNEL_OPENED);
} else {
    // 对象已被销毁
}
```

### 8.9 优先使用 make_unique / make_shared

```cpp
// ❌ 不推荐：两次分配，且可能异常不安全
std::shared_ptr<EattChannel> sp(new EattChannel(...));

// ✅ 推荐：单次分配，异常安全
auto sp = std::make_shared<EattChannel>(...);
```

例外：当需要自定义删除器时，无法使用 `make_shared`，只能从裸指针构造。

### 8.10 总结：智能指针使用的"黄金法则"

1. **能用 `unique_ptr` 就不用 `shared_ptr`**：独占所有权更简单、更高效
2. **能用 `make_unique`/`make_shared` 就不用 `new`**：更安全、更高效
3. **不拥有对象就用裸指针或引用**：不要无谓地增加引用计数
4. **异步回调用弱引用**：防止对象在回调前被销毁
5. **永远不要 `delete` 智能指针 `.get()` 返回的裸指针**
6. **Pimpl 析构函数必须在 `.cc` 文件中定义**

### 📌 本节小结

- 永远不要 `delete` 智能指针 `.get()` 返回的裸指针
- `shared_ptr` 循环引用用 `weak_ptr` 打破
- 优先用 `make_unique`/`make_shared`，不用 `new`
- `weak_ptr` 必须通过 `lock()` 使用

---

## 常见错误

1. **`unique_ptr` 不能拷贝**：`auto ptr2 = ptr1;` 编译错误，必须用 `auto ptr2 = std::move(ptr1);` 转移所有权
2. **`shared_ptr` 循环引用**：两个对象互相持有 `shared_ptr` 导致内存泄漏，应将一方改为 `weak_ptr`
3. **`get()` 后 `delete`**：`delete ptr.get();` 导致 double free，智能指针自己会 `delete`
4. **忘记 `move` `unique_ptr`**：函数返回 `unique_ptr` 不需要 `move`（自动移动），但赋值给变量时需要

---

## 附录：关键源码文件索引

| 文件 | 路径 | 核心内容 |
|------|------|---------|
| eatt.h | `system/stack/eatt/eatt.h` | EattExtension 类定义，Pimpl 声明 |
| eatt.cc | `system/stack/eatt/eatt.cc` | EattExtension::impl 定义，make_unique 使用 |
| eatt_impl.h | `system/stack/eatt/eatt_impl.h` | eatt_device（shared_ptr）、WeakPtrFactory |
| handler.h | `system/gd/os/handler.h` | unique_ptr\<Reactor::Event\> |
| queue.h | `system/gd/os/queue.h` | TryDequeue 返回 unique_ptr |
| connection_manager.cc | `system/stack/connection_manager/connection_manager.cc` | 自定义删除器 unique_alarm_ptr |
| btm_iso_api.h | `system/stack/include/btm_iso_api.h` | IsoManager Pimpl |
| gatt_int.h | `system/stack/gatt/gatt_int.h` | shared_ptr 用于服务列表 |

---

## 速查卡

| 语法 | 用途 | 示例 | Java类比 |
|------|------|------|----------|
| `unique_ptr` | 独占所有权智能指针 | `auto p = std::make_unique<EattChannel>(...);` | ❌ GC 管理 |
| `shared_ptr` | 共享所有权智能指针 | `auto p = std::make_shared<EattChannel>(...);` | ❌ GC 管理 |
| `enable_shared_from_this` | 成员函数安全返回自身shared_ptr | `class Packet : public std::enable_shared_from_this<Packet>;` | ❌ 不需要 |
| `weak_ptr` | 弱引用，不增加引用计数 | `std::weak_ptr<EattChannel> w = shared;` | `WeakReference<T>` |
| `make_unique` / `make_shared` | 推荐的创建方式 | `std::make_unique<impl>()` | `new Impl()` |
| Pimpl | 隐藏实现细节 | `struct impl; unique_ptr<impl> pimpl_;` | ❌ 不需要 |
| 自定义删除器 | 管理 C 风格资源 | `unique_ptr<alarm_t, decltype(&alarm_free)>` | `Cleaner`（Java 9+） |
