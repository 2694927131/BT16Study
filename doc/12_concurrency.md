# 第12章：并发与线程安全 —— 蓝牙协议栈中的多线程编程

## 1. 为什么蓝牙协议栈需要并发

### 1.1 多线程架构

蓝牙协议栈是一个高度并发的系统。在 Android 蓝牙实现中，至少存在以下关键线程：

| 线程 | 职责 | 代码位置 |
|------|------|----------|
| **蓝牙主线程 (BT Main Thread)** | 处理蓝牙协议栈的核心逻辑，包括连接管理、状态机等 | `osi/include/thread.h` |
| **HCI 线程** | 与蓝牙控制器交互，发送/接收 HCI 命令和数据 | `gd/os/thread.h` |
| **Binder 线程** | 处理来自 Android Framework 层的 IPC 调用 | 系统提供 |
| **管理线程 (Management Thread)** | 协议栈的启动/停止管理 | `main/shim/stack.cc` |

在 GD (Generic Data) 架构中，线程基于 **Reactor 模式** 实现：

```cpp
// system/gd/os/thread.h:29-81
// Reactor-based looper thread implementation. The thread runs immediately after
// it is constructed, and stops after Stop() is invoked.
class Thread {
public:
  enum class Priority {
    REAL_TIME,  // 软实时调度保证（如 HCI 线程）
    NORMAL,     // 普通优先级（如管理线程）
  };

  Thread(const std::string& name, Priority priority);
  bool Stop();
  bool IsSameThread() const;
  std::string GetThreadName() const;
  Reactor* GetReactor() const;

private:
  void run(Priority priority);
  mutable std::mutex mutex_;
  const std::string name_;
  mutable Reactor reactor_;
  std::thread running_thread_;
};
```

协议栈启动时，会创建不同优先级的线程：

```cpp
// system/main/shim/stack.cc:178-180
stack_thread_ = new os::Thread("gd_stack_thread", os::Thread::Priority::REAL_TIME);
stack_handler_ = new os::Handler(stack_thread_);

management_thread_ = new Thread("management_thread", Thread::Priority::NORMAL);
management_handler_ = new Handler(management_thread_);
```

### 1.2 共享数据的竞争条件

当多个线程同时访问共享数据时，就会产生**竞争条件 (Race Condition)**。在蓝牙协议栈中，这种情况无处不在：

- **Binder 线程**可能随时调用 `connect()` 发起连接
- **HCI 线程**正在处理来自控制器的连接完成事件
- **主线程**正在遍历连接列表进行状态更新

如果不加保护，这些并发操作可能导致：
1. **数据结构损坏**：一个线程正在遍历 map，另一个线程同时删除元素
2. **状态不一致**：连接状态在读取后被另一个线程修改
3. **崩溃**：访问已被另一个线程释放的内存

```
线程A (Binder)                  线程B (HCI事件)
─────────────                   ─────────────
读取 bgconn_dev[addr]
  → doing_direct_conn 为空
                                删除 bgconn_dev[addr]
访问 it->second                 ← 悬空迭代器！崩溃！
```

这就是为什么蓝牙协议栈中大量使用了接下来要介绍的并发原语。

---

## 2. std::mutex 与 std::lock_guard

### 2.1 互斥锁的基本概念

`std::mutex`（互斥锁）是最基本的同步原语。它保证同一时刻只有一个线程可以访问被保护的共享数据：

- **加锁 (lock)**：如果锁空闲，当前线程获取锁；如果锁被占用，当前线程阻塞等待
- **解锁 (unlock)**：释放锁，允许其他等待的线程获取

```cpp
std::mutex m;
m.lock();      // 获取锁（可能阻塞）
// ... 访问共享数据 ...
m.unlock();    // 释放锁
```

> ⚠️ **危险**：手动调用 `lock()/unlock()` 容易出错。如果共享数据访问期间抛出异常，`unlock()` 将永远不会被调用，导致**死锁**。

### 2.2 RAII 锁管理

C++ 提供了 RAII 风格的锁管理器，自动在构造时加锁、析构时解锁：

| 类 | 特点 |
|----|------|
| `std::lock_guard` | 最简单，构造即加锁，析构即解锁，不可手动解锁 |
| `std::unique_lock` | 更灵活，可延迟加锁、手动解锁、条件变量配合使用 |

**推荐**：在绝大多数场景下使用 `std::lock_guard`，它简洁且不易出错。

### 2.3 真实示例：connection_manager 中的锁保护

蓝牙连接管理器是协议栈中并发访问最频繁的模块之一。多个线程可能同时请求连接、取消连接或查询连接状态：

```cpp
// system/stack/connection_manager/connection_manager.cc:104-108
namespace {
// Maps address to apps trying to connect to it
std::map<RawAddress, tAPPS_CONNECTING> bgconn_dev; // Guarded by bgconn_dev_mutex
std::recursive_mutex bgconn_dev_mutex;
```

每个操作共享数据 `bgconn_dev` 的函数都使用 `lock_guard` 保护：

```cpp
// system/stack/connection_manager/connection_manager.cc:111
int num_of_targeted_announcements_users(void) {
  std::lock_guard<std::recursive_mutex> lock(bgconn_dev_mutex);
  // ^^^ 构造时自动加锁
  return std::count_if(bgconn_dev.begin(), bgconn_dev.end(),
    [](const auto& pair) {
      return !pair.second.is_in_accept_list &&
             !pair.second.doing_targeted_announcements_conn.empty();
    });
} // ^^^ 析构时自动解锁，即使函数中途 return 或抛出异常
```

```cpp
// system/stack/connection_manager/connection_manager.cc:160-169
std::set<tAPP_ID> get_apps_connecting_to(const RawAddress& address) {
  std::lock_guard<std::recursive_mutex> lock(bgconn_dev_mutex);
  auto it = bgconn_dev.find(address);
  if (it == bgconn_dev.end()) {
    return std::set<tAPP_ID>();  // 即使提前返回，lock 析构也会解锁
  }
  // ... 构建结果集 ...
  return result;
}
```

### 2.4 真实示例：Handler 中的锁保护

GD 架构的 Handler 类使用 `std::mutex` 保护内部状态：

