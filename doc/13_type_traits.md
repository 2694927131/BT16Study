# 第13章 类型特征与元编程 (Type Traits and Metaprogramming)

## 1. 什么是类型特征 (Type Traits)

### 1.1 编译期类型检查与转换

类型特征 (Type Traits) 是 C++ 模板元编程的核心工具，它允许我们在**编译期**对类型进行查询、比较和转换。与运行时的 `dynamic_cast` 或 `typeid` 不同，type traits 的所有计算都发生在编译阶段，**零运行时开销**。

核心思想：**让编译器帮你做类型判断**。

```cpp
// 运行时判断 —— 有开销，且无法用于模板实例化
if (typeid(T) == typeid(int)) { ... }

// 编译期判断 —— 零开销，可用于模板实例化
if constexpr (std::is_integral_v<T>) { ... }
```

### 1.2 `<type_traits>` 头文件

C++11 引入了 `<type_traits>` 头文件，提供了数十种编译期类型判断和转换工具。C++14/17/20 不断补充了更便捷的 `_v` 变量模板形式。

```cpp
#include <type_traits>

// C++11 形式：通过 ::value 获取结果
std::is_integral<int>::value  // true

// C++17 形式：通过 _v 变量模板直接获取
std::is_integral_v<int>       // true，更简洁
```

> **本书约定**：除非特别说明，我们统一使用 C++17 的 `_v` 变量模板形式。

### 1.3 为什么蓝牙协议栈需要类型特征

蓝牙协议栈是一个复杂的系统软件，它需要处理多种不同类型的数据——整数、枚举、布尔值、字符串、可序列化对象、容器等。类型特征在协议栈中扮演了以下关键角色：

| 角色 | 说明 | 示例 |
|------|------|------|
| **类型安全存储** | 根据不同类型选择不同的序列化策略 | `MutationEntry::Set` 的 6 个重载 |
| **内存布局保证** | 确保蓝牙数据结构的内存布局符合协议规范 | `static_assert(sizeof(RawAddress) == 6)` |
| **编译期防御** | 在编译期捕获类型错误，而非运行时崩溃 | `static_assert(std::is_trivial<Uuid>())` |
| **泛型代码分发** | 在泛型函数中根据类型选择不同代码路径 | `if constexpr (std::is_same_v<T, ...>)` |

### ☕ Java 类比

Java **没有等价的 type_traits 机制**。Java 泛型使用类型擦除（Type Erasure），所有泛型信息在编译后被擦除为 `Object`，无法在编译期进行类型查询和分发：

| C++ 机制 | Java 对应 | 说明 |
|----------|----------|------|
| `type_traits` 编译期类型检查 | ❌ 无等价 | Java 泛型是类型擦除 |
| `is_integral_v<T>` | ❌ 无等价 | Java 无法在编译期判断泛型类型 |
| `is_enum_v<T>` | ❌ 无等价 | 同上 |
| `is_same_v<T, U>` | ❌ 无等价 | 同上 |
| `is_base_of_v<Base, Derived>` | `Class.isAssignableFrom()` | Java 只能在运行时检查 |
| `is_trivial<T>` | ❌ 无等价 | Java 无此概念 |
| 编译期零开销 | 不适用 | Java 的类型检查只能在运行时 |

```cpp
// C++：编译期类型检查，零运行时开销
if constexpr (std::is_integral_v<T>) {
    return std::to_string(value);  // 仅对整数类型编译
}
```

```java
// Java：只能在运行时检查，有开销
if (value instanceof Integer) {
    return String.valueOf(value);  // 运行时类型检查
}
// 或者通过方法重载实现类似效果（但需要为每种类型写一个重载）
```

**Java 为什么不需要 type_traits**：Java 的泛型是类型擦除的，不支持编译期类型分发。Java 通过**方法重载**和**运行时类型检查**（`instanceof`、`Class.isAssignableFrom()`）实现类似效果，但无法做到 C++ 那样的零运行时开销。

---

## 2. 类型判断 traits

类型判断 traits 用于在编译期查询类型的属性，返回 `bool` 值。

### 2.1 `std::is_integral_v<T>` — 是否整数类型

判断 `T` 是否为整数类型（包括 `bool`、`char`、`short`、`int`、`long` 及其 `unsigned` 变体）。

```cpp
static_assert(std::is_integral_v<int>);         // true
static_assert(std::is_integral_v<uint16_t>);    // true
static_assert(std::is_integral_v<bool>);         // true
static_assert(!std::is_integral_v<float>);       // false
static_assert(!std::is_integral_v<std::string>); // false
```

### 2.2 `std::is_enum_v<T>` — 是否枚举类型

判断 `T` 是否为枚举类型（包括有作用域和无作用域枚举）。

```cpp
enum class AddressPolicy { POLICY_NOT_SET, USE_PUBLIC_ADDRESS };
enum EntryType { SET, REMOVE_PROPERTY, REMOVE_SECTION };

static_assert(std::is_enum_v<AddressPolicy>); // true
static_assert(std::is_enum_v<EntryType>);     // true
static_assert(!std::is_enum_v<int>);          // false
```

### 2.3 `std::is_same_v<T, U>` — 是否相同类型

判断 `T` 和 `U` 是否为同一类型（忽略 cv 限定符后比较）。

```cpp
static_assert(std::is_same_v<int, int>);              // true
static_assert(!std::is_same_v<int, long>);            // false
static_assert(std::is_same_v<bool, bool>);            // true
static_assert(std::is_same_v<std::string, std::string>); // true
```

