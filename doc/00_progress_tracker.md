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

### 快速上手路径（推荐按顺序学习，按此顺序可最快上手协议栈代码：
```
01→02→03→05→06→07→09→14→15→12→13→04→08→10→11
```
