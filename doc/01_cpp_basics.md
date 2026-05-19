# C++ 基础语法教材 —— 基于蓝牙协议栈真实代码

> **目标读者**：C++ 刚入门、基础薄弱的初学者
> **特色**：所有示例均来自 Android 蓝牙协议栈（Bluetooth Stack）真实代码，标注来源文件与行号

---

## 目录

1. [基本数据类型](#1-基本数据类型)
2. [变量与初始化](#2-变量与初始化)
3. [const 关键字](#3-const-关键字)
4. [引用 (Reference)](#4-引用-reference)
5. [指针 (Pointer)](#5-指针-pointer)
6. [static 关键字（基础部分）](#6-static-关键字基础部分)
7. [结构体 struct vs 类 class](#7-结构体-struct-vs-类-class)
8. [nullptr 与 NULL](#8-nullptr-与-null)

---

## 1. 基本数据类型

### 1.1 为什么协议栈不用 int 和 char？

在普通 C++ 程序中，你可能经常看到 `int`、`char` 这样的类型。但在蓝牙协议栈这种**底层系统代码**中，几乎看不到它们，取而代之的是：

| 类型 | 含义 | 占用字节数 | 取值范围 |
|------|------|-----------|---------|
| `uint8_t` | 无符号 8 位整数 | 1 字节 | 0 ~ 255 |
| `uint16_t` | 无符号 16 位整数 | 2 字节 | 0 ~ 65535 |
| `uint32_t` | 无符号 32 位整数 | 4 字节 | 0 ~ 4,294,967,295 |
| `int8_t` | 有符号 8 位整数 | 1 字节 | -128 ~ 127 |
| `int16_t` | 有符号 16 位整数 | 2 字节 | -32768 ~ 32767 |
| `int32_t` | 有符号 32 位整数 | 4 字节 | -2,147,483,648 ~ 2,147,483,647 |

**为什么要用固定宽度整型？**

1. **协议规范精确要求**：蓝牙核心规范明确规定，Channel ID 是 16 位的，MTU 是 16 位的。用 `uint16_t` 可以**精确匹配协议字段宽度**，不多不少。
2. **跨平台一致性**：`int` 在不同平台上可能是 2 字节或 4 字节，而 `uint16_t` 永远是 2 字节。协议栈代码需要在 ARM、x86 等不同架构上运行，必须保证数据宽度一致。
3. **避免隐式溢出**：如果你用 `int` 存一个协议字段，可能不小心存了负数或超出范围的值，编译器不会报错。而 `uint16_t` 明确表示"0~65535 的无符号值"，语义更清晰。

### 1.2 真实代码示例

**示例 1：EattChannel 类中的固定宽度整型成员**

```cpp
// 来源: system/stack/eatt/eatt.h:44-50
class EattChannel {
public:
  RawAddress bda_;
  uint16_t cid_;        // Channel ID，协议规定为 16 位
  uint16_t tx_mtu_;     // 发送最大传输单元，16 位
  uint16_t rx_mtu_;     // 接收最大传输单元，16 位
  EattChannelState state_;  // 枚举类型（底层也是 uint8_t，见下方）
};
```

**解读**：
- `cid_` 是 L2CAP 通道 ID，蓝牙规范规定它是 16 位无符号整数，所以用 `uint16_t`
- `tx_mtu_` 和 `rx_mtu_` 是 MTU（Maximum Transmission Unit），也是 16 位
- 如果写成 `int cid_`，既浪费空间（int 通常是 4 字节），又语义不清（CID 不可能为负数）

**示例 2：枚举类型的底层类型指定**

```cpp
// 来源: system/stack/eatt/eatt.h:37-41
enum class EattChannelState : uint8_t {
  EATT_CHANNEL_PENDING = 0x00,
  EATT_CHANNEL_OPENED,
  EATT_CHANNEL_RECONFIGURING,
};
```

**解读**：
- `enum class` 是 C++11 的强类型枚举（后面章节会详细讲）
- `: uint8_t` 指定了枚举的底层类型为 `uint8_t`，这意味着这个枚举值只占 1 字节
- 在蓝牙协议中，状态值通常只占用 1 字节，这样指定可以与协议报文精确对应

**示例 3：Controller 类中的多种整型**

```cpp
// 来源: system/gd/hci/controller.h:30-33
class Controller {
public:
  static constexpr uint64_t kDefaultEventMask = 0x3dbfffffffffffff;    // 64 位
  static constexpr uint64_t kDefaultEventMaskPage2 = 0x2000000;        // 64 位
  static constexpr uint64_t kDefaultLeEventMask = 0x000000074d02fe7f;  // 64 位
```

```cpp
// 来源: system/gd/hci/controller.h:125-131
  virtual uint16_t GetAclPacketLength() const = 0;      // 16 位
  virtual uint16_t GetNumAclPacketBuffers() const = 0;  // 16 位
  virtual uint8_t GetScoPacketLength() const = 0;       // 8 位
  virtual uint16_t GetNumScoPacketBuffers() const = 0;  // 16 位
```

**解读**：
- 事件掩码（Event Mask）是 64 位的，所以用 `uint64_t`
- ACL 包长度是 16 位的，SCO 包长度是 8 位的——每种都精确匹配 HCI 规范
- 这就是为什么协议栈代码中 `uint8_t`、`uint16_t`、`uint32_t`、`uint64_t` 随处可见

**示例 4：VendorCapabilities 结构体中的混合整型**

```cpp
// 来源: system/gd/hci/controller.h:194-213
struct VendorCapabilities {
  uint8_t is_supported_;                              // 1 字节
  uint8_t max_advt_instances_;                        // 1 字节
  uint16_t total_scan_results_storage_;               // 2 字节
  uint8_t max_irk_list_sz_;                           // 1 字节
  uint32_t a2dp_source_offload_capability_mask_;      // 4 字节
  uint8_t a2dp_offload_v2_support_;                   // 1 字节
  // ...
};
```

**解读**：一个结构体中混合使用了 `uint8_t`、`uint16_t`、`uint32_t`，每种类型都根据实际数据范围选择，既节省内存又精确表达语义。

### 1.3 bool 类型

`bool` 类型只有两个值：`true` 和 `false`，占用 1 字节。

```cpp
// 来源: system/stack/eatt/eatt_impl.h:58
bool collision;  // 标记是否发生了连接冲突

// 来源: system/stack/eatt/eatt_impl.h:59-60
eatt_device(const RawAddress& bd_addr, uint16_t mtu, uint16_t mps)
    : rx_mtu_(mtu), rx_mps_(mps), eatt_tcb_(nullptr), collision(false) {
```

**解读**：`collision` 表示"是否发生了冲突"，只有是/否两种状态，所以用 `bool` 最合适。

### ☕ Java 类比

| C++ 类型 | Java 对应 | 占用字节数 | 说明 |
|---------|----------|-----------|------|
| `uint8_t` | `byte` | 1 | Java 的 byte 是**有符号**的 (-128~127)，无等价无符号 byte |
| `uint16_t` | `short` / `int` | 2/4 | Java 的 short 是有符号的；协议开发中常用 int 代替 |
| `uint32_t` | `int` | 4 | Java 的 int 是有符号的 (-2^31 ~ 2^31-1) |
| `uint64_t` | `long` | 8 | Java 的 long 是有符号的 |
| `int8_t` | `byte` | 1 | Java 的 byte 恰好是有符号 8 位 |
| `int16_t` | `short` | 2 | Java 的 short 恰好是有符号 16 位 |
| `int32_t` | `int` | 4 | Java 的 int 恰好是有符号 32 位 |
| `bool` | `boolean` | 1/1 | 语义相同 |

**关键差异**：
- Java **没有无符号整型**（unsigned），所有整型都是有符号的。如果需要无符号语义，必须用更大的类型（如用 `long` 代替 `uint32_t`）或使用 `Integer.toUnsignedLong()` 等方法
- Java 的 `char` 是 16 位 Unicode，而 C++ 的 `char` 是 8 位
- C++ 的固定宽度类型（`uint8_t` 等）精确匹配协议字段，Java 中通常直接用 `int` 或 `long`，牺牲了精确宽度但简化了代码

```java
// Java 中表示蓝牙 Channel ID（16位无符号）
int cid = 0x0040;  // 用 int 代替 uint16_t，注意不要赋负值

// Java 中表示 64 位事件掩码
long eventMask = 0x3dbfffffffffffffL;  // 用 long 代替 uint64_t
```

### 1.4 练习思考题

1. 蓝牙设备地址（MAC 地址）是 48 位的，你觉得应该用什么类型来存储？`uint16_t`？`uint32_t`？还是其他方案？
2. 如果一个协议字段表示"信号强度"，范围是 -127 到 +127 dBm，应该用什么类型？
3. 为什么 `EattChannelState` 枚举的底层类型用 `uint8_t` 而不是 `int`？如果用 `int` 会怎样？

---

## 2. 变量与初始化

### 2.1 直接初始化 vs 列表初始化（C++11）

C++ 有多种初始化变量的方式：

```cpp
int a = 10;          // 拷贝初始化（C 风格）
int b(10);           // 直接初始化
int c{10};           // 列表初始化（C++11 推荐）
int d = {10};        // 列表初始化的另一种写法
```

**列表初始化的优点**：不允许窄化转换（narrowing conversion），更安全。

```cpp
int x{3.14};   // 编译错误！double 不能窄化为 int
int y = 3.14;  // 可以编译，但会丢失小数部分（危险！）
```

### 2.2 成员初始化列表

在 C++ 中，类的成员变量推荐使用**成员初始化列表**来初始化，而不是在构造函数体内赋值。

**真实代码示例：EattChannel 构造函数**

```cpp
// 来源: system/stack/eatt/eatt.h:63-73
EattChannel(RawAddress& bda, uint16_t cid, uint16_t tx_mtu, uint16_t rx_mtu)
    : bda_(bda),              // 初始化 bda_
      cid_(cid),              // 初始化 cid_
      rx_mtu_(rx_mtu),        // 初始化 rx_mtu_
      state_(EattChannelState::EATT_CHANNEL_PENDING),  // 初始化 state_
      indicate_handle_(0),    // 初始化 indicate_handle_
      ind_ack_timer_(NULL),   // 初始化 ind_ack_timer_
      ind_confirmation_timer_(NULL) {  // 初始化 ind_confirmation_timer_
  cl_cmd_q_ = std::deque<tGATT_CMD_Q>();  // 构造函数体内赋值
  EattChannelSetTxMTU(tx_mtu);
}
```

**逐行解读**：

1. 冒号 `:` 后面的部分就是**成员初始化列表**
2. 每个成员用 `成员名(初始值)` 的格式初始化，用逗号分隔
3. 花括号 `{ }` 内是构造函数体，可以放额外的逻辑

**成员初始化列表 vs 构造函数体内赋值**：

```cpp
// 方式一：成员初始化列表（推荐）
EattChannel(RawAddress& bda, uint16_t cid)
    : cid_(cid) {          // 直接初始化，只执行一次
}

// 方式二：构造函数体内赋值（不推荐）
EattChannel(RawAddress& bda, uint16_t cid) {
  cid_ = cid;              // 先默认初始化，再赋值，执行了两次
}
```

**为什么推荐成员初始化列表？**

1. **效率更高**：成员初始化列表是直接初始化，而函数体内赋值是"先默认构造，再赋值"，多了一步
2. **必须用的场景**：对于 `const` 成员、引用成员、没有默认构造函数的成员，**只能**用初始化列表
3. **初始化顺序**：成员的初始化顺序由**声明顺序**决定，而不是初始化列表中的书写顺序。在上面的例子中，即使你把 `state_` 写在 `bda_` 前面，`bda_` 仍然会先被初始化，因为它先声明。

**另一个示例：eatt_device 构造函数**

```cpp
// 来源: system/stack/eatt/eatt_impl.h:59-62
eatt_device(const RawAddress& bd_addr, uint16_t mtu, uint16_t mps)
    : rx_mtu_(mtu), rx_mps_(mps), eatt_tcb_(nullptr), collision(false) {
  bda_ = bd_addr;  // 注意：bda_ 没有放在初始化列表中，而是在函数体内赋值
}
```

**解读**：这里 `bda_` 是在函数体内赋值的，而其他成员用了初始化列表。这种写法虽然可以工作，但不够统一。更规范的做法是把 `bda_` 也放到初始化列表中：

```cpp
eatt_device(const RawAddress& bd_addr, uint16_t mtu, uint16_t mps)
    : bda_(bd_addr), rx_mtu_(mtu), rx_mps_(mps), eatt_tcb_(nullptr), collision(false) {
}
```

### 2.3 = default 的含义

C++11 引入了 `= default`，告诉编译器"请帮我生成默认的实现"。

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:48
Uuid() = default;  // 默认构造函数

// 来源: system/stack/eatt/eatt_impl.h:80
~eatt_impl() = default;  // 默认析构函数

// 来源: system/stack/eatt/eatt.cc:38-39
struct EattExtension::impl {
  impl() = default;
  ~impl() = default;
};

// 来源: system/stack/eatt/eatt.cc:217
EattExtension::~EattExtension() = default;

// 来源: system/gd/hci/controller.h:35-36
Controller() = default;
virtual ~Controller() = default;
```

**为什么要写 `= default`？**

你可能会问：既然编译器会自动生成默认构造/析构函数，为什么还要显式写出来？

1. **明确意图**：告诉代码阅读者"我是有意使用默认行为的，不是忘了写"
2. **当存在其他构造函数时**：如果你定义了带参数的构造函数，编译器就**不再**自动生成默认构造函数了。此时如果还需要默认构造函数，就必须显式写 `= default`
3. **保持平凡类型（trivial）特性**：`= default` 生成的函数是平凡的，有利于编译器优化

**对比 = delete**：

```cpp
// 来源: system/stack/eatt/eatt.h:112-113
EattExtension(const EattExtension&) = delete;             // 禁止拷贝构造
EattExtension& operator=(const EattExtension&) = delete;  // 禁止拷贝赋值
```

`= delete` 与 `= default` 相反，它告诉编译器"不要生成这个函数，而且不允许任何人调用它"。这是实现**不可拷贝**类的标准方式。

### 2.4 练习思考题

1. 在 `EattChannel` 的构造函数中，`tx_mtu_` 没有出现在初始化列表中，而是在函数体内通过 `EattChannelSetTxMTU(tx_mtu)` 设置。这样做有什么好处？有什么潜在问题？
2. 如果一个类有一个 `const` 成员变量，能在构造函数体内赋值吗？为什么？
3. `= default` 和自己写一个空的构造函数 `{}` 有什么区别？

---

## 3. const 关键字

`const` 是 C++ 中最重要的关键字之一，意思是"不可修改"。在协议栈代码中大量使用。

### 3.1 const 变量

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:38-42
static constexpr size_t kNumBytes128 = 16;   // 128 位 UUID 的字节数
static constexpr size_t kNumBytes32 = 4;     // 32 位 UUID 的字节数
static constexpr size_t kNumBytes16 = 2;     // 16 位 UUID 的字节数
static constexpr size_t kString128BitLen = 36; // 128 位 UUID 的字符串长度
```

**解读**：
- `const` 表示"运行时不可修改"
- `kNumBytes128` 的值一旦设定就不能再改变
- 命名惯例：`const` 变量通常以 `k` 开头（Google C++ 代码风格）

### 3.2 const 成员函数

`const` 放在成员函数参数列表后面，表示**这个函数不会修改对象的任何成员变量**。

```cpp
// 来源: system/gd/hci/controller.h:51
virtual std::string GetLocalName() const = 0;

// 来源: system/gd/hci/controller.h:54-82
virtual bool SupportsSimplePairing() const = 0;
virtual bool SupportsSecureConnections() const = 0;
virtual bool SupportsBle() const = 0;
// ... 大量 const 成员函数

// 来源: system/gd/hci/controller.h:125-131
virtual uint16_t GetAclPacketLength() const = 0;
virtual uint16_t GetNumAclPacketBuffers() const = 0;
virtual uint8_t GetScoPacketLength() const = 0;
```

**解读**：
- `GetLocalName() const` 表示"获取本地名称，但不会修改 Controller 对象的任何状态"
- 所有 `Get...` 和 `Supports...` 函数都是 `const` 的，因为它们只是查询信息，不会改变对象
- 这是一个很好的编程习惯：**如果一个函数逻辑上不应该修改对象，就一定要加 `const`**

**const 成员函数的规则**：

```cpp
class Example {
public:
  int GetValue() const {   // OK: const 成员函数
    value_ = 10;           // 编译错误！const 函数不能修改成员变量
    return value_;         // OK: 只读取成员变量
  }

  void SetValue(int v) {   // OK: 非 const 成员函数
    value_ = v;            // OK: 非 const 函数可以修改成员变量
  }

private:
  int value_;
};
```

**const 对象只能调用 const 成员函数**：

```cpp
const Controller* ctrl = GetController();
ctrl->GetLocalName();     // OK: GetLocalName 是 const 函数
ctrl->Reset();            // 编译错误！Reset 不是 const 函数，不能在 const 对象上调用
```

### 3.3 constexpr vs const 的区别

`constexpr` 是 C++11 引入的关键字，比 `const` 更严格：它要求值必须在**编译期**就能确定。

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:38
static constexpr size_t kNumBytes128 = 16;  // 编译期常量

// 来源: system/types/include/bluetooth/types/uuid.h:118
constexpr Uuid(const UUID128Bit& val) : uu{val} {}  // 编译期可计算的构造函数
```

```cpp
// 来源: system/gd/hci/controller.h:30-33
static constexpr uint64_t kDefaultEventMask = 0x3dbfffffffffffff;
static constexpr uint64_t kDefaultEventMaskPage2 = 0x2000000;
static constexpr uint64_t kDefaultLeEventMask = 0x000000074d02fe7f;
static constexpr uint64_t kLeCSEventMask = 0x0007f80000000000;
```

**const 和 constexpr 的区别**：

| 特性 | `const` | `constexpr` |
|------|---------|-------------|
| 值何时确定 | 运行时或编译期 | **必须**在编译期 |
| 能否用于数组大小 | 不一定（取决于值是否编译期已知） | 可以 |
| 能否用于模板参数 | 不一定 | 可以 |
| 函数修饰 | 表示不修改对象 | 表示函数可在编译期执行 |

```cpp
const int x = 10;          // OK: 运行时常量（碰巧值已知）
constexpr int y = 10;      // OK: 编译期常量

int get_value();            // 运行时才能知道返回值
const int a = get_value();  // OK: const 可以接受运行时值
constexpr int b = get_value(); // 编译错误！constexpr 要求编译期值
```

**Uuid 中的 constexpr 构造函数**：

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:78-81
static constexpr Uuid From128BitBE(const UUID128Bit& uuid) {
  Uuid u(uuid);    // 调用 constexpr 构造函数
  return u;        // 整个函数可以在编译期执行
}

// 来源: system/types/include/bluetooth/types/uuid.h:118
constexpr Uuid(const UUID128Bit& val) : uu{val} {}  // 私有的 constexpr 构造函数
```

这意味着 `Uuid::From128BitBE(...)` 可以在编译期就完成计算，不需要等到运行时，这对性能敏感的协议栈代码非常有价值。

### ☕ Java 类比

| C++ 关键字 | Java 对应 | 编译期求值 | 运行时不可变 | 用途 |
|-----------|----------|----------|------------|------|
| `const` | `final` | 不一定 | ✅ 是 | 运行时常量 |
| `constexpr` | `static final`（基本类型） | ✅ 必须 | ✅ 是 | 编译期常量 |
| `const` 成员函数 | ❌ 无等价 | — | — | Java 没有等价语法 |

**对比代码**：

```cpp
// C++: const 变量
const int kMaxConnections = 7;

// C++: constexpr 变量（编译期常量）
static constexpr size_t kNumBytes128 = 16;
```

```java
// Java: final 变量（类似 const）
final int kMaxConnections = 7;

// Java: static final 基本类型（类似 constexpr，编译期内联）
public static final int K_NUM_BYTES_128 = 16;
```

**关键差异**：
- Java 的 `final` 只表示"不可重新赋值"，不区分编译期和运行时。对于 `static final` 的基本类型和字符串，编译器会做内联优化，效果类似 `constexpr`
- C++ 的 `const` 成员函数（`void Foo() const`）在 Java 中**没有等价语法**。Java 的 `final` 不能修饰方法参数列表后的位置。Java 程序员只能通过**设计约定**（如将类设计为不可变类）来达到类似效果
- C++ 的 `constexpr` 函数可以在编译期执行，Java 没有这个能力

### 3.4 练习思考题

1. 为什么 `Controller` 类中几乎所有的 `Get...` 函数都是 `const` 的，但 `Reset()` 不是？
2. 如果你在 `GetLocalName() const` 函数中试图修改一个成员变量，编译器会怎样？
3. `constexpr size_t kNumBytes128 = 16;` 中的 `constexpr` 能否换成 `const`？效果有什么不同？

---

## 4. 引用 (Reference)

引用是 C++ 对 C 语言的重要扩展，它是一个**已存在变量的别名**。

### 4.1 左值引用 `T&`

```cpp
int x = 10;
int& ref = x;   // ref 是 x 的引用（别名）
ref = 20;       // 等同于 x = 20
```

**关键特性**：
- 引用必须在声明时初始化
- 引用初始化后不能再指向其他变量
- 对引用的操作就是对原变量的操作

### 4.2 const 引用 `const T&`（函数参数中最常见）

在函数参数中，`const T&` 是最常见的用法之一，意思是"传引用以避免拷贝，但不允许修改"。

**真实代码示例 1：EattChannel 构造函数**

```cpp
// 来源: system/stack/eatt/eatt.h:63
EattChannel(RawAddress& bda, uint16_t cid, uint16_t tx_mtu, uint16_t rx_mtu)
```

**解读**：
- `RawAddress& bda`：传引用，避免拷贝 `RawAddress` 对象。但注意这里**没有 const**，说明函数可能会修改 `bda`
- `uint16_t cid`：基本类型直接传值，因为拷贝一个 `uint16_t` 的开销和传引用一样（甚至更小）

**真实代码示例 2：EattExtension 的接口函数**

```cpp
// 来源: system/stack/eatt/eatt.h:129-161
virtual bool IsEattSupportedByPeer(const RawAddress& bd_addr);
virtual void Connect(const RawAddress& bd_addr);
virtual void Disconnect(const RawAddress& bd_addr, uint16_t cid = EATT_ALL_CIDS);
virtual void Reconfigure(const RawAddress& bd_addr, uint16_t cid, uint16_t mtu);
virtual void ReconfigureAll(const RawAddress& bd_addr, uint16_t mtu);
```

**解读**：
- 所有函数的第一个参数都是 `const RawAddress& bd_addr`
- `const` 表示函数不会修改传入的地址
- `&` 表示传引用，避免拷贝 `RawAddress` 对象
- 这是 C++ 中传递"只读大对象"的标准模式

**真实代码示例 3：Uuid 类的运算符重载**

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:113-115
bool operator<(const Uuid& rhs) const;
bool operator==(const Uuid& rhs) const;
bool operator!=(const Uuid& rhs) const;
```

**解读**：
- `const Uuid& rhs`：右侧操作数以 const 引用传入
- 函数末尾的 `const`：左侧操作数不会被修改
- 两个 `const` 配合，确保比较操作不会修改任何一个 UUID

### 4.3 为什么传引用比传值效率高？

```cpp
// 传值：需要拷贝整个对象
void Connect(RawAddress bd_addr);     // 拷贝 RawAddress 的所有字节

// 传引用：只传递对象的地址
void Connect(const RawAddress& bd_addr);  // 只传递一个指针大小的地址
```

`RawAddress` 内部存储 6 字节的 MAC 地址，加上其他成员，可能有几十字节。传值意味着每次调用都要拷贝这些字节，而传引用只需要传递一个地址（4 或 8 字节）。

**规则**：
- 基本类型（`int`、`uint16_t` 等）：直接传值，因为拷贝开销很小
- 大对象（`RawAddress`、`std::string`、`std::vector` 等）：传 `const T&`，避免拷贝
- 需要修改原对象：传 `T&`

### ☕ Java 类比

| 特性 | C++ 引用 `T&` | Java 引用 |
|------|-------------|----------|
| 语法 | 需要显式 `&` | 默认行为，无需额外语法 |
| 可以为 null | ❌ 不可以（必须绑定到对象） | ✅ 可以为 `null` |
| 可以重新指向 | ❌ 不可以 | ✅ 可以重新赋值 |
| 传参避免拷贝 | `const T&` 显式声明 | 对象自动按引用传递 |
| 基本类型传参 | 直接传值（`uint16_t`） | 直接传值（`int` 等） |

**对比代码**：

```cpp
// C++: 引用需要显式声明，基本类型传值
void Connect(const RawAddress& bd_addr, uint16_t cid);
```

```java
// Java: 对象自动按引用传递，基本类型自动传值
void connect(RawAddress bdAddr, int cid);  // RawAddress 自动按引用传递
```

**关键差异**：
- Java 中**所有对象变量都是引用**，不需要像 C++ 那样显式写 `&`。Java 的引用更像 C++ 的指针（可以为 null、可以重新指向），但使用语法像 C++ 的引用（不需要 `*` 解引用）
- Java 没有与 C++ `const T&` 等价的语法。Java 无法在参数层面声明"传入的对象不可修改"，只能通过将类设计为不可变类（immutable）来达到类似效果
- C++ 的 `const T&` 既避免拷贝又禁止修改，是 C++ 独有的精妙设计，Java 没有直接对应

### 4.4 练习思考题

1. 为什么 `uint16_t cid` 用传值而 `RawAddress& bda` 用传引用？
2. 如果把 `const RawAddress& bd_addr` 改成 `RawAddress bd_addr`，程序还能编译吗？有什么问题？
3. `EattChannel(RawAddress& bda, ...)` 中的 `bda` 没有 `const`，这意味着什么？如果加上 `const` 会怎样？

---

## 5. 指针 (Pointer)

指针是 C/C++ 中最强大也最容易出错的特性之一。它存储的是**另一个变量的内存地址**。

### 5.1 基本指针语法

```cpp
int x = 10;
int* p = &x;     // p 存储了 x 的地址（& 是取地址运算符）
*p = 20;         // 通过 * 解引用，修改 p 指向的值，即 x = 20
```

**核心运算符**：

| 运算符 | 含义 | 示例 |
|--------|------|------|
| `*`（声明时） | 声明指针类型 | `int* p;` |
| `*`（使用时） | 解引用，获取指针指向的值 | `*p = 10;` |
| `&`（使用时） | 取地址 | `p = &x;` |
| `->` | 通过指针访问成员 | `p->member` |
| `nullptr` | 空指针字面量 | `p = nullptr;` |

### 5.2 真实代码示例

**示例 1：alarm_t 指针成员**

```cpp
// 来源: system/stack/eatt/eatt.h:57-59
alarm_t* ind_ack_timer_;            // 指向 alarm 对象的指针
alarm_t* ind_confirmation_timer_;   // 指向另一个 alarm 对象的指针
```

**解读**：
- `alarm_t*` 表示"指向 `alarm_t` 类型对象的指针"
- 这里用指针而不是直接存对象，是因为定时器对象可能不存在（还没创建或已销毁），用指针可以表示"空"状态
- 在构造函数中初始化为 `NULL`（见下文）

**示例 2：tGATT_TCB 指针成员**

```cpp
// 来源: system/stack/eatt/eatt_impl.h:55
tGATT_TCB* eatt_tcb_;   // 指向 GATT TCB（Transport Control Block）的指针
```

**解读**：
- `eatt_tcb_` 指向一个由 GATT 层管理的 TCB 对象
- EATT 层不拥有这个对象，只是引用它，所以用指针
- 初始化为 `nullptr`（见 eatt_impl.h:60）

**示例 3：通过指针访问成员（-> 运算符）**

```cpp
// 来源: system/stack/eatt/eatt_impl.h:179-180
log::assert_that(eatt_dev->eatt_tcb_ != nullptr,
                 "assert failed: eatt_dev->eatt_tcb_ != nullptr");
```

**解读**：
- `eatt_dev` 是 `eatt_device*` 类型的指针
- `eatt_dev->eatt_tcb_` 通过 `->` 访问指针所指对象的成员
- 等价于 `(*eatt_dev).eatt_tcb_`，但 `->` 更简洁

**示例 4：函数返回指针**

```cpp
// 来源: system/stack/eatt/eatt_impl.h:82-91
eatt_device* find_device_by_cid(uint16_t lcid) {
  auto iter = find_if(devices_.begin(), devices_.end(), [&lcid](const eatt_device& ed) {
    auto it = ed.eatt_channels.find(lcid);
    return it != ed.eatt_channels.end();
  });

  return (iter == devices_.end()) ? nullptr : &(*iter);
}
```

**解读**：
- 函数返回 `eatt_device*`（指针）
- 如果找到了，返回该元素的地址 `&(*iter)`
- 如果没找到，返回 `nullptr`（空指针，表示"没找到"）
- 这是 C++ 中表示"可能找不到"的经典模式

### 5.3 空指针检查模式

在协议栈代码中，几乎每次使用指针前都会检查是否为空：

```cpp
// 来源: system/stack/eatt/eatt_impl.h:94-97
EattChannel* find_channel_by_cid(uint16_t lcid) {
  eatt_device* eatt_dev = find_device_by_cid(lcid);
  if (!eatt_dev) {        // 检查指针是否为空
    return nullptr;       // 为空则提前返回
  }
  // ... 使用 eatt_dev
}

// 来源: system/stack/eatt/eatt_impl.h:241-244
void upper_tester_delay_connect_cb(const RawAddress& bda) {
  eatt_device* eatt_dev = find_device_by_address(bda);
  if (eatt_dev == nullptr) {   // 另一种空指针检查写法
    log::error("device is not available");
    return;
  }
  connect_eatt_wrap(eatt_dev);
}
```

**两种等价的空指针检查**：
```cpp
if (!ptr)           // 推荐：简洁
if (ptr == nullptr) // 也常见：更明确
if (ptr != nullptr) // 检查非空
```

**EattChannel 析构函数中的空指针检查**：

```cpp
// 来源: system/stack/eatt/eatt.h:75-83
~EattChannel() {
  if (ind_ack_timer_ != NULL) {       // 检查是否为空
    alarm_free(ind_ack_timer_);       // 非空才释放
  }

  if (ind_confirmation_timer_ != NULL) {
    alarm_free(ind_confirmation_timer_);
  }
}
```

**解读**：如果不检查就直接调用 `alarm_free(NULL)`，可能会导致未定义行为或崩溃。这就是为什么使用指针时必须做空指针检查。

### 5.4 指针与引用的区别

| 特性 | 指针 `T*` | 引用 `T&` |
|------|-----------|-----------|
| 可以为空 | 可以（`nullptr`） | 不可以（必须绑定到对象） |
| 可以重新指向 | 可以 | 不可以 |
| 需要解引用 | 是（`*p` 或 `p->`） | 否（直接使用） |
| 声明时必须初始化 | 否 | 是 |
| 表示"可选" | 适合 | 不适合 |

**选择原则**：
- 如果一个对象**必须存在**，用引用
- 如果一个对象**可能不存在**，用指针（配合 `nullptr` 检查）
- 如果需要**在运行时改变指向**，用指针

### ☕ Java 类比

| 特性 | C++ 指针 `T*` | Java 引用 |
|------|-------------|----------|
| 可以为空 | ✅ `nullptr` | ✅ `null` |
| 需要解引用 | ✅ `*p` 或 `p->` | ❌ 直接用 `.` |
| 指针运算 | ✅ `p++` 等 | ❌ 不支持 |
| 重新指向 | ✅ `p = &other` | ✅ `ref = other` |
| 手动内存管理 | ✅ `new`/`delete` | ❌ 自动 GC |
| 悬空指针风险 | ✅ 有 | ❌ GC 避免此问题 |

**对比代码**：

```cpp
// C++: 指针需要手动管理、解引用、空指针检查
EattChannel* channel = find_channel(cid);
if (channel != nullptr) {
    channel->EattChannelSetTxMTU(256);  // -> 访问成员
}
```

```java
// Java: 引用自动管理、直接访问、null 检查
EattChannel channel = findChannel(cid);
if (channel != null) {
    channel.setTxMTU(256);  // 直接 . 访问成员
}
```

**关键差异**：
- Java **没有指针**，所有对象通过引用访问。Java 引用在语法上像 C++ 引用（用 `.` 不用 `->`），在语义上像 C++ 指针（可以为 null、可以重新指向）
- Java 有**垃圾回收器（GC）**，不存在 `delete`，也不会出现悬空指针或内存泄漏（循环引用除外）。C++ 指针必须手动 `delete` 或使用智能指针
- Java 不支持指针运算（如 `p++`），也不支持取地址（`&`），避免了 C++ 指针的许多危险操作
- C++ 中用指针表示"可选"（可能为空）是常见模式，Java 中直接用引用 + `null` 检查即可

### 5.5 练习思考题

1. `eatt_dev->eatt_tcb_` 中，`->` 和 `.` 有什么区别？什么情况下用哪个？
2. 为什么 `find_device_by_cid` 返回指针而不是引用？如果返回引用，怎么表示"没找到"？
3. 在 `~EattChannel()` 析构函数中，如果把 `!= NULL` 的检查去掉，直接调用 `alarm_free()`，可能会发生什么？

---

## 6. static 关键字（基础部分）

`static` 在 C++ 中有多种含义，取决于它用在什么地方。

### 6.1 静态成员变量

静态成员变量属于**类本身**，而不是某个对象。所有对象共享同一份静态成员变量。

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:38-42
class Uuid final {
public:
  static constexpr size_t kNumBytes128 = 16;  // 所有 Uuid 对象共享
  static constexpr size_t kNumBytes32 = 4;    // 所有 Uuid 对象共享
  static constexpr size_t kNumBytes16 = 2;    // 所有 Uuid 对象共享

  static const Uuid kEmpty;  // 静态常量，表示空 UUID
```

**解读**：
- `kNumBytes128` 不属于任何一个 `Uuid` 对象，而是属于 `Uuid` 类
- 访问方式：`Uuid::kNumBytes128`，不需要创建 `Uuid` 对象
- `static constexpr` 组合意味着"编译期常量，属于类级别"

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:46
using UUID128Bit = std::array<uint8_t, kNumBytes128>;
// kNumBytes128 在这里被用作模板参数，因为它在编译期就已知
```

### 6.2 静态成员函数

静态成员函数也属于**类本身**，不需要对象就能调用。它没有 `this` 指针，因此不能访问非静态成员。

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:69-75
static Uuid FromString(const std::string& uuid, bool* is_valid = nullptr);
static Uuid From16Bit(uint16_t uuid16bit);
static Uuid From32Bit(uint32_t uuid32bit);
static constexpr Uuid From128BitBE(const UUID128Bit& uuid);
```

**解读**：
- 这些都是"工厂函数"——通过某种输入创建 `Uuid` 对象
- 调用方式：`Uuid::From16Bit(0x180F)`，不需要先创建 `Uuid` 对象
- 静态成员函数只能访问静态成员变量和其他静态成员函数

**另一个示例：Controller 类中的静态常量**

```cpp
// 来源: system/gd/hci/controller.h:30-33
class Controller {
public:
  static constexpr uint64_t kDefaultEventMask = 0x3dbfffffffffffff;
  static constexpr uint64_t kDefaultEventMaskPage2 = 0x2000000;
  static constexpr uint64_t kDefaultLeEventMask = 0x000000074d02fe7f;
  static constexpr uint64_t kLeCSEventMask = 0x0007f80000000000;
```

### 6.3 单例模式的实现

单例模式（Singleton）确保一个类只有一个实例。在协议栈中，`EattExtension` 就使用了单例模式。

```cpp
// 来源: system/stack/eatt/eatt.h:117-120
static EattExtension* GetInstance() {
  static EattExtension* instance = new EattExtension();
  return instance;
}
```

**逐行解读**：

1. `static EattExtension* GetInstance()`：静态成员函数，可以通过 `EattExtension::GetInstance()` 调用
2. `static EattExtension* instance = new EattExtension();`：
   - 函数内的 `static` 局部变量只在**第一次执行时初始化**
   - 后续调用不会再创建新对象，直接返回已有的
   - C++11 保证这种初始化是线程安全的
3. `return instance;`：返回单例指针

**使用方式**：

```cpp
// 来源: system/stack/eatt/eatt_impl.h:725
EattExtension::GetInstance()->Disconnect(channel->bda_, channel->cid_);
```

**单例模式的配套措施**：

```cpp
// 来源: system/stack/eatt/eatt.h:111-113
EattExtension(const EattExtension&) = delete;             // 禁止拷贝
EattExtension& operator=(const EattExtension&) = delete;  // 禁止赋值
```

**解读**：单例模式必须禁止拷贝和赋值，否则可能意外创建多个实例。

**静态成员函数作为回调**：

```cpp
// 来源: system/stack/eatt/eatt_impl.h:713-719
static void eatt_ind_ack_timeout(void* data) {
  EattChannel* channel = (EattChannel*)data;
  tGATT_TCB* p_tcb = gatt_find_tcb_by_addr(channel->bda_, BT_TRANSPORT_LE);
  log::warn("send ack now");
  attp_send_cl_confirmation_msg(*p_tcb, channel->cid_);
}

// 来源: system/stack/eatt/eatt_impl.h:721-726
static void eatt_ind_confirmation_timeout(void* data) {
  EattChannel* channel = (EattChannel*)data;
  log::warn("disconnecting channel {:#x} for {}", channel->cid_, channel->bda_);
  EattExtension::GetInstance()->Disconnect(channel->bda_, channel->cid_);
}
```

**解读**：
- 这些静态成员函数被用作 C 风格的回调函数
- C 回调函数不能是普通成员函数（因为成员函数有隐含的 `this` 指针），但静态成员函数没有 `this`，所以可以作为回调
- 这是在 C++ 中使用 C 风格回调接口的常见模式

### 6.4 static 在不同位置的含义总结

| 位置 | 含义 | 示例 |
|------|------|------|
| 类内的静态成员变量 | 属于类，所有对象共享 | `static constexpr size_t kNumBytes128 = 16;` |
| 类内的静态成员函数 | 属于类，无 `this` 指针 | `static EattExtension* GetInstance();` |
| 函数内的静态局部变量 | 只初始化一次，生命周期到程序结束 | `static EattExtension* instance = new EattExtension();` |
| 全局/命名空间内的静态变量/函数 | 内部链接性，只在当前编译单元可见 | `static void alarm_closure_cb(void* p) { ... }` |

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:62
static void alarm_closure_cb(void* p) {  // 文件级 static，只在当前 .cc 文件可见
  closure_data* data = (closure_data*)p;
  std::move(data->user_task).Run();
  delete data;
}
```

### ☕ Java 类比

| 位置 | C++ `static` | Java `static` | 差异 |
|------|-------------|--------------|------|
| 类的静态成员变量 | `static constexpr size_t kNumBytes128 = 16;` | `public static final int K_NUM_BYTES_128 = 16;` | 语义相同 |
| 类的静态成员函数 | `static Uuid From16Bit(uint16_t);` | `public static Uuid from16Bit(int);` | 语义相同 |
| 函数内静态局部变量 | `static EattExtension* instance = ...;` | ❌ 无等价 | Java 需要用类级别的字段实现 |
| 文件级静态（内部链接） | `static void alarm_closure_cb(...)` | ❌ 无等价 | Java 用 `private` 访问控制代替 |

**对比代码——静态成员**：

```cpp
// C++: 静态成员变量和函数
class Uuid final {
public:
    static constexpr size_t kNumBytes128 = 16;
    static Uuid From16Bit(uint16_t uuid16bit);
};
// 访问：Uuid::kNumBytes128, Uuid::From16Bit(0x180F)
```

```java
// Java: 静态成员变量和函数
public final class Uuid {
    public static final int K_NUM_BYTES_128 = 16;
    public static Uuid from16Bit(int uuid16bit) { ... }
}
// 访问：Uuid.K_NUM_BYTES_128, Uuid.from16Bit(0x180F)
```

**对比代码——单例模式**：

```cpp
// C++: 函数内静态局部变量实现单例
static EattExtension* GetInstance() {
    static EattExtension* instance = new EattExtension();
    return instance;
}
```

```java
// Java: 类级别静态字段实现单例
private static EattExtension instance;
public static EattExtension getInstance() {
    if (instance == null) {
        instance = new EattExtension();
    }
    return instance;
}
```

**关键差异**：
- Java **没有函数内的静态局部变量**。C++ 中 `static` 局部变量只初始化一次的特性，在 Java 中需要用类级别的 `static` 字段来模拟
- C++ 的文件级 `static`（限制符号在当前编译单元可见）在 Java 中不存在，Java 用 `private` 或包访问权限来控制可见性
- C++ 静态成员函数**没有 `this` 指针**，Java 的静态方法也**没有 `this` 引用**，两者一致

### 6.5 练习思考题

1. `EattExtension::GetInstance()` 中的 `static EattExtension* instance` 是函数内静态变量。如果两次调用 `GetInstance()`，会创建两个 `EattExtension` 对象吗？
2. 为什么单例模式要 `= delete` 拷贝构造函数和赋值运算符？
3. 静态成员函数能访问非静态成员变量吗？为什么？

---

## 7. 结构体 struct vs 类 class

### 7.1 默认访问权限的区别

在 C++ 中，`struct` 和 `class` 几乎完全相同，唯一的区别是**默认访问权限**：

| 特性 | `struct` | `class` |
|------|----------|---------|
| 默认成员访问权限 | `public` | `private` |
| 默认继承方式 | `public` | `private` |

```cpp
struct MyStruct {
  int x;    // 默认 public
};

class MyClass {
  int x;    // 默认 private
};
```

### 7.2 何时用 struct 何时用 class

**约定**（Google C++ 代码风格，也是协议栈代码遵循的风格）：
- **struct**：用于**被动数据载体**，即主要就是存数据的，没有太多逻辑
- **class**：用于有**不变量（invariant）需要维护**的类型，有封装和逻辑

### 7.3 真实代码示例

**示例 1：struct 作为前置声明（Pimpl 惯用法）**

```cpp
// 来源: system/stack/eatt/eatt.h:283-285
private:
  struct impl;                      // 前置声明：声明 impl 但不定义
  std::unique_ptr<impl> pimpl_;     // 指向 impl 的智能指针
```

**解读**：
- `struct impl;` 是前置声明，告诉编译器"存在一个叫 `impl` 的结构体，但具体内容稍后定义"
- 实际定义在 `.cc` 文件中：

```cpp
// 来源: system/stack/eatt/eatt.cc:37-39
struct EattExtension::impl {
  impl() = default;
  ~impl() = default;
  // ... 实际的成员和方法
};
```

- 这是 **Pimpl（Pointer to Implementation）惯用法**：把实现细节隐藏在 `.cc` 文件中，`.h` 文件只暴露接口
- 好处：减少头文件依赖，加快编译速度，改变实现不需要重新编译使用者

**示例 2：struct 作为实现细节**

```cpp
// 来源: system/stack/eatt/eatt_impl.h:65-78
struct eatt_impl {
  std::vector<eatt_device> devices_;
  uint16_t psm_;
  uint16_t default_mtu_;
  uint16_t max_mps_;
  tL2CAP_APPL_INFO reg_info_;

  base::WeakPtrFactory<eatt_impl> weak_factory_{this};

  eatt_impl() {
    default_mtu_ = EATT_DEFAULT_MTU;
    max_mps_ = EATT_MIN_MTU_MPS;
    psm_ = BT_PSM_EATT;
  }

  ~eatt_impl() = default;
  // ... 大量成员函数
};
```

**解读**：
- `eatt_impl` 虽然用了 `struct`，但它有大量成员函数和逻辑
- 这里用 `struct` 是因为它是内部实现细节，所有成员默认 `public` 方便内部访问
- 它不暴露给外部用户，所以不需要严格的封装

**示例 3：struct 作为纯数据载体**

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:56-58
struct closure_data {
  base::OnceClosure user_task;
};
```

**解读**：
- `closure_data` 只有一个成员变量，没有任何成员函数
- 它的作用就是把一个闭包（callback）打包成一个数据结构，传给 C 风格的回调
- 这是最典型的 struct 用法：纯数据，没有不变量需要维护

**示例 4：class 作为有封装的类型**

```cpp
// 来源: system/stack/eatt/eatt.h:43-106
class EattChannel {
public:
  RawAddress bda_;
  uint16_t cid_;
  uint16_t tx_mtu_;
  uint16_t rx_mtu_;
  EattChannelState state_;
  // ... 其他成员

  EattChannel(RawAddress& bda, uint16_t cid, uint16_t tx_mtu, uint16_t rx_mtu);
  ~EattChannel();
  void EattChannelSetState(EattChannelState state);
  void EattChannelSetTxMTU(uint16_t tx_mtu);
};
```

**解读**：
- `EattChannel` 有构造函数、析构函数和业务方法
- 它有不变量需要维护：`tx_mtu_` 必须在 `[EATT_MIN_MTU_MPS, EATT_MAX_TX_MTU]` 范围内
- 设置 MTU 通过 `EattChannelSetTxMTU()` 方法，而不是直接赋值，确保值合法

```cpp
// 来源: system/stack/eatt/eatt.h:102-105
void EattChannelSetTxMTU(uint16_t tx_mtu) {
  this->tx_mtu_ = std::min<uint16_t>(tx_mtu, EATT_MAX_TX_MTU);  // 不超过最大值
  this->tx_mtu_ = std::max<uint16_t>(tx_mtu, EATT_MIN_MTU_MPS); // 不低于最小值
}
```

**示例 5：struct 作为连接信息载体**

```cpp
// 来源: system/stack/connection_manager/connection_manager.cc:95-103
struct tAPPS_CONNECTING {
  std::set<tAPP_ID> doing_bg_conn;
  std::set<tAPP_ID> doing_targeted_announcements_conn;
  bool is_in_accept_list;
  std::map<tAPP_ID, unique_alarm_ptr> doing_direct_conn;
};
```

**解读**：
- 这个 struct 把"正在连接的应用信息"组织在一起
- 虽然有多个成员，但没有复杂的不变量或业务逻辑
- 用 struct 让所有成员默认 public，方便直接访问

**示例 6：VendorCapabilities —— struct 混合整型成员**

```cpp
// 来源: system/gd/hci/controller.h:194-213
struct VendorCapabilities {
  uint8_t is_supported_;
  uint8_t max_advt_instances_;
  uint8_t offloaded_resolution_of_private_address_;
  uint16_t total_scan_results_storage_;
  uint8_t max_irk_list_sz_;
  uint8_t filtering_support_;
  uint8_t max_filter_;
  uint8_t activity_energy_info_support_;
  uint16_t version_supported_;
  uint16_t total_num_of_advt_tracked_;
  uint8_t extended_scan_support_;
  uint8_t debug_logging_supported_;
  uint8_t le_address_generation_offloading_support_;
  uint32_t a2dp_source_offload_capability_mask_;
  uint8_t bluetooth_quality_report_support_;
  uint32_t dynamic_audio_buffer_support_;
  uint8_t a2dp_offload_v2_support_;
  uint8_t sniff_offload_support_;
};
```

**解读**：纯数据结构，对应控制器厂商能力的各个字段，用 `struct` + 默认 `public` 非常合适。

### ☕ Java 类比

| 特性 | C++ `struct` | C++ `class` | Java |
|------|------------|------------|------|
| 默认访问权限 | `public` | `private` | — |
| 可以有方法 | ✅ | ✅ | — |
| Java 有 `struct` 吗 | — | — | ❌ **没有** |

**关键差异**：
- Java **没有 `struct` 关键字**，只有 `class`。所有数据载体在 Java 中都是 `class`
- C++ 中 `struct` 和 `class` 功能几乎完全相同，区别仅在于默认访问权限。Java 中不存在这种区分
- C++ 用 `struct` 表示"纯数据载体"的约定，在 Java 中通常用 **POJO（Plain Old Java Object）** 或 **Record 类（Java 16+）** 来表达

**对比代码**：

```cpp
// C++: struct 作为纯数据载体
struct closure_data {
    base::OnceClosure user_task;
};
```

```java
// Java 方式1: 普通 class（类似 struct）
public class ClosureData {
    public Runnable userTask;  // 默认需要显式 public
}

// Java 方式2: Record 类（Java 16+，更接近 struct 的简洁性）
public record ClosureData(Runnable userTask) {}
```

**对比代码——Pimpl 惯用法**：

```cpp
// C++: struct 前置声明用于 Pimpl
class EattExtension {
private:
    struct impl;                    // 前置声明
    std::unique_ptr<impl> pimpl_;   // 不透明指针
};
```

```java
// Java: 不需要 Pimpl！
// Java 的类天然隔离了接口和实现：
// - .java 源文件编译后只有 .class 字节码
// - 使用者只能看到 public 成员
// - 修改 private 成员不影响使用方（不需要重新编译）
// 所以 Java 天然具有 C++ Pimpl 想要达到的效果
public class EattExtension {
    private Impl impl;  // 直接持有实现类，无需隐藏
}
```

### 7.4 练习思考题

1. 如果把 `struct closure_data` 改成 `class closure_data`，代码还能编译吗？需要做什么修改？
2. `struct impl;` 是前置声明。为什么不在头文件中直接定义 `impl` 的内容？这样做有什么好处？
3. `eatt_impl` 用了 `struct` 但有很多成员函数，这违反了"struct 只用于数据载体"的约定吗？你怎么看？

---

## 8. nullptr 与 NULL

### 8.1 NULL 的问题

在 C 语言中，`NULL` 通常定义为 `((void*)0)` 或 `0`。在 C++ 中，`NULL` 通常定义为 `0`。这会导致一个严重的问题：

```cpp
void func(int x);       // 重载 1
void func(char* p);     // 重载 2

func(NULL);  // 你想调用重载 2，但 NULL 是 0，所以调用了重载 1！
```

### 8.2 nullptr 的优势

C++11 引入了 `nullptr`，它是专门的空指针字面量，类型是 `std::nullptr_t`：

```cpp
func(nullptr);  // 明确调用重载 2，因为 nullptr 是指针类型
```

**`nullptr` 的优点**：
1. **类型安全**：`nullptr` 只能隐式转换为指针类型，不能转换为整数类型
2. **不会与整数 0 混淆**：在函数重载时不会选错
3. **语义更清晰**：`nullptr` 一看就知道是空指针，`0` 或 `NULL` 则有歧义

### 8.3 协议栈中的混用情况

在蓝牙协议栈代码中，我们可以看到 `NULL` 和 `nullptr` 的混用，这反映了代码的历史演变：

**使用 NULL 的代码（较早的代码风格）**：

```cpp
// 来源: system/stack/eatt/eatt.h:69-70
ind_ack_timer_(NULL),           // 构造函数中用 NULL 初始化指针
ind_confirmation_timer_(NULL) {

// 来源: system/stack/eatt/eatt.h:76-82
~EattChannel() {
  if (ind_ack_timer_ != NULL) {       // 用 NULL 做比较
    alarm_free(ind_ack_timer_);
  }
  if (ind_confirmation_timer_ != NULL) {
    alarm_free(ind_confirmation_timer_);
  }
}

// 来源: system/stack/eatt/eatt_impl.h:132
eatt_dev->eatt_tcb_ = NULL;    // 赋值用 NULL

// 来源: system/stack/eatt/eatt_impl.h:671-672
fixed_queue_free(channel->server_outstanding_cmd_.multi_rsp_q, NULL);
channel->server_outstanding_cmd_.multi_rsp_q = NULL;
```

**使用 nullptr 的代码（较新的代码风格）**：

```cpp
// 来源: system/stack/eatt/eatt_impl.h:60
eatt_tcb_(nullptr),    // 构造函数中用 nullptr 初始化指针

// 来源: system/stack/eatt/eatt_impl.h:90
return (iter == devices_.end()) ? nullptr : &(*iter);  // 返回 nullptr

// 来源: system/stack/eatt/eatt_impl.h:96
return nullptr;        // 返回 nullptr

// 来源: system/stack/eatt/eatt_impl.h:179
log::assert_that(eatt_dev->eatt_tcb_ != nullptr,  // 用 nullptr 做比较

// 来源: system/stack/eatt/eatt_impl.h:242
if (eatt_dev == nullptr) {  // 用 nullptr 做比较
```

**同一个文件中的混用**：

注意 `eatt_impl.h` 中，同一个文件甚至同一个类中混用了 `NULL` 和 `nullptr`：

```cpp
// eatt_impl.h:60 - 用 nullptr
eatt_tcb_(nullptr), collision(false) {

// eatt_impl.h:132 - 用 NULL
eatt_dev->eatt_tcb_ = NULL;
```

**解读**：
- `eatt.h` 中的 `EattChannel` 类（较早编写）使用 `NULL`
- `eatt_impl.h` 中的 `eatt_device` 和 `eatt_impl`（较新编写或重构过）使用 `nullptr`
- 这在大型项目中很常见：代码是逐步演进的，新旧风格并存
- **新代码应该统一使用 `nullptr`**

### 8.4 nullptr 在函数参数中的使用

```cpp
// 来源: system/types/include/bluetooth/types/uuid.h:69
static Uuid FromString(const std::string& uuid, bool* is_valid = nullptr);
```

**解读**：
- `bool* is_valid = nullptr`：参数默认值为 `nullptr`
- 调用者可以选择不传这个参数，函数内部会检查 `is_valid != nullptr` 来决定是否设置验证结果
- 这是 C++ 中"可选输出参数"的常见模式

### 8.5 NULL 与 nullptr 的等价性

在大多数情况下，`NULL` 和 `nullptr` 可以互换使用：

```cpp
int* p1 = NULL;      // OK
int* p2 = nullptr;   // OK，推荐

if (p1 != NULL) {}   // OK
if (p2 != nullptr) {} // OK，推荐
if (p1) {}           // OK，最简洁
if (!p2) {}          // OK，最简洁
```

但在函数重载时会有区别：

```cpp
void process(int value);
void process(void* ptr);

process(NULL);      // 调用 process(int)，可能不是你想要的！
process(nullptr);   // 调用 process(void*)，明确无误
```

### ☕ Java 类比

| 特性 | C++ `nullptr` | C++ `NULL` | Java `null` |
|------|-------------|-----------|------------|
| 类型 | `std::nullptr_t`（专用类型） | `int` 0 或 `void*` 0 | `null`（专用字面量） |
| 类型安全 | ✅ 只能转为指针类型 | ❌ 可能与 `int` 0 混淆 | ✅ 只能赋给引用类型 |
| 函数重载安全 | ✅ 不会选错重载 | ❌ 可能选 `int` 版本 | ✅ 不会选错重载 |
| 可用于基本类型 | ❌ | ⚠️ 可以但危险 | ❌ |

**对比代码**：

```cpp
// C++: nullptr 和 NULL 的区别
void process(int value);
void process(void* ptr);

process(NULL);      // 调用 process(int)！可能不是你想要的
process(nullptr);   // 调用 process(void*)，明确无误
```

```java
// Java: null 是类型安全的
void process(int value) { }
void process(Object ptr) { }

process(0);         // 调用 process(int)，清晰
process(null);      // 调用 process(Object)，清晰
// process((int)null);  // 编译错误！null 不能转为基本类型
```

**关键差异**：
- Java 的 `null` 天然是类型安全的，不存在 C++ `NULL` 那样与整数 0 混淆的问题
- Java 的 `null` 只能赋给引用类型（对象），不能赋给基本类型（`int`、`boolean` 等），这比 C++ 更严格
- C++ 需要 `nullptr` 来解决 `NULL` 的历史遗留问题，Java 从一开始就设计正确

### 8.6 练习思考题

1. 在 `eatt.h` 的 `EattChannel` 构造函数中，`ind_ack_timer_(NULL)` 改成 `ind_ack_timer_(nullptr)` 有什么影响？
2. 为什么 `eatt_impl.h` 中同一文件会混用 `NULL` 和 `nullptr`？如果你来重构，会怎么统一？
3. `bool* is_valid = nullptr` 这种写法中，调用者如何判断函数是否设置了 `is_valid` 的值？

---

## 总结

| 语法点 | 核心要点 | 协议栈中的典型用法 |
|--------|---------|-------------------|
| 固定宽度整型 | `uint8_t`/`uint16_t`/`uint32_t` 精确匹配协议字段 | `cid_` 用 `uint16_t`，MTU 用 `uint16_t` |
| 成员初始化列表 | `: member_(value)` 比函数体内赋值更高效 | `EattChannel` 构造函数 |
| `= default` | 让编译器生成默认实现 | `Uuid() = default;` |
| `= delete` | 禁止某个函数 | 禁止单例的拷贝构造 |
| `const` 成员函数 | 承诺不修改对象状态 | `GetLocalName() const` |
| `constexpr` | 编译期常量/函数 | `kNumBytes128`，`From128BitBE()` |
| `const T&` 参数 | 避免拷贝 + 不可修改 | `const RawAddress& bd_addr` |
| 指针 | 可以为空，需要检查 | `alarm_t* ind_ack_timer_` |
| `nullptr` | C++11 空指针，替代 `NULL` | `eatt_tcb_(nullptr)` |
| `static` 成员 | 属于类而非对象 | `kNumBytes128`，`GetInstance()` |
| `struct` vs `class` | 默认访问权限不同 | 数据载体用 `struct`，有逻辑用 `class` |

---

> **下一步学习建议**：
> - 掌握以上基础后，可以继续学习：智能指针（`std::unique_ptr`、`std::shared_ptr`）、枚举类（`enum class`）、命名空间（`namespace`）、虚函数与多态
> - 尝试阅读 `eatt_impl.h` 中的完整代码，用本教材的知识点逐行分析