```cpp
// system/gd/os/handler.h:89-96
bool IsCleared() const LOCKS_EXCLUDED(mutex_) {
  std::lock_guard<std::mutex> lock(mutex_);
  return reactable_ == nullptr;
}
```

Handler 的 `Post()` 方法同样使用 `lock_guard` 保护任务队列：

```cpp
// system/gd/os/handler.cc:59-67
void Handler::Post(OnceClosure closure) {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (was_cleared()) {
      log::warn("Posting to a handler which has been cleared");
      return;
    }
    tasks_->emplace(std::move(closure));
  }  // 锁在此处释放，然后通知 Reactor
  event_->Notify();  // 在锁外执行，避免持锁调用外部函数
}
```

> 💡 **关键设计**：`event_->Notify()` 放在锁的外面！这是一个重要的最佳实践——**不要在持锁时调用外部函数**，因为外部函数可能会阻塞或尝试获取同一把锁。

### 2.5 真实示例：HCI HAL 层的锁保护

HCI HAL 层在接收数据时使用 `lock_guard` 保护回调：

```cpp
// system/gd/hal/hci_hal_impl_android.cc:97-106
void aclDataReceived(const std::vector<uint8_t>& packet) override {
  btsnoop_logger_->Capture(packet, SnoopLogger::Direction::INCOMING,
                           SnoopLogger::PacketType::ACL);
  {
    std::lock_guard<std::mutex> lock(mutex_);
    callback_->aclDataReceived(packet);
  }
}
```

---

## 3. std::recursive_mutex

### 3.1 与 std::mutex 的区别

`std::recursive_mutex` 允许**同一线程**对同一互斥锁多次加锁。每次加锁必须对应一次解锁，锁的持有计数归零时才真正释放。

| 特性 | `std::mutex` | `std::recursive_mutex` |
|------|-------------|----------------------|
| 同一线程重复加锁 | **死锁** | ✅ 允许（计数+1） |
| 解锁要求 | 1次 | 与加锁次数相同 |
| 性能 | 略快 | 略慢（需维护计数） |
| 使用场景 | 默认选择 | 需要可重入的函数调用链 |

**典型使用场景**：函数 A 获取锁后调用函数 B，函数 B 也需要获取同一把锁。使用 `std::mutex` 会导致死锁，使用 `std::recursive_mutex` 则可以正常工作。

### 3.2 真实示例：connection_manager 的可重入调用

在 `connection_manager` 中，`on_app_deregistered()` 获取锁后调用了 `direct_connect_remove()`，而后者也需要获取同一把锁：

```cpp
// system/stack/connection_manager/connection_manager.cc:108
std::recursive_mutex bgconn_dev_mutex;
```

```cpp
// system/stack/connection_manager/connection_manager.cc:449-473
void on_app_deregistered(uint8_t app_id) {
  std::lock_guard<std::recursive_mutex> lock(bgconn_dev_mutex);  // 第1次加锁
  auto it = bgconn_dev.begin();
  auto end = bgconn_dev.end();
  while (it != end) {
    it->second.doing_bg_conn.erase(app_id);
    it->second.doing_direct_conn.erase(app_id);
    if (is_anyone_connecting(it)) {
      it++;
      continue;
    }
    ACL_IgnoreLeConnectionFrom(BTM_Sec_GetAddressWithType(it->first));
    it = bgconn_dev.erase(it);
  }
}  // lock 析构，解锁

static void remove_all_clients_with_pending_connections(const RawAddress& address) {
  std::lock_guard<std::recursive_mutex> lock(bgconn_dev_mutex);  // 第1次加锁
  auto it = bgconn_dev.find(address);
  while (it != bgconn_dev.end() && !it->second.doing_direct_conn.empty()) {
    uint8_t app_id = it->second.doing_direct_conn.begin()->first;
    direct_connect_remove(app_id, address);  // 内部也会加锁 → 第2次加锁（同一线程）
    it = bgconn_dev.find(address);
  }
}
```

如果使用 `std::mutex`，`remove_all_clients_with_pending_connections` 在持有锁的情况下调用 `direct_connect_remove()`（也会尝试加锁），会导致**死锁**。使用 `recursive_mutex` 则允许同一线程重复加锁。

### 3.3 真实示例：全局互斥锁

协议栈还使用 `recursive_mutex` 作为全局锁：

```cpp
// system/osi/src/mutex.cc:24-29
static std::recursive_mutex global_mutex;

void mutex_global_lock(void) { global_mutex.lock(); }
void mutex_global_unlock(void) { global_mutex.unlock(); }
```

使用 `recursive_mutex` 是因为全局锁可能在嵌套调用中被多次获取。

### 3.4 真实示例：AVRCP 连接处理器

```cpp
// system/profile/avrcp/connection_handler.cc:52-53
// ConnectionHandler::CleanUp take the lock and calls
// ConnectionHandler::AcceptorControlCB with AVRC_CLOSE_IND_EVT
// which also takes the lock, so use a recursive_mutex.
static std::recursive_mutex device_map_lock;
```

注释清楚地说明了选择 `recursive_mutex` 的原因：`CleanUp` 持锁调用 `AcceptorControlCB`，而后者也需要加锁。

### 3.5 真实示例：btif_config 的配置锁

```cpp
// system/btif/src/btif_config.cc:136
static std::recursive_mutex config_lock;  // protects operations on |config|.
```

### 3.6 何时选择 recursive_mutex

```
是否需要 recursive_mutex 的判断流程：

函数A持锁 → 调用函数B → 函数B也需要同一把锁？
    │
    ├── 是 → 用 recursive_mutex
    │
    └── 否 → 用 mutex（默认选择）
```

> ⚠️ **注意**：`recursive_mutex` 虽然解决了重入问题，但也可能掩盖设计缺陷。如果可能，更好的做法是重构代码，将需要锁保护的操作提取为内部函数（不加锁），外部统一加锁调用。

---

## 4. 线程安全注解 (Thread Safety Annotations)

### 4.1 为什么需要注解

C++ 的 `std::mutex` 本身不会在编译时检查你是否正确地加锁。如果你忘记加锁就访问共享数据，编译器不会报错，但运行时可能出现难以调试的竞争条件。

