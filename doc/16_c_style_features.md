# 16. C风格特性与预处理器

> 📎 关联教材：01, 05, 07, 10, 14

蓝牙协议栈是一个有着数十年历史的代码库，其中大量使用了 C 语言风格的语法特性。即使在新版 C++ 重构中，你仍然会频繁遇到预处理器指令、宏定义、位域、联合体、函数指针等传统写法。理解这些特性，是阅读和维护协议栈代码的必备技能。

本文将系统讲解协议栈中常见的 12 类 C 风格特性，每个知识点都配有真实代码示例。

---

## 1. 预处理器指令基础

C/C++ 的预处理器（Preprocessor）在编译之前对源代码进行文本替换。它是 C 体系中最古老也最强大的机制之一。

### 1.1 #include 文本包含

`#include` 的本质是**文本粘贴**——把指定文件的内容原封不动地插入到当前位置。

```cpp
// 尖括号：在系统/项目 include 路径中搜索
#include <bluetooth/log.h>
#include <cstdint>

// 引号：先搜索当前目录，再搜索系统路径
#include "macros.h"
#include "osi/include/alarm.h"
```

**关键区别**：`#include` 是纯文本替换，同一个头文件被包含两次，其内容就会出现两次，导致重复定义错误。这就是为什么需要头文件卫士。

### 1.2 #pragma once 头文件防重复包含

`#pragma once` 是一种简洁的头文件防重复包含方式，告诉编译器"这个文件只处理一次"。

```cpp
// system/osi/include/osi.h:19
#pragma once

#include <stdbool.h>
#include <stdint.h>

#define UNUSED_ATTR __attribute__((unused))
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
```

```cpp
// system/types/include/bluetooth/types/remote_version.h:19
#pragma once

#include <cstdint>
#include <format>
#include <string>
```

`#pragma once` 简单高效，但不是 C/C++ 标准——它由编译器厂商约定支持（GCC、Clang、MSVC 均支持）。协议栈的 GD（Gable Dormer）新模块大量使用此方式。

### 1.3 #ifndef/#define/#endif 头文件卫士

这是 C/C++ 标准规定的传统防重复包含方式，又称"include guard"：

```cpp
// system/stack/smp/smp_int.h:24-25
#ifndef SMP_INT_H
#define SMP_INT_H

// ... 整个文件内容 ...

// system/stack/smp/smp_int.h:517
#endif /* SMP_INT_H */
```

工作原理：
1. 第一次包含时，`SMP_INT_H` 未定义，`#ifndef` 为真，执行 `#define SMP_INT_H` 并包含内容
2. 第二次包含时，`SMP_INT_H` 已定义，`#ifndef` 为假，跳过全部内容直到 `#endif`

### 1.4 条件性宏定义

有时宏可能已被其他文件定义，需要先检查再定义：

```cpp
// system/log/include/bluetooth/log.h（典型模式）
#ifndef LOG_TAG
#define LOG_TAG "bluetooth"
#endif
```

这样，在包含此头文件之前，使用者可以先定义自己的 `LOG_TAG`：

```cpp
// system/stack/smp/smp_utils.cc:24
#define LOG_TAG "smp"

// system/udrv/ulinux/uipc.cc:27
#define LOG_TAG "uipc"
```

### ☕ Java 类比

| C/C++ | Java | 说明 |
|-------|------|------|
| `#include <header>` | `import pkg.Class` | C 是文本粘贴，Java 是类引用 |
| `#pragma once` | 无需 | Java 的 import 机制天然防止重复 |
| `#ifndef`/`#define`/`#endif` | 无需 | Java 没有头文件重复包含问题 |
| `#ifndef LOG_TAG`/`#define` | 无直接等价 | Java 中通常用 final 变量或注解 |

Java 的 `import` 不会导致代码重复——它只是告诉编译器去哪里找类。而 C 的 `#include` 是真正的文本复制，所以必须用卫士机制防止重复。

### 📌 本节小结

- `#include` 是文本粘贴，不是模块引用，需要防重复机制
- `#pragma once` 简洁但非标准，新代码推荐使用
- `#ifndef`/`#define`/`#endif` 是标准方式，协议栈老代码大量使用
- 条件性宏定义允许用户在包含前自定义值

---

## 2. 宏定义 (#define)

宏定义是预处理器最核心的功能，在协议栈中无处不在。

### 2.1 对象宏（Object-like Macro）

对象宏是简单的文本替换，用于定义常量：

```cpp
// system/stack/smp/smp_int.h:259-269
#define SMP_PAIR_FLAGS_WE_STARTED_DD       (1)
#define SMP_PAIR_FLAGS_PEER_STARTED_DD     (1 << 1)
#define SMP_PAIR_FLAGS_CMD_CONFIRM_RCVD    (1 << SMP_OPCODE_CONFIRM)  /* 1 << 3 */
#define SMP_PAIR_FLAG_ENC_AFTER_PAIR       (1 << 4)
#define SMP_PAIR_FLAG_HAVE_PEER_DHK_CHK    (1 << 5)
#define SMP_PAIR_FLAG_HAVE_PEER_PUBL_KEY   (1 << 6)
#define SMP_PAIR_FLAG_HAVE_PEER_COMM       (1 << 7)
#define SMP_PAIR_FLAG_HAVE_LOCAL_PUBL_KEY  (1 << 8)
#define SMP_PAIR_FLAGS_CMD_CONFIRM_SENT    (1 << 9)
```

这些是位标志（bit flags），用移位运算定义每个标志位。注意每个值都用括号包裹——这是宏定义的基本安全措施。

```cpp
// system/osi/include/osi.h:26
#define INVALID_FD (-1)

// system/stack/include/bt_types.h:295
#define BT_1SEC_TIMEOUT_MS (1 * 1000)  /* 1 second */
```

### 2.2 函数宏（Function-like Macro）

函数宏接受参数，像函数一样使用，但本质仍是文本替换：

```cpp
// system/stack/sdp/sdp_discovery_db.h:30-31
#define SDP_DISC_ATTR_TYPE(len_type) ((len_type) >> 12)
#define SDP_DISC_ATTR_LEN(len_type)  ((len_type) & SDP_DISC_ATTR_LEN_MASK)
```

使用时：
```cpp
// system/stack/sdp/sdp_utils.cc:89
if (SDP_DISC_ATTR_TYPE(p_attr->attr_len_type) != DATA_ELE_SEQ_DESC_TYPE) {
```

预处理后展开为：
```cpp
if (((p_attr->attr_len_type) >> 12) != DATA_ELE_SEQ_DESC_TYPE) {
```

### 2.3 复杂函数宏：字节流操作

协议栈中最典型的复杂宏是字节流操作系列，用于解析蓝牙数据包：

