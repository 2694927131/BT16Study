# C++ 蓝牙协议栈教材 - 任务进度跟踪

> 生成时间: 2026-05-19
> 目标: 基于Android 16蓝牙协议栈(system/)代码，生成面向C++初学者的详细教材

---

## 教材清单与进度

| 编号 | 教材名称 | 文件名 | 优先级 | 状态 | 完成时间 |
|------|---------|--------|--------|------|---------|
| 01 | C++基础语法回顾 | 01_cpp_basics.md | 高 | ✅ 已完成 | 2026-05-19 |
| 02 | 类与对象 | 02_class_and_object.md | 高 | ✅ 已完成 | 2026-05-19 |
| 03 | 继承与多态 | 03_inheritance_and_polymorphism.md | 高 | ✅ 已完成 | 2026-05-19 |
| 04 | 模板与泛型编程 | 04_templates.md | 高 | ✅ 已完成 | 2026-05-19 |
| 05 | 智能指针与内存管理 | 05_smart_pointers.md | 高 | ✅ 已完成 | 2026-05-19 |
| 06 | 现代C++特性 | 06_modern_cpp_features.md | 高 | ✅ 已完成 | 2026-05-19 |
| 07 | Lambda表达式与函数式编程 | 07_lambda_and_functional.md | 高 | ✅ 已完成 | 2026-05-19 |
| 08 | 移动语义与完美转发 | 08_move_semantics.md | 高 | ✅ 已完成 | 2026-05-19 |
| 09 | STL容器与算法 | 09_stl_containers_and_algorithms.md | 高 | ✅ 已完成 | 2026-05-19 |
| 10 | 命名空间与类型别名 | 10_namespaces_and_aliases.md | 中 | ✅ 已完成 | 2026-05-19 |
| 11 | 运算符重载与friend | 11_operator_overloading_and_friend.md | 中 | ✅ 已完成 | 2026-05-19 |
| 12 | 并发与线程安全 | 12_concurrency.md | 中 | ✅ 已完成 | 2026-05-19 |
| 13 | 类型特征与元编程 | 13_type_traits.md | 中 | ✅ 已完成 | 2026-05-19 |
| 14 | Chromium基础库 | 14_chromium_base.md | 高 | ✅ 已完成 | 2026-05-19 |
| 15 | 如何阅读与导航蓝牙协议栈代码 | 15_reading_bt_stack.md | 高 | ✅ 已完成 | 2026-05-19 |

---

## 状态说明

- ⬜ 未开始
- 🔄 进行中
- ✅ 已完成

---

## 协议栈代码关键参考文件索引

| C++ 模式 | 代表性文件 |
|----------|-----------|
| 类继承 + override | `system/stack/l2cap/l2c_api.h`, `system/gd/hci/hci_layer.h` |
| 纯虚接口 | `system/gd/hci/controller.h`, `system/stack/include/l2cap_interface.h` |
| 模板类 | `system/gd/common/bidi_queue.h`, `system/gd/os/queue.h`, `system/gd/common/lru_cache.h` |
| SFINAE + enable_if | `system/gd/storage/mutation_entry.h` |
| CRTP | `system/gd/storage/serializable.h` |
| enum class | `system/stack/eatt/eatt.h`, `system/stack/include/btm_status.h` |
| constexpr | `system/types/include/bluetooth/types/uuid.h`, `system/gd/hci/controller.h` |
| Lambda | `system/stack/eatt/eatt_impl.h`, `system/gd/os/handler.h` |
| std::move | `system/stack/hcic/hciblecmds.cc`, `system/gd/storage/mutation_entry.h` |
| = delete / = default | `system/stack/eatt/eatt.h`, `system/gd/hci/hci_layer.h` |
| Pimpl | `system/stack/eatt/eatt.h`, `system/stack/include/btm_iso_api.h` |
| 智能指针 | `system/stack/eatt/eatt_impl.h`, `system/gd/os/queue.h` |
| std::optional | `system/types/include/bluetooth/types/address.h`, `system/gd/storage/device.h` |
| std::variant | `system/include/hardware/bt_vc.h` |
| static_assert | `system/types/src/uuid.cc`, `system/types/src/address.cc` |
| if constexpr | `system/main/shim/acl.cc`, `system/gd/hci/le_address_manager.cc` |
| 类型特征 | `system/gd/storage/mutation_entry.h`, `system/main/shim/acl.cc` |
| 线程同步 | `system/stack/connection_manager/connection_manager.cc`, `system/gd/os/handler.h` |
| [[nodiscard]] | `system/stack/l2cap/l2cap_api.cc`, `system/stack/rnr/remote_name_request.h` |
| WeakPtr | `system/stack/eatt/eatt_impl.h`, `system/profile/avrcp/device.h` |
| base::Callback/Bind | `system/stack/include/btm_ble_api.h`, `system/stack/hcic/hciblecmds.cc` |
| 运算符重载 | `system/types/include/bluetooth/types/uuid.h` |
| friend | `system/stack/acl/acl.h`, `system/profile/avrcp/device.h` |
| std::hash 特化 | `system/types/include/bluetooth/types/uuid.h`, `system/types/include/bluetooth/types/address.h` |
| std::chrono | `system/gd/os/handler.h`, `system/main/shim/stack.cc` |
| std::promise/future | `system/main/shim/stack.cc`, `system/main/shim/acl_api.cc` |