**线程安全注解 (Thread Safety Annotations)** 是 Chromium/Clang 提供的编译时检查机制，能够在编译阶段发现锁的遗漏。

### 4.2 三大核心注解

| 注解 | 作用 | 标注位置 |
|------|------|----------|
| `GUARDED_BY(mutex)` | 该变量必须在持有 `mutex` 时才能访问 | 数据成员声明 |
| `EXCLUSIVE_LOCKS_REQUIRED(mutex)` | 调用此函数前必须持有 `mutex` | 函数声明 |
| `LOCKS_EXCLUDED(mutex)` | 调用此函数前不能持有 `mutex`（函数内部会自己加锁） | 函数声明 |

这些注解定义在 `<base/thread_annotations.h>` 中（Chromium base 库），在编译时由 Clang 的线程安全分析器检查。

### 4.3 GUARDED_BY：保护数据成员

`GUARDED_BY` 声明一个变量必须被指定的 mutex 保护。如果代码在未持有锁的情况下访问该变量，编译器会产生警告：

```cpp
// system/gd/os/handler.h:120-129
std::queue<common::OnceClosure>* tasks_ GUARDED_BY(mutex_);
Reactor::Reactable* reactable_ GUARDED_BY(mutex_);
DelayedTaskQueue* delayed_tasks_ GUARDED_BY(mutex_);
Alarm* alarm_ GUARDED_BY(mutex_);
```

这意味着所有对 `tasks_`、`reactable_`、`delayed_tasks_`、`alarm_` 的访问都必须在持有 `mutex_` 的情况下进行。

更复杂的示例来自 HCI 层的测试替身：

```cpp
// system/gd/hci/hci_layer_fake.h:106-127
std::list<common::ContextualOnceCallback<void(CommandCompleteView)>>
    command_complete_callbacks_ GUARDED_BY(mutex_);
std::list<common::ContextualOnceCallback<void(CommandStatusView)>>
    command_status_callbacks_ GUARDED_BY(mutex_);
std::map<EventCode, common::ContextualCallback<void(EventView)>>
    registered_events_ GUARDED_BY(mutex_);
std::map<SubeventCode, common::ContextualCallback<void(LeMetaEventView)>>
    registered_le_events_ GUARDED_BY(mutex_);
common::BidiQueue<AclView, AclBuilder> acl_queue_ GUARDED_BY(mutex_){3};
std::queue<std::unique_ptr<CommandBuilder>> command_queue_ GUARDED_BY(mutex_);
CommandView empty_command_view_ GUARDED_BY(mutex_) = CommandView::Create(
    PacketView<packet::kLittleEndian>(std::make_shared<std::vector<uint8_t>>()));
```

ACL 仲裁器也使用了 `GUARDED_BY`：

```cpp
// system/stack/arbiter/acl_arbiter.h:78-79
mutable std::mutex mutex_;
mutable ArbiterInterface* arbiter_ GUARDED_BY(mutex_) = nullptr;
```

### 4.4 EXCLUSIVE_LOCKS_REQUIRED：要求调用者持锁

`EXCLUSIVE_LOCKS_REQUIRED` 声明调用此函数时，调用者必须已经持有指定的锁。这通常用于**内部函数**——它们假设锁已被外部获取，自己不再加锁：

```cpp
// system/gd/os/handler.h:119-121
inline bool was_cleared() const EXCLUSIVE_LOCKS_REQUIRED(mutex_) {
  return tasks_ == nullptr || delayed_tasks_ == nullptr;
}
```

`was_cleared()` 是一个内部辅助函数，它直接访问 `GUARDED_BY(mutex_)` 的成员变量，但不自己加锁。注解告诉编译器：调用此函数前必须持有 `mutex_`。

如果有人在没有持锁的情况下调用 `was_cleared()`，编译器会产生警告。

### 4.5 LOCKS_EXCLUDED：函数内部自己加锁

`LOCKS_EXCLUDED` 声明调用此函数时，调用者**不能**持有指定的锁。这通常用于**公共接口函数**——它们自己负责加锁：

```cpp
// system/gd/os/handler.h:91-96
bool IsCleared() const LOCKS_EXCLUDED(mutex_) {
  std::lock_guard<std::mutex> lock(mutex_);  // 函数内部加锁
  return reactable_ == nullptr;
}
```

`IsCleared()` 是一个公共接口，它自己获取 `mutex_`。如果调用者已经持有 `mutex_` 再调用此函数，会导致**死锁**（`std::mutex` 不支持重入）。`LOCKS_EXCLUDED` 注解让编译器检查调用者是否已持有该锁。

### 4.6 注解之间的关系

```
┌──────────────────────────────────────────────────────────────┐
│                    线程安全注解关系图                          │
│                                                              │
│  GUARDED_BY(mutex_)          EXCLUSIVE_LOCKS_REQUIRED(mutex_)│
│  ┌──────────────┐            ┌──────────────────────┐        │
│  │ int data_    │◄───────────│ was_cleared()        │        │
│  │ 必须持锁访问  │            │ 调用者必须持锁        │        │
│  └──────────────┘            └──────────────────────┘        │
│         ▲                              ▲                     │
│         │ 访问                          │ 调用                 │
│         │                              │                     │
│  ┌──────┴───────────┐          ┌───────┴──────────────┐      │
│  │ lock_guard<mutex>│          │ lock_guard<mutex>    │      │
│  │ Post()           │          │ IsCleared()          │      │
│  │ LOCKS_EXCLUDED   │          │ LOCKS_EXCLUDED       │      │
│  └──────────────────┘          └──────────────────────┘      │
│                                                              │
│  LOCKS_EXCLUDED(mutex_) = 函数内部会加锁，调用者不能已持有锁    │
└──────────────────────────────────────────────────────────────┘
```

### 4.7 编译时检查示例

```cpp
class Handler {
  mutable std::mutex mutex_;
  std::queue<Closure>* tasks_ GUARDED_BY(mutex_);

  bool was_cleared() const EXCLUSIVE_LOCKS_REQUIRED(mutex_) {
    return tasks_ == nullptr;  // ✅ 注解保证调用时已持锁
  }

  bool IsCleared() const LOCKS_EXCLUDED(mutex_) {
    std::lock_guard<std::mutex> lock(mutex_);
    return tasks_ == nullptr;  // ✅ 已加锁，可以访问
  }

  void BadAccess() const {
    return tasks_ == nullptr;  // ❌ 编译警告：访问 GUARDED_BY 变量但未持锁
  }

  void BadCall() const {
    std::lock_guard<std::mutex> lock(mutex_);
    IsCleared();  // ❌ 编译警告：已持有 mutex_ 但调用了 LOCKS_EXCLUDED(mutex_)
  }
};
```