```cpp
// system/stack/include/bt_types.h:141-145
#define STREAM_TO_UINT8(u8, p)  \
  {                             \
    (u8) = (uint8_t)(*(p));     \
    (p) += 1;                   \
  }

// system/stack/include/bt_types.h:146-149
#define STREAM_TO_UINT16(u16, p)                                    \
  {                                                                 \
    (u16) = ((uint16_t)(*(p)) + (((uint16_t)(*((p) + 1))) << 8));  \
    (p) += 2;                                                       \
  }

// system/stack/include/bt_types.h:157-162
#define STREAM_TO_UINT32(u32, p)                                                       \
  {                                                                                    \
    (u32) = (((uint32_t)(*(p))) + ((((uint32_t)(*((p) + 1)))) << 8) +                  \
             ((((uint32_t)(*((p) + 2)))) << 16) + ((((uint32_t)(*((p) + 3)))) << 24)); \
    (p) += 4;                                                                          \
  }
```

这些宏从字节流 `p` 中读取 8/16/32 位整数，同时移动指针。注意每个参数都用括号包裹——这是宏安全的基本规则。

### 2.4 宏的陷阱

**陷阱 1：无类型检查**

```cpp
#define MAX(a, b) ((a) > (b) ? (a) : (b))

// 传入不同类型，编译器不会警告
int x = MAX(3.14, "hello");  // 编译通过，运行时出错
```

**陷阱 2：参数副作用**

```cpp
#define SQUARE(x) ((x) * (x))

int a = 5;
int result = SQUARE(a++);  // 展开为 ((a++) * (a++))，a 被自增两次！
```

**陷阱 3：缺少括号**

```cpp
#define DOUBLE(x) x + x

int result = DOUBLE(3) * 2;  // 展开为 3 + 3 * 2 = 9，而非 (3+3)*2 = 12
```

### ☕ Java 类比

| C/C++ 宏 | Java 等价 | 说明 |
|----------|----------|------|
| `#define MAX_SIZE 100` | `static final int MAX_SIZE = 100` | Java 用 final 常量 |
| `#define MAX(a,b) ((a)>(b)?(a):(b))` | `static int max(int a, int b)` | Java 用方法，有类型检查 |
| 函数宏 | 无直接等价 | Java 没有文本替换机制 |

Java 没有"宏"这个概念——所有常量用 `final`，所有"函数式替换"用方法。方法有类型检查，没有副作用陷阱。

### 📌 本节小结

- 对象宏定义常量，函数宏模拟函数——但本质都是文本替换
- 宏参数必须用括号包裹：`(param)`，整个表达式也要括号包裹
- 宏没有类型检查，参数可能有副作用，是 C 代码 bug 的常见来源
- 协议栈中大量使用宏做字节流操作，因为宏可以直接操作指针并内联展开

---

## 3. do-while(0) 宏技巧

### 3.1 问题：为什么宏函数要用 do { } while(0) 包裹？

考虑一个简单的宏：

```cpp
// 危险写法：不用 do-while(0)
#define SKIP_BYTE(p) { (p) += 1; }
```

在 if-else 中使用时：

```cpp
if (condition)
    SKIP_BYTE(p);   // 展开为 if (condition) { (p) += 1; }; ← 多了分号
else
    do_something();  // else 变成孤立的，编译错误！
```

展开后：
```cpp
if (condition)
    { (p) += 1; }
;    // 这个分号是空的语句
else // else 没有匹配的 if！
    do_something();
```

### 3.2 解决方案：do-while(0)

`do { ... } while(0)` 保证宏展开后是一个完整的语句，且**需要分号结尾**：

```cpp
// system/stack/include/bt_types.h:198-201
#define STREAM_SKIP_UINT8(p) \
  do {                       \
    (p) += 1;                \
  } while (0)

#define STREAM_SKIP_UINT16(p) \
  do {                        \
    (p) += 2;                 \
  } while (0)

#define STREAM_SKIP_UINT32(p) \
  do {                        \
    (p) += 4;                 \
  } while (0)
```

使用时：
```cpp
// system/stack/btu/btu_hcif.cc:834-838
STREAM_SKIP_UINT8(p);   // tx_interval
STREAM_SKIP_UINT8(p);   // retrans_window
STREAM_SKIP_UINT8(p);   // air_mode
```

在 if-else 中使用：
```cpp
if (condition)
    STREAM_SKIP_UINT8(p);  // 展开为 do { (p) += 1; } while(0); ← 正确！
else
    do_something();
```

### 3.3 更复杂的 do-while(0) 宏

```cpp
// system/stack/avdt/avdt_defs.h:136-141
#define AVDT_MSG_PRS_HDR(p, lbl, pkt, msg) \
  do {                                     \
    (lbl) = (*(p) >> 4) & 0x0F;            \
    (pkt) = (*(p) >> 2) & 0x03;            \
    (msg) = *(p)++ & 0x03;                 \
  } while (0)

// system/stack/avdt/avdt_defs.h:143-149
#define AVDT_MSG_PRS_DISC(p, seid, in_use, type, tsep) \
  do {                                                  \
    (seid) = *(p) >> 2;                                 \
    (in_use) = (*(p)++ >> 1) & 0x01;                    \
    (type) = (*(p) >> 4) & 0x0F;                        \
    (tsep) = *(p)++ >> 3) & 0x01;                       \
  } while (0)
```

这些宏解析 AVDTP 协议包头，一次提取多个字段。`do-while(0)` 确保多条语句作为一个整体使用。

### 3.4 do-while(0) 的另一个用途：提前退出

`do { ... } while(0)` 中的 `break` 可以跳到 `while(0)` 处，实现类似"提前返回"的效果（在宏中不能用 `return`）：

```cpp
#define PARSE_HEADER(p, result)      \
  do {                               \
    if ((p) == nullptr) {            \
      (result) = -1;                 \
      break;                         \
    }                                \
    (result) = *(p)++;               \
  } while (0)
```

### ☕ Java 类比

Java 不需要这个技巧，因为：
- Java 没有"宏函数"，所有代码都是真正的方法调用
- 方法天然就是一个语句块，不存在分号匹配问题
- Java 的 `if-else` 语法不会因为宏展开而断裂

### 📌 本节小结

- `do { ... } while(0)` 是 C 宏的标准包裹技巧
- 它让宏在 if-else 中使用时不会因多余分号而破坏语法
- 协议栈中所有多语句宏都使用此模式
- 记住：看到 `do { ... } while(0)`，就知道这是一个"安全的宏"

---

## 4. 条件编译

条件编译允许根据编译时的条件选择性地包含或排除代码，是 C/C++ 实现"功能裁剪"的核心机制。

### 4.1 基本语法

```cpp
#ifdef  MACRO_NAME    // 如果定义了 MACRO_NAME
#ifndef MACRO_NAME    // 如果未定义 MACRO_NAME
#if defined(A) && defined(B)  // 如果 A 和 B 都定义了
#if VALUE > 10       // 如果 VALUE > 10
#else                // 否则
#elif                // 否则如果
#endif               // 结束条件编译
```

### 4.2 功能裁剪：可配置的常量

```cpp
// system/stack/sdp/sdpint.h:64-68
#ifdef SDP_MAX_ATTR_LEN
#define MAX_ATTR_LEN SDP_MAX_ATTR_LEN
#else
#define MAX_ATTR_LEN 256
#endif
```

