# C++ 类与对象 —— 基于蓝牙协议栈代码的详细教程

> **目标读者**：C++ 刚入门、基础很薄弱的初学者
> **代码来源**：Android 蓝牙协议栈（Bluetooth Stack）真实项目代码
> **学习目标**：通过阅读真实项目代码，掌握 C++ 类与对象的核心语法

---

## 目录

1. [类的定义与基本结构](#1-类的定义与基本结构)
2. [构造函数](#2-构造函数)
3. [析构函数](#3-析构函数)
4. [this 指针](#4-this-指针)
5. [const 成员函数](#5-const-成员函数)
6. [static 成员](#6-static-成员)
7. [final 关键字](#7-final-关键字)
8. [内联函数 inline](#8-内联函数-inline)
9. [嵌套类型与内部定义](#9-嵌套类型与内部定义)
10. [实际阅读建议](#10-实际阅读建议)

---

> 📎 关联教材：01(基础语法), 03(继承与多态), 05(智能指针)

## 1. 类的定义与基本结构

### 1.1 什么是类？

类（class）是 C++ 中用来创建"自定义类型"的工具。你可以把类想象成一张**蓝图**，而对象就是根据这张蓝图造出来的**具体产品**。

比如，"蓝牙设备地址"就是一个概念，而 `00:11:22:33:44:55` 就是一个具体的地址对象。

### 1.2 class 关键字

用 `class` 关键字来定义一个类：

```cpp
class 类名 {
  // 类的内容
};
```

**注意**：类定义的末尾有一个**分号** `;`，这是初学者最容易遗漏的地方！

### 1.3 public / private / protected 访问控制

类内部的成员（变量和函数）可以设置访问权限：

| 关键字 | 含义 | 谁能访问 |
|--------|------|----------|
| `public` | 公开的 | 任何地方都能访问 |
| `private` | 私有的 | 只有类自己的成员函数能访问 |
| `protected` | 受保护的 | 类自己和子类能访问 |

**简单记忆**：
- `public` = 大门敞开，谁都能来
- `private` = 自己的日记本，只有自己能看
- `protected` = 家族内部共享，外人不能看

### 1.4 成员变量与成员函数

- **成员变量**：类中定义的变量，描述对象的"属性"
- **成员函数**：类中定义的函数，描述对象的"行为"

### 1.5 真实示例：EattChannel 类完整解析

> 📄 来源：`system/stack/eatt/eatt.h` 第 43-106 行

```cpp
class EattChannel {
public:
  /* 成员变量 —— 描述一个 EATT 通道的属性 */
  RawAddress bda_;                              // 蓝牙设备地址
  uint16_t cid_;                                // 通道 ID
  uint16_t tx_mtu_;                             // 发送最大传输单元
  uint16_t rx_mtu_;                             // 接收最大传输单元
  EattChannelState state_;                      // 通道状态

  tGATT_SR_CMD server_outstanding_cmd_;         // 服务端待处理命令
  uint16_t indicate_handle_;                    // 指示句柄
  alarm_t* ind_ack_timer_;                      // 指示确认定时器
  alarm_t* ind_confirmation_timer_;             // 指示确认定时器
  std::deque<tGATT_CMD_Q> cl_cmd_q_;           // GATT 客户端命令队列

  /* 成员函数 —— 描述 EATT 通道的行为 */
  EattChannel(RawAddress& bda, uint16_t cid, uint16_t tx_mtu, uint16_t rx_mtu);  // 构造函数
  ~EattChannel();                               // 析构函数
  void EattChannelSetState(EattChannelState state);  // 设置状态
  void EattChannelSetTxMTU(uint16_t tx_mtu);         // 设置发送 MTU
};
```

**逐行解读**：

1. `class EattChannel {` —— 定义一个名为 `EattChannel` 的类，表示一个 EATT（Enhanced ATT）蓝牙通道
2. `public:` —— 下面的成员都是公开的，外部代码可以访问
3. `RawAddress bda_;` —— 成员变量，存储远端蓝牙设备地址，类型是 `RawAddress`
4. `uint16_t cid_;` —— 成员变量，16 位无符号整数，存储通道 ID
5. `alarm_t* ind_ack_timer_;` —— 指针类型的成员变量，指向一个定时器
6. `std::deque<tGATT_CMD_Q> cl_cmd_q_;` —— 使用 STL 双端队列存储命令
7. `EattChannel(...)` —— 构造函数（下一节详解）
8. `~EattChannel()` —— 析构函数（第 3 节详解）

**设计思路**：这个类把一个 EATT 通道的所有相关信息（地址、ID、MTU、定时器、命令队列）打包在一起，形成一个完整的"通道"概念。

### 📌 本节小结

- `class` 定义自定义类型，`public`/`private`/`protected` 控制访问权限
- 成员变量描述属性，成员函数描述行为
- 类定义末尾的分号 `;` 不能遗漏

---

## 2. 构造函数

### 2.1 什么是构造函数？

构造函数是一种**特殊的成员函数**，在创建对象时**自动调用**，用于初始化对象。

构造函数的特点：
- 函数名与类名**完全相同**
- **没有返回值**（连 `void` 都不写）
- 创建对象时**自动执行**

### 2.2 默认构造函数

默认构造函数就是**不需要参数**的构造函数：

```cpp
class RawAddress final {
public:
  RawAddress() = default;   // 默认构造函数
};
```

> 📄 来源：`system/types/include/bluetooth/types/address.h` 第 33 行

`RawAddress() = default;` 的含义是："我需要一个默认构造函数，但请编译器帮我自动生成。"

**什么时候会自动生成默认构造函数？**
- 如果你不写任何构造函数，编译器会自动生成一个
- 一旦你写了带参数的构造函数，编译器就**不再**自动生成默认构造函数
- 用 `= default` 可以显式要求编译器生成

### 2.3 带参构造函数

带参构造函数可以在创建对象时传入初始值：

> 📄 来源：`system/stack/eatt/eatt.h` 第 63-73 行

```cpp
EattChannel(RawAddress& bda, uint16_t cid, uint16_t tx_mtu, uint16_t rx_mtu)
    : bda_(bda),
      cid_(cid),
      rx_mtu_(rx_mtu),
      state_(EattChannelState::EATT_CHANNEL_PENDING),
      indicate_handle_(0),
      ind_ack_timer_(NULL),
      ind_confirmation_timer_(NULL) {
  cl_cmd_q_ = std::deque<tGATT_CMD_Q>();
  EattChannelSetTxMTU(tx_mtu);
}
```

**解读**：
- 函数名 `EattChannel` 与类名相同 → 这是构造函数
- 接收 4 个参数：`bda`（设备地址）、`cid`（通道ID）、`tx_mtu`（发送MTU）、`rx_mtu`（接收MTU）
- 冒号 `:` 后面是**成员初始化列表**（下一小节详解）
- 花括号 `{}` 内是构造函数的函数体

### 2.4 成员初始化列表（重点！）

成员初始化列表是构造函数中**初始化成员变量**的高效方式，语法如下：

```cpp
类名(参数列表)
    : 成员1(初始值1),
      成员2(初始值2),
      成员3(初始值3) {
  // 函数体
}
```

**为什么用初始化列表而不是在函数体里赋值？**

| 方式 | 过程 | 效率 |
|------|------|------|
| 初始化列表 | 直接初始化 | 高效，只执行一次 |
| 函数体赋值 | 先默认构造，再赋值 | 低效，执行两次 |

来看 `EattChannel` 的初始化列表：

```cpp
: bda_(bda),                                    // 用参数 bda 初始化 bda_
  cid_(cid),                                    // 用参数 cid 初始化 cid_
  rx_mtu_(rx_mtu),                              // 用参数 rx_mtu 初始化 rx_mtu_
  state_(EattChannelState::EATT_CHANNEL_PENDING), // 初始状态设为 PENDING
  indicate_handle_(0),                          // 初始指示句柄为 0
  ind_ack_timer_(NULL),                         // 定时器指针初始为空
  ind_confirmation_timer_(NULL)                  // 定时器指针初始为空
```

**注意**：
1. 初始化列表的顺序最好与成员变量**声明顺序一致**（C++ 实际按声明顺序初始化）
2. 有些成员**必须**用初始化列表：`const` 成员、引用成员、没有默认构造函数的类类型成员
3. `bda_` 末尾的下划线是命名惯例，表示这是成员变量，以区分同名的参数

### 2.5 另一个真实示例：eatt_device 的构造函数

> 📄 来源：`system/stack/eatt/eatt_impl.h` 第 59-63 行

```cpp
eatt_device(const RawAddress& bd_addr, uint16_t mtu, uint16_t mps)
    : rx_mtu_(mtu), rx_mps_(mps), eatt_tcb_(nullptr), collision(false) {
  bda_ = bd_addr;
}
```

**解读**：
- 参数 `bd_addr` 前加了 `const` 和 `&`，表示"常量引用"——不会修改传入的值，也不拷贝
- 初始化列表初始化了 `rx_mtu_`、`rx_mps_`、`eatt_tcb_`、`collision` 四个成员
- `bda_` 在函数体中赋值（两种方式混用也是合法的，但推荐统一使用初始化列表）
- `eatt_tcb_` 初始化为 `nullptr`（C++11 推荐用 `nullptr` 代替 `NULL`）

### 2.6 `= default` 含义

> 📄 来源：`system/types/include/bluetooth/types/address.h` 第 33 行

```cpp
RawAddress() = default;
```

`= default` 是 C++11 引入的语法，含义是："请编译器为我生成默认实现。"

**与不写构造函数的区别**：
- 不写：编译器自动生成，但如果你写了其他构造函数，它就不再生成
- `= default`：显式告诉编译器"我要默认版本"，即使你写了其他构造函数，默认版本依然存在

**另一个例子**：

> 📄 来源：`system/gd/hci/controller.h` 第 35-36 行

```cpp
Controller() = default;
virtual ~Controller() = default;
```

这里 `Controller` 的默认构造函数和虚析构函数都用了 `= default`，表示使用编译器生成的默认实现。

### ☕ Java 类比

| 特性 | C++ | Java |
|------|-----|------|
| 构造函数语法 | 类名(参数) | 类名(参数) |
| 初始化列表 | `: member_(value)` | ❌ 无等价 |
| `= default` | ✅ | ❌ 无等价（Java 自动生成默认构造函数） |
| `= delete` | ✅ 禁止拷贝构造 | ❌ 无等价（Java 不支持拷贝构造） |

**对比代码——初始化列表**：

```cpp
// C++: 成员初始化列表
EattChannel(RawAddress& bda, uint16_t cid, uint16_t tx_mtu, uint16_t rx_mtu)
    : bda_(bda),              // 初始化列表
      cid_(cid),
      rx_mtu_(rx_mtu),
      state_(EATT_CHANNEL_PENDING) {
  EattChannelSetTxMTU(tx_mtu);  // 函数体内额外逻辑
}
```

```java
// Java: 直接在构造函数体内赋值（没有初始化列表）
public EattChannel(RawAddress bda, int cid, int txMtu, int rxMtu) {
    this.bda = bda;           // 直接赋值
    this.cid = cid;
    this.rxMtu = rxMtu;
    this.state = EattChannelState.PENDING;
    setTxMTU(txMtu);          // 函数体内额外逻辑
}
```

**关键差异**：
- Java **没有成员初始化列表**。所有成员变量都在构造函数体内赋值。Java 不存在 C++ 中"先默认构造再赋值"的效率问题，因为 Java 的对象都是引用，赋值只是复制引用
- Java 中如果没写任何构造函数，编译器自动生成默认构造函数；如果写了带参构造函数，默认构造函数**不会**自动生成——这与 C++ 行为一致
- C++ 的 `= default` 和 `= delete` 在 Java 中没有等价语法。Java 不支持拷贝构造函数（对象赋值是引用赋值），也不需要显式删除

### 📌 本节小结

- 构造函数与类同名、无返回值，创建对象时自动调用
- 成员初始化列表 `: member_(value)` 比函数体内赋值更高效，const/引用成员必须用
- `= default` 显式要求编译器生成默认实现，`= delete` 禁止某个函数

---

## 3. 析构函数

### 3.1 什么是析构函数？

析构函数是对象**销毁时自动调用**的函数，用于清理资源（释放内存、关闭文件等）。

析构函数的特点：
- 函数名是 `~类名`（波浪号 + 类名）
- **没有参数**，**没有返回值**
- 每个类只能有**一个**析构函数
- 对象销毁时**自动执行**

### 3.2 真实示例：EattChannel 的析构函数

> 📄 来源：`system/stack/eatt/eatt.h` 第 75-83 行

```cpp
~EattChannel() {
  if (ind_ack_timer_ != NULL) {
    alarm_free(ind_ack_timer_);
  }

  if (ind_confirmation_timer_ != NULL) {
    alarm_free(ind_confirmation_timer_);
  }
}
```

**逐行解读**：

1. `~EattChannel()` —— 析构函数，名字是 `~` + 类名
2. `if (ind_ack_timer_ != NULL)` —— 检查定时器指针是否为空
3. `alarm_free(ind_ack_timer_);` —— 如果不为空，释放定时器占用的内存
4. 同样处理 `ind_confirmation_timer_`

**为什么需要析构函数？**

`EattChannel` 在构造时（或后续 `EattChannelSetState` 中）通过 `alarm_new()` 分配了定时器内存。如果对象销毁时不释放这些内存，就会造成**内存泄漏**。析构函数确保了"谁分配，谁释放"。

### 3.3 资源释放时机

对象在以下情况会被销毁，析构函数自动调用：
- 局部对象离开作用域时
- `delete` 动态分配的对象时
- 对象作为成员，其所属对象被销毁时

### 3.4 `virtual ~` vs 非 virtual 析构

**虚析构函数**（`virtual ~ClassName()`）用于通过基类指针删除派生类对象的场景：

> 📄 来源：`system/stack/eatt/eatt.h` 第 115 行

```cpp
virtual ~EattExtension();
```

> 📄 来源：`system/gd/hci/controller.h` 第 36 行

```cpp
virtual ~Controller() = default;
```

**什么时候用虚析构？**

```
如果类可能被继承，且会通过基类指针删除对象 → 必须用 virtual ~
如果类不会被继承（比如 final 类） → 不需要 virtual
```

**为什么？** 如果基类的析构函数不是 `virtual`，通过基类指针 `delete` 派生类对象时，只会调用基类的析构函数，派生类的析构函数不会被调用，导致资源泄漏。

**对比**：

| 析构函数类型 | 适用场景 | 示例 |
|-------------|---------|------|
| `~EattChannel()` | 不被继承的类 | eatt.h:75 |
| `virtual ~EattExtension()` | 会被继承的接口类 | eatt.h:115 |
| `virtual ~Controller() = default` | 会被继承的接口类 | controller.h:36 |

### ☕ Java 类比

| 特性 | C++ 析构函数 | Java |
|------|------------|------|
| 语法 | `~ClassName()` | `protected void finalize()`（已废弃） |
| 调用时机 | 对象销毁时**确定**调用 | GC 回收时**不确定**是否调用 |
| RAII | ✅ 核心资源管理模式 | ❌ 无等价 |
| 替代方案 | — | `try-with-resources` + `AutoCloseable` |
| 虚析构函数 | `virtual ~ClassName()` | ❌ 不需要（GC 管理） |

**对比代码——RAII vs try-with-resources**：

```cpp
// C++: RAII —— 析构函数自动释放资源
{
    EattChannel channel(bda, cid, tx_mtu, rx_mtu);
    // 使用 channel...
    // 离开作用域，~EattChannel() 自动调用，释放定时器
}  // ← 自动清理，无需手动操作
```

```java
// Java: try-with-resources —— 实现 AutoCloseable 接口
try (EattChannel channel = new EattChannel(bda, cid, txMtu, rxMtu)) {
    // 使用 channel...
}  // ← channel.close() 自动调用

// 或者手动管理（不推荐）
EattChannel channel = new EattChannel(bda, cid, txMtu, rxMtu);
try {
    // 使用 channel...
} finally {
    channel.close();  // 必须手动关闭
}
```

**关键差异**：
- Java **没有析构函数**。`finalize()` 方法在 Java 9 中已被标记为废弃，因为它的调用时机不可预测
- C++ 的 **RAII（Resource Acquisition Is Initialization）** 是 C++ 最重要的资源管理模式：资源获取在构造函数中，释放 在析构函数中，确保资源不会泄漏。Java 没有等价机制，需要用 `try-with-resources` + `AutoCloseable` 接口来手动管理
- C++ 需要**虚析构函数**是因为通过基类指针 `delete` 派生类对象时，必须正确调用派生类的析构函数。Java 有 GC，不需要手动 `delete`，所以不存在这个问题

### 📌 本节小结

- 析构函数 `~ClassName()` 在对象销毁时自动调用，用于释放资源（RAII 核心）
- 会被继承的类必须用 `virtual ~` 析构函数，否则通过基类指针 delete 派生类对象会导致内存泄漏
- Java 没有 RAII，用 `try-with-resources` + `AutoCloseable` 替代

---

## 4. this 指针

### 4.1 什么是 this 指针？

`this` 是一个隐含的指针，每个非静态成员函数内部都有一个 `this` 指针，指向**调用该函数的那个对象本身**。

你可以把 `this` 理解为"我自己"——对象说"this 就是我"。

### 4.2 this->member 语法

```cpp
this->成员变量名
this->成员函数名(参数)
```

### 4.3 什么时候必须用 this？

**最常见的情况：参数名与成员变量名冲突时**。

### 4.4 真实示例

> 📄 来源：`system/stack/eatt/eatt.h` 第 102-105 行

```cpp
void EattChannelSetTxMTU(uint16_t tx_mtu) {
  this->tx_mtu_ = std::min<uint16_t>(tx_mtu, EATT_MAX_TX_MTU);
  this->tx_mtu_ = std::max<uint16_t>(tx_mtu, EATT_MIN_MTU_MPS);
}
```

**逐行解读**：

1. 函数参数叫 `tx_mtu`，成员变量叫 `tx_mtu_`
2. `this->tx_mtu_` 明确表示"这是成员变量"
3. 没加 `this->` 的 `tx_mtu` 是函数参数
4. 如果不写 `this->`，`tx_mtu_` 由于末尾有下划线，与 `tx_mtu` 不同名，其实可以省略 `this->`

**另一种必须用 this 的场景**：

> 📄 来源：`system/stack/eatt/eatt_impl.h` 第 150 行

```cpp
eatt_device* eatt_dev = this->find_device_by_address(bda);
```

这里 `this->` 用来调用当前对象的成员函数，虽然在类内部可以省略，但有时为了代码清晰度会显式写出。

**总结**：

| 场景 | 是否必须用 this |
|------|---------------|
| 参数名与成员变量同名 | ✅ 必须 |
| 参数名与成员变量不同名（如 `tx_mtu_`） | ❌ 可省略 |
| 调用自己的成员函数 | ❌ 可省略 |
| 链式调用返回自身 `return *this;` | ✅ 必须 |
| 将自身传给其他函数 | ✅ 必须 |

### ☕ Java 类比

| 特性 | C++ `this` | Java `this` |
|------|-----------|------------|
| 类型 | 指针（`ClassName*`） | 引用（`ClassName`） |
| 访问成员 | `this->member` | `this.member` |
| 解引用 | `*this` 返回对象本身 | `this` 本身就是对象引用 |
| 可以为 null | ❌ 不可能 | ❌ 不可能 |

**对比代码**：

```cpp
// C++: this 是指针，用 -> 访问成员
void EattChannelSetTxMTU(uint16_t tx_mtu) {
    this->tx_mtu_ = std::min<uint16_t>(tx_mtu, EATT_MAX_TX_MTU);
}
// 返回自身：return *this;
```

```java
// Java: this 是引用，用 . 访问成员
public void setTxMTU(int txMtu) {
    this.txMtu = Math.min(txMtu, EATT_MAX_TX_MTU);
}
// 返回自身：return this;
```

**关键差异**：
- C++ 的 `this` 是**指针**，需要用 `->` 访问成员或 `*this` 解引用。Java 的 `this` 是**引用**，直接用 `.` 访问成员
- 两者都不能为 null，都指向调用方法的当前对象
- 用法场景完全一致：区分参数和成员变量同名、链式调用返回自身、将自身传给其他函数

### 📌 本节小结

- `this` 是隐含的指针，指向调用成员函数的对象本身
- 参数名与成员变量同名时必须用 `this->` 区分；不同名时可省略
- C++ 的 `this` 是指针（用 `->`），Java 的 `this` 是引用（用 `.`）

---

## 5. const 成员函数

### 5.1 语法

在成员函数的参数列表后面加上 `const`：

```cpp
返回值类型 函数名(参数列表) const {
  // 函数体
}
```

### 5.2 const 成员函数的含义

`const` 成员函数承诺：**不会修改任何成员变量的值**。

如果你在 `const` 成员函数里尝试修改成员变量，编译器会报错！

### 5.3 为什么需要 const 成员函数？

当你有一个 `const` 对象时，只能调用 `const` 成员函数：

```cpp
const RawAddress addr;
addr.IsEmpty();    // OK，IsEmpty() 是 const 函数
addr.ToString();   // OK，ToString() 也是 const 函数
// addr.SomeMutatingFunction();  // 错误！const 对象不能调用非 const 函数
```

### 5.4 真实示例一：RawAddress::IsEmpty()

> 📄 来源：`system/types/include/bluetooth/types/address.h` 第 43 行

```cpp
bool IsEmpty() const { return *this == kEmpty; }
```

**解读**：
- `bool IsEmpty() const` —— 这是一个 const 成员函数，返回 `bool` 类型
- 它判断当前地址是否为空地址
- 因为只是"查看"而不"修改"，所以标记为 `const`
- 函数体直接写在类定义内，自动成为内联函数

### 5.5 真实示例二：Uuid 类的 const 成员函数

> 📄 来源：`system/types/include/bluetooth/types/uuid.h` 第 52-105 行

```cpp
size_t GetShortestRepresentationSize() const;   // 获取最短表示大小
bool Is16Bit() const;                           // 是否是 16 位 UUID
uint16_t As16Bit() const;                       // 转为 16 位表示
uint32_t As32Bit() const;                       // 转为 32 位表示
const UUID128Bit To128BitLE() const;            // 转为 128 位 LE 表示
const UUID128Bit& To128BitBE() const;           // 转为 128 位 BE 表示
std::string ToString() const;                   // 转为字符串
bool IsEmpty() const;                           // 是否为空
bool IsBase() const;                            // 是否为基础 UUID
bool operator<(const Uuid& rhs) const;          // 小于比较
bool operator==(const Uuid& rhs) const;         // 等于比较
bool operator!=(const Uuid& rhs) const;         // 不等于比较
```

**观察规律**：所有"查询/获取"类操作都是 `const` 的，因为它们不修改对象状态。

### 5.6 真实示例三：Controller::Dump()

> 📄 来源：`system/gd/hci/controller.h` 第 40 行

```cpp
virtual void Dump(int /*fd*/) const {}
```

**解读**：
- `virtual` —— 虚函数，子类可以重写
- `void Dump(int /*fd*/) const` —— const 虚成员函数
- `/*fd*/` —— 参数名被注释掉，表示这个参数在函数体内未使用
- `{}` —— 空的默认实现
- `const` —— 转储调试信息不应该修改对象状态

### 5.7 const 与非 const 对比

| 函数类型 | 能否修改成员变量 | const 对象能否调用 |
|---------|---------------|------------------|
| 普通成员函数 | ✅ 能 | ❌ 不能 |
| const 成员函数 | ❌ 不能 | ✅ 能 |

### ☕ Java 类比

| 特性 | C++ `const` 成员函数 | Java |
|------|-------------------|------|
| 语法 | `void Foo() const;` | ❌ **无等价语法** |
| 编译器强制检查 | ✅ 修改成员变量编译报错 | ❌ 无此机制 |
| const 对象限制 | 只能调用 const 成员函数 | ❌ 无此概念 |

**Java 为什么不需要 const 成员函数？**

Java 没有与 C++ `const` 成员函数等价的语法。Java 程序员通过以下方式替代：

1. **不可变类设计**：将类设计为不可变（所有字段 `private final`，无 setter 方法），如 Java 的 `String` 类
2. **防御性拷贝**：返回可变字段时返回副本，而不是原对象
3. **接口约束**：通过只读接口（只有 getter 的接口）来限制修改

```cpp
// C++: const 成员函数，编译器强制保证不修改对象
class Uuid final {
public:
    bool IsEmpty() const;      // 承诺不修改对象
    uint16_t As16Bit() const;  // 承诺不修改对象
    void SetData(...);         // 非 const，可能修改对象
};

const Uuid uuid = Uuid::From16Bit(0x180F);
uuid.IsEmpty();    // ✅ 可以调用 const 函数
// uuid.SetData(); // ❌ 编译错误！const 对象不能调用非 const 函数
```

```java
// Java: 没有语法约束，只能通过设计约定
public final class Uuid {
    public boolean isEmpty() { ... }       // 无法声明"不修改对象"
    public int as16Bit() { ... }           // 无法声明"不修改对象"
    public void setData(...) { ... }       // 无法区分"只读"和"修改"方法
}

// 替代方案：提供只读接口
public interface ReadOnlyUuid {
    boolean isEmpty();
    int as16Bit();
    // 没有 setData()
}
public final class Uuid implements ReadOnlyUuid {
    // ...
}
```

**关键差异**：
- C++ 的 `const` 成员函数是**编译器强制执行**的约束，Java 只能通过**设计模式**来模拟
- C++ 中 `const` 对象只能调用 `const` 成员函数，Java 没有这种限制
- 这是 C++ 在类型安全方面优于 Java 的一个重要特性

### 📌 本节小结

- `const` 成员函数承诺不修改对象状态，编译器强制检查
- `const` 对象只能调用 `const` 成员函数
- Java 没有等价语法，只能通过不可变类设计或只读接口来模拟

---

## 6. static 成员

### 6.1 static 成员变量

`static` 成员变量属于**类本身**，而不是某个具体的对象。所有对象共享同一个 static 变量。

**类比**：
- 普通成员变量 = 每个人的银行卡余额（每人不同）
- static 成员变量 = 银行利率（所有人共享同一个值）

### 6.2 static 成员函数

`static` 成员函数也属于**类本身**，不需要创建对象就能调用。

```cpp
类名::静态函数名(参数);
```

### 6.3 真实示例一：Uuid 的 static constexpr 成员

> 📄 来源：`system/types/include/bluetooth/types/uuid.h` 第 38-43 行

```cpp
class Uuid final {
public:
  static constexpr size_t kNumBytes128 = 16;    // 128 位 UUID 的字节数
  static constexpr size_t kNumBytes32 = 4;      // 32 位 UUID 的字节数
  static constexpr size_t kNumBytes16 = 2;      // 16 位 UUID 的字节数
  static constexpr size_t kString128BitLen = 36; // 128 位 UUID 字符串长度

  static const Uuid kEmpty;                     // 空的 UUID 对象
```

**解读**：
- `static` —— 这些成员属于 `Uuid` 类本身，不属于某个 `Uuid` 对象
- `constexpr` —— 常量表达式，编译期就能确定值
- `kNumBytes128 = 16` —— 128 位 UUID 占 16 个字节，这是固定的常识
- `kEmpty` —— 一个共享的"空 UUID"常量对象

**使用方式**：

```cpp
// 不需要创建 Uuid 对象，直接用类名访问
size_t bytes = Uuid::kNumBytes128;  // 值为 16
```

### 6.4 真实示例二：RawAddress 的 static 成员

> 📄 来源：`system/types/include/bluetooth/types/address.h` 第 58-68 行

```cpp
class RawAddress final {
public:
  // static 成员函数 —— 不需要对象就能调用
  static std::optional<RawAddress> FromString(const std::string& from);
  static RawAddress FromOctets(const uint8_t* from);
  static bool IsValidAddress(const std::string& address);

  // static 成员变量 —— 所有对象共享
  static constexpr unsigned int kLength = 6;   // 蓝牙地址长度固定为 6 字节
  static const RawAddress kEmpty;              // 00:00:00:00:00:00
  static const RawAddress kAny;                // FF:FF:FF:FF:FF:FF
};
```

**解读**：
- `kLength = 6` —— 蓝牙地址永远是 6 字节，这是蓝牙协议规定的，所以是类级别的常量
- `kEmpty` —— 全局共享的"空地址"对象
- `kAny` —— 全局共享的"任意地址"对象
- `FromString()` —— 工厂函数，从字符串创建地址对象，不需要先有对象

**使用方式**：

```cpp
// 从字符串解析地址（不需要先创建对象）
auto addr = RawAddress::FromString("12:34:56:ab:cd:ef");

// 使用共享常量
if (addr == RawAddress::kEmpty) {
  // 地址为空
}
```

### 6.5 真实示例三：EattExtension::GetInstance() —— 单例模式

> 📄 来源：`system/stack/eatt/eatt.h` 第 117-120 行

```cpp
static EattExtension* GetInstance() {
  static EattExtension* instance = new EattExtension();
  return instance;
}
```

**这是经典的单例模式（Singleton Pattern）！**

**逐行解读**：

1. `static EattExtension* GetInstance()` —— 静态成员函数，返回 `EattExtension*` 指针
2. `static EattExtension* instance = new EattExtension();` —— 函数内的 `static` 局部变量
   - 只在第一次调用时创建
   - 后续调用返回同一个对象
3. `return instance;` —— 返回唯一的实例

**为什么用单例？**

EATT 扩展模块在整个蓝牙栈中只需要一个实例。用单例模式可以：
- 保证全局只有一个实例
- 提供全局访问点
- 避免重复创建

**使用方式**：

```cpp
// 获取唯一的 EattExtension 实例
EattExtension* eatt = EattExtension::GetInstance();
eatt->Connect(device_address);
```

**注意**：函数内的 `static` 局部变量和类的 `static` 成员变量是不同的概念：
- 类的 `static` 成员变量：属于类，所有对象共享
- 函数内的 `static` 局部变量：只在第一次执行时初始化，之后保持值不变

### 6.6 static 成员总结

| 类型 | 关键字 | 属于 | 访问方式 |
|------|--------|------|----------|
| static 成员变量 | `static` | 类 | `类名::变量名` |
| static 成员函数 | `static` | 类 | `类名::函数名()` |
| 普通成员变量 | 无 | 对象 | `对象.变量名` |
| 普通成员函数 | 无 | 对象 | `对象.函数名()` |

### ☕ Java 类比

| 特性 | C++ `static` 成员 | Java `static` 成员 |
|------|------------------|-------------------|
| 静态成员变量 | `static constexpr size_t kNumBytes128 = 16;` | `public static final int K_NUM_BYTES_128 = 16;` |
| 静态成员函数 | `static Uuid From16Bit(uint16_t);` | `public static Uuid from16Bit(int);` |
| 访问方式 | `类名::成员` | `类名.成员` |
| 静态方法中访问实例成员 | ❌ 不可以（无 `this`） | ❌ 不可以（无 `this`） |

**对比代码**：

```cpp
// C++: static 成员
class Uuid final {
public:
    static constexpr size_t kNumBytes128 = 16;  // 类内初始化
    static const Uuid kEmpty;                     // 类内声明，类外定义
    static Uuid From16Bit(uint16_t uuid16bit);   // 静态工厂函数
};
// 访问：Uuid::kNumBytes128, Uuid::From16Bit(0x180F)
```

```java
// Java: static 成员
public final class Uuid {
    public static final int K_NUM_BYTES_128 = 16;  // 直接初始化
    public static final Uuid K_EMPTY = new Uuid();  // 直接创建
    public static Uuid from16Bit(int uuid16bit) { ... }  // 静态工厂方法
}
// 访问：Uuid.K_NUM_BYTES_128, Uuid.from16Bit(0x180F)
```

**关键差异**：
- C++ 的 `static` 成员变量通常需要在**类外定义**（除了 `static constexpr` 整型可以在类内初始化），Java 的 `static` 成员可以直接在类内初始化
- 访问语法不同：C++ 用 `::`，Java 用 `.`
- 语义完全一致：都属于类而非对象，所有实例共享，静态方法没有 `this`

### 📌 本节小结

- `static` 成员变量属于类，所有对象共享；`static` 成员函数无 `this` 指针
- 函数内 `static` 局部变量只初始化一次，常用于单例模式
- 访问方式：C++ 用 `::`，Java 用 `.`

---

## 7. final 关键字

### 7.1 class final —— 禁止继承

在类名后面加 `final`，表示这个类**不能被继承**：

```cpp
class 类名 final {
  // ...
};
```

如果有人尝试继承 `final` 类，编译器会报错。

### 7.2 为什么要禁止继承？

- 设计上不希望被扩展（比如值类型、简单数据封装）
- 避免继承带来的复杂性
- 编译器可以对 `final` 类做优化（不需要虚函数表）

### 7.3 真实示例一：Uuid final

> 📄 来源：`system/types/include/bluetooth/types/uuid.h` 第 36 行

```cpp
class Uuid final {
```

**解读**：`Uuid` 是一个表示蓝牙 UUID 的值类型，设计者认为 UUID 的行为是固定的，不需要通过继承来扩展，所以标记为 `final`。

### 7.4 真实示例二：RawAddress final

> 📄 来源：`system/types/include/bluetooth/types/address.h` 第 29 行

```cpp
class RawAddress final {
```

**解读**：`RawAddress` 是一个简单的蓝牙地址封装，6 字节数据加上一些工具函数，不需要继承扩展。

### 7.5 final 与 non-final 对比

| 类 | 是否 final | 是否有 virtual 函数 | 设计意图 |
|----|-----------|-------------------|---------|
| `RawAddress final` | ✅ 是 | ❌ 无 | 值类型，不需要继承 |
| `Uuid final` | ✅ 是 | ❌ 无 | 值类型，不需要继承 |
| `EattExtension` | ❌ 否 | ✅ 有 | 接口类，需要被继承 |
| `Controller` | ❌ 否 | ✅ 有 | 接口类，需要被继承 |

**规律**：有 `virtual` 函数的类通常不应该是 `final`，因为虚函数的目的就是让子类重写。

### ☕ Java 类比

| 特性 | C++ `final` | Java `final` |
|------|-----------|------------|
| 禁止类被继承 | `class Uuid final { };` | `public final class Uuid { }` |
| 禁止方法被重写 | `void foo() final;` | `public final void foo() { }` |
| 修饰变量 | ❌ 不用 `final`（用 `const`） | `final int x = 10;`（不可重新赋值） |

**对比代码**：

```cpp
// C++: final 放在类名后面
class Uuid final {       // 禁止继承
    // ...
};

// C++: final 放在成员函数声明后
class Base {
    virtual void foo() final;  // 禁止子类重写此虚函数
};
```

```java
// Java: final 放在 class 关键字前面
public final class Uuid {  // 禁止继承
    // ...
}

// Java: final 放在方法返回类型前面
public class Base {
    public final void foo() { }  // 禁止子类重写此方法
}
```

**关键差异**：
- C++ 的 `final` 放在**类名后面**或**函数声明末尾**，Java 的 `final` 放在**`class`/返回类型前面**
- Java 的 `final` 用途更广：还能修饰变量（不可重新赋值）、方法参数（方法内不可修改）。C++ 的 `final` 只用于类和虚函数
- C++ 中禁止变量重新赋值用 `const`，Java 中用 `final`——同一个关键字在两种语言中含义不同

### 📌 本节小结

- `class Name final` 禁止类被继承，`void foo() final` 禁止虚函数被重写
- 有 `virtual` 函数的类通常不应该是 `final`，值类型（如 `Uuid`、`RawAddress`）适合用 `final`
- C++ 的 `final` 只用于类和虚函数，Java 的 `final` 还能修饰变量

---

## 8. 内联函数 inline

### 8.1 什么是内联函数？

内联函数是建议编译器**将函数代码直接嵌入调用处**，而不是进行传统的函数调用（压栈、跳转、返回）。这样可以减少函数调用的开销，适合简短的函数。

### 8.2 定义在类内的函数自动内联

如果成员函数的函数体直接写在类定义内部，它就**自动成为内联函数**：

> 📄 来源：`system/types/include/bluetooth/types/address.h` 第 36-43 行

```cpp
class RawAddress final {
public:
  // 这些函数定义在类内部，自动内联
  bool operator<(const RawAddress& rhs) const { return address < rhs.address; }
  bool operator==(const RawAddress& rhs) const { return address == rhs.address; }
  bool operator>(const RawAddress& rhs) const { return rhs < *this; }
  bool operator<=(const RawAddress& rhs) const { return !(*this > rhs); }
  bool operator>=(const RawAddress& rhs) const { return !(*this < rhs); }
  bool operator!=(const RawAddress& rhs) const { return !(*this == rhs); }
  bool IsEmpty() const { return *this == kEmpty; }
};
```

这些比较函数都很简短（一行代码），适合内联。

### 8.3 显式 inline

如果函数定义在类外部（比如在头文件中但不在类定义内），需要用 `inline` 关键字：

> 📄 来源：`system/gd/os/handler.h` 第 40-44 行

```cpp
inline auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
  return a.first > b.first;
};
```

**解读**：
- `inline` —— 显式声明为内联
- `auto` —— 让编译器自动推导类型
- `[...]` —— Lambda 表达式（匿名函数）
- 这个比较器用于优先队列，会被频繁调用，内联可以提高性能

### 8.4 另一个显式 inline 示例

> 📄 来源：`system/types/include/bluetooth/types/address.h` 第 83-87 行

```cpp
inline void BDADDR_TO_STREAM(uint8_t*& p, const RawAddress& a) {
  for (int ijk = 0; ijk < BD_ADDR_LEN; ijk++) {
    *(p)++ = a.address[BD_ADDR_LEN - 1 - ijk];
  }
}
```

**解读**：
- `inline void BDADDR_TO_STREAM(...)` —— 显式内联函数
- 这是一个工具函数，将蓝牙地址写入数据流
- 因为在头文件中定义且不在类内部，必须加 `inline` 避免多重定义错误

### 8.5 inline 使用建议

| 情况 | 建议 |
|------|------|
| 函数体在类定义内 | 自动内联，不需要加 `inline` |
| 函数体在头文件但类定义外 | 加 `inline` |
| 函数体在 .cpp 文件中 | 不需要 `inline`（加了也没用） |
| 函数很长（超过 10 行） | 不建议内联 |
| 函数很短（1-3 行） | 建议内联 |

### ☕ Java 类比

| 特性 | C++ `inline` | Java |
|------|-------------|------|
| `inline` 关键字 | ✅ 显式声明 | ❌ **没有 `inline` 关键字** |
| 类内定义自动内联 | ✅ 函数体在类内则自动 inline | ❌ 无此概念 |
| 内联决策 | 程序员建议 + 编译器决定 | **JIT 编译器自动决定** |

**Java 为什么不需要 `inline` 关键字？**

- Java 的 **JIT（Just-In-Time）编译器**会在运行时自动将频繁调用的短方法内联，不需要程序员手动标记
- Java 没有"头文件/源文件分离"的问题，不存在 C++ 中 `inline` 避免多重定义的需求
- C++ 的 `inline` 除了性能提示外，还有**链接语义**：允许同一函数在多个编译单元中定义而不报重复定义错误。Java 没有这种编译模型

```cpp
// C++: 显式 inline，避免头文件多重定义
inline void BDADDR_TO_STREAM(uint8_t*& p, const RawAddress& a) {
    for (int ijk = 0; ijk < BD_ADDR_LEN; ijk++) {
        *(p)++ = a.address[BD_ADDR_LEN - 1 - ijk];
    }
}
```

```java
// Java: 不需要 inline，JIT 自动优化
public static void bdaddrToStream(byte[] p, RawAddress a) {
    for (int i = 0; i < BD_ADDR_LEN; i++) {
        p[i] = a.address[BD_ADDR_LEN - 1 - i];
    }
}
```

**关键差异**：
- C++ 的 `inline` 是**编译期**优化提示，Java 的方法内联是 **JIT 运行期**自动优化
- C++ 程序员需要关心 `inline` 的放置位置（头文件 vs 源文件），Java 程序员完全不需要
- Java 的 JIT 内联甚至比 C++ 的 `inline` 更智能：它可以根据运行时 profiling 数据决定是否内联

### 📌 本节小结

- 函数体写在类定义内自动内联；写在头文件类外需加 `inline`
- `inline` 是对编译器的建议，编译器可以忽略
- Java 没有 `inline` 关键字，JIT 编译器自动决定方法内联

---

## 9. 嵌套类型与内部定义

### 9.1 什么是嵌套类型？

在类内部定义的类型（`using` 别名、`struct`、`enum`、`class` 等），属于该类的作用域。

**好处**：
- 逻辑上相关的类型放在一起
- 避免全局命名空间污染
- 体现类型之间的从属关系

### 9.2 真实示例一：Uuid 内部的类型别名

> 📄 来源：`system/types/include/bluetooth/types/uuid.h` 第 46 行

```cpp
class Uuid final {
public:
  static constexpr size_t kNumBytes128 = 16;
  using UUID128Bit = std::array<uint8_t, kNumBytes128>;
  // ...
};
```

**逐行解读**：

1. `using UUID128Bit = std::array<uint8_t, kNumBytes128>;`
   - `using` 是 C++11 引入的类型别名语法（替代旧的 `typedef`）
   - `UUID128Bit` 是 `std::array<uint8_t, 16>` 的别名
   - 含义：128 位 UUID 就是一个 16 字节的数组

2. `kNumBytes128` 在同一个类中定义，`UUID128Bit` 可以直接引用它

**使用方式**：

```cpp
// 使用嵌套类型
Uuid::UUID128Bit my_uuid_bytes;  // 等价于 std::array<uint8_t, 16>
```

**对比旧语法**：

```cpp
// C++11 之前（typedef）
typedef std::array<uint8_t, 16> UUID128Bit;

// C++11 之后（using，推荐）
using UUID128Bit = std::array<uint8_t, 16>;
```

`using` 的优势：更直观，尤其是定义模板别名时。

### 9.3 真实示例二：Controller 内部的 VendorCapabilities

> 📄 来源：`system/gd/hci/controller.h` 第 194-213 行

```cpp
class Controller {
public:
  // ... 其他成员 ...

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

  virtual VendorCapabilities GetVendorCapabilities() const = 0;
};
```

**解读**：

1. `struct VendorCapabilities` 定义在 `Controller` 类内部
2. 它描述了蓝牙控制器厂商特有的能力信息
3. 因为"厂商能力"是"控制器"的子概念，所以嵌套在 `Controller` 内
4. `GetVendorCapabilities()` 返回这个嵌套类型

**使用方式**：

```cpp
Controller::VendorCapabilities caps = controller->GetVendorCapabilities();
uint8_t max_advt = caps.max_advt_instances_;
```

### 9.4 真实示例三：EattExtension 内部的 impl 前置声明

> 📄 来源：`system/stack/eatt/eatt.h` 第 283-285 行

```cpp
class EattExtension {
  // ...
private:
  struct impl;
  std::unique_ptr<impl> pimpl_;
};
```

**解读**：
- `struct impl;` —— 前置声明，只声明类型名，不定义内容
- `std::unique_ptr<impl> pimpl_;` —— 用智能指针管理 impl 对象
- 这是 **Pimpl 惯用法**（Pointer to Implementation），将实现细节隐藏在 .cpp 文件中

### 9.5 嵌套类型总结

| 嵌套类型 | 语法 | 示例来源 |
|---------|------|---------|
| 类型别名 | `using 别名 = 实际类型;` | uuid.h:46 |
| 嵌套结构体 | `struct 名称 { ... };` | controller.h:194 |
| 前置声明 | `struct 名称;` | eatt.h:284 |
| 嵌套枚举 | `enum class 名称 { ... };` | eatt.h:37-41 |

### 📌 本节小结

- 嵌套类型（`using` 别名、`struct`、`enum`）放在类内部，避免全局命名空间污染
- `using UUID128Bit = std::array<uint8_t, 16>` 比 `typedef` 更直观
- Pimpl 用 `struct impl;` 前置声明 + `unique_ptr<impl>` 隐藏实现

---

## 10. 实际阅读建议

### 10.1 如何从头文件快速理解一个类的功能

当你打开一个陌生的头文件，按以下步骤阅读：

**第一步：看类名和注释**

```cpp
/** Bluetooth Address */
class RawAddress final {
```

类名通常能告诉你这个类代表什么。注释会进一步说明。

**第二步：看 public 部分**

`public` 部分是类的"对外接口"，告诉你这个类能做什么：

```cpp
public:
  bool IsEmpty() const;              // 能判断是否为空
  std::string ToString() const;      // 能转为字符串
  static RawAddress FromString(...); // 能从字符串创建
```

**第三步：看 private 部分**

`private` 部分是类的"内部实现"，告诉你这个类用了什么数据：

```cpp
private:
  constexpr Uuid(const UUID128Bit& val) : uu{val} {}
  UUID128Bit uu;   // 内部就是一个 16 字节数组
```

### 10.2 如何从构造函数理解类的初始化需求

构造函数的参数和初始化列表告诉你：创建这个对象**必须提供什么**。

**示例**：`EattChannel` 的构造函数

```cpp
EattChannel(RawAddress& bda, uint16_t cid, uint16_t tx_mtu, uint16_t rx_mtu)
    : bda_(bda),              // 必须知道是哪个设备
      cid_(cid),              // 必须知道通道 ID
      rx_mtu_(rx_mtu),        // 必须知道接收 MTU
      state_(EattChannelState::EATT_CHANNEL_PENDING),  // 状态默认为 PENDING
      indicate_handle_(0),    // 指示句柄默认为 0
      ind_ack_timer_(NULL),   // 定时器默认为空
      ind_confirmation_timer_(NULL)  // 定时器默认为空
```

**解读**：
- 必须提供 4 个参数：设备地址、通道 ID、发送 MTU、接收 MTU
- 状态默认为 `PENDING`（刚创建的通道还在等待连接）
- 定时器默认为空（只有通道打开后才创建定时器）

### 10.3 如何从 public/private 分组理解接口和实现

**好的类设计**通常遵循以下模式：

```
class ClassName {
public:
  // 1. 类型别名和常量
  // 2. 构造函数和析构函数
  // 3. 核心操作函数
  // 4. 查询函数（const）
  // 5. 静态工厂函数

private:
  // 6. 内部辅助函数
  // 7. 成员变量
};
```

**以 `Uuid` 类为例**：

```cpp
class Uuid final {
public:
  // 1. 常量
  static constexpr size_t kNumBytes128 = 16;
  static const Uuid kEmpty;

  // 2. 类型别名
  using UUID128Bit = std::array<uint8_t, kNumBytes128>;

  // 3. 构造函数
  Uuid() = default;

  // 4. 查询函数（const）
  bool IsEmpty() const;
  bool Is16Bit() const;
  size_t GetShortestRepresentationSize() const;

  // 5. 转换函数（const）
  uint16_t As16Bit() const;
  std::string ToString() const;

  // 6. 静态工厂函数
  static Uuid FromString(const std::string& uuid, bool* is_valid = nullptr);
  static Uuid From16Bit(uint16_t uuid16bit);

  // 7. 运算符
  bool operator==(const Uuid& rhs) const;

private:
  // 8. 私有构造函数（限制创建方式）
  constexpr Uuid(const UUID128Bit& val) : uu{val} {}

  // 9. 成员变量
  UUID128Bit uu;
};
```

**设计亮点**：
- `Uuid()` = default 是公开的 → 允许创建默认 UUID
- `Uuid(const UUID128Bit&)` 是私有的 → 外部不能直接用字节数组创建
- 想创建 UUID？用 `From16Bit()`、`FromString()` 等工厂函数 → 保证创建的 UUID 是合法的
- 所有查询函数都是 `const` → UUID 一旦创建就不可变（不可变对象）

### 10.4 阅读顺序总结

```
1. 类名 + final/继承关系 → 这是什么？能被继承吗？
2. public 函数签名 → 这个类能做什么？
3. 构造函数 → 创建对象需要什么？
4. 析构函数 + virtual → 需要清理什么？是否多态？
5. static 成员 → 类级别的常量和工具
6. private 成员 → 内部数据结构
7. 嵌套类型 → 辅助类型定义
```

### 📌 本节小结

- 阅读类的顺序：类名 → public 函数 → 构造函数 → 析构函数 → static 成员 → private 成员
- 构造函数的参数和初始化列表告诉你创建对象必须提供什么
- 好的类设计：public 放接口，private 放数据和内部辅助

---

## 常见错误

1. **忘记初始化列表**：对 `const` 成员、引用成员、没有默认构造函数的类类型成员，不用初始化列表会编译错误
2. **忘记虚析构函数**：会被继承的类如果不写 `virtual ~`，通过基类指针 delete 派生类对象会导致内存泄漏
3. **忘记 `= default` / `= delete`**：定义了带参构造函数后默认构造函数不再自动生成，需要显式 `= default`；单例类需要 `= delete` 拷贝构造和赋值
4. **混淆 `this->` 和成员名**：参数名与成员变量不同名时 `this->` 可省略，同名时必须加；末尾下划线命名（如 `tx_mtu_`）可避免冲突

---

## 附录：本教程涉及的所有源文件索引

| 文件路径 | 关键内容 |
|---------|---------|
| `system/stack/eatt/eatt.h` | `EattChannel` 类（43-106行）、`EattExtension` 类（109-286行）、`EattChannelState` 枚举（37-41行） |
| `system/stack/eatt/eatt_impl.h` | `eatt_device` 类（49-63行）、`eatt_impl` 结构体（65-1012行） |
| `system/types/include/bluetooth/types/uuid.h` | `Uuid` 类（36-122行） |
| `system/types/include/bluetooth/types/address.h` | `RawAddress` 类（29-69行）、`BDADDR_TO_STREAM` 内联函数（83-87行） |
| `system/gd/hci/controller.h` | `Controller` 类（28-226行）、`VendorCapabilities` 嵌套结构体（194-213行） |
| `system/gd/os/handler.h` | `compare_task_by_time` 内联 Lambda（40-44行）、`Handler` 类（57-137行） |

---

## 速查卡

| 语法 | 用途 | 示例 | Java类比 |
|------|------|------|----------|
| `class` | 定义类 | `class EattChannel { ... };` | `class` |
| 构造函数 | 初始化对象 | `EattChannel(RawAddress& bda, uint16_t cid);` | 同名构造方法 |
| 析构函数 | 释放资源 | `~EattChannel();` | `finalize()`（已废弃） |
| `this` | 指向当前对象 | `this->tx_mtu_ = value;` | `this.txMtu = value;` |
| `const` 成员函数 | 承诺不修改对象 | `bool IsEmpty() const;` | ❌ 无等价 |
| `static` 成员 | 属于类而非对象 | `static Uuid From16Bit(uint16_t);` | `static` 成员 |
| `final` | 禁止继承/重写 | `class Uuid final { ... };` | `final class Uuid` |
| `inline` | 建议内联展开 | `inline void BDADDR_TO_STREAM(...);` | ❌ JIT自动优化 |
