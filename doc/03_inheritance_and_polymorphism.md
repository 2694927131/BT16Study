# C++ 继承与多态 —— 基于蓝牙协议栈的实战教程

> **目标读者**: C++ 刚入门的初学者
> **前置知识**: 了解 C++ 类的基本概念（class、成员函数、构造/析构函数）
> **代码来源**: Android 蓝牙协议栈 (Fluoride / Bluedroid)

---

## 目录

1. [继承的基本概念](#1-继承的基本概念)
2. [虚函数与多态](#2-虚函数与多态)
3. [override 关键字 (C++11)](#3-override-关键字-c11)
4. [纯虚函数与抽象类](#4-纯虚函数与抽象类)
5. [虚析构函数](#5-虚析构函数)
6. [多继承](#6-多继承)
7. [虚继承](#7-虚继承)
8. [接口设计模式](#8-接口设计模式)
9. [阅读继承关系的技巧](#9-阅读继承关系的技巧)

---

## 1. 继承的基本概念

### 1.1 什么是继承？

**继承（Inheritance）** 是面向对象编程的三大特性之一（另外两个是封装和多态）。它允许我们定义一个新类，这个新类可以"继承"已有类的属性和方法。

用生活中的例子来说：如果你要设计一个"学生管理系统"，你可能需要 `Student`（学生）、`Teacher`（教师）等类。它们都有一些共同特征——比如都有姓名、年龄、联系方式。这时就可以先定义一个 `Person`（人）基类，然后让 `Student` 和 `Teacher` 继承它。

### 1.2 基本语法：`class Derived : public Base`

```cpp
// 基类（父类）
class Animal {
public:
    std::string name;
    int age;

    void eat() { std::cout << name << " is eating.\n"; }
};

// 派生类（子类）—— 通过 : public Animal 继承
class Dog : public Animal {
public:
    void bark() { std::cout << name << " says: Woof!\n"; }
};

// 使用
int main() {
    Dog myDog;
    myDog.name = "旺财";   // 继承自 Animal 的成员
    myDog.age = 3;         // 继承自 Animal 的成员
    myDog.eat();           // 调用继承自 Animal 的方法 → "旺财 is eating."
    myDog.bark();          // 调用自己定义的方法     → "旺财 says: Woof!"
}
```

**关键语法点**：
- `:` 冒号后面跟继承方式 + 基类名
- `public` 是最常用的继承方式（后面会详细讲三种方式的区别）
- 派生类自动拥有基类的所有 `public` 和 `protected` 成员

### 1.3 三种继承方式的区别

| 继承方式 | 基类 public 成员在派生类中变成 | 基类 protected 成员在派生类中变成 | 基类 private 成员 |
|---------|------|------|------|
| **public 继承** | public | protected | **不可访问** |
| **protected 继承** | protected | protected | **不可访问** |
| **private 继承** | private | private | **不可访问** |

> **注意**：无论哪种继承方式，基类的 **private 成员永远不能在派生类中直接访问**！它们虽然被继承了（占用了内存），但对外部不可见。

```cpp
class Base {
public:      int pub = 1;
protected:   int prot = 2;
private:     int priv = 3;
};

// ========== public 继承 ==========
class PubDerived : public Base {
    void test() {
        pub;    // ✅ public（保持不变）
        prot;   // ✅ protected（降一级）
        // priv; // ❌ 编译错误！private 成员不可访问
    }
};
// 外部使用时：pub 可访问，prot 和 priv 不可访问

// ========== protected 继承 ==========
class ProtDerived : protected Base {
    void test() {
        pub;    // ✅ 变成了 protected
        prot;   // ✅ 保持 protected
        // priv; // ❌ 仍然不可访问
    }
};
// 外部使用时：pub、prot、priv 都不可访问（全部变成了 protected 或更严格）

// ========== private 继承 ==========
class PrivDerived : private Base {
    void test() {
        pub;    // ✅ 变成了 private
        prot;   // ✅ 变成了 private
        // priv; // ❌ 仍然不可访问
    }
};
// 外部使用时：所有成员都不可访问
```

### 1.4 is-a 关系：什么时候该用继承？

**public 继承表达的是 "is-a"（是一个）关系**：

```cpp
// ✅ 正确的 is-a 关系：狗是一种动物
class Dog : public Animal { };

// ✅ 正确的 is-a 关系：ControllerImpl 是一种 Controller
// （来自蓝牙协议栈真实代码）
class ControllerImpl : public Controller { };  // controller_impl.h:34

// ❌ 错误的设计：汽车不是一种发动机！这是 has-a 关系，应该用组合
class Car : public Engine { ... };  // ❌ 不要这样写！

// ✅ 正确的做法：汽车"拥有"一个引擎（组合）
class Car {
    Engine engine_;  // 组合：has-a 关系
};
```

**判断标准**：如果"A 是 B 的一种"，就用继承；如果"A 有一个 B"，就用组合。

> **蓝牙协议栈中的例子**：`ControllerImpl`（控制器实现）**是** `Controller`（控制器接口）的一种具体实现。这完全符合 is-a 关系。

### ☕ Java 类比

| 特性 | C++ | Java |
|------|-----|------|
| 继承语法 | `class Derived : public Base` | `class Derived extends Base` |
| 继承方式选择 | `public`/`protected`/`private` | 只有 `public`（相当于 C++ 的 public 继承） |
| 默认继承方式 | `private`（class）/ `public`（struct） | 始终 `public` |

**对比代码**：

```cpp
// C++: 必须指定继承方式
class ControllerImpl : public Controller { };   // public 继承
class ControllerImpl : protected Controller { }; // protected 继承（罕见）
class ControllerImpl : private Controller { };   // private 继承（罕见）
```

```java
// Java: 只有 public 继承，无需指定
public class ControllerImpl extends Controller { }  // 唯一方式
```

**关键差异**：
- Java **只有 `public` 继承**，没有 `protected` 和 `private` 继承。C++ 的三种继承方式在 Java 中简化为一种
- Java 用 `extends` 关键字，语义更清晰；C++ 用 `: public`，更简洁但需要记住继承方式
- Java 的 `extends` 只能继承一个类（单继承），C++ 可以继承多个类（多继承，第 6 节详解）

---

## 2. 虚函数与多态

### 2.1 为什么需要多态？

假设你在开发一个绘图程序，需要画不同的形状：

```cpp
// ❌ 没有 virtual 的版本 —— 静态绑定（编译期决定调用哪个函数）
class Shape {
public:
    void draw() { cout << "Drawing a shape\n"; }  // 注意：没有 virtual
};

class Circle : public Shape {
public:
    void draw() { cout << "Drawing a circle\n"; }  // 重写了 draw()
};

class Rectangle : public Shape {
public:
    void draw() { cout << "Drawing a rectangle\n"; }
};

int main() {
    Circle c;
    Rectangle r;

    Shape* s1 = &c;   // 基类指针指向派生类对象
    Shape& s2 = r;     // 基类引用绑定派生类对象

    s1->draw();  // 输出："Drawing a shape"  ← 不是我们期望的！
    s2.draw();   // 输出："Drawing a shape"  ← 也不是我们期望的！

    c.draw();    // 输出："Drawing a circle"     ← 只有直接调用才正确
    r.draw();    // 输出："Drawing a rectangle"
}
```

**问题**：通过基类指针或引用调用时，编译器根据指针类型（`Shape*`）来决定调用哪个函数，而不是根据实际对象类型。这叫 **静态绑定（Static Binding）** 或 **早绑定（Early Binding）**。

### 2.2 virtual 关键字：开启动态绑定

```cpp
// ✅ 加上 virtual 的版本 —— 动态绑定（运行期决定调用哪个函数）
class Shape {
public:
    virtual void draw() { cout << "Drawing a shape\n"; }  // 加了 virtual！
};

class Circle : public Shape {
public:
    void draw() override { cout << "Drawing a circle\n"; }  // override 更安全（下节详述）
};

class Rectangle : public Shape {
public:
    void draw() override { cout << "Drawing a rectangle\n"; }
};

int main() {
    Circle c;
    Rectangle r;

    Shape* shapes[] = { &c, &r };

    for (Shape* s : shapes) {
        s->draw();
        // 输出：
        // "Drawing a circle"     ← 根据实际对象类型调用！
        // "Drawing a rectangle"  ← 这就是多态！
    }
}
```

**关键区别**：
- **virtual 函数**：通过基类指针/引用调用时，程序在 **运行时** 根据对象的实际类型来决定调用哪个版本的函数 → **动态绑定（Dynamic Binding）**
- **普通函数**：在 **编译时** 就确定了调用哪个版本 → **静态绑定**

### 2.3 动态绑定的原理：vtable 与 vptr

当你在一个类中声明了 `virtual` 函数后，编译器会为这个类做两件事：

#### vtable（虚函数表）

每个有虚函数的类，编译器都会生成一个 **虚函数表（Virtual Function Table, 简称 vtable）**。这是一个静态的函数指针数组，存储着该类所有虚函数的地址。

```
                    Shape 的 vtable                Circle 的 vtable
                ┌──────────────────┐          ┌──────────────────┐
                │ &Shape::draw     │          │ &Circle::draw     │  ← 覆盖了基类
                └──────────────────┘          └──────────────────┘
```

#### vptr（虚函数表指针）

每个对象内部都会被编译器悄悄插入一个 **虚函数表指针（vptr）**，指向所属类的 vtable：

```
Circle 对象内存布局：
┌─────────────┐
│  vptr ──────│──→ Circle 的 vtable ──→ [&Circle::draw]
├─────────────┤
│  其他成员... │
└─────────────┘
```

**动态绑定的过程**：

```
s->draw() 的执行过程：

1. 编译器看到 s 是 Shape* 类型，且 draw() 是 virtual 函数
2. 运行时：通过 s 对象内部的 vptr 找到对应的 vtable
3. 在 vtable 中找到 draw() 的函数指针
4. 跳转到那个函数执行

如果 s 实际指向的是 Circle 对象：
  vptr → Circle::vtable → &Circle::draw() → 输出 "Drawing a circle"

如果 s 实际指向的是 Rectangle 对象：
  vptr → Rectangle::vtable → &Rectangle::draw() → 输出 "Drawing a rectangle"
```

### 2.4 虚函数在蓝牙协议栈中的核心地位

在 Android 蓝牙协议栈中，**几乎所有的模块间通信都依赖虚函数多态**。这是因为协议栈需要支持多种硬件平台（Qualcomm、Broadcom、MediaTek 等不同芯片厂商），而不同芯片的操作方式各不相同。

核心设计思想：**定义统一的接口（纯虚函数），让不同厂商提供各自的实现**。

```cpp
// 协议栈上层代码只需要知道 Controller 接口，不需要关心底层芯片是什么
void some_upper_layer_function(Controller* controller) {
    // 这些调用会在运行时自动路由到正确的实现
    std::string name = controller->GetLocalName();  // virtual 调用
    bool ble_ok = controller->SupportsBle();         // virtual 调用
    controller->Reset();                             // virtual 调用
}

// 如果手机用的是高通芯片，controller 指向 QualcommControllerImpl
// 如果手机用的是博通芯片，controller 指向 BroadcomControllerImpl
// 上层代码完全不需要修改！这就是多态的威力。
```

### ☕ Java 类比

| 特性 | C++ 虚函数 | Java 方法 |
|------|----------|----------|
| 默认行为 | **非虚**（静态绑定），需显式加 `virtual` | **默认虚**（动态绑定），无需额外关键字 |
| 声明虚函数 | `virtual void draw();` | `void draw();`（自动虚） |
| 关闭虚行为 | 不加 `virtual` 即可 | `final` 关键字：`final void draw()` |
| 性能开销 | 有 vtable 指针开销 | 同样有虚方法表开销 |

**对比代码**：

```cpp
// C++: 必须显式写 virtual 才能多态
class Shape {
public:
    virtual void draw() { cout << "Drawing a shape\n"; }  // 必须加 virtual！
};

class Circle : public Shape {
public:
    void draw() override { cout << "Drawing a circle\n"; }
};
```

```java
// Java: 方法默认就是虚的，自动支持多态
public class Shape {
    public void draw() { System.out.println("Drawing a shape"); }  // 自动虚！
}

public class Circle extends Shape {
    @Override
    public void draw() { System.out.println("Drawing a circle"); }
}
```

**关键差异**：
- Java 的**所有非 static、非 final、非 private 的方法默认都是虚函数**，自动支持多态。C++ 必须显式加 `virtual` 关键字
- Java 的设计哲学是"默认安全"——多态是常态，不需要记住加 `virtual`。C++ 的设计哲学是"零开销"——不为不需要多态的函数付出 vtable 开销
- Java 中要禁止方法被重写，用 `final`；C++ 中要启用多态，用 `virtual`——两者思路相反

---

## 3. override 关键字 (C++11)

### 3.1 什么是 override？

`override` 是 C++11 引入的关键字，放在派生类的虚函数声明末尾，明确表示"这个函数是在重写（覆盖）基类的虚函数"。

### 3.2 为什么一定要用 override？

**原因一：防止拼写错误**

```cpp
class Base {
public:
    virtual void print_info() const {}
};

class Derived : public Base {
public:
    // ❌ 拼写错误！printinfo 少了下划线
    // 但编译器不会报错！它以为你要定义一个新的普通函数
    virtual void printinfo() const {}  // 这是一个全新的函数，不是重写！

    // ✅ 加上 override 后，编译器会帮你检查
    // virtual void printinfo() const override;  // 编译错误！基类中没有 printinfo
};

// 结果：你本想重写 print_info，但实际上创建了一个新函数 printinfo
// 多态调用时调用的还是 Base::print_info()，bug 隐藏得很深！
```

**原因二：防止参数不匹配**

```cpp
class Base {
public:
    virtual void process(int value) {}
};

class Derived : public Base {
public:
    // ❌ 参数类型错了！应该是 int，但写成了 double
    // 没有 override 时：这是一个新的重载函数，不是重写
    virtual void process(double value) {}

    // ✅ 加上 override：编译器立即报错！
    // virtual void process(double value) override;  // 编译错误！
};
```

**原因三：防止忘记加 virtual**

```cpp
class Base {
public:
    void handle() {}  // 基类忘了加 virtual！
};

class Derived : public Base {
public:
    // 你以为自己在重写，其实不是...
    void handle() override;  // ✅ 编译器告诉你：Base::handle 不是虚函数！
};
```

### 3.3 蓝牙协议栈中的真实示例

#### 示例一：Handler 类 (`system/gd/os/handler.h:57-70`)

```cpp
// 来自 handler.h 第 57-70 行
namespace bluetooth {
namespace os {

// Handler 继承自 PostableContext
class Handler : public common::PostableContext {
public:
  explicit Handler(Thread* thread);
  Handler(const Handler&) = delete;
  Handler& operator=(const Handler&) = delete;
  virtual ~Handler();

  // 👇 这里使用了 override！表示 Post() 重写了基类 PostableContext 的虚函数
  virtual void Post(common::OnceClosure closure) override;

  void Clear();
  // ...
};

}  // namespace os
}  // namespace bluetooth
```

**完整的继承链路**：

```
IPostableContext （最顶层接口 - i_postable_context.h:24-28）
    ↓ 纯虚函数: Post(base::OnceClosure) = 0
    ↓
PostableContext （中间层 - postable_context.h:25-56）
    ↓ 提供了 BindOnce/Bind 等模板工具方法
    ↓
Handler       （最终实现 - handler.h:57-137）
    ↓ override Post()，提供具体的消息投递逻辑
```

让我们看看每一层的源码：

```cpp
// ===== 第一层：IPostableContext — 最顶层的纯虚接口 =====
// 文件：system/gd/common/i_postable_context.h:24-28
namespace bluetooth {
namespace common {

class IPostableContext {
public:
  virtual ~IPostableContext() {}
  virtual void Post(base::OnceClosure closure) = 0;  // 纯虚函数！
};

}  // namespace common
}  // namespace bluetooth


// ===== 第二层：PostableContext — 中间抽象层 =====
// 文件：system/gd/common/postable_context.h:25-56
namespace bluetooth::common {

class PostableContext : public IPostableContext {
public:
  virtual ~PostableContext() = default;

  // 提供模板工具方法，用于将回调绑定到当前上下文
  template <typename Functor, typename... Args>
  auto BindOnce(Functor&& functor, Args&&... args) { ... }

  template <typename Functor, typename... Args>
  auto Bind(Functor&& functor, Args&&... args) { ... }
  // ...
  // 注意：Post() 仍然是纯虚的（从 IPostableContext 继承），这里没有实现
};


// ===== 第三层：Handler — 最终的具体实现 =====
// 文件：system/gd/os/handler.h:57-70
namespace bluetooth {
namespace os {

class Handler : public common::PostableContext {
public:
  explicit Handler(Thread* thread);
  virtual ~Handler();

  // 👇 override！实现了 Post() 的具体逻辑
  virtual void Post(common::OnceClosure closure) override;
  // 具体实现：将 closure 投递到消息队列，由 Reactor 线程循环处理

  void Clear();
  // ...
};

}  // namespace os
}  // namespace bluetooth
```

#### 示例二：BidiQueueEnd 类 (`system/gd/common/bidi_queue.h:31-59`) —— 多个 override 方法

这是一个非常经典的多继承 + override 示例：

```cpp
// 文件：bidi_queue.h 第 31-59 行
template <typename TENQUEUE, typename TDEQUEUE>
class BidiQueueEnd : public ::bluetooth::os::IQueueEnqueue<TENQUEUE>,
                     public ::bluetooth::os::IQueueDequeue<TDEQUEUE> {
public:
  using EnqueueCallback = Callback<std::unique_ptr<TENQUEUE>()>;
  using DequeueCallback = Callback<void()>;

  BidiQueueEnd(::bluetooth::os::IQueueEnqueue<TENQUEUE>* tx,
               ::bluetooth::os::IQueueDequeue<TDEQUEUE>* rx)
      : tx_(tx), rx_(rx) {}

  // ===== 以下全部是 override 方法 =====

  // 来自 IQueueEnqueue 接口的重写
  void RegisterEnqueue(::bluetooth::os::Handler* handler,
                       EnqueueCallback callback) override {
    tx_->RegisterEnqueue(handler, callback);  // 委托给内部对象
  }

  void UnregisterEnqueue() override {
    tx_->UnregisterEnqueue();
  }

  // 来自 IQueueDequeue 接口的重写
  void RegisterDequeue(::bluetooth::os::Handler* handler,
                       DequeueCallback callback) override {
    rx_->RegisterDequeue(handler, callback);  // 委托给内部对象
  }

  void UnregisterDequeue() override {
    rx_->UnregisterEnqueue();
  }

  std::unique_ptr<TDEQUEUE> TryDequeue() override {
    return rx_->TryDequeue();
  }

private:
  ::bluetooth::os::IQueueEnqueue<TENQUEUE>* tx_;
  ::bluetooth::os::IQueueDequeue<TDEQUEUE>* rx_;
};
```

**解读**：
- `BidiQueueEnd` 同时继承了两个接口：`IQueueEnqueue`（入队接口）和 `IQueueDequeue`（出队接口）
- 它需要重写 **5 个** 虚函数，每个都加了 `override` 关键字
- 这种模式叫做 **委托模式（Delegation Pattern）**：BidiQueueEnd 本身不做实际工作，而是把请求转发给内部的 `tx_` 和 `rx_` 对象

### 3.4 最佳实践总结

```cpp
// ✅ 推荐写法：基类加 virtual，派生类加 override
class Base {
public:
    virtual void foo() {}
    virtual void bar(int x) const {}
};

class Derived : public Base {
public:
    void foo() override {}           // ✅ 明确表示"我在重写"
    void bar(int x) const override {} // ✅ 参数和 const 都必须匹配
};

// ❌ 不推荐：不加 override
class BadDerived : public Base {
public:
    void foo() {}  // 能编译，但如果基类改了名字就发现不了
};
```

> **黄金法则**：C++11 及以后，**所有重写基类虚函数的地方都必须加上 `override`**。这不是可选项，而是必须遵守的编码规范。

### ☕ Java 类比

| 特性 | C++ `override` | Java `@Override` |
|------|---------------|-----------------|
| 类型 | 关键字（语言级） | 注解（Annotation） |
| 位置 | 函数声明末尾：`void foo() override;` | 函数声明上方：`@Override public void foo()` |
| 编译器检查 | ✅ 确认基类有对应虚函数 | ✅ 确认父类/接口有对应方法 |
| 防止拼写错误 | ✅ | ✅ |
| 防止参数不匹配 | ✅ | ✅ |

**对比代码**：

```cpp
// C++: override 关键字
class Handler : public PostableContext {
public:
    virtual void Post(common::OnceClosure closure) override;  // 末尾
};
```

```java
// Java: @Override 注解
public class Handler extends PostableContext {
    @Override                                           // 上方
    public void post(Runnable closure) { ... }
}
```

**关键差异**：
- C++ 的 `override` 是**关键字**，Java 的 `@Override` 是**注解**，但功能完全一致
- 位置不同：C++ 放在函数声明末尾，Java 放在函数声明上方
- 两者都是**最佳实践**：凡是重写父类方法，都应该加上 `override`/`@Override`

---

## 4. 纯虚函数与抽象类

### 4.1 纯虚函数语法

```cpp
virtual 返回值类型 函数名(参数列表) = 0;
```

`= 0` 就是"纯虚"的标记，意思是 **"这个函数没有实现，子类必须提供实现"**。

### 4.2 抽象类

**包含至少一个纯虚函数的类称为抽象类（Abstract Class）。抽象类不能被实例化（不能创建对象）**。

```cpp
// 抽象类示例
class Shape {               // 抽象类
public:
    // 纯虚函数 —— 子类必须实现
    virtual double area() const = 0;
    virtual double perimeter() const = 0;

    // 普通虚函数 —— 子类可以选择性重写
    virtual void describe() const {
        cout << "This is a shape.\n";
    }

    virtual ~Shape() = default;
};

// Shape s;  // ❌ 编译错误！不能实例化抽象类
// Shape* ps = new Shape();  // ❌ 同样错误！

// 必须通过派生类来使用
class Circle : public Shape {
public:
    Circle(double r) : radius_(r) {}

    // ✅ 必须实现所有纯虚函数
    double area() const override {
        return 3.14159 * radius_ * radius_;
    }

    double perimeter() const override {
        return 2 * 3.14159 * radius_;
    }
private:
    double radius_;
};

// ✅ 可以实例化派生类
Circle c(5.0);
Shape* shape = &c;  // 用基类指针指向派生类对象
cout << shape->area();  // 多态调用 → 78.54
```

### 4.3 核心示例：Controller 类 —— 包含 100+ 个纯虚函数的接口类！

这是 Android 蓝牙协议栈中最震撼的抽象类之一。打开 `system/gd/hci/controller.h`，你会看到一个包含 **100 多个纯虚函数**的接口类：

```cpp
// 文件：system/gd/hci/controller.h:28-226
#pragma once

#include "hci/address.h"
#include "hci/class_of_device.h"
#include "hci/hci_packets.h"
#include "hci/le_rand_callback.h"

namespace bluetooth {
namespace hci {

class Controller {
public:
  // 常量定义
  static constexpr uint64_t kDefaultEventMask = 0x3dbfffffffffffff;
  static constexpr uint64_t kDefaultEventMaskPage2 = 0x2000000;
  static constexpr uint64_t kDefaultLeEventMask = 0x000000074d02fe7f;
  static constexpr uint64_t kLeCSEventMask = 0x0007f80000000000;

  // 构造和析构
  Controller() = default;
  virtual ~Controller() = default;  // 虚析构函数！（第 5 节详解）

  // 一个非纯虚的方法（有默认实现的 dump 函数）
  virtual void Dump(int /*fd*/) const {}

  // ============================================================
  // 下面开始是 100+ 个纯虚函数！每一个都代表一个 HCI 命令或查询
  // ============================================================

  // --- ACL 数据包回调 ---
  using CompletedAclPacketsCallback =
          common::ContextualCallback<void(uint16_t /* handle */, uint16_t /* num_packets */)>;
  virtual void RegisterCompletedAclPacketsCallback(CompletedAclPacketsCallback cb) = 0;
  virtual void UnregisterCompletedAclPacketsCallback() = 0;
  virtual void RegisterCompletedMonitorAclPacketsCallback(CompletedAclPacketsCallback cb) = 0;
  virtual void UnregisterCompletedMonitorAclPacketsCallback() = 0;

  // --- 控制器信息查询 ---
  virtual std::string GetLocalName() const = 0;
  virtual LocalVersionInformation GetLocalVersionInformation() const = 0;
  virtual Address GetMacAddress() const = 0;

  // --- 功能支持查询（40+ 个 SupportsXxx 方法）---
  virtual bool SupportsSimplePairing() const = 0;
  virtual bool SupportsSecureConnections() const = 0;
  virtual bool SupportsSimultaneousLeBrEdr() const = 0;
  virtual bool SupportsInterlacedInquiryScan() const = 0;
  virtual bool SupportsRssiWithInquiryResults() const = 0;
  virtual bool SupportsExtendedInquiryResponse() const = 0;
  virtual bool SupportsRoleSwitch() const = 0;
  virtual bool Supports3SlotPackets() const = 0;
  virtual bool Supports5SlotPackets() const = 0;
  virtual bool SupportsClassic2mPhy() const = 0;
  virtual bool SupportsClassic3mPhy() const = 0;
  virtual bool SupportsSco() const = 0;
  virtual bool SupportsHoldMode() const = 0;
  virtual bool SupportsSniffMode() const = 0;
  virtual bool SupportsParkMode() const = 0;
  virtual bool SupportsBle() const = 0;         // 是否支持低功耗蓝牙
  virtual bool SupportsBleEncryption() const = 0;
  virtual bool SupportsBlePrivacy() const = 0;
  virtual bool SupportsBleCodedPhy() const = 0;
  virtual bool SupportsBleExtendedAdvertising() const = 0;
  virtual bool SupportsBlePeriodicAdvertising() const = 0;
  // ... 还有 20+ 个 SupportsXxx ...

  // --- 缓冲区大小查询 ---
  virtual uint16_t GetAclPacketLength() const = 0;
  virtual uint16_t GetNumAclPacketBuffers() const = 0;
  virtual uint8_t GetScoPacketLength() const = 0;
  virtual uint16_t GetNumScoPacketBuffers() const = 0;

  // --- HCI 命令 ---
  virtual void SetEventMask(uint64_t event_mask) = 0;
  virtual void Reset() = 0;                      // 复位控制器
  virtual void LeRand(LeRandCallback cb) = 0;    // 获取随机数
  virtual void WriteLocalName(std::string local_name) = 0;
  virtual void HostBufferSize(...) = 0;

  // --- LE 命令 ---
  virtual void LeSetEventMask(uint64_t le_event_mask) = 0;
  virtual LeBufferSize GetLeBufferSize() const = 0;
  virtual uint64_t GetLeSupportedStates() const = 0;
  // ... 更多 LE 相关方法 ...

  // --- 厂商特定能力 ---
  struct VendorCapabilities {
    uint8_t is_supported_;
    uint8_t max_advt_instances_;
    uint8_t offloaded_resolution_of_private_address_;
    uint16_t total_scan_results_storage_;
    // ... 更多字段 ...
  };
  virtual VendorCapabilities GetVendorCapabilities() const = 0;

  // --- 操作码支持检查 ---
  virtual bool IsSupported(OpCode op_code) const = 0;
  virtual bool IsRpaGenerationSupported(void) const = 0;

  // ... 总共 100+ 个纯虚函数 ...
};

}  // namespace hci
}  // namespace bluetooth
```

### 4.4 为什么 Controller 要这样设计？

这是一个经典的 **接口分离模式（Interface Segregation）** 设计。理解它背后的原因非常重要：

#### 问题背景

Android 蓝牙系统运行在各种设备上：
- Pixel 手机可能用 **Qualcomm（高通）** 芯片
- 其他手机可能用 **Broadcom（博通）** 芯片
- 还有的用 **MediaTek（联发科）**、**Realtek（瑞昱）** 等芯片
- 测试环境可能用 **Fake（模拟）** 控制器

每种芯片的 HCI 命令格式、寄存器操作都不同，但上层协议栈（L2CAP、GATT、ATT 等）**不应该关心底层芯片的差异**。

#### 解决方案

```
┌─────────────────────────────────────────────────────┐
│                  上层协议栈                           │
│  (GATT / L2CAP / A2DP / HFP / ...)                 │
│                                                     │
│  只知道 Controller 接口，不知道芯片型号               │
│  controller->Reset();                               │
│  controller->GetLocalName();                        │
│  controller->SupportsBle();                         │
└──────────────────────┬──────────────────────────────┘
                       │ 只通过 Controller* 指针交互
                       ▼
            ┌─────────────────────┐
            │    Controller       │  ← 纯虚接口类
            │  (100+ 纯虚函数)     │  ← 定义"能做什么"
            └──────┬──────┬───────┘
                   │      │
       ┌───────────┘      └───────────┐
       ▼                              ▼
┌──────────────┐              ┌──────────────┐
│ControllerImpl│              │ControllerImpl│  ← 各厂商实现
│ (通用实现)   │              │ (测试 Fake)  │  ← 定义"怎么做"
│ hci_hal_xxx  │              │ hci_hal_fake │
└──────────────┘              └──────────────┘
```

#### 具体实现类：ControllerImpl

```cpp
// 文件：system/gd/hci/controller_impl.h:34-222
class ControllerImpl : public Controller {
public:
  ControllerImpl(os::Handler* handler, hci::HciInterface* hci_interface);

  // ===== 必须实现 Controller 的所有 100+ 个纯虚函数 =====

  void Dump(int fd) const override;
  std::string GetLocalName() const override;
  LocalVersionInformation GetLocalVersionInformation() const override;
  bool SupportsSimplePairing() const override;
  bool SupportsSecureConnections() const override;
  bool SupportsBle() const override;
  Address GetMacAddress() const override;
  void SetEventMask(uint64_t event_mask) override;
  void Reset() override;
  void LeRand(LeRandCallback cb) override;
  // ... 还有 90+ 个 override ...

private:
  struct impl;                          // Pimpl 惯用法，隐藏实现细节
  std::unique_ptr<impl> impl_;          // 具体实现在 .cc 文件中
};
```

**设计优势总结**：

| 优势 | 说明 |
|-----|------|
| **解耦** | 上层代码只依赖 `Controller` 接口，不依赖任何具体芯片实现 |
| **可替换** | 换芯片只需换 `ControllerImpl` 实现，上层代码零修改 |
| **可测试** | 单元测试可以用 `FakeController` 替代真实硬件 |
| **规范约束** | 所有芯片实现者必须实现完整的 100+ 个函数，遗漏任何一个都会编译失败 |

### ☕ Java 类比

| 特性 | C++ 纯虚函数/抽象类 | Java `interface`/`abstract class` |
|------|-------------------|--------------------------------|
| 纯虚函数 | `virtual void foo() = 0;` | `abstract void foo();`（abstract 类中）或 `void foo();`（interface 中） |
| 抽象类 | 含 `= 0` 的类 | `abstract class` |
| 接口 | 用全纯虚类模拟 | `interface` 关键字 |
| 不能实例化 | ✅ | ✅ |
| 可以有默认实现 | ✅（普通虚函数） | ✅（Java 8+ 的 `default` 方法） |

**对比代码**：

```cpp
// C++: 用全纯虚类模拟接口
class IPostableContext {
public:
    virtual ~IPostableContext() {}
    virtual void Post(base::OnceClosure closure) = 0;  // 纯虚函数
};

// C++: 抽象类（部分纯虚 + 部分有实现）
class Controller {
public:
    virtual ~Controller() = default;
    virtual void Reset() = 0;           // 纯虚
    virtual void Dump(int fd) const {}  // 有默认实现
};
```

```java
// Java: 用 interface 关键字
public interface IPostableContext {
    void post(Runnable closure);  // 自动 abstract，无需 = 0
}

// Java: abstract class
public abstract class Controller {
    public abstract void reset();           // 抽象方法
    public void dump(int fd) { }           // 有默认实现
}
```

**关键差异**：
- Java 有专门的 `interface` 关键字，C++ 用"全纯虚函数 + 虚析构函数的类"来模拟
- Java 的 `interface` 中方法默认是 `public abstract` 的，不需要显式写 `abstract`。C++ 必须写 `= 0`
- Java 8+ 的 interface 支持 `default` 方法（有默认实现），这与 C++ 抽象类中的普通虚函数类似
- C++ 的纯虚函数可以有函数体（`virtual void foo() = 0 { /* 实现 */ }`），但很少用；Java 的 abstract 方法不能有函数体

---

## 5. 虚析构函数

### 5.1 为什么基类析构函数必须是 virtual？

这是 C++ 继承中最容易踩的坑之一，也是导致 **内存泄漏** 的常见原因。

```cpp
// ❌ 危险！基类析构函数不是 virtual
class Base {
public:
    ~Base() { cout << "Base destroyed\n"; }  // 注意：没有 virtual！
    // 假设 Base 分配了一些资源需要释放...
};

class Derived : public Base {
public:
    Derived() { data_ = new int[1000]; }  // 分配了内存
    ~Derived() { delete[] data_; cout << "Derived destroyed\n"; }  // 释放内存
private:
    int* data_;
};

int main() {
    Base* ptr = new Derived();  // 用基类指针管理派生类对象
    delete ptr;                 // ⚠️ 危险！

    // 输出结果：
    // "Base destroyed"          ← 只有 Base 的析构函数被调用！
    //
    // Derived 的析构函数没有被调用！
    // data_ 指向的 1000 个 int 内存泄漏了！
}
```

**为什么会这样？**

当通过基类指针 `delete` 对象时：
- 如果析构函数 **不是 virtual**：编译器执行 **静态绑定**，只调用 `~Base()`，完全忽略 `~Derived()`
- 如果析构函数 **是 virtual**：编译器执行 **动态绑定**，先调用 `~Derived()`，再自动调用 `~Base()`

```cpp
// ✅ 安全！基类析构函数加上 virtual
class Base {
public:
    virtual ~Base() { cout << "Base destroyed\n"; }  // 加上 virtual！
};

class Derived : public Base {
public:
    Derived() { data_ = new int[1000]; }
    virtual ~Derived() override {  // 派生类也加上 override
        delete[] data_;
        cout << "Derived destroyed\n";
    }
private:
    int* data_;
};

int main() {
    Base* ptr = new Derived();
    delete ptr;

    // 输出结果：
    // "Derived destroyed"   ← 先调用派生类析构函数 ✅
    // "Base destroyed"      ← 再自动调用基类析构函数 ✅
    // 内存正确释放，无泄漏 ✅
}
```

### 5.2 蓝牙协议栈中的实践

#### Controller 类中的虚析构函数

```cpp
// system/gd/hci/controller.h:35-36
class Controller {
public:
  Controller() = default;
  virtual ~Controller() = default;  // ✅ 虚析构函数！
  // ...
};
```

**为什么写成 `= default`？**

C++11 引入了 `= default` 语法，意思是"使用编译器生成的默认实现"。对于析构函数来说，默认实现就是按顺序调用成员变量的析构函数。这里写 `virtual ~Controller() = default;` 等价于：

```cpp
virtual ~Controller() {}  // 空函数体，但因为是 virtual 所以安全
```

但 `= default` 写法更清晰地表达了意图："我不需要自定义析构逻辑，但要确保它是 virtual 的"。

#### IQueueEnqueue / IQueueDequeue 中的虚析构函数

```cpp
// system/gd/os/queue.h:36-42
template <typename T>
class IQueueEnqueue {
public:
  using EnqueueCallback = common::Callback<std::unique_ptr<T>()>;
  virtual ~IQueueEnqueue() = default;  // ✅ 虚析构函数
  virtual void RegisterEnqueue(Handler* handler, EnqueueCallback callback) = 0;
  virtual void UnregisterEnqueue() = 0;
};

template <typename T>
class IQueueDequeue {
public:
  using DequeueCallback = common::Callback<void()>;
  virtual ~IQueueDequeue() = default;  // ✅ 虚析构函数
  virtual void RegisterDequeue(Handler* handler, DequeueCallback callback) = 0;
  virtual void UnregisterEnqueue() = 0;
  virtual std::unique_ptr<T> TryDequeue() = 0;
};
```

#### IPostableContext 中的虚析构函数

```cpp
// system/gd/common/i_postable_context.h:24-28
class IPostableContext {
public:
  virtual ~IPostableContext() {}  // ✅ 虚析构函数（空实现也可以）
  virtual void Post(base::OnceClosure closure) = 0;
};
```

### 5.3 黄金法则

> **如果一个类会被作为基类使用，并且有可能通过基类指针 delete 派生类对象，那么基类的析构函数必须是 virtual 的。**
>
> 更简单的记忆方式：**只要你的类有 virtual 函数，析构函数也应该是 virtual 的。**

### ☕ Java 类比

| 特性 | C++ 虚析构函数 | Java |
|------|-------------|------|
| 是否需要 | ✅ 必须手动声明 | ❌ **不需要** |
| 原因 | 通过基类指针 delete 派生类对象时，需动态绑定析构函数 | Java 有 GC，不需要手动 delete |
| 析构顺序问题 | 非 virtual 析构会导致派生类析构不被调用 | GC 自动处理，不存在此问题 |

**Java 为什么不需要虚析构函数？**

- Java 有**垃圾回收器**，对象不再被引用时自动回收，程序员不需要手动 `delete`
- C++ 的虚析构函数解决的是"通过基类指针 `delete` 派生类对象"的问题。Java 中不存在 `delete`，所以这个问题根本不存在
- Java 中如果需要显式释放资源，使用 `AutoCloseable` + `try-with-resources`，而不是析构函数

```cpp
// C++: 必须用虚析构函数确保正确释放
class Controller {
public:
    virtual ~Controller() = default;  // 必须 virtual！
};
Controller* ptr = new ControllerImpl();
delete ptr;  // 需要 virtual ~ 才能正确调用 ControllerImpl 的析构函数
```

```java
// Java: 不需要虚析构函数
Controller ctrl = new ControllerImpl();
// ctrl 不再被引用时，GC 自动回收，无需手动 delete
// 如果需要显式释放资源：
try (Controller ctrl = new ControllerImpl()) {
    // 使用 ctrl...
}  // ctrl.close() 自动调用
```

---

## 6. 多继承

### 6.1 基本语法：一个类继承多个基类

```cpp
class Derived : public Base1, public Base2, public Base3 {
    // ...
};
```

### 6.2 简单的多继承示例

```cpp
// === 基类 1：能飞 ===
class Flyable {
public:
    virtual void fly() { cout << "Flying!\n"; }
    virtual ~Flyable() = default;
};

// === 基类 2：能游泳 ===
class Swimmable {
public:
    virtual void swim() { cout << "Swimming!\n"; }
    virtual ~Swimmable() = default;
};

// === 派生类：鸭子（既能飞又能游泳）===
class Duck : public Flyable, public Swimmable {
public:
    void fly() override { cout << "Duck is flying!\n"; }
    void swim() override { cout << "Duck is swimming!\n"; }
    void quack() { cout << "Quack quack!\n"; }
};

int main() {
    Duck d;
    d.fly();    // "Duck is flying!"
    d.swim();   // "Duck is swimming!"
    d.quack();  // "Quack quack!"

    // 多态使用
    Flyable* f = &d;
    f->fly();   // "Duck is flying!"  ← 动态绑定生效

    Swimmable* s = &d;
    s->swim();  // "Duck is swimming!" ← 动态绑定生效
}
```

### 6.3 蓝牙协议栈中的真实示例：BidiQueueEnd

这是 Android 蓝牙协议栈中最典型的多继承案例：

```cpp
// 文件：system/gd/common/bidi_queue.h:31-59
//
// BidiQueueEnd 同时继承了两个接口：
//   1. IQueueEnqueue<TENQUEUE>  —— 入队接口（发送数据）
//   2. IQueueDequeue<TDEQUEUE>   —— 出队接口（接收数据）
//
// 这样 BidiQueueEnd 就同时具备了"入队能力"和"出队能力"！
//
template <typename TENQUEUE, typename TDEQUEUE>
class BidiQueueEnd : public ::bluetooth::os::IQueueEnqueue<TENQUEUE>,   // ← 第一个基类
                     public ::bluetooth::os::IQueueDequeue<TDEQUEUE> {  // ← 第二个基类
public:
  using EnqueueCallback = Callback<std::unique_ptr<TENQUEUE>()>;
  using DequeueCallback = Callback<void()>();

  BidiQueueEnd(::bluetooth::os::IQueueEnqueue<TENQUEUE>* tx,
               ::bluetooth::os::IQueueDequeue<TDEQUEUE>* rx)
      : tx_(tx), rx_(rx) {}

  // ===== 来自 IQueueEnqueue 的方法（override）=====
  void RegisterEnqueue(::bluetooth::os::Handler* handler,
                       EnqueueCallback callback) override {
    tx_->RegisterEnqueue(handler, callback);
  }
  void UnregisterEnqueue() override { tx_->UnregisterEnqueue(); }

  // ===== 来自 IQueueDequeue 的方法（override）=====
  void RegisterDequeue(::bluetooth::os::Handler* handler,
                       DequeueCallback callback) override {
    rx_->RegisterDequeue(handler, callback);
  }
  void UnregisterDequeue() override { rx_->UnregisterDequeue(); }
  std::unique_ptr<TDEQUEUE> TryDequeue() override { return rx_->TryDequeue(); }

private:
  ::bluetooth::os::IQueueEnqueue<TENQUEUE>* tx_;  // 内部持有的入队队列
  ::bluetooth::os::IQueueDequeue<TDEQUEUE>* rx_;  // 内部持有的出队队列
};
```

**继承关系图**：

```
                    IQueueEnqueue<T>          IQueueDequeue<T>
                    ┌──────────────┐          ┌──────────────┐
                    │ RegisterEnq  │          │ RegisterDeq  │
                    │ UnregisterEnq│          │ UnregisterDeq│
                    └──────┬───────┘          │ TryDequeue   │
                           │                  └──────┬───────┘
                           │                         │
                           └──────────┬──────────────┘
                                      │
                                      ▼
                            ┌──────────────────┐
                            │   BidiQueueEnd   │
                            │  (多继承两者)     │
                            │                  │
                            │ 同时具备入队+出队  │
                            └──────────────────┘
```

**为什么需要多继承？**

在蓝牙协议栈中，数据需要在上下层之间双向流动：

```
 上层（如 GATT 层）
    │
    │  发送数据 ↓     接收数据 ↑
    │                   │
    ▼                   ▼
 ┌─────────────────────────────────┐
 │          BidiQueue              │
 │                                 │
 │  up_end_: BidiQueueEnd          │  ← 上层使用的端点
 │    ├─ 入队(IQueueEnqueue): 向下发数据  │
 │    └─ 出队(IQueueDequeue): 从下收数据  │
 │                                 │
 │  down_end_: BidiQueueEnd        │  ← 下层使用的端点
 │    ├─ 入队(IQueueEnqueue): 向上发数据  │
 │    └─ 出队(IQueueDequeue): 从上收数据  │
 └─────────────────────────────────┘
    │
    ▼
 下层（如 HCI 层）
```

`BidiQueueEnd` 必须同时实现入队和出队接口，因为它的两端都需要双向操作。**多继承在这里是最自然的设计选择**。

### 6.4 Queue 类也是多继承

```cpp
// system/gd/os/queue.h:70
template <typename T>
class Queue : public IQueueEnqueue<T>, public IQueueDequeue<T> {
    // Queue 也是同时继承两个接口
    // 但 Queue 是真正的实现类（有内部 queue_ 存储数据）
    // 而 BidiQueueEnd 只是委托包装类
};
```

**对比 Queue 和 BidiQueueEnd**：

| 特征 | `Queue<T>` | `BidiQueueEnd<T1,T2>` |
|-----|-----------|----------------------|
| 继承 | `IQueueEnqueue<T>` + `IQueueDequeue<T>` | `IQueueEnqueue<T1>` + `IQueueDequeue<T2>` |
| 角色 | **真正持有数据**的队列 | **委托代理**，转发到其他队列 |
| 内部存储 | 有 `std::queue<std::unique_ptr<T>> queue_` | 只有两个指针 `tx_`, `rx_` |
| 模板参数 | 同一个 T | 可以是不同的 T1 和 T2 |

### ☕ Java 类比

| 特性 | C++ 多继承 | Java |
|------|----------|------|
| 类的多继承 | ✅ 支持 | ❌ **不支持**（只能继承一个类） |
| 接口多继承 | ✅（用纯虚类模拟） | ✅ `implements Interface1, Interface2` |
| 替代方案 | — | 用接口 + 组合（委托模式） |

**对比代码**：

```cpp
// C++: 多继承——同时继承两个接口
class BidiQueueEnd : public IQueueEnqueue<TENQUEUE>,
                     public IQueueDequeue<TDEQUEUE> {
    // 必须实现两个接口的所有纯虚函数
    void RegisterEnqueue(...) override { tx_->RegisterEnqueue(...); }
    void TryDequeue() override { return rx_->TryDequeue(); }
    // ...
};
```

```java
// Java: 用接口实现类似效果
public class BidiQueueEnd<TEnqueue, TDequeue>
        implements IQueueEnqueue<TEnqueue>, IQueueDequeue<TDequeue> {
    // 实现两个接口的所有方法
    @Override
    public void registerEnqueue(...) { tx.registerEnqueue(...); }
    @Override
    public TDequeue tryDequeue() { return rx.tryDequeue(); }
    // ...
}
```

**关键差异**：
- Java **不支持类的多继承**，一个类只能 `extends` 一个父类。但可以 `implements` 多个接口
- C++ 的多继承可以继承有状态的类（有成员变量），Java 的接口不能有实例字段（Java 8+ 只能有 `default` 方法和 `static` 方法）
- Java 用**接口 + 委托模式**来替代 C++ 的多继承。`BidiQueueEnd` 内部持有 `tx_` 和 `rx_` 指针并转发调用，这种模式在 Java 中同样适用

---

## 7. 虚继承

### 7.1 菱形继承问题

当一个类通过多条路径间接继承同一个基类时，就会出现 **菱形继承（Diamond Inheritance）** 问题：

```cpp
// === 最顶层基类 ===
class Device {
public:
    int id_;
    Device() : id_(0) { cout << "Device constructed\n"; }
};

// === 中间层：两个类都继承 Device ===
class Scanner : public Device {    // 路径 1
public:
    Scanner() { cout << "Scanner constructed\n"; }
};

class Connector : public Device {   // 路径 2
public:
    Connector() { cout << "Connector constructed\n"; }
};

// === 最底层：同时继承 Scanner 和 Connector ===
// 形成了菱形结构：
//
//        Device
//       /      \
//   Scanner   Connector
//       \      /
//     BluetoothDevice   ← Device 被继承了两次！
//
class BluetoothDevice : public Scanner, public Connector {
public:
    BluetoothDevice() { cout << "BluetoothDevice constructed\n"; }
};

int main() {
    BluetoothDevice bt;

    // 问题 1：id_ 有两份！
    // bt.id_ = 42;  // ❌ 编译错误！id_ 歧义——不知道是 Scanner::id_ 还是 Connector::id_
    bt.Scanner::id_ = 42;     // 必须这样指定
    bt.Connector::id_ = 43;    // 两份独立的 id_，这不合理！

    // 问题 2：Device 的构造函数被调用了两次
    // 输出：
    // "Device constructed"      ← Scanner 带来的
    // "Scanner constructed"
    // "Device constructed"      ← Connector 又带来一份
    // "Connector constructed"
    // "BluetoothDevice constructed"
}
```

**问题本质**：`BluetoothDevice` 对象内部包含了 **两份** `Device` 子对象，浪费内存且语义混乱。

### 7.2 解决方案：虚继承

使用 `virtual public`（或 `virtual protected/private`）继承中间层类：

```cpp
class Device {
public:
    int id_;
    Device() : id_(0) { cout << "Device constructed\n"; }
};

// 使用 virtual 继承！
class Scanner : virtual public Device {     // 👈 加了 virtual
public:
    Scanner() { cout << "Scanner constructed\n"; }
};

class Connector : virtual public Device {    // 👈 加了 virtual
public:
    Connector() { cout << "Connector constructed\n"; }
};

class BluetoothDevice : public Scanner, public Connector {
public:
    BluetoothDevice() { cout << "BluetoothDevice constructed\n"; }
};

int main() {
    BluetoothDevice bt;

    // ✅ 现在 id_ 只有一份了！
    bt.id_ = 42;  // 直接访问，无歧义

    // ✅ Device 的构造函数只调用一次
    // 输出：
    // "Device constructed"          ← 只有一次！
    // "Scanner constructed"
    // "Connector constructed"
    // "BluetoothDevice constructed"
}
```

**虚继承的工作原理**：

```
普通继承（菱形问题）：              虚继承（解决问题）：

  BluetoothDevice                    BluetoothDevice
  ├── Scanner                        ├── Scanner
  │   └── Device (id_=?)             │   └── (虚基类指针 → 共享的 Device)
  └── Connector                      └── Connector
      └── Device (id_=?)                 └── (虚基类指针 → 共享的 Device)
                                       
  两份 Device！❌                       只有一份 Device！✅
```

使用虚继承后，`Scanner` 和 `Connector` 内部不再包含 `Device` 子对象，而是保存一个 **虚基类指针（vbptr）**，运行时指向共享的 `Device` 子对象。

### 7.3 虚继承注意事项

```cpp
// ⚠️ 虚基类由最底层的派生类负责初始化
class Device {
public:
    int id_;
    Device(int id) : id_(id) {}  // 带参数的构造函数
};

class Scanner : virtual public Device {
public:
    Scanner(int id) : Device(id) {}  // Scanner 也初始化 Device（但可能被绕过）
};

class Connector : virtual public Device {
public:
    Connector(int id) : Device(id) {}  // Connector 也初始化 Device
};

class BluetoothDevice : public Scanner, public Connector {
public:
    // ⚠️ 最底层的类必须直接初始化虚基类！
    BluetoothDevice() : Device(42), Scanner(10), Connector(20) {
        // Device(42) 才是真正执行的！Scanner(10) 和 Connector(20) 中的
        // Device 初始化会被忽略（因为虚基类只初始化一次）
    }
};
```

> **注意**：在 Android 蓝牙协议栈的实际代码中，菱形继承比较少见。大多数情况下的多继承都是像 `BidiQueueEnd` 那样继承多个 **不相关的接口类**（`IQueueEnqueue` 和 `IQueueDequeue` 没有共同基类），所以不需要虚继承。

### ☕ Java 类比

| 特性 | C++ 虚继承 | Java |
|------|----------|------|
| 菱形继承问题 | ✅ 存在（多继承有状态类时） | ❌ **不存在** |
| 虚继承 `virtual public` | ✅ 解决菱形问题 | ❌ 不需要 |
| 原因 | C++ 支持多继承有状态的类 | Java 只能继承一个类 + 多个无状态接口 |

**Java 为什么没有菱形继承问题？**

- Java 的接口**没有实例字段**（无状态），即使一个类实现了两个有相同方法签名的接口，也不会产生"两份数据"的问题
- Java 只允许继承**一个类**，所以不可能出现"通过两条路径继承同一个有状态的类"的情况
- 即使接口有 `default` 方法的冲突，Java 编译器也会要求子类**显式重写**冲突方法

```cpp
// C++: 菱形继承——Device 被继承两次
class Device { public: int id_; };
class Scanner : public Device { };
class Connector : public Device { };
class BluetoothDevice : public Scanner, public Connector { };
// bt.id_ 歧义！两份 id_！
```

```java
// Java: 不可能有菱形问题
// 1. 只能继承一个类
public class BluetoothDevice extends Scanner { }  // Scanner 是唯一的父类

// 2. 接口无状态，即使"菱形"也不冲突
interface IScanner { void scan(); }
interface IConnector { void connect(); }
class BluetoothDevice implements IScanner, IConnector {
    // 两个接口没有共同状态，不会产生歧义
}
```

**关键差异**：
- Java 的**单继承 + 多接口**设计从根本上避免了菱形继承问题，不需要虚继承
- C++ 的虚继承是解决多继承副作用的复杂机制，Java 通过限制语言特性（不支持类多继承）来避免这个复杂性
- 这是 Java 在语言设计上"少即是多"的典型体现

---

## 8. 接口设计模式

### 8.1 什么是接口类（Interface Class）？

在 C++ 中，**接口类** 是一种特殊的抽象类，具有以下特征：
1. 所有成员函数都是 `public` 纯虚函数（`= 0`）
2. 没有数据成员（或者只有 static 常量）
3. 有一个 **virtual 析构函数**
4. 通常以 `I` 开头命名（如 `IQueueEnqueue`、`IPostableContext`）

```cpp
// 典型的 C++ 接口类写法
class IShape {
public:
    virtual ~IShape() = default;        // 虚析构函数
    virtual double area() const = 0;    // 纯虚函数
    virtual double perimeter() const = 0;
    // 没有数据成员！
};
```

> **Java/C# 对比**：Java 有 `interface` 关键字，C# 也有专门的接口语法。C++ 没有原生的 interface 关键字，但用 **全纯虚函数的抽象类** 来模拟接口，效果完全一样。

### 8.2 蓝牙协议栈中的 Interface 类

#### 接口一：Controller —— HCI 控制器接口

我们已经详细分析过这个类了（第 4 节）。它是协议栈中最大的接口类，定义了蓝牙控制器（硬件芯片）的所有操作能力。

```
角色：定义"蓝牙控制器能做什么"
位置：system/gd/hci/controller.h
纯虚函数数量：100+
使用者：HCI Layer、所有上层模块
实现者：ControllerImpl（以及可能的 Fake 版本）
```

#### 接口二：IQueueEnqueue / IQueueDequeue —— 队列操作接口

```cpp
// system/gd/os/queue.h:36-53
template <typename T>
class IQueueEnqueue {     // 入队接口
public:
  virtual ~IQueueEnqueue() = default;
  virtual void RegisterEnqueue(Handler* handler, EnqueueCallback callback) = 0;
  virtual void UnregisterEnqueue() = 0;
};

template <typename T>
class IQueueDequeue {     // 出队接口
public:
  virtual ~IQueueDequeue() = default;
  virtual void RegisterDequeue(Handler* handler, DequeueCallback callback) = 0;
  virtual void UnregisterDequeue() = 0;
  virtual std::unique_ptr<T> TryDequeue() = 0;
};
```

```
角色：定义"如何向队列放入/取出数据"
位置：system/gd/os/queue.h
使用者：BidiQueueEnd、Queue、EnqueueBuffer
实现者：Queue（真正存数据的）、BidiQueueEnd（委托的）
```

#### 接口三：IPostableContext —— 可投递上下文接口

```cpp
// system/gd/common/i_postable_context.h:24-28
class IPostableContext {
public:
  virtual ~IPostableContext() {}
  virtual void Post(base::OnceClosure closure) = 0;
};
```

```
角色：定义"可以将任务投递到某个执行上下文"
位置：system/gd/common/i_postable_context.h
使用者：所有需要异步执行任务的模块
实现者：PostableContext → Handler
```

#### 接口四：EattExtension —— EATT 扩展接口（特殊案例）

```cpp
// system/stack/eatt/eatt.h:109-286
class EattExtension {
public:
  EattExtension();
  EattExtension(const EattExtension&) = delete;
  EattExtension& operator=(const EattExtension&) = delete;
  virtual ~EattExtension();

  // 单例模式获取实例
  static EattExtension* GetInstance() {
    static EattExtension* instance = new EattExtension();
    return instance;
  }

  // ⚠️ 注意：这些方法是 virtual 但不是纯虚的！
  // EattExtension 不是一个纯接口类，它本身就有默认实现
  virtual bool IsEattSupportedByPeer(const RawAddress& bd_addr);
  virtual void Connect(const RawAddress& bd_addr);
  virtual void Disconnect(const RawAddress& bd_addr, uint16_t cid = EATT_ALL_CIDS);
  virtual void Reconfigure(const RawAddress& bd_addr, uint16_t cid, uint16_t mtu);
  // ... 还有很多 virtual 方法（约 15 个）

  // ⚠️ 这些是非 virtual 的普通方法
  void Start();
  void Stop();
  static void AddFromStorage(const RawAddress& bd_addr);

private:
  struct impl;
  std::unique_ptr<impl> pimpl_;  // Pimpl 惯用法
};
```

**EattExtension 与 Controller 的对比**：

| 特征 | `Controller` | `EattExtension` |
|-----|-------------|----------------|
| 类型 | **纯接口类** | **带有虚方法的实体类** |
| 纯虚函数 | 全部 100+ 个都是 `= 0` | **没有**纯虚函数！ |
| 能否实例化 | ❌ 不能（抽象类） | ✅ 能（通过单例 `GetInstance()`） |
| virtual 用途 | 强制子类实现 | **允许子类覆盖**（可选） |
| 设计目的 | 定义接口契约 | 提供默认实现 + 允许扩展 |
| 非虚方法 | 无 | 有（Start/Stop/AddFromStorage） |

> **EattExtension 的设计思路**：它本身就是一个完整可用的实现（通过 Pimpl 模式隐藏细节），但它的方法都是 virtual 的，这意味着 **测试时可以用 Mock 子类替换**。这是一种介于"纯接口"和"具体类"之间的灵活设计。

### 8.3 接口与实现的分离 —— 依赖倒置原则

这是蓝牙协议栈架构设计的核心思想之一：

```
传统的紧耦合设计（❌ 不推荐）：

  UpperLayer 直接依赖 LowerLayerImpl
  ┌─────────────┐        ┌──────────────┐
  │ UpperLayer  │───────▶│LowerLayerImpl│
  │             │  直接用 │              │
  └─────────────┘        └──────────────┘
  问题：UpperLayer 无法独立编译和测试


接口分离设计（✅ 推荐）：

  UpperLayer 只依赖接口，不依赖具体实现
  ┌─────────────┐      ┌──────────┐      ┌──────────────┐
  │ UpperLayer  │─────▶│ Interface│◀─────│ ImplA (正式) │
  │             │  依赖 │(纯虚类)  │      │ ImplB (测试) │
  └─────────────┘      └──────────┘      └──────────────┘

  优势：
  1. UpperLayer 可以独立编译（只要有接口头文件）
  2. 测试时注入 Mock 实现
  3. 替换实现不需要修改 UpperLayer
```

---

## 9. 阅读继承关系的技巧

### 9.1 如何从头文件快速画出继承图

阅读大型 C++ 项目时，快速理清类的继承关系是非常重要的技能。

**步骤 1：找到类声明的第一行**

```cpp
// 在 .h 文件中找到 class 声明
class Handler : public common::PostableContext {
//             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
//             这里就是继承关系！冒号后面就是基类列表
```

**步骤 2：追踪基类链**

```
Handler (handler.h:57)
  └─ : public common::PostableContext (postable_context.h:25)
       └─ : public IPostableContext (i_postable_context.h:24)
            └─ (最顶层，没有更多基类了)
```

**步骤 3：识别每个类扮演的角色**

| 层级 | 类名 | 角色 | 特征 |
|-----|------|------|------|
| 顶层 | `IPostableContext` | 纯接口 | 全是 `= 0` 纯虚函数 |
| 中间 | `PostableContext` | 半抽象层 | 提供工具方法，未实现纯虚函数 |
| 底层 | `Handler` | 具体实现 | 实现所有纯虚函数，有真实逻辑 |

### 9.2 从虚函数找到实现类的技巧

**技巧一：搜索 `override` 关键字**

当你看到接口类中的一个纯虚函数，想知道谁实现了它：

```bash
# 在项目中搜索
grep -rn "GetLocalName.*override" --include="*.h" --include="*.cc"
```

预期会找到 `ControllerImpl` 中的实现：

```cpp
// controller_impl.h:51
virtual std::string GetLocalName() const override;
```

**技巧二：搜索类名 + `: public`**

想知道哪些类继承自某个接口：

```bash
# 找到所有继承 Controller 的类
grep -rn ": public.*Controller" --include="*.h"
# 结果：ControllerImpl : public Controller (controller_impl.h:34)
```

**技巧三：使用 IDE 功能**

现代 IDE（VS Code、CLion、Android Studio 等）提供了强大的导航功能：

| 操作 | 快捷键（VS Code） | 说明 |
|-----|------------------|------|
| Go to Definition | `F12` | 跳转到定义处 |
| Go to References | `Shift+F12` | 查看所有引用 |
| Go to Implementation | `Ctrl+F12` | **跳转到虚函数的实现**（最有用！） |
| Call Hierarchy | `Shift+Alt+H` | 查看调用链 |

**最实用的场景**：你在读 `Controller::SupportsBle()` 这个纯虚函数，想看实际实现：

1. 光标放在 `SupportsBle` 上
2. 按 `Ctrl+F12`（Go to Implementation）
3. IDE 直接跳转到 `ControllerImpl::SupportsBle()` 的实现代码

### 9.3 实战演练：画出 BidiQueue 相关的完整继承图

让我们把前面学到的知识综合运用，画出 `BidiQueue` 系统的完整继承关系：

```
                        ┌────────────────────┐
                        │  IQueueEnqueue<T>   │  ← 纯接口
                        │  ~IQueueEnqueue()   │
                        │  RegisterEnqueue()=0│
                        │  UnregisterEnqueue()=0│
                        └─────────┬──────────┘
                                  │ 继承
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
        ┌─────────────────────┐    ┌─────────────────────────┐
        │   Queue<T>          │    │ BidiQueueEnd<TEN,TDE>   │
        │ (多继承)            │    │ (多继承)                 │
        │                     │    │                         │
        │ 实现 Enqueue/Dequeue│    │ 委托 Enqueue → tx_      │
        │ 内部持有 queue_ 数据│    │ 委托 Dequeue → rx_      │
        └─────────┬──────────┘    └────────────┬────────────┘
                  │ 继承                         │
                  ▼                              │
        ┌────────────────────┐                   │
        │ IQueueDequeue<T>   │ ◀─────────────────┘ 继承
        │  ~IQueueDequeue()  │
        │  RegisterDequeue()=0│
        │  UnregisterDequeue()=0│
        │  TryDequeue()=0     │
        └────────────────────┘


使用关系：

  BidiQueue<TUP, TDOWN>
  ├── up_queue_:   Queue<TUP>          （上行数据队列）
  ├── down_queue_: Queue<TDOWN>        （下行数据队列）
  ├── up_end_:     BidiQueueEnd<TDOWN, TUP>   （上层端点）
  └── down_end_:   BidiQueueEnd<TUP, TDOWN>   （下层端点）
```

### 9.4 常见继承关系模式的识别速查表

| 模式 | 识别特征 | 蓝牙协议栈中的例子 |
|-----|---------|------------------|
| **纯接口** | 全是 `= 0`，以 I 开头 | `IPostableContext`, `IQueueEnqueue` |
| **大接口** | 50+ 个纯虚函数 | `Controller` (100+) |
| **中间抽象层** | 有 virtual 但非全部 `= 0` | `PostableContext` |
| **具体实现类** | 全部 override 了基类纯虚函数 | `ControllerImpl`, `Handler` |
| **委托包装** | 多继承 + 内部指针转发 | `BidiQueueEnd` |
| **可扩展实体** | virtual 方法但非纯虚 | `EattExtension` |
| **Pimpl 隐藏** | `struct impl; unique_ptr<impl>` | `ControllerImpl`, `EattExtension` |

---

## 总结：核心知识点速查卡

### 语法速查

```cpp
// 1. 基本继承
class Derived : public Base { };

// 2. 虚函数
class Base {
    virtual void func();          // 虚函数（可被子类重写）
    virtual void pure() = 0;      // 纯虚函数（子类必须实现）
    virtual ~Base() = default;    // 虚析构函数（必须！）
};

// 3. override（C++11，必须用！）
class Derived : public Base {
    void func() override;         // 重写基类虚函数
    void pure() override;         // 实现基类纯虚函数
};

// 4. 多继承
class Multi : public Base1, public Base2 { };

// 5. 虚继承（解决菱形问题）
class Mid : virtual public Top { };
`` ### 关键原则

| 原则 | 说明 |
|-----|------|
| **is-a 用继承，has-a 用组合** | 继承表达"是一种"关系 |
| **基类析构函数必须是 virtual** | 否则 delete 基类指针会导致内存泄漏 |
| **重写时必须加 override** | 让编译器帮你检查错误 |
| **接口类 = 全纯虚 + virtual 析构** | C++ 的 interface 模式 |
| **优先用接口指针/引用** | 实现多态和解耦 |
| **虚继承只在菱形问题时使用** | 不要滥用 |

### 蓝牙协议栈中的继承体系一览

```
IPostableContext ──▶ PostableContext ──▶ Handler
     (纯接口)          (工具层)          (实现层)

Controller ──▶ ControllerImpl
 (100+纯虚函数)    (具体实现)

IQueueEnqueue ──┬──▶ Queue          (数据存储实现)
                └──▶ BidiQueueEnd   (委托包装)

IQueueDequeue ──┬──▶ Queue
                └──▶ BidiQueueEnd

EattExtension (带 virtual 方法的实体类，非纯接口)
```

---

> **下一步学习建议**：掌握了继承与多态后，建议继续学习以下主题：
> 1. **智能指针（smart pointer）**：`std::unique_ptr`、`std::shared_ptr` —— 协议栈大量使用
> 2. **模板编程（Template）**：`BidiQueueEnd<TENQUEUE, TDEQUEUE>` 这样的模板类
> 3. **Pimpl 惯用法**：`ControllerImpl` 和 `EattExtension` 都用了这种模式
> 4. **回调机制（Callback）**：协议栈中 `Callback<>` 和 `OnceClosure` 的使用