如果编译时定义了 `SDP_MAX_ATTR_LEN`，就用用户指定的值；否则使用默认值 256。这允许不同产品根据内存限制调整缓冲区大小。

### 4.3 C/C++ 兼容性：#ifdef __cplusplus

`__cplusplus` 是 C++ 编译器自动定义的宏。利用它可以在同一个头文件中同时支持 C 和 C++ 编译器：

```cpp
// system/types/include/bluetooth/types/ble_address_with_type.h:31-48
#ifdef __cplusplus
inline std::string AddressTypeText(tBLE_ADDR_TYPE type) {
  switch (type) {
    case BLE_ADDR_PUBLIC:
      return std::string("public");
    case BLE_ADDR_RANDOM:
      return std::string("random");
    // ...
    default:
      return std::string("unknown");
  }
}
#endif  // __cplusplus
```

这段代码使用了 `std::string` 和 `inline` 函数——这些是 C++ 特有的，C 编译器无法理解。用 `#ifdef __cplusplus` 包裹后，C 编译器会跳过这段代码。

### 4.4 extern "C" 与 C/C++ 混合链接

当 C++ 代码需要调用 C 编译的库时，必须用 `extern "C"` 告诉 C++ 编译器"这些函数用 C 的命名规则"：

```cpp
// system/stack/include/ldacBT_bco_for_fluoride.h:21-24
#ifdef __cplusplus
#include <cstdint>
extern "C" {
#endif /* __cplusplus */

// ... 函数声明 ...

#ifdef __cplusplus
}
#endif /* __cplusplus */
```

C++ 支持函数重载，编译器会给函数名加上参数类型信息（name mangling）。`extern "C"` 禁止这种修饰，确保链接时能找到 C 库中的函数。

### 4.5 #if defined() 组合条件

```cpp
// 典型模式：多条件组合
#if defined(SMP_CLIENT) && defined(BLE_INCLUDED)
  // SMP 客户端 + BLE 都启用时才编译
#endif
```

### ☕ Java 类比

| C/C++ 条件编译 | Java 等价 | 说明 |
|---------------|----------|------|
| `#ifdef FEATURE` | `if (BuildConfig.FEATURE)` | Java 用运行时判断 |
| `#ifdef __cplusplus` | 无需 | Java 没有多语言混合问题 |
| `extern "C"` | JNI `native` | Java 通过 JNI 调用 C/C++ |
| 功能裁剪 | Gradle build variants | Java 用构建变体，不是源码级裁剪 |

Java 没有条件编译——所有代码都会编译到 class 文件中。功能裁剪通过 Gradle 的 build variants 或运行时检查实现。

### 📌 本节小结

- 条件编译是 C/C++ 实现"编译时功能裁剪"的核心机制
- `#ifdef __cplusplus` 用于 C/C++ 兼容，`extern "C"` 用于混合链接
- 协议栈中大量使用 `#ifdef` 来支持不同芯片和产品的配置
- 条件编译的代码在编译时决定，零运行时开销

---

## 5. 位域 (bit-field)

### 5.1 基本语法

位域允许在结构体中指定每个成员占用的位数，精确控制内存布局：

```cpp
struct Example {
    type field1 : n1;  // field1 占 n1 位
    type field2 : n2;  // field2 占 n2 位
};
```

### 5.2 协议包头中的位域

蓝牙 HCI 数据包头的 16 位中包含多个字段，用位域可以精确映射：

```cpp
// system/stack/include/hcidefs.h:830-836
struct HciDataPreambleBits {
  uint16_t handle : 12;     // 连接句柄，12 位
  uint16_t boundary : 2;    // 包边界标志，2 位
  uint16_t broadcast : 1;   // 广播标志，1 位
  uint16_t unused15 : 1;    // 未使用，1 位
  uint16_t length;           // 有效载荷长度，16 位
};
```

内存布局（前 16 位）：
```
bit 0-11:  handle      (12位)
bit 12-13: boundary    (2位)
bit 14:    broadcast   (1位)
bit 15:    unused15    (1位)
```

这样，访问 `bits.handle` 就能直接获取 12 位的连接句柄，无需手动移位。

### 5.3 AVRCP 协议中的位域

```cpp
// system/packet/avrcp/set_player_application_setting_value.h:49
// （注释中的位域示例）
//     uint8_t subunit_type_ : 5;
//     uint8_t subunit_id_ : 3;
```

AVRCP 命令包头的 8 位被分为 5 位子单元类型和 3 位子单元 ID。

### 5.4 位域的注意事项

**1. 位域的布局依赖编译器**

位域的位序（从高位还是低位开始）由编译器决定。同一份代码在不同平台上可能有不同布局。协议栈代码通常只在特定平台上运行，所以这不是问题。

**2. 位域不能取地址**

```cpp
HciDataPreambleBits bits;
uint16_t* p = &bits.handle;  // 编译错误！位域成员不能取地址
```

**3. 位域的类型应该一致**

同一组位域成员应使用相同的整数类型（如都用 `uint16_t`），避免编译器插入填充位。

### ☕ Java 类比

Java 没有位域语法。要实现相同效果，需要手动移位和掩码：

```java
// C++ 位域方式
// uint16_t handle : 12;
// uint16_t boundary : 2;

// Java 等价方式
int raw;  // 16位原始值
int getHandle()   { return raw & 0x0FFF; }
int getBoundary() { return (raw >> 12) & 0x03; }
```

Java 的做法本质上就是 C 语言不使用位域时的手动移位方式。

### 📌 本节小结

- 位域 `type field : n;` 精确控制结构体成员占用的位数
- 在协议包头解析中，位域可以直接映射硬件/协议定义的位级字段
- 位域不能取地址，布局依赖编译器
- Java 没有位域，需要手动移位和掩码

---

## 6. 联合体 (union)

### 6.1 基本语法

联合体的所有成员共享同一块内存，大小等于最大成员的大小：

```cpp
union Data {
    int i;
    float f;
    char str[4];
};  // 大小 = max(sizeof(int), sizeof(float), sizeof(char[4])) = 4
```

同一时刻只能使用一个成员——写入一个成员后再读另一个成员，结果是未定义的（除非是做类型双关）。

### 6.2 union + 位域：协议包头的位级访问

这是协议栈中最经典的 union 用法——同时提供"按位访问"和"按字访问"两种视图：

```cpp
// system/stack/include/hcidefs.h:830-844
struct HciDataPreambleBits {
  uint16_t handle : 12;
  uint16_t boundary : 2;
  uint16_t broadcast : 1;
  uint16_t unused15 : 1;
  uint16_t length;
};

struct HciDataPreambleRaw {
  uint16_t word0;
  uint16_t word1;
};

union HciDataPreamble {
  HciDataPreambleBits bits;   // 按位域访问
  HciDataPreambleRaw raw;     // 按原始字访问

  void Serialize(uint8_t* data) {
    *data++ = ((raw.word0) & 0xff);
    *data++ = (((raw.word0) >> 8) & 0xff);
    *data++ = ((raw.word1) & 0xff);
    *data++ = ((raw.word1 >> 8) & 0xff);
  }

  bool IsFlushable() const { return bits.boundary == kHCI_FIRST_AUTOMATICALLY_FLUSHABLE; }
  void SetFlushable() { bits.boundary = kHCI_FIRST_AUTOMATICALLY_FLUSHABLE; }
};
```

