# 08 - 移动语义与完美转发

> **目标读者**：了解 C++ 基本引用（`T&`），但不了解右值引用和移动语义的开发者
> **代码来源**：Android 蓝牙协议栈（AOSP Bluetooth）

---

## 目录

1. [为什么需要移动语义](#1-为什么需要移动语义)
2. [左值与右值](#2-左值与右值)
3. [std::move](#3-stdmove)
4. [移动构造函数与移动赋值](#4-移动构造函数与移动赋值)
5. [= delete 和 = default](#5-delete-和-default)
6. [完美转发 std::forward](#6-完美转发-stdforward)
7. [返回值优化 (RVO/NRVO)](#7-返回值优化-rvonrvo)
8. [实际开发中的最佳实践](#8-实际开发中的最佳实践)

---

> 📎 关联教材：05(智能指针), 06(现代C++特性), 14(Chromium基础库)

## 1. 为什么需要移动语义

### 1.1 拷贝的开销

在 C++11 之前，所有"传递对象"的操作都是**拷贝**。对于包含动态内存的类（如 `std::string`、`std::vector`），每次拷贝都意味着深拷贝——分配新内存、逐字节复制数据。

```cpp
std::string a = "Hello, Bluetooth Low Energy!";  // a 拥有一块内存
std::string b = a;  // 拷贝：b 分配新内存，把 a 的内容逐字节复制过来
```

想象一下：`a` 里面存了一个 1MB 的蓝牙数据包，你只是想把 `a` 交给另一个函数去处理，处理完之后 `a` 就不再需要了。但拷贝意味着要再分配 1MB 内存、再复制 1MB 数据——**完全是浪费**。

```
拷贝前:  a ──▶ [1MB 数据]
拷贝后:  a ──▶ [1MB 数据]    ← a 仍然持有，但我们不再需要它了
         b ──▶ [1MB 数据]    ← 新分配的 1MB 内存，内容完全相同
```

### 1.2 移动 vs 拷贝

**移动**的核心思想：与其复制数据，不如直接"偷走"源对象的资源（指针、文件句柄等），让目标对象接管。

```
移动前:  a ──▶ [1MB 数据]
移动后:  b ──▶ [1MB 数据]    ← b 直接接管了 a 的内存
         a ──▶ nullptr       ← a 变为空，不再拥有资源
```

移动操作通常是 O(1) 的——只需交换几个指针，而不需要复制大量数据。

```cpp
// 拷贝：O(n)，需要复制所有数据
std::string b = a;

// 移动：O(1)，只转移指针所有权
std::string c = std::move(a);  // a 之后不再有效
```

### 1.3 移动后源对象的状态

移动后，源对象进入**有效但未指定（valid but unspecified）**的状态：

- **有效**：你可以安全地对其进行赋值或析构，不会崩溃
- **未指定**：你不应该假设它还持有原来的值

```cpp
std::string a = "Bluetooth";
std::string b = std::move(a);

// a 现在是"有效但未指定"的状态
// 大多数实现下 a 变为空字符串 ""，但标准不保证
// 安全操作：a = "new value";  ✅ 重新赋值
// 安全操作：~a()              ✅ 析构
// 危险操作：cout << a;        ⚠️ 结果未定义，可能为空，也可能是其他值
```

> **实践建议**：移动源对象后，不要再读取它的值，除非你给它赋了新值。

### ☕ Java 类比

Java **不需要移动语义**，因为 Java 有垃圾回收器（GC），对象的传递天然就是引用传递（零拷贝）。

| 对比项 | C++ | Java |
|--------|-----|------|
| 对象传递方式 | 默认值拷贝（深拷贝），需移动语义优化 | 天然引用传递（零拷贝） |
| 移动语义 | `std::move`，转移资源所有权 | 不需要（GC 管理对象生命周期） |
| 深拷贝问题 | 存在（`string`、`vector` 等） | 不存在（赋值只是复制引用） |
| 移动后源对象 | 有效但未指定 | 不适用（引用传递，无"移动"概念） |

**C++ 拷贝 vs 移动：**

```cpp
std::string a = "Bluetooth";  // a 拥有内存
std::string b = a;            // 拷贝：b 分配新内存，复制内容
std::string c = std::move(a); // 移动：c 接管 a 的内存，a 变空
```

**Java 的等价操作：**

```java
String a = "Bluetooth";  // a 引用字符串对象
String b = a;            // 只复制引用，不复制对象！零开销
String c = a;            // 同上，a、b、c 指向同一个对象
// 不需要 "移动"，因为 Java 从不深拷贝对象
```

> **为什么 Java 不需要移动语义？** Java 中所有对象都通过引用访问，赋值操作只复制引用（4/8 字节），不复制对象本身。GC 自动管理对象生命周期，当没有引用指向对象时自动回收。因此 Java 不存在 C++ 的"深拷贝开销"问题，也就不需要移动语义。

### 📌 本节小结

- 移动语义的核心：与其复制数据，不如"偷走"源对象的资源，让目标对象接管
- 移动操作通常是O(1)（交换指针），而拷贝是O(n)（复制所有数据）
- 移动后源对象进入"有效但未指定"状态，不应再读取其值
- Java不需要移动语义，因为对象传递天然是引用传递（零拷贝）

---

## 2. 左值与右值

### 2.1 左值（lvalue）

**左值**是有名字的、可以取地址的表达式。你可以把它理解为"有固定位置的东西"。

```cpp
int x = 10;          // x 是左值
std::string name = "BLE";  // name 是左值
&x;                  // ✅ 可以取地址
&name;               // ✅ 可以取地址

// 函数返回左值引用时，结果也是左值
int& get_ref();
get_ref() = 5;       // ✅ 可以赋值，因为 get_ref() 返回左值
```

### 2.2 右值（rvalue）

**右值**是没有名字的、无法取地址的临时对象或字面量。

```cpp
10;                  // 右值：字面量
x + 1;               // 右值：临时计算结果
std::string("BLE");  // 右值：临时对象

&10;                 // ❌ 无法取地址
&(x + 1);            // ❌ 无法取地址
```

右值的生命周期很短暂——通常在当前表达式结束后就被销毁了。

### 2.3 左值引用 vs 右值引用

| 类型 | 声明 | 能绑定到 | 用途 |
|------|------|---------|------|
| 左值引用 | `T&` | 左值 | 修改已有对象 |
| 常量左值引用 | `const T&` | 左值和右值 | 只读访问（万能但无法修改右值） |
| 右值引用 | `T&&` | 右值 | 移动语义的核心 |

```cpp
int x = 10;

int& lr = x;           // ✅ 左值引用绑定到左值
int& lr2 = 10;         // ❌ 左值引用不能绑定到右值
const int& clr = 10;   // ✅ const 左值引用可以绑定到右值（但无法修改）
int&& rr = 10;         // ✅ 右值引用绑定到右值
int&& rr2 = x;         // ❌ 右值引用不能绑定到左值
int&& rr3 = std::move(x);  // ✅ std::move 把左值转为右值引用
```

**右值引用的核心意义**：它让我们能"捕获"即将销毁的临时对象，从中"偷走"资源，而不是白白地复制一份再销毁。

### ☕ Java 类比

Java **没有**右值引用的概念，也不需要。

| 对比项 | C++ | Java |
|--------|-----|------|
| 左值 | 有名字、可取地址的表达式 | 不区分（Java 所有对象都是引用） |
| 右值 | 临时对象、字面量 | 不区分 |
| 左值引用 `T&` | 绑定到左值 | 不适用（Java 引用天然是引用） |
| 右值引用 `T&&` | 绑定到右值，移动语义核心 | 不适用 |
| `const T&` | 可绑定左值和右值 | 不适用（Java 无 const 引用） |

> **为什么 Java 不需要右值引用？** Java 的对象始终通过引用访问，不存在"值拷贝 vs 引用"的选择问题。C++ 引入右值引用是为了区分"可以偷走资源的临时对象"和"不能偷走资源的持久对象"，而 Java 的 GC 已经解决了资源管理问题。

### 📌 本节小结

- 左值有名字可取地址（如变量），右值是临时对象或字面量（如`42`、`std::string("BLE")`）
- 右值引用`T&&`是移动语义的核心，让我们能"捕获"即将销毁的临时对象
- `const T&`可绑定左值和右值（万能但无法修改），`T&`只能绑定左值
- `std::move(x)`将左值转为右值引用，让编译器选择移动版本

---

## 3. std::move

### 3.1 std::move 并不移动！

这是最重要的概念：**`std::move` 本身不移动任何东西**。它只是一个类型转换——把左值转换为右值引用。

```cpp
// std::move 的简化实现
template<typename T>
constexpr typename std::remove_reference<T>::type&& move(T&& t) noexcept {
    return static_cast<typename std::remove_reference<T>::type&&>(t);
}
```

它做的事情等价于 `static_cast<T&&>(t)`，仅仅是**改变了值的类别**，让编译器选择移动版本的函数（移动构造/移动赋值），而不是拷贝版本。

```cpp
std::string a = "Bluetooth";
std::string b = std::move(a);  // std::move 只是让 a 变成右值
                                // 真正的"移动"发生在 string 的移动构造函数里
```

### 3.2 何时使用 std::move

**原则**：当你确定某个对象不再需要，希望转移其资源时，使用 `std::move`。

典型场景：
1. 将对象传入函数后不再使用
2. 将对象放入容器后不再使用
3. 函数返回时转移局部对象
4. 一次性回调（callback）被消费时

### 3.3 蓝牙协议栈中的真实示例

#### 示例 1：传递回调给 HCI 命令

```cpp
// system/stack/hcic/hciblecmds.cc:391
btu_hcif_send_cmd_with_cb(HCI_LE_SET_CIG_PARAMS, param, params_len, std::move(cb));
```

**分析**：`cb` 是一个回调对象（`base::OnceCallback`），代表"一次性"操作。用 `std::move(cb)` 把它传给 `btu_hcif_send_cmd_with_cb`，意味着调用之后 `cb` 就不再有效了——这正是 `OnceCallback` 的语义：只能调用一次。

如果不使用 `std::move`，`cb` 会被拷贝，那么调用者手里还保留着一份回调，这违反了"一次性"的约定，可能导致回调被执行两次。

#### 示例 2：将操作数据放入容器

```cpp
// system/stack/gatt/gatt_attr.cc:569
OngoingOps[conn_id].emplace_back(std::move(cb_data));
```

**分析**：`cb_data` 是一个 GATT 操作的回调数据。把它 `emplace_back` 到 `OngoingOps` 容器后，调用者不再需要 `cb_data`。使用 `std::move` 避免了一次不必要的深拷贝。

#### 示例 3：链式传递参数

```cpp
// system/gd/storage/mutation_entry.h:37-38
return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                          std::to_string(value_param));
```

**分析**：`section_param` 和 `property_param` 都是 `std::string`，在 `Set` 函数内部它们会被存入 `MutationEntry` 对象。使用 `std::move` 将字符串的所有权转移给下一层函数，避免中间的字符串拷贝。

#### 示例 4：消费一次性回调

```cpp
// system/stack/connection_manager/connection_manager.cc:64-65
static void alarm_closure_cb(void* p) {
  closure_data* data = (closure_data*)p;
  std::move(data->user_task).Run();  // 移动并执行一次性回调
  delete data;
}
```

**分析**：`user_task` 是 `base::OnceClosure`（一次性闭包）。`std::move(data->user_task).Run()` 的含义是：
1. `std::move` 将 `user_task` 转为右值引用
2. 调用 `OnceClosure` 的右值限定版 `Run()`（只能对右值调用）
3. 执行后，`user_task` 变为空状态，确保不会被再次调用

这种写法在编译期保证了"一次性"语义——如果你忘了 `std::move`，编译器会报错，因为 `OnceClosure::Run()` 只接受右值。

### ☕ Java 类比

Java **不需要** `std::move`，因为 Java 没有移动语义的需求。

| 对比项 | C++ `std::move` | Java |
|--------|------------------|------|
| 作用 | 将左值转为右值引用，触发移动 | 不需要 |
| 本质 | `static_cast<T&&>(t)` | 不适用 |
| 使用场景 | 传递不再需要的对象、一次性回调 | 不适用 |
| 移动后源对象 | 有效但未指定 | 不适用 |

**C++ std::move 示例：**

```cpp
// 一次性回调：移动后原回调不可再使用
btu_hcif_send_cmd_with_cb(HCI_LE_SET_CIG_PARAMS, param, params_len, std::move(cb));
// cb 此后不可再使用
```

**Java 的等价写法：**

```java
// Java 没有移动语义，回调对象可以多次传递
sendCommand(HCI_LE_SET_CIG_PARAMS, param, paramsLen, callback);
// callback 仍然有效，但逻辑上只应调用一次（靠约定，不靠编译器强制）
```

> **关键区别**：C++ 的 `std::move` 在编译期强制"一次性"语义——`OnceClosure::Run()` 只能对右值调用。Java 无法在编译期强制这种约束，只能靠运行时检查或编程约定。

### 📌 本节小结

- `std::move`本身不移动任何东西，只是`static_cast<T&&>(t)`类型转换
- 使用原则：确定对象不再需要时才用`std::move`转移资源
- 蓝牙协议栈中`std::move`最常用于一次性回调传递和容器插入
- `std::move(data->user_task).Run()`在编译期保证"一次性"语义

---

## 4. 移动构造函数与移动赋值

### 4.1 移动构造函数

移动构造函数从另一个对象"窃取"资源，而不是复制：

```cpp
class Buffer {
public:
    // 普通构造
    Buffer(size_t size) : size_(size), data_(new int[size]) {}

    // 移动构造函数
    Buffer(Buffer&& other) noexcept
        : size_(other.size_), data_(other.data_) {
        other.size_ = 0;
        other.data_ = nullptr;  // 源对象置空，防止双重释放
    }

    ~Buffer() { delete[] data_; }

private:
    size_t size_;
    int* data_;
};
```

### 4.2 移动赋值运算符

```cpp
Buffer& operator=(Buffer&& other) noexcept {
    if (this != &other) {
        delete[] data_;           // 释放自己的旧资源
        size_ = other.size_;
        data_ = other.data_;
        other.size_ = 0;
        other.data_ = nullptr;
    }
    return *this;
}
```

### 4.3 noexcept 的重要性

移动操作通常应该标记为 `noexcept`。原因：**`std::vector` 扩容时的策略选择**。

当 `vector` 需要扩容时，它要把旧元素搬到新内存。它有两个选择：

| 元素的移动构造函数 | vector 的行为 |
|---|---|
| `noexcept` | 使用移动构造（O(n)，快） |
| 非 `noexcept` | 使用拷贝构造（O(n)，慢但安全） |

为什么？因为如果移动构造函数抛出异常，旧内存已经被破坏（部分元素被移走了），新内存又不完整——数据就丢失了。拷贝构造则不会破坏旧数据，即使抛异常也能回滚。

```cpp
// ❌ 没有 noexcept，vector 扩容时不敢用移动
Buffer(Buffer&& other);

// ✅ 有 noexcept，vector 扩容时放心用移动
Buffer(Buffer&& other) noexcept;
```

### 4.4 蓝牙协议栈中的真实示例

#### 示例 1：LeDevice 的移动操作

```cpp
// system/gd/storage/le_device.h:34-35
class LeDevice {
public:
  // 移动构造和移动赋值，使用 = default 让编译器自动生成
  LeDevice(LeDevice&& other) noexcept = default;
  LeDevice& operator=(LeDevice&& other) noexcept = default;

  // 拷贝操作也保留
  LeDevice(const LeDevice& other) noexcept = default;
  LeDevice& operator=(const LeDevice& other) noexcept = default;

private:
  ConfigCache* config_;           // 原始指针
  ConfigCache* memory_only_config_;  // 原始指针
  std::string section_;           // 字符串
};
```

**分析**：`LeDevice` 的成员是两个指针和一个 `std::string`。编译器自动生成的移动构造函数会：
- 拷贝两个指针（O(1)）
- 移动 `std::string`（O(1)，转移内部缓冲区）

这比拷贝构造（需要拷贝 `std::string` 的内容，O(n)）更高效。

#### 示例 2：LruCache 的移动操作

```cpp
// system/gd/common/lru_cache.h:68-69
template <typename Key, typename T>
class LruCache {
public:
  LruCache(LruCache&& other) noexcept = default;
  LruCache& operator=(LruCache&& other) noexcept = default;

  // 注意：拷贝操作需要手动实现，因为内部迭代器不能直接拷贝
  LruCache(const LruCache& other) : capacity_(other.capacity_), list_map_(other.list_map_) {}
  LruCache& operator=(const LruCache& other) {
    if (&other == this) return *this;
    capacity_ = other.capacity_;
    list_map_ = other.list_map_;
    return *this;
  }

private:
  size_t capacity_;
  ListMap<Key, T> list_map_;
};
```

**分析**：
- 移动操作用 `= default`，因为 `ListMap` 内部支持移动，编译器能正确生成
- 拷贝操作需要**手动实现**，因为 `list_map_` 内部有迭代器，迭代器不能直接拷贝
- 这体现了一个重要规律：**移动通常比拷贝简单得多**

### ☕ Java 类比

Java **不需要**移动构造函数和移动赋值运算符，因为 Java 的对象传递天然是引用传递。

| 对比项 | C++ | Java |
|--------|-----|------|
| 移动构造函数 | `T(T&& other)`，窃取资源 | 不需要（Java 无值语义） |
| 移动赋值 | `T& operator=(T&& other)` | 不需要（Java 无运算符重载） |
| 拷贝构造函数 | `T(const T& other)`，深拷贝 | 不常用（`clone()` 方法，需显式实现） |
| `noexcept` | 移动操作应标记 | 不适用（Java 异常机制不同） |
| vector 扩容策略 | 根据 `noexcept` 选择移动或拷贝 | 不适用（`ArrayList` 存储引用，扩容只复制引用） |

**C++ 移动构造示例：**

```cpp
class Buffer {
public:
    Buffer(Buffer&& other) noexcept
        : size_(other.size_), data_(other.data_) {
        other.size_ = 0;
        other.data_ = nullptr;  // 防止双重释放
    }
};
```

**Java 的等价操作：**

```java
// Java 不需要移动构造函数
// 对象传递只复制引用，不存在深拷贝问题
Buffer buf1 = new Buffer(1024);
Buffer buf2 = buf1;  // 只复制引用，零开销
// buf1 和 buf2 指向同一个对象，GC 统一管理
```

> **为什么 Java 不需要移动构造/赋值？** Java 的 `ArrayList` 等容器存储的是引用（4/8 字节），扩容时只需复制引用数组，不存在"深拷贝 vs 浅拷贝"的选择。C++ 容器直接存储对象值，扩容时需要决定是拷贝还是移动，因此需要 `noexcept` 来指导策略选择。

### 📌 本节小结

- 移动构造函数从源对象"窃取"资源（指针等），源对象置空防止双重释放
- `noexcept`至关重要：没有它，`std::vector`扩容时不敢使用移动，只能用拷贝
- `= default`让编译器生成移动操作，通常比手写更正确
- 移动通常比拷贝简单得多——只交换指针，不复制数据

---

## 5. = delete 和 = default

### 5.1 = default：让编译器生成默认实现

`= default` 告诉编译器："请帮我生成这个特殊成员函数的默认实现"。

```cpp
class Controller {
public:
  Controller() = default;          // 默认构造函数
  virtual ~Controller() = default; // 默认析构函数
};
```

什么时候用 `= default`：
- 你声明了其他构造函数，编译器不再自动生成默认构造函数时
- 你想明确表达"使用默认实现"的意图
- 虚析构函数需要 `= default` 来保持虚函数性质

### 5.2 = delete：禁止某个函数

`= delete` 告诉编译器："这个函数不允许调用"。

最常见的用途是**禁止拷贝**——对于管理独占资源（如文件句柄、网络连接、蓝牙连接）的类，拷贝没有意义甚至危险。

### 5.3 蓝牙协议栈中的真实示例

#### 示例 1：EattExtension — 禁止拷贝的单例

```cpp
// system/stack/eatt/eatt.h:112-113
class EattExtension {
public:
  EattExtension();
  EattExtension(const EattExtension&) = delete;
  EattExtension& operator=(const EattExtension&) = delete;

  static EattExtension* GetInstance() {
    static EattExtension* instance = new EattExtension();
    return instance;
  }
};
```

**分析**：`EattExtension` 是一个单例类，管理 EATT（Enhanced ATT）通道。单例不应该被拷贝——如果拷贝了一份，就出现了两个"管理者"，导致状态混乱。`= delete` 在编译期阻止了这种错误。

#### 示例 2：HciLayer — 禁止拷贝的硬件接口

```cpp
// system/gd/hci/hci_layer.h:52-53
class HciLayer : public HciInterface {
public:
  HciLayer(const HciLayer&) = delete;
  HciLayer& operator=(const HciLayer&) = delete;
};
```

**分析**：`HciLayer` 是 HCI（Host Controller Interface）层的核心类，直接与蓝牙硬件通信。它持有硬件资源（HAL 指针、命令队列等），拷贝会导致两个对象试图操作同一硬件——这是灾难性的。

#### 示例 3：Controller — 默认构造/析构的接口类

```cpp
// system/gd/hci/controller.h:35-36
class Controller {
public:
  Controller() = default;
  virtual ~Controller() = default;
};
```

**分析**：`Controller` 是一个接口类（纯虚类），它本身不需要在构造/析构中做任何事。`= default` 明确表达了"使用默认实现"的意图，比空函数体更清晰：

```cpp
// 不推荐：空函数体，读者会疑惑"是不是忘了写什么？"
Controller() {}
virtual ~Controller() {}

// 推荐：= default，明确表示"我知道这里什么都不用做"
Controller() = default;
virtual ~Controller() = default;
```

#### 示例 4：tCONN_CB — 只允许默认构造，禁止拷贝

```cpp
// system/stack/sdp/sdpint.h:208-211
struct tCONN_CB {
  tCONN_CB() = default;                // 允许默认构造

private:
  tCONN_CB(const tCONN_CB&) = delete;  // 禁止拷贝
};
```

**分析**：`tCONN_CB` 是 SDP（Service Discovery Protocol）的连接控制块，包含连接状态、定时器等。它只允许默认构造（初始化为默认状态），但禁止拷贝——因为每个连接控制块对应一个唯一的连接，不应该被复制。

注意 `= delete` 被放在 `private` 区域。这是 C++11 的风格（在 `private` 中声明但不定义 = 禁止使用）。C++11 之后更推荐直接在 `public` 区域用 `= delete`，因为编译器能给出更清晰的错误信息。

### ☕ Java 类比

Java 通过访问控制和运行时异常来模拟 C++ 的 `= delete` 效果：

| 对比项 | C++ `= delete` | Java 替代方案 |
|--------|----------------|--------------|
| 禁止拷贝 | `T(const T&) = delete;` | 不实现 `Cloneable`，或将 `clone()` 设为 `private` |
| 禁止赋值 | `operator=(const T&) = delete;` | 不需要（Java 无赋值运算符重载） |
| 编译期检测 | **是**（调用已删除函数 → 编译错误） | 否（运行时异常或访问控制） |
| `= default` | 显式要求编译器生成默认实现 | 不需要（Java 自动提供默认构造） |

**C++ = delete 示例：**

```cpp
class EattExtension {
public:
    EattExtension(const EattExtension&) = delete;           // 编译期禁止
    EattExtension& operator=(const EattExtension&) = delete;
};
EattExtension copy = *inst;  // 编译错误！
```

**Java 替代方案：**

```java
class EattExtension {
    // 禁止克隆
    @Override
    private Object clone() throws CloneNotSupportedException {
        throw new CloneNotSupportedException("Singleton cannot be cloned");
    }
}
// EattExtension copy = inst.clone();  // 编译错误（private）或运行时异常
```

> **关键区别**：C++ 的 `= delete` 是编译期强制，任何尝试调用都会直接编译失败。Java 的替代方案要么是访问控制（`private`，编译期），要么是运行时异常，不如 C++ 优雅和统一。

---

### 5.4 Rule of Five / Rule of Zero

C++ 有两个重要规则：

**Rule of Zero**：如果一个类的所有成员都正确实现了拷贝/移动/析构，那么这个类**不需要**自己声明任何特殊成员函数。

```cpp
// Rule of Zero 的好例子
class LeDevice {
  // 不需要声明任何特殊成员函数
  // 编译器自动生成的就够用了
private:
  ConfigCache* config_;
  ConfigCache* memory_only_config_;
  std::string section_;
};
```

**Rule of Five**：如果你自定义了**任何一个**特殊成员函数（析构、拷贝构造、拷贝赋值、移动构造、移动赋值），那么你应该**显式定义全部五个**。

```cpp
// Rule of Five 的例子
class LruCache {
public:
  ~LruCache() { clear(); }                                    // 自定义析构
  LruCache(LruCache&& other) noexcept = default;              // 移动构造
  LruCache& operator=(LruCache&& other) noexcept = default;   // 移动赋值
  LruCache(const LruCache& other);                            // 拷贝构造（手动实现）
  LruCache& operator=(const LruCache& other);                 // 拷贝赋值（手动实现）
};
```

### 📌 本节小结

- `= default`让编译器生成默认实现，比手写空函数体更好（保持trivial性）
- `= delete`禁止函数调用，最常用于禁止拷贝（单例、资源管理类）
- Rule of Zero：所有成员正确实现时，不需要声明任何特殊成员函数
- Rule of Five：自定义任一特殊成员函数时，应显式定义全部五个

---

## 6. 完美转发 std::forward

### 6.1 问题：参数的值类别丢失

考虑一个通用的包装函数，它要把参数原封不动地传给另一个函数：

```cpp
// 尝试 1：用 const 引用
template<typename T>
void wrapper(const T& arg) {
    target(arg);  // 总是传左值引用，target 无法区分原始参数是左值还是右值
}
```

问题：如果 `target` 有重载版本（一个接受左值引用，一个接受右值引用），`wrapper` 永远只会调用左值版本——即使你传入的是右值。

```cpp
void target(std::string& s)  { std::cout << "左值版本\n"; }
void target(std::string&& s) { std::cout << "右值版本\n"; }

std::string name = "BLE";
wrapper(name);              // 期望调用左值版本 ✅
wrapper(std::string("BLE")); // 期望调用右值版本 ❌ 实际调用了左值版本！
```

### 6.2 引用折叠与万能引用

要解决这个问题，需要用到**万能引用（forwarding reference）**：

```cpp
template<typename T>
void wrapper(T&& arg) {  // T&& 是万能引用，不是右值引用！
    // ...
}
```

**万能引用的规则**（注意：只对模板参数推导有效）：

| 传入参数 | 推导的 T | `T&&` 的实际类型 |
|---------|---------|----------------|
| 左值 `name` | `std::string&` | `std::string& &&` → 折叠为 `std::string&` |
| 右值 `std::string("BLE")` | `std::string` | `std::string&&` |

这就是**引用折叠（reference collapsing）**规则：

- `& &` → `&`
- `& &&` → `&`
- `&& &` → `&`
- `&& &&` → `&&`

简单记忆：**只要有左值引用参与，结果就是左值引用**。

### 6.3 std::forward：恢复原始值类别

虽然万能引用能正确推导类型，但在函数体内，**命名的右值引用本身是左值**：

```cpp
template<typename T>
void wrapper(T&& arg) {
    target(arg);  // arg 有名字，所以是左值！即使 T&& 推导为右值引用
}
```

`std::forward` 的作用就是**恢复参数的原始值类别**：

```cpp
template<typename T>
void wrapper(T&& arg) {
    target(std::forward<T>(arg));  // 如果原始参数是左值，转发为左值
                                    // 如果原始参数是右值，转发为右值
}
```

`std::forward` 的简化实现：

```cpp
// 当 T = std::string&（左值传入）
// 返回 std::string&（左值引用）
template<typename T>
T&& forward(typename std::remove_reference<T>::type& t) noexcept {
    return static_cast<T&&>(t);
}

// 当 T = std::string（右值传入）
// 返回 std::string&&（右值引用）
template<typename T>
T&& forward(typename std::remove_reference<T>::type&& t) noexcept {
    static_assert(!std::is_lvalue_reference<T>::value, "不能将左值转发为右值");
    return static_cast<T&&>(t);
}
```

### 6.4 std::forward vs std::move

| | `std::move` | `std::forward` |
|---|---|---|
| **作用** | 无条件转为右值 | 有条件地转为右值（仅当原始参数是右值时） |
| **使用场景** | 你确定要移动这个对象 | 你只是转发，保持原始语义 |
| **典型位置** | 函数内部消费参数时 | 模板函数中传递参数时 |

```cpp
template<typename T>
void wrapper(T&& arg) {
    // 场景 1：我要消费 arg，不再需要它 → 用 std::move
    consume(std::move(arg));

    // 场景 2：我只是转发 arg，由调用者决定是否移动 → 用 std::forward
    forward_to(std::forward<T>(arg));
}
```

**错误示范**：在转发场景中使用 `std::move`：

```cpp
template<typename T>
void wrapper(T&& arg) {
    forward_to(std::move(arg));  // ❌ 即使调用者传入左值，也会被转为右值
                                  //    可能导致调用者的对象被意外移动
}

std::string name = "BLE";
wrapper(name);  // name 可能被意外清空！
```

### 6.5 蓝牙协议栈中的真实示例

#### 示例 1：Handler::Call — 完美转发回调和参数

```cpp
// system/gd/os/handler.h:78-81
template <typename Functor, typename... Args>
void Call(Functor&& functor, Args&&... args) {
  Post(common::BindOnce(std::forward<Functor>(functor), std::forward<Args>(args)...));
}
```

**逐行解析**：

1. `Functor&& functor` — 万能引用，可以接受任何可调用对象（lambda、函数指针、`std::function`、`BindOnce` 结果等）
2. `Args&&... args` — 参数包，每个参数都是万能引用
3. `std::forward<Functor>(functor)` — 保持 `functor` 的原始值类别：
   - 如果传入的是左值回调，转发为左值（`BindOnce` 会拷贝它）
   - 如果传入的是右值回调（如 `std::move(callback)`），转发为右值（`BindOnce` 会移动它）
4. `std::forward<Args>(args)...` — 对每个参数做同样的完美转发

**使用示例**：

```cpp
// 传入右值回调 + 右值参数 → 全部被移动
handler->Call(std::move(my_callback), std::move(my_data));

// 传入左值回调 + 左值参数 → 全部被拷贝
handler->Call(existing_callback, existing_data);
```

#### 示例 2：Handler::CallOn — 完美转发成员函数调用

```cpp
// system/gd/os/handler.h:83-87
template <typename T, typename Functor, typename... Args>
void CallOn(T* obj, Functor&& functor, Args&&... args) {
  Post(common::BindOnce(std::forward<Functor>(functor), common::Unretained(obj),
                        std::forward<Args>(args)...));
}
```

**分析**：与 `Call` 类似，但多了一个 `T* obj` 参数。`Unretained(obj)` 是裸指针包装器，表示"不管理对象生命周期"。`functor` 和 `args` 通过 `std::forward` 完美转发。

**为什么不用 `std::move`**：因为 `Call` 和 `CallOn` 是通用模板函数，它们不知道调用者传入的是左值还是右值。使用 `std::forward` 可以保持调用者的意图——如果调用者传入左值，就拷贝；如果传入右值，就移动。

#### 示例 3：LruCache::try_emplace — 完美转发构造参数

```cpp
// system/gd/common/lru_cache.h:155-169
template <class... Args>
std::tuple<iterator, bool, std::optional<node_type>> try_emplace(const Key& key, Args&&... args) {
  if (contains(key)) {
    return std::make_tuple(end(), false, std::nullopt);
  }
  std::optional<node_type> evicted_node = std::nullopt;
  if (list_map_.size() == capacity_) {
    evicted_node = list_map_.extract(std::prev(list_map_.end())->first);
  }
  auto pair = list_map_.try_emplace(list_map_.begin(), key, std::forward<Args>(args)...);
  return std::make_tuple(pair.first, pair.second, std::move(evicted_node));
}
```

**分析**：`try_emplace` 在缓存中原地构造值对象。`Args&&... args` 是构造参数，通过 `std::forward<Args>(args)...` 完美转发给 `list_map_::try_emplace`，最终传给值类型的构造函数。

注意最后一行 `std::move(evicted_node)`：这里用 `std::move` 而不是 `std::forward`，因为 `evicted_node` 是函数内的局部变量，我们确定要转移它，不需要保持原始值类别。

### ☕ Java 类比

Java **不需要**完美转发，因为 Java 的泛型使用类型擦除，不存在"左值/右值"区分。

| 对比项 | C++ `std::forward` | Java |
|--------|---------------------|------|
| 完美转发 | `std::forward<T>(arg)` | 不需要 |
| 万能引用 | `T&& arg` | 不适用 |
| 引用折叠 | `& &&` → `&`，`&& &&` → `&&` | 不适用 |
| 保持值类别 | 转发时保持左值/右值属性 | 不适用（Java 只有引用） |
| 模板参数推导 | 推导为 `T&` 或 `T` | 类型擦除，统一为 `Object` |

> **为什么 Java 不需要完美转发？** Java 的方法参数只有一种传递方式——引用传递。不存在"拷贝还是移动"的选择，因此不需要保持参数的"值类别"。Java 的泛型方法天然就是"完美转发"的——参数原样传递，无需额外处理。

### 📌 本节小结

- 完美转发解决"参数值类别丢失"问题：万能引用`T&&`+`std::forward<T>`保持原始左值/右值属性
- 引用折叠规则：只要有左值引用参与，结果就是左值引用
- `std::move`是无条件转右值，`std::forward`是有条件转右值
- 消费参数用`std::move`，转发参数用`std::forward`

---

## 7. 返回值优化 (RVO/NRVO)

### 7.1 编译器自动优化

C++ 编译器可以自动消除返回值的拷贝/移动，这叫做**返回值优化（RVO）**。

```cpp
std::string create_message() {
    std::string msg = "Hello, BLE!";
    return msg;  // NRVO：编译器直接在调用者的栈上构造 msg，无需拷贝或移动
}

std::string create_message2() {
    return std::string("Hello, BLE!");  // RVO：编译器直接在调用者的栈上构造临时对象
}
```

C++17 起，RVO 对纯右值（prvalue）是**强制**的（guaranteed copy elision）：

```cpp
// C++17 保证：不会发生任何拷贝或移动
std::string s = std::string("Hello");
```

### 7.2 什么时候不需要 std::move 返回值

**常见错误**：在 return 语句中对局部变量使用 `std::move`。

```cpp
std::string create_message() {
    std::string msg = "Hello, BLE!";
    return std::move(msg);  // ❌ 反而可能阻止 NRVO！
}
```

为什么？因为 NRVO 的条件之一是返回的是**局部变量本身**（不是右值引用）。当你写 `return std::move(msg)` 时，返回的不再是 `msg` 本身，而是一个右值引用，编译器可能无法应用 NRVO。

不过，C++11 起有一条特殊规则：如果 NRVO 没有生效，编译器也会**自动**把局部变量的返回当作右值处理（先尝试移动，再尝试拷贝）。所以你不需要手动加 `std::move`。

**正确做法**：

```cpp
std::string create_message() {
    std::string msg = "Hello, BLE!";
    return msg;  // ✅ 编译器优先 NRVO，不行则自动移动
}
```

### 7.3 蓝牙协议栈中的 RVO 示例

```cpp
// system/gd/storage/mutation_entry.h:88-92
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, std::string value_param) {
  return MutationEntry(EntryType::SET, property_type, std::move(section_param),
                       std::move(property_param), std::move(value_param));
}
```

**分析**：这里 `return` 的是构造函数调用（纯右值），C++17 保证不会发生拷贝。构造函数内部的参数用 `std::move` 是正确的——因为 `section_param` 等是函数参数（不是返回值），我们需要将它们移动到 `MutationEntry` 的成员中。

### ☕ Java 类比

Java **不需要** RVO/NRVO，因为 Java 的对象都在堆上，返回对象只返回引用。

| 对比项 | C++ RVO/NRVO | Java |
|--------|-------------|------|
| 返回值优化 | 编译器消除返回值的拷贝/移动 | 不需要（返回引用，零开销） |
| `return std::move(x)` | ❌ 可能阻止 NRVO | 不适用 |
| `return x;` | ✅ 编译器优先 NRVO，不行则自动移动 | 返回引用，天然零开销 |
| C++17 强制消除 | `return T(args);` 保证零拷贝 | 不适用 |

**C++ RVO 示例：**

```cpp
std::string create_message() {
    std::string msg = "Hello, BLE!";
    return msg;  // NRVO：编译器直接在调用者栈上构造 msg
}
```

**Java 的等价操作：**

```java
String createMessage() {
    String msg = "Hello, BLE!";
    return msg;  // 只返回引用，天然零开销
}
// Java 的对象始终在堆上，返回只是复制引用（4/8 字节）
// 不存在 C++ 那样的"返回值拷贝"问题
```

> **为什么 Java 不需要 RVO？** Java 的方法返回对象时，只返回堆上对象的引用（4/8 字节），不存在"拷贝整个对象"的开销。C++ 的 RVO 是为了消除"在函数栈上构造对象，然后拷贝到调用者栈上"的开销，这个问题在 Java 中根本不存在。

### 📌 本节小结

- RVO/NRVO让编译器直接在调用者栈上构造返回值，消除拷贝/移动
- C++17起RVO对纯右值是强制的（guaranteed copy elision）
- **不要**在return语句中对局部变量用`std::move`，会阻止NRVO
- C++11起即使NRVO没生效，编译器也会自动将局部变量返回当作右值处理

---

## 8. 实际开发中的最佳实践

### 8.1 函数参数传递指南

| 参数类型 | 传递方式 | 原因 |
|---------|---------|------|
| 只读小类型（`int`, `double`, 指针） | 按值传递 `T` | 拷贝开销可忽略 |
| 只读大类型（`string`, `vector`） | `const T&` | 避免拷贝 |
| 需要修改原对象 | `T&` | 直接修改 |
| 需要转移所有权 | `T&&` 或按值传递 + `std::move` | 移动语义 |
| 需要存储/转发参数 | 万能引用 `T&&` + `std::forward<T>` | 完美转发 |

```cpp
// 只读小类型 → 按值
void set_channel(uint16_t cid);

// 只读大类型 → const 引用
void process_packet(const std::vector<uint8_t>& data);

// 需要修改 → 非const引用
void update_device(Device& device);

// 转移所有权 → 右值引用
void send_command(base::OnceCallback<void()> cb);  // OnceCallback 只能移动

// 通用转发 → 完美转发
template<typename T>
void wrapper(T&& arg) { target(std::forward<T>(arg)); }
```

### 8.2 蓝牙协议栈中 std::move 的典型使用模式

#### 模式 1：一次性回调传递

这是蓝牙协议栈中最常见的 `std::move` 模式。HCI 命令是异步的，发送命令时传入回调，命令完成后执行回调。回调只能执行一次，所以必须移动。

```cpp
// 发送 HCI 命令，传递一次性回调
void btsnd_hcic_le_set_cig_params(..., base::OnceCallback<void(uint8_t*, uint16_t)> cb) {
  // ... 构造 HCI 命令参数 ...
  btu_hcif_send_cmd_with_cb(HCI_LE_SET_CIG_PARAMS, param, params_len, std::move(cb));
}

// 定时器回调
void alarm_set_closure(alarm_t* alarm, uint64_t interval_ms, base::OnceClosure user_task) {
  closure_data* data = new closure_data;
  data->user_task = std::move(user_task);  // 移动到堆上的结构体
  alarm_set_on_mloop(alarm, interval_ms, alarm_closure_cb, data);
}
```

#### 模式 2：容器中插入元素

```cpp
// GATT 操作入队
gatt_op_cb_data cb_data;
cb_data.cb = base::BindOnce([](const RawAddress&, uint8_t) { return; });
cb_data.op_uuid = GATT_UUID_CLIENT_SUP_FEAT;
OngoingOps[conn_id].emplace_back(std::move(cb_data));  // 移动入容器
```

#### 模式 3：链式参数传递

```cpp
// 字符串参数从外层传递到内层，每层都用 std::move 避免拷贝
MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                   std::to_string(value_param));
```

#### 模式 4：LRU 缓存中的值转移

```cpp
// LruCache::insert_or_assign 中，值被移动到缓存或赋值给已有条目
std::optional<node_type> insert_or_assign(const Key& key, T value) {
  if (contains(key)) {
    list_map_.begin()->second = std::move(value);  // 移动赋值
    return std::nullopt;
  }
  // ...
  list_map_.insert_or_assign(list_map_.begin(), key, std::move(value));  // 移动插入
  return evicted_node;
}
```

### 8.3 常见错误

#### 错误 1：移动后继续使用源对象

```cpp
std::string name = "Bluetooth";
std::string other = std::move(name);
std::cout << name << std::endl;  // ❌ 未定义行为，name 可能是空的
```

#### 错误 2：在 return 语句中使用 std::move

```cpp
std::string create() {
    std::string s = "BLE";
    return std::move(s);  // ❌ 阻止 NRVO，反而可能更慢
}
// 正确写法：
// return s;  ✅
```

#### 错误 3：在完美转发场景中使用 std::move

```cpp
template<typename T>
void wrapper(T&& arg) {
    target(std::move(arg));  // ❌ 即使传入左值也会被转为右值
}
// 正确写法：
// target(std::forward<T>(arg));  ✅
```

#### 错误 4：对 const 对象使用 std::move

```cpp
const std::string name = "BLE";
std::string other = std::move(name);  // ⚠️ 不会移动！因为 const，实际执行的是拷贝
```

`std::move` 只是转为右值引用，但移动构造函数接受的是非 const 右值引用（`T&&`），const 右值引用（`const T&&`）无法匹配移动构造函数，只能匹配拷贝构造函数。

#### 错误 5：移动操作不加 noexcept

```cpp
class MyClass {
public:
    MyClass(MyClass&& other);  // ❌ 没有 noexcept，vector 扩容时不会使用移动
};
// 正确写法：
// MyClass(MyClass&& other) noexcept;  ✅
```

#### 错误 6：函数返回右值引用

```cpp
std::string&& bad_func() {
    std::string local = "BLE";
    return std::move(local);  // ❌ 返回局部变量的引用，悬垂引用！
}
// 正确写法：
// std::string good_func() {
//     std::string local = "BLE";
//     return local;  // ✅ NRVO 或隐式移动
// }
```

### 📌 本节小结

- 参数传递指南：小类型按值、大类型`const T&`、需修改`T&`、转移所有权`T&&`+move、转发用万能引用+forward
- 蓝牙协议栈中`std::move`四大模式：一次性回调、容器插入、链式传递、LRU缓存值转移
- 移动后不要读、返回值不要`std::move`、移动操作加`noexcept`
- 对const对象`std::move`不会移动，只会拷贝

---

## 总结

| 概念 | 一句话总结 |
|------|-----------|
| **移动语义** | 与其复制数据，不如转移资源所有权 |
| **左值/右值** | 左值有名字可取地址，右值是临时对象 |
| **右值引用 `T&&`** | 捕获右值，让移动成为可能 |
| **`std::move`** | 无条件转为右值引用，本身不移动 |
| **`std::forward`** | 有条件地转发，保持原始值类别 |
| **移动构造/赋值** | 从源对象"偷"资源，源对象变为空 |
| **`noexcept`** | 移动操作必须加，否则 vector 不敢用 |
| **`= delete`** | 禁止拷贝，保护独占资源 |
| **`= default`** | 让编译器生成默认实现 |
| **RVO/NRVO** | 编译器自动消除返回值的拷贝/移动 |

**核心心法**：

1. **`std::move`** = "我不再需要这个对象了，你可以偷走它的资源"
2. **`std::forward`** = "我只是个搬运工，保持参数的原始左值/右值性质"
3. **移动后不要读** = 移动后的源对象处于"有效但未指定"状态
4. **返回值不要 `std::move`** = 让编译器做 NRVO
5. **移动操作加 `noexcept`** = 让标准库敢于使用移动

---

## 常见错误

### 1. 移动后继续使用源对象

```cpp
std::string name = "Bluetooth";
std::string other = std::move(name);
std::cout << name << std::endl;  // ❌ 未定义行为！name可能为空
name = "new value";              // ✅ 重新赋值后可以安全使用
```

移动后源对象处于"有效但未指定"状态，读取其值是未定义行为。应给源对象赋新值后再使用。

### 2. 在 return 中使用 std::move（阻碍 RVO）

```cpp
std::string create() {
    std::string s = "BLE";
    return std::move(s);  // ❌ 阻止NRVO，反而可能更慢！
}
// ✅ 正确写法：
// return s;  // 编译器优先NRVO，不行则自动移动
```

`return std::move(s)`返回的是右值引用而非局部变量本身，编译器可能无法应用NRVO。C++11起编译器会自动将`return s;`当作右值处理。

### 3. 忘记 noexcept

```cpp
class MyClass {
public:
    MyClass(MyClass&& other);  // ❌ 没有noexcept，vector扩容时不敢用移动
};
// ✅ 正确写法：
// MyClass(MyClass&& other) noexcept;
```

`std::vector`扩容时根据移动构造函数是否有`noexcept`决定使用移动还是拷贝。没有`noexcept`会退化为低效的拷贝。

### 4. 混淆 forward 和 move

```cpp
template<typename T>
void wrapper(T&& arg) {
    target(std::move(arg));  // ❌ 即使传入左值也会被转为右值，可能意外修改调用者的对象
}
// ✅ 正确写法：
// target(std::forward<T>(arg));  // 保持原始值类别
```

`std::move`是无条件转右值，`std::forward`是有条件转右值。转发参数时必须用`std::forward`，只有在你确定要消费参数时才用`std::move`。

---

## 速查卡

| 语法 | 用途 | 示例 | Java类比 |
|------|------|------|---------|
| `std::move` | 无条件转右值引用 | `std::string b = std::move(a);` | 不需要 |
| 右值引用`T&&` | 捕获右值，启用移动 | `void func(std::string&& s);` | 不适用 |
| 移动构造 | 从源对象窃取资源 | `T(T&& other) noexcept;` | 不需要 |
| `noexcept` | 承诺不抛异常 | `T(T&& other) noexcept;` | 不适用 |
| `std::forward` | 有条件转发，保持值类别 | `std::forward<T>(arg)` | 不需要 |
| `=delete` | 禁止函数 | `T(const T&) = delete;` | `private`构造函数 |
| `=default` | 显式默认实现 | `T() = default;` | 自动提供 |
| RVO/NRVO | 编译器消除返回值拷贝 | `return local_var;` | 不需要 |