> **注意**：`std::is_same_v` 对 cv 限定符敏感，`std::is_same_v<int, const int>` 为 `false`。如需忽略 cv 限定符，可先使用 `std::remove_cv_t`。

### 2.4 `std::is_base_of_v<Base, Derived>` — 是否继承关系

判断 `Base` 是否为 `Derived` 的基类（包括 `Base` 就是 `Derived` 自身的情况）。

```cpp
class SerializableBase {};
class MyConfig : public SerializableBase {};

static_assert(std::is_base_of_v<SerializableBase, MyConfig>);     // true
static_assert(std::is_base_of_v<SerializableBase, SerializableBase>); // true（自身）
static_assert(!std::is_base_of_v<MyConfig, SerializableBase>);   // false（方向反了）
```

### 2.5 `std::is_trivial<T>` — 是否平凡类型

判断 `T` 是否为平凡类型。平凡类型意味着：
- 使用编译器默认生成的默认构造/析构/拷贝/移动函数
- 没有 virtual 函数或 virtual 基类
- 所有非静态数据成员也是平凡的

平凡类型可以安全地使用 `memcpy` 进行复制，这对蓝牙协议栈中二进制数据的直接传输至关重要。

```cpp
struct RawAddress {
    std::array<uint8_t, 6> address;
};
// RawAddress 是平凡类型 —— 没有自定义构造/析构，没有 virtual

struct Uuid {
    UUID128Bit uu;
    // Uuid 是平凡类型
};

static_assert(std::is_trivial<RawAddress>()); // true
static_assert(std::is_trivial<Uuid>());       // true
```

### 2.6 `std::is_standard_layout<T>` — 是否标准布局

判断 `T` 是否为标准布局类型。标准布局类型保证：
- 所有非静态数据成员具有相同的访问控制
- 没有 virtual 函数或 virtual 基类
- 布局与 C 兼容

标准布局类型可以安全地与 C 代码交互，也可以通过 `memcpy` 进行序列化/反序列化。

```cpp
static_assert(std::is_standard_layout<Uuid>());              // true
static_assert(std::is_standard_layout<Uuid::UUID128Bit>());  // true
```

> **`is_trivial` 与 `is_standard_layout` 的区别**：一个类型可以 `is_trivial` 但不 `is_standard_layout`（如含不同访问控制的成员），也可以 `is_standard_layout` 但不 `is_trivial`（如有用户定义的构造函数）。两者都满足的类型称为 **POD (Plain Old Data)** 类型，可用 `std::is_pod_v<T>` 检测（C++20 中已弃用）。

### 2.7 真实示例：MutationEntry::Set 的类型分发

这是蓝牙协议栈中最精彩的 type traits 应用之一。`MutationEntry::Set` 是一个静态方法，需要将不同类型的值统一转换为字符串存储到配置中。通过 `enable_if` + type traits，实现了**编译期的类型分发**：

```cpp
// system/gd/storage/mutation_entry.h

class MutationEntry {
public:
  // 重载1: 整数类型 —— 用 std::to_string 转换
  template <typename T, typename std::enable_if<std::is_integral_v<T>, int>::type = 0>
  static MutationEntry Set(PropertyType property_type, std::string section_param,
                           std::string property_param, T value_param) {
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              std::to_string(value_param));
  }

  // 重载2: 枚举类型 —— 转为底层整数类型后递归调用重载1
  template <typename T, typename std::enable_if<std::is_enum_v<T>, int>::type = 0>
  static MutationEntry Set(PropertyType property_type, std::string section_param,
                           std::string property_param, T value_param) {
    using EnumUnderlyingType = typename std::underlying_type_t<T>;
    return MutationEntry::Set<EnumUnderlyingType>(property_type, std::move(section_param),
                                                  std::move(property_param),
                                                  static_cast<EnumUnderlyingType>(value_param));
  }

  // 重载3: bool 类型 —— 用 common::ToString 转换
  template <typename T, typename std::enable_if<std::is_same_v<T, bool>, int>::type = 0>
  static MutationEntry Set(PropertyType property_type, std::string section_param,
                           std::string property_param, T value_param) {
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              common::ToString(value_param));
  }

  // 重载4: std::string 类型 —— 直接使用
  template <typename T, typename std::enable_if<std::is_same_v<T, std::string>, int>::type = 0>
  static MutationEntry Set(PropertyType property_type, std::string section_param,
                           std::string property_param, T value_param) {
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              std::move(value_param));
  }

  // 重载5: Serializable 子类 —— 调用 ToLegacyConfigString()
  template <typename T,
            typename std::enable_if<std::is_base_of_v<Serializable<T>, T>, int>::type = 0>
  static MutationEntry Set(PropertyType property_type, std::string section_param,
                           std::string property_param, const T& value_param) {
    return MutationEntry::Set(property_type, std::move(section_param), std::move(property_param),
                              value_param.ToLegacyConfigString());
  }

  // 重载6: Serializable 的 vector —— 遍历并拼接
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
};
```

**调用流程图**：

```
MutationEntry::Set(type, section, property, value)
    │
    ├── T 是 int/uint16_t/... ──→ std::to_string(value) ──→ 重载7(非模板)
    │
    ├── T 是 enum ──→ 转为底层整数 ──→ 递归调用重载1
    │
    ├── T 是 bool ──→ common::ToString(value) ──→ 重载7(非模板)
    │
    ├── T 是 std::string ──→ 直接传递 ──→ 重载7(非模板)
    │
    ├── T 是 Serializable 子类 ──→ value.ToLegacyConfigString() ──→ 重载7(非模板)
    │
    └── T 是 vector<Serializable子类> ──→ 遍历拼接 ──→ 重载7(非模板)
```