使用方式：
```cpp
HciDataPreamble preamble;
preamble.raw.word0 = 0x0123;    // 按字写入
uint16_t h = preamble.bits.handle;  // 按位域读取 handle
preamble.bits.boundary = 0x02;     // 修改位域
uint16_t w0 = preamble.raw.word0;  // 再按字读出修改后的值
```

编译器还加了静态断言确保两种视图大小一致：
```cpp
// system/stack/include/hcidefs.h:855
static_assert(sizeof(HciDataPreambleRaw) == sizeof(HciDataPreambleBits));
```

### 6.3 union 作为多态数据容器

在 C 风格代码中，union 常用于在不同类型数据之间复用内存：

```cpp
// system/stack/smp/smp_int.h:249-256
typedef union {
  uint8_t* p_data;           /* uint8_t 类型数据指针 */
  tSMP_KEY key;              /* 密钥信息 */
  tSMP_STATUS status;        /* 状态值 */
  uint32_t passkey;          /* 配对密钥 */
  tSMP_OOB_DATA_TYPE req_oob_type;  /* OOB 数据类型 */
  RawAddress p_bda;          /* 蓝牙地址 */
} tSMP_INT_DATA;
```

这个 union 用于 SMP（安全管理协议）的状态机事件数据——不同事件携带不同类型的数据，但都通过 `tSMP_INT_DATA` 传递。

```cpp
// system/stack/include/gatt_api.h:498-503
typedef union {
  tGATT_VALUE attr_value;  /* READ, HANDLE_VALUE_IND, PREPARE_WRITE */
  uint16_t handle;         /* WRITE, WRITE_BLOB */
} tGATTS_RSP;
```

GATT 服务器响应可能是属性值或句柄，用 union 节省内存。

### 6.4 匿名 union

C++ 允许在结构体中使用匿名 union，其成员可以直接访问：

```cpp
struct Packet {
  int type;
  union {          // 匿名 union
    uint8_t byte_val;
    uint16_t short_val;
    uint32_t int_val;
  };               // 无名
};

Packet p;
p.int_val = 42;    // 直接访问，不需要 p.union_name.int_val
```

### ☕ Java 类比

Java 没有 union。等价做法：

```java
// C++ union 的 Java 等价
class tSMPIntData {
    // 用 Object 模拟 union 的多态
    Object data;  // 可能是 byte[], int, String 等

    // 或者用继承/组合
    byte[] p_data;
    int passkey;
    // 同一时刻只用一个字段
}
```

Java 的类型系统不允许"同一内存多种解读"。如果需要类似功能，通常用继承或 `Object` 引用。

### 📌 本节小结

- union 的所有成员共享内存，大小等于最大成员
- union + 位域 = 协议包头的位级访问利器，同时支持"按字段"和"按原始字节"两种视图
- union 可作为多态数据容器，不同时刻存储不同类型的数据
- Java 没有 union，需要用继承或 Object 引用模拟

---

## 7. typedef 函数指针

### 7.1 语法解析

函数指针的 typedef 语法是 C 语言中最令人困惑的语法之一：

```cpp
typedef return_type (*name)(param_types);
```

拆解步骤：
1. `name` 是新定义的类型名
2. `(*name)` 表示 name 是一个指针
3. `(*name)(param_types)` 表示这个指针指向一个函数
4. `return_type` 是函数的返回类型

```cpp
// system/stack/smp/smp_int.h:363
typedef void (*tSMP_ACT)(tSMP_CB* p_cb, tSMP_INT_DATA* p_data);
```

这定义了 `tSMP_ACT` 类型——一个函数指针，指向的函数接受 `tSMP_CB*` 和 `tSMP_INT_DATA*` 两个参数，返回 `void`。

### 7.2 函数指针作为结构体成员

协议栈中大量使用"函数指针结构体"来实现类似接口的效果：

```cpp
// system/stack/include/security_client_callbacks.h:89-119
typedef struct {
  void (*BTM_Sec_Init)();
  void (*BTM_Sec_Free)();

  bool (*BTM_SecRegister)(const tBTM_APPL_INFO* p_cb_info);

  void (*BTM_BleLoadLocalKeys)(uint8_t key_type, tBTM_BLE_LOCAL_KEYS* p_key);

  void (*BTM_SecAddDevice)(const RawAddress& bd_addr, const DEV_CLASS dev_class,
                           LinkKey link_key, uint8_t key_type, uint8_t pin_length);
  void (*BTM_SecAddBleDevice)(const RawAddress& bd_addr, tBT_DEVICE_TYPE dev_type,
                              tBLE_ADDR_TYPE addr_type);

  bool (*BTM_SecDeleteDevice)(const RawAddress& bd_addr);

  void (*BTM_SecAddBleKey)(const RawAddress& bd_addr, tBTM_LE_KEY_VALUE* p_le_key,
                           tBTM_LE_KEY_TYPE key_type);

  void (*BTM_SecClearSecurityFlags)(const RawAddress& bd_addr);

  tBTM_STATUS (*BTM_SetEncryption)(const RawAddress& bd_addr, tBT_TRANSPORT transport,
                                   tBTM_SEC_CALLBACK* p_callback, void* p_ref_data,
                                   tBTM_BLE_SEC_ACT sec_act);
  // ... 更多函数指针 ...
} tBTM_Sec_Callbacks;
```

这种模式在 C 语言中等价于 Java 的接口——结构体中的函数指针就是"接口方法"。

### 7.3 函数指针数组：状态机实现

```cpp
// system/stack/smp/smp_int.h:363
typedef void (*tSMP_ACT)(tSMP_CB* p_cb, tSMP_INT_DATA* p_data);

// system/stack/smp/smp_main.cc:171
static const tSMP_ACT smp_sm_action[] = {
  smp_proc_sec_req,
  smp_pair_terminate,
  // ... 更多函数 ...
};
```

函数指针数组是 C 语言实现状态机的经典模式——用状态/事件作为数组索引，直接调用对应的处理函数。

### 7.4 回调函数类型定义

```cpp
// system/stack/include/ldacBT_bco_for_fluoride.h:40
typedef void (*decoded_data_callback_t)(uint8_t* buf, uint32_t len);
```

这定义了一个回调类型，用于 LDAC 解码器传递解码后的数据。

### 7.5 语法速查

```cpp
// 无参数函数指针
typedef void (*SimpleCallback)();

// 带参数函数指针
typedef int (*Comparator)(const void* a, const void* b);

// 返回指针的函数指针（注意 * 的位置）
typedef int* (*Factory)(int value);

// 函数指针数组
typedef void (*Handler)(int event);
Handler handlers[10];
```

### ☕ Java 类比