---

## 5. std::atomic

### 5.1 原子操作

`std::atomic` 提供了**原子性**保证——对原子变量的操作是不可分割的，不会被其他线程观察到中间状态。

与 `std::mutex` 的对比：

| 特性 | `std::mutex` | `std::atomic` |
|------|-------------|---------------|
| 保护粒度 | 代码块（临界区） | 单个变量 |
| 开销 | 较重（系统调用） | 较轻（CPU 原子指令） |
| 阻塞 | 是（锁竞争时阻塞） | 否（无锁） |
| 适用场景 | 复杂的共享数据结构 | 简单的状态标志、计数器 |

### 5.2 内存序

原子操作支持不同的**内存序 (Memory Order)**，控制操作之间的可见性顺序：

| 内存序 | 含义 | 开销 |
|--------|------|------|
| `memory_order_seq_cst`（默认） | 顺序一致性，所有线程看到相同顺序 | 最高 |
| `memory_order_acquire` | 获取语义，后续读写不能重排到此操作之前 | 中等 |
| `memory_order_release` | 释放语义，之前的读写不能重排到此操作之后 | 中等 |
| `memory_order_relaxed` | 只保证原子性，不保证顺序 | 最低 |
| `memory_order_acq_rel` | 同时具有获取和释放语义 | 中等 |

> 💡 **实践建议**：除非有明确的性能需求，否则使用默认的 `memory_order_seq_cst`。错误的内存序选择可能导致极难调试的问题。

### 5.3 真实示例：Reactor 的运行状态

Reactor 使用 `std::atomic<bool>` 标记自身是否正在运行：

```cpp
// system/gd/os/reactor.h:107
std::atomic<bool> is_running_;
```

这个标志被多个线程读取（查询 Reactor 状态），但只由 Reactor 所在线程修改。使用原子变量避免了加锁的开销，同时保证了可见性。

### 5.4 真实示例：队列的注册状态

`EnqueueBuffer` 使用 `std::atomic_bool` 跟踪是否已注册入队回调：

```cpp
// system/gd/os/queue.h:163
std::atomic_bool enqueue_registered_ = false;
```

在 `Enqueue()` 方法中，使用 `exchange()` 原子操作来确保只注册一次：

```cpp
// system/gd/os/queue.h:127-137
void Enqueue(std::unique_ptr<T> t, os::Handler* handler) {
  std::lock_guard<std::mutex> lock(mutex_);
  buffer_.push(std::move(t));
  if (!enqueue_registered_.exchange(true)) {
    // exchange(true) 原子地：读取旧值 → 设置新值为 true → 返回旧值
    // 如果旧值为 false，说明之前未注册，现在注册
    // 如果旧值为 true，说明之前已注册，跳过
    queue_->RegisterEnqueue(
        handler, common::Bind(&EnqueueBuffer<T>::enqueue_callback,
                              common::Unretained(this)));
  }
}
```

在析构函数中也使用了 `exchange()`：

```cpp
// system/gd/os/queue.h:121-125
~EnqueueBuffer() {
  if (enqueue_registered_.exchange(false)) {
    // 如果之前已注册，则取消注册
    queue_->UnregisterEnqueue();
  }
}
```

### 5.5 真实示例：ISO 连接的状态标志

ISO（Isochronous）连接使用 `std::atomic_uint8_t` 作为位标志，表示连接的多种状态：

```cpp
// system/stack/btm/btm_iso_impl.h:87
struct iso_base {
  union {
    uint8_t cig_id;
    uint8_t big_handle;
  };

  struct iso_sync_info sync_info;
  std::atomic_uint8_t state_flags;       // ← 原子状态标志
  uint32_t sdu_itv;
  std::atomic_uint16_t used_credits;     // ← 原子信用计数
  // ...
};
```

状态标志的定义：

```cpp
// system/stack/btm/btm_iso_impl.h:37-43
static constexpr uint8_t kStateFlagsNone = 0x00;
static constexpr uint8_t kStateFlagIsConnecting = 0x01;
static constexpr uint8_t kStateFlagIsConnected = 0x02;
static constexpr uint8_t kStateFlagHasDataPathSet = 0x04;
static constexpr uint8_t kStateFlagIsBroadcast = 0x10;
static constexpr uint8_t kStateFlagIsCancelled = 0x20;
static constexpr uint8_t kStateFlagSettingDataPath = 0x40;
```

使用位操作修改状态：

```cpp
// system/stack/btm/btm_iso_impl.h:288-289
cis->state_flags |= kStateFlagIsConnecting;     // 设置"正在连接"标志

// system/stack/btm/btm_iso_impl.h:319-320
cis->state_flags &= ~kStateFlagIsConnecting;    // 清除"正在连接"标志
cis->state_flags |= kStateFlagIsCancelled;      // 设置"已取消"标志
```

ISO 信用计数也使用原子变量：

```cpp
// system/stack/btm/btm_iso_impl.h:960
std::atomic_uint16_t iso_credits_;
```

### 5.6 真实示例：旧式线程的 join 标志

在旧式 OSI 线程实现中，使用 `std::atomic_bool` 标记线程是否已 join：

```cpp
// system/osi/src/thread.cc:43-50
struct thread_t {
  std::atomic_bool is_joined{false};
  pthread_t pthread;
  pid_t tid;
  char name[THREAD_NAME_MAX + 1];
  reactor_t* reactor;
  fixed_queue_t* work_queue;
};
```

### 5.7 atomic vs mutex 的选择

```
选择决策树：

需要保护的是什么？
│
├── 单个简单变量（标志、计数器）
│   └── 使用 std::atomic
│
├── 复杂数据结构（map、queue、自定义结构体）
│   └── 使用 std::mutex
│
└── 需要多个变量的操作是原子的
    └── 使用 std::mutex（atomic 无法保护多个变量的一致性）
```

