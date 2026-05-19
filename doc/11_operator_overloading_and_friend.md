# 运算符重载与 friend —— 基于蓝牙协议栈的 C++ 实战教材

> 本教材以 Android 蓝牙协议栈（Fluoride）真实代码为案例，系统讲解 C++ 中运算符重载与 friend 机制的核心知识。

---

## 目录

1. [运算符重载基础](#1-运算符重载基础)
2. [比较运算符重载](#2-比较运算符重载)
3. [流插入运算符重载 operator<<](#3-流插入运算符重载-operator)
4. [std::hash 特化](#4-stdhash-特化)
5. [std::formatter 特化 (C++20)](#5-stdformatter-特化-c20)
6. [friend 声明](#6-friend-声明)
7. [赋值运算符重载](#7-赋值运算符重载)

---

## 1. 运算符重载基础

### 1.1 什么是运算符重载

运算符重载（Operator Overloading）允许我们为自定义类型重新定义 C++ 内置运算符的行为。通过运算符重载，用户定义的类型可以像内置类型一样使用 `+`、`==`、`<`、`<<` 等运算符，从而使代码更直观、更符合领域语言的直觉。

**核心思想**：运算符重载本质上是函数调用的语法糖。当你写下 `a < b` 时，编译器实际上在寻找一个可以调用的 `operator<` 函数。

```cpp
// 这两种写法等价：
if (addr1 < addr2) { ... }           // 运算符语法（推荐）
if (addr1.operator<(addr2)) { ... }  // 函数调用语法（成员函数版本）
if (operator<(addr1, addr2)) { ... } // 函数调用语法（非成员函数版本）
```

### 1.2 可重载的运算符列表

C++ 允许重载以下运算符：

| 分类 | 运算符 |
|------|--------|
| **算术** | `+` `-` `*` `/` `%` `++` `--` |
| **关系/比较** | `==` `!=` `<` `>` `<=` `>=` `<=>`(C++20) |
| **逻辑** | `&&` `\|\|` `!` |
| **位运算** | `&` `\|` `^` `~` `<<` `>>` |
| **赋值** | `=` `+=` `-=` `*=` `/=` `%=` `&=` `\|=` `^=` `<<=` `>>=` |
| **下标与调用** | `[]` `()` `->` |
| **内存** | `new` `delete` `new[]` `delete[]` |
| **其他** | `,` `->*` |

**不可重载的运算符**：
- `.` （成员访问）
- `.*` （成员指针访问）
- `::` （作用域解析）
- `?:` （三目条件运算符）
- `sizeof`、`typeid`、`alignof`

### 1.3 重载的两种方式：成员函数 vs 非成员函数

#### 成员函数方式

```cpp
class MyClass {
public:
    // 左操作数是 *this，右操作数是参数
    bool operator<(const MyClass& rhs) const;
};
```

**特点**：
- 左操作数必须是该类的对象（或引用），不能进行隐式类型转换
- 适用于左操作数一定属于该类的场景（如比较、赋值）
- `=`、`()`、`[]`、`->` **必须**以成员函数方式重载

#### 非成员函数方式

```cpp
// 两个操作数都作为参数传入，支持对称的隐式类型转换
bool operator<(const MyClass& lhs, const MyClass& rhs);
```

**特点**：
- 左右操作数地位对称，都支持隐式类型转换
- 适用于流运算符（`<<`、`>>`），因为左操作数是流对象，不是自定义类
- 如果需要访问私有成员，需要通过 `friend` 声明

#### 选择原则

| 场景 | 推荐方式 |
|------|----------|
| `=` `()` `[]` `->` | 必须成员函数 |
| `<<` `>>` | 必须非成员函数（左操作数是流） |
| 比较运算符 `==` `<` 等 | 均可，推荐非成员函数（C++20 spaceship 推荐） |
| 对称运算符 `+` `*` 等 | 推荐非成员函数（支持双向隐式转换） |
| 复合赋值 `+=` `-=` 等 | 推荐成员函数 |

---

## 2. 比较运算符重载

### 2.1 六大比较运算符

C++ 定义了六种关系运算符：`==`、`!=`、`<`、`>`、`<=`、`>=`。在实际工程中，通常只需手动实现 `==` 和 `<`，其余运算符可以基于这两个推导出来。

### 2.2 蓝牙协议栈实例：Uuid 的比较运算符

> 文件：`system/types/include/bluetooth/types/uuid.h:113-115`

```cpp
class Uuid final {
public:
  bool operator<(const Uuid& rhs) const;
  bool operator==(const Uuid& rhs) const;
  bool operator!=(const Uuid& rhs) const;

private:
  UUID128Bit uu;  // 内部存储：128位大端序字节数组
};
```

**分析**：

- `operator<` 和 `operator==` 是**基础运算符**，需要独立实现（通常比较内部的 `uu` 数组）
- `operator!=` 可以基于 `operator==` 推导：`return !(*this == rhs)`
- 这三个运算符以**成员函数**方式实现，左操作数是 `*this`

**为什么 Uuid 需要比较运算符？** 在蓝牙协议栈中，UUID 用于标识服务（Service）和特征（Characteristic）。将 Uuid 用作 `std::map` 的 key 时，`std::map` 需要比较操作来维护红黑树的有序性，因此必须提供 `operator<`。

### 2.3 蓝牙协议栈实例：RawAddress 的完整比较运算符族

> 文件：`system/types/include/bluetooth/types/address.h:36-41`

```cpp
class RawAddress final {
public:
  std::array<uint8_t, 6> address;

  bool operator<(const RawAddress& rhs) const { return address < rhs.address; }
  bool operator==(const RawAddress& rhs) const { return address == rhs.address; }
  bool operator>(const RawAddress& rhs) const { return rhs < *this; }
  bool operator<=(const RawAddress& rhs) const { return !(*this > rhs); }
  bool operator>=(const RawAddress& rhs) const { return !(*this < rhs); }
  bool operator!=(const RawAddress& rhs) const { return !(*this == rhs); }
};
```

**逐行解析**：

| 运算符 | 实现 | 策略 |
|--------|------|------|
| `operator<` | `address < rhs.address` | **基础实现**：委托给 `std::array` 的字典序比较 |
| `operator==` | `address == rhs.address` | **基础实现**：委托给 `std::array` 的逐元素相等比较 |
| `operator>` | `rhs < *this` | **推导**：a > b 等价于 b < a |
| `operator<=` | `!(*this > rhs)` | **推导**：a <= b 等价于 !(a > b) |
| `operator>=` | `!(*this < rhs)` | **推导**：a >= b 等价于 !(a < b) |
| `operator!=` | `!(*this == rhs)` | **推导**：a != b 等价于 !(a == b) |

**关键设计要点**：

1. **委托模式**：`RawAddress` 的 `address` 是 `std::array<uint8_t, 6>`，`std::array` 本身已经支持 `operator<` 和 `operator==`，因此 RawAddress 直接委托，无需手写逐字节比较逻辑。

2. **推导模式**：六个运算符中只有 `<` 和 `==` 是"真正"实现的，其余四个通过逻辑推导得出。这保证了**一致性**——不会出现 `a < b` 和 `a >= b` 同时为真的逻辑矛盾。

3. **`address` 是 public 成员**：RawAddress 将 `address` 暴露为 public，这在蓝牙协议栈中是有意为之——许多 C 风格的遗留代码需要直接访问地址字节数组。

**实际用途**：`RawAddress` 表示蓝牙设备地址（如 `12:34:56:ab:cd:ef`）。在协议栈中，它被广泛用作 `std::map<RawAddress, ...>` 的 key，这要求 `operator<` 可用；同时也用作 `std::unordered_map<RawAddress, ...>` 的 key，这要求 `std::hash<RawAddress>` 特化可用（见第 4 节）。

### 2.4 C++20 的太空船运算符 <=>（补充知识）

C++20 引入了三路比较运算符 `<=>`（spaceship operator），编译器可以自动生成全部六个比较运算符：

```cpp
// C++20 方式（自动生成所有比较运算符）
auto operator<=>(const RawAddress&) const = default;
```

蓝牙协议栈中的 `RawAddress` 和 `Uuid` 目前仍采用手动实现的方式，这是为了兼容 C++17 及更早的标准。

---

## 3. 流插入运算符重载 operator<<

### 3.1 为什么必须是非成员函数

流插入运算符 `<<` 的左操作数是 `std::ostream`（如 `std::cout`、`std::ostringstream`），而不是我们自定义的类。因此，我们**无法**在自定义类中将其作为成员函数重载——成员函数的第一个参数隐式为 `this`，类型只能是类本身。

```cpp
// 错误：成员函数方式——左操作数变成了 Uuid，而不是 ostream
class Uuid {
  std::ostream& operator<<(std::ostream& os) const;  // 调用方式：uuid << cout，反直觉！
};

// 正确：非成员函数方式——左操作数是 ostream
std::ostream& operator<<(std::ostream& os, const Uuid& a);  // 调用方式：cout << uuid
```

### 3.2 标准实现模式

```cpp
inline std::ostream& operator<<(std::ostream& os, const YourType& obj) {
  os << obj.ToString();  // 或其他格式化输出
  return os;             // 返回 os 以支持链式调用：cout << a << b << c;
}
```

**要点**：
- 返回 `std::ostream&` 以支持链式调用
- 通常声明为 `inline`（定义在头文件中避免 ODR 违规）
- 如果需要访问私有成员，需配合 `friend` 声明

### 3.3 蓝牙协议栈实例：Uuid 的流插入运算符

> 文件：`system/types/include/bluetooth/types/uuid.h:124-127`

```cpp
inline std::ostream& operator<<(std::ostream& os, const bluetooth::Uuid& a) {
  os << a.ToString();
  return os;
}
```

**分析**：

- `Uuid` 提供了 `ToString()` 公有方法，返回形如 `00001234-0000-1000-8000-00805f9b34fb` 的字符串
- `operator<<` 直接委托给 `ToString()`，无需访问私有成员，因此不需要 `friend`
- `inline` 关键字确保头文件多重包含不会导致链接错误

**使用效果**：

```cpp
bluetooth::Uuid uuid = bluetooth::Uuid::From16Bit(0x1234);
LOG(INFO) << "Service UUID: " << uuid;  // 输出：Service UUID: 00001234-0000-1000-8000-00805f9b34fb
```

在蓝牙协议栈中，日志系统大量使用 `operator<<` 来输出自定义类型。这种模式使得日志代码简洁且类型安全。

---

## 4. std::hash 特化

### 4.1 为什么需要特化

`std::unordered_map` 和 `std::unordered_set` 基于哈希表实现，需要两个东西：
1. **哈希函数**：通过 `std::hash<Key>` 计算键的哈希值
2. **相等比较**：通过 `operator==` 判断键是否相等

标准库已经为 `int`、`std::string` 等内置类型提供了 `std::hash` 特化，但**自定义类型默认没有**。如果要将自定义类型用作 `unordered_map` 的 key，必须提供 `std::hash` 的特化。

```cpp
// 没有特化时，编译错误：
std::unordered_map<RawAddress, DeviceInfo> devices;  // error: std::hash<RawAddress> 未定义

// 提供特化后，可以正常使用：
std::unordered_map<RawAddress, DeviceInfo> devices;  // OK
```

### 4.2 特化语法

```cpp
// 在 std 命名空间中特化（这是标准库允许的少数几种向 std 添加内容的情况之一）
namespace std {
template <>
struct hash<YourType> {
  std::size_t operator()(const YourType& key) const {
    // 计算并返回哈希值
  }
};
}  // namespace std
```

**规则**：
- 只能为**已有类型**添加 `std::hash` 特化，不能发明新的标准库特化
- `operator()` 必须是 `const` 成员函数
- 返回类型是 `std::size_t`
- 对于相同的对象，多次调用必须返回相同的哈希值

### 4.3 蓝牙协议栈实例：Uuid 的 hash 特化

> 文件：`system/types/include/bluetooth/types/uuid.h:133-145`

```cpp
// Custom std::hash specialization so that bluetooth::UUID can be used as a key
// in std::unordered_map.
namespace std {

template <>
struct hash<bluetooth::Uuid> {
  std::size_t operator()(const bluetooth::Uuid& key) const {
    const auto& uuid_bytes = key.To128BitBE();
    std::hash<std::string> hash_fn;
    return hash_fn(
        std::string(reinterpret_cast<const char*>(uuid_bytes.data()), uuid_bytes.size()));
  }
};

}  // namespace std
```

**逐行解析**：

1. `key.To128BitBE()`：获取 UUID 的 128 位大端序字节表示（`std::array<uint8_t, 16>`）
2. `reinterpret_cast<const char*>(uuid_bytes.data())`：将字节数组视为字符数组，以便构造 `std::string`
3. `std::string(...)`：用这 16 字节构造一个 `std::string`（注意：这里不是人类可读字符串，而是原始字节）
4. `hash_fn(...)`：复用 `std::hash<std::string>` 来计算哈希值

**设计思路**：将 UUID 的字节数据转换为 `std::string`，然后复用已有的 `std::hash<std::string>`。这是一种常见的"委托"策略——避免自己实现哈希算法，而是利用标准库中经过充分测试的实现。

### 4.4 蓝牙协议栈实例：RawAddress 的 hash 特化

> 文件：`system/types/include/bluetooth/types/address.h:71-79`

```cpp
template <>
struct std::hash<RawAddress> {
  std::size_t operator()(const RawAddress& val) const {
    static_assert(sizeof(uint64_t) >= RawAddress::kLength);
    uint64_t int_addr = 0;
    memcpy(reinterpret_cast<uint8_t*>(&int_addr), val.address.data(), RawAddress::kLength);
    return std::hash<uint64_t>{}(int_addr);
  }
};
```

**逐行解析**：

1. `static_assert(sizeof(uint64_t) >= RawAddress::kLength)`：编译期断言 `uint64_t`（8字节）能容纳蓝牙地址（6字节）
2. `uint64_t int_addr = 0`：初始化一个 64 位整数（高 2 字节为 0）
3. `memcpy(...)`：将 6 字节蓝牙地址拷贝到 `int_addr` 的低 6 字节
4. `std::hash<uint64_t>{}(int_addr)`：复用 `std::hash<uint64_t>` 计算哈希值

**设计思路**：与 Uuid 的策略类似——委托给标准库的哈希实现。但方法不同：RawAddress 将 6 字节地址映射为 `uint64_t`，而 Uuid 将 16 字节映射为 `std::string`。选择哪种中间类型取决于数据大小和性能考量。

**两种策略对比**：

| 策略 | 适用场景 | 性能 |
|------|----------|------|
| 字节 → `std::string` → hash | 数据较大（如 16 字节 UUID） | 较低（涉及字符串构造和内存分配） |
| 字节 → 整数 → hash | 数据较小，能放入整数类型 | 较高（纯栈操作，无内存分配） |

### 4.5 注意事项

1. **向 `std` 命名空间添加特化是合法的**，但仅限于用户自定义类型的 `std::hash` 特化。不能为标准库类型添加特化。
2. **哈希质量直接影响哈希表性能**。差的哈希函数会导致大量冲突，使 `unordered_map` 退化为链表。
3. **`operator==` 必须与 `std::hash` 一致**：如果 `a == b` 为真，则 `hash(a) == hash(b)` 必须为真。反之不要求。

---

## 5. std::formatter 特化 (C++20)

### 5.1 背景：从 operator<< 到 std::formatter

C++20 之前，自定义类型的格式化输出主要依赖 `operator<<`。C++20 引入了 `<format>` 库和 `std::formatter` 机制，提供了更强大、更类型安全的格式化能力：

```cpp
// C++20 之前：只能通过 operator<< 输出
std::cout << "Address: " << address << std::endl;

// C++20：支持格式化字符串，可以控制宽度、对齐等
std::cout << std::format("Address: {}", address) << std::endl;
std::cout << std::format("Address: {:>20}", address) << std::endl;  // 右对齐，宽度20
```

### 5.2 特化方式一：继承 ostream_formatter（最简方式）

如果自定义类型已经有了 `operator<<`，最简单的方式是继承 `ostream_formatter`，编译器会自动复用 `operator<<` 的逻辑。

### 5.3 蓝牙协议栈实例：Uuid 的 formatter 特化

> 文件：`system/types/include/bluetooth/types/uuid.h:153-156`

```cpp
#if __has_include(<bluetooth/log.h>)

#include <bluetooth/log.h>

namespace std {
template <>
struct formatter<bluetooth::Uuid> : ostream_formatter {};
}  // namespace std

#endif  // __has_include(<bluetooth/log.h>)
```

**分析**：

- `formatter<bluetooth::Uuid> : ostream_formatter`：继承 `ostream_formatter`，自动将 `std::format` 调用转发给已有的 `operator<<`
- 使用 `__has_include` 条件编译：确保只在有 `bluetooth/log.h` 的编译环境中启用，避免在缺少依赖的组件中编译失败
- 这是一种**零成本**的迁移策略——无需重写格式化逻辑，只需一行声明

### 5.4 特化方式二：继承 formatter<std::string> 并自定义 format 函数

当需要完全自定义格式化输出（不依赖 `operator<<`）时，可以继承 `formatter<std::string>` 并重写 `format` 函数。

### 5.5 蓝牙协议栈实例：RawAddress 的 formatter 特化

> 文件：`system/types/include/bluetooth/types/address.h:97-104`

```cpp
namespace std {
template <>
struct formatter<RawAddress> : formatter<std::string> {
  template <class Context>
  typename Context::iterator format(const RawAddress& address, Context& ctx) const {
    std::string repr = address.ToRedactedStringForLogging();
    return std::formatter<std::string>::format(repr, ctx);
  }
};
}  // namespace std
```

**逐行解析**：

1. `formatter<RawAddress> : formatter<std::string>`：继承 `formatter<std::string>`，获得字符串格式化的全部能力（宽度、对齐、填充等）
2. `format(const RawAddress& address, Context& ctx) const`：重写 `format` 函数
3. `address.ToRedactedStringForLogging()`：生成**脱敏**的地址字符串（如 `xx:xx:xx:xx:ab:cd`，前 4 字节被遮蔽）
4. `std::formatter<std::string>::format(repr, ctx)`：将脱敏字符串交给父类格式化

**安全设计亮点**：RawAddress 的 `formatter` 特化使用 `ToRedactedStringForLogging()` 而非 `ToString()`，这意味着在日志和格式化输出中，蓝牙地址会自动脱敏，防止用户隐私泄露。这是蓝牙协议栈中一个重要的安全实践——`operator<<` 也应该遵循同样的脱敏原则。

**两种 formatter 特化方式对比**：

| 方式 | 适用场景 | 代码量 | 灵活性 |
|------|----------|--------|--------|
| 继承 `ostream_formatter` | 已有 `operator<<`，直接复用 | 1 行 | 低（完全依赖 `operator<<`） |
| 继承 `formatter<string>` + 重写 `format` | 需要自定义格式化逻辑 | 数行 | 高（可自由控制输出内容） |

---

## 6. friend 声明

### 6.1 什么是 friend

`friend` 是 C++ 中一种打破访问控制限制的机制。被声明为 `friend` 的函数或类可以访问该类的 `private` 和 `protected` 成员。

```cpp
class MyClass {
private:
  int secret_;

  // 声明外部函数为友元——它可以访问 MyClass 的私有成员
  friend void revealSecret(const MyClass& obj);

  // 声明外部类为友元——该类的所有成员函数都可以访问 MyClass 的私有成员
  friend class TrustedPartner;
};
```

### 6.2 friend 函数 vs friend 类

| 类型 | 语法 | 效果 |
|------|------|------|
| friend 函数 | `friend ReturnType funcName(params);` | 该函数可以访问私有成员 |
| friend 类 | `friend class ClassName;` | 该类的**所有**成员函数都可以访问私有成员 |
| friend 模板类 | `template <typename T> friend class ClassName;` | 该模板类的所有实例化都可以访问私有成员 |

**注意**：`friend` 声明是单向的、不可传递的。如果 A 是 B 的 friend，B 并不自动是 A 的 friend；如果 A 是 B 的 friend，B 是 C 的 friend，A 并不自动是 C 的 friend。

### 6.3 蓝牙协议栈实例：Handler 的 friend 声明

> 文件：`system/gd/os/handler.h:109-114`

```cpp
namespace bluetooth {
namespace os {

class Handler : public common::PostableContext {
public:
  // ...

  template <typename T>
  friend class Queue;

  friend class Alarm;
  friend class RepeatingAlarm;

private:
  std::queue<common::OnceClosure>* tasks_ GUARDED_BY(mutex_);
  std::unique_ptr<Reactor::Event> event_;
  Reactor::Reactable* reactable_ GUARDED_BY(mutex_);
  mutable std::mutex mutex_;
  DelayedTaskQueue* delayed_tasks_ GUARDED_BY(mutex_);
  Alarm* alarm_ GUARDED_BY(mutex_);
};

}  // namespace os
}  // namespace bluetooth
```

**分析**：

Handler 是蓝牙协议栈中消息处理的核心类，它管理着一个任务队列和延迟任务队列。以下三个类被声明为 Handler 的 friend：

1. **`Queue<T>`**（模板友元类）：Queue 需要直接操作 Handler 的内部任务队列 `tasks_`，以便将消息投递到 Handler 中。使用模板友元是因为 Queue 本身是模板类，需要为所有 `T` 类型实例化授予友元权限。

2. **`Alarm`**：定时器类需要访问 Handler 的 `event_` 和 `reactable_` 来注册/注销事件，以及操作 `delayed_tasks_` 来管理延迟任务。

3. **`RepeatingAlarm`**：重复定时器类，与 Alarm 类似，需要访问 Handler 的内部机制来调度周期性任务。

**设计意义**：Handler 将内部实现细节封装为 `private`，但通过 `friend` 为密切协作的类开放"后门"。这种模式在协议栈中很常见——某些类之间存在紧密的协作关系，它们的内部实现相互依赖，但对其他类保持封装。

### 6.4 蓝牙协议栈实例：MutationEntry 的 friend 声明

> 文件：`system/gd/storage/mutation_entry.h:105-106`

```cpp
namespace bluetooth {
namespace storage {

class MutationEntry {
public:
  // ... 静态工厂方法（Set、Remove 等）

private:
  friend class ConfigCache;
  friend class Mutation;

  MutationEntry(EntryType entry_type_param, PropertyType property_type_param,
                std::string section_param, std::string property_param = "",
                std::string value_param = "");

  EntryType entry_type;
  PropertyType property_type;
  std::string section;
  std::string property;
  std::string value;
};

}  // namespace storage
}  // namespace bluetooth
```

**分析**：

MutationEntry 表示配置存储中的一个变更条目（设置属性、删除属性、删除节）。注意它的设计模式：

1. **构造函数是 private 的**：外部无法直接创建 MutationEntry 对象
2. **公有静态工厂方法**（如 `Set()`、`Remove()`）是创建 MutationEntry 的唯一途径
3. **`ConfigCache` 和 `Mutation` 是 friend**：它们可以直接调用私有构造函数

**为什么这样设计？**

- `ConfigCache`（配置缓存）需要直接构造 MutationEntry 来表示内部变更
- `Mutation`（变更集合）需要访问 MutationEntry 的私有成员来执行批量操作
- 其他代码只能通过静态工厂方法创建 MutationEntry，保证了创建路径的可控性

这是一种**受限创建模式**（Bounded Creation Pattern）：通过 `friend` + 私有构造函数，精确控制哪些类可以创建对象。

### 6.5 蓝牙协议栈实例：A2dpCodecConfig 的 friend 声明

> 文件：`system/stack/include/a2dp_codec_api.h:56`

```cpp
class A2dpCodecConfig {
  friend class A2dpCodecs;

public:
  // ... 大量公有方法

private:
  // ... 私有成员
};
```

**分析**：

- `A2dpCodecConfig` 表示单个 A2DP 编解码器的配置（如 SBC、AAC、LDAC 等）
- `A2dpCodecs`（注意复数形式）是编解码器管理器，负责管理所有可用的编解码器
- `A2dpCodecs` 作为 `A2dpCodecConfig` 的 friend，可以直接操作编解码器的内部状态（如修改当前选择的编解码器参数）

这体现了**管理器-被管理对象**的 friend 模式：管理器类需要深入了解被管理对象的内部状态，但被管理对象不希望将这些细节暴露给所有外部代码。

### 6.6 friend 的使用原则

| 原则 | 说明 |
|------|------|
| **最小权限** | 只将真正需要访问私有成员的类/函数声明为 friend |
| **避免过度使用** | 如果可以通过公有接口完成，就不要用 friend |
| **友元关系应反映真实耦合** | friend 类之间应该确实存在紧密的设计耦合 |
| **文档化友元关系** | 在注释中说明为什么需要 friend |

---

## 7. 赋值运算符重载

### 7.1 拷贝赋值运算符 operator=

拷贝赋值运算符控制对象之间的赋值行为：

```cpp
class MyClass {
public:
  MyClass& operator=(const MyClass& rhs) {
    if (this != &rhs) {  // 自赋值检查
      // 释放旧资源
      // 分配新资源
      // 复制数据
    }
    return *this;  // 返回 *this 以支持链式赋值：a = b = c
  }
};
```

### 7.2 移动赋值运算符

C++11 引入了移动语义，移动赋值运算符用于"窃取"资源而非复制：

```cpp
class MyClass {
public:
  MyClass& operator=(MyClass&& rhs) noexcept {
    if (this != &rhs) {
      // 释放当前资源
      // 窃取 rhs 的资源（指针转移等）
      // 将 rhs 置为安全状态
    }
    return *this;
  }
};
```

### 7.3 = default 和 = delete

C++11 引入了两个重要的特殊成员函数控制机制：

#### `= default`：显式使用编译器生成的默认实现

```cpp
class MyClass {
public:
  MyClass& operator=(const MyClass&) = default;  // 使用编译器生成的逐成员拷贝赋值
};
```

适用场景：
- 类的成员都是可简单复制的，但因为有其他自定义的特殊成员函数（如自定义析构函数），编译器不再自动生成默认赋值运算符
- 显式表达"使用默认行为"的设计意图

#### `= delete`：禁止该操作

```cpp
class MyClass {
public:
  MyClass& operator=(const MyClass&) = delete;  // 禁止拷贝赋值
};
```

适用场景：
- 对象语义上不可复制（如表示独占资源的类）
- 单例模式
- 管理不可复制资源的类（如文件句柄、网络连接）

### 7.4 蓝牙协议栈实例：EattExtension 禁止拷贝赋值

> 文件：`system/stack/eatt/eatt.h:109-113`

```cpp
class EattExtension {
public:
  EattExtension();
  EattExtension(const EattExtension&) = delete;
  EattExtension& operator=(const EattExtension&) = delete;

  virtual ~EattExtension();

  static EattExtension* GetInstance() {
    static EattExtension* instance = new EattExtension();
    return instance;
  }

  // ...

private:
  struct impl;
  std::unique_ptr<impl> pimpl_;
};
```

**分析**：

`EattExtension` 同时删除了拷贝构造函数和拷贝赋值运算符，这是**不可复制类**（non-copyable）的标准写法。原因如下：

1. **单例模式**：`EattExtension` 通过 `GetInstance()` 提供全局唯一实例，拷贝一个单例在语义上是错误的
2. **Pimpl 惯用法**：`pimpl_` 是 `std::unique_ptr<impl>`，`unique_ptr` 本身不可复制，因此包含它的类也默认不可复制
3. **资源独占**：EattExtension 管理着 EATT（Enhanced ATT）通道等资源，这些资源不应被多个实例共享

### 7.5 蓝牙协议栈实例：Handler 禁止拷贝赋值

> 文件：`system/gd/os/handler.h:62-63`

```cpp
class Handler : public common::PostableContext {
public:
  explicit Handler(Thread* thread);

  Handler(const Handler&) = delete;
  Handler& operator=(const Handler&) = delete;
```

**分析**：

Handler 同样禁止拷贝，原因类似：
- Handler 与特定 Thread 绑定，管理着该线程上的任务队列
- 拷贝 Handler 会导致两个实例操作同一个任务队列，产生竞态条件
- Handler 持有 `std::unique_ptr` 成员，天然不可复制

### 7.6 Rule of Five / Rule of Zero

C++ 资源管理有两条重要规则：

**Rule of Five**：如果类需要自定义以下任何一个，就应该自定义全部五个：
1. 析构函数
2. 拷贝构造函数
3. 拷贝赋值运算符
4. 移动构造函数
5. 移动赋值运算符

**Rule of Zero**：如果类不需要任何自定义的资源管理，就不要声明任何特殊成员函数，让编译器自动生成。

蓝牙协议栈中的实践：

| 类 | 策略 | 说明 |
|----|------|------|
| `RawAddress` | Rule of Zero | 所有成员都是可简单复制的，无需自定义特殊成员函数 |
| `Uuid` | Rule of Zero | 内部只有 `std::array`，默认行为正确 |
| `EattExtension` | 删除拷贝 | 单例 + unique_ptr，显式删除拷贝操作 |
| `Handler` | 删除拷贝 | 绑定线程资源，显式删除拷贝操作 |

---

## 总结

本教材通过蓝牙协议栈中的真实代码，展示了运算符重载和 friend 机制在实际工程中的应用：

| 机制 | 核心用途 | 协议栈实例 |
|------|----------|------------|
| 比较运算符重载 | 使自定义类型可用作有序容器的 key | `RawAddress`、`Uuid` |
| `operator<<` | 日志和调试输出 | `Uuid` |
| `std::hash` 特化 | 使自定义类型可用作哈希容器的 key | `RawAddress`、`Uuid` |
| `std::formatter` 特化 | C++20 格式化输出 | `RawAddress`（脱敏）、`Uuid` |
| `friend` 类 | 允许紧密协作的类访问私有成员 | `Handler`↔`Queue`/`Alarm`、`MutationEntry`↔`ConfigCache` |
| `operator= = delete` | 禁止拷贝，保护资源独占语义 | `EattExtension`、`Handler` |

这些机制不是孤立的——它们共同构成了 C++ 类型设计的基石。一个设计良好的自定义类型应该像内置类型一样自然地参与比较、哈希、格式化输出等操作，同时通过适当的访问控制保护内部实现细节。