| C/C++ 函数指针 | Java 等价 | 说明 |
|---------------|----------|------|
| `typedef void (*Callback)(int)` | `interface Callback { void call(int); }` | Java 用函数式接口 |
| 函数指针结构体 | 接口实现类 | C 用结构体+函数指针模拟接口 |
| 函数指针数组 | `List<Callback>` | Java 用集合或数组 |
| `callback(args)` | `callback.call(args)` | 调用方式不同 |

Java 8+ 可以用 lambda 简化：
```java
// Java 8+
Callback cb = (value) -> System.out.println(value);
```

### 📌 本节小结

- `typedef return_type (*name)(params)` 定义函数指针类型
- 函数指针结构体 = C 语言的"接口"实现方式
- 函数指针数组是状态机的经典实现模式
- Java 用函数式接口和 lambda 表达式替代函数指针

---

## 8. C风格回调模式

### 8.1 函数指针回调 vs base::Callback

协议栈中存在两种回调模式：

| 模式 | 语法 | 特点 |
|------|------|------|
| C 风格回调 | 函数指针 + `void*` | 老代码，兼容 C |
| C++ 回调 | `base::OnceCallback` / `base::RepeatingCallback` | 新代码，类型安全 |

### 8.2 静态成员函数作为 C 回调

C 风格的回调函数必须是普通函数或静态成员函数（因为 C 不理解 `this` 指针）：

```cpp
// system/stack/eatt/eatt_impl.h:713-719
static void eatt_ind_ack_timeout(void* data) {
  EattChannel* channel = (EattChannel*)data;
  tGATT_TCB* p_tcb = gatt_find_tcb_by_addr(channel->bda_, BT_TRANSPORT_LE);

  log::warn("send ack now");
  attp_send_cl_confirmation_msg(*p_tcb, channel->cid_);
}

static void eatt_ind_confirmation_timeout(void* data) {
  EattChannel* channel = (EattChannel*)data;

  log::warn("disconnecting channel {:#x} for {}", channel->cid_, channel->bda_);
  EattExtension::GetInstance()->Disconnect(channel->bda_, channel->cid_);
}
```

### 8.3 void* user_data 模式

C 回调的标准模式：回调函数接收一个 `void*` 参数，用于传递用户上下文：

```cpp
// 注册回调时传入 this 或相关对象
// system/stack/eatt/eatt_impl.h:756
alarm_set_on_mloop(channel->ind_ack_timer_,
                   GATT_WAIT_FOR_RSP_TIMEOUT_MS,
                   eatt_ind_ack_timeout,
                   (void*)channel);  // 传入 channel 作为 user_data
```

回调被触发时：
```cpp
static void eatt_ind_ack_timeout(void* data) {
  // 从 void* 恢复回具体类型
  EattChannel* channel = (EattChannel*)data;
  // 使用 channel 的成员...
}
```

### 8.4 完整的回调注册与调用流程

```
1. 注册阶段：
   alarm_set_on_mloop(timer, timeout_ms, callback_func, user_data)
                                  ↑                ↑
                              函数指针          void* 上下文

2. 触发阶段（定时器到期）：
   callback_func(user_data)
       ↓
   static void callback_func(void* data) {
       RealType* obj = (RealType*)data;  // 恢复类型
       obj->do_something();               // 调用成员
   }
```

### 8.5 整数与指针的转换宏

有时候需要把小整数作为 `void*` 传递（比如设备 ID），协议栈提供了专用宏：

```cpp
// system/osi/include/osi.h:43-47
#define PTR_TO_UINT(p) ((unsigned int)((uintptr_t)(p)))
#define UINT_TO_PTR(u) ((void*)((uintptr_t)(u)))

#define PTR_TO_INT(p) ((int)((intptr_t)(p)))
#define INT_TO_PTR(i) ((void*)((intptr_t)(i)))
```

使用示例：
```cpp
// system/stack/hid/hidh_conn.cc:293
uint8_t dhandle = PTR_TO_UINT(data);  // void* → uint8_t

// system/stack/hid/hidh_conn.cc:570
alarm_set_on_mloop(..., UINT_TO_PTR(dhandle));  // uint8_t → void*
```

> ⚠️ 这些宏只用于小整数值，不能用于实际指针。注释明确说"should be used sparingly in new code"。

### ☕ Java 类比

| C/C++ 回调 | Java 等价 | 说明 |
|-----------|----------|------|
| 函数指针 + `void*` | 接口 + 实现类 | Java 有类型安全的回调 |
| `static void callback(void* data)` | `interface Listener { void onEvent(); }` | Java 不需要 void* |
| `void*` 传递上下文 | 闭包/lambda 捕获 | Java lambda 自动捕获上下文 |
| `UINT_TO_PTR` | 无需 | Java 有泛型，不需要这种 hack |

Java 的回调天然类型安全，lambda 还能自动捕获上下文，不需要 `void*` 这种"万能指针"。

### 📌 本节小结

- C 风格回调 = 函数指针 + `void*` 上下文，是协议栈老代码的标准模式
- 静态成员函数可以作为 C 回调，普通成员函数不行（有 this 指针）
- `void*` 是 C 语言的"万能容器"，类型安全完全靠程序员保证
- 新代码应优先使用 `base::OnceCallback` 等类型安全的回调机制

---

## 9. C风格类型转换

### 9.1 语法

C 风格类型转换的语法是 `(type)expression`：

```cpp
int x = 42;
double d = (double)x;           // int → double
void* p = (void*)&x;            // int* → void*
uint8_t byte = (uint8_t)d;      // double → uint8_t（截断）
```

### 9.2 协议栈中的典型用法

**1. malloc 返回值的类型转换**

```cpp
// system/stack/eatt/eatt_impl.h:229
BT_HDR* p_buf = (BT_HDR*)osi_malloc(mtu + sizeof(BT_HDR));
```

`osi_malloc` 返回 `void*`，必须转换为具体类型的指针才能使用。

**2. 字节流操作中的类型转换**

```cpp
// system/stack/include/bt_types.h:174
uint8_t* _pa = (uint8_t*)(a) + 15;  // 通用指针转为字节指针

// system/stack/include/bt_types.h:282-285
#define UINT32_TO_BE_FIELD(p, u32)                 \
  {                                                \
    *(uint8_t*)(p) = (uint8_t)((u32) >> 24);       \
    *((uint8_t*)(p) + 1) = (uint8_t)((u32) >> 16); \
    *((uint8_t*)(p) + 2) = (uint8_t)((u32) >> 8);  \
    *((uint8_t*)(p) + 3) = (uint8_t)(u32);         \
  }
```

**3. void* 恢复为具体类型**

```cpp
// system/stack/eatt/eatt_impl.h:714
EattChannel* channel = (EattChannel*)data;  // void* → EattChannel*
```

### 9.3 C++ 风格转换的对比

| C 风格 | C++ 风格 | 用途 |
|--------|---------|------|
| `(Type*)ptr` | `static_cast<Type*>(ptr)` | 相关类型之间的转换 |
| `(Derived*)base_ptr` | `dynamic_cast<Derived*>(base_ptr)` | 多态向下转型（有运行时检查） |
| `(int*)float_ptr` | `reinterpret_cast<int*>(float_ptr)` | 不相关类型之间的重新解释 |
| `(const Type*)ptr` | `const_cast<const Type*>(ptr)` | 添加/移除 const |