---

## 6. std::promise 和 std::future

### 6.1 一次性线程间通信

`std::promise` 和 `std::future` 是 C++ 提供的**一次性**线程间通信机制：

- **`std::promise<T>`**：值的**提供者**，可以设置一个值（或异常）
- **`std::future<T>`**：值的**获取者**，可以等待值被设置

工作流程：

```
线程A                           线程B
──────                          ──────
promise<T> p;
future<T> f = p.get_future();
将 p 传递给线程B ──────────────→
                                ... 执行工作 ...
f.wait_for(timeout)             p.set_value(result);
← ─────────────────────────────
获取结果: f.get()
```

### 6.2 真实示例：Handler::Synchronize()

`Handler::Synchronize()` 是一个精妙的设计——它将一个空任务投递到 Handler 所在线程，然后等待该任务被执行。这确保了调用 `Synchronize()` 时，Handler 之前投递的所有任务都已完成：

```cpp
// system/gd/os/handler.h:98-103
bool Synchronize(std::chrono::milliseconds timeout) {
  std::promise<void> promise;
  auto future = promise.get_future();
  // 将 promise.set_value 投递到 Handler 线程执行
  // 当这个任务被执行时，说明之前的任务都已处理完
  Post(common::BindOnce(&std::promise<void>::set_value,
                        common::Unretained(&promise)));
  return future.wait_for(timeout) == std::future_status::ready;
}
```

**执行时序**：

```
调用线程                        Handler线程
────────                       ──────────
创建 promise
获取 future
Post(set_value) ───────────→ 任务队列: [...旧任务..., set_value]
wait_for(timeout)             处理旧任务...
  (阻塞等待)                   处理旧任务...
                               处理 set_value → promise.set_value()
← ─────────────────────────
future 就绪，返回 true
```

### 6.3 真实示例：协议栈启动的同步

协议栈启动时，使用 `promise/future` 确保启动完成后再继续：

```cpp
// system/main/shim/stack.cc:183-210
std::promise<void> promise;
auto future = promise.get_future();
management_handler_->Post(
    common::BindOnce(&Stack::handle_start_up, common::Unretained(this),
                     std::move(promise)));
auto init_status = future.wait_for(
    std::chrono::milliseconds(get_gd_stack_timeout_ms(/* is_start = */ true)));

log::info("init_status == {}", int(init_status));

if (init_status != std::future_status::ready) {
  /* Crash stuck thread and print it's stack trace */
  management_thread_->Abort();
  std::this_thread::sleep_for(std::chrono::milliseconds(2000));
  log::assert_that(init_status == std::future_status::ready,
                   "Can't start stack");
}
```

启动处理函数在完成后设置 promise：

```cpp
// system/main/shim/stack.cc:396-404
void Stack::handle_start_up(std::promise<void> promise) {
  if (!com_android_bluetooth_flags_same_handler_for_all_modules()) {
    pimpl_ = std::make_unique<Stack::impl>(stack_thread_);
  } else {
    pimpl_ = std::make_unique<Stack::impl>(stack_handler_);
  }
  promise.set_value();  // 通知启动完成
}
```

### 6.4 真实示例：Dump 的同步

`Stack::Dump()` 使用 `promise` 确保在 Handler 线程上完成 dump 操作后再返回：

```cpp
// system/main/shim/stack.cc:369-383
void Stack::Dump(int fd, std::promise<void> promise) const {
  std::lock_guard<std::recursive_mutex> lock(mutex_);
  if (is_running_ && fd >= 0) {
    stack_handler_->Call(
        [](int fd, std::promise<void> promise) {
          bluetooth::shim::GetController()->Dump(fd);
          bluetooth::shim::GetAclManagerLe()->Dump(fd);
          bluetooth::shim::GetAdvertising()->Dump(fd);
          bluetooth::os::WakelockManager::Get().Dump(fd);
          bluetooth::shim::GetSnoopLogger()->DumpSnoozLogToFile();
          promise.set_value();  // dump 完成后通知
        },
        fd, std::move(promise));
  } else {
    promise.set_value();  // 未运行，直接通知
  }
}
```

### 6.5 真实示例：ACL 地址查询的同步

ACL 模块使用 `promise/future` 实现跨线程的地址查询：

```cpp
// system/main/shim/acl.cc:1301-1305
void shim::Acl::GetConnectionLocalAddress(
    uint16_t handle, bool ota_address,
    std::promise<bluetooth::hci::AddressWithType> promise) {
  handler_->CallOn(pimpl_.get(), &Acl::impl::get_connection_local_address,
                   handle, ota_address, std::move(promise));
}

void shim::Acl::GetConnectionPeerAddress(
    uint16_t handle, bool ota_address,
    std::promise<bluetooth::hci::AddressWithType> promise) {
  handler_->CallOn(pimpl_.get(), &Acl::impl::get_connection_peer_address,
                   handle, ota_address, std::move(promise));
}
```

### 6.6 future 的等待方式

```cpp
// 阻塞等待，直到值可用
T value = future.get();

// 等待指定时间，返回状态
auto status = future.wait_for(std::chrono::milliseconds(2000));
if (status == std::future_status::ready) {
  // 值已就绪
} else if (status == std::future_status::timeout) {
  // 超时
} else if (status == std::future_status::deferred) {
  // 延迟执行（使用 std::async 时可能出现）
}

// 等待直到指定时间点
auto status = future.wait_until(std::chrono::system_clock::now() + 2s);
```

---

## 7. std::chrono (时间库)

### 7.1 时长 (Duration)

`std::chrono::duration` 表示一段时间间隔。蓝牙协议栈中常用以下时长类型：

```cpp
std::chrono::milliseconds  // 毫秒
std::chrono::seconds       // 秒
std::chrono::microseconds  // 微秒
```

时长支持算术运算和隐式转换（从小单位到大单位）：

```cpp
auto ms = std::chrono::milliseconds(2000);
auto sec = std::chrono::duration_cast<std::chrono::seconds>(ms);  // 2s
```

### 7.2 时间点 (Time Point)

`std::chrono::time_point` 表示某个时钟上的一个时间点，由**时钟**和**时长**组合而成：

