# C++ 模板与泛型编程 —— 从蓝牙协议栈代码学起

> **目标读者**：C++ 初学者，对模板完全不了解
> **教学策略**：由浅入深，每个概念都配有真实代码示例
> **代码来源**：Android 蓝牙协议栈 (Bluetooth GD Stack)

---

## 目录

1. [函数模板基础](#1-函数模板基础)
2. [类模板基础](#2-类模板基础)
3. [模板的变长参数包 (Variadic Templates)](#3-模板的变长参数包-variadic-templates)
4. [SFINAE (替换失败并非错误)](#4-sfinae-替换失败并非错误)
5. [CRTP (奇异递归模板模式)](#5-crtp-奇异递归模板模式)
6. [模板特化](#6-模板特化)
7. [模板在实际开发中的应用场景](#7-模板在实际开发中的应用场景)
8. [初学者如何阅读模板代码](#8-初学者如何阅读模板代码)

---

## 1. 函数模板基础

### 1.1 为什么需要函数模板？

假设你要写一个"求两个数中较大值"的函数。对于 `int` 和 `double`，你需要写两个版本：

```cpp
int Max(int a, int b) {
    return (a > b) ? a : b;
}

double Max(double a, double b) {
    return (a > b) ? a : b;
}
```

这两个函数的逻辑完全一样，只是类型不同。如果还要支持 `float`、`long long`……就得写无数个版本。**函数模板**让你只写一次：

```cpp
template <typename T>
T Max(T a, T b) {
    return (a > b) ? a : b;
}
```

`template <typename T>` 的意思是：**T 是一个类型参数，在调用时由编译器自动推导或手动指定**。

### 1.2 `template <typename T>` 语法详解

```cpp
template <typename T>      // 声明一个类型参数 T
T Max(T a, T b) {          // T 可以用在返回值、参数、函数体中
    return (a > b) ? a : b;
}
```

语法要点：
- `template <...>` 是模板声明关键字，放在函数定义之前
- `typename T` 声明了一个**类型参数**（也可以用 `class T`，两者等价）
- `T` 可以在函数的返回类型、参数类型、函数体中使用

调用方式：

```cpp
int result1 = Max(3, 5);           // 编译器推导 T = int
double result2 = Max(3.14, 2.72);  // 编译器推导 T = double
int result3 = Max<int>(3, 5);      // 显式指定 T = int（通常不需要）
```

### 1.3 类型推导

编译器根据你传入的参数，自动推断 `T` 的类型，这个过程叫**模板参数推导**。

```cpp
template <typename T>
void Print(T value) {
    std::cout << value << std::endl;
}

Print(42);        // T = int
Print(3.14);      // T = double
Print("hello");   // T = const char*
Print<std::string>("hello");  // 显式指定 T = std::string
```

**注意**：当推导出现歧义时，需要显式指定：

```cpp
Max(3, 3.14);     // 错误！T 是 int 还是 double？
Max<double>(3, 3.14);  // 正确，显式指定 T = double
```

### 1.4 多个模板参数

模板可以有多个类型参数：

```cpp
template <typename T1, typename T2>
auto Add(T1 a, T2 b) -> decltype(a + b) {
    return a + b;
}
```

### 1.5 真实示例：Handler::Call

> 文件：`system/gd/os/handler.h` 第 78-81 行

```cpp
template <typename Functor, typename... Args>
void Call(Functor&& functor, Args&&... args) {
    Post(common::BindOnce(std::forward<Functor>(functor), std::forward<Args>(args)...));
}
```

让我们逐步拆解这个函数模板：

**第一步：识别模板参数**
- `Functor`：表示"可调用对象"的类型（函数指针、lambda、函数对象等）
- `Args...`：变长参数包（后面第 3 章详解）

**第二步：识别函数参数**
- `Functor&& functor`：一个可调用对象，`&&` 是右值引用（配合 `std::forward` 实现完美转发）
- `Args&&... args`：零个或多个额外参数

**第三步：理解函数体**
- `std::forward<Functor>(functor)`：完美转发，保持 functor 的值类别（左值/右值）
- `std::forward<Args>(args)...`：展开参数包并完美转发每个参数
- `common::BindOnce(...)`：将可调用对象和参数绑定成一个闭包
- `Post(...)`：将闭包投递到消息队列

**使用示例**：

```cpp
// 调用普通函数
handler->Call(SomeFunction);

// 调用带参数的函数
handler->Call(SomeFunction, arg1, arg2);

// 调用 lambda
handler->Call([]() { /* do something */ });
```

编译器在看到 `handler->Call(SomeFunction, arg1, arg2)` 时，会推导出：
- `Functor` = `SomeFunction` 的类型
- `Args...` = `arg1的类型, arg2的类型`

然后生成对应的函数实例。

### 1.6 真实示例：Handler::CallOn

> 文件：`system/gd/os/handler.h` 第 83-87 行

```cpp
template <typename T, typename Functor, typename... Args>
void CallOn(T* obj, Functor&& functor, Args&&... args) {
    Post(common::BindOnce(std::forward<Functor>(functor), common::Unretained(obj),
                          std::forward<Args>(args)...));
}
```

与 `Call` 的区别：
- 多了一个模板参数 `T`（对象类型）
- 多了一个函数参数 `T* obj`（对象指针）
- `common::Unretained(obj)` 将裸指针包装为不管理生命周期的指针
- 用于调用**成员函数**：`handler->CallOn(device, &Device::Connect)`

---

## 2. 类模板基础

### 2.1 为什么需要类模板？

就像函数模板让函数泛型化一样，类模板让**类**泛型化。最经典的例子是容器：

```cpp
// 不用模板：每种类型写一个栈
class IntStack { int data[100]; /* ... */ };
class DoubleStack { double data[100]; /* ... */ };

// 用模板：写一次，适用所有类型
template <typename T>
class Stack {
    T data[100];
    int top = -1;
public:
    void Push(const T& value) { data[++top] = value; }
    T Pop() { return data[top--]; }
};
```

### 2.2 `template <typename T> class` 语法

```cpp
template <typename T>       // 声明类型参数 T
class ClassName {           // 类定义
    T member;               // T 可以用在成员变量
    T Method(T param);      // T 可以用在成员函数的返回值和参数
};

// 使用时必须指定 T
ClassName<int> obj;
```

语法要点：
- 类模板的模板参数声明与函数模板相同
- `T` 可以用在类的任何地方：成员变量、成员函数、嵌套类型等
- **使用类模板时必须显式指定类型参数**（编译器通常无法从上下文推导）

### 2.3 多个模板参数的类

```cpp
template <typename TKey, typename TValue>
class Dictionary {
    // TKey 和 TValue 可以在类中自由使用
    struct Entry {
        TKey key;
        TValue value;
    };
    // ...
};

Dictionary<std::string, int> word_count;
```

### 2.4 真实示例：BidiQueue<TUP, TDOWN>

> 文件：`system/gd/common/bidi_queue.h` 第 77-95 行

```cpp
template <typename TUP, typename TDOWN>
class BidiQueue {
public:
  explicit BidiQueue(size_t capacity)
      : up_queue_(capacity),
        down_queue_(capacity),
        up_end_(&down_queue_, &up_queue_),
        down_end_(&up_queue_, &down_queue_) {}

  BidiQueueEnd<TDOWN, TUP>* GetUpEnd() { return &up_end_; }
  BidiQueueEnd<TUP, TDOWN>* GetDownEnd() { return &down_end_; }

private:
  ::bluetooth::os::Queue<TUP> up_queue_;
  ::bluetooth::os::Queue<TDOWN> down_queue_;
  BidiQueueEnd<TDOWN, TUP> up_end_;
  BidiQueueEnd<TUP, TDOWN> down_end_;
};
```

**理解这个类模板**：

`BidiQueue` 是一个**双向队列**，用于蓝牙协议栈中两个层之间的数据传输：
- `TUP`：上行数据的类型（从控制器发往主机方向的数据）
- `TDOWN`：下行数据的类型（从主机发往控制器方向的数据）

**为什么需要两个类型参数？** 因为上行和下行可能传输不同类型的数据包。例如：

```cpp
// 上行传输 HCI 事件包，下行传输 HCI 命令包
BidiQueue<HciEvent, HciCommand> queue(10);
```

**注意模板参数的交叉使用**：
- `up_end_` 的类型是 `BidiQueueEnd<TDOWN, TUP>`（注意顺序反了！）
- `down_end_` 的类型是 `BidiQueueEnd<TUP, TDOWN>`
- 这是因为"上端"发送的是下行数据（`TDOWN`），接收的是上行数据（`TUP`）

### 2.5 真实示例：BidiQueueEnd<TENQUEUE, TDEQUEUE>

> 文件：`system/gd/common/bidi_queue.h` 第 31-59 行

```cpp
template <typename TENQUEUE, typename TDEQUEUE>
class BidiQueueEnd : public ::bluetooth::os::IQueueEnqueue<TENQUEUE>,
                     public ::bluetooth::os::IQueueDequeue<TDEQUEUE> {
public:
  using EnqueueCallback = Callback<std::unique_ptr<TENQUEUE>()>;
  using DequeueCallback = Callback<void()>;

  BidiQueueEnd(::bluetooth::os::IQueueEnqueue<TENQUEUE>* tx,
               ::bluetooth::os::IQueueDequeue<TDEQUEUE>* rx)
      : tx_(tx), rx_(rx) {}

  void RegisterEnqueue(::bluetooth::os::Handler* handler, EnqueueCallback callback) override {
    tx_->RegisterEnqueue(handler, callback);
  }

  void UnregisterEnqueue() override { tx_->UnregisterEnqueue(); }

  void RegisterDequeue(::bluetooth::os::Handler* handler, DequeueCallback callback) override {
    rx_->RegisterDequeue(handler, callback);
  }

  void UnregisterDequeue() override { rx_->UnregisterDequeue(); }

  std::unique_ptr<TDEQUEUE> TryDequeue() override { return rx_->TryDequeue(); }

private:
  ::bluetooth::os::IQueueEnqueue<TENQUEUE>* tx_;
  ::bluetooth::os::IQueueDequeue<TDEQUEUE>* rx_;
};
```

**理解这个类模板**：

`BidiQueueEnd` 是双向队列的一端，它有两个类型参数：
- `TENQUEUE`：该端可以**入队**（发送）的数据类型
- `TDEQUEUE`：该端可以**出队**（接收）的数据类型

**关键观察**：
1. 类模板可以继承自其他类模板：`IQueueEnqueue<TENQUEUE>` 和 `IQueueDequeue<TDEQUEUE>`
2. 模板参数可以用在 `using` 类型别名中：`Callback<std::unique_ptr<TENQUEUE>()>`
3. 模板参数可以用在成员变量类型中：`IQueueEnqueue<TENQUEUE>* tx_`

### 2.6 真实示例：Serializable<T>

> 文件：`system/gd/storage/serializable.h` 第 27-50 行

```cpp
template <typename T>
class Serializable {
public:
  Serializable() = default;
  virtual ~Serializable() = default;

  virtual std::string ToString() const = 0;

  static std::optional<T> FromString(const std::string& str) { return T::FromString(str); }

  virtual std::string ToLegacyConfigString() const = 0;

  static std::optional<T> FromLegacyConfigString(const std::string& str) {
    return T::FromLegacyConfigString(str);
  }
};
```

**理解这个类模板**：

`Serializable<T>` 是一个**序列化基类**，`T` 表示要序列化的具体类型。这个类使用了 CRTP 模式（第 5 章详解），这里先关注模板方面：

1. `T` 用在静态方法的返回类型中：`std::optional<T>`
2. `T` 用在静态方法体中调用 `T::FromString(str)`——这要求 `T` 必须有 `FromString` 静态方法
3. 使用方式：`class MyConfig : public Serializable<MyConfig> { ... };`

---

## 3. 模板的变长参数包 (Variadic Templates)

### 3.1 什么是变长参数包？

C++11 之前，要实现"接受任意数量参数"的函数，只能用 `va_list`（C 风格，类型不安全）。C++11 引入了**变长参数包 (Variadic Templates)**，让你能安全地接受任意数量、任意类型的参数。

```cpp
template <typename... Args>    // Args 是一个"参数包"，可以包含零个或多个类型
void Print(Args... args) {     // args 是与 Args 对应的"参数值包"
    // ...
}
```

- `typename... Args` 声明一个**类型参数包**
- `Args... args` 声明对应的**函数参数包**
- 参数包可以包含零个或多个参数

### 3.2 参数包展开

参数包不能直接使用，必须**展开**。最常见的方式是递归：

```cpp
// 递归终止条件：没有参数时调用这个版本
void Print() {
    std::cout << std::endl;
}

// 递归版本：取出第一个参数，剩余参数递归处理
template <typename T, typename... Rest>
void Print(T first, Rest... rest) {
    std::cout << first << " ";
    Print(rest...);  // 递归调用，rest... 展开剩余参数
}

// 使用
Print(1, 3.14, "hello", 'A');
// 输出：1 3.14 hello A
```

执行过程：
1. `Print(1, 3.14, "hello", 'A')` → T=int, Rest={double, const char*, char}
2. `Print(3.14, "hello", 'A')` → T=double, Rest={const char*, char}
3. `Print("hello", 'A')` → T=const char*, Rest={char}
4. `Print('A')` → T=char, Rest={}
5. `Print()` → 无参版本，结束递归

### 3.3 `sizeof...(Args)` 获取参数数量

```cpp
template <typename... Args>
void CountArgs(Args... args) {
    std::cout << "参数数量: " << sizeof...(Args) << std::endl;
    // sizeof...(Args) 在编译期就能确定值
}

CountArgs(1, 2, 3);      // 输出：参数数量: 3
CountArgs("hello");       // 输出：参数数量: 1
CountArgs();              // 输出：参数数量: 0
```

### 3.4 参数包展开的其他方式

**在函数调用中展开**（最常用）：

```cpp
template <typename... Args>
void ForwardPrint(Args&&... args) {
    // args... 在函数调用中展开
    Print(std::forward<Args>(args)...);
}
```

**在初始化列表中展开**：

```cpp
template <typename... Args>
void PrintWithBraces(Args... args) {
    // 使用初始化列表展开，避免递归
    int dummy[] = {(std::cout << args << " ", 0)...};
    (void)dummy;  // 抑制未使用变量警告
}
```

**C++17 折叠表达式 (Fold Expressions)**：

```cpp
template <typename... Args>
int Sum(Args... args) {
    return (args + ...);  // C++17 折叠表达式：等价于 arg1 + (arg2 + (arg3 + ...))
}
```

### 3.5 真实示例：Handler::Call 中的 `Args&&... args`

> 文件：`system/gd/os/handler.h` 第 78-81 行

```cpp
template <typename Functor, typename... Args>
void Call(Functor&& functor, Args&&... args) {
    Post(common::BindOnce(std::forward<Functor>(functor), std::forward<Args>(args)...));
}
```

**逐行分析**：

1. **`typename... Args`**：声明一个类型参数包 `Args`，可以匹配任意数量的类型
2. **`Args&&... args`**：声明函数参数包 `args`，每个参数都是右值引用（配合完美转发）
3. **`std::forward<Args>(args)...`**：这是参数包展开的关键！
   - `std::forward<Args>(args)...` 展开为 `std::forward<Arg1>(arg1), std::forward<Arg2>(arg2), ...`
   - 每个参数都被完美转发，保持原始的值类别

**具体展开示例**：

假设调用 `handler->Call(MyFunc, 42, 3.14, "hello")`：
- `Functor` = `MyFunc` 的类型
- `Args...` = `int, double, const char*`
- `args...` = `42, 3.14, "hello"`

展开后的 `std::forward<Args>(args)...` 变成：
```cpp
std::forward<int>(42), std::forward<double>(3.14), std::forward<const char*>("hello")
```

### 3.6 真实示例：Handler::CallOn 中的 `Args&&... args`

> 文件：`system/gd/os/handler.h` 第 83-87 行

```cpp
template <typename T, typename Functor, typename... Args>
void CallOn(T* obj, Functor&& functor, Args&&... args) {
    Post(common::BindOnce(std::forward<Functor>(functor), common::Unretained(obj),
                          std::forward<Args>(args)...));
}
```

与 `Call` 类似，但多了 `T* obj` 参数。调用示例：

```cpp
// 调用成员函数 Device::Connect，带一个参数
handler->CallOn(device, &Device::Connect, timeout_value);
// T = Device, Functor = void(Device::*)(int), Args = {int}
```

---

## 4. SFINAE (替换失败并非错误)

### 4.1 什么是 SFINAE？

SFINAE = **S**ubstitution **F**ailure **I**s **N**ot **A**n **E**rror（替换失败并非错误）

当编译器在实例化模板时，如果某个候选模板的参数替换失败，编译器**不会报错**，而是**跳过这个候选**，继续尝试其他候选。

这听起来很抽象，让我们用一个简单的例子来说明：

```cpp
// 版本1：T 必须有 size() 方法
template <typename T>
auto GetSize(const T& obj) -> decltype(obj.size()) {
    return obj.size();
}

// 版本2：兜底版本，T 没有 size() 方法时使用
template <typename T>
int GetSize(const T& obj) {
    return sizeof(obj);
}

std::vector<int> v = {1, 2, 3};
GetSize(v);    // 调用版本1：v.size() 有效，返回 3

int x = 42;
GetSize(x);    // 调用版本2：int 没有 size() 方法，版本1替换失败，但不报错
```

### 4.2 `std::enable_if` 的作用

`std::enable_if` 是 SFINAE 最常用的工具。它的定义（简化版）如下：

```cpp
// 当 Condition 为 true 时，enable_if 有一个 type 成员，类型为 T
template <bool Condition, typename T = void>
struct enable_if {
    using type = T;   // 只在 Condition = true 时存在
};

// 当 Condition 为 false 时，enable_if 没有 type 成员
template <typename T>
struct enable_if<false, T> {
    // 没有 type 成员！
};
```

**核心思想**：当条件为 `false` 时，`enable_if<false, T>::type` 不存在，导致模板替换失败，该候选被跳过。

### 4.3 `enable_if` 的两种常见用法

**用法一：作为默认模板参数（推荐）**

```cpp
template <typename T, typename std::enable_if<std::is_integral_v<T>, int>::type = 0>
void Process(T value) {
    std::cout << "处理整数: " << value << std::endl;
}
```

解析：
- `std::is_integral_v<T>`：判断 T 是否为整数类型
- 当 T 是整数类型时，`std::enable_if<true, int>::type` = `int`，模板变成 `template <typename T, int = 0>`，有效
- 当 T 不是整数类型时，`std::enable_if<false, int>::type` 不存在，替换失败，该模板被跳过

**用法二：作为函数返回类型**

```cpp
template <typename T>
typename std::enable_if<std::is_integral_v<T>, T>::type Process(T value) {
    return value;
}
```

### 4.4 C++17 的简化写法

C++17 引入了 `if constexpr`，可以在编译期根据条件选择代码路径：

```cpp
template <typename T>
auto Process(T value) {
    if constexpr (std::is_integral_v<T>) {
        std::cout << "处理整数: " << value << std::endl;
    } else if constexpr (std::is_floating_point_v<T>) {
        std::cout << "处理浮点数: " << value << std::endl;
    } else {
        std::cout << "处理其他类型" << std::endl;
    }
}
```

但 `if constexpr` 不能完全替代 SFINAE——当你需要**不同的函数签名**时，仍然需要 SFINAE。

### 4.5 常用的类型判断工具

C++ `<type_traits>` 头文件提供了丰富的类型判断工具：

| 判断工具 | 含义 |
|---------|------|
| `std::is_integral_v<T>` | T 是否为整数类型（int, long, char 等） |
| `std::is_enum_v<T>` | T 是否为枚举类型 |
| `std::is_same_v<T, U>` | T 和 U 是否为相同类型 |
| `std::is_base_of_v<Base, Derived>` | Base 是否为 Derived 的基类 |
| `std::is_pointer_v<T>` | T 是否为指针类型 |
| `std::is_class_v<T>` | T 是否为类/结构体类型 |

### 4.6 核心真实示例：MutationEntry::Set 的多个重载

> 文件：`system/gd/storage/mutation_entry.h` 第 34-86 行

这是 SFINAE 最精彩的实战案例！`MutationEntry::Set` 有**6 个模板重载**，每个重载针对不同的类型，通过 `enable_if` 在编译期自动选择正确的版本。

#### 重载 1：整数类型

```cpp
template <typename T, typename std::enable_if<std::is_integral_v<T>, int>::type = 0>
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, T value_param) {
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              std::to_string(value_param));
}
```

**解读**：
- 当 `T` 是整数类型（`int`, `long`, `short`, `char` 等）时，此重载被启用
- 实现方式：调用 `std::to_string()` 将整数转为字符串
- **注意**：`bool` 虽然也是整数类型，但后面有专门的 bool 重载，优先级更高（`is_same_v` 比 `is_integral_v` 更具体）

#### 重载 2：枚举类型

```cpp
template <typename T, typename std::enable_if<std::is_enum_v<T>, int>::type = 0>
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, T value_param) {
    using EnumUnderlyingType = typename std::underlying_type_t<T>;
    return MutationEntry::Set<EnumUnderlyingType>(property_type, std::move(section_param),
                                                  std::move(property_param),
                                                  static_cast<EnumUnderlyingType>(value_param));
}
```

**解读**：
- 当 `T` 是枚举类型时，此重载被启用
- `std::underlying_type_t<T>`：获取枚举的底层整数类型
- 实现方式：将枚举值转为底层整数，然后递归调用整数版本的 `Set`

#### 重载 3：bool 类型

```cpp
template <typename T, typename std::enable_if<std::is_same_v<T, bool>, int>::type = 0>
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, T value_param) {
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              common::ToString(value_param));
}
```

**解读**：
- 当 `T` 是 `bool` 时，此重载被启用
- `std::is_same_v<T, bool>`：判断 T 是否恰好是 bool
- 实现方式：使用 `common::ToString()` 将 bool 转为 "true"/"false" 字符串
- **为什么需要单独的 bool 重载？** 因为 `std::to_string(true)` 会输出 "1" 而不是 "true"

#### 重载 4：std::string 类型

```cpp
template <typename T, typename std::enable_if<std::is_same_v<T, std::string>, int>::type = 0>
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, T value_param) {
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              std::move(value_param));
}
```

**解读**：
- 当 `T` 是 `std::string` 时，此重载被启用
- 实现方式：直接将字符串传递给最终的非模板 `Set` 方法

#### 重载 5：Serializable 子类

```cpp
template <typename T,
          typename std::enable_if<std::is_base_of_v<Serializable<T>, T>, int>::type = 0>
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, const T& value_param) {
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              value_param.ToLegacyConfigString());
}
```

**解读**：
- 当 `T` 继承自 `Serializable<T>` 时（即 T 是 CRTP 的派生类），此重载被启用
- `std::is_base_of_v<Serializable<T>, T>`：判断 `Serializable<T>` 是否是 `T` 的基类
- 实现方式：调用 `ToLegacyConfigString()` 将对象序列化为字符串

#### 重载 6：vector\<Serializable\> 类型

```cpp
template <typename T, typename std::enable_if<
                              bluetooth::common::is_specialization_of<T, std::vector>::value &&
                                      std::is_base_of_v<Serializable<typename T::value_type>,
                                                        typename T::value_type>,
                              int>::type = 0>
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, const T& value_param) {
    std::vector<std::string> str_values;
    str_values.reserve(value_param.size());
    for (const auto& v : value_param) {
        str_values.push_back(v.ToLegacyConfigString());
    }
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              common::StringJoin(str_values, " "));
}
```

**解读**：
- 条件 1：`is_specialization_of<T, std::vector>::value`——T 是否是 `std::vector` 的特化
- 条件 2：`std::is_base_of_v<Serializable<typename T::value_type>, typename T::value_type>`——vector 的元素类型是否继承自 `Serializable`
- 两个条件**同时满足**时，此重载才被启用
- 实现方式：遍历 vector，对每个元素调用 `ToLegacyConfigString()`，然后用空格连接

#### 最终的非模板重载

```cpp
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, std::string value_param) {
    return MutationEntry(EntryType::SET, property_type, std::move(section_param),
                         std::move(property_param), std::move(value_param));
}
```

这是最终被所有模板重载调用的"落地"函数，接受 `std::string` 类型的值参数。

#### SFINAE 选择流程图

```
调用 MutationEntry::Set(property_type, section, property, value)
                │
                ▼
        value 的类型 T 是什么？
                │
    ┌───────────┼───────────┬───────────┬───────────┬───────────┬───────────┐
    ▼           ▼           ▼           ▼           ▼           ▼           ▼
  is_same_v   is_same_v  is_enum_v  is_integral_v  is_base_of  is_vector   非模板
  <T,bool>   <T,string>              (非bool)     <Serializable,  +元素     版本
    │           │           │           │           │  T>        是Serializable
    ▼           ▼           ▼           ▼           ▼           ▼
  ToString   直接传递   转底层整数  to_string   ToLegacy    遍历+Join   直接构造
  (bool)    (string)   再转整数   (整数)     ConfigString  (vector)
```

### 4.7 is_specialization_of 辅助模板

> 文件：`system/gd/common/type_helper.h` 第 25-28 行

```cpp
template <typename T, template <typename...> class TemplateType>
struct is_specialization_of : std::false_type {};

template <template <typename...> class TemplateType, typename... Args>
struct is_specialization_of<TemplateType<Args...>, TemplateType> : std::true_type {};
```

**解读**：

这是一个**模板的偏特化**（第 6 章详解），用来判断一个类型是否是某个模板的特化版本。

- 第一个定义是通用版本：对于任意类型 `T`，它不是 `TemplateType` 的特化，继承 `std::false_type`
- 第二个定义是偏特化版本：当 `T` 恰好是 `TemplateType<Args...>` 的形式时，继承 `std::true_type`

使用示例：
```cpp
is_specialization_of<std::vector<int>, std::vector>::value   // true
is_specialization_of<std::string, std::vector>::value        // false
is_specialization_of<std::list<double>, std::vector>::value  // false
```

---

## 5. CRTP (奇异递归模板模式)

### 5.1 什么是 CRTP？

CRTP = **C**uriously **R**ecurring **T**emplate **P**attern（奇异递归模板模式）

它的基本形式是：

```cpp
template <typename T>
class Base {
    // 可以调用 T 的方法
};

class Derived : public Base<Derived> {
    // 实现 T 应有的方法
};
```

"奇异"的地方在于：派生类把自己作为模板参数传给了基类。这看起来像是递归，但实际上不是——因为 `Base<Derived>` 在 `Derived` 定义之前就已经完成了实例化。

### 5.2 CRTP vs 虚函数多态

**传统虚函数多态（运行时多态）**：

```cpp
class Animal {
public:
    virtual void Speak() = 0;  // 虚函数，运行时通过虚函数表调用
    virtual ~Animal() = default;
};

class Dog : public Animal {
public:
    void Speak() override { std::cout << "Woof!" << std::endl; }
};

Animal* a = new Dog();
a->Speak();  // 运行时查找虚函数表，调用 Dog::Speak
```

**CRTP 多态（编译期多态）**：

```cpp
template <typename T>
class Animal {
public:
    void Speak() {
        static_cast<T*>(this)->SpeakImpl();  // 编译期确定调用哪个函数
    }
};

class Dog : public Animal<Dog> {
public:
    void SpeakImpl() { std::cout << "Woof!" << std::endl; }
};

Dog d;
d.Speak();  // 编译期就确定了调用 Dog::SpeakImpl，没有虚函数表开销
```

### 5.3 CRTP 的优势

| 特性 | 虚函数多态 | CRTP 多态 |
|------|-----------|----------|
| 绑定时机 | 运行时 | 编译期 |
| 性能开销 | 虚函数表查找 | 无（直接调用） |
| 代码膨胀 | 无 | 有（每个派生类生成一份基类代码） |
| 灵活性 | 可以用基类指针管理不同派生类 | 不能用基类指针（类型不同） |
| 适用场景 | 需要运行时多态 | 需要编译期多态、零开销抽象 |

### 5.4 核心真实示例：Serializable\<T\>

> 文件：`system/gd/storage/serializable.h` 第 27-50 行

```cpp
template <typename T>
class Serializable {
public:
  Serializable() = default;
  virtual ~Serializable() = default;

  // 序列化为字符串
  virtual std::string ToString() const = 0;

  // CRTP：从字符串反序列化，调用子类的静态方法
  static std::optional<T> FromString(const std::string& str) {
    return T::FromString(str);
  }

  // 序列化为旧版配置字符串
  virtual std::string ToLegacyConfigString() const = 0;

  // CRTP：从旧版配置字符串反序列化
  static std::optional<T> FromLegacyConfigString(const std::string& str) {
    return T::FromLegacyConfigString(str);
  }
};
```

**CRTP 体现在哪里？**

看 `FromString` 方法：
```cpp
static std::optional<T> FromString(const std::string& str) {
    return T::FromString(str);  // 调用 T（子类）的静态方法
}
```

基类 `Serializable<T>` 中调用了 `T::FromString(str)`，而 `T` 就是派生类本身。这意味着：
- 基类**要求**派生类必须实现 `FromString` 静态方法
- 基类通过 `T::` 来调用派生类的方法，而不需要虚函数

**实际使用**：

```cpp
// 定义一个可序列化的配置类
class DeviceConfig : public Serializable<DeviceConfig> {
public:
    // 必须实现 ToString（虚函数要求）
    std::string ToString() const override {
        return name_ + ":" + std::to_string(id_);
    }

    // 必须实现 ToLegacyConfigString（虚函数要求）
    std::string ToLegacyConfigString() const override {
        return name_ + " " + std::to_string(id_);
    }

    // 必须实现 FromString（CRTP 要求，T::FromString 会调用这里）
    static std::optional<DeviceConfig> FromString(const std::string& str) {
        // 解析字符串，构造 DeviceConfig
        // ...
        return DeviceConfig(/* ... */);
    }

    // 必须实现 FromLegacyConfigString（CRTP 要求）
    static std::optional<DeviceConfig> FromLegacyConfigString(const std::string& str) {
        // 解析旧版配置字符串
        // ...
        return DeviceConfig(/* ... */);
    }

private:
    std::string name_;
    int id_;
};

// 使用
DeviceConfig config;
std::string str = config.ToString();  // 调用虚函数
auto parsed = Serializable<DeviceConfig>::FromString(str);  // 通过 CRTP 调用 DeviceConfig::FromString
auto parsed2 = DeviceConfig::FromString(str);  // 也可以直接调用
```

**为什么用 CRTP 而不是纯虚函数？**

因为 `FromString` 是**静态方法**，它需要返回 `T`（派生类类型），而虚函数不能是静态的。CRTP 让基类可以在静态方法中"知道"派生类的类型，从而调用派生类的静态方法。

### 5.5 CRTP 的编译期检查

如果派生类没有实现所需的方法，编译器会直接报错：

```cpp
class BadConfig : public Serializable<BadConfig> {
    // 忘记实现 FromString！
};

// 编译错误：BadConfig::FromString 不存在
auto result = Serializable<BadConfig>::FromString("test");
```

这种编译期检查正是 CRTP 的价值——错误在编译期就被发现，而不是运行时。

---

## 6. 模板特化

### 6.1 什么是模板特化？

模板特化是指：为模板的**某个特定类型**提供专门的实现。就像一个通用规则有一个例外情况。

**全特化**：为所有模板参数都指定具体类型。
**偏特化**：只为部分模板参数指定类型，或对类型施加约束。

### 6.2 函数模板的全特化

```cpp
// 通用模板
template <typename T>
std::string ToString(T value) {
    return std::to_string(value);
}

// 全特化：当 T = std::string 时的特殊实现
template <>
std::string ToString<std::string>(std::string value) {
    return value;  // string 不需要转换，直接返回
}

ToString(42);          // 调用通用模板
ToString(std::string("hello"));  // 调用特化版本
```

### 6.3 类模板的全特化

```cpp
// 通用模板
template <typename T>
class Comparator {
public:
    static bool Equal(const T& a, const T& b) {
        return a == b;
    }
};

// 全特化：当 T = const char* 时，比较字符串内容而不是指针
template <>
class Comparator<const char*> {
public:
    static bool Equal(const char* const& a, const char* const& b) {
        return strcmp(a, b) == 0;
    }
};

Comparator<int>::Equal(3, 3);                    // true，用通用模板
Comparator<const char*>::Equal("abc", "abc");    // true，用特化版本
```

### 6.4 类模板的偏特化

偏特化是对模板参数施加约束，但不完全指定所有参数：

```cpp
// 通用模板
template <typename T, typename U>
class Pair {
public:
    T first;
    U second;
};

// 偏特化：当两个类型相同时
template <typename T>
class Pair<T, T> {
public:
    T first;
    T second;
    // 可以提供针对相同类型的特殊实现
};

// 偏特化：当第二个类型是指针时
template <typename T, typename U>
class Pair<T, U*> {
public:
    T first;
    U* second;
    // 可以提供指针类型的特殊处理
};
```

### 6.5 真实示例：`std::hash<Uuid>` 全特化

> 文件：`system/types/include/bluetooth/types/uuid.h` 第 133-145 行

```cpp
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

**为什么要特化 `std::hash`？**

`std::unordered_map` 和 `std::unordered_set` 需要键类型有对应的 `std::hash` 特化。标准库只为基本类型（`int`, `string` 等）提供了 `std::hash` 特化。自定义类型如果要用作哈希表的键，必须自己特化 `std::hash`。

**代码解读**：

1. `template <>` 表示这是一个**全特化**——所有模板参数都已指定
2. `struct hash<bluetooth::Uuid>`：特化 `std::hash`，专门处理 `bluetooth::Uuid` 类型
3. `operator()` 是哈希函数，接受 `Uuid` 引用，返回 `std::size_t` 哈希值
4. 实现方式：将 UUID 的 128 位字节转为 `std::string`，然后复用 `std::hash<std::string>`

**使用效果**：

```cpp
// 没有 std::hash<Uuid> 特化时，这行代码会编译失败
std::unordered_map<bluetooth::Uuid, Device> device_map;

// 有了特化后，Uuid 可以作为哈希表的键
device_map[uuid] = device;
```

### 6.6 真实示例：`std::hash<RawAddress>` 全特化

> 文件：`system/types/include/bluetooth/types/address.h` 第 71-79 行

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

**代码解读**：

1. `RawAddress` 是蓝牙 MAC 地址，6 字节（`kLength = 6`）
2. 将 6 字节地址拷贝到 `uint64_t` 中（高位 2 字节为 0）
3. 复用 `std::hash<uint64_t>` 计算哈希值

**与 `std::hash<Uuid>` 的对比**：

| 特性 | `hash<Uuid>` | `hash<RawAddress>` |
|------|-------------|-------------------|
| 数据大小 | 16 字节 | 6 字节 |
| 转换方式 | 转为 string 再哈希 | 转为 uint64_t 再哈希 |
| 效率 | 较低（涉及字符串构造） | 较高（直接整数运算） |

### 6.7 真实示例：is_specialization_of 偏特化

> 文件：`system/gd/common/type_helper.h` 第 25-28 行

```cpp
// 通用版本：T 不是 TemplateType 的特化
template <typename T, template <typename...> class TemplateType>
struct is_specialization_of : std::false_type {};

// 偏特化版本：当 T 的形式恰好是 TemplateType<Args...> 时
template <template <typename...> class TemplateType, typename... Args>
struct is_specialization_of<TemplateType<Args...>, TemplateType> : std::true_type {};
```

**偏特化体现在哪里？**

第二个定义中，第一个模板参数不是任意的 `typename T`，而是 `TemplateType<Args...>`——这是一个**模式匹配**。当编译器看到 `is_specialization_of<std::vector<int>, std::vector>` 时：
- 尝试通用版本：`T = std::vector<int>`, `TemplateType = std::vector`，可以匹配
- 尝试偏特化版本：`TemplateType<Args...>` 匹配 `std::vector<int>`，得出 `TemplateType = std::vector`, `Args = {int}`，匹配成功
- 偏特化优先级更高，所以选择偏特化版本，继承 `std::true_type`

---

## 7. 模板在实际开发中的应用场景

### 7.1 容器类型的通用化

模板最常见的用途是让容器能存储任意类型的数据。

**蓝牙协议栈中的例子**：

```cpp
// Queue<T>：通用队列，可以存储任何类型
::bluetooth::os::Queue<TUP> up_queue_;     // 上行队列
::bluetooth::os::Queue<TDOWN> down_queue_; // 下行队列

// BidiQueue<TUP, TDOWN>：双向队列，两个方向可以有不同的数据类型
BidiQueue<HciEvent, HciCommand> hci_queue(10);
```

如果没有模板，你需要为每种数据类型写一个队列类，代码重复且难以维护。

### 7.2 类型安全的回调

模板让回调机制既灵活又类型安全。

**蓝牙协议栈中的例子**：

```cpp
// Callback<ReturnType(Args...)>：类型安全的回调
using EnqueueCallback = Callback<std::unique_ptr<TENQUEUE>()>;

// BindOnce<Functor, Args...>：将函数和参数绑定为闭包
handler->Call(MyFunction, arg1, arg2);
```

对比 C 风格的函数指针回调：

```cpp
// C 风格：类型不安全
void register_callback(void (*cb)(void* user_data), void* user_data);

// C++ 模板风格：类型安全
template <typename Functor, typename... Args>
void Call(Functor&& functor, Args&&... args);
```

模板回调的优势：
- **编译期类型检查**：参数类型不匹配时编译失败，而不是运行时崩溃
- **不需要 `void*` 用户数据**：参数直接绑定到闭包中
- **支持任意可调用对象**：函数指针、lambda、函数对象、成员函数

### 7.3 编译期类型检查

SFINAE 和 `enable_if` 让你在编译期就确保类型正确，而不是运行时才发现问题。

**蓝牙协议栈中的例子**：

```cpp
// MutationEntry::Set 通过 SFINAE 确保只有合法类型才能调用
MutationEntry::Set(NORMAL, "section", "property", 42);        // OK：整数
MutationEntry::Set(NORMAL, "section", "property", true);      // OK：bool
MutationEntry::Set(NORMAL, "section", "property", "hello"s);  // OK：string
MutationEntry::Set(NORMAL, "section", "property", 3.14);      // 编译错误！没有匹配的重载
```

如果不使用 SFINAE，你可能会写一个接受 `void*` 的函数，然后在运行时检查类型——既不安全又容易出错。

### 7.4 零开销抽象

CRTP 让你在不引入虚函数开销的情况下实现多态。

**蓝牙协议栈中的例子**：

```cpp
// Serializable<T> 通过 CRTP 实现编译期多态
// 基类可以调用子类的静态方法，没有虚函数表开销
static std::optional<T> FromString(const std::string& str) {
    return T::FromString(str);  // 直接调用，无虚函数表查找
}
```

### 7.5 标准库扩展

模板特化让你能将自定义类型无缝融入标准库。

**蓝牙协议栈中的例子**：

```cpp
// 特化 std::hash，让自定义类型可以用在 unordered_map 中
std::unordered_map<bluetooth::Uuid, Device> device_map;
std::unordered_map<RawAddress, Connection> connection_map;

// 特化 std::formatter，让自定义类型支持 std::format
std::cout << std::format("UUID: {}", uuid);
```

---

## 8. 初学者如何阅读模板代码

### 8.1 先忽略模板参数，把 T 当作具体类型看

面对复杂的模板代码，第一步是**把所有模板参数替换成具体类型**，理解代码的逻辑。

**示例**：

```cpp
// 原始模板代码
template <typename TENQUEUE, typename TDEQUEUE>
class BidiQueueEnd {
    using EnqueueCallback = Callback<std::unique_ptr<TENQUEUE>()>;
    std::unique_ptr<TDEQUEUE> TryDequeue() override;
};
```

**替换后**（假设 `TENQUEUE = HciCommand`, `TDEQUEUE = HciEvent`）：

```cpp
class BidiQueueEnd {
    using EnqueueCallback = Callback<std::unique_ptr<HciCommand>()>;
    std::unique_ptr<HciEvent> TryDequeue() override;
};
```

替换后是不是清晰多了？这就是一个入队命令、出队事件的队列端点。

### 8.2 从实例化的地方反推模板参数的含义

当你看到 `template <typename T>` 但不知道 `T` 代表什么时，**找到使用这个模板的地方**：

```cpp
// 看到模板定义
template <typename T>
class Serializable { ... };

// 找到使用的地方
class DeviceConfig : public Serializable<DeviceConfig> { ... };
class AdapterConfig : public Serializable<AdapterConfig> { ... };
```

从使用处可以推断：`T` 就是"要序列化的类型本身"。

### 8.3 不要试图一次性理解所有模板元编程

模板元编程可以非常复杂。对于初学者，建议：

1. **先理解基本用法**：函数模板、类模板、模板参数推导
2. **再理解 SFINAE**：`enable_if` 的基本用法
3. **然后理解 CRTP**：基类如何调用派生类的方法
4. **最后理解模板特化**：全特化和偏特化
5. **暂时跳过**：表达式模板、模板元编程的递归计算等高级话题

### 8.4 阅读模板代码的检查清单

遇到一段模板代码时，按以下步骤分析：

1. **识别模板参数**：有几个？分别叫什么？
2. **识别约束条件**：有没有 `enable_if`？条件是什么？
3. **找到实例化点**：这个模板在哪里被使用？传入了什么类型？
4. **替换具体类型**：把模板参数替换成具体类型，理解代码逻辑
5. **理解参数包**：如果有 `...`，想想展开后会是什么样子

### 8.5 常见错误与调试技巧

**错误 1：模板参数推导失败**

```cpp
template <typename T>
void Foo(T a, T b) { }

Foo(3, 3.14);  // 错误：T 是 int 还是 double？
```

解决：显式指定 `Foo<double>(3, 3.14)` 或使用两个模板参数。

**错误 2：SFINAE 条件重叠**

```cpp
// bool 既是整数类型，又有 is_same_v<T, bool> 为 true
// 两个重载都可能匹配，导致二义性
```

解决：确保条件互斥，或让更具体的条件优先（`is_same_v` 比 `is_integral_v` 更具体）。

**错误 3：CRTP 忘记实现方法**

```cpp
class BadConfig : public Serializable<BadConfig> {
    // 忘记实现 FromString
};
// 编译错误：BadConfig::FromString 未定义
```

解决：确保派生类实现了 CRTP 要求的所有方法。

**调试技巧**：

1. **阅读编译错误**：模板错误信息通常很长，但关键信息在最后几行——那里会告诉你哪个类型不匹配
2. **使用 `static_assert`**：在模板中插入 `static_assert` 来验证类型特征
3. **简化模板**：如果编译错误难以理解，尝试用具体类型替换模板参数，逐步定位问题

---

## 附录：关键概念速查表

| 概念 | 语法 | 用途 |
|------|------|------|
| 函数模板 | `template <typename T> void Foo(T x)` | 泛型函数 |
| 类模板 | `template <typename T> class Foo { }` | 泛型类 |
| 变长参数包 | `typename... Args` | 接受任意数量参数 |
| 参数包展开 | `args...` | 将参数包展开为逗号分隔的列表 |
| SFINAE | `std::enable_if<condition, T>::type` | 根据条件启用/禁用模板 |
| CRTP | `class Derived : public Base<Derived>` | 编译期多态 |
| 全特化 | `template <> class Foo<int> { }` | 为特定类型提供专门实现 |
| 偏特化 | `template <typename T> class Foo<T*> { }` | 为某一类类型提供专门实现 |
| `std::is_integral_v<T>` | 类型判断 | T 是否为整数类型 |
| `std::is_same_v<T, U>` | 类型判断 | T 和 U 是否相同 |
| `std::is_base_of_v<B, D>` | 类型判断 | B 是否为 D 的基类 |
| `std::forward<T>(x)` | 完美转发 | 保持参数的值类别 |
| `sizeof...(Args)` | 参数包大小 | 获取参数包中参数的数量 |

---

> **总结**：模板是 C++ 最强大的特性之一，它让代码既泛型又类型安全。蓝牙协议栈中的 `Handler::Call`、`BidiQueue`、`MutationEntry::Set`、`Serializable<T>`、`std::hash` 特化等，都是模板在实际项目中的典型应用。掌握模板，你就能写出更灵活、更安全、更高效的 C++ 代码。