在协议栈中，C 风格转换占主导地位，因为：
1. 历史代码量巨大
2. C 风格转换更简洁
3. 很多转换场景（如 `void*` → 具体类型）用 `static_cast` 即可

### 9.4 危险的转换

```cpp
// 危险：截断
uint32_t big = 0x12345678;
uint8_t small = (uint8_t)big;  // small = 0x78，高位被截断

// 危险：未定义行为
float f = 3.14f;
int* pi = (int*)&f;            // 重新解释 float 的位模式为 int
int val = *pi;                  // 未定义行为（但协议栈中经常这样做）
```

### ☕ Java 类比

| C/C++ 类型转换 | Java 等价 | 说明 |
|---------------|----------|------|
| `(int)3.14` | `(int)3.14` | Java 也有基本类型强制转换 |
| `(Derived*)base` | `(Derived)base` | Java 有 instanceof + 强制转换 |
| `(int*)float_ptr` | 无等价 | Java 不允许指针类型重新解释 |
| `(Type*)void_ptr` | 无等价 | Java 有泛型，不需要 void* |

Java 的类型转换比 C 安全得多——不兼容的转换会在编译时或运行时抛出异常。

### 📌 本节小结

- C 风格转换 `(type)expr` 简洁但危险，协议栈中大量使用
- 最常见的场景：`void*` → 具体类型指针、数值类型截断
- C++ 推荐使用 `static_cast`/`reinterpret_cast`/`const_cast`，但协议栈以 C 风格为主
- Java 的类型系统更安全，不兼容转换会直接报错

---

## 10. 结构体指定初始化器

### 10.1 C99 `.field = value` 语法

C99 引入了指定初始化器（Designated Initializers），允许按字段名初始化结构体，而不必按顺序：

```cpp
struct Config {
    int result;
    int mtu;
    int mps;
    int credits;
};

// C99 指定初始化器
struct Config cfg = {
    .result = 0,
    .mtu = 512,
    .mps = 64,
    .credits = 16
};
```

### 10.2 协议栈中的真实示例

```cpp
// system/stack/eatt/eatt_impl.h:163-168
tL2CAP_LE_CFG_INFO local_coc_cfg = {
    .result = tL2CAP_CFG_RESULT::L2CAP_CFG_OK,
    .mtu = eatt_dev->rx_mtu_,
    .mps = eatt_dev->rx_mps_ < max_mps ? eatt_dev->rx_mps_ : max_mps,
    .credits = L2CA_LeCreditDefault(),
};
```

这种写法的优势：
1. **可读性强**：一眼看出每个字段的含义
2. **不怕字段顺序变化**：即使结构体定义中字段顺序调整，初始化仍然正确
3. **可以只初始化部分字段**：未指定的字段自动为零

### 10.3 C++ 的类内初始化

C++11 引入了类内成员初始化器（in-class member initializer）：

```cpp
// system/types/include/bluetooth/types/remote_version.h:25-29
struct tREMOTE_VERSION_INFO {
  uint8_t lmp_version{0};       // C++11 类内初始化
  uint16_t lmp_subversion{0};   // C++11 类内初始化
  uint16_t manufacturer{0};     // C++11 类内初始化
  bool valid{false};            // C++11 类内初始化

  std::string ToString() const {
    return (valid) ? std::format("{:02}-{:05}-{:05}", lmp_version, lmp_subversion, manufacturer)
                   : std::string("UNKNOWN");
  }
};
```

`{0}` 是 C++11 的列表初始化语法，在构造时如果未提供值，就使用这个默认值。

### 10.4 `{0}` 零初始化

```cpp
tL2CAP_LE_CFG_INFO cfg = {0};  // 所有字段初始化为零
```

`{0}` 是 C/C++ 中将整个结构体清零的惯用写法。它比 `memset(&cfg, 0, sizeof(cfg))` 更安全，因为：
- 不会错误地把指针设为非 NULL（某些平台上 NULL 不一定是全零）
- 不会破坏浮点数的零值表示
- 编译器可以做更好的优化

### 10.5 C++20 指定初始化器

C++20 正式支持了指定初始化器（从 C99 借鉴），语法与 C99 相同：

```cpp
// C++20 也支持这种写法
Point p = {.x = 1, .y = 2};
```

但 C++ 的指定初始化器有一些限制：
- 必须按声明顺序初始化
- 不能跳过中间的成员

### ☕ Java 类比

| C/C++ 指定初始化器 | Java 等价 | 说明 |
|-------------------|----------|------|
| `{.mtu = 512, .mps = 64}` | Builder 模式 | Java 用 Builder 链式调用 |
| `uint8_t ver{0}` | `byte ver = 0` | Java 字段声明时直接赋值 |
| `Config cfg = {0}` | `new Config()` | Java 构造器初始化 |

Java 的等价写法：
```java
// Java Builder 模式
Config cfg = new Config.Builder()
    .setResult(0)
    .setMtu(512)
    .setMps(64)
    .setCredits(16)
    .build();
```

### 📌 本节小结

- C99 指定初始化器 `.field = value` 提高可读性，不怕字段顺序变化
- C++11 的类内初始化 `type field{value}` 为成员提供默认值
- `{0}` 是结构体零初始化的惯用写法，比 `memset` 更安全
- C++20 正式支持指定初始化器

---

## 11. C风格内存管理

### 11.1 协议栈的内存管理 API

协议栈封装了自己的内存管理函数，而非直接使用 `malloc`/`free`：

```cpp
// system/stack/eatt/eatt_impl.h:229
BT_HDR* p_buf = (BT_HDR*)osi_malloc(mtu + sizeof(BT_HDR));
p_buf->offset = L2CAP_MIN_OFFSET;
p_buf->len = mtu;
```

```cpp
// system/stack/eatt/eatt_impl.h:516
osi_free(data_p);
```

```cpp
// system/stack/gatt/gatt_sr.cc:173
BT_HDR* p_buf = (BT_HDR*)osi_calloc(len);  // osi_calloc = osi_malloc + memset(0)
```

三个核心函数：

| 函数 | 等价标准库 | 说明 |
|------|----------|------|
| `osi_malloc(size)` | `malloc(size)` | 分配内存，内容未初始化 |
| `osi_calloc(size)` | `calloc(1, size)` | 分配内存，内容清零 |
| `osi_free(ptr)` | `free(ptr)` | 释放内存 |

### 11.2 为什么要封装？

1. **内存追踪**：可以统计分配/释放次数，检测泄漏
2. **分配器切换**：可以在不同场景使用不同的内存分配器
3. **调试支持**：debug 模式下可以添加边界检查和填充标记

### 11.3 alloca 栈上分配

`alloca` 在栈上分配内存，函数返回时自动释放，无需手动 free：

```cpp
// 典型用法（协议栈中较少见，但存在于加密模块）
void process_data(size_t len) {
  uint8_t* temp = (uint8_t*)alloca(len);  // 栈上分配
  // 使用 temp ...
  // 函数返回时自动释放，无需 osi_free
}
```