```cpp
std::chrono::time_point<std::chrono::system_clock>  // 系统时钟时间点
std::chrono::time_point<std::chrono::steady_clock>  // 单调时钟时间点
```

### 7.3 真实示例：Handler 停止超时

```cpp
// system/gd/os/handler.h:35
constexpr std::chrono::milliseconds kHandlerStopTimeout =
    std::chrono::milliseconds(2000);
```

这个常量定义了 Handler 停止时的最大等待时间。使用 `constexpr` 确保编译期求值。

### 7.4 真实示例：ACL 连接的创建时间

ACL 模块使用 `time_point` 记录连接的创建和拆除时间：

```cpp
// system/main/shim/acl.cc:177-178
using CreationTime = std::chrono::time_point<std::chrono::system_clock>;
using TeardownTime = std::chrono::time_point<std::chrono::system_clock>;
```

这些时间点用于构建连接描述符，记录连接的生命周期：

```cpp
// system/main/shim/acl.cc:203-230
struct ConnectionDescriptor {
  CreationTime creation_time_;
  TeardownTime teardown_time_;
  uint16_t handle_;
  bool is_locally_initiated_;
  hci::ErrorCode disconnect_reason_;

  ConnectionDescriptor(CreationTime creation_time, TeardownTime teardown_time,
                       uint16_t handle, bool is_locally_initiated,
                       hci::ErrorCode disconnect_reason)
      : creation_time_(creation_time),
        teardown_time_(teardown_time),
        handle_(handle),
        is_locally_initiated_(is_locally_initiated),
        disconnect_reason_(disconnect_reason) {}

  std::string ToString() const {
    return std::format(
        "peer:{} handle:0x{:04x} is_locally_initiated:{} "
        "creation_time:{} teardown_time:{} disconnect_reason:{}",
        GetPrivateRemoteAddress(), handle_, is_locally_initiated_,
        common::StringFormatTimeWithMilliseconds(
            kConnectionDescriptorTimeFormat, creation_time_),
        common::StringFormatTimeWithMilliseconds(
            kConnectionDescriptorTimeFormat, teardown_time_),
        hci::ErrorCodeText(disconnect_reason_));
  }
};
```

在连接创建和断开时获取当前时间：

```cpp
// system/main/shim/acl.cc:1367
std::chrono::system_clock::now()  // 创建时间

// system/main/shim/acl.cc:1293
TeardownTime teardown_time = std::chrono::system_clock::now();  // 拆除时间
```

### 7.5 真实示例：协议栈启动超时

协议栈启动/停止使用可配置的超时时间：

```cpp
// system/main/shim/stack.cc:406-413
std::chrono::milliseconds Stack::get_gd_stack_timeout_ms(bool is_start) {
  auto gd_timeout = os::GetSystemPropertyUint32(
      is_start ? "bluetooth.gd.start_timeout" : "bluetooth.gd.stop_timeout",
      /* default_value = */ is_start ? 3000 : 5000);
  return std::chrono::milliseconds(gd_timeout *
      os::GetSystemPropertyUint32("ro.hw_timeout_multiplier",
                                  /* default_value = */ 1));
}
```

### 7.6 真实示例：Reactor 注销超时

```cpp
// system/gd/os/reactor.h:50-51
constexpr std::chrono::milliseconds kReactableUnregistrationTimeout =
    std::chrono::milliseconds(1000);
```

### 7.7 chrono 在协议栈中的典型用法

```cpp
// 1. 定义超时常量
constexpr std::chrono::milliseconds kTimeout = std::chrono::milliseconds(2000);

// 2. 计算未来时间点（用于延迟任务）
auto time_to_run = boottime_clock::now() + delay;

// 3. 等待 future
future.wait_for(std::chrono::milliseconds(3000));

// 4. 休眠当前线程
std::this_thread::sleep_for(std::chrono::milliseconds(2000));

// 5. 记录时间戳
auto creation_time = std::chrono::system_clock::now();
```

---

## 8. Handler 线程模型

### 8.1 Reactor 模式

蓝牙 GD 架构的线程模型基于 **Reactor 模式**（也称为事件循环模式）：

```
┌────────────────────────────────────────────────────────────┐
│                      Reactor 模式                          │
│                                                            │
│   ┌──────────┐    Register     ┌──────────────────────┐    │
│   │ Handler A │───────────────→│                      │    │
│   └──────────┘                 │     Reactor          │    │
│   ┌──────────┐    Register     │                      │    │
│   │ Handler B │───────────────→│  epoll_wait() 阻塞    │    │
│   └──────────┘                 │  → 事件就绪时回调      │    │
│   ┌──────────┐    Register     │                      │    │
│   │  Alarm    │───────────────→│                      │    │
│   └──────────┘                 └──────────────────────┘    │
│                                         │                  │
│                                         ▼                  │
│                               调用 on_read_ready()        │
│                               → Handler::handle_next_event │
│                                 → 从队列取出任务执行         │
└────────────────────────────────────────────────────────────┘
```

Reactor 的核心是 `epoll` 系统调用，它监控多个文件描述符，当某个描述符就绪时通知 Reactor：

```cpp
// system/gd/os/reactor.h:42-60
class Reactor {
public:
  class Reactable;
  Reactor();
  void Run();       // 阻塞运行事件循环
  void Stop();      // 从其他线程停止 Reactor
  Reactable* Register(int fd, common::Closure on_read_ready,
                      common::Closure on_write_ready);
  void Unregister(Reactable* reactable);
  bool WaitForUnregisteredReactable(std::chrono::milliseconds timeout);
  bool WaitForIdle(std::chrono::milliseconds timeout);

private:
  mutable std::mutex mutex_;
  int epoll_fd_;
  int control_fd_;
  std::atomic<bool> is_running_;
  // ...
};
```

### 8.2 Post()：将任务投递到目标线程

`Post()` 是 Handler 最核心的方法，它将一个闭包（任务）投递到 Handler 关联的线程上执行：

```cpp
// system/gd/os/handler.h:70
virtual void Post(common::OnceClosure closure) override;
```

实现细节：

```cpp
// system/gd/os/handler.cc:59-67
void Handler::Post(OnceClosure closure) {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (was_cleared()) {
      log::warn("Posting to a handler which has been cleared");
      return;
    }
    tasks_->emplace(std::move(closure));  // 将任务加入队列
  }
  event_->Notify();  // 通知 Reactor 有新任务
}
```

