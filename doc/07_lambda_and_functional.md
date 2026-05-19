# Lambda 表达式与函数式编程 —— 让 C++ 代码更简洁、更强大

> **基于 Android 蓝牙协议栈 (Fluoride) 真实代码的 C++ 教材**
>
> 目标读者：对 Lambda 表达式完全不了解的 C++ 初学者

---

## 目录

1. [什么是 Lambda 表达式](#1-什么是-lambda-表达式)
2. [Lambda 基础语法](#2-lambda-基础语法)
3. [捕获列表 (Capture) 详解](#3-捕获列表-capture-详解)
4. [Lambda 与 STL 算法结合](#4-lambda-与-stl-算法结合)
5. [Lambda 作为变量存储](#5-lambda-作为变量存储)
6. [Lambda 作为回调函数](#6-lambda-作为回调函数)
7. [泛型 Lambda (C++14)](#7-泛型-lambda-c14)
8. [Lambda 与 priority_queue](#8-lambda-与-priority_queue)
9. [常见陷阱与最佳实践](#9-常见陷阱与最佳实践)

---

## 1. 什么是 Lambda 表达式

### 1.1 从一个实际问题出发

假设你在蓝牙协议栈中维护一个设备列表，想找出某个特定逻辑通道标识符 (LCID) 对应的设备。如果不用 Lambda，你需要这样写：

```cpp
// 传统方式：定义一个单独的函数或函数对象
struct FindByLcid {
    uint16_t target_lcid;
    FindByLcid(uint16_t lcid) : target_lcid(lcid) {}

    bool operator()(const eatt_device& ed) const {
        auto it = ed.eatt_channels.find(target_lcid);
        return it != ed.eatt_channels.end();
    }
};

// 使用时
auto iter = std::find_if(devices_.begin(), devices_.end(), FindByLcid(lcid));
```

你需要定义一个完整的结构体，写构造函数，重载 `operator()`……仅仅是为了一个简单的查找逻辑！而且这个结构体可能只在一个地方用到，却占据了十几行代码。

**Lambda 表达式**就是解决这个问题的——它让你能在需要函数的地方，直接"就地"写一个匿名函数：

```cpp
// Lambda 方式：直接在调用处写出逻辑
auto iter = std::find_if(devices_.begin(), devices_.end(),
    [&lcid](const eatt_device& ed) {
        auto it = ed.eatt_channels.find(lcid);
        return it != ed.eatt_channels.end();
    });
```

三行代码，清晰明了，逻辑就在使用的地方，不需要跳转到别处去看定义。

### 1.2 Lambda 的本质

Lambda 表达式本质上就是**一个匿名的函数对象**。编译器在背后为你生成了一个类似上面 `FindByLcid` 的类，重载了 `operator()`。你不需要手写这个类，编译器帮你做了。

理解这一点很重要：Lambda 不是什么黑魔法，它只是编译器帮你自动生成函数对象的**语法糖**。

### ☕ Java 类比

Java 8 (2014) 引入了 Lambda 表达式，与 C++11 (2011) 的 Lambda 功能相似，但语法和捕获机制不同：

| 对比项 | C++ Lambda | Java Lambda |
|--------|------------|-------------|
| 语法 | `[capture](params) { body }` | `(params) -> { body }` |
| 类型 | 编译器生成的唯一匿名类 | 函数式接口的实现 |
| 捕获列表 | 显式指定 `[=]`, `[&]`, `[var]` | 自动捕获（effective final） |
| 修改捕获变量 | `[&var]` 或 `[var] mutable` | 不允许（变量必须是 effectively final） |
| 无参无返回 | `[](){}` | `() -> {}` |
| 类型推断 | 返回类型可自动推导 | 函数式接口决定签名 |

**C++ Lambda 示例：**

```cpp
auto iter = std::find_if(devices.begin(), devices.end(),
    [&lcid](const eatt_device& ed) {
        auto it = ed.eatt_channels.find(lcid);
        return it != ed.eatt_channels.end();
    });
```

**Java Lambda 示例：**

```java
var iter = devices.stream()
    .filter(ed -> ed.getChannels().containsKey(lcid))
    .findFirst();
// Java 自动捕获 lcid（必须是 effectively final）
```

> **关键区别**：C++ 需要显式声明捕获列表，精确控制每个变量是按值还是按引用捕获。Java 自动捕获，但要求变量是 effectively final（不可修改），更安全但灵活性较低。

---

## 2. Lambda 基础语法

### 2.1 完整语法形式

一个 Lambda 表达式的完整语法如下：

```
[capture](parameters) mutable -> return_type { body }
```

各部分含义：

| 部分 | 含义 | 是否必须 |
|------|------|----------|
| `[capture]` | 捕获列表，决定如何使用外部变量 | **必须**（可以为空 `[]`） |
| `(parameters)` | 参数列表，和普通函数一样 | **必须**（可以为空 `()`） |
| `mutable` | 允许修改按值捕获的变量 | 可选 |
| `-> return_type` | 尾置返回类型 | 可选 |
| `{ body }` | 函数体 | **必须** |

### 2.2 最简形式

最简单的 Lambda 什么都不做：

```cpp
[](){}   // 不捕获任何变量，没有参数，函数体为空
```

虽然看起来没什么用，但它是一个合法的 Lambda 表达式。让我们逐步增加内容：

```cpp
// 第一步：最简形式
[](){}

// 第二步：加上参数
[](int x, int y){}

// 第三步：加上函数体
[](int x, int y) { return x + y; }

// 第四步：加上返回类型（通常可省略，编译器自动推导）
[](int x, int y) -> int { return x + y; }

// 第五步：加上捕获列表
[z = 10](int x, int y) -> int { return x + y + z; }
```

### 2.3 各部分详解

#### 参数列表 `(parameters)`

和普通函数的参数列表完全一样：

```cpp
// 无参数
[]() { std::cout << "Hello"; };

// 有参数
[](int a, int b) { return a + b; };

// 有参数，带 const 引用（在蓝牙协议栈中极为常见）
[](const eatt_device& ed) { return ed.bda_ == some_addr; };
```

#### 返回类型 `-> return_type`

大多数情况下可以省略，编译器会根据 `return` 语句自动推导：

```cpp
// 编译器自动推导返回类型为 bool
[](const eatt_device& ed) { return ed.bda_ == some_addr; };

// 等价于显式指定
[](const eatt_device& ed) -> bool { return ed.bda_ == some_addr; };
```

**必须显式指定返回类型的情况**：当函数体中有多个 `return` 语句且返回类型不一致时：

```cpp
// 错误：编译器无法推导，两个 return 类型不同
[](int x) {
    if (x > 0) return x;      // int
    return 0.5;                // double
};

// 正确：显式指定返回类型
[](int x) -> double {
    if (x > 0) return x;
    return 0.5;
};
```

#### `mutable` 关键字

默认情况下，按值捕获的变量在 Lambda 内是 **只读** 的（因为 `operator()` 默认是 `const` 成员函数）。如果你想修改按值捕获的变量，需要加 `mutable`：

```cpp
int count = 0;

// 错误：不能修改按值捕获的变量
[count]() { count++; };  // 编译错误！

// 正确：加 mutable 允许修改（修改的是 Lambda 内部的副本，不影响外部）
[count]() mutable { count++; };  // OK，但外部的 count 不变
```

> **注意**：`mutable` 修改的是 Lambda 内部的副本，不会影响外部的原始变量。如果需要修改外部变量，应该按引用捕获 `[&count]`。

### ☕ Java 类比

Java Lambda 的参数列表和返回类型与 C++ 类似，但 `mutable` 概念不存在：

| 对比项 | C++ Lambda | Java Lambda |
|--------|------------|-------------|
| 参数类型 | 显式或 `auto`（C++14） | 显式或 `var`（Java 11） |
| 返回类型推导 | 自动 | 由函数式接口决定 |
| `mutable` | 需要，修改按值捕获的副本 | 不需要（Java 没有按值捕获对象） |
| 修改外部变量 | `[&var]` 按引用捕获 | 变量必须是 effectively final，**不能修改** |
| 多返回类型 | 需显式指定 `-> double` | 不适用（接口决定） |

**C++ mutable 示例：**

```cpp
int count = 0;
auto inc = [count]() mutable { return ++count; };  // 修改副本
inc();  // 返回 1，外部 count 仍为 0
```

**Java 的替代方案：**

```java
// Java Lambda 不能修改局部变量，但可以用可变引用类型：
int[] count = {0};  // 用数组包装
Runnable inc = () -> count[0]++;  // 修改数组内容（引用不变）
inc();
// count[0] == 1

// 或使用 AtomicInteger
var counter = new AtomicInteger(0);
Runnable inc2 = () -> counter.incrementAndGet();
```

> **关键区别**：C++ 的 `mutable` 允许 Lambda 修改按值捕获的副本（不影响外部）。Java 不允许 Lambda 修改捕获的局部变量，但可以通过捕获可变对象（如数组、`AtomicInteger`）间接实现。

---

## 3. 捕获列表 (Capture) 详解

捕获列表是 Lambda 最独特、也最容易出错的部分。它决定了 Lambda 如何访问外部的变量。

### 3.1 不捕获 `[]`

```cpp
int main() {
    auto say_hello = []() {
        std::cout << "Hello, Bluetooth!" << std::endl;
    };
    say_hello();  // 输出: Hello, Bluetooth!
}
```

不捕获任何外部变量时，Lambda 只能使用：
- 自己的参数
- 全局变量和静态变量
- 字面量常量

**蓝牙协议栈真实示例**——无捕获的 Lambda，只使用参数：

```cpp
// system/stack/eatt/eatt_impl.h:637-641
// 查找已打开且没有有效 indicate_handle 的通道
// 不需要任何外部变量，所有信息都在参数 el 中
auto iter = find_if(eatt_dev->eatt_channels.begin(),
                    eatt_dev->eatt_channels.end(),
                    [](const std::pair<uint16_t, std::shared_ptr<EattChannel>>& el) {
                      return el.second->state_ == EattChannelState::EATT_CHANNEL_OPENED &&
                             !GATT_HANDLE_IS_VALID(el.second->indicate_handle_);
                    });
```

这个 Lambda 不需要捕获任何外部变量，因为判断条件（通道状态和 handle 有效性）完全来自参数 `el`。

### 3.2 按值捕获所有外部变量 `[=]`

```cpp
int threshold = 5;
auto is_big = [=](int x) { return x > threshold; };
// threshold 被按值拷贝到 Lambda 中，Lambda 内部有一份副本
```

**特点**：
- Lambda 创建时，拷贝一份外部变量的值到 Lambda 内部
- 之后外部变量改变，Lambda 内部的副本**不会**跟着变
- Lambda 内部默认不能修改这个副本（除非加 `mutable`）

```cpp
int value = 10;
auto lambda = [=]() { return value; };  // 拷贝了 value = 10

value = 20;  // 修改外部变量
std::cout << lambda();  // 输出 10，不是 20！Lambda 保存的是创建时的副本
```

### 3.3 按引用捕获所有外部变量 `[&]`

```cpp
int threshold = 5;
auto is_big = [&](int x) { return x > threshold; };
// threshold 被按引用捕获，Lambda 内部直接使用外部变量本身
```

**特点**：
- Lambda 不拷贝变量，而是持有外部变量的引用
- 外部变量改变，Lambda 内部看到的是**最新值**
- Lambda 内部可以修改外部变量

```cpp
int value = 10;
auto lambda = [&]() { return value; };  // 持有 value 的引用

value = 20;  // 修改外部变量
std::cout << lambda();  // 输出 20！引用指向的是外部变量
```

### 3.4 按值捕获指定变量 `[var]`

```cpp
int a = 1, b = 2, c = 3;
auto lambda = [b]() { return b; };  // 只拷贝 b，a 和 c 不可用
```

### 3.5 按引用捕获指定变量 `[&var]`

这是蓝牙协议栈中**最常见的捕获方式**。当你只需要引用一个外部变量时，显式指定比 `[&]` 更安全、更清晰。

**蓝牙协议栈真实示例**——按引用捕获 `lcid`：

```cpp
// system/stack/eatt/eatt_impl.h:85-88
// 在设备列表中查找包含指定 LCID 的设备
void EattImpl::RemoveChannelByLcid(uint16_t lcid) {
    // lcid 是函数参数，Lambda 按引用捕获它
    auto iter = find_if(devices_.begin(), devices_.end(),
                        [&lcid](const eatt_device& ed) {
                          auto it = ed.eatt_channels.find(lcid);
                          return it != ed.eatt_channels.end();
                        });
    // ...
}
```

**为什么用 `[&lcid]` 而不是 `[=]` 或 `[lcid]`？**

- `lcid` 是 `uint16_t`（小类型），按值和按引用性能差别不大
- 但按引用捕获是蓝牙协议栈的编码习惯——对于函数参数，通常按引用捕获，避免不必要的拷贝
- 显式写出 `[&lcid]` 让读者一眼看出 Lambda 依赖了哪个外部变量

**蓝牙协议栈真实示例**——按引用捕获 `bd_addr`：

```cpp
// system/stack/eatt/eatt_impl.h:524-525
// 在设备列表中查找指定蓝牙地址的设备
EattDevice* EattImpl::FindEattDevice(const RawAddress& bd_addr) {
    auto iter = find_if(devices_.begin(), devices_.end(),
                        [&bd_addr](const eatt_device& ed) {
                          return ed.bda_ == bd_addr;
                        });
    // ...
}
```

这里 `bd_addr` 是 `RawAddress` 类型（蓝牙地址，6 字节），按引用捕获避免了拷贝。

**蓝牙协议栈真实示例**——按引用捕获 `cid`：

```cpp
// system/stack/eatt/eatt_impl.h:598-601
// 在通道映射中查找指定 CID 的通道
std::shared_ptr<EattChannel> EattImpl::FindChannelByCid(
    const RawAddress& bd_addr, uint16_t cid) {
    auto eatt_dev = FindEattDevice(bd_addr);
    if (!eatt_dev) return nullptr;

    auto iter = find_if(eatt_dev->eatt_channels.begin(),
                        eatt_dev->eatt_channels.end(),
                        [&cid](const std::pair<uint16_t, std::shared_ptr<EattChannel>>& el) {
                          return el.first == cid;
                        });
    // ...
}
```

### 3.6 捕获 `this` 指针 `[this]`

在类的成员函数中，Lambda 可以捕获 `this` 指针来访问类的成员变量和成员函数：

```cpp
class EattImpl {
private:
    std::vector<eatt_device> devices_;

public:
    void DoSomething() {
        // 捕获 this，可以访问 devices_ 等成员
        auto iter = find_if(devices_.begin(), devices_.end(),
            [this](const eatt_device& ed) {
                return ed.bda_ == this->some_member_;  // 可以访问成员变量
            });
    }
};
```

> **注意**：在成员函数中写 `[=]` 会隐式捕获 `this`（C++20 之前），这可能导致意外行为。C++20 中 `[=]` 不再隐式捕获 `this`，需要显式写 `[=, this]` 或 `[this]`。

### 3.7 混合捕获

你可以组合多种捕获方式：

```cpp
int a = 1, b = 2, c = 3;

// a 按值，b 按引用，其余不捕获
auto lambda = [a, &b]() { /* 可以读 a，可以读写 b */ };

// 所有变量按值捕获，但 c 按引用
auto lambda2 = [=, &c]() { /* 所有变量只读，c 可读写 */ };

// 所有变量按引用捕获，但 a 按值
auto lambda3 = [&, a]() { /* 所有变量可读写，a 只读 */ };
```

**混合捕获的规则**：
- `[=, &var]`：默认按值，指定变量按引用
- `[&, var]`：默认按引用，指定变量按值
- 不能同时有 `[=]` 和 `[&]` 作为默认
- 混合捕获时，指定的变量不能和默认方式重复（`[&, &x]` 是错误的）

### 3.8 捕获方式选择指南

| 场景 | 推荐方式 | 原因 |
|------|----------|------|
| Lambda 只在当前函数内使用，且不存储 | `[&]` 或 `[&var]` | 方便，安全（生命周期可控） |
| Lambda 可能被存储（如回调、定时器） | `[=]` 或 `[var]` | 避免悬空引用 |
| 需要修改外部变量 | `[&var]` | 按引用才能修改 |
| 捕获大对象 | `[&var]` | 避免昂贵的拷贝 |
| 捕获小类型（int, 指针等） | `[var]` 或 `[&var]` 均可 | 性能差别可忽略 |
| 在类成员函数中访问成员 | `[this]` | 显式表明意图 |

### ☕ Java 类比

C++ 的捕获列表是 Java 程序员学习 C++ Lambda 时最需要适应的特性。Java 自动捕获，C++ 需要显式指定：

| 对比项 | C++ 捕获列表 | Java Lambda 捕获 |
|--------|-------------|------------------|
| 按值捕获所有 | `[=]` | 自动（所有 effectively final 变量） |
| 按引用捕获所有 | `[&]` | 无等价（Java 不支持引用捕获） |
| 按值捕获指定变量 | `[var]` | 自动（仅捕获使用的变量） |
| 按引用捕获指定变量 | `[&var]` | 无等价 |
| 捕获 this | `[this]` 或 `[*this]` | 自动（内部类隐式持有外部类引用） |
| 修改捕获的变量 | `[&var]` 或 `[var] mutable` | 不允许（effectively final 限制） |
| 悬空引用风险 | 有（`[&]` 可能捕获已销毁的局部变量） | 无（GC 保证对象存活） |

**C++ 捕获列表示例：**

```cpp
uint16_t lcid = 0x0040;
auto iter = find_if(devices.begin(), devices.end(),
    [&lcid](const eatt_device& ed) {   // 显式按引用捕获 lcid
        return ed.eatt_channels.find(lcid) != ed.eatt_channels.end();
    });
```

**Java Lambda 捕获示例：**

```java
int lcid = 0x0040;  // 必须是 effectively final
var iter = devices.stream()
    .filter(ed -> ed.getChannels().containsKey(lcid))  // 自动捕获 lcid
    .findFirst();
// lcid = 0x0050;  // 编译错误！捕获后不能修改
```

> **关键区别**：C++ 的捕获列表让程序员精确控制每个变量的捕获方式，但增加了出错风险（悬空引用）。Java 的 effectively final 规则更安全，但灵活性较低——无法在 Lambda 内修改局部变量。Java 不需要担心悬空引用，因为 GC 保证了对象的生命周期。

---

## 4. Lambda 与 STL 算法结合

Lambda 最常见的用途之一就是和 STL 算法配合使用。STL 提供了大量接受"谓词"（返回 bool 的函数）的算法，Lambda 是提供谓词最方便的方式。

### 4.1 `std::find_if` —— 查找满足条件的元素

`std::find_if` 在范围内查找第一个满足谓词的元素，返回指向该元素的迭代器。

**函数签名**：
```cpp
template<class InputIt, class UnaryPredicate>
InputIt find_if(InputIt first, InputIt last, UnaryPredicate p);
```

**蓝牙协议栈真实示例**——查找包含指定 LCID 的设备：

```cpp
// system/stack/eatt/eatt_impl.h:85-88
auto iter = find_if(devices_.begin(), devices_.end(),
    [&lcid](const eatt_device& ed) {
      auto it = ed.eatt_channels.find(lcid);
      return it != ed.eatt_channels.end();
    });

if (iter != devices_.end()) {
    // 找到了，iter 指向该设备
} else {
    // 没找到
}
```

**逐步解读**：

1. `devices_.begin(), devices_.end()` —— 遍历整个设备列表
2. `[&lcid]` —— 按引用捕获外部的 `lcid` 变量
3. `(const eatt_device& ed)` —— 每次迭代，当前元素以 const 引用传入
4. 函数体 —— 在当前设备的通道映射中查找 `lcid`，找到了就返回 `true`

**蓝牙协议栈真实示例**——查找指定蓝牙地址的设备：

```cpp
// system/stack/eatt/eatt_impl.h:524-525
auto iter = find_if(devices_.begin(), devices_.end(),
    [&bd_addr](const eatt_device& ed) { return ed.bda_ == bd_addr; });
```

这个更简洁——直接比较蓝牙地址。

**蓝牙协议栈真实示例**——在通道映射中查找：

```cpp
// system/stack/eatt/eatt_impl.h:598-601
auto iter = find_if(eatt_dev->eatt_channels.begin(),
                    eatt_dev->eatt_channels.end(),
    [&cid](const std::pair<uint16_t, std::shared_ptr<EattChannel>>& el) {
      return el.first == cid;
    });
```

注意这里的参数类型是 `const std::pair<uint16_t, std::shared_ptr<EattChannel>>&`，因为 `eatt_channels` 是一个 `std::map`，其元素类型是 `std::pair<const Key, Value>`。

### 4.2 `std::count_if` —— 统计满足条件的元素个数

`std::count_if` 统计范围内满足谓词的元素数量。

**蓝牙协议栈真实示例**——统计正在执行定向公告连接的设备数：

```cpp
// system/stack/connection_manager/connection_manager.cc:112-114
size_t count = std::count_if(
    bgconn_dev.begin(), bgconn_dev.end(),
    [](const auto& pair) {
      return !pair.second.is_in_accept_list &&
             !pair.second.doing_targeted_announcements_conn.empty();
    });
```

**逐步解读**：

1. 遍历 `bgconn_dev`（后台连接设备映射）
2. 对每个 `pair`（键值对），检查：
   - `pair.second.is_in_accept_list` 为 `false`（不在接受列表中）
   - `pair.second.doing_targeted_announcements_conn` 不为空（正在做定向公告连接）
3. 同时满足这两个条件的设备被计入

**注意**：这里使用了 `auto` 参数（泛型 Lambda，C++14 特性，详见[第 7 节](#7-泛型-lambda-c14)），`const auto& pair` 让编译器自动推导参数类型。

### 4.3 `std::for_each` —— 对每个元素执行操作

`std::for_each` 对范围内的每个元素执行给定的函数：

```cpp
// 假设要打印所有已连接设备的地址
std::for_each(devices_.begin(), devices_.end(),
    [](const eatt_device& ed) {
        std::cout << "Device: " << ed.bda_.ToString() << std::endl;
    });
```

`for_each` 的 Lambda 通常不返回值（返回值会被忽略），它的作用是产生副作用（如打印、修改等）。

### 4.4 `std::sort` —— 自定义排序

`std::sort` 可以接受一个比较函数，当默认的 `<` 运算符不满足需求时使用：

```cpp
// 按通道的 MTU 从大到小排序
std::sort(channels.begin(), channels.end(),
    [](const std::shared_ptr<EattChannel>& a,
       const std::shared_ptr<EattChannel>& b) {
        return a->tx_mtu_ > b->tx_mtu_;
    });
```

**比较函数的规则**：返回 `true` 表示第一个参数应该排在第二个参数**前面**。

### 4.5 STL 算法 + Lambda 的优势

| 对比项 | 传统 for 循环 | STL 算法 + Lambda |
|--------|--------------|-------------------|
| 意图表达 | 需要读代码理解 | 算法名直接表达意图（find_if、count_if） |
| 代码量 | 较多（循环变量、迭代器操作） | 较少（一行调用 + Lambda） |
| 出错概率 | 较高（越界、off-by-one） | 较低（算法处理边界） |
| 可读性 | 循环逻辑混在一起 | 查找/计数/遍历逻辑分离 |

### ☕ Java 类比

C++ 的 STL 算法 + Lambda 对应 Java 的 Stream API + Lambda。两者都提供了函数式风格的集合操作：

| C++ STL 算法 | Java Stream API | 功能 |
|-------------|-----------------|------|
| `std::find_if` | `.filter().findFirst()` | 条件查找 |
| `std::count_if` | `.filter().count()` | 条件计数 |
| `std::for_each` | `.forEach()` | 遍历执行 |
| `std::sort` + Lambda | `.sorted(Comparator)` | 自定义排序 |
| `std::transform` | `.map()` | 变换元素 |
| `std::copy_if` | `.filter().collect()` | 条件拷贝 |
| `std::any_of` | `.anyMatch()` | 是否存在满足条件的 |
| `std::all_of` | `.allMatch()` | 是否全部满足 |
| `std::none_of` | `.noneMatch()` | 是否全部不满足 |
| `std::remove_if` + `erase` | `.removeIf()` | 条件删除 |

**C++ STL 算法 + Lambda 示例：**

```cpp
// 查找
auto it = std::find_if(devices.begin(), devices.end(),
    [&bd_addr](const eatt_device& ed) { return ed.bda_ == bd_addr; });

// 计数
size_t count = std::count_if(bgconn_dev.begin(), bgconn_dev.end(),
    [](const auto& pair) { return !pair.second.is_in_accept_list; });

// 排序
std::sort(channels.begin(), channels.end(),
    [](const auto& a, const auto& b) { return a->tx_mtu_ > b->tx_mtu_; });
```

**Java Stream API + Lambda 示例：**

```java
// 查找
var device = devices.stream()
    .filter(ed -> ed.getBda().equals(bdAddr))
    .findFirst();

// 计数
long count = bgconnDev.entrySet().stream()
    .filter(entry -> !entry.getValue().isInAcceptList())
    .count();

// 排序
var sorted = channels.stream()
    .sorted((a, b) -> Integer.compare(b.getTxMtu(), a.getTxMtu()))
    .collect(Collectors.toList());
```

> **关键区别**：C++ STL 算法直接操作迭代器（可修改原容器），Java Stream 生成新流（不修改原集合）。C++ 的 `find_if` 返回迭代器，Java 的 `filter` 返回新 Stream。Java Stream 是惰性求值的，只有终端操作（`collect`、`count` 等）才触发计算。

---

## 5. Lambda 作为变量存储

Lambda 不一定要"即用即弃"，你可以把它存储在变量中，反复使用。

### 5.1 基本用法

```cpp
// 用 auto 存储一个 Lambda
auto is_even = [](int n) { return n % 2 == 0; };

// 反复使用
std::cout << is_even(4) << std::endl;   // 1 (true)
std::cout << is_even(7) << std::endl;   // 0 (false)

// 传给 STL 算法
std::vector<int> nums = {1, 2, 3, 4, 5, 6};
int even_count = std::count_if(nums.begin(), nums.end(), is_even);  // 3
```

### 5.2 `inline auto` 全局 Lambda

在头文件中，你可以用 `inline auto` 定义一个全局 Lambda，供多个编译单元使用。

**蓝牙协议栈真实示例**——定时器任务队列的比较器：

```cpp
// system/gd/os/handler.h:40-44
// 定义一个全局 Lambda，用于比较两个延时任务的时间
inline auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
    return a.first > b.first;  // a.first 是时间戳，大的排前面（最小堆）
};
```

**为什么用 `inline`？**

在头文件中定义全局变量，如果不加 `inline`，每个包含该头文件的编译单元都会有一份定义，导致链接时的"多重定义"错误。`inline` 允许多次定义，链接器会合并它们。

### 5.3 `decltype` 获取 Lambda 的类型

Lambda 表达式的类型是编译器自动生成的**唯一匿名类类型**，你无法直接写出这个类型名。但可以用 `decltype` 获取：

```cpp
auto my_lambda = [](int x) { return x * 2; };

// decltype(my_lambda) 就是 Lambda 的类型
// 你无法手写这个类型名，但 decltype 可以获取

// 常见用途：作为模板参数
std::vector<int> vec = {5, 3, 1, 4, 2};
auto comp = [](int a, int b) { return a > b; };
std::priority_queue<int, std::vector<int>, decltype(comp)> pq(comp);
```

**蓝牙协议栈真实示例**——用 `decltype` 为 `priority_queue` 指定比较器类型：

```cpp
// system/gd/os/handler.h:40-46
inline auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
    return a.first > b.first;
};

// 用 decltype(compare_task_by_time) 作为 priority_queue 的模板参数
using DelayedTaskQueue =
    std::priority_queue<DelayedTask,
                        std::vector<DelayedTask>,
                        decltype(compare_task_by_time)>;
```

**逐步解读**：

1. `compare_task_by_time` 是一个 Lambda，定义了两个延时任务的比较规则
2. `decltype(compare_task_by_time)` 获取这个 Lambda 的类型
3. `std::priority_queue` 的第三个模板参数是比较器的类型
4. 创建 `priority_queue` 对象时，需要传入比较器的实例（见下节详解）

### 5.4 Lambda 变量 vs 函数指针

Lambda 可以转换为函数指针（前提是无捕获），但两者有本质区别：

```cpp
// 无捕获 Lambda 可以转为函数指针
auto lambda1 = [](int x) { return x + 1; };
int (*func_ptr)(int) = lambda1;  // OK

// 有捕获 Lambda 不能转为函数指针
int y = 10;
auto lambda2 = [y](int x) { return x + y; };
// int (*func_ptr2)(int) = lambda2;  // 错误！有捕获的 Lambda 不能转为函数指针
```

原因：无捕获的 Lambda 不存储任何状态，等价于普通函数；有捕获的 Lambda 存储了捕获的变量，是一个有状态的对象，无法用函数指针表示。

### ☕ Java 类比

Java 的 Lambda 可以赋值给函数式接口类型的变量，这与 C++ 用 `auto` 存储 Lambda 类似：

| 对比项 | C++ Lambda 变量 | Java Lambda 变量 |
|--------|----------------|-----------------|
| 存储方式 | `auto func = [](int x) { ... };` | `Function<Integer, R> func = x -> ...;` |
| 类型 | 编译器生成的匿名类 | 函数式接口的实现 |
| 获取类型 | `decltype(func)` | 直接使用接口类型 |
| 全局 Lambda | `inline auto func = [](..){..};` | `static final Function<..> func = .. -> ..;` |
| 转函数指针 | 无捕获时可以 | 不适用（Java 无函数指针） |

**C++ Lambda 变量示例：**

```cpp
auto is_even = [](int n) { return n % 2 == 0; };
int count = std::count_if(nums.begin(), nums.end(), is_even);
```

**Java Lambda 变量示例：**

```java
Predicate<Integer> isEven = n -> n % 2 == 0;
long count = nums.stream().filter(isEven).count();
```

> **关键区别**：C++ 用 `auto` 存储 Lambda，类型是编译器生成的唯一匿名类，比 `std::function` 更高效（无运行时多态开销）。Java 的 Lambda 必须赋值给函数式接口（如 `Predicate<T>`、`Function<T,R>`），通过接口多态调用。

---

## 6. Lambda 作为回调函数

在蓝牙协议栈这种事件驱动的系统中，回调函数无处不在。Lambda 为回调提供了更简洁的写法。

### 6.1 替代函数指针

传统 C 风格的回调使用函数指针：

```cpp
// 传统方式：定义回调函数
void on_connection_complete(uint16_t handle, void* context) {
    // 处理连接完成事件
}

// 注册回调
register_callback(on_connection_complete, user_data);
```

Lambda 方式更简洁，且可以直接访问上下文变量：

```cpp
// Lambda 方式
uint16_t expected_handle = 0x0040;
register_callback([&expected_handle](uint16_t handle) {
    if (handle == expected_handle) {
        // 处理连接完成
    }
});
```

### 6.2 与 `base::Bind` / `base::BindOnce` 配合

Android 蓝牙协议栈使用 Chromium 的 `base::Bind` / `base::BindOnce` 机制来管理回调。`base::BindOnce` 创建一个只能调用一次的回调，`base::Bind` 创建可多次调用的回调。

```cpp
// 使用 base::BindOnce 绑定成员函数
post_on_bt_thread(
    base::BindOnce(&BtmSec::OnAuthenticationComplete,
                   base::Unretained(this),
                   bda,
                   status));

// 使用 base::BindOnce 绑定 Lambda
post_on_bt_thread(
    base::BindOnce([](const RawAddress& bda, tBTM_STATUS status) {
        LOG(INFO) << "Auth complete for " << bda << " status=" << status;
    }, bd_addr, auth_status));
```

### 6.3 蓝牙协议栈中的谓词 Lambda

在安全模块中，Lambda 常被用作谓词来判断设备状态：

```cpp
// system/stack/btm/btm_sec.cc 中的典型模式
// 查找满足安全条件的设备
auto iter = std::find_if(sec_devices.begin(), sec_devices.end(),
    [&bda](const tBTM_SEC_DEV_REC& rec) {
        return rec.bd_addr == bda &&
               rec.sec_state != BTM_SEC_STATE_IDLE;
    });
```

这种模式在蓝牙协议栈中反复出现：**查找满足某个条件的元素**。Lambda 让谓词逻辑可以就地编写，不需要定义额外的函数或函数对象。

### ☕ Java 类比

Java 的 Lambda 回调与 C++ 类似，但回调机制不同：

| 对比项 | C++ 回调 | Java 回调 |
|--------|---------|----------|
| 函数指针回调 | `void (*callback)(int)` | 无（Java 无函数指针） |
| 通用回调类型 | `std::function<void(int)>` | 函数式接口（如 `Consumer<Integer>`） |
| 一次性回调 | `base::OnceCallback` | 无内置（需自定义或用 `Consumer`） |
| 成员函数回调 | `base::Bind(&Class::Method, this)` | `this::method`（方法引用） |
| Lambda 回调 | `[&var](int x) { ... }` | `x -> { ... }` |

**C++ 回调示例：**

```cpp
// 绑定成员函数
post_on_bt_thread(
    base::BindOnce(&BtmSec::OnAuthenticationComplete,
                   base::Unretained(this), bda, status));

// Lambda 回调
post_on_bt_thread(
    base::BindOnce([](const RawAddress& bda, tBTM_STATUS status) {
        LOG(INFO) << "Auth complete";
    }, bd_addr, auth_status));
```

**Java 回调示例：**

```java
// 方法引用
handler.post(() -> btmSec.onAuthenticationComplete(bda, status));

// Lambda 回调
handler.post(() -> Log.i("Auth complete for " + bdAddr));
```

> **关键区别**：C++ 的 `base::Bind`/`base::BindOnce` 可以绑定成员函数并延迟传参，Java 用方法引用和 Lambda 更简洁。Java 的回调天然是对象，由 GC 管理生命周期；C++ 需要手动管理回调对象的生命周期（如 `base::Unretained`）。

---

## 7. 泛型 Lambda (C++14)

### 7.1 `auto` 参数

C++14 引入了泛型 Lambda，允许在参数列表中使用 `auto`：

```cpp
// C++11：必须明确写出参数类型
[](const std::pair<uint16_t, std::shared_ptr<EattChannel>>& el) {
    return el.first == 42;
}

// C++14：可以用 auto 代替
[](const auto& el) {
    return el.first == 42;
}
```

**好处**：
- 代码更简洁
- 同一个 Lambda 可以用于不同类型的容器
- 减少类型拼写错误

### 7.2 蓝牙协议栈真实示例

```cpp
// system/stack/connection_manager/connection_manager.cc:112-114
// 使用 auto 参数，不需要知道 map 的 value_type 具体是什么
size_t count = std::count_if(
    bgconn_dev.begin(), bgconn_dev.end(),
    [](const auto& pair) {
      return !pair.second.is_in_accept_list &&
             !pair.second.doing_targeted_announcements_conn.empty();
    });
```

这里 `bgconn_dev` 是一个 `std::unordered_map<RawAddress, ...>`，其元素类型是 `std::pair<const RawAddress, ...>`。用 `const auto& pair` 代替冗长的类型名，代码更清晰。

### 7.3 泛型 Lambda 的本质

泛型 Lambda 本质上是一个模板化的 `operator()`：

```cpp
// 你写的泛型 Lambda
auto lambda = [](const auto& x) { return x.size(); };

// 编译器生成的等价代码（简化）
struct __lambda {
    template<typename T>
    auto operator()(const T& x) const { return x.size(); }
};
```

这意味着同一个 Lambda 可以接受不同类型的参数：

```cpp
auto get_size = [](const auto& container) { return container.size(); };

std::vector<int> vec = {1, 2, 3};
std::string str = "hello";

std::cout << get_size(vec);  // 3
std::cout << get_size(str);  // 5
```

### ☕ Java 类比

C++ 的泛型 Lambda（`auto` 参数）与 Java 的泛型方法功能类似，但实现机制不同：

| 对比项 | C++ 泛型 Lambda | Java 泛型方法 |
|--------|----------------|-------------|
| 语法 | `[](const auto& x) { ... }` | `<T> void process(T x) { ... }` |
| 本质 | 模板化的 `operator()` | 类型擦除的泛型方法 |
| 类型推导 | 编译期为每种类型生成特化 | 运行时类型擦除 |
| 性能 | 零开销（编译期多态） | 可能有装箱开销（基本类型） |
| 约束类型 | C++20 可用 `concept` 约束 | 可用 `<T extends ...>` 约束 |

**C++ 泛型 Lambda 示例：**

```cpp
auto get_size = [](const auto& container) { return container.size(); };
get_size(std::vector<int>{1, 2, 3});  // 3
get_size(std::string("hello"));        // 5
```

**Java 泛型方法示例：**

```java
// Java Lambda 不支持泛型参数，需要用泛型方法包装
<T> int getSize(Collection<T> collection) { return collection.size(); }
getSize(List.of(1, 2, 3));  // 3

// 或使用通配符函数式接口
Function<Collection<?>, Integer> getSize = Collection::size;
```

> **关键区别**：C++ 泛型 Lambda 的 `auto` 参数让同一个 Lambda 对象可以接受不同类型，编译器为每种类型生成特化代码。Java Lambda 不支持泛型参数，需要用泛型方法或通配符类型间接实现。

---

## 8. Lambda 与 priority_queue

`std::priority_queue` 是一个优先队列（堆），默认使用 `std::less` 即最大堆。当你需要自定义排序规则时，Lambda 是最方便的方式。

### 8.1 问题描述

在蓝牙协议栈的消息处理系统中，延时任务需要按执行时间排序——**最早执行的任务应该最先出队**。这就是一个最小堆的需求。

### 8.2 蓝牙协议栈真实示例

```cpp
// system/gd/os/handler.h:40-46
// DelayedTask 是一个 pair<时间戳, 任务>
using DelayedTask = std::pair<std::chrono::steady_clock::time_point,
                              base::OnceClosure>;

// 定义比较器：时间戳大的排前面 → 最小堆（最早时间先出队）
inline auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
    return a.first > b.first;  // a 的时间更晚 → a 排在后面
};

// 用 decltype 获取 Lambda 类型，作为 priority_queue 的比较器类型
using DelayedTaskQueue =
    std::priority_queue<DelayedTask,
                        std::vector<DelayedTask>,
                        decltype(compare_task_by_time)>;
```

### 8.3 使用这个优先队列

```cpp
class Handler {
private:
    // 使用自定义比较器的优先队列
    DelayedTaskQueue delayed_tasks_{compare_task_by_time};
    // 注意：必须传入 Lambda 实例作为构造参数！

public:
    void PostDelayedTask(base::OnceClosure task, int delay_ms) {
        auto deadline = std::chrono::steady_clock::now() +
                        std::chrono::milliseconds(delay_ms);
        delayed_tasks_.emplace(deadline, std::move(task));
    }

    void ProcessDelayedTasks() {
        auto now = std::chrono::steady_clock::now();
        while (!delayed_tasks_.empty() &&
               delayed_tasks_.top().first <= now) {
            auto task = std::move(delayed_tasks_.top().second);
            delayed_tasks_.pop();
            std::move(task)();  // 执行任务
        }
    }
};
```

### 8.4 关键知识点

**为什么 `priority_queue` 需要比较器的类型作为模板参数？**

`std::priority_queue` 的模板声明：

```cpp
template<class T,
         class Container = std::vector<T>,
         class Compare = std::less<typename Container::value_type>>
class priority_queue;
```

`Compare` 是一个**类型参数**，不是值参数。所以你需要：
1. 提供比较器的**类型**（用 `decltype(lambda)` 获取）
2. 在构造时提供比较器的**实例**（传入 Lambda 变量）

```cpp
// 完整步骤
auto my_comp = [](int a, int b) { return a > b; };  // 1. 定义 Lambda
std::priority_queue<int, std::vector<int>, decltype(my_comp)> pq(my_comp);  // 2. 类型 + 实例
```

**为什么 `a.first > b.first` 是最小堆？**

`priority_queue` 的比较器语义是：`comp(a, b)` 返回 `true` 表示 `a` 的优先级**低于** `b`，`a` 排在后面。所以：
- `a.first > b.first` 返回 `true` → `a` 的时间更晚 → `a` 优先级更低 → `a` 排在后面
- 结果：时间最早的任务优先级最高，最先出队 → 最小堆

### ☕ Java 类比

C++ 的 `std::priority_queue` + Lambda 比较器对应 Java 的 `PriorityQueue<T>` + `Comparator<T>`：

| 对比项 | C++ `priority_queue` | Java `PriorityQueue` |
|--------|---------------------|---------------------|
| 默认行为 | 大顶堆（最大先出） | 小顶堆（最小先出） |
| 自定义比较器 | Lambda + `decltype` | `Comparator<T>` Lambda |
| 比较器传入方式 | 模板参数 + 构造参数 | 构造参数 |
| 获取堆顶 | `pq.top()` | `pq.peek()` |
| 出队 | `pq.pop()`（无返回值） | `pq.poll()`（返回堆顶元素） |
| 入队 | `pq.push(x)` / `pq.emplace(...)` | `pq.offer(x)` / `pq.add(x)` |

**C++ priority_queue + Lambda 示例：**

```cpp
auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
    return a.first > b.first;  // 小顶堆
};
std::priority_queue<DelayedTask, std::vector<DelayedTask>,
                    decltype(compare_task_by_time)> pq(compare_task_by_time);
```

**Java PriorityQueue + Comparator 示例：**

```java
// 方式 1：Lambda Comparator
PriorityQueue<DelayedTask> pq = new PriorityQueue<>(
    (a, b) -> a.getDeadline().compareTo(b.getDeadline())  // 小顶堆
);

// 方式 2：Comparator.comparing
PriorityQueue<DelayedTask> pq = new PriorityQueue<>(
    Comparator.comparing(DelayedTask::getDeadline)
);

// 使用
pq.offer(new DelayedTask(deadline, task));
DelayedTask top = pq.peek();  // 查看堆顶
DelayedTask next = pq.poll(); // 取出并移除堆顶
```

> **关键区别**：C++ 的 `priority_queue` 需要将比较器类型作为模板参数（用 `decltype` 获取 Lambda 类型），并在构造时传入实例。Java 的 `PriorityQueue` 只需在构造时传入 `Comparator` 对象，更简洁。Java 默认是小顶堆，C++ 默认是大顶堆。

---

## 9. 常见陷阱与最佳实践

### 9.1 悬空引用——最危险的陷阱

**问题**：Lambda 按引用捕获了局部变量，但 Lambda 的生命周期超过了该局部变量。

```cpp
// 危险！悬空引用示例
std::function<int()> create_counter() {
    int count = 0;
    // 按引用捕获 count，但 count 在函数返回后就被销毁了！
    return [&count]() { return ++count; };
    //         ^^^^^^ count 已经不存在了！
}

auto counter = create_counter();
counter();  // 未定义行为！访问了已销毁的局部变量
```

**修复**：按值捕获，或使用 `shared_ptr`：

```cpp
// 修复方案 1：按值捕获（如果不需要修改外部变量）
std::function<int()> create_counter() {
    int count = 0;
    return [count]() mutable { return ++count; };
    // 捕获 count 的副本，Lambda 自己持有这个副本
}

// 修复方案 2：使用 shared_ptr（如果需要共享状态）
std::function<int()> create_counter() {
    auto count = std::make_shared<int>(0);
    return [count]() { return ++(*count); };
    // Lambda 持有 shared_ptr，引用计数保证 count 不被销毁
}
```

### 9.2 捕获 `this` 指针的风险

**问题**：Lambda 捕获了 `this` 指针，但对象可能已被销毁。

```cpp
class BluetoothManager {
public:
    void ScheduleTask() {
        // 在另一个线程上延迟执行
        // 危险！this 可能在这 1 秒内被销毁！
        scheduler.PostDelayedTask(
            [this]() { this->DoWork(); },  // this 可能已悬空！
            1000ms);
    }

    void DoWork() { /* ... */ }
};
```

**修复**：使用 `weak_ptr` 确保对象仍然存活：

```cpp
class BluetoothManager : public std::enable_shared_from_this<BluetoothManager> {
public:
    void ScheduleTask() {
        auto weak_self = std::weak_ptr<BluetoothManager>(shared_from_this());
        scheduler.PostDelayedTask(
            [weak_self]() {
                auto self = weak_self.lock();  // 尝试提升为 shared_ptr
                if (self) {
                    self->DoWork();  // 对象还活着，安全执行
                }
                // 对象已销毁，什么都不做
            },
            1000ms);
    }
};
```

### 9.3 按值捕获 vs 按引用捕获的选择

| 情况 | 推荐 | 原因 |
|------|------|------|
| Lambda 立即使用，不存储 | `[&]` | 方便，无悬空风险 |
| Lambda 被存储（回调、定时器等） | `[=]` 或 `[var]` | 避免悬空引用 |
| 捕获大对象 | `[&var]` | 避免拷贝开销 |
| 多线程场景 | `[=]` 或 `[var]` | 按引用捕获可能导致数据竞争 |
| 需要修改外部变量 | `[&var]` | 按值捕获修改的是副本 |

### 9.4 `[=]` 隐式捕获 `this` 的问题

```cpp
class Foo {
    int x_;
public:
    void bar() {
        // C++17 及之前：[=] 会隐式捕获 this
        // 你可能以为捕获了 x_ 的副本，实际捕获的是 this 指针！
        auto lambda = [=]() { return x_; };
        // 等价于：
        // auto lambda = [this]() { return this->x_; };
        // 如果 this 被销毁，x_ 也不可访问了！
    }
};
```

**最佳实践**：需要访问成员变量时，显式捕获 `this` 或使用 C++17 的 `[*this]`（按值拷贝整个对象）：

```cpp
// 显式捕获 this，让意图更清晰
auto lambda = [this]() { return x_; };

// C++17：按值拷贝 *this，Lambda 持有对象的副本
auto lambda = [*this]() { return x_; };
```

### 9.5 初始化捕获 (C++14)

C++14 支持在捕获列表中初始化新变量，这是移动捕获的唯一方式：

```cpp
auto ptr = std::make_unique<EattChannel>(bda, cid, mtu, rx_mtu);

// 错误：unique_ptr 不能按值捕获（不可拷贝）
// auto lambda = [ptr]() { return ptr->state_; };

// C++14 初始化捕获：移动 ptr 到 Lambda 中
auto lambda = [p = std::move(ptr)]() { return p->state_; };
// p 是 Lambda 内部的新变量，通过移动构造初始化
```

初始化捕获的语法：`name = expression`，其中 `name` 是 Lambda 内部的变量名，`expression` 是初始化表达式。

### 9.6 常见错误速查表

| 错误代码 | 问题 | 修复 |
|----------|------|------|
| `[&]()` 存储到 `std::function` 后使用 | 悬空引用 | 改为 `[=]` 或 `[var]` |
| `[=]()` 中修改捕获的变量 | 编译错误（const） | 加 `mutable` 或改用 `[&var]` |
| `[this]()` 在对象销毁后调用 | 悬空 this | 使用 `weak_ptr` |
| `[&vec]()` 在多线程中使用 | 数据竞争 | 改为 `[vec]` 按值捕获 |
| `priority_queue` 忘记传比较器实例 | 编译错误或运行时错误 | 构造时传入 Lambda 实例 |

---

## 附录：蓝牙协议栈 Lambda 使用模式总结

在 Android 蓝牙协议栈中，Lambda 的使用遵循以下模式：

### 模式 1：`find_if` + Lambda 查找

这是最频繁出现的模式，几乎每个模块都有：

```cpp
// 在容器中查找满足条件的元素
auto iter = std::find_if(container.begin(), container.end(),
    [&key](const auto& element) {
        return element.some_field == key;
    });
```

### 模式 2：`count_if` + Lambda 计数

```cpp
// 统计满足条件的元素个数
size_t count = std::count_if(container.begin(), container.end(),
    [](const auto& element) {
        return element.some_condition;
    });
```

### 模式 3：Lambda 作为比较器

```cpp
// 定义比较器
inline auto comparator = [](const T& a, const T& b) {
    return a.key > b.key;
};

// 用于 priority_queue
using Queue = std::priority_queue<T, std::vector<T>, decltype(comparator)>;
```

### 模式 4：Lambda 作为回调

```cpp
// 异步操作完成后执行
do_async_operation(
    base::BindOnce([this, request_id](Result result) {
        HandleResult(request_id, result);
    }));
```

---

> **学习建议**：Lambda 是现代 C++ 最重要的特性之一。建议从最简单的 `[](){}` 开始，逐步理解捕获列表、STL 算法配合、变量存储等用法。在实际编码中，**先写对，再写简**——用传统 for 循环能写对的代码，再尝试用 Lambda + STL 算法改写，体会 Lambda 的简洁之处。