> ⚠️ `alloca` 有栈溢出风险——如果 `len` 很大，会导致栈溢出崩溃。只用于小量临时内存。

### 11.4 与智能指针的对比

```cpp
// C 风格：手动管理
BT_HDR* p_buf = (BT_HDR*)osi_malloc(size);
// ... 使用 p_buf ...
osi_free(p_buf);           // 必须记得释放！
p_buf = nullptr;           // 防止悬空指针

// C++ 风格：RAII 自动管理
auto p_buf = std::make_unique<BT_HDR>();
// ... 使用 p_buf ...
// 离开作用域自动释放，不会忘记
```

| 特性 | C 风格 (osi_malloc) | C++ 风格 (智能指针) |
|------|---------------------|---------------------|
| 释放方式 | 手动 `osi_free` | 自动（RAII） |
| 内存泄漏风险 | 高 | 极低 |
| 异常安全 | 不安全 | 安全 |
| 所有权明确 | 不明确 | 明确（unique_ptr 独占） |

### ☕ Java 类比

| C/C++ 内存管理 | Java 等价 | 说明 |
|---------------|----------|------|
| `osi_malloc` / `osi_free` | `new` / GC 自动回收 | Java 有垃圾回收，无需手动释放 |
| `osi_calloc` | `new byte[n]`（默认零值） | Java 数组/对象默认初始化为零 |
| `alloca` | 无等价 | Java 所有对象都在堆上 |
| 智能指针 | 无需 | Java GC 自动管理生命周期 |

Java 程序员不需要关心内存释放——这是 GC 的工作。但在 C/C++ 中，忘记 `osi_free` 就会导致内存泄漏。

### 📌 本节小结

- 协议栈使用 `osi_malloc`/`osi_calloc`/`osi_free` 封装内存管理
- `osi_calloc` 分配并清零，`osi_malloc` 只分配不清零
- `alloca` 在栈上分配，自动释放，但有栈溢出风险
- 新代码应优先使用智能指针（`std::unique_ptr`），避免手动管理

---

## 12. 无名枚举与 __attribute__

### 12.1 无名枚举当常量

C 语言中，无名枚举是定义整数常量的传统方式：

```cpp
// system/stack/smp/smp_int.h:204-223
enum {
  SMP_STATE_IDLE,
  SMP_STATE_WAIT_APP_RSP,
  SMP_STATE_SEC_REQ_PENDING,
  SMP_STATE_PAIR_REQ_RSP,
  SMP_STATE_WAIT_CONFIRM,
  SMP_STATE_CONFIRM,
  SMP_STATE_RAND,
  SMP_STATE_PUBLIC_KEY_EXCH,
  SMP_STATE_SEC_CONN_PHS1_START,
  SMP_STATE_WAIT_COMMITMENT,
  SMP_STATE_WAIT_NONCE,
  SMP_STATE_SEC_CONN_PHS2_START,
  SMP_STATE_WAIT_DHK_CHECK,
  SMP_STATE_DHK_CHECK,
  SMP_STATE_ENCRYPTION_PENDING,
  SMP_STATE_BOND_PENDING,
  SMP_STATE_CREATE_LOCAL_SEC_CONN_OOB_DATA,
  SMP_STATE_MAX
};
typedef uint8_t tSMP_STATE;
```

这里无名枚举定义了 SMP 状态机的所有状态常量，`typedef uint8_t tSMP_STATE` 定义了存储这些值的类型。

**为什么用枚举而不是宏？**

| 特性 | `enum` | `#define` |
|------|--------|-----------|
| 调试可见 | ✅ 调试器显示名字 | ❌ 预处理后消失 |
| 类型安全 | ✅ 有类型（enum） | ❌ 纯文本替换 |
| 自动编号 | ✅ 自动递增 | ❌ 手动编号 |
| 作用域 | ⚠️ C 中全局可见 | ⚠️ 全局可见 |

### 12.2 __attribute__((packed)) 紧凑结构体

`__attribute__((packed))` 告诉编译器不要在结构体成员之间插入填充字节：

```cpp
// system/include/hardware/bluetooth.h:64-66
typedef struct {
  uint8_t name[249];
} __attribute__((packed)) bt_bdname_t;
```

```cpp
// system/include/hardware/bt_sock.h:93
} __attribute__((packed)) sock_connect_signal_t;
```

```cpp
// system/stack/acl/btm_acl.cc:124-127
typedef struct {
  uint16_t handle;
  uint16_t hci_len;
} __attribute__((packed)) acl_header_t;
```

**为什么需要 packed？**

默认情况下，编译器会在结构体成员之间插入填充字节以保证对齐。例如：

```cpp
struct WithoutPacked {
    uint8_t a;    // 1 字节
                   // 编译器插入 1 字节填充
    uint16_t b;   // 2 字节
};  // sizeof = 4（而非 3）

struct __attribute__((packed)) WithPacked {
    uint8_t a;    // 1 字节，无填充
    uint16_t b;   // 2 字节
};  // sizeof = 3
```

在协议栈中，`packed` 确保结构体的内存布局与协议定义完全一致，没有多余的字节。

### 12.3 __attribute__((unused)) 抑制未使用警告

```cpp
// system/osi/include/osi.h:24
#define UNUSED_ATTR __attribute__((unused))
```

使用示例：
```cpp
// system/device/src/device_iot_config_int.cc:185
void device_iot_config_write(uint16_t event, UNUSED_ATTR char* p_param) {
  // p_param 未使用，但不产生编译警告
}
```

当一个函数的参数在某些实现中不需要时，用 `UNUSED_ATTR` 标记可以抑制编译器的"未使用参数"警告。这在回调函数中很常见——回调的签名是固定的，但具体实现可能不需要所有参数。

### 12.4 __attribute__((aligned)) 对齐

```cpp
// system/btif/include/btif_common.h:92
char __attribute__((aligned)) p_param[];  /* parameter area needs to be last */
```

`__attribute__((aligned))` 指定变量或结构体字段的对齐方式。不带参数时使用编译器认为最大的对齐值。这在需要确保内存对齐（如 DMA 传输、SIMD 操作）时很重要。

### 12.5 volatile 关键字

`volatile` 告诉编译器该变量可能被外部因素修改，不要优化对它的访问：

```cpp
// 协议栈中 volatile 使用较少，但在嵌入式场景中常见
volatile uint32_t* hardware_register = (volatile uint32_t*)0x40000000;
```

`volatile` 的三个使用场景：
1. **硬件寄存器**：寄存器的值可能被硬件改变
2. **信号处理**：信号处理函数中修改的变量
3. **多线程共享**：不推荐，应使用 `std::atomic`

> ⚠️ `volatile` 不保证原子性，不保证内存序，不适合用于线程同步。多线程场景请使用 `std::atomic`。

### ☕ Java 类比

