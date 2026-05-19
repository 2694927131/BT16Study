# 现代 C++ 特性 —— 让代码更安全、更简洁、更强大

> **基于 Android 蓝牙协议栈 (Fluoride) 真实代码的 C++ 教材**
>
> 目标读者：了解基本 C++ 但不熟悉现代 C++ 特性的初学者

---

## 目录

1. [enum class（强类型枚举，C++11）](#1-enum-class强类型枚举c11)
2. [constexpr（常量表达式，C++11/14）](#2-constexpr常量表达式c1114)
3. [auto 关键字（C++11）](#3-auto-关键字c11)
4. [nullptr（C++11）](#4-nullptrc11)
5. [范围 for 循环（C++11）](#5-范围-for-循环c11)
6. [static_assert（编译期断言，C++11）](#6-static_assert编译期断言c11)
7. [if constexpr（编译期条件分支，C++17）](#7-if-constexpr编译期条件分支c17)
8. [[[nodiscard]] 和 [[fallthrough]]（C++17 属性）](#8-nodiscard-和-fallthroughc17-属性)
9. [= delete 和 = default（C++11）](#9-delete-和-defaultc11)
10. [std::optional（C++17）](#10-stdoptionalc17)
11. [std::variant（C++17）](#11-stdvariantc17)

---

## 1. enum class（强类型枚举，C++11）

### 1.1 C 风格 enum 的问题

在传统 C++ 中，`enum` 有几个令人头疼的问题：

```cpp
// 传统 C 风格 enum —— 问题百出
enum Color { RED, GREEN, BLUE };
enum TrafficLight { RED, YELLOW, GREEN };  // 编译错误！RED 和 GREEN 重复定义！

// 问题 1：枚举值会"泄漏"到外部作用域
int x = RED;  // 可以隐式转换为 int，没有任何警告

// 问题 2：不同枚举类型之间可以比较
enum DeviceState { CONNECTED, DISCONNECTED };
Color c = RED;
DeviceState d = CONNECTED;
if (c == d) { ... }  // 编译通过！但语义上毫无意义

// 问题 3：底层类型不确定，大小不可控
enum BigEnum { A = 0, B = 1 };  // 可能是 int（4 字节），浪费空间
```

在蓝牙协议栈中，我们经常需要精确控制枚举的大小（比如只占 1 字节，因为蓝牙协议包对大小非常敏感），而且不同模块的枚举值很容易冲突。C 风格 `enum` 完全无法满足这些需求。

### 1.2 enum class 的基本语法

`enum class`（也叫"强类型枚举"或"限定作用域枚举"）完美解决了上述所有问题：

```cpp
enum class EattChannelState : uint8_t {
    EATT_CHANNEL_PENDING = 0x00,
    EATT_CHANNEL_OPENED,
    EATT_CHANNEL_RECONFIGURING,
};
```

让我们逐个拆解：

| 语法元素 | 含义 |
|---------|------|
| `enum class` | 声明一个强类型枚举（而非传统 enum） |
| `EattChannelState` | 枚举类名 |
| `: uint8_t` | 指定底层类型为 1 字节无符号整数 |
| `EATT_CHANNEL_PENDING = 0x00` | 显式指定第一个值为 0 |
| `EATT_CHANNEL_OPENED` | 自动递增为 1 |
| `EATT_CHANNEL_RECONFIGURING` | 自动递增为 2 |

### 1.3 enum class 的三大优势

**优势 1：作用域隔离——必须用 `枚举类名::枚举值` 访问**

```cpp
// 传统 enum：枚举值直接暴露在外部作用域
enum OldState { PENDING, OPENED };
int s = PENDING;  // 直接使用，容易与其他名字冲突

// enum class：必须通过枚举类名限定
enum class EattChannelState : uint8_t {
    EATT_CHANNEL_PENDING = 0x00,
    EATT_CHANNEL_OPENED,
    EATT_CHANNEL_RECONFIGURING,
};

// 正确用法
EattChannelState state = EattChannelState::EATT_CHANNEL_PENDING;

// 错误用法——编译失败
EattChannelState state = EATT_CHANNEL_PENDING;  // 错误！必须加限定
```

这意味着不同枚举类可以有同名枚举值，互不冲突：

```cpp
enum class EattChannelState : uint8_t {
    EATT_CHANNEL_PENDING = 0x00,
    EATT_CHANNEL_OPENED,
};

enum class L2capState : uint8_t {
    EATT_CHANNEL_PENDING = 0x00,  // 没问题！不会冲突
    EATT_CHANNEL_OPENED,
};
```

**优势 2：不允许隐式转换为整数**

```cpp
EattChannelState state = EattChannelState::EATT_CHANNEL_PENDING;

// 错误！不能隐式转换为 int
int x = state;                    // 编译失败！
if (state == 0) { ... }          // 编译失败！

// 必须显式转换
int x = static_cast<uint8_t>(state);  // 正确：显式转换
```

这防止了意外将枚举值当作整数使用，避免了大量潜在 bug。

**优势 3：精确控制底层类型和大小**

```cpp
// 蓝牙协议中，状态值只需要 1 字节
enum class EattChannelState : uint8_t { ... };     // 1 字节

// L2CAP 结果码需要 2 字节（协议规定 16 位）
enum class tL2CAP_LE_RESULT_CODE : uint16_t { ... };  // 2 字节

// A2DP 编解码器 ID 需要 8 字节
enum class CodecId : uint64_t { ... };              // 8 字节
```

这在蓝牙协议栈中至关重要——协议包的每个字段都有精确的字节数要求，不能多也不能少。

### 1.4 enum class 与整数之间的转换

```cpp
EattChannelState state = EattChannelState::EATT_CHANNEL_OPENED;

// enum class → 整数（显式转换）
uint8_t value = static_cast<uint8_t>(state);  // value == 1

// 整数 → enum class（显式转换）
uint8_t raw = 0x02;
EattChannelState s = static_cast<EattChannelState>(raw);  // EATT_CHANNEL_RECONFIGURING

// 比较操作
if (state == EattChannelState::EATT_CHANNEL_OPENED) {  // 正确
    // 通道已打开
}
```

### 1.5 蓝牙协议栈中的真实示例

**示例 1：EATT 通道状态**（`system/stack/eatt/eatt.h:37-41`）

```cpp
enum class EattChannelState : uint8_t {
    EATT_CHANNEL_PENDING = 0x00,
    EATT_CHANNEL_OPENED,
    EATT_CHANNEL_RECONFIGURING,
};

// 使用示例
void handle_channel(EattChannel* channel) {
    // 检查状态——必须用完整限定名
    if (channel->state_ == EattChannelState::EATT_CHANNEL_PENDING) {
        // 通道正在等待建立
    }

    // 需要传给 C 接口时，转换为整数
    uint8_t state_value = static_cast<uint8_t>(channel->state_);
    btm_send_state_notification(state_value);
}
```

**示例 2：BTM 状态码**（`system/stack/include/btm_status.h`）

```cpp
enum class tBTM_STATUS : uint8_t {
    BTM_SUCCESS = 0,
    BTM_UNKNOWN_ADDR,
    BTM_DEVICE_TIMEOUT,
    BTM_ILLEGAL_VALUE,
    // ... 更多状态码
};

// 使用
tBTM_STATUS result = btm_read_remote_version(bd_addr);
if (result == tBTM_STATUS::BTM_SUCCESS) {
    LOG_INFO("Read remote version success");
}
```

**示例 3：L2CAP LE 结果码**（`system/stack/include/l2cdefs.h`）

```cpp
// 注意底层类型是 uint16_t，因为蓝牙协议规定此字段为 16 位
enum class tL2CAP_LE_RESULT_CODE : uint16_t {
    L2CAP_LE_RESULT_SUCCESS = 0x0000,
    L2CAP_LE_RESULT_UNKNOWN_PSM = 0x0002,
    L2CAP_LE_RESULT_NO_RESOURCES = 0x0004,
    L2CAP_LE_RESULT_INSUFFICIENT_AUTHEN = 0x0005,
    // ...
};
```

**示例 4：A2DP 编解码器 ID**（`system/stack/include/a2dp_constants.h`）

```cpp
// 底层类型 uint64_t，因为编解码器 ID 可能很大
enum class CodecId : uint64_t {
    SBC = 0,
    AAC = 2,
    APTX = 0x00FF,
    LDAC = 0x0100,
    // ...
};
```

### 1.6 小结

| 特性 | C 风格 enum | enum class |
|------|------------|------------|
| 作用域 | 枚举值泄漏到外部 | 必须用 `类名::值` 访问 |
| 隐式转 int | 允许 | 禁止，必须 `static_cast` |
| 指定底层类型 | 不可（C++11 前不可） | 可以 `: uint8_t` 等 |
| 同名枚举值 | 冲突 | 不冲突（不同类名限定） |
| 大小可控 | 不确定 | 精确控制 |

### ☕ Java 类比

C++ 的 `enum class` 与 Java 的 `enum` 都解决了传统枚举的类型安全问题，但设计哲学不同：

| 对比项 | C++ `enum class` | Java `enum` |
|--------|------------------|-------------|
| 本质 | 强类型整数 | 真正的类（继承自 `java.lang.Enum`） |
| 作用域 | 必须用 `类名::值` | 必须用 `类名.值` |
| 隐式转 int | 禁止，需 `static_cast` | 禁止，需 `ordinal()` 或自定义字段 |
| 指定底层类型 | 可以 `: uint8_t` 等 | 不可以（固定为 int 语义） |
| 添加字段/方法 | 不可以（纯枚举） | **可以**（枚举是类） |
| 实现接口 | 不可以 | 可以 |
| 同名枚举值 | 不冲突 | 不冲突 |

**C++ enum class 示例：**

```cpp
enum class EattChannelState : uint8_t {
    EATT_CHANNEL_PENDING = 0x00,
    EATT_CHANNEL_OPENED,
    EATT_CHANNEL_RECONFIGURING,
};
// 使用
EattChannelState s = EattChannelState::EATT_CHANNEL_OPENED;
int val = static_cast<uint8_t>(s);  // 显式转换
```

**Java enum 示例：**

```java
enum EattChannelState {
    PENDING(0x00),
    OPENED(0x01),
    RECONFIGURING(0x02);

    private final int value;

    EattChannelState(int value) { this.value = value; }
    public int getValue() { return value; }
}
// 使用
EattChannelState s = EattChannelState.OPENED;
int val = s.getValue();  // 通过自定义方法获取整数值
```

> **关键区别**：Java 的 `enum` 是真正的类，可以拥有字段、构造函数、方法和实现接口，功能远比 C++ `enum class` 丰富。C++ `enum class` 更轻量，只解决类型安全和大小控制问题。如果 C++ 需要"带方法的枚举"，通常用单独的类 + `static` 方法模拟。

---

## 2. constexpr（常量表达式，C++11/14）

### 2.1 为什么需要 constexpr

在传统 C++ 中，定义常量有两种方式：

```cpp
// 方式 1：宏定义——没有类型检查，调试困难
#define NUM_BYTES_128 16

// 方式 2：const 变量——运行时可能才初始化
const size_t kNumBytes128 = 16;
```

`constexpr` 的出现让常量真正在**编译期**就计算好，而不是等到运行时：

```cpp
// constexpr 变量：编译期就确定值
static constexpr size_t kNumBytes128 = 16;
```

这在蓝牙协议栈中非常重要——UUID 的字节数、HCI 事件掩码等都是编译期就能确定的常量，用 `constexpr` 可以让编译器优化得更好。

### 2.2 constexpr 变量

`constexpr` 变量**必须**在编译期就能计算出值：

```cpp
// 编译期常量
static constexpr size_t kNumBytes128 = 16;    // UUID 128 位的字节数
static constexpr size_t kNumBytes32 = 4;      // UUID 32 位的字节数

// 蓝牙 HCI 的默认事件掩码（64 位）
static constexpr uint64_t kDefaultEventMask = 0x3dbfffffffffffff;

// Handler 停止超时时间
constexpr std::chrono::milliseconds kHandlerStopTimeout = std::chrono::milliseconds(2000);
```

`constexpr` 和 `const` 的区别：

```cpp
int x = 10;
const int ci = x;          // 正确：const 可以用运行时值初始化
constexpr int ce = x;      // 错误！x 是运行时变量，constexpr 要求编译期值

const int ci2 = 42;        // 正确
constexpr int ce2 = 42;    // 正确：42 是编译期常量
```

简单记忆：**`constexpr` 是更严格的 `const`**——它保证值一定在编译期确定。

### 2.3 constexpr 函数

`constexpr` 函数可以在编译期被调用（如果参数都是编译期常量），也可以在运行时被调用：

```cpp
// constexpr 函数：编译期可计算
constexpr size_t BytesToBits(size_t bytes) {
    return bytes * 8;
}

// 编译期调用——结果直接嵌入代码，没有运行时开销
constexpr size_t uuid_bits = BytesToBits(16);  // 编译期算出 128

// 运行时调用——和普通函数一样
size_t runtime_bytes = get_buffer_size();
size_t runtime_bits = BytesToBits(runtime_bytes);  // 运行时计算
```

### 2.4 constexpr 构造函数

C++11 允许构造函数也是 `constexpr` 的，这意味着可以在编译期创建对象：

```cpp
// 蓝牙协议栈中的 UUID 类（system/types/include/bluetooth/types/uuid.h:38-42）
class Uuid {
public:
    using UUID128Bit = std::array<uint8_t, 16>;

    static constexpr size_t kNumBytes128 = 16;
    static constexpr size_t kNumBytes32 = 4;

    // constexpr 构造函数——可以在编译期创建 Uuid 对象
    constexpr Uuid(const UUID128Bit& val) : uu{val} {}

    // constexpr 静态工厂方法
    static constexpr Uuid From128BitBE(const UUID128Bit& uuid) {
        Uuid u(uuid);
        return u;
    }

private:
    UUID128Bit uu;
};

// 编译期创建 UUID 对象
constexpr Uuid::UUID128Bit bluetooth_base = {0x00, 0x00, 0x00, 0x00, /* ... */};
constexpr Uuid my_uuid = Uuid::From128BitBE(bluetooth_base);
```

这在蓝牙协议栈中非常有用——很多标准的 UUID（如各种服务的 UUID）可以在编译期就创建好，不需要运行时初始化。

### 2.5 constexpr 的规则演进

| C++ 版本 | constexpr 函数的限制 |
|----------|-------------------|
| C++11 | 函数体只能有一条 `return` 语句（极其受限） |
| C++14 | 允许局部变量、`if`/`for` 等控制流 |
| C++17 | 允许 `if constexpr`、lambda 等 |
| C++20 | 几乎没有限制，甚至可以 `new`/`delete` |

### 2.6 蓝牙协议栈中的真实示例

**示例 1：UUID 常量**（`system/types/include/bluetooth/types/uuid.h`）

```cpp
class Uuid {
public:
    using UUID128Bit = std::array<uint8_t, 16>;

    static constexpr size_t kNumBytes128 = 16;
    static constexpr size_t kNumBytes32 = 4;
    static constexpr size_t kNumBytes16 = 2;

    constexpr Uuid(const UUID128Bit& val) : uu{val} {}

    static constexpr Uuid From128BitBE(const UUID128Bit& uuid) {
        Uuid u(uuid);
        return u;
    }

private:
    UUID128Bit uu;
};
```

**示例 2：HCI 控制器常量**（`system/gd/hci/controller.h:30-33`）

```cpp
class Controller : public hci::ControllerInterface {
public:
    // 默认事件掩码——编译期常量，直接嵌入代码
    static constexpr uint64_t kDefaultEventMask = 0x3dbfffffffffffff;
    static constexpr uint64_t kDefaultLeEventMask = 0x000000000000001f;

    Controller() = default;
    virtual ~Controller() = default;
};
```

**示例 3：Handler 超时常量**（`system/gd/os/handler.h:35`）

```cpp
// 注意：chrono 类型也可以是 constexpr！
constexpr std::chrono::milliseconds kHandlerStopTimeout = std::chrono::milliseconds(2000);
```

### 2.7 小结

| 特性 | const | constexpr |
|------|-------|-----------|
| 初始化时机 | 运行时或编译期 | **必须**编译期 |
| 编译期优化 | 不保证 | 保证 |
| 函数修饰 | 表示不修改成员 | 可在编译期执行 |
| 构造函数 | 不能修饰 | 可以修饰 |

### ☕ Java 类比

Java **没有**与 `constexpr` 等价的机制。Java 的常量优化由 JIT 编译器在运行时完成，而非源码层面强制编译期计算。

| 对比项 | C++ `constexpr` | Java |
|--------|------------------|------|
| 编译期常量变量 | `constexpr int X = 42;` | `static final int X = 42;`（JVM 可能内联，但不保证） |
| 编译期函数 | `constexpr int square(int x) { return x * x; }` | 无等价。Java 方法总是在运行时执行 |
| 编译期构造对象 | `constexpr Uuid(...)` | 无等价。Java 对象在运行时创建 |
| 编译期断言 | `static_assert` 配合 constexpr | 无等价 |
| 保证编译期求值 | **是**（编译器强制） | 否（`static final` 可能被内联，但不保证） |

**C++ constexpr 示例：**

```cpp
constexpr size_t kNumBytes128 = 16;                    // 编译期常量
constexpr size_t BytesToBits(size_t bytes) {            // 编译期可计算函数
    return bytes * 8;
}
constexpr size_t uuid_bits = BytesToBits(16);           // 编译期算出 128
```

**Java 近似写法：**

```java
static final int NUM_BYTES_128 = 16;                    // 运行时常量，JIT 可能内联
static int bytesToBits(int bytes) { return bytes * 8; } // 普通方法，运行时执行
// 无法强制编译期计算
```

> **为什么 Java 不需要 `constexpr`？** Java 有垃圾回收和 JIT 编译器，运行时性能优化由 JVM 负责。Java 不需要像 C++ 那样在源码层面控制编译期计算，因为 JVM 会在运行时根据实际使用情况做更智能的优化（如内联、逃逸分析等）。

---

## 3. auto 关键字（C++11）

### 3.1 auto 是什么

`auto` 让编译器自动推导变量的类型，你不需要手动写出冗长的类型名：

```cpp
// 不用 auto：类型名又长又烦
std::map<uint16_t, std::unique_ptr<EattChannel>>::iterator iter =
    eatt_channels.find(lcid);

// 用 auto：简洁清晰
auto iter = eatt_channels.find(lcid);
```

`auto` 不是"没有类型"——变量的类型在编译期就已经确定，编译器会根据初始化表达式推导出精确的类型。

### 3.2 auto 的基本用法

```cpp
auto x = 42;              // int
auto pi = 3.14;           // double
auto name = std::string("hello");  // std::string
auto& ref = x;            // int&（引用）
const auto& cref = x;     // const int&（常量引用）
```

### 3.3 auto 与迭代器——最常见的使用场景

在蓝牙协议栈中，容器和迭代器的类型名往往非常长，`auto` 能极大简化代码：

```cpp
// system/stack/eatt/eatt_impl.h:85-90
// 在设备列表中查找包含指定 LCID 的设备
auto iter = find_if(devices_.begin(), devices_.end(),
    [&lcid](const eatt_device& ed) {
        auto it = ed.eatt_channels.find(lcid);
        return it != ed.eatt_channels.end();
    });

// 如果不用 auto，类型是什么？
// std::vector<eatt_device>::iterator iter = ...
// 这还算短的，如果容器是 std::map，迭代器类型更长
```

### 3.4 auto 与 lambda

`auto` 可以用来存储 lambda 表达式（lambda 的类型是编译器内部生成的，你无法手写出来）：

```cpp
// system/gd/os/handler.h:40-44
// 定义一个比较函数对象，用于优先队列的排序
inline auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
    return a.first > b.first;
};

// 如果不用 auto，你需要写成：
// std::function<bool(const DelayedTask&, const DelayedTask&)> compare_task_by_time = ...
// 不仅更长，而且 std::function 有运行时开销！auto 推导出的类型更高效。
```

### 3.5 何时使用 auto

**应该使用 auto 的场景：**

```cpp
// 1. 迭代器类型——太长，且显而易见
auto iter = map.find(key);
for (auto it = vec.begin(); it != vec.end(); ++it) { ... }

// 2. lambda 表达式——类型无法手写
auto callback = [](int x) { return x * 2; };

// 3. 范围 for 循环中的元素
for (const auto& entry : map) { ... }

// 4. new 表达式
auto ptr = std::make_unique<EattChannel>(bda, cid, mtu, rx_mtu);

// 5. 类型显而易见的局部变量
auto addr = p_inq->remote_bd_addr;  // 显然是 RawAddress
```

**不应该使用 auto 的场景：**

```cpp
// 1. 类型不明显，读者无法判断
auto result = do_something();  // result 是什么类型？看不出来！

// 2. 需要特定类型时
auto x = 42;     // int，但如果你需要 size_t 呢？
size_t y = 42;   // 明确指定类型

// 3. 表达式模板等复杂类型可能带来性能差异
auto val = vec1 + vec2;  // 可能是表达式模板，不是你想要的
```

### 3.6 auto 的引用与 const

```cpp
std::map<uint16_t, std::unique_ptr<EattChannel>> channels;

// auto 默认会丢弃引用和 const
auto item = *channels.begin();
// item 是 std::pair<uint16_t, std::unique_ptr<EattChannel>>
// 注意：unique_ptr 不能复制！这会编译错误！

// 正确：用 const auto& 避免复制
for (const auto& item : channels) {
    // item 是 const std::pair<const uint16_t, std::unique_ptr<EattChannel>>&
    // 可以安全使用
}

// 需要修改元素时：用 auto&
for (auto& item : channels) {
    item.second->EattChannelSetState(EattChannelState::EATT_CHANNEL_RECONFIGURING);
}
```

### 3.7 蓝牙协议栈中的真实示例

**示例 1：find_if 中的 auto**（`system/stack/eatt/eatt_impl.h:85-90`）

```cpp
auto iter = find_if(devices_.begin(), devices_.end(), [&lcid](const eatt_device& ed) {
    auto it = ed.eatt_channels.find(lcid);
    return it != ed.eatt_channels.end();
});
if (iter != devices_.end()) {
    // 找到了包含指定 LCID 的设备
    eatt_device* dev = &(*iter);
}
```

**示例 2：lambda 比较器**（`system/gd/os/handler.h:40-44`）

```cpp
inline auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
    return a.first > b.first;
};
// 用于 std::priority_queue 的模板参数
```

**示例 3：简化局部变量**（`system/stack/connection_manager/connection_manager.cc:207`）

```cpp
auto addr = p_inq->remote_bd_addr;
// 等价于 RawAddress addr = p_inq->remote_bd_addr;
// 但更简洁，且如果 remote_bd_addr 的类型改了，这里不用改
```

### 3.8 小结

| 用法 | 示例 | 适用场景 |
|------|------|---------|
| `auto x = ...` | 值类型，会复制 | 简单局部变量 |
| `const auto& x = ...` | 常量引用，不复制 | 遍历容器、避免复制 |
| `auto& x = ...` | 可修改引用 | 需要修改元素 |
| `auto&& x = ...` | 转发引用 | 泛型编程 |

### ☕ Java 类比

Java 10 引入了 `var` 关键字，与 C++ 的 `auto` 类似，都是让编译器推导变量类型。

| 对比项 | C++ `auto` | Java `var` |
|--------|------------|------------|
| 引入版本 | C++11 (2011) | Java 10 (2018) |
| 推导时机 | 编译期 | 编译期 |
| 可用于成员变量 | 否（仅局部变量） | 否（仅局部变量） |
| 可用于方法参数 | 否（泛型 Lambda 除外） | 否 |
| 可用于方法返回值 | 否（C++14 可用 `auto` 返回） | 否 |
| 引用语义 | `auto&` / `const auto&` 区分 | 无（Java 引用类型天然是引用） |
| 值类型 | `auto x = 42;` → `int` | `var x = 42;` → `int`（基本类型） |
| 复杂类型推导 | `auto it = map.find(key);` | `var it = map.get(key);` |

**C++ auto 示例：**

```cpp
auto iter = eatt_channels.find(lcid);  // 推导为 map::iterator
auto& channel = iter->second;          // 引用，可修改
const auto& entry = *iter;             // 常量引用，只读
```

**Java var 示例：**

```java
var channels = new HashMap<Integer, EattChannel>();  // 推导为 HashMap<Integer, EattChannel>
var channel = channels.get(5);                       // 推导为 EattChannel（天然是引用）
// Java 无需 const auto&，因为引用类型天然不复制对象
```

> **关键区别**：C++ 的 `auto` 需要配合 `&` 和 `const` 来控制值/引用语义，因为 C++ 有值语义和引用语义之分。Java 的 `var` 只有引用语义（对于对象类型），不需要这些修饰符。

---

## 4. nullptr（C++11）

### 4.1 NULL 和 0 的问题

在 C++11 之前，空指针用 `NULL` 或 `0` 表示，但它们都有问题：

```cpp
// NULL 的定义因编译器而异
#define NULL 0          // 有些编译器
#define NULL ((void*)0) // 有些编译器

// 问题：函数重载时产生歧义
void connect(RawAddress* addr);   // 重载 1：指针版本
void connect(int timeout);        // 重载 2：整数版本

connect(NULL);   // 调用哪个？在 C++ 中，NULL 是 0，所以调用 connect(int)！
connect(0);      // 同样调用 connect(int)！
```

这显然不是我们想要的——`NULL` 的本意是"空指针"，但它实际上是个整数 `0`。

### 4.2 nullptr 的解决方案

`nullptr` 是 C++11 引入的空指针常量，它的类型是 `std::nullptr_t`，可以隐式转换为任何指针类型，但**不会**转换为整数类型：

```cpp
void connect(RawAddress* addr);   // 重载 1
void connect(int timeout);        // 重载 2

connect(nullptr);  // 正确！调用 connect(RawAddress*)
connect(NULL);     // 错误/歧义！可能调用 connect(int)
connect(0);        // 调用 connect(int)
```

### 4.3 nullptr 的类型安全

```cpp
int* p1 = nullptr;          // 正确：nullptr 可以转换为任何指针类型
int* p2 = NULL;             // 可能正确（取决于 NULL 的定义）
int  i1 = nullptr;          // 错误！nullptr 不能转换为整数
int  i2 = NULL;             // 可能正确（NULL 可能是 0）

// nullptr 有自己的类型
std::nullptr_t np = nullptr;  // 正确
```

### 4.4 在模板中的优势

```cpp
// 模板中 NULL 的问题
template<typename T>
void set_value(T arg) {
    // 如果 T 推导为 int（当传入 NULL 时），下面的赋值会出错
    int* ptr = arg;  // 错误！int 不能赋值给 int*
}

set_value(NULL);     // T 推导为 int，编译错误
set_value(nullptr);  // T 推导为 std::nullptr_t，可以赋值给任何指针
```

### 4.5 蓝牙协议栈中的真实示例

在蓝牙协议栈中，你可以看到新旧风格混用的情况——这正是历史遗留代码的典型特征：

```cpp
// system/stack/eatt/eatt.h
// 新代码使用 nullptr
EattChannel* FindChannel(uint16_t lcid);
// 内部实现中：
if (channel == nullptr) {
    return nullptr;
}

// 旧代码仍然使用 NULL
if (p_dev_rec == NULL) {
    // 旧风格
}
```

在编写新代码时，**始终使用 `nullptr`**，不要使用 `NULL` 或 `0` 来表示空指针。

### 4.6 小结

| 特性 | NULL / 0 | nullptr |
|------|----------|---------|
| 类型 | int 或 void* | std::nullptr_t |
| 重载歧义 | 有 | 无 |
| 转换为整数 | 可以 | 不可以 |
| 转换为指针 | 隐式 | 隐式 |
| 模板安全 | 不安全 | 安全 |

### ☕ Java 类比

Java 的 `null` 与 C++ 的 `nullptr` 在概念上相似，但类型系统差异很大：

| 对比项 | C++ `nullptr` | Java `null` |
|--------|---------------|-------------|
| 类型 | `std::nullptr_t`（独立类型） | 无独立类型，是所有引用类型的特殊值 |
| 可赋给整型 | 不可以 | 不可以 |
| 可赋给指针/引用 | 可以 | 可以（任何引用类型） |
| 重载歧义 | 无（`nullptr_t` 不会与 `int` 混淆） | 无（Java 无指针/整型重载歧义） |
| 成员访问 | `nullptr->method()` → 未定义行为 | `null.method()` → `NullPointerException` |
| 模板/泛型安全 | 安全（`nullptr_t` 不会推导为 `int`） | 安全（`null` 只能赋给引用类型） |

**C++ nullptr 示例：**

```cpp
void connect(RawAddress* addr);   // 重载 1
void connect(int timeout);        // 重载 2
connect(nullptr);  // 调用重载 1，无歧义
```

**Java null 示例：**

```java
// Java 没有指针与整型的重载歧义问题
void connect(RawAddress addr) { ... }  // 只有一种引用参数
connect(null);  // 调用 connect(RawAddress)，无歧义
// 如果 addr 为 null，调用 addr.method() 会抛 NullPointerException
```

> **关键区别**：C++ 需要 `nullptr` 来解决 `NULL`/`0` 在函数重载中的歧义问题。Java 没有这个问题，因为 Java 的引用类型和基本类型是完全不同的类别，`null` 只能赋给引用类型。

---

## 5. 范围 for 循环（C++11）

### 5.1 传统 for 循环的痛苦

在 C++11 之前，遍历容器的代码非常冗长：

```cpp
// 传统方式 1：下标遍历（只适用于随机访问容器）
for (size_t i = 0; i < connecting_cids.size(); i++) {
    uint16_t cid = connecting_cids[i];
    // 使用 cid ...
}

// 传统方式 2：迭代器遍历（适用于所有容器，但很冗长）
for (std::map<uint16_t, std::unique_ptr<EattChannel>>::iterator it =
         eatt_dev->eatt_channels.begin();
     it != eatt_dev->eatt_channels.end(); ++it) {
    it->second->EattChannelSetState(EattChannelState::EATT_CHANNEL_RECONFIGURING);
}
```

### 5.2 范围 for 循环的语法

C++11 引入了范围 for 循环（range-based for），让遍历变得极其简洁：

```cpp
// 基本语法
for (声明 : 容器) {
    // 循环体
}

// 三种常用形式
for (auto item : container) { ... }          // 复制每个元素
for (auto& item : container) { ... }         // 引用每个元素（可修改）
for (const auto& item : container) { ... }   // 常量引用（只读，不复制）
```

### 5.3 读取元素：`const auto&`

当你只需要读取元素，不需要修改时，使用 `const auto&`：

```cpp
// system/stack/connection_manager/connection_manager.cc:136
// 遍历后台连接设备列表，只读
for (const auto& entry : bgconn_dev) {
    // entry 是 const 引用，不能修改
    LOG_INFO("Device: %s", entry.first.ToString().c_str());
}
```

**为什么用 `const auto&` 而不是 `auto`？**

```cpp
std::vector<std::string> names = {"Alice", "Bob", "Charlie"};

// auto：每次循环都会复制一个 string，浪费！
for (auto name : names) {
    // name 是副本，修改不影响原容器
}

// const auto&：零复制，高效
for (const auto& name : names) {
    // name 是原元素的引用，不复制
}
```

### 5.4 修改元素：`auto&`

当你需要修改容器中的元素时，使用 `auto&`：

```cpp
// system/stack/eatt/eatt_impl.h:842-844
// 将所有 EATT 通道设置为重配置状态
for (auto& channel : eatt_dev->eatt_channels) {
    // channel 是引用，可以修改
    channel.second->EattChannelSetState(EattChannelState::EATT_CHANNEL_RECONFIGURING);
}
```

注意：`eatt_channels` 是 `std::map`，所以 `channel` 的类型是 `std::pair<const uint16_t, std::unique_ptr<EattChannel>>&`。`channel.first` 是 CID（不可修改，因为 map 的 key 是 const），`channel.second` 是指向通道对象的智能指针（可以修改通道对象的状态）。

### 5.5 简单值类型：直接 `auto`

当元素是简单类型（如整数），复制代价很小时，可以直接用 `auto`：

```cpp
// system/stack/eatt/eatt_impl.h:575
// connecting_cids 是 std::vector<uint16_t>
for (uint16_t cid : connecting_cids) {
    // uint16_t 只有 2 字节，复制代价极小
    // 用 const auto& 也行，但没必要
    EattChannel* channel = FindChannel(cid);
    if (channel != nullptr) {
        channel->EattChannelSetState(EattChannelState::EATT_CHANNEL_RECONFIGURING);
    }
}
```

### 5.6 范围 for 循环的工作原理

范围 for 循环本质上是迭代器循环的语法糖。编译器会将：

```cpp
for (const auto& item : container) {
    // 使用 item
}
```

展开为：

```cpp
{
    auto __begin = container.begin();
    auto __end = container.end();
    for (; __begin != __end; ++__begin) {
        const auto& item = *__begin;
        // 使用 item
    }
}
```

这意味着任何有 `begin()` 和 `end()` 方法的类型都可以用范围 for 循环，包括：
- `std::vector`、`std::list`、`std::map`、`std::set` 等标准容器
- `std::array`
- 原生数组（如 `int arr[10]`）
- 自定义容器（只要提供 `begin()`/`end()`）

### 5.7 蓝牙协议栈中的真实示例

**示例 1：修改 map 中的元素**（`system/stack/eatt/eatt_impl.h:842-844`）

```cpp
for (auto& channel : eatt_dev->eatt_channels) {
    channel.second->EattChannelSetState(EattChannelState::EATT_CHANNEL_RECONFIGURING);
}
```

**示例 2：遍历 vector 中的简单值**（`system/stack/eatt/eatt_impl.h:575`）

```cpp
for (uint16_t cid : connecting_cids) {
    // 处理每个正在连接的 CID
}
```

**示例 3：只读遍历 map**（`system/stack/connection_manager/connection_manager.cc:136`）

```cpp
for (const auto& entry : bgconn_dev) {
    // entry.first: 设备地址
    // entry.second: 连接参数
    LOG_INFO("Background connection to %s", entry.first.ToString().c_str());
}
```

### 5.8 小结

| 形式 | 用途 | 是否复制 | 是否可修改 |
|------|------|---------|-----------|
| `for (auto x : c)` | 简单值类型 | 是 | 修改副本，不影响原容器 |
| `for (auto& x : c)` | 需要修改元素 | 否 | 是 |
| `for (const auto& x : c)` | 只读遍历 | 否 | 否 |

**最佳实践**：默认使用 `const auto&`，需要修改时用 `auto&`，简单值类型可以用 `auto`。

### ☕ Java 类比

C++ 的范围 for 循环与 Java 的 for-each 循环功能相同，但 C++ 需要显式控制引用语义：

| 对比项 | C++ 范围 for | Java for-each |
|--------|-------------|---------------|
| 语法 | `for (const auto& x : container)` | `for (var x : container)` |
| 引用/值控制 | `auto` / `auto&` / `const auto&` | 无需控制（引用类型天然是引用） |
| 修改元素 | `for (auto& x : container)` | `for (var x : list) { x.set...() }` |
| 遍历 map | `for (const auto& [k, v] : map)` (C++17) | `for (var entry : map.entrySet())` |
| 可遍历数组 | 是（原生数组也支持） | 是 |
| 迭代时删除 | 不安全（需用迭代器） | 不安全（需用 `Iterator.remove()`） |

**C++ 范围 for 示例：**

```cpp
// 只读遍历
for (const auto& entry : bgconn_dev) {
    LOG_INFO("Device: %s", entry.first.ToString().c_str());
}
// 修改元素
for (auto& channel : eatt_channels) {
    channel.second->SetState(RECONFIGURING);
}
```

**Java for-each 示例：**

```java
// 只读遍历
for (var entry : bgconnDev.entrySet()) {
    Log.info("Device: " + entry.getKey());
}
// 修改元素（引用类型，直接修改即可）
for (var channel : channels.values()) {
    channel.setState(State.RECONFIGURING);
}
```

> **关键区别**：C++ 需要用 `const auto&` 避免不必要的拷贝，用 `auto&` 才能修改元素。Java 的 for-each 对引用类型天然不复制对象，也不需要 `const` 修饰。

---

## 6. static_assert（编译期断言，C++11）

### 6.1 运行时断言 vs 编译期断言

你可能已经熟悉 `assert()`：

```cpp
#include <cassert>

void process(uint8_t* data, size_t len) {
    assert(len >= 6);  // 运行时检查：如果 len < 6，程序终止
    // ...
}
```

`assert()` 的问题在于：它只在**运行时**检查，如果这段代码没有被执行到，错误就不会被发现。

`static_assert` 在**编译期**检查条件——如果条件不满足，**编译直接失败**，错误根本不可能进入运行时：

```cpp
static_assert(sizeof(RawAddress) == 6, "RawAddress must be 6 bytes long!");
// 如果 RawAddress 不是 6 字节，编译失败，错误信息是 "RawAddress must be 6 bytes long!"
```

### 6.2 static_assert 的语法

```cpp
static_assert(常量表达式, 错误信息);

// C++17 中错误信息可以省略
static_assert(常量表达式);  // C++17
```

- **常量表达式**：必须是编译期可计算的布尔表达式
- **错误信息**：字符串字面量，编译失败时显示

### 6.3 典型用途

**用途 1：检查类型大小**

在蓝牙协议栈中，协议包的结构体大小必须精确——蓝牙规范规定了每个字段占多少字节，差一个字节都不行：

```cpp
// system/types/src/address.cc
// 蓝牙设备地址必须是 6 字节（48 位 MAC 地址）
static_assert(sizeof(RawAddress) == 6, "RawAddress must be 6 bytes long!");
```

如果有人修改了 `RawAddress` 的定义导致大小不再是 6 字节，编译时就会报错，而不是等到运行时才发现数据包格式错误。

**用途 2：检查类型特性**

```cpp
// system/types/src/uuid.cc
// Uuid 必须是 trivial 类型（可以用 memcpy 复制，没有虚函数等）
static_assert(std::is_trivial<Uuid>(), "Uuid must be trivial!");
```

`std::is_trivial<T>()` 是一个类型特征（type trait），检查类型 `T` 是否是"平凡类型"。平凡类型：
- 可以用 `memcpy` 安全复制
- 可以用 `memset` 清零
- 没有虚函数、虚基类
- 构造/析构/赋值都是默认的

在蓝牙协议栈中，很多数据结构需要直接序列化为字节流发送，所以必须是平凡类型。

**用途 3：检查平台相关常量**

```cpp
// 确保 int 是 4 字节（蓝牙协议栈的假设）
static_assert(sizeof(int) == 4, "int must be 4 bytes on this platform!");

// 确保指针大小符合预期
static_assert(sizeof(void*) == 4 || sizeof(void*) == 8, "Unsupported pointer size!");
```

### 6.4 static_assert 与模板

`static_assert` 在模板中特别有用，可以在编译期检查模板参数是否满足要求：

```cpp
template<typename T>
void serialize(const T& obj, uint8_t* buffer) {
    // T 必须是平凡类型才能安全地 memcpy
    static_assert(std::is_trivial<T>(), "T must be trivial for serialization!");
    memcpy(buffer, &obj, sizeof(T));
}
```

### 6.5 蓝牙协议栈中的真实示例

**示例 1：地址大小检查**（`system/types/src/address.cc`）

```cpp
// 蓝牙 MAC 地址必须是 6 字节
static_assert(sizeof(RawAddress) == 6, "RawAddress must be 6 bytes long!");
static_assert(sizeof(RawAddress) == BD_ADDR_LEN, "RawAddress must be same size as BD_ADDR_LEN");
```

**示例 2：UUID 类型检查**（`system/types/src/uuid.cc`）

```cpp
// Uuid 必须是平凡类型，因为需要直接序列化
static_assert(std::is_trivial<Uuid>(), "Uuid must be trivial!");
// 确保 Uuid 的大小是 16 字节（128 位 UUID）
static_assert(sizeof(Uuid) == 16, "Uuid must be 16 bytes long!");
```

### 6.6 小结

| 特性 | assert() | static_assert |
|------|----------|---------------|
| 检查时机 | 运行时 | 编译期 |
| 条件类型 | 任意布尔表达式 | 常量表达式 |
| 生产代码 | 可通过 NDEBUG 禁用 | 始终生效 |
| 开销 | 运行时开销 | 零运行时开销 |
| 错误发现 | 迟（运行时） | 早（编译时） |

### ☕ Java 类比

Java **没有**与 `static_assert` 等价的机制。Java 无法在编译期对类型大小、布局等属性进行断言。

| 对比项 | C++ `static_assert` | Java |
|--------|---------------------|------|
| 编译期断言 | `static_assert(sizeof(X) == 6, "...")` | 无等价 |
| 运行时断言 | `assert(condition);` | `assert condition;`（需 `-ea` 启用） |
| 检查类型大小 | 可以（`sizeof`） | 不可以（Java 不暴露对象大小） |
| 检查类型特性 | 可以（`std::is_trivial<T>`） | 不可以（无等价类型特征） |
| 自定义编译期检查 | 可以 | 无等价 |

**C++ static_assert 示例：**

```cpp
static_assert(sizeof(RawAddress) == 6, "RawAddress must be 6 bytes!");
static_assert(std::is_trivial<Uuid>(), "Uuid must be trivial!");
```

**Java 的替代方案：**

```java
// Java 无法在编译期检查对象大小或类型特性
// 只能在运行时用 assert 或手动检查：
assert rawAddress.getBytes().length == 6 : "Address must be 6 bytes";
// 注意：Java 的 assert 默认禁用，需要 -ea 标志才能生效
```

> **为什么 Java 不需要 `static_assert`？** Java 运行在 JVM 上，对象布局由 JVM 管理，开发者无法也不需要控制类型大小。Java 也没有模板元编程的需求，因此编译期断言在 Java 中没有使用场景。

---

## 7. if constexpr（编译期条件分支，C++17）

### 7.1 运行时 if vs 编译期 if

普通的 `if` 语句在运行时判断条件，两个分支都会被编译：

```cpp
// 普通 if：两个分支都会编译
template<typename T>
void process(T value) {
    if (std::is_same_v<T, int>) {
        // 即使 T 是 string，这行也会被编译检查
        int x = value + 1;  // 如果 T 是 string，编译错误！
    } else {
        // 即使 T 是 int，这行也会被编译检查
        std::string s = value + " world";  // 如果 T 是 int，编译错误！
    }
}
```

`if constexpr` 在**编译期**判断条件，**不满足条件的分支根本不会被编译**：

```cpp
// if constexpr：只有满足条件的分支会被编译
template<typename T>
void process(T value) {
    if constexpr (std::is_same_v<T, int>) {
        int x = value + 1;  // T 是 int 时才编译这行
    } else {
        std::string s = value + " world";  // T 不是 int 时才编译这行
    }
}

process(42);            // 正确：只编译 int 分支
process(std::string("hello"));  // 正确：只编译 string 分支
```

### 7.2 if constexpr 的语法

```cpp
if constexpr (编译期常量表达式) {
    // 条件为真时编译的代码
} else {
    // 条件为假时编译的代码（不会被编译）
}
```

注意：`if constexpr` 的条件必须是编译期常量表达式，通常是：
- `std::is_same_v<T, U>` —— 类型是否相同
- `std::is_integral_v<T>` —— 是否是整数类型
- `std::is_pointer_v<T>` —— 是否是指针类型
- 其他 `std::is_*` 类型特征
- `sizeof(T) == N` —— 类型大小判断

### 7.3 与模板结合的威力

`if constexpr` 最大的用处是在模板中根据类型选择不同的代码路径：

```cpp
// system/main/shim/acl.cc
// 根据连接角色类型选择不同的处理逻辑
template<typename T>
void handle_acl_data(T data) {
    if constexpr (std::is_same_v<T, hci::acl_manager::DataAsPeripheral>) {
        // 作为从设备接收数据
        LOG_DEBUG("Received data as peripheral");
    } else if constexpr (std::is_same_v<T, hci::acl_manager::DataAsCentral>) {
        // 作为主设备接收数据
        LOG_DEBUG("Received data as central");
    }
}
```

如果没有 `if constexpr`，你需要用函数重载或特化来实现，代码会复杂得多。

### 7.4 另一个真实示例

```cpp
// system/gd/hci/le_address_manager.cc
// 根据命令类型选择不同的序列化方式
template<typename T>
void send_command(T command) {
    if constexpr (std::is_same_v<T, UpdateIRKCommand>) {
        // IRK 更新命令的序列化
        serialize_irk_command(command);
    } else if constexpr (std::is_same_v<T, SetRandomAddressCommand>) {
        // 设置随机地址命令的序列化
        serialize_random_address_command(command);
    }
}
```

### 7.5 if constexpr vs 函数重载

同样的功能可以用函数重载实现：

```cpp
// 方式 1：if constexpr（推荐——代码集中在一个函数）
template<typename T>
void handle(T data) {
    if constexpr (std::is_same_v<T, int>) {
        // 处理 int
    } else {
        // 处理其他类型
    }
}

// 方式 2：函数重载（代码分散在多个函数）
void handle(int data) { /* 处理 int */ }
template<typename T>
void handle(T data) { /* 处理其他类型 */ }
```

`if constexpr` 的优势在于：所有逻辑集中在一个函数中，更容易阅读和维护。当分支逻辑共享大量公共代码时尤其方便。

### 7.6 注意事项

```cpp
// if constexpr 不会消除外部依赖
template<typename T>
void foo() {
    if constexpr (std::is_same_v<T, int>) {
        bar_for_int();  // 即使 T 不是 int，bar_for_int 也必须声明
    }
}

// if constexpr 只在模板中有效
void regular_function() {
    if constexpr (true) { ... }  // 可以，但没什么意义——普通函数中用普通 if 就行
}
```

### 7.7 小结

| 特性 | 普通 if | if constexpr |
|------|---------|-------------|
| 判断时机 | 运行时 | 编译期 |
| 分支编译 | 所有分支都编译 | 只编译满足条件的分支 |
| 条件类型 | 任意布尔表达式 | 编译期常量表达式 |
| 典型用途 | 运行时逻辑分支 | 模板中根据类型选择代码路径 |

### ☕ Java 类比

Java **没有**与 `if constexpr` 等价的机制。Java 的泛型使用类型擦除，不存在"根据类型选择不同代码路径"的编译期分支需求。

| 对比项 | C++ `if constexpr` | Java |
|--------|---------------------|------|
| 编译期条件分支 | `if constexpr (std::is_same_v<T, int>)` | 无等价 |
| 不满足条件的分支 | 不编译（可以包含无效代码） | 必须通过编译 |
| 类型特征判断 | `std::is_same_v`, `std::is_integral_v` 等 | `instanceof`（运行时） |
| 替代方案 | — | 方法重载、访问者模式、`instanceof` |

**C++ if constexpr 示例：**

```cpp
template<typename T>
void process(T value) {
    if constexpr (std::is_same_v<T, int>) {
        int x = value + 1;  // T 是 int 时才编译
    } else {
        std::string s = value + " world";  // T 不是 int 时才编译
    }
}
```

**Java 的替代方案：**

```java
// 方式 1：方法重载（编译期选择，最常用）
void process(int value) { int x = value + 1; }
void process(String value) { String s = value + " world"; }

// 方式 2：运行时 instanceof 检查
void process(Object value) {
    if (value instanceof Integer i) {
        int x = i + 1;
    } else if (value instanceof String s) {
        String result = s + " world";
    }
}
```

> **为什么 Java 不需要 `if constexpr`？** C++ 模板在编译期实例化，不同类型可能需要完全不同的代码路径，`if constexpr` 让这些路径互不干扰。Java 的泛型使用类型擦除，所有类型共享同一份字节码，不需要编译期分支。Java 用方法重载实现类似效果。

---

## 8. [[nodiscard]] 和 [[fallthrough]]（C++17 属性）

### 8.1 C++ 属性简介

C++11 引入了属性（attribute）的通用语法 `[[...]]`，用来给编译器提供额外的信息。C++17 标准化了两个常用属性：`[[nodiscard]]` 和 `[[fallthrough]]`。

### 8.2 [[nodiscard]]——不要忽略返回值

有些函数的返回值非常重要，忽略它很可能是一个 bug。`[[nodiscard]]` 告诉编译器：如果调用者忽略了返回值，就发出警告。

```cpp
// 没有 [[nodiscard]] 的问题
bool BTM_SecAddRmtNameNotifyCallback(tBTM_RMT_NAME_CALLBACK* p_callback);
// 调用者可能写成：
BTM_SecAddRmtNameNotifyCallback(my_callback);  // 忘记检查返回值！
// 如果注册失败，程序不会报错，但回调永远不会被调用——非常难调试

// 加上 [[nodiscard]]
[[nodiscard]] bool BTM_SecAddRmtNameNotifyCallback(tBTM_RMT_NAME_CALLBACK* p_callback);
// 调用者如果忽略返回值，编译器会警告：
// warning: ignoring return value of function declared with 'nodiscard' attribute
```

**什么时候应该用 `[[nodiscard]]`？**

- 函数返回错误码，忽略错误可能导致严重问题
- 函数返回新创建的资源（如分配的内存），忽略会导致泄漏
- 函数返回的状态信息对后续逻辑至关重要

```cpp
// 典型场景 1：错误码
[[nodiscard]] bool Connect(const RawAddress& bd_addr);
// 忽略返回值意味着不知道连接是否成功

// 典型场景 2：资源获取
[[nodiscard]] int OpenFile(const char* path);
// 忽略返回值意味着不知道文件是否打开成功

// 典型场景 3：查询结果
[[nodiscard]] bool IsConnected() const;
// 忽略返回值毫无意义
```

### 8.3 蓝牙协议栈中的 [[nodiscard]] 示例

**示例 1：远程名称通知回调注册**（`system/stack/rnr/remote_name_request.h`）

```cpp
[[nodiscard]] bool BTM_SecAddRmtNameNotifyCallback(tBTM_RMT_NAME_CALLBACK* p_callback);
[[nodiscard]] bool BTM_SecDeleteRmtNameNotifyCallback(tBTM_RMT_NAME_CALLBACK* p_callback);
```

注册和删除回调都可能失败，调用者必须检查返回值。

**示例 2：L2CAP 接口中的大量 [[nodiscard]]**（`system/stack/l2cap/l2cap_api.cc`）

```cpp
[[nodiscard]] bool L2CA_Register(uint16_t psm, const tL2CAP_APPL_INFO& p_cb_info);
[[nodiscard]] uint16_t L2CA_ConnectReq(uint16_t psm, const RawAddress& p_bd_addr);
[[nodiscard]] bool L2CA_DisconnectReq(uint16_t cid);
// ... 更多函数
```

L2CAP 是蓝牙的核心协议层，几乎每个操作都可能失败，所以返回值都很重要。

### 8.4 [[fallthrough]]——switch 中故意穿透

在 `switch` 语句中，如果一个 `case` 没有 `break`，执行会"穿透"到下一个 `case`。这通常是 bug，所以编译器会发出警告。但有时我们确实想穿透，这时用 `[[fallthrough]]` 告诉编译器"我是故意的"：

```cpp
// system/stack/rfcomm/rfc_mx_fsm.cc
switch (event) {
    case RFC_MX_EVENT_START_REQ:
        // 处理开始请求
        rfc_mx_sm_state_idle(exec_cb, p_mcb, event, data);
        [[fallthrough]];  // 故意穿透到下一个 case

    case RFC_MX_EVENT_SABME:
        // 处理 SABME 帧
        rfc_mx_sm_sabme(exec_cb, p_mcb, event, data);
        break;

    default:
        LOG_WARN("Unexpected event: %d", event);
        break;
}
```

没有 `[[fallthrough]]`，编译器可能会警告：
```
warning: this statement may fall through [-Wimplicit-fallthrough]
```

加上 `[[fallthrough]]` 后，编译器知道这是有意为之，不再警告。

### 8.5 [[fallthrough]] 的使用场景

```cpp
// 场景 1：多个 case 共享同一段处理代码
switch (status) {
    case tBTM_STATUS::BTM_SUCCESS:
        handle_success();
        break;

    case tBTM_STATUS::BTM_UNKNOWN_ADDR:
    case tBTM_STATUS::BTM_DEVICE_TIMEOUT:
        // 两种错误共享同一段处理代码
        // 这里不需要 [[fallthrough]]，因为 case 之间没有代码
        handle_connection_error();
        break;
}

// 场景 2：一个 case 处理完后，继续执行下一个 case 的逻辑
switch (state) {
    case State::CONNECTING:
        setup_connection();
        [[fallthrough]];  // 连接建立后，继续执行 CONNECTED 的逻辑

    case State::CONNECTED:
        start_data_transfer();
        break;
}
```

### 8.6 其他 C++ 属性

C++ 标准还定义了其他属性，了解即可：

| 属性 | C++ 版本 | 用途 |
|------|---------|------|
| `[[noreturn]]` | C++11 | 函数不会返回（如 `exit()`） |
| `[[deprecated]]` | C++14 | 标记已弃用的实体 |
| `[[nodiscard]]` | C++17 | 忽略返回值时警告 |
| `[[fallthrough]]` | C++17 | switch 穿透时抑制警告 |
| `[[maybe_unused]]` | C++17 | 抑制未使用变量的警告 |
| `[[likely]]` / `[[unlikely]]` | C++20 | 提示分支预测 |

### 8.7 小结

| 属性 | 作用 | 典型场景 |
|------|------|---------|
| `[[nodiscard]]` | 忽略返回值时编译器警告 | 错误码、资源获取、重要查询结果 |
| `[[fallthrough]]` | 抑制 switch 穿透警告 | 故意让 case 穿透到下一个 |

### ☕ Java 类比

Java **没有**与 `[[nodiscard]]` 和 `[[fallthrough]]` 等价的机制。

| 对比项 | C++ 属性 | Java |
|--------|----------|------|
| 忽略返回值警告 | `[[nodiscard]]` | 无等价（IDE 可能警告，但非语言特性） |
| switch 穿透警告 | `[[fallthrough]]` | 无等价（Java 允许穿透，不警告） |
| 标记已弃用 | `[[deprecated]]` | `@Deprecated` 注解 |
| 标记不返回 | `[[noreturn]]` | 无等价 |
| 抑制未使用警告 | `[[maybe_unused]]` | 无等价（IDE 可能警告） |

**C++ [[nodiscard]] 示例：**

```cpp
[[nodiscard]] bool Connect(const RawAddress& addr);
Connect(addr);  // 编译器警告：忽略返回值
```

**Java 的替代方案：**

```java
// Java 没有语言级别的 [[nodiscard]]
// 替代方案 1：使用注解（需要自定义或第三方库）
@CheckReturnValue  // 来自 Error Prone 或 JSR-305
boolean connect(RawAddress addr);

// 替代方案 2：IDE 配置检查规则（如 IntelliJ 的 "Result of method call ignored"）
```

> **为什么 Java 不需要这些属性？** Java 的注解系统（如 `@Deprecated`）提供了部分类似功能，但 `[[nodiscard]]` 和 `[[fallthrough]]` 这类编译器提示在 Java 社区中需求不强。Java 程序员通常依赖 IDE 警告和代码审查工具（如 Error Prone、SpotBugs）来发现这类问题，而非语言内置机制。

---

## 9. = delete 和 = default（C++11）

### 9.1 C++ 的特殊成员函数

C++ 中每个类都有最多 6 个特殊成员函数：

| 函数 | 默认行为 |
|------|---------|
| 默认构造函数 | 如果没有其他构造函数，编译器自动生成 |
| 析构函数 | 编译器自动生成 |
| 拷贝构造函数 | 逐成员复制 |
| 拷贝赋值运算符 | 逐成员赋值 |
| 移动构造函数（C++11） | 逐成员移动 |
| 移动赋值运算符（C++11） | 逐成员移动赋值 |

但有时候，编译器自动生成的行为不是我们想要的：
- 单例类不应该被复制
- 管理资源的类不应该被默认复制
- 有时我们只是想让编译器生成默认实现，而不是手写

`= delete` 和 `= default` 就是用来精确控制这些特殊成员函数的。

### 9.2 = delete——删除特殊成员函数

`= delete` 告诉编译器：**不要生成这个函数，任何尝试调用它的代码都是编译错误**。

```cpp
// system/stack/eatt/eatt.h:112-113
class EattExtension {
public:
    // 获取单例实例
    static EattExtension* GetInstance();

    // 删除拷贝构造和拷贝赋值——单例不能被复制！
    EattExtension(const EattExtension&) = delete;
    EattExtension& operator=(const EattExtension&) = delete;

private:
    EattExtension();  // 私有构造，防止外部创建实例
};

// 尝试复制单例——编译错误！
EattExtension* inst = EattExtension::GetInstance();
EattExtension copy = *inst;  // 错误：拷贝构造函数已删除
EattExtension another;
another = *inst;  // 错误：拷贝赋值运算符已删除
```

### 9.3 = delete 的传统替代方案

在 C++11 之前，人们用各种技巧来禁止拷贝：

```cpp
// 方式 1：声明为 private 且不实现（Boost 风格）
class EattExtension {
private:
    EattExtension(const EattExtension&);             // 只声明，不实现
    EattExtension& operator=(const EattExtension&);   // 只声明，不实现
};

// 方式 2：继承 noncopyable（Boost 库）
class EattExtension : private boost::noncopyable {
    // ...
};
```

`= delete` 是更清晰、更标准的方式：
- 意图明确：一看就知道是"禁止"
- 错误信息更好：编译器会明确说"已删除的函数"
- 可以是 public 的（错误信息更友好）

### 9.4 = delete 的高级用法

`= delete` 不仅可以删除特殊成员函数，还可以删除普通函数，用来禁止某些参数类型：

```cpp
// 禁止浮点数参数
void process(int value);
void process(double) = delete;  // 禁止传入 double
void process(float) = delete;   // 禁止传入 float

process(42);    // 正确：调用 process(int)
process(3.14);  // 错误！double 版本已删除
process(3.14f); // 错误！float 版本已删除
```

### 9.5 = default——显式使用默认实现

`= default` 告诉编译器：**请生成默认的实现**。虽然编译器通常会自动生成，但显式 `= default` 有几个好处：

```cpp
// system/gd/hci/controller.h:35-36
class Controller : public hci::ControllerInterface {
public:
    Controller() = default;              // 显式要求生成默认构造函数
    virtual ~Controller() = default;     // 显式要求生成默认析构函数
};
```

**为什么要用 `= default`？**

原因 1：**当你定义了其他构造函数时，编译器不再自动生成默认构造函数**

```cpp
class MyClass {
public:
    MyClass(int x);  // 自定义构造函数

    // 此时编译器不再自动生成 MyClass()
    // 如果需要无参构造，必须显式声明：
    MyClass() = default;  // 让编译器生成默认构造
};
```

原因 2：**明确表达意图**——"我确实想要默认行为，不是忘了写"

```cpp
class Controller {
public:
    Controller() = default;          // 我确实想要默认构造
    virtual ~Controller() = default; // 我确实想要默认析构
};
// 读者一看就知道：这些是故意用默认实现的，不是遗漏
```

原因 3：**恢复被抑制的默认函数**

```cpp
class EattExtension {
public:
    EattExtension(const EattExtension&) = delete;  // 删除拷贝构造
    EattExtension& operator=(const EattExtension&) = delete;  // 删除拷贝赋值

    // 但移动操作可以是默认的
    EattExtension(EattExtension&&) = default;       // 恢复移动构造
    EattExtension& operator=(EattExtension&&) = default;  // 恢复移动赋值
};
```

### 9.6 = default 与移动语义

```cpp
// system/gd/storage/le_device.h
class LeDevice {
public:
    // 默认的移动构造——高效转移资源
    LeDevice(LeDevice&& other) noexcept = default;

    // 默认的移动赋值
    LeDevice& operator=(LeDevice&& other) noexcept = default;

    // 删除拷贝（如果内部有不可复制的资源）
    LeDevice(const LeDevice&) = delete;
    LeDevice& operator=(const LeDevice&) = delete;
};
```

注意 `noexcept`——移动操作通常不会抛异常，标记为 `noexcept` 可以让标准容器（如 `std::vector`）在重新分配内存时使用移动而非复制，提升性能。

### 9.7 = default 的规则

`= default` 生成的函数与手写的默认实现有一个关键区别：

```cpp
class A {
public:
    A() = default;  // 仍然是 trivial（平凡）构造函数
};

class B {
public:
    B() {}  // 不是 trivial 构造函数（手写了函数体，即使为空）
};

static_assert(std::is_trivially_default_constructible<A>::value, "");  // 通过
static_assert(std::is_trivially_default_constructible<B>::value, "");  // 失败！
```

在蓝牙协议栈中，很多类型需要是 trivial 的（方便序列化），所以 `= default` 比手写空函数体更好。

### 9.8 蓝牙协议栈中的真实示例

**示例 1：EattExtension 单例——禁止拷贝**（`system/stack/eatt/eatt.h:112-113`）

```cpp
class EattExtension {
public:
    static EattExtension* GetInstance();

    // 单例模式：禁止拷贝和赋值
    EattExtension(const EattExtension&) = delete;
    EattExtension& operator=(const EattExtension&) = delete;

private:
    EattExtension();
};
```

**示例 2：Controller 接口——显式默认**（`system/gd/hci/controller.h:35-36`）

```cpp
class Controller : public hci::ControllerInterface {
public:
    Controller() = default;
    virtual ~Controller() = default;
};
```

**示例 3：LeDevice——移动 + 禁止拷贝**（`system/gd/storage/le_device.h`）

```cpp
class LeDevice {
public:
    LeDevice(LeDevice&& other) noexcept = default;
    LeDevice& operator=(LeDevice&& other) noexcept = default;
    LeDevice(const LeDevice&) = delete;
    LeDevice& operator=(const LeDevice&) = delete;
};
```

### 9.9 小结

| 特性 | = delete | = default |
|------|----------|-----------|
| 作用 | 禁止某个函数 | 使用编译器默认实现 |
| 常见用途 | 禁止拷贝/赋值（单例、资源管理类） | 显式声明默认构造/析构 |
| 错误检测 | 编译期（调用已删除函数 → 编译错误） | — |
| 生成代码 | 不生成 | 生成默认实现 |

### ☕ Java 类比

Java **没有** `= delete` 和 `= default` 的直接等价，但可以通过其他方式实现相同效果：

| 对比项 | C++ | Java |
|--------|-----|------|
| 禁止拷贝 | `ClassName(const ClassName&) = delete;` | 将拷贝构造函数设为 `private`（或不提供） |
| 禁止赋值 | `operator=(const ClassName&) = delete;` | 无需处理（Java 没有运算符重载） |
| 显式默认构造 | `ClassName() = default;` | 无需处理（Java 默认就有无参构造） |
| 显式默认析构 | `~ClassName() = default;` | 无需处理（Java 有 GC，无析构函数） |
| 禁止特定参数类型 | `void process(double) = delete;` | 无等价（Java 无法禁止特定类型重载） |

**C++ = delete 示例：**

```cpp
class EattExtension {
public:
    EattExtension(const EattExtension&) = delete;           // 禁止拷贝
    EattExtension& operator=(const EattExtension&) = delete; // 禁止赋值
    Controller() = default;                                   // 显式默认构造
};
```

**Java 的替代方案：**

```java
class EattExtension {
    // 禁止拷贝：将克隆方法设为 private 或不实现 Cloneable
    private EattExtension copy() { throw new UnsupportedOperationException(); }

    // Java 没有赋值运算符重载，无需禁止

    // 默认构造：Java 自动提供，无需显式声明
    // 如果定义了其他构造函数，无参构造不会自动生成，需手动写：
    public EattExtension() {}
}
```

> **关键区别**：C++ 的 `= delete` 是语言级别的禁止，编译器会直接报错。Java 需要通过访问控制（`private`）或运行时异常来模拟，不如 C++ 优雅。Java 不需要 `= default`，因为 Java 没有析构函数，默认构造函数的行为也更简单。

---

## 10. std::optional（C++17）

### 10.1 "可能没有值"的问题

在编程中，我们经常遇到"可能没有值"的情况：

```cpp
// 传统方式 1：用特殊值表示"无"
int find_device_index(const RawAddress& addr) {
    // 找不到时返回 -1
    // 但 -1 是有效的 int 值！如果返回类型是 unsigned 呢？
    return -1;
}

// 传统方式 2：用输出参数 + 返回 bool
bool find_device_address(const std::string& name, RawAddress* out_addr) {
    // 找到返回 true，out_addr 填入地址
    // 找不到返回 false，out_addr 不变
    // 但调用者可能忘记检查返回值！
}

// 传统方式 3：用指针（可能为 null）
const RawAddress* find_device_address(const std::string& name) {
    // 找到返回指针
    // 找不到返回 nullptr
    // 但返回指针意味着生命周期管理的问题
}
```

每种方式都有缺陷。`std::optional` 提供了一个类型安全的解决方案。

### 10.2 std::optional 的基本概念

`std::optional<T>` 表示"一个可能存在也可能不存在的 `T` 类型的值"：

```cpp
#include <optional>

std::optional<RawAddress> find_device_address(const std::string& name) {
    // 找到了
    return found_address;  // 隐式构造 optional（有值）

    // 没找到
    return std::nullopt;   // 表示"无值"
    // 或者
    return {};             // 也表示"无值"
}
```

### 10.3 std::optional 的核心操作

```cpp
std::optional<RawAddress> addr = find_device_address("MyPhone");

// 1. 检查是否有值
if (addr.has_value()) {
    // 有值
}

// 2. 获取值（如果无值，行为未定义！）
RawAddress a = addr.value();  // 无值时抛出 std::bad_optional_access

// 3. 获取值或默认值
RawAddress a = addr.value_or(RawAddress::kEmpty);  // 无值时返回默认值

// 4. 直接用 bool 语境检查
if (addr) {  // 等价于 addr.has_value()
    // 有值
}

// 5. 用 * 和 -> 访问值（类似指针）
RawAddress a = *addr;       // 无值时未定义行为
addr->ToString();           // 无值时未定义行为
```

### 10.4 安全使用模式

```cpp
// 模式 1：先检查，再使用
std::optional<RawAddress> addr = RawAddress::FromString(str);
if (addr.has_value()) {
    LOG_INFO("Address: %s", addr->ToString().c_str());
} else {
    LOG_WARN("Invalid address string");
}

// 模式 2：使用 value_or 提供默认值
RawAddress addr = RawAddress::FromString(str).value_or(RawAddress::kEmpty);

// 模式 3：使用 value() 在无值时抛异常（适合严重错误）
try {
    RawAddress addr = RawAddress::FromString(str).value();
} catch (const std::bad_optional_access& e) {
    LOG_ERROR("Invalid address: %s", e.what());
}
```

### 10.5 std::optional 与指针的区别

```cpp
// 指针：可能指向有效对象，也可能为 null
RawAddress* ptr = get_address();
// 问题：ptr 指向的对象什么时候销毁？谁负责释放？

// optional：值就存在 optional 内部，没有生命周期问题
std::optional<RawAddress> opt = get_address();
// 值就在 opt 里面，opt 销毁时值也销毁
```

| 特性 | 指针 | std::optional |
|------|------|--------------|
| 值的位置 | 指向外部内存 | 存储在自身内部 |
| 生命周期 | 需要手动管理 | 自动管理 |
| 大小开销 | 1 个指针 | sizeof(T) + 1 字节（标记位） |
| 语义 | "指向某处" | "可能有值" |

### 10.6 蓝牙协议栈中的真实示例

**示例 1：从字符串解析蓝牙地址**（`system/types/include/bluetooth/types/address.h:58`）

```cpp
class RawAddress {
public:
    // 从字符串解析地址，可能失败（字符串格式不正确）
    static std::optional<RawAddress> FromString(const std::string& from);
};

// 使用
std::optional<RawAddress> addr = RawAddress::FromString("00:11:22:33:44:55");
if (addr.has_value()) {
    LOG_INFO("Parsed address: %s", addr->ToString().c_str());
} else {
    LOG_ERROR("Failed to parse address");
}
```

**示例 2：反序列化**（`system/gd/storage/serializable.h:39`）

```cpp
template<typename T>
struct Serializable {
    // 从字符串反序列化，可能失败
    static std::optional<T> FromString(const std::string& str);
};

// 使用
auto device = Serializable<LeDevice>::FromString(data);
if (device.has_value()) {
    // 反序列化成功
    process_device(*device);
} else {
    LOG_ERROR("Failed to deserialize device data");
}
```

### 10.7 小结

| 操作 | 代码 | 无值时行为 |
|------|------|-----------|
| 检查 | `opt.has_value()` 或 `if (opt)` | 返回 false |
| 获取值 | `opt.value()` | 抛异常 |
| 获取值 | `*opt` 或 `opt->` | 未定义行为 |
| 获取值或默认 | `opt.value_or(default)` | 返回默认值 |

### ☕ Java 类比

Java 8 引入了 `Optional<T>`，与 C++ 的 `std::optional<T>` 概念相同，但使用方式有差异：

| 对比项 | C++ `std::optional<T>` | Java `Optional<T>` |
|--------|------------------------|---------------------|
| 引入版本 | C++17 (2017) | Java 8 (2014) |
| 检查有值 | `opt.has_value()` 或 `if (opt)` | `opt.isPresent()` |
| 获取值 | `opt.value()` 或 `*opt` | `opt.get()` |
| 获取值或默认 | `opt.value_or(default)` | `opt.orElse(default)` |
| 无值时抛异常 | `opt.value()` → `bad_optional_access` | `opt.get()` → `NoSuchElementException` |
| 函数式操作 | 无（需手动检查） | `opt.map()`, `opt.filter()`, `opt.flatMap()` |
| 存储基本类型 | `std::optional<int>` 可以 | `OptionalInt`（不能用 `Optional<int>`） |
| 值的位置 | 存储在 optional 内部 | 存储在 optional 内部 |
| 推荐作为字段 | 可以 | 不推荐（`Optional` 主要用于返回值） |

**C++ std::optional 示例：**

```cpp
std::optional<RawAddress> addr = RawAddress::FromString(str);
if (addr.has_value()) {
    connect(addr.value());
} else {
    auto default_addr = addr.value_or(RawAddress::kEmpty);
}
```

**Java Optional 示例：**

```java
Optional<RawAddress> addr = RawAddress.fromString(str);
if (addr.isPresent()) {
    connect(addr.get());
} else {
    RawAddress defaultAddr = addr.orElse(RawAddress.EMPTY);
}
// Java 独有的函数式风格：
addr.ifPresent(this::connect);
RawAddress result = addr.orElseGet(RawAddress::empty);
```

> **关键区别**：Java 的 `Optional` 有丰富的函数式 API（`map`、`filter`、`flatMap`、`ifPresent` 等），C++ 的 `std::optional` 更轻量，只提供基本操作。Java 社区推荐 `Optional` 只用作方法返回值，不建议作为字段类型；C++ 没有这个限制。

---

## 11. std::variant（C++17）

### 11.1 "多种类型选一种"的问题

在蓝牙协议栈中，有些数据可能是多种类型之一。例如，一个操作的目标可能是单个设备地址，也可能是一组设备（用组 ID 表示）：

```cpp
// 传统方式 1：用 union（不安全！）
union Target {
    RawAddress addr;
    int group_id;
};
// 问题：不知道当前存的是哪种类型，容易误读

// 传统方式 2：用标签 + union（tagged union）
struct Target {
    enum Type { ADDRESS, GROUP_ID } type;
    union {
        RawAddress addr;
        int group_id;
    };
};
// 可以工作，但需要手动管理类型标签，容易出错

// 传统方式 3：用多态
class Target { ... };
class AddressTarget : public Target { RawAddress addr; };
class GroupTarget : public Target { int group_id; };
// 过于重量级，需要堆分配
```

`std::variant` 是类型安全的联合体，自动管理类型标签，不需要堆分配。

### 11.2 std::variant 的基本用法

```cpp
#include <variant>

// 定义一个可以是 RawAddress 或 int 的类型
std::variant<RawAddress, int> addr_or_group_id;

// 赋值为地址
addr_or_group_id = RawAddress{0x00, 0x11, 0x22, 0x33, 0x44, 0x55};

// 赋值为组 ID
addr_or_group_id = 42;
```

### 11.3 访问 variant 中的值

**方式 1：std::holds_alternative + std::get**

```cpp
std::variant<RawAddress, int> addr_or_group_id = RawAddress{...};

// 检查当前持有哪种类型
if (std::holds_alternative<RawAddress>(addr_or_group_id)) {
    // 当前是地址
    RawAddress addr = std::get<RawAddress>(addr_or_group_id);
    LOG_INFO("Target address: %s", addr.ToString().c_str());
} else if (std::holds_alternative<int>(addr_or_group_id)) {
    // 当前是组 ID
    int group_id = std::get<int>(addr_or_group_id);
    LOG_INFO("Target group: %d", group_id);
}

// 如果 get 的类型不匹配，抛出 std::bad_variant_access
```

**方式 2：std::get_if（不抛异常）**

```cpp
// 返回指针，类型不匹配时返回 nullptr
if (RawAddress* addr = std::get_if<RawAddress>(&addr_or_group_id)) {
    // *addr 就是地址
} else if (int* group_id = std::get_if<int>(&addr_or_group_id)) {
    // *group_id 就是组 ID
}
```

**方式 3：std::visit（最优雅）**

```cpp
// 使用 visitor 模式
std::visit([](auto&& arg) {
    using T = std::decay_t<decltype(arg)>;
    if constexpr (std::is_same_v<T, RawAddress>) {
        LOG_INFO("Target address: %s", arg.ToString().c_str());
    } else if constexpr (std::is_same_v<T, int>) {
        LOG_INFO("Target group: %d", arg);
    }
}, addr_or_group_id);
```

### 11.4 std::variant vs union

| 特性 | union | std::variant |
|------|-------|-------------|
| 类型安全 | 否（不知道当前存的是哪种类型） | 是（自动跟踪当前类型） |
| 非平凡类型 | 不支持（不能存 string 等） | 支持 |
| 访问方式 | 直接访问成员 | `std::get`、`std::visit` |
| 内存 | 只占最大成员的大小 | 最大成员 + 类型标签 |
| 构造/析构 | 需要手动管理 | 自动管理 |

### 11.5 蓝牙协议栈中的真实示例

**示例：音量控制目标**（`system/include/hardware/bt_vc.h`）

```cpp
// 音量控制操作的目标：可能是单个设备，也可能是设备组
struct VolumeControlTarget {
    std::variant<RawAddress, int> addr_or_group_id;
};

// 使用
void set_volume(const VolumeControlTarget& target, uint8_t volume) {
    std::visit([volume](auto&& arg) {
        using T = std::decay_t<decltype(arg)>;
        if constexpr (std::is_same_v<T, RawAddress>) {
            // 对单个设备设置音量
            set_device_volume(arg, volume);
        } else if constexpr (std::is_same_v<T, int>) {
            // 对设备组设置音量
            set_group_volume(arg, volume);
        }
    }, target.addr_or_group_id);
}
```

### 11.6 小结

`std::variant` 是类型安全的联合体，适用于"多种类型选一种"的场景。相比传统 `union`：
- 自动管理类型标签，不会误读
- 支持非平凡类型（如 `std::string`）
- 配合 `std::visit` 和 `if constexpr` 使用非常优雅

### ☕ Java 类比

Java **没有**与 `std::variant` 直接等价的机制。Java 是面向对象语言，通常用继承/多态来处理"多种类型选一种"的场景。

| 对比项 | C++ `std::variant` | Java |
|--------|---------------------|------|
| 类型安全联合体 | `std::variant<A, B>` | 无直接等价 |
| 访问方式 | `std::get`, `std::visit` | 无 |
| 替代方案 1 | — | 继承体系 + 多态（重量级） |
| 替代方案 2 | — | 密封类 + 模式匹配（Java 17+） |
| 替代方案 3 | — | `Object` 类型 + `instanceof` 检查 |
| 内存开销 | 栈上，最大成员 + 标签 | 堆上（每个对象独立分配） |

**C++ std::variant 示例：**

```cpp
std::variant<RawAddress, int> target;
target = RawAddress{0x00, 0x11, 0x22, 0x33, 0x44, 0x55};
std::visit([](auto&& arg) {
    using T = std::decay_t<decltype(arg)>;
    if constexpr (std::is_same_v<T, RawAddress>) {
        set_device_volume(arg, volume);
    } else if constexpr (std::is_same_v<T, int>) {
        set_group_volume(arg, volume);
    }
}, target);
```

**Java 的替代方案（密封类 + 模式匹配，Java 17+）：**

```java
sealed interface VolumeTarget permits DeviceTarget, GroupTarget {}
record DeviceTarget(RawAddress address) implements VolumeTarget {}
record GroupTarget(int groupId) implements VolumeTarget {}

// 使用模式匹配
void setVolume(VolumeTarget target, int volume) {
    switch (target) {
        case DeviceTarget(var addr) -> setDeviceVolume(addr, volume);
        case GroupTarget(var id)    -> setGroupVolume(id, volume);
    }
}
```

**Java 的替代方案（传统继承）：**

```java
abstract class VolumeTarget {}
class DeviceTarget extends VolumeTarget { RawAddress address; }
class GroupTarget extends VolumeTarget { int groupId; }

void setVolume(VolumeTarget target, int volume) {
    if (target instanceof DeviceTarget dt) {
        setDeviceVolume(dt.address, volume);
    } else if (target instanceof GroupTarget gt) {
        setGroupVolume(gt.groupId, volume);
    }
}
```

> **关键区别**：C++ 的 `variant` 是值类型，存储在栈上，零堆分配开销。Java 的替代方案都需要堆分配对象。Java 17+ 的密封类（sealed class）+ 模式匹配是最接近 `variant` 的特性，但仍然基于继承体系。

---

## 总结：现代 C++ 特性一览

| 特性 | C++ 版本 | 核心价值 | 一句话总结 |
|------|---------|---------|-----------|
| `enum class` | C++11 | 类型安全 | 枚举值不再泄漏，大小可控 |
| `constexpr` | C++11/14 | 编译期计算 | 把运行时开销移到编译期 |
| `auto` | C++11 | 简化代码 | 让编译器推导类型，减少冗余 |
| `nullptr` | C++11 | 类型安全 | 空指针不再与整数混淆 |
| 范围 for | C++11 | 简洁遍历 | 遍历容器不再需要迭代器 |
| `static_assert` | C++11 | 编译期检查 | 错误越早发现越好 |
| `if constexpr` | C++17 | 编译期分支 | 模板中根据类型选择代码路径 |
| `[[nodiscard]]` | C++17 | 防止遗漏 | 忽略重要返回值时编译器警告 |
| `[[fallthrough]]` | C++17 | 意图表达 | switch 穿透不再是 bug 嫌疑 |
| `= delete` | C++11 | 禁止操作 | 明确禁止不需要的函数 |
| `= default` | C++11 | 显式默认 | 明确表达"我要默认实现" |
| `std::optional` | C++17 | 可选值 | 类型安全地表示"可能没有值" |
| `std::variant` | C++17 | 类型安全联合体 | 类型安全地表示"多种类型选一种" |

这些特性共同构成了现代 C++ 的核心风格：**更安全、更简洁、更表达意图**。在蓝牙协议栈这样的系统级代码中，它们帮助开发者写出既高效又不容易出错的代码。