**执行流程**：

```
任意线程                          Handler 线程 (Reactor)
────────                         ─────────────────────
Post(closure)
  ├─ lock(mutex_)
  ├─ tasks_.push(closure)
  ├─ unlock(mutex_)
  └─ event_->Notify() ──────→   epoll_wait() 返回
                                 handle_next_event()
                                   ├─ lock(mutex_)
                                   ├─ closure = tasks_.front()
                                   ├─ tasks_.pop()
                                   ├─ unlock(mutex_)
                                   └─ closure()  ← 执行任务
```

### 8.3 Call() 和 CallOn()：带参数的任务投递

`Call()` 是 `Post()` 的便捷封装，允许直接传递可调用对象和参数：

```cpp
// system/gd/os/handler.h:78-81
template <typename Functor, typename... Args>
void Call(Functor&& functor, Args&&... args) {
  Post(common::BindOnce(std::forward<Functor>(functor),
                        std::forward<Args>(args)...));
}
```

`CallOn()` 是对特定对象方法的调用：

```cpp
// system/main/shim/acl.cc:1301-1305
void shim::Acl::GetConnectionLocalAddress(
    uint16_t handle, bool ota_address,
    std::promise<bluetooth::hci::AddressWithType> promise) {
  handler_->CallOn(pimpl_.get(), &Acl::impl::get_connection_local_address,
                   handle, ota_address, std::move(promise));
}
```

### 8.4 延迟任务：PostWithDelay()

Handler 支持延迟执行任务，内部使用优先队列和 Alarm 实现：

```cpp
// system/gd/os/handler.cc:112-134
bool Handler::PostWithDelay(OnceClosure closure,
                            std::chrono::milliseconds delay) {
  if (delay == std::chrono::milliseconds::zero()) {
    Post(std::move(closure));
    return true;
  }

  bool reschedule = false;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    if (was_cleared()) {
      return false;
    }
    auto time_to_run = boottime_clock::now() + delay;
    // 如果新任务比当前最早的延迟任务更早，需要重新调度 Alarm
    if (delayed_tasks_->empty() || delayed_tasks_->top().first > time_to_run) {
      reschedule = true;
    }
    delayed_tasks_->emplace(time_to_run, std::move(closure));
  }

  if (reschedule) {
    reschedule_delayed_tasks();
  }
  return true;
}
```

### 8.5 Handler 的生命周期管理

```
Handler 状态转换：

  Created ──→ Running ──→ Cleared ──→ Destroyed
    │            │            │
    │            │            └─ WaitUntilStopped(): 等待 Reactor 注销完成
    │            │
    │            └─ Post() / Call() / PostWithDelay(): 投递任务
    │
    └─ 构造时注册到 Reactor

  Clear(): 清空队列，注销 Reactable
  Synchronize(): 等待所有已投递任务执行完
```

`Clear()` 方法的实现展示了安全释放资源的技巧：

```cpp
// system/gd/os/handler.cc:69-89
void Handler::Clear() {
  std::queue<OnceClosure>* tmp = nullptr;
  Reactor::Reactable* reactable = nullptr;
  DelayedTaskQueue* delayed_tasks = nullptr;
  Alarm* alarm = nullptr;

  {
    std::lock_guard<std::mutex> lock(mutex_);
    log::assert_that(!was_cleared(), "Handlers must only be cleared once");
    // 使用 swap 将资源指针移到局部变量，在锁外释放
    std::swap(tasks_, tmp);
    std::swap(reactable_, reactable);
    std::swap(delayed_tasks_, delayed_tasks);
    std::swap(alarm_, alarm);
  }
  // 在锁外执行耗时操作，避免持锁时间过长
  alarm->Cancel();
  delete tmp;
  delete delayed_tasks;
  delete alarm;
  event_->Clear();
  thread_->GetReactor()->Unregister(reactable);
}
```

### 8.6 Handler 在协议栈中的使用模式

```
┌─────────────────────────────────────────────────────────────┐
│              蓝牙协议栈的 Handler 使用模式                     │
│                                                             │
│  Framework层 (Binder线程)                                    │
│       │                                                     │
│       │ connect(addr)                                       │
│       ▼                                                     │
│  Shim层 ─── Post() ──→ GD Handler (stack_handler_)          │
│       │                    │                                │
│       │                    │ 处理连接请求                      │
│       │                    ▼                                │
│       │              HCI层 ─── Post() ──→ HCI Handler        │
│       │                                   │                 │
│       │                                   │ 发送HCI命令       │
│       │                                   ▼                 │
│       │                              控制器 (硬件)            │
│       │                                   │                 │
│       │                              HCI事件回调             │
│       │                                   │                 │
│       │                    ← ── Post() ──┘                  │
│       │              GD Handler 处理事件                      │
│       │                    │                                │
│       │  ← ── Post() ───┘                                   │
│  Shim层 回调主线程                                            │
│       │                                                     │
│       ▼                                                     │
│  主线程 (do_in_main_thread)                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 9. 蓝牙协议栈中的线程安全最佳实践

### 9.1 所有共享数据必须用 mutex 保护

这是最基本的原则。在协议栈中，任何被多线程访问的可变数据都必须有对应的 mutex：

```cpp
// ✅ 正确：共享数据有对应的 mutex
std::recursive_mutex bgconn_dev_mutex;
std::map<RawAddress, tAPPS_CONNECTING> bgconn_dev;  // 受 bgconn_dev_mutex 保护

// ✅ 正确：Handler 的内部状态有 mutex 保护
mutable std::mutex mutex_;
std::queue<common::OnceClosure>* tasks_ GUARDED_BY(mutex_);
```

### 9.2 使用 GUARDED_BY 注解

为所有受 mutex 保护的成员变量添加 `GUARDED_BY` 注解，让编译器帮助检查：

```cpp
// ✅ 推荐：使用注解
std::queue<common::OnceClosure>* tasks_ GUARDED_BY(mutex_);
Reactor::Reactable* reactable_ GUARDED_BY(mutex_);
DelayedTaskQueue* delayed_tasks_ GUARDED_BY(mutex_);
Alarm* alarm_ GUARDED_BY(mutex_);