> **注意**：`bool` 也是整数类型，但 `is_same_v<T, bool>` 比 `is_integral_v<T>` 更精确，因此重载3 比重载1 优先匹配 `bool` 参数（更特化的模板优先）。

### ☕ Java 类比

C++ 的类型判断 traits 在 Java 中没有编译期等价，但可以通过方法重载实现类似效果：

| C++ type_trait | Java 替代方案 | 说明 |
|----------------|-------------|------|
| `is_integral_v<T>` | 方法重载 `set(int)`, `set(long)` | Java 为每种整数类型写一个重载 |
| `is_enum_v<T>` | 方法重载 + `Enum.ordinal()` | Java 枚举有 `ordinal()` 方法 |
| `is_same_v<T, bool>` | 方法重载 `set(boolean)` | Java 有基本类型 `boolean` |
| `is_same_v<T, string>` | 方法重载 `set(String)` | Java 有 `String` 类型 |
| `is_base_of_v<Serializable, T>` | `instanceof Serializable` | Java 运行时检查 |
| `is_specialization_of<T, vector>` | `instanceof List` | Java 运行时检查 |

```cpp
// C++：用 enable_if + type_traits 实现编译期类型分发
template <typename T, typename enable_if<is_integral_v<T>, int>::type = 0>
static MutationEntry Set(PropertyType type, string section, string property, T value) {
    return Set(type, section, property, to_string(value));
}
```

```java
// Java：用方法重载实现类型分发（运行时解析）
public class MutationEntry {
    public static MutationEntry set(PropertyType type, String section,
                                     String property, int value) {
        return set(type, section, property, String.valueOf(value));
    }
    public static MutationEntry set(PropertyType type, String section,
                                     String property, long value) {
        return set(type, section, property, String.valueOf(value));
    }
    public static MutationEntry set(PropertyType type, String section,
                                     String property, boolean value) {
        return set(type, section, property, String.valueOf(value));
    }
    public static MutationEntry set(PropertyType type, String section,
                                     String property, String value) {
        // 直接使用字符串
    }
    public static MutationEntry set(PropertyType type, String section,
                                     String property, Serializable value) {
        return set(type, section, property, value.toLegacyConfigString());
    }
}
```

**关键差异**：C++ 用模板 + `enable_if` 实现编译期分发，一个模板函数覆盖所有整数类型；Java 必须为每种类型写一个重载方法，但代码更直观、更易理解。

---

## 3. 类型转换 traits

类型转换 traits 用于在编译期对类型进行变换，产生新的类型。

### 3.1 `std::underlying_type_t<T>` — 获取枚举底层类型

将枚举类型 `T` 映射为其底层整数类型。这在蓝牙协议栈中非常常用——枚举值需要被序列化为整数存储。

```cpp
enum class AddressPolicy : uint8_t { POLICY_NOT_SET, USE_PUBLIC_ADDRESS, ... };
//                              ^^^^^^^^ 底层类型

using Underlying = std::underlying_type_t<AddressPolicy>;  // uint8_t
```

**真实示例**：在 `MutationEntry::Set` 的枚举重载中，将枚举值转换为其底层整数类型，然后递归调用整数版本的重载：

```cpp
// system/gd/storage/mutation_entry.h:41-48
template <typename T, typename std::enable_if<std::is_enum_v<T>, int>::type = 0>
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, T value_param) {
    // 获取枚举 T 的底层类型（如 int、uint8_t 等）
    using EnumUnderlyingType = typename std::underlying_type_t<T>;
    // 将枚举值转为底层整数，递归调用整数版本的 Set
    return MutationEntry::Set<EnumUnderlyingType>(property_type, std::move(section_param),
                                                  std::move(property_param),
                                                  static_cast<EnumUnderlyingType>(value_param));
}
```

**为什么需要这一步？** 因为 `std::to_string` 不接受枚举类型，必须先转换为底层整数类型。

### 3.2 `std::decay_t<T>` — 去除引用和 cv 限定符

`std::decay_t<T>` 模拟了按值传参时的类型退化：
1. 去除引用（`T&` → `T`，`T&&` → `T`）
2. 去除 cv 限定符（`const T` → `T`，`volatile T` → `T`）
3. 数组和函数类型退化为指针（`T[N]` → `T*`，`T(U)` → `T(*)(U)`）

```cpp
static_assert(std::is_same_v<std::decay_t<const int&>, int>);           // true
static_assert(std::is_same_v<std::decay_t<volatile std::string>, std::string>); // true
static_assert(std::is_same_v<std::decay_t<int[10]>, int*>);             // true
```

**真实示例**：在 `std::visit` 的 lambda 中，`std::decay_t` 用于获取 variant 中实际存储的类型（去除引用和 const）：

```cpp
// system/main/shim/acl.cc:691-699
std::visit(
    [](auto&& data) {
        using T = std::decay_t<decltype(data)>;
        // data 的类型是 const 引用，但 T 是去除引用和 const 后的纯类型
        if constexpr (std::is_same_v<T, hci::acl_manager::DataAsPeripheral>) {
            return data.advertising_set_id;
        } else {
            return std::optional<uint8_t>{};
        }
    },
    connection_->GetRoleSpecificData());
```

```cpp
// system/gd/hci/le_address_manager.cc:626-639
std::visit(
    [this](auto&& command) {
        using T = std::decay_t<decltype(command)>;
        if constexpr (std::is_same_v<T, UpdateIRKCommand>) {
            update_irk(command);
        } else if constexpr (std::is_same_v<T, RotateRandomAddressCommand>) {
            rotate_random_address();
        } else if constexpr (std::is_same_v<T, HCICommand>) {
            enqueue_command_.Run(std::move(command.command));
        } else {
            static_assert(!sizeof(T*), "non-exhaustive visitor!");
        }
    },
    command.contents);
```