| C/C++ 特性 | Java 等价 | 说明 |
|-----------|----------|------|
| 无名枚举 | `enum State { IDLE, ACTIVE }` | Java 的 enum 是真正的类 |
| `__attribute__((packed))` | 无需 | Java 没有结构体填充问题 |
| `__attribute__((unused))` | `@SuppressWarnings` | Java 用注解抑制警告 |
| `__attribute__((aligned))` | 无需 | Java 不控制内存布局 |
| `volatile` | `volatile` | 语义不同！Java volatile 保证可见性 |

Java 的 `volatile` 比 C 的 `volatile` 语义更强——Java `volatile` 保证 happens-before 关系（类似 `memory_order_seq_cst`），而 C `volatile` 只禁止编译器优化。

### 📌 本节小结

- 无名枚举是 C 语言定义整数常量的传统方式，比宏更安全
- `__attribute__((packed))` 消除结构体填充，确保内存布局与协议一致
- `__attribute__((unused))` 抑制未使用参数警告，回调函数中常用
- `__attribute__((aligned))` 控制对齐，DMA/SIMD 场景需要
- `volatile` 禁止编译器优化，但不保证线程安全

---

## 常见错误

### ❌ 1. 宏定义缺少括号

```cpp
// 错误
#define DOUBLE(x) x + x
int r = DOUBLE(3) * 2;  // 3 + 3 * 2 = 9

// 正确
#define DOUBLE(x) ((x) + (x))
int r = DOUBLE(3) * 2;  // ((3) + (3)) * 2 = 12
```

### ❌ 2. 宏参数有副作用

```cpp
// 错误
#define MAX(a, b) ((a) > (b) ? (a) : (b))
int r = MAX(x++, y++);  // x 或 y 可能被自增两次

// 正确：先计算，再传给宏
int tmp_x = x++;
int tmp_y = y++;
int r = MAX(tmp_x, tmp_y);
```

### ❌ 3. 多语句宏不用 do-while(0)

```cpp
// 错误
#define SWAP(a, b) { int tmp = a; a = b; b = tmp; }
if (cond) SWAP(x, y); else do_nothing();  // else 变成孤立的

// 正确
#define SWAP(a, b) do { int tmp = a; a = b; b = tmp; } while(0)
```

### ❌ 4. union 的类型双关导致未定义行为

```cpp
// 错误：写入一个成员，读取另一个成员（C 中是 UB，C++ 中也是）
union { float f; uint32_t i; } u;
u.f = 3.14f;
uint32_t bits = u.i;  // 未定义行为！

// 正确：使用 memcpy（编译器会优化为相同代码）
float f = 3.14f;
uint32_t bits;
memcpy(&bits, &f, sizeof(bits));
```

### ❌ 5. 忘记释放 osi_malloc 分配的内存

```cpp
// 错误：内存泄漏
void process() {
    BT_HDR* p_buf = (BT_HDR*)osi_malloc(size);
    if (error) return;  // 忘记 osi_free！
    // ...
    osi_free(p_buf);
}

// 正确：每个退出路径都要释放
void process() {
    BT_HDR* p_buf = (BT_HDR*)osi_malloc(size);
    if (error) {
        osi_free(p_buf);  // 提前退出也要释放
        return;
    }
    // ...
    osi_free(p_buf);
}
```

### ❌ 6. C 风格转换掩盖错误

```cpp
// 危险：C 风格转换可能做了意料之外的转换
const int* pci = &value;
int* pi = (int*)pci;  // 移除了 const！编译器不会警告

// 安全：C++ 风格转换会明确意图
int* pi2 = const_cast<int*>(pci);  // 明确表示要移除 const
```

### ❌ 7. 位域跨平台布局不一致

```cpp
// 危险：位域的位序依赖编译器
struct Flags {
    uint8_t a : 1;  // 是最高位还是最低位？取决于编译器！
    uint8_t b : 7;
};

// 安全：用显式移位和掩码
uint8_t raw;
bool a = raw & 0x01;
uint8_t b = (raw >> 1) & 0x7F;
```

---

## 速查卡

### 预处理器

| 指令 | 用途 | 示例 |
|------|------|------|
| `#include` | 文本包含 | `#include "smp_int.h"` |
| `#pragma once` | 防重复包含 | `#pragma once` |
| `#ifndef`/`#define`/`#endif` | 头文件卫士 | `#ifndef SMP_INT_H` ... `#endif` |
| `#ifdef`/`#ifndef` | 条件编译 | `#ifdef SDP_MAX_ATTR_LEN` |
| `#if defined(A)` | 组合条件 | `#if defined(A) && defined(B)` |
| `#define NAME value` | 对象宏 | `#define INVALID_FD (-1)` |
| `#define F(x)` | 函数宏 | `#define SDP_DISC_ATTR_TYPE(t) ((t) >> 12)` |

### 类型特性

| 特性 | 语法 | 用途 |
|------|------|------|
| 位域 | `uint16_t field : 12;` | 精确控制位数 |
| 联合体 | `union { A a; B b; };` | 共享内存/多态数据 |
| union+位域 | `union { Bits b; Raw r; };` | 按位/按字双视图 |
| 函数指针 | `typedef void (*Fn)(int);` | 回调/状态机 |
| 指定初始化器 | `{.field = value}` | 按名初始化结构体 |
| 无名枚举 | `enum { A, B, C };` | 定义整数常量 |

### __attribute__

| 属性 | 语法 | 用途 |
|------|------|------|
| packed | `__attribute__((packed))` | 消除结构体填充 |
| unused | `__attribute__((unused))` | 抑制未使用警告 |
| aligned | `__attribute__((aligned))` | 指定对齐方式 |

### 内存管理

| 函数 | 说明 | 等价标准库 |
|------|------|----------|
| `osi_malloc(size)` | 分配内存 | `malloc` |
| `osi_calloc(size)` | 分配并清零 | `calloc` |
| `osi_free(ptr)` | 释放内存 | `free` |
| `alloca(size)` | 栈上分配 | 无标准等价 |

### 宏技巧

| 模式 | 语法 | 用途 |
|------|------|------|
| do-while(0) | `do { ... } while(0)` | 多语句宏安全包裹 |
| 条件定义 | `#ifndef X` / `#define X` | 允许用户自定义 |
| 指针转换 | `PTR_TO_UINT(p)` / `UINT_TO_PTR(u)` | 整数↔指针安全转换 |
| 数组大小 | `ARRAY_SIZE(x)` | 计算数组元素数 |

### C vs C++ vs Java 对比

| 特性 | C | C++ | Java |
|------|---|-----|------|
| 常量定义 | `#define` / `enum` | `constexpr` / `enum` | `static final` / `enum` |
| 回调 | 函数指针 + `void*` | `std::function` / `base::Callback` | 函数式接口 / lambda |
| 内存管理 | `malloc`/`free` | 智能指针 / RAII | GC 自动回收 |
| 类型转换 | `(Type)expr` | `static_cast<>` 等 | `(Type) expr` + 运行时检查 |
| 多态 | 函数指针结构体 | 虚函数 / 模板 | 接口 / 继承 |
| 防重复包含 | `#pragma once` / 卫士 | 同 C | 无需 |