// ❌ 不推荐：没有注解，编译器无法检查
std::queue<common::OnceClosure>* tasks_;
```

### 9.3 跨线程操作用 Post/Call

永远不要在非 Handler 线程上直接操作该 Handler 管理的数据。使用 `Post()` 或 `Call()` 将操作投递到正确的线程：

```cpp
// ✅ 正确：通过 Post 将操作投递到目标线程
handler_->Post(common::BindOnce(&SomeClass::SomeMethod,
                                common::Unretained(this), args));

// ✅ 正确：使用 Call 简化调用
handler_->Call([](int fd, std::promise<void> promise) {
  // 在 Handler 线程上执行
  Dump(fd);
  promise.set_value();
}, fd, std::move(promise));

// ❌ 错误：直接在当前线程操作 Handler 管理的数据
handler_->tasks_->push(closure);  // 竞争条件！
```

### 9.4 避免在持锁时调用外部函数

持锁调用外部函数可能导致：
1. **死锁**：外部函数可能尝试获取同一把锁
2. **性能下降**：锁持有时间过长，阻塞其他线程
3. **优先级反转**：低优先级线程持锁，高优先级线程等待

```cpp
// ✅ 正确：在锁外执行外部操作
void Handler::Post(OnceClosure closure) {
  {
    std::lock_guard<std::mutex> lock(mutex_);
    tasks_->emplace(std::move(closure));
  }  // 锁已释放
  event_->Notify();  // 在锁外通知
}

// ✅ 正确：使用 swap 技巧在锁外释放资源
void Handler::Clear() {
  std::queue<OnceClosure>* tmp = nullptr;
  {
    std::lock_guard<std::mutex> lock(mutex_);
    std::swap(tasks_, tmp);  // 快速交换指针
  }
  delete tmp;  // 在锁外释放
}
```

### 9.5 使用 Synchronize() 确保任务完成

在关闭 Handler 之前，使用 `Synchronize()` 确保所有已投递的任务都已完成：

```cpp
// system/common/message_loop_thread.cc:148-155
log::assert_that(handler_->Synchronize(kHandlerStopTimeout),
                 "Could not synchronize the handler for thread: {}",
                 handler_thread_->GetThreadName());
handler_->Clear();
```

### 9.6 使用 promise/future 进行跨线程同步

当需要等待某个操作在另一个线程上完成时，使用 `promise/future` 而不是自己实现条件变量：

```cpp
// ✅ 正确：使用 promise/future
std::promise<void> promise;
auto future = promise.get_future();
handler_->Post(common::BindOnce(&std::promise<void>::set_value,
                                common::Unretained(&promise)));
if (future.wait_for(timeout) == std::future_status::ready) {
  // 操作完成
}

// ❌ 不推荐：手动使用条件变量（容易出错）
std::mutex m;
std::condition_variable cv;
bool done = false;
handler_->Post([&]() {
  std::lock_guard<std::mutex> lock(m);
  done = true;
  cv.notify_one();
});
std::unique_lock<std::mutex> lock(m);
cv.wait_for(lock, timeout, [&]{ return done; });
```

### 9.7 选择合适的锁类型

```
锁类型选择指南：

std::mutex
├── 默认选择，性能最好
├── 不允许同一线程重复加锁
└── 适用于：大多数场景

std::recursive_mutex
├── 允许同一线程重复加锁
├── 性能略差
└── 适用于：函数调用链中需要重入的场景
    （如 connection_manager、AVRCP）

std::atomic
├── 无锁，性能最好
├── 只能保护单个变量
└── 适用于：简单状态标志、计数器
    （如 is_running_、state_flags、enqueue_registered_）
```

### 9.8 线程安全检查清单

在编写蓝牙协议栈代码时，请对照以下清单检查：

| 检查项 | 说明 |
|--------|------|
| ☐ 共享数据是否有 mutex 保护？ | 所有被多线程访问的可变数据 |
| ☐ 是否使用了 `GUARDED_BY` 注解？ | 编译时检查锁的正确性 |
| ☐ 跨线程操作是否通过 `Post/Call`？ | 不要在非 Handler 线程直接操作 |
| ☐ 是否在持锁时调用了外部函数？ | 避免持锁调用可能阻塞的函数 |
| ☐ 是否选择了正确的锁类型？ | 需要重入用 `recursive_mutex`，简单标志用 `atomic` |
| ☐ 资源释放是否在锁外进行？ | 使用 swap 技巧将资源移到锁外释放 |
| ☐ 关闭时是否先 Synchronize？ | 确保所有任务完成后再 Clear |
| ☐ promise/future 的超时处理？ | 始终设置合理的超时，避免无限等待 |

---

## 附录：关键源文件索引

| 文件 | 并发原语 | 说明 |
|------|----------|------|
| `system/gd/os/handler.h` | mutex, lock_guard, GUARDED_BY, promise/future | Handler 线程模型核心 |
| `system/gd/os/handler.cc` | lock_guard, swap 技巧 | Handler 实现 |
| `system/gd/os/reactor.h` | atomic, mutex, future, promise | Reactor 事件循环 |
| `system/gd/os/queue.h` | atomic_bool, mutex, lock_guard | 流控队列 |
| `system/gd/os/thread.h` | mutex, thread | 线程抽象 |
| `system/stack/connection_manager/connection_manager.cc` | recursive_mutex, lock_guard | 连接管理 |
| `system/stack/btm/btm_iso_impl.h` | atomic_uint8_t, atomic_uint16_t | ISO 状态管理 |
| `system/main/shim/stack.cc` | promise/future, recursive_mutex | 协议栈启动/停止 |
| `system/main/shim/acl.cc` | chrono::time_point, promise | ACL 连接管理 |
| `system/osi/src/mutex.cc` | recursive_mutex | 全局锁 |
| `system/gd/hal/hci_hal_impl_android.cc` | mutex, lock_guard | HCI 数据接收 |
| `system/gd/hci/hci_layer_fake.h` | GUARDED_BY, LOCKS_EXCLUDED | 测试替身 |
| `system/stack/arbiter/acl_arbiter.h` | GUARDED_BY | ACL 仲裁器 |