> **为什么在 `std::visit` 中需要 `decay_t`？** 因为 `auto&&` 推导出的类型是引用类型（如 `const UpdateIRKCommand&`），而 `std::is_same_v` 对引用类型和值类型视为不同类型。使用 `decay_t` 可以得到干净的值类型，便于与目标类型比较。

### ☕ Java 类比

C++ 的类型转换 traits 在 Java 中大多不需要，因为 Java 的类型系统更简单：

| C++ 类型转换 trait | Java 对应 | 说明 |
|-------------------|----------|------|
| `underlying_type_t<T>` | `Enum.ordinal()` / `Enum.getDeclaringClass()` | Java 枚举有运行时支持 |
| `decay_t<T>` | ❌ 不需要 | Java 没有引用/值类型区分 |
| `remove_cv_t<T>` | ❌ 不需要 | Java 没有 const/volatile |
| `remove_reference_t<T>` | ❌ 不需要 | Java 没有引用引用 |
| `add_const_t<T>` | `final` 关键字（不等价） | Java 用 `final` 而非 `const` |

```cpp
// C++：underlying_type_t 获取枚举底层类型
using Underlying = std::underlying_type_t<AddressPolicy>;  // uint8_t
return MutationEntry::Set<Underlying>(..., static_cast<Underlying>(value));
```

```java
// Java：枚举天然支持 ordinal() 和 name()
public enum AddressPolicy {
    POLICY_NOT_SET, USE_PUBLIC_ADDRESS;
}

// 获取枚举的整数值
int underlyingValue = AddressPolicy.POLICY_NOT_SET.ordinal();  // 0
// 或者自定义值
public enum AddressPolicy {
    POLICY_NOT_SET(0), USE_PUBLIC_ADDRESS(1);
    private final int value;
    AddressPolicy(int value) { this.value = value; }
    public int getValue() { return value; }
}
```

**Java 不需要 `underlying_type_t` 的原因**：Java 的枚举是完整的类（继承自 `java.lang.Enum`），自带 `ordinal()`、`name()`、`getDeclaringClass()` 等方法。C++ 的枚举本质上是整数，需要 `underlying_type_t` 来获取其底层类型信息。

---

## 4. std::enable_if (SFINAE)

### 4.1 替换失败并非错误 (Substitution Failure Is Not An Error)

SFINAE 是 C++ 模板的核心规则：当编译器在实例化模板时，如果某个候选重载的模板参数替换失败，**不会产生编译错误**，而是将该重载从候选集中移除，继续尝试其他重载。

```cpp
// 假设 T = std::string
template <typename T, typename std::enable_if<std::is_integral_v<T>, int>::type = 0>
void foo(T val);   // 替换失败：is_integral_v<std::string> 为 false
                    // enable_if<false, int> 没有 ::type 成员
                    // 但这不是错误！只是这个重载被忽略

template <typename T, typename std::enable_if<std::is_same_v<T, std::string>, int>::type = 0>
void foo(T val);   // 替换成功：is_same_v<std::string, std::string> 为 true
                    // enable_if<true, int>::type 是 int，匹配成功
```

### 4.2 `enable_if` 的原理

```cpp
// C++ 标准库中的简化定义
template <bool B, typename T = void>
struct enable_if {};           // B 为 false 时，没有 ::type

template <typename T>
struct enable_if<true, T> {
    using type = T;            // B 为 true 时，::type = T
};
```

`enable_if` 的两种常见用法：

**用法一：模板参数默认值（推荐）**

```cpp
template <typename T, typename std::enable_if<条件, int>::type = 0>
void foo(T val);
```

- 当条件为 `true` 时，第二个模板参数推导为 `int`，默认值 `0` 匹配
- 当条件为 `false` 时，`enable_if<false, int>` 没有 `::type`，替换失败，该重载被忽略
- **优点**：不影响函数签名，调用时无需额外参数

**用法二：函数返回类型**

```cpp
template <typename T>
typename std::enable_if<条件, ReturnType>::type foo(T val);
```

- 当条件为 `true` 时，返回类型为 `ReturnType`
- 当条件为 `false` 时，替换失败

### 4.3 真实示例：MutationEntry::Set 的 6 个重载

让我们完整分析 `MutationEntry::Set` 如何利用 SFINAE 实现**编译期类型分发**：

```
调用 MutationEntry::Set(NORMAL, "section", "prop", 42)
    │
    │ 编译器依次尝试每个重载：
    │
    ├─ 重载1: is_integral_v<int> = true  ✓ enable_if<true, int>::type = int
    │         匹配成功！
    │
    ├─ 重载2: is_enum_v<int> = false  ✗ enable_if<false, int> 无 ::type
    │         SFINAE，跳过
    │
    ├─ 重载3: is_same_v<int, bool> = false  ✗ 跳过
    ├─ 重载4: is_same_v<int, string> = false  ✗ 跳过
    ├─ 重载5: is_base_of_v<Serializable<int>, int> = false  ✗ 跳过
    └─ 重载6: is_specialization_of<int, vector> = false  ✗ 跳过
```

```
调用 MutationEntry::Set(NORMAL, "section", "prop", AddressPolicy::USE_PUBLIC_ADDRESS)
    │
    ├─ 重载1: is_integral_v<AddressPolicy> = false  ✗ 跳过
    ├─ 重载2: is_enum_v<AddressPolicy> = true  ✓ 匹配！
    │         内部：underlying_type_t<AddressPolicy> = uint8_t
    │         递归调用 Set<uint8_t>(..., static_cast<uint8_t>(value))
    │         → 匹配重载1
    ...
```