---

## 推荐阅读顺序

### 基础阶段（入门）
| 顺序 | 编号 | 教材名称 | 核心内容 |
|------|------|---------|---------|
| 1 | 01 | C++基础语法回顾 | 变量、类型、引用、指针、const、static |
| 2 | 02 | 类与对象 | 构造、析构、成员函数、访问控制、final |
| 3 | 03 | 继承与多态 | 虚函数、override、纯虚接口、多继承 |
| 4 | 10 | 命名空间与类型别名 | namespace、using、typedef |

### 进阶阶段（核心）
| 顺序 | 编号 | 教材名称 | 核心内容 |
|------|------|---------|---------|
| 5 | 05 | 智能指针与内存管理 | unique_ptr/shared_ptr/Pimpl惯用法 |
| 6 | 06 | 现代C++特性 | enum class/constexpr/auto/optional/variant |
| 7 | 07 | Lambda表达式与函数式编程 | 捕获列表、STL算法结合 |
| 8 | 09 | STL容器与算法 | vector/map/queue/optional/priority_queue |

### 高级阶段（应用）
| 顺序 | 编号 | 教材名称 | 核心内容 |
|------|------|---------|---------|
| 9 | 14 | Chromium基础库 | base::Callback/BindOnce/WeakPtr/Unretained |
| 10 | 08 | 移动语义与完美转发 | std::move/std::forward/RVO |
| 11 | 11 | 运算符重载与friend | operator重载、hash特化、formatter |

### 实战阶段（协议栈）
| 顺序 | 编号 | 教材名称 | 核心内容 |
|------|------|---------|---------|
| 12 | 12 | 并发与线程安全 | mutex/atomic/promise/future/Handler |
| 13 | 13 | 类型特征与元编程 | is_integral/enable_if/if constexpr |
| 14 | 04 | 模板与泛型编程 | 模板类/SFINAE/CRTP |
| 15 | 15 | 如何阅读与导航蓝牙协议栈代码 | 整体架构、代码风格、调试技巧 |

### 快速上手路径
推荐按顺序学习，按此顺序可最快上手协议栈代码：
```
01→02→03→05→06→07→09→14→15→12→13→04→08→10→11
```

---

## 文档质量标准（V2）

### 基本要求
1. **真实代码示例**：每个C++语法点必须有来自蓝牙协议栈的真实代码示例，标注来源文件和行号
2. **通俗易懂**：讲解语言适合C++初学者，避免过度学术化
3. **结构清晰**：每个文档有目录、章节标题、代码块、总结
4. **练习思考题**：每个主要章节末尾附思考题

### Java 类比要求（V2新增）
5. **Java类比讲解**：每个C++语法点必须附带Java类比对照，帮助有Java基础的开发者快速理解：
   - 在每个主要语法点下添加 `☕ Java 类比` 小节
   - 格式：用对比表格或并列代码块展示C++与Java的异同
   - 重点说明：C++有而Java没有的特性（如指针、多继承、运算符重载等）
   - 重点说明：Java有而C++用法不同的特性（如接口vs纯虚类、泛型vs模板等）
   - 对于C++独有的特性（如移动语义、RAII等），说明Java为什么不需要以及Java的替代方案

### Java 类比对照速查表

