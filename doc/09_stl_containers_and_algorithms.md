# STL 容器与算法 —— 数据组织的标准武器库

> **基于 Android 蓝牙协议栈 (Fluoride) 真实代码的 C++ 教材**
>
> 目标读者：了解基本 C++ 语法但不熟悉 STL 的初学者

---

## 目录

1. [std::array — 固定大小数组](#1-stdarray--固定大小数组)
2. [std::vector — 动态数组](#2-stdvector--动态数组)
3. [std::map — 有序映射](#3-stdmap--有序映射)
4. [std::unordered_map — 哈希映射](#4-stdunordered_map--哈希映射)
5. [std::set — 有序集合](#5-stdset--有序集合)
6. [std::deque — 双端队列](#6-stddeque--双端队列)
7. [std::queue — 队列](#7-stdqueue--队列)
8. [std::priority_queue — 优先队列](#8-stdpriority_queue--优先队列)
9. [std::pair — 值对](#9-stdpair--值对)
10. [std::optional — 可能不存在的值 (C++17)](#10-stdoptional--可能不存在的值-c17)
11. [std::variant — 类型安全的联合体 (C++17)](#11-stdvariant--类型安全的联合体-c17)
12. [STL 算法](#12-stl-算法)
13. [容器选择指南](#13-容器选择指南)

---

## 1. std::array — 固定大小数组

### 1.1 什么是 std::array

`std::array` 是 C++11 引入的**固定大小**数组容器。它封装了 C 风格数组，提供了更安全的接口，同时**零开销**——不占用额外内存。

```
std::array<元素类型, 元素个数>
```

### 1.2 与 C 数组的区别

| 特性 | C 数组 `int arr[5]` | `std::array<int, 5>` |
|------|---------------------|----------------------|
| 获取大小 | 需要手动计算 `sizeof(arr)/sizeof(arr[0])` | `arr.size()` 直接获取 |
| 赋值 | 不支持 `arr2 = arr1` | 支持 `arr2 = arr1` |
| 边界检查 | `[]` 无检查 | `at()` 有边界检查 |
| 作为函数参数 | 退化为指针，丢失长度信息 | 保留完整类型信息 |
| 与 STL 算法配合 | 需要手动传首尾指针 | 直接用 `begin()`/`end()` |

### 1.3 初始化与访问

```cpp
#include <array>

// 初始化方式
std::array<int, 5> a1 = {1, 2, 3, 4, 5};       // 列表初始化
std::array<int, 5> a2 = {};                       // 全部初始化为 0
std::array<int, 5> a3;                            // 未初始化（值不确定！）

// 访问元素
int x = a1[0];           // 下标访问，无边界检查
int y = a1.at(0);        // at() 访问，越界抛出 std::out_of_range
int f = a1.front();      // 首元素
int b = a1.back();       // 尾元素

// 获取信息
size_t n = a1.size();    // 元素个数：5
bool empty = a1.empty(); // 是否为空：false（固定大小数组永远不为空）

// 遍历
for (const auto& elem : a1) {
    std::cout << elem << " ";
}

// 填充
a1.fill(0);              // 将所有元素设为 0
```

### 1.4 蓝牙协议栈中的真实示例

在蓝牙协议栈中，很多协议数据单元（PDU）的地址和标识符都是**固定长度**的字节序列，非常适合用 `std::array` 表示：

```cpp
// system/types/include/bluetooth/types/uuid.h:46
// UUID 是 128 位（16 字节）的标识符，长度固定
using UUID128Bit = std::array<uint8_t, kNumBytes128>;  // std::array<uint8_t, 16>
```

```cpp
// system/types/include/bluetooth/types/address.h:31
// 蓝牙设备地址（MAC 地址）固定 6 字节
std::array<uint8_t, 6> address;
```

**为什么用 `std::array` 而不是 C 数组或 `std::vector`？**

- 比 C 数组更安全：支持赋值、知道自身大小、可与 STL 算法无缝配合
- 比 `std::vector` 更高效：没有堆分配开销，大小编译期确定
- 语义清晰：`std::array<uint8_t, 6>` 一眼就能看出"6 字节的固定序列"

### 1.5 小贴士

> `std::array` 的大小是模板参数，编译期确定。如果你需要运行时动态改变大小，请用 `std::vector`。

---

## 2. std::vector — 动态数组

### 2.1 什么是 std::vector

`std::vector` 是最常用的 STL 容器，是一个**能自动扩容**的动态数组。它在内存中连续存储元素，支持随机访问，尾部插入/删除高效。

```
std::vector<元素类型>
```

### 2.2 常用操作

```cpp
#include <vector>

// 创建
std::vector<int> v1;                    // 空向量
std::vector<int> v2 = {1, 2, 3};        // 列表初始化
std::vector<int> v3(10);                // 10 个元素，默认值 0
std::vector<int> v4(10, 42);            // 10 个元素，全部为 42

// 添加元素
v1.push_back(10);       // 在末尾添加元素（拷贝）
v1.emplace_back(20);    // 在末尾原地构造元素（更高效，推荐）

// 删除元素
v1.pop_back();          // 删除末尾元素
v1.clear();             // 清空所有元素

// 访问
int x = v2[0];          // 下标访问
int y = v2.at(0);       // 带边界检查的访问

// 大小信息
size_t n = v2.size();   // 元素个数
bool empty = v2.empty();// 是否为空
size_t c = v2.capacity();// 已分配的容量（≥ size）

// 遍历
for (size_t i = 0; i < v2.size(); i++) {
    std::cout << v2[i] << " ";
}

// 范围 for 遍历（推荐）
for (const auto& elem : v2) {
    std::cout << elem << " ";
}

// 迭代器遍历
for (auto it = v2.begin(); it != v2.end(); ++it) {
    std::cout << *it << " ";
}
```

### 2.3 push_back vs emplace_back

```cpp
class Device {
public:
    Device(RawAddress addr, uint16_t mtu) : addr_(addr), mtu_(mtu) {}
private:
    RawAddress addr_;
    uint16_t mtu_;
};

std::vector<Device> devices;

// push_back：先构造临时对象，再移动/拷贝到 vector 中
devices.push_back(Device(bd_addr, 64));

// emplace_back：直接在 vector 的内存中原地构造，省去移动/拷贝
devices.emplace_back(bd_addr, 64);   // 推荐！更高效
```

> **经验法则**：当添加的元素类型与容器元素类型相同时，优先使用 `emplace_back`。

### 2.4 蓝牙协议栈中的真实示例

**示例 1：EATT 设备列表**

EATT（Enhanced ATT）是蓝牙 5.2 引入的增强属性协议。协议栈用一个 `vector` 管理所有已连接的 EATT 设备：

```cpp
// system/stack/eatt/eatt_impl.h:66
std::vector<eatt_device> devices_;
```

当新设备连接时，将其添加到列表：

```cpp
// system/stack/eatt/eatt_impl.h:531
devices_.push_back(eatt_device(bd_addr, default_mtu_, max_mps_));
```

**示例 2：L2CAP 连接返回的 CID 列表**

L2CAP（逻辑链路控制和适配协议）建立 EATT 通道时，会返回一组 CID（Channel ID）：

```cpp
// system/stack/eatt/eatt_impl.h:564-566
std::vector<uint16_t> connecting_cids =
    stack::l2cap::get_interface().L2CA_ConnectCreditBasedReq(
        psm, bd_addr, &eatt_inst->eatt_cb_info_, channels_to_open);
```

这里 `vector` 特别合适，因为：
- 连接可能建立 1 个或多个通道，数量运行时才确定
- 需要遍历所有 CID 进行后续处理
- 只在尾部添加，不需要在中间插入

### 2.5 小贴士

> `vector` 在尾部操作是 O(1)，但在中间插入/删除是 O(n)。如果你的操作主要在两端进行，考虑用 `std::deque`。

---

## 3. std::map — 有序映射

### 3.1 什么是 std::map

`std::map` 是**有序的键值对**容器，基于红黑树实现。每个键唯一，按键自动排序，查找/插入/删除都是 O(log n)。

```
std::map<键类型, 值类型>
```

### 3.2 常用操作

```cpp
#include <map>

// 创建
std::map<std::string, int> scores;

// 插入
scores.insert({"Alice", 95});          // insert + 花括号初始化
scores.insert(std::make_pair("Bob", 87)); // insert + make_pair
scores["Charlie"] = 72;                // [] 操作符（键不存在则创建）

// 查找
auto it = scores.find("Alice");        // 返回迭代器
if (it != scores.end()) {
    std::cout << it->first << ": " << it->second << "\n";  // Alice: 95
}

// [] 操作符：键存在则返回值，不存在则插入默认值
int val = scores["Alice"];             // 95
int val2 = scores["David"];            // 0（David 不存在，自动插入，值为 0）

// 删除
scores.erase("Bob");                   // 按键删除
scores.erase(it);                      // 按迭代器删除

// 大小
size_t n = scores.size();
bool empty = scores.empty();

// 遍历（按键的升序）
for (const auto& [key, value] : scores) {   // C++17 结构化绑定
    std::cout << key << ": " << value << "\n";
}

// C++11 遍历方式
for (const std::pair<const std::string, int>& p : scores) {
    std::cout << p.first << ": " << p.second << "\n";
}
```

### 3.3 [] 操作符的陷阱

```cpp
std::map<int, std::shared_ptr<Channel>> channels;

// 危险！如果 5 不存在，会插入一个 nullptr
auto ch = channels[5];   // ch 可能是 nullptr

// 安全做法：先 find
auto it = channels.find(5);
if (it != channels.end()) {
    auto ch = it->second;   // 确实存在的通道
}
```

> **经验法则**：如果你只想查询不想插入，用 `find()` 而不是 `[]`。

### 3.4 蓝牙协议栈中的真实示例

**示例 1：EATT 通道映射**

EATT 用 `map` 将 L2CAP 通道 ID（CID）映射到对应的 EATT 通道对象：

```cpp
// system/stack/eatt/eatt_impl.h:57
std::map<uint16_t, std::shared_ptr<EattChannel>> eatt_channels;
```

**查找通道**——收到数据时，根据 CID 找到对应的通道：

```cpp
// system/stack/eatt/eatt_impl.h:99
auto it = eatt_dev->eatt_channels.find(lcid);
```

**访问通道**——确认存在后用 `[]` 获取：

```cpp
// system/stack/eatt/eatt_impl.h:123
auto channel = eatt_dev->eatt_channels[lcid];
```

**删除通道**——通道关闭时移除映射：

```cpp
// system/stack/eatt/eatt_impl.h:129
eatt_dev->eatt_channels.erase(lcid);
```

**插入通道**——新通道建立时添加映射：

```cpp
// system/stack/eatt/eatt_impl.h:188
eatt_dev->eatt_channels.insert({cid, chan});
```

**遍历所有通道**：

```cpp
// system/stack/eatt/eatt_impl.h:104
for (const std::pair<uint16_t, std::shared_ptr<EattChannel>> el : eatt_dev->eatt_channels) {
    // el.first  是 CID
    // el.second 是 EattChannel 的 shared_ptr
}
```

**示例 2：后台连接管理**

连接管理器用 `map` 记录每个设备的后台连接状态：

```cpp
// system/stack/connection_manager/connection_manager.cc:107
std::map<RawAddress, tAPPS_CONNECTING> bgconn_dev;
```

这里 `RawAddress` 是蓝牙设备地址，作为键；`tAPPS_CONNECTING` 记录哪些应用正在等待连接该设备。

### 3.5 小贴士

> `std::map` 的键会自动排序。如果你不需要排序，只需要快速查找，用 `std::unordered_map` 可以获得更好的性能。

---

## 4. std::unordered_map — 哈希映射

### 4.1 什么是 std::unordered_map

`std::unordered_map` 是基于**哈希表**的键值对容器。查找/插入/删除平均 O(1)，最坏 O(n)。键**无序**存储。

```
std::unordered_map<键类型, 值类型>
```

### 4.2 与 std::map 的区别

| 特性 | `std::map` | `std::unordered_map` |
|------|-----------|---------------------|
| 底层实现 | 红黑树 | 哈希表 |
| 查找复杂度 | O(log n) | 平均 O(1)，最坏 O(n) |
| 键的顺序 | 有序（升序） | 无序 |
| 对键的要求 | 支持 `<` 比较 | 支持 `==` 比较 + `std::hash` 特化 |
| 内存开销 | 每节点 3 指针 | 哈希桶 + 链表 |
| 适用场景 | 需要遍历有序键 | 只需快速查找 |

### 4.3 std::hash 特化

`unordered_map` 需要哈希函数来计算键的存储位置。对于 `int`、`std::string` 等标准类型，STL 已经提供了 `std::hash` 特化。但对于**自定义类型**，你需要自己提供。

在蓝牙协议栈中，`RawAddress` 和 `Uuid` 是自定义类型，需要特化 `std::hash` 才能用作 `unordered_map` 的键：

```cpp
// 为 RawAddress 提供 hash 特化
namespace std {
template <>
struct hash<RawAddress> {
    size_t operator()(const RawAddress& addr) const {
        // 将 6 字节地址组合成一个 size_t 作为哈希值
        size_t h = 0;
        for (int i = 0; i < 6; i++) {
            h = h * 31 + addr.address[i];
        }
        return h;
    }
};
}  // namespace std

// 现在可以用了！
std::unordered_map<RawAddress, DeviceInfo> device_map;
```

```cpp
// 为 Uuid 提供 hash 特化（类似原理）
namespace std {
template <>
struct hash<bluetooth::Uuid> {
    size_t operator()(const bluetooth::Uuid& uuid) const {
        // 基于 UUID 的字节数据计算哈希值
        // ...
    }
};
}  // namespace std

std::unordered_map<Uuid, ServiceInfo> service_map;
```

### 4.4 使用示例

```cpp
#include <unordered_map>

std::unordered_map<RawAddress, DeviceInfo> device_map;

// 插入
device_map[addr] = info;
device_map.insert({addr, info});

// 查找（平均 O(1)，比 map 的 O(log n) 更快）
auto it = device_map.find(addr);
if (it != device_map.end()) {
    // 找到了
}

// 遍历（顺序不确定！）
for (const auto& [key, value] : device_map) {
    // 键的顺序不保证
}
```

### 4.5 小贴士

> 如果你的键是标准类型（`int`、`std::string` 等），且不需要键有序，优先用 `unordered_map`。如果键是自定义类型，需要额外提供 `std::hash` 特化，这时可以权衡是否用 `map` 更简单。

---

## 5. std::set — 有序集合

### 5.1 什么是 std::set

`std::set` 是**有序的唯一元素**集合，基于红黑树实现。每个元素只出现一次，自动排序。

```
std::set<元素类型>
```

### 5.2 常用操作

```cpp
#include <set>

// 创建
std::set<int> s = {3, 1, 4, 1, 5};  // 实际存储：{1, 3, 4, 5}（去重 + 排序）

// 插入
s.insert(2);    // {1, 2, 3, 4, 5}
s.insert(3);    // 3 已存在，插入失败，set 不变

// 查找
auto it = s.find(3);      // 返回指向 3 的迭代器
if (it != s.end()) {
    // 找到了
}

// 计数（set 中只有 0 或 1）
size_t c = s.count(3);    // 1（存在）
size_t c2 = s.count(6);   // 0（不存在）

// 删除
s.erase(3);               // 按值删除

// 遍历（升序）
for (const auto& elem : s) {
    std::cout << elem << " ";
}

// 大小
size_t n = s.size();
bool empty = s.empty();
```

### 5.3 蓝牙协议栈中的真实示例

连接管理器用 `set` 记录哪些应用正在执行后台连接：

```cpp
// system/stack/connection_manager/connection_manager.cc:97-98
std::set<tAPP_ID> doing_bg_conn;
std::set<tAPP_ID> doing_targeted_announcements_conn;
```

为什么用 `set` 而不是 `vector`？

- **去重**：同一个应用不应该被重复记录。`set` 自动去重，`vector` 需要手动检查
- **快速查找**：判断某个应用是否在集合中，`set::count()` 是 O(log n)，`vector` 的遍历查找是 O(n)
- **快速删除**：`set::erase()` 是 O(log n)，`vector` 在中间删除是 O(n)

```cpp
// 应用请求后台连接
doing_bg_conn.insert(app_id);    // 添加（重复插入自动忽略）

// 检查是否有应用在后台连接
if (!doing_bg_conn.empty()) {
    // 有应用在等待
}

// 应用取消后台连接
doing_bg_conn.erase(app_id);     // 删除
```

### 5.4 小贴士

> 如果你只需要"判断某个元素是否存在"，`set` 比 `vector` 更高效。如果元素不需要排序且数量较大，考虑 `std::unordered_set`。

---

## 6. std::deque — 双端队列

### 6.1 什么是 std::deque

`std::deque`（Double-Ended Queue）是**双端**动态数组，在头部和尾部都能高效地插入/删除。

```
std::deque<元素类型>
```

### 6.2 与 vector 的区别

| 特性 | `std::vector` | `std::deque` |
|------|--------------|-------------|
| 尾部插入 | O(1) 均摊 | O(1) 均摊 |
| 头部插入 | O(n) | O(1) 均摊 |
| 内存连续 | 是 | 分段连续 |
| 随机访问 | O(1) | O(1) |
| 迭代器失效 | 扩容时全部失效 | 插入/删除可能导致失效 |
| 适用场景 | 主要在尾部操作 | 需要在两端操作 |

### 6.3 常用操作

```cpp
#include <deque>

std::deque<int> dq;

// 尾部操作（和 vector 一样）
dq.push_back(10);
dq.emplace_back(20);
dq.pop_back();

// 头部操作（vector 没有的高效操作！）
dq.push_front(5);
dq.emplace_front(3);
dq.pop_front();

// 随机访问
int x = dq[0];
int y = dq.at(1);

// 遍历
for (const auto& elem : dq) {
    std::cout << elem << " ";
}
```

### 6.4 蓝牙协议栈中的真实示例

GATT（通用属性协议）的命令队列使用 `deque`：

```cpp
// system/stack/eatt/eatt.h:61
std::deque<tGATT_CMD_Q> cl_cmd_q_;
```

为什么用 `deque` 而不是 `vector`？

- 命令队列需要频繁在头部取出（`pop_front`）、尾部添加（`push_back`）
- `vector` 的 `pop_front` 是 O(n)，需要移动所有后续元素
- `deque` 的 `pop_front` 是 O(1)，天然适合队列场景

```cpp
// 生产者：新命令入队（尾部）
cl_cmd_q_.push_back(new_cmd);

// 消费者：取出最旧的命令处理（头部）
if (!cl_cmd_q_.empty()) {
    tGATT_CMD_Q cmd = cl_cmd_q_.front();
    cl_cmd_q_.pop_front();
    process_command(cmd);
}
```

### 6.5 小贴士

> 如果你需要频繁在头部删除元素，`deque` 比 `vector` 更合适。如果只在尾部操作，`vector` 通常更快（内存更连续，缓存更友好）。

---

## 7. std::queue — 队列

### 7.1 什么是 std::queue

`std::queue` 是**先进先出（FIFO）**的容器适配器。它不自己存储数据，而是包装一个底层容器（默认是 `std::deque`），只暴露队列相关的操作。

```
std::queue<元素类型>              // 默认底层用 deque
std::queue<元素类型, std::list<元素类型>>  // 也可以用 list
```

### 7.2 常用操作

```cpp
#include <queue>

std::queue<std::string> q;

// 入队（尾部）
q.push("task1");
q.push("task2");
q.emplace("task3");

// 查看队首/队尾
std::string front = q.front();   // "task1"（最早入队的）
std::string back = q.back();     // "task3"（最晚入队的）

// 出队（头部）
q.pop();                         // 移除 "task1"

// 大小
size_t n = q.size();
bool empty = q.empty();
```

> 注意：`queue` 没有 `begin()`/`end()`，不能遍历。它故意只提供 FIFO 接口。

### 7.3 蓝牙协议栈中的真实示例

蓝牙框架的消息处理器用 `queue` 管理待执行的任务：

```cpp
// system/gd/os/handler.h:120
std::queue<common::OnceClosure>* tasks_;
```

`OnceClosure` 是一个"只能执行一次的闭包"（类似 `std::function` 但只能调用一次）。Handler 是蓝牙框架中事件循环的核心组件：

```cpp
// 向 Handler 投递任务
void Handler::Post(common::OnceClosure task) {
    {
        std::lock_guard<std::mutex> lock(mutex_);
        tasks_->push(std::move(task));   // 任务入队
    }
    cv_.notify_one();                     // 通知工作线程
}

// Handler 的工作线程循环
void Handler::Run() {
    while (running_) {
        common::OnceClosure task;
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (tasks_->empty()) continue;
            task = std::move(tasks_->front());  // 取队首任务
            tasks_->pop();                       // 出队
        }
        task();   // 执行任务
    }
}
```

这完美体现了队列的 FIFO 语义：**先投递的任务先执行**。

### 7.4 小贴士

> `std::queue` 是容器适配器，不是容器。它限制你只能从一端进、另一端出，保证了 FIFO 语义，防止你意外在中间插入或删除元素。

---

## 8. std::priority_queue — 优先队列

### 8.1 什么是 std::priority_queue

`std::priority_queue` 是**优先级最高者先出**的容器适配器，基于堆（heap）实现。默认是**大顶堆**——最大的元素先出。

```
std::priority_queue<元素类型>                                          // 默认大顶堆
std::priority_queue<元素类型, 底层容器类型, 比较器类型>                   // 自定义
```

### 8.2 常用操作

```cpp
#include <queue>

// 默认：大顶堆（最大的先出）
std::priority_queue<int> pq;
pq.push(3);
pq.push(1);
pq.push(4);
pq.push(1);
pq.push(5);

int top = pq.top();   // 5（最大值）
pq.pop();             // 移除 5
top = pq.top();       // 4

// 小顶堆（最小的先出）
std::priority_queue<int, std::vector<int>, std::greater<int>> min_pq;
min_pq.push(3);
min_pq.push(1);
min_pq.push(4);
int t = min_pq.top();  // 1（最小值）
```

### 8.3 自定义比较器

当元素类型比较复杂时，需要自定义比较器：

```cpp
// 按时间排序的延迟任务
struct CompareTaskByTime {
    bool operator()(const DelayedTask& a, const DelayedTask& b) const {
        return a.first > b.first;   // 时间更早的优先级更高（小顶堆）
    }
};

std::priority_queue<DelayedTask, std::vector<DelayedTask>, CompareTaskByTime> pq;
```

### 8.4 蓝牙协议栈中的真实示例

蓝牙框架的 Handler 用优先队列管理**延迟任务**——任务关联一个执行时间，需要按时间顺序取出执行：

```cpp
// system/gd/os/handler.h:49-50
using DelayedTaskQueue =
    std::priority_queue<DelayedTask, std::vector<DelayedTask>, decltype(compare_task_by_time)>;
```

其中 `DelayedTask` 是一个 `std::pair<TimePoint, OnceClosure>`（见第 9 节），比较器 `compare_task_by_time` 按时间排序：

```cpp
// system/gd/os/handler.h:37
using DelayedTask = std::pair<TimePoint, common::OnceClosure>;

// 比较器：时间更早的任务优先级更高
auto compare_task_by_time = [](const DelayedTask& a, const DelayedTask& b) {
    return a.first > b.first;   // 小顶堆：时间早的先出
};

// 使用
DelayedTaskQueue delayed_tasks_;

// 投递延迟任务
void Handler::PostDelayed(common::OnceClosure task, TimePoint deadline) {
    delayed_tasks_.push({deadline, std::move(task)});
}

// 取出到期的任务
void Handler::ProcessDelayedTasks() {
    while (!delayed_tasks_.empty() && delayed_tasks_.top().first <= now) {
        auto task = std::move(delayed_tasks_.top().second);
        delayed_tasks_.pop();
        task();
    }
}
```

为什么用 `priority_queue` 而不是排序整个列表？

- 插入 O(log n)，取顶部 O(1)，比每次排序 O(n log n) 高效
- 只关心"最近要执行的任务"，不需要维护完整顺序
- 堆天然适合这种"取最值"的场景

### 8.5 小贴士

> `priority_queue` 默认是大顶堆。如果你需要小顶堆（最小的先出），用 `std::greater<>` 作为比较器，或者自定义比较器时用 `>` 而不是 `<`。

---

## 9. std::pair — 值对

### 9.1 什么是 std::pair

`std::pair` 是最简单的组合容器，将**两个值**绑定在一起。它不是容器，而是一个"值对"工具类。

```
std::pair<第一个类型, 第二个类型>
```

### 9.2 常用操作

```cpp
#include <utility>   // std::pair 和 std::make_pair

// 创建
std::pair<int, std::string> p1(1, "hello");
auto p2 = std::make_pair(2, "world");    // 自动推导类型
auto p3 = std::pair(3, "c++");           // C++17 CTAD

// 访问
int n = p1.first;            // 1
std::string s = p1.second;   // "hello"

// 结构化绑定（C++17）
auto [key, value] = p1;      // key = 1, value = "hello"

// 比较（先比 first，再比 second）
std::pair<int, int> a(1, 3);
std::pair<int, int> b(1, 5);
bool less = (a < b);         // true（first 相同，3 < 5）
```

### 9.3 pair 与 map 的关系

`map` 的元素类型就是 `std::pair<const Key, Value>`。遍历 map 时，迭代器指向的就是 pair：

```cpp
std::map<int, std::string> m = {{1, "one"}, {2, "two"}};

// 迭代器指向 pair<const int, string>
for (auto it = m.begin(); it != m.end(); ++it) {
    std::cout << it->first << ": " << it->second << "\n";
}
```

### 9.4 蓝牙协议栈中的真实示例

**示例 1：延迟任务**

Handler 的延迟任务用 `pair` 将**执行时间**和**任务闭包**绑定在一起：

```cpp
// system/gd/os/handler.h:37
using DelayedTask = std::pair<TimePoint, common::OnceClosure>;
```

- `first`（TimePoint）：任务应该执行的时间
- `second`（OnceClosure）：要执行的任务本身

这样 `priority_queue` 就能按 `first`（时间）排序，时间最早的任务先出队。

**示例 2：遍历 map**

遍历 EATT 通道映射时，迭代器指向 pair：

```cpp
// system/stack/eatt/eatt_impl.h:104
for (const std::pair<uint16_t, std::shared_ptr<EattChannel>> el : eatt_dev->eatt_channels) {
    // el.first  = CID（uint16_t）
    // el.second = EattChannel 的 shared_ptr
}
```

### 9.5 小贴士

> `pair` 主要用于 `map` 的元素和需要返回两个值的函数。如果你需要绑定三个或更多值，用 `std::tuple` 或自定义结构体。

---

## 10. std::optional — 可能不存在的值 (C++17)

### 10.1 什么是 std::optional

`std::optional` 表示一个值**可能存在，也可能不存在**。它是比返回"特殊值"（如 `nullptr`、`-1`、空字符串）更安全、更语义化的替代方案。

```
std::optional<值类型>
```

### 10.2 常用操作

```cpp
#include <optional>

// 创建
std::optional<int> o1;                  // 空（不包含值）
std::optional<int> o2 = 42;             // 包含值 42
std::optional<int> o3 = std::nullopt;   // 显式设为空

// 检查是否有值
if (o2.has_value()) {        // true
    int x = o2.value();      // 42（有值时安全访问）
}

// 隐式转 bool
if (o2) {                    // true（有值时为 true）
    int x = *o2;             // 42（解引用访问）
}

// 没有值时访问会怎样？
int y = o1.value();          // 抛出 std::bad_optional_access！
int z = *o1;                 // 未定义行为！危险！

// 提供默认值
int w = o1.value_or(0);      // 0（o1 为空，使用默认值）

// 重置
o2.reset();                  // 变为空
o2 = std::nullopt;           // 同上
```

### 10.3 为什么不用指针或特殊值

```cpp
// 方案 1：返回特殊值（不安全，-1 可能是合法值）
int find_device_id(RawAddress addr);   // 返回 -1 表示未找到

// 方案 2：返回指针（语义不明确，调用者不知道是否需要 delete）
int* find_device_id(RawAddress addr);  // 返回 nullptr 表示未找到

// 方案 3：返回 optional（语义清晰，安全）
std::optional<int> find_device_id(RawAddress addr);  // 返回 nullopt 表示未找到
```

### 10.4 蓝牙协议栈中的真实示例

**示例 1：从字符串解析蓝牙地址**

蓝牙地址字符串（如 "00:11:22:33:44:55"）可能格式错误，解析可能失败。用 `optional` 表示"可能解析成功，也可能失败"：

```cpp
// system/types/include/bluetooth/types/address.h:58
static std::optional<RawAddress> FromString(const std::string& from);
```

使用方式：

```cpp
auto addr = RawAddress::FromString("00:11:22:33:44:55");
if (addr.has_value()) {
    // 解析成功，使用 addr.value()
    connect_to_device(addr.value());
} else {
    // 解析失败，字符串格式不正确
    log_error("Invalid address format");
}
```

**示例 2：反序列化**

从字符串反序列化对象可能失败（格式错误、数据不完整等）：

```cpp
// system/gd/storage/serializable.h:39
template <typename T>
static std::optional<T> FromString(const std::string& str);
```

```cpp
auto config = Config::FromString(data);
if (config) {
    use_config(config.value());
} else {
    use_default_config();
}
```

### 10.5 小贴士

> 当函数可能"没有结果"时，优先用 `optional` 而不是返回指针或特殊值。它让意图更清晰，使用更安全。

---

## 11. std::variant — 类型安全的联合体 (C++17)

### 11.1 什么是 std::variant

`std::variant` 是 C++17 引入的**类型安全联合体**。它可以持有**一组指定类型中的某一个**，且始终知道当前持有的是哪个类型。

```
std::variant<类型1, 类型2, ...>
```

### 11.2 与 C 联合体的区别

```cpp
// C 联合体：不安全，不知道当前是哪种类型
union Data {
    int i;
    float f;
    char* s;
};
Data d;
d.i = 42;
// d.f 是什么？不知道！没有运行时类型信息

// std::variant：安全，始终知道当前类型
std::variant<int, float, std::string> v;
v = 42;                                    // 当前是 int
std::cout << std::get<int>(v);             // 安全访问
// std::get<float>(v);                     // 抛出 std::bad_variant_access！
```

### 11.3 常用操作

```cpp
#include <variant>

// 创建和赋值
std::variant<int, float, std::string> v = 42;      // 当前是 int
v = 3.14f;                                           // 切换为 float
v = "hello";                                         // 切换为 string

// 访问
std::string s = std::get<std::string>(v);            // 按类型访问
int idx = v.index();                                  // 当前类型的索引（2 = string）

// 安全访问
auto* ptr = std::get_if<int>(&v);                    // 返回指针，如果类型不匹配返回 nullptr
if (ptr) {
    std::cout << *ptr;
}

// 访问者模式（推荐）
std::visit([](auto&& arg) {
    using T = std::decay_t<decltype(arg)>;
    if constexpr (std::is_same_v<T, int>) {
        std::cout << "int: " << arg;
    } else if constexpr (std::is_same_v<T, float>) {
        std::cout << "float: " << arg;
    } else if constexpr (std::is_same_v<T, std::string>) {
        std::cout << "string: " << arg;
    }
}, v);
```

### 11.4 蓝牙协议栈中的真实示例

音量控制（Volume Control）协议中，操作目标可能是**单个设备**（用地址标识），也可能是**设备组**（用组 ID 标识）：

```cpp
// system/include/hardware/bt_vc.h
std::variant<RawAddress, int> addr_or_group_id;
```

这表示：
- 当值是 `RawAddress` 类型时 → 操作单个设备
- 当值是 `int` 类型时 → 操作一个设备组

使用方式：

```cpp
void set_volume(std::variant<RawAddress, int> target, uint8_t volume) {
    std::visit([volume](auto&& arg) {
        using T = std::decay_t<decltype(arg)>;
        if constexpr (std::is_same_v<T, RawAddress>) {
            // 单设备操作
            set_device_volume(arg, volume);
        } else if constexpr (std::is_same_v<T, int>) {
            // 组操作
            set_group_volume(arg, volume);
        }
    }, target);
}
```

为什么不用 `union` 或两个变量？

- `union`：不安全，没有类型信息，容易误用
- 两个变量 `RawAddress addr; int group_id;`：语义不明确，需要额外标志位表示"当前用哪个"
- `variant`：类型安全，编译期保证只能是两种类型之一，运行时可以正确判断

### 11.5 小贴士

> `variant` 适合"同一个概念，不同类型表示"的场景。使用 `std::visit` 是最安全的访问方式，编译器会检查你是否处理了所有可能的类型。

---

## 12. STL 算法

STL 算法是定义在 `<algorithm>` 和 `<numeric>` 头文件中的**通用函数模板**，可以作用于任何容器。它们让你的代码更简洁、更正确、更高效。

### 12.1 std::find_if — 条件查找

`std::find_if` 在范围内查找**第一个满足条件**的元素，返回迭代器。

```cpp
#include <algorithm>

std::vector<int> v = {1, 2, 3, 4, 5};

// 查找第一个大于 3 的元素
auto it = std::find_if(v.begin(), v.end(), [](int x) {
    return x > 3;
});
if (it != v.end()) {
    std::cout << *it;   // 4
}
```

**蓝牙协议栈中的典型用法**——在设备列表中查找特定设备：

```cpp
// 在 devices_ 中查找指定地址的设备
auto it = std::find_if(devices_.begin(), devices_.end(),
    [&bd_addr](const eatt_device& dev) {
        return dev.bd_addr_ == bd_addr;
    });
if (it != devices_.end()) {
    // 找到了
}
```

### 12.2 std::count_if — 条件计数

`std::count_if` 统计范围内**满足条件的元素个数**。

```cpp
#include <algorithm>

std::vector<int> v = {1, 2, 3, 4, 5, 6};

// 统计偶数的个数
size_t n = std::count_if(v.begin(), v.end(), [](int x) {
    return x % 2 == 0;
});
// n = 3（2, 4, 6）
```

**蓝牙协议栈中的典型用法**——统计处于某种状态的通道数：

```cpp
// 统计正在连接的通道数
size_t connecting_count = std::count_if(
    channels.begin(), channels.end(),
    [](const auto& ch) { return ch.state_ == State::CONNECTING; });
```

### 12.3 std::min 和 std::max — 取最小/最大值

```cpp
#include <algorithm>

int a = 10, b = 20;
int m = std::min(a, b);    // 10
int n = std::max(a, b);    // 20

// 可以显式指定返回类型（避免隐式转换问题）
auto x = std::min<uint16_t>(100, 200);
auto y = std::max<uint16_t>(50, 300);
```

**蓝牙协议栈中的真实示例**——限制 MTU（最大传输单元）在合法范围内：

```cpp
// system/stack/eatt/eatt.h:103-104
this->tx_mtu_ = std::min<uint16_t>(tx_mtu, EATT_MAX_TX_MTU);   // 不超过最大值
this->tx_mtu_ = std::max<uint16_t>(tx_mtu, EATT_MIN_MTU_MPS);  // 不低于最小值
```

这两行代码实现了**值域夹紧（clamping）**：确保 `tx_mtu_` 在 `[EATT_MIN_MTU_MPS, EATT_MAX_TX_MTU]` 范围内。

C++17 提供了更简洁的写法：

```cpp
// C++17: std::clamp 一步到位
this->tx_mtu_ = std::clamp(tx_mtu, EATT_MIN_MTU_MPS, EATT_MAX_TX_MTU);
```

### 12.4 std::sort — 排序

```cpp
#include <algorithm>

std::vector<int> v = {5, 2, 8, 1, 9};

// 升序排序（默认）
std::sort(v.begin(), v.end());
// v = {1, 2, 5, 8, 9}

// 降序排序
std::sort(v.begin(), v.end(), std::greater<int>());
// v = {9, 8, 5, 2, 1}

// 自定义排序
std::sort(v.begin(), v.end(), [](int a, int b) {
    return a % 3 < b % 3;   // 按对 3 取模的结果排序
});
```

**蓝牙协议栈中的典型用法**——按信号强度排序扫描结果：

```cpp
// 按信号强度（RSSI）从强到弱排序扫描结果
std::sort(scan_results.begin(), scan_results.end(),
    [](const ScanResult& a, const ScanResult& b) {
        return a.rssi > b.rssi;
    });
```

### 12.5 其他常用算法速查

| 算法 | 功能 | 示例 |
|------|------|------|
| `std::find` | 查找等于某值的元素 | `std::find(v.begin(), v.end(), 42)` |
| `std::find_if_not` | 查找第一个不满足条件的 | `std::find_if_not(v.begin(), v.end(), pred)` |
| `std::any_of` | 是否存在满足条件的元素 | `std::any_of(v.begin(), v.end(), pred)` |
| `std::all_of` | 是否所有元素都满足条件 | `std::all_of(v.begin(), v.end(), pred)` |
| `std::none_of` | 是否没有元素满足条件 | `std::none_of(v.begin(), v.end(), pred)` |
| `std::count` | 统计等于某值的元素数 | `std::count(v.begin(), v.end(), 42)` |
| `std::remove_if` | 逻辑删除（需配合 erase） | `v.erase(std::remove_if(v.begin(), v.end(), pred), v.end())` |
| `std::for_each` | 对每个元素执行操作 | `std::for_each(v.begin(), v.end(), func)` |
| `std::transform` | 变换每个元素 | `std::transform(v.begin(), v.end(), out.begin(), func)` |
| `std::copy_if` | 条件拷贝 | `std::copy_if(v.begin(), v.end(), out.begin(), pred)` |

### 12.6 小贴士

> 优先使用 STL 算法而不是手写循环。算法代码更简洁、更不容易出错，而且实现通常经过优化。

---

## 13. 容器选择指南

### 13.1 决策流程图

```
需要存储一组数据？
│
├─ 大小编译期确定？
│   └─ 是 → std::array
│
├─ 需要键值对映射？
│   ├─ 需要键有序？
│   │   └─ 是 → std::map
│   └─ 只需快速查找？
│       └─ 是 → std::unordered_map
│
├─ 只需要集合（不需要值）？
│   ├─ 需要元素有序？
│   │   └─ 是 → std::set
│   └─ 只需快速判断存在？
│       └─ 是 → std::unordered_set
│
├─ 需要队列语义？
│   ├─ FIFO（先进先出）？
│   │   └─ 是 → std::queue
│   ├─ 优先级最高的先出？
│   │   └─ 是 → std::priority_queue
│   └─ 两端都需要操作？
│       └─ 是 → std::deque
│
├─ 需要动态数组？
│   └─ 是 → std::vector（默认选择！）
│
└─ 值可能不存在？
    └─ 是 → std::optional
```

### 13.2 蓝牙协议栈中的容器使用总结

| 容器 | 协议栈用途 | 选择原因 |
|------|-----------|---------|
| `std::array<uint8_t, 6>` | 蓝牙地址 | 固定 6 字节，编译期确定 |
| `std::array<uint8_t, 16>` | UUID | 固定 16 字节，编译期确定 |
| `std::vector<eatt_device>` | EATT 设备列表 | 数量运行时变化，尾部添加 |
| `std::vector<uint16_t>` | CID 列表 | L2CAP 返回的通道 ID 列表 |
| `std::map<uint16_t, shared_ptr<EattChannel>>` | CID → 通道映射 | 按 CID 快速查找通道 |
| `std::map<RawAddress, tAPPS_CONNECTING>` | 设备 → 连接状态 | 按地址快速查找连接状态 |
| `std::set<tAPP_ID>` | 后台连接应用集合 | 去重 + 快速查找/删除 |
| `std::deque<tGATT_CMD_Q>` | GATT 命令队列 | 头部删除 + 尾部添加 |
| `std::queue<OnceClosure>` | 任务队列 | FIFO 语义 |
| `std::priority_queue<DelayedTask>` | 延迟任务队列 | 按时间排序，最近的先执行 |
| `std::pair<TimePoint, OnceClosure>` | 延迟任务 | 绑定时间与任务 |
| `std::optional<RawAddress>` | 解析结果 | 解析可能失败 |
| `std::variant<RawAddress, int>` | 设备或组 | 同一概念，两种表示 |

### 13.3 性能对比速查表

| 容器 | 随机访问 | 头部插入/删除 | 尾部插入/删除 | 查找 | 内存 |
|------|---------|-------------|-------------|------|------|
| `array` | O(1) | - | - | - | 连续 |
| `vector` | O(1) | O(n) | O(1) 均摊 | O(n) | 连续 |
| `deque` | O(1) | O(1) 均摊 | O(1) 均摊 | O(n) | 分段连续 |
| `map` | - | O(log n) | O(log n) | O(log n) | 节点 |
| `unordered_map` | - | O(1) 均摊 | O(1) 均摊 | O(1) 均摊 | 哈希桶 |
| `set` | - | O(log n) | O(log n) | O(log n) | 节点 |
| `priority_queue` | O(1) 顶部 | - | O(log n) | - | 连续 |

### 13.4 默认选择：std::vector

> 如果你不确定该用哪个容器，**就用 `std::vector`**。
>
> 理由：
> - 内存连续，缓存最友好
> - 随机访问 O(1)
> - 尾部操作 O(1)
> - 与 C API 兼容（`v.data()` 返回裸指针）
> - 绝大多数场景下性能最优
>
> 只有当你有明确的理由（需要键值映射、需要有序、需要 FIFO 等）时，才考虑其他容器。

---

## 总结

STL 容器和算法是 C++ 程序员工具箱中最基础、最重要的工具。在蓝牙协议栈这样的真实工程中，我们可以看到：

1. **`std::array`** 用于固定大小的协议数据（地址、UUID）
2. **`std::vector`** 用于动态数量的列表（设备、通道 ID）
3. **`std::map`** 用于键值映射（CID → 通道、地址 → 状态）
4. **`std::unordered_map`** 用于需要 O(1) 查找的映射（需要 hash 特化）
5. **`std::set`** 用于去重集合（应用 ID 集合）
6. **`std::deque`** 用于双端操作（命令队列）
7. **`std::queue`** 用于 FIFO（任务队列）
8. **`std::priority_queue`** 用于按优先级出队（延迟任务）
9. **`std::pair`** 用于绑定两个值（map 元素、延迟任务）
10. **`std::optional`** 用于可能不存在的值（解析结果）
11. **`std::variant`** 用于类型安全的联合体（设备地址或组 ID）
12. **STL 算法** 用于通用操作（查找、计数、排序、取极值）

掌握这些容器和算法，你就拥有了组织数据的"标准武器库"，能够根据场景选择最合适的工具，写出高效、安全、可维护的代码。