```
调用 MutationEntry::Set(NORMAL, "section", "prop", true)
    │
    ├─ 重载1: is_integral_v<bool> = true  ✓ 候选
    ├─ 重载2: is_enum_v<bool> = false  ✗
    ├─ 重载3: is_same_v<bool, bool> = true  ✓ 候选
    ...
    │
    │ 重载1 和重载3 都匹配！
    │ 但重载3 的条件 is_same_v<bool, bool> 比重载1 的 is_integral_v<bool>
    │ 更特化（更严格），因此编译器选择重载3
```

> **关键洞察**：这 6 个重载就像编译期的 `switch-case`，每个 `enable_if` 条件就是一个 `case` 分支。SFINAE 保证了不匹配的分支被自动排除。

### ☕ Java 类比

Java **没有 SFINAE / enable_if 机制**。Java 通过方法重载和泛型边界实现类似效果：

| C++ 机制 | Java 替代方案 | 说明 |
|----------|-------------|------|
| `enable_if` + SFINAE | 方法重载 | Java 编译器自动选择最匹配的重载 |
| 编译期类型分发 | 运行时 `instanceof` | Java 在运行时判断类型 |
| 模板条件启用 | 泛型边界 `<T extends Xxx>` | Java 只能约束上界 |
| 6 个模板重载 | 6 个具体类型重载 | Java 更冗长但更直观 |

```cpp
// C++：SFINAE 实现编译期类型分发
template <typename T, typename enable_if<is_integral_v<T>, int>::type = 0>
static MutationEntry Set(PropertyType type, string section, string property, T value);
```

```java
// Java：方法重载实现类型分发（编译器在编译期选择正确的重载）
public static MutationEntry set(PropertyType type, String section,
                                 String property, int value) { ... }
public static MutationEntry set(PropertyType type, String section,
                                 String property, long value) { ... }
public static MutationEntry set(PropertyType type, String section,
                                 String property, boolean value) { ... }
public static MutationEntry set(PropertyType type, String section,
                                 String property, String value) { ... }
public static MutationEntry set(PropertyType type, String section,
                                 String property, Serializable value) { ... }
```

**Java 为什么不需要 SFINAE**：Java 的方法重载在编译期由编译器自动选择最匹配的方法，不需要"替换失败"机制。Java 的泛型不支持条件启用，但方法重载提供了更直观的类型分发方式。

---

## 5. if constexpr (C++17)

### 5.1 编译期条件分支

`if constexpr` 是 C++17 引入的编译期条件语句。与普通 `if` 不同，`if constexpr` 的条件必须是编译期常量表达式，且**未选中的分支不会被实例化**（甚至可以包含语法上有效但类型上不合法的代码）。

```cpp
template <typename T>
auto process(T value) {
    if constexpr (std::is_integral_v<T>) {
        return value + 1;       // 仅当 T 是整数类型时实例化
    } else if constexpr (std::is_same_v<T, std::string>) {
        return value + "!";     // 仅当 T 是 string 时实例化
    } else {
        return value;           // 其他类型
    }
}
```

### 5.2 与 SFINAE 的对比

| 特性 | SFINAE (enable_if) | if constexpr |
|------|-------------------|--------------|
| **作用范围** | 选择不同的函数重载 | 在同一函数内选择不同代码路径 |
| **代码可读性** | 较差（需要理解 enable_if 机制） | 较好（类似普通 if-else） |
| **返回类型** | 不同重载可有不同返回类型 | 同一函数，返回类型必须一致 |
| **错误信息** | 往往晦涩难懂 | 更清晰 |
| **适用场景** | 需要不同函数签名时 | 同一函数内根据类型选择逻辑时 |

**经验法则**：能用 `if constexpr` 就不用 SFINAE，除非需要不同的函数签名。

### 5.3 真实示例一：ACL 连接的角色特定数据处理

在蓝牙 LE 连接中，连接角色可能是 Central（中心设备）或 Peripheral（外围设备），不同角色有不同的数据。使用 `std::visit` + `if constexpr` 可以优雅地处理这种变体：

```cpp
// system/main/shim/acl.cc:689-700
std::optional<uint8_t> GetAdvertisingSetConnectedTo() {
    return std::visit(
        [](auto&& data) {
            using T = std::decay_t<decltype(data)>;
            if constexpr (std::is_same_v<T, hci::acl_manager::DataAsPeripheral>) {
                // 仅当角色为 Peripheral 时，才有 advertising_set_id
                return data.advertising_set_id;
            } else {
                // Central 角色没有 advertising_set_id
                return std::optional<uint8_t>{};
            }
        },
        connection_->GetRoleSpecificData());
}
```

```cpp
// system/main/shim/acl.cc:1436-1447
auto can_read_discoverable_characteristics = std::visit(
    [&](auto&& data) {
        using T = std::decay_t<decltype(data)>;
        if constexpr (std::is_same_v<T, hci::acl_manager::DataAsPeripheral>) {
            return data.connected_to_discoverable;
        } else {
            // 如果是 Central，对端总是可发现的
            return true;
        }
    },
    connection_->GetRoleSpecificData());
```

### 5.4 真实示例二：LE 地址管理器的命令分发

LE 地址管理器使用 `std::variant` 存储不同类型的命令，通过 `std::visit` + `if constexpr` 实现类型安全的命令分发：