| C++ 概念 | Java 类比 | 关键差异 |
|----------|----------|---------|
| `class` | `class` | C++有析构函数，Java有finalize/try-with-resources |
| `virtual` 函数 | 普通方法 | Java所有非final方法默认虚函数，C++需显式virtual |
| 纯虚类 `=0` | `interface` | C++纯虚类可有成员变量，Java接口不能(Java8+可有default) |
| `override` | `@Override` | 功能相同，编译期检查 |
| `const` 成员函数 | 无直接等价 | Java无const方法概念，只能通过设计约束 |
| `constexpr` | 无直接等价 | Java无编译期常量表达式计算 |
| `enum class` | `enum` | C++强类型枚举更严格，Java枚举是类 |
| `namespace` | `package` | C++可嵌套、可别名，Java与目录结构绑定 |
| `using`/`typedef` | 无直接等价 | Java无类型别名，可用继承或包装类模拟 |
| `std::unique_ptr` | 无直接等价 | Java有GC，不需要独占指针 |
| `std::shared_ptr` | 无直接等价 | Java引用类似shared_ptr但由GC管理 |
| `std::weak_ptr` | `WeakReference<T>` | 概念相同，用途相同 |
| `template` | 泛型 `<T>` | C++模板是代码生成，Java泛型是类型擦除 |
| `std::move` | 无直接等价 | Java所有对象都是引用，无需移动语义 |
| `operator<<` | `toString()` | Java用toString()，C++用流插入运算符 |
| `friend` | 无直接等价 | Java无友元，可用包访问或内部类模拟 |
| `std::optional` | `Optional<T>` | 概念相同，Java的Optional是引用类型 |
| `std::variant` | 无直接等价 | Java可用继承体系或Object模拟 |
| `std::mutex` | `synchronized`/`ReentrantLock` | 概念相同，C++更底层 |
| `std::atomic` | `AtomicInteger`等 | 概念相同 |
| `std::promise/future` | `CompletableFuture` | 概念相似 |
| Lambda `[=](x){}` | Lambda `(x) -> {}` | C++需指定捕获方式，Java自动捕获有效final变量 |
| `base::Callback` | `Consumer<T>`/`Function<T,R>` | 概念相似，Chromium回调更注重一次性语义 |
| `base::WeakPtr` | `WeakReference<T>` | 概念相同，用途相同(防止悬空引用) |
| `static_assert` | 无直接等价 | Java无编译期断言，可用注解处理器实现 |
| `if constexpr` | 无直接等价 | Java泛型无编译期条件分支 |
| `=delete` | `private`构造函数 | Java用private构造禁止实例化 |
| Pimpl | 无直接等价 | Java天然隔离(不同文件)，不需要Pimpl |
| RAII | try-with-resources | C++用析构函数，Java用AutoCloseable |
| 指针 `*`/`->` | 无直接等价 | Java只有引用，无指针运算 |
| 引用 `&` | 引用(默认) | Java所有对象变量都是引用 |
| `#include` | `import` | C++是文本包含，Java是模块引用 |
| `#pragma once` | 无需 | Java的import机制天然防止重复 |

### 优化状态

| 编号 | 教材名称 | V1完成 | V2(Java类比) | V3(小结+速查卡+关联) |
|------|---------|--------|-------------|---------------------|
| 01 | C++基础语法回顾 | ✅ | ✅ | ✅ |
| 02 | 类与对象 | ✅ | ✅ | ✅ |
| 03 | 继承与多态 | ✅ | ✅ | ✅ |
| 04 | 模板与泛型编程 | ✅ | ✅ | ✅ |
| 05 | 智能指针与内存管理 | ✅ | ✅ | ✅ |
| 06 | 现代C++特性 | ✅ | ✅ | ✅ |
| 07 | Lambda表达式与函数式编程 | ✅ | ✅ | ✅ |
| 08 | 移动语义与完美转发 | ✅ | ✅ | ✅ |
| 09 | STL容器与算法 | ✅ | ✅ | ✅ |
| 10 | 命名空间与类型别名 | ✅ | ✅ | ✅ |
| 11 | 运算符重载与friend | ✅ | ✅ | ✅ |
| 12 | 并发与线程安全 | ✅ | ✅ | ✅ |
| 13 | 类型特征与元编程 | ✅ | ✅ | ✅ |
| 14 | Chromium基础库 | ✅ | ✅ | ✅ |
| 15 | 如何阅读与导航蓝牙协议栈代码 | ✅ | ✅ | ✅ |

---

## 文档质量标准（V3）

### V1-V2 要求（继续生效）
1. 真实代码示例，标注来源文件和行号
2. 通俗易懂，适合C++初学者
3. 结构清晰：目录、章节标题、代码块
4. 练习思考题
5. ☕ Java 类比小节（V2）

### V3 新增要求

6. **章节小结**：每个主要章节末尾添加 `📌 本节小结` 小节，用3-5个要点总结该章核心内容，方便快速回顾
7. **速查卡**：每个文档末尾添加 `## 速查卡` 章节，用表格形式列出该文档所有关键语法的一行速查，格式：`语法 | 用途 | 示例 | Java类比`
8. **关联教材**：每个文档开头（目录之后）添加 `> 📎 关联教材：xx, xx, xx` 行，标注与本篇内容相关的其他教材编号，方便交叉参考
9. **常见错误**：在速查卡之前添加 `## 常见错误` 章节，列出3-5个初学者在该主题上最容易犯的错误及修正方法