```cpp
// system/gd/hci/le_address_manager.cc:626-639
std::visit(
    [this](auto&& command) {
        using T = std::decay_t<decltype(command)>;
        if constexpr (std::is_same_v<T, UpdateIRKCommand>) {
            update_irk(command);
        } else if constexpr (std::is_same_v<T, RotateRandomAddressCommand>) {
            rotate_random_address();
        } else if constexpr (std::is_same_v<T, HCICommand>) {
            enqueue_command_.Run(std::move(command.command));
        } else {
            // 编译期穷举检查：如果新增了 variant 类型但忘记处理，
            // static_assert 会触发编译错误
            static_assert(!sizeof(T*), "non-exhaustive visitor!");
        }
    },
    command.contents);
```

> **技巧**：`static_assert(!sizeof(T*), "non-exhaustive visitor!")` 是一种惯用写法。`sizeof(T*)` 永远不为 0（指针大小至少 1 字节），所以 `!sizeof(T*)` 永远为 `false`。由于它在 `else` 分支中，只有当新增了未处理的 variant 类型时才会触发，起到编译期"穷举检查"的作用。

### ☕ Java 类比

Java **没有 `if constexpr` 机制**。Java 的 `if` 语句所有分支都会被编译，无法在编译期丢弃分支：

| C++ 机制 | Java 对应 | 说明 |
|----------|----------|------|
| `if constexpr` | ❌ 无等价 | Java 的 `if` 所有分支都编译 |
| 编译期丢弃未选中分支 | 不适用 | Java 无法做到 |
| `std::visit` + `if constexpr` | `switch` 语句 + `enum` | Java 用 switch 匹配枚举 |
| 编译期穷举检查 | `switch` 缺少 `default` 时编译器警告 | Java 编译器可检查枚举穷举 |

```cpp
// C++：if constexpr + std::visit
std::visit([](auto&& data) {
    using T = std::decay_t<decltype(data)>;
    if constexpr (std::is_same_v<T, DataAsPeripheral>) {
        return data.advertising_set_id;
    } else {
        return std::optional<uint8_t>{};
    }
}, roleData);
```

```java
// Java：switch + enum（编译器可检查穷举）
public Optional<Integer> getAdvertisingSetId(RoleData data) {
    return switch (data.getType()) {
        case PERIPHERAL -> Optional.of(((PeripheralData) data).advertisingSetId);
        case CENTRAL -> Optional.empty();
        // 编译器会检查是否穷举了所有枚举值
    };
}
```

**Java 为什么不需要 `if constexpr`**：Java 的泛型是类型擦除的，不存在"模板实例化"的概念，因此不需要编译期分支丢弃。Java 通过 `switch` + 枚举实现类型安全的分支分发，且编译器可以检查穷举性。

---

## 6. static_assert

### 6.1 编译期断言

`static_assert` 是 C++11 引入的编译期断言机制。如果条件为 `false`，编译立即失败并显示指定的错误信息。

```cpp
static_assert(常量表达式, "错误信息");
// C++17 起可省略错误信息
static_assert(常量表达式);
```

与 `assert()` 的区别：

| 特性 | `assert()` | `static_assert` |
|------|-----------|-----------------|
| **检查时机** | 运行时 | 编译期 |
| **条件类型** | 任意布尔表达式 | 常量表达式 |
| **Release 模式** | 通过 `NDEBUG` 禁用 | 始终生效 |
| **适用场景** | 运行时不变量 | 类型/编译期不变量 |

### 6.2 与 type_traits 配合

`static_assert` + type_traits 是编译期防御的黄金组合，确保类型属性满足要求：

```cpp
// 确保类型是平凡的
static_assert(std::is_trivial<T>(), "T must be trivial!");

// 确保类型是标准布局
static_assert(std::is_standard_layout<T>(), "T must have standard layout!");

// 确保类型大小正确
static_assert(sizeof(T) == expected_size, "T has wrong size!");
```

### 6.3 真实示例一：RawAddress 的大小保证

蓝牙 MAC 地址必须是 6 字节，这是蓝牙核心规范的要求。`static_assert` 确保这一约束在编译期被强制执行：

```cpp
// system/types/src/address.cc:27
static_assert(sizeof(RawAddress) == 6, "RawAddress must be 6 bytes long!");
```

```cpp
// system/types/include/bluetooth/types/address.h:74
template <>
struct std::hash<RawAddress> {
    std::size_t operator()(const RawAddress& val) const {
        // 确保 uint64_t 至少有 6 字节，可以容纳 RawAddress
        static_assert(sizeof(uint64_t) >= RawAddress::kLength);
        uint64_t int_addr = 0;
        memcpy(reinterpret_cast<uint8_t*>(&int_addr), val.address.data(), RawAddress::kLength);
        return std::hash<uint64_t>{}(int_addr);
    }
};
```

> **为什么这很重要？** 蓝牙数据包中的地址字段是固定 6 字节。如果 `RawAddress` 的大小不是 6（比如因为编译器添加了填充字节），所有地址的序列化/反序列化都会出错，导致设备无法通信。`static_assert` 将这种错误从"运行时难以调试的协议错误"变为"编译期立即发现的类型错误"。

### 6.4 真实示例二：Uuid 的完整性保证

UUID 是蓝牙中标识服务和特征的核心数据结构。它必须是 16 字节的平凡类型，以便可以安全地通过 `memcpy` 在协议层传输：

```cpp
// system/types/src/uuid.cc:30-38
static_assert(Uuid::kNumBytes128 == 16, "kNumBytes128 must be 16 bytes long!");
static_assert(std::is_trivial<Uuid>(), "Uuid must be trivial!");
static_assert(std::is_standard_layout<Uuid>(), "Uuid must have standard layout!");
static_assert(sizeof(Uuid) == Uuid::kNumBytes128, "Uuid must be 16 bytes long!");
static_assert(std::is_trivial<Uuid::UUID128Bit>(), "Uuid::UUID128Bit must be trivial!");
static_assert(std::is_standard_layout<Uuid::UUID128Bit>(),
              "Uuid::UUID128Bit must have standard layout!");
static_assert(sizeof(Uuid::UUID128Bit) == Uuid::kNumBytes128,
              "Uuid::UUID128Bit must be 16 bytes long!");
```

这 7 条 `static_assert` 构成了一套完整的**编译期防御体系**：

1. **常量正确性**：`kNumBytes128 == 16` 确保常量定义正确
2. **平凡性**：`is_trivial` 确保 `memcpy` 安全
3. **标准布局**：`is_standard_layout` 确保 C 兼容
4. **大小正确**：`sizeof` 确保没有编译器填充
5. **内部类型一致性**：对 `UUID128Bit` 同样检查

### 6.5 真实示例三：ACL 哈希中的大小检查

```cpp
// system/main/shim/acl.cc:108-109
struct hash<ConnectAddressWithType> {
    std::size_t operator()(const ConnectAddressWithType& val) const {
        static_assert(sizeof(uint64_t) >= (bluetooth::hci::Address::kLength +
                                           sizeof(bluetooth::hci::FilterAcceptListAddressType)));
        // ...
    }
```

### ☕ Java 类比

Java **没有 `static_assert` 机制**。Java 无法在编译期检查类型属性或大小约束：

| C++ 机制 | Java 对应 | 说明 |
|----------|----------|------|
| `static_assert(condition, msg)` | ❌ 无等价 | Java 无编译期断言 |
| `static_assert(sizeof(T) == 6)` | ❌ 无等价 | Java 无法检查对象大小 |
| `static_assert(is_trivial<T>())` | ❌ 无等价 | Java 无平凡类型概念 |
| `assert(condition)` | `assert condition : msg` | Java 运行时断言 |
| 编译期防御 | 运行时检查 + 单元测试 | Java 依赖测试保证正确性 |

```cpp
// C++：编译期断言，错误在编译时发现
static_assert(sizeof(RawAddress) == 6, "RawAddress must be 6 bytes long!");
static_assert(std::is_trivial<Uuid>(), "Uuid must be trivial!");
```

```java
// Java：无法在编译期检查对象大小或类型属性
// 只能在运行时通过测试验证
@Test
public void testRawAddressSize() {
    // Java 无法直接检查对象内存大小
    // 但可以通过序列化大小间接验证
    RawAddress addr = new RawAddress();
    byte[] bytes = addr.toBytes();
    assertEquals(6, bytes.length);
}
```

**Java 为什么不需要 `static_assert`**：Java 运行在 JVM 上，对象的大小和内存布局由 JVM 管理，开发者无法也不需要控制。Java 通过运行时检查和单元测试来保证正确性，而非编译期断言。

---

## 7. 自定义 type traits

### 7.1 `is_specialization_of` 检测模板特化

标准库没有提供"判断一个类型是否是某个模板的特化"的工具。例如，判断 `std::vector<int>` 是否是 `std::vector` 的特化。蓝牙协议栈自己实现了这个 trait：

```cpp
// system/gd/common/type_helper.h

namespace bluetooth {
namespace common {

// 通用模板：默认不是特化，继承 false_type
template <typename T, template <typename...> class TemplateType>
struct is_specialization_of : std::false_type {};

// 偏特化：当 T 恰好是 TemplateType<Args...> 的实例化时，继承 true_type
template <template <typename...> class TemplateType, typename... Args>
struct is_specialization_of<TemplateType<Args...>, TemplateType> : std::true_type {};

}  // namespace common
}  // namespace bluetooth
```

**原理解析**：

```
is_specialization_of<std::vector<int>, std::vector>
    │
    │ 编译器尝试偏特化匹配：
    │ T = std::vector<int>  能否匹配 TemplateType<Args...>？
    │   → TemplateType = std::vector, Args... = {int}
    │   → 匹配成功！继承 true_type
    │
    └── is_specialization_of<std::vector<int>, std::vector>::value = true

is_specialization_of<std::string, std::vector>
    │
    │ 编译器尝试偏特化匹配：
    │ T = std::string  能否匹配 TemplateType<Args...>？
    │   → std::string 不是任何 TemplateType<Args...> 的形式
    │   → 匹配失败，使用通用模板
    │
    └── is_specialization_of<std::string, std::vector>::value = false
```

### 7.2 真实示例：MutationEntry::Set 的 vector 重载

在 `MutationEntry::Set` 的最后一个重载中，`is_specialization_of` 用于判断 `T` 是否是 `std::vector` 的特化：

```cpp
// system/gd/storage/mutation_entry.h:72-76
template <typename T, typename std::enable_if<
                          bluetooth::common::is_specialization_of<T, std::vector>::value &&
                                  std::is_base_of_v<Serializable<typename T::value_type>,
                                                    typename T::value_type>,
                          int>::type = 0>
static MutationEntry Set(PropertyType property_type, std::string section_param,
                         std::string property_param, const T& value_param);
```

这里的 `enable_if` 条件是**两个条件的合取**：

1. `is_specialization_of<T, std::vector>::value`：`T` 必须是 `std::vector` 的特化
2. `std::is_base_of_v<Serializable<typename T::value_type>, typename T::value_type>`：vector 的元素类型必须继承自 `Serializable`

只有同时满足这两个条件（如 `std::vector<Device>`，其中 `Device` 继承自 `Serializable<Device>`），这个重载才会被选中。

### ☕ Java 类比

Java **没有自定义 type traits 的机制**，但可以通过运行时类型检查实现类似效果：

| C++ 机制 | Java 对应 | 说明 |
|----------|----------|------|
| `is_specialization_of<T, vector>` | `obj instanceof List<?>` | Java 运行时检查 |
| 自定义 trait（偏特化） | ❌ 无等价 | Java 泛型不支持偏特化 |
| 编译期模板匹配 | 运行时 `instanceof` | Java 只能在运行时判断 |

```cpp
// C++：自定义 is_specialization_of trait
template <typename T, template <typename...> class TemplateType>
struct is_specialization_of : std::false_type {};

template <template <typename...> class TemplateType, typename... Args>
struct is_specialization_of<TemplateType<Args...>, TemplateType> : std::true_type {};
```

```java
// Java：运行时检查是否是 List 类型
public static <T> MutationEntry set(PropertyType type, String section,
                                     String property, T value) {
    if (value instanceof List<?>) {
        List<?> list = (List<?>) value;
        if (!list.isEmpty() && list.get(0) instanceof Serializable) {
            // 处理 List<Serializable> 的情况
        }
    }
    // ...
}
```

**Java 为什么不需要自定义 traits**：Java 的泛型是类型擦除的，无法在编译期进行模板匹配。Java 通过 `instanceof` 和反射在运行时检查类型，虽然牺牲了编译期安全性，但代码更简单。

---

## 8. 初学者如何阅读 type_traits 代码

### 8.1 先看 enable_if 的条件部分

遇到带 `enable_if` 的模板函数时，**不要从头到尾逐字阅读**，而是先找到 `enable_if` 的条件：

```cpp
template <typename T, typename std::enable_if<std::is_integral_v<T>, int>::type = 0>
//                                   ^^^^^^^^^^^^^^^^^^^^^^^^
//                                   先看这里！条件是"T 必须是整数类型"
static MutationEntry Set(...);
```

**阅读步骤**：
1. 找到 `enable_if<条件, ...>` 中的**条件**
2. 理解条件的含义（如 `is_integral_v<T>` = "T 是整数类型"）
3. 知道这个重载**只对满足条件的类型生效**
4. 看函数体，理解满足条件后的处理逻辑

### 8.2 理解"编译期 if-Else"

将 `enable_if` 重载集合理解为编译期的 `if-else` 链：

```cpp
// 编译期逻辑（伪代码）：
if (is_integral_v<T>) {
    // 重载1: 整数处理
} else if (is_enum_v<T>) {
    // 重载2: 枚举处理
} else if (is_same_v<T, bool>) {
    // 重载3: 布尔处理
} else if (is_same_v<T, std::string>) {
    // 重载4: 字符串处理
} else if (is_base_of_v<Serializable<T>, T>) {
    // 重载5: 可序列化对象处理
} else if (is_vector<T> && is_serializable<T::value_type>) {
    // 重载6: 可序列化对象向量处理
}
```

同样，`if constexpr` 就是字面意义上的编译期 `if-else`：

```cpp
// 运行期 if —— 两个分支都会编译
if (std::is_integral_v<T>) { ... }  // 即使 T 不是整数，这行也会被编译

// 编译期 if constexpr —— 未选中的分支不会编译
if constexpr (std::is_integral_v<T>) { ... }  // T 不是整数时，这行被丢弃
```

### 8.3 不必深究模板元编程原理

对于初学者，以下知识**足够使用** type_traits：

| 你需要知道的 | 你暂时不需要知道的 |
|-------------|-------------------|
| `enable_if<条件, int>::type = 0` 是固定写法 | `enable_if` 的完整模板元编程原理 |
| `_v` 后缀等价于 `::value` | SFINAE 的所有边界情况 |
| `decay_t` 用于去除引用和 const | 完整的类型退化规则（数组→指针等） |
| `if constexpr` 是编译期 if | 模板实例化的完整机制 |
| `static_assert` 是编译期断言 | 编译器如何处理编译期错误 |

**实用建议**：
1. **抄模式**：遇到 `enable_if` 代码，照着现有模式写，不必从零推导
2. **看效果**：关注"这个重载对什么类型生效"，而非"编译器如何选择"
3. **用 `if constexpr`**：新代码优先使用 `if constexpr`，比 SFINAE 更易读
4. **善用 `static_assert`**：在模板函数开头加 `static_assert`，让错误信息更友好

---

## 附录：蓝牙协议栈 type_traits 速查表

| type_trait | 用途 | 协议栈示例 |
|-----------|------|-----------|
| `is_integral_v<T>` | 判断整数类型 | MutationEntry::Set 整数重载 |
| `is_enum_v<T>` | 判断枚举类型 | MutationEntry::Set 枚举重载 |
| `is_same_v<T, U>` | 判断相同类型 | MutationEntry::Set bool/string 重载；if constexpr 分支 |
| `is_base_of_v<B, D>` | 判断继承关系 | MutationEntry::Set Serializable 重载 |
| `is_trivial<T>` | 判断平凡类型 | Uuid 的 static_assert |
| `is_standard_layout<T>` | 判断标准布局 | Uuid 的 static_assert |
| `underlying_type_t<T>` | 枚举底层类型 | MutationEntry::Set 枚举转整数 |
| `decay_t<T>` | 去除引用/cv | std::visit lambda 中的类型提取 |
| `enable_if` | SFINAE 条件启用 | MutationEntry::Set 的 6 个重载 |
| `is_specialization_of` | 检测模板特化 | MutationEntry::Set vector 重载 |
