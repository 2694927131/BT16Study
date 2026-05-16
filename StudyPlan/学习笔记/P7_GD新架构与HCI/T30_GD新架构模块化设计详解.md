# T30 GD新架构模块化设计详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：GD 17个子目录模块体系 | OS层Handler→Reactor→epoll事件驱动 | Packet PDL自动代码生成 | module_t依赖拓扑排序 | Stack单例依赖注入
> 待回顾问题：无

---

## 1. GD架构设计理念

### 1.1 为什么引入GD？

```
旧架构(AOSP Legacy Stack)的问题：
  ┌───────────────────────────────────────────────────┐
  │ 1. 全局状态满天飞 (tBTA_AV_CB, bta_hh_cb...)     │
  │ 2. 固定线程模型 (BTIF线程+BTA线程, 无法扩展)     │
  │ 3. 函数指针回调深层嵌套 (回调地狱)               │
  │ 4. 循环依赖 (btif→bta→stack→bta→btif)            │
  │ 5. 无法单元测试 (强依赖硬件+FIFO+全局变量)        │
  │ 6. 车机/手机/手表共享一套代码但行为差 (难以定制)  │
  └───────────────────────────────────────────────────┘

GD新架构的解决方案：
  ┌───────────────────────────────────────────────────┐
  │ 1. 依赖注入 (通过构造函数显式传入依赖)           │
  │ 2. 单线程事件循环 (每个Module有独立Handler)      │
  │ 3. 异步回调 (ContextualOnceCallback)             │
  │ 4. 接口抽象 (HciHal/HciBackend可通过mock替换)    │
  │ 5. 构建时可测试 (Host模式用RootCanal替换硬件)    │
  │ 6. 模块化 (每个功能独立模块, 可独立开关)         │
  └───────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

| 原则 | 旧架构 | GD新架构 |
|------|--------|----------|
| 状态管理 | 全局变量 | 类成员+依赖注入 |
| 线程 | 固定2线程(BTIF+BTA) | 按需创建Thread+Handler |
| 回调 | 函数指针 | ContextualOnceCallback(绑定Handler) |
| 数据包 | 原始字节数组 | 类型安全PacketView/PacketBuilder |
| 测试 | 需硬件 | Host模式+Mock HAL |
| 依赖 | 隐式(通过全局变量) | 显式(构造函数参数) |

---

## 2. GD模块化体系

### 2.1 目录结构一览

```
system/gd/
├── common/          # 通用工具
│   ├── Bind.h       → 参数绑定 (类似std::bind)
│   ├── Callback.h   → 回调封装 (once/repeating)
│   ├── BidiQueue.h  → 双向生产者-消费者队列
│   ├── BlockingQueue.h → 阻塞队列
│   ├── CircularBuffer.h → 环形缓冲区
│   ├── LruCache.h   → LRU缓存
│   └── strings.h    → 字符串工具
│
├── os/              # OS抽象层 (核心)
│   ├── thread.h    → 线程(封装std::thread+Reactor)
│   ├── handler.h   → 事件处理器(Post队列+延迟任务)
│   ├── reactor.h   → epoll事件循环
│   ├── alarm.h     → timerfd定时器
│   ├── queue.h     → 线程安全队列
│   └── wakelock_manager.h → Wakelock管理
│
├── packet/          # 数据包框架
│   ├── packet_view.h    → 零拷贝数据包视图
│   ├── packet_builder.h → 类型安全包构建器
│   ├── view.h           → 结构化数据迭代器
│   └── parser/          → PDL代码生成器
│
├── hal/             # HAL抽象层
│   ├── hci_hal.h        → HCI HAL接口(HciHal/HciHalCallbacks)
│   ├── hci_hal_impl_android.h → Android实现
│   ├── hci_backend.h    → AIDL/HIDL后端抽象
│   ├── snoop_logger.h   → Snoop Log
│   └── ranging_hal.h    → Ranging HAL
│
├── hci/             # HCI层 (新架构核心)
│   ├── hci_layer.h  → HCI层主类
│   ├── hci_interface.h → HCI接口抽象
│   ├── controller.h → 蓝牙控制器管理
│   │
│   ├── acl_manager/     → ACL连接管理
│   │   ├── acl_manager_classic.h → BR/EDR ACL
│   │   ├── acl_manager_le.h      → LE ACL
│   │   ├── round_robin_scheduler.h → 轮询调度
│   │   └── acl_fragmenter.h       → ACL分片/重组
│   │
│   ├── acl_manager/le_impl/    → LE实现细节
│   ├── le_scanning_manager/    → LE扫描
│   ├── le_advertising_manager/ → LE广播
│   ├── le_address_manager.h    → LE隐私地址
│   ├── security_interface.h    → BR/EDR安全
│   ├── le_security_interface.h → LE安全
│   └── distance_measurement/   → 距离测量
│
├── storage/         # 设备存储
│   ├── storage_module.h   → 存储模块
│   ├── config_cache.h    → 配置缓存
│   └── mutation.h        → 事务性修改
│
├── crypto_toolbox/  # 加密工具
├── metrics/         # 度量统计
├── lpp/             # LE Power Path offload
├── sysprops/        # 系统属性(Floss)
└── docs/architecture/ → 架构文档
```

### 2.2 module_t 模块系统（桥接层）

源码：[module.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btcore/include/module.h)

```cpp
#define BTCORE_MAX_MODULE_DEPENDENCIES 10

typedef struct {
    const char* name;
    module_lifecycle_fn init;       // 初始化
    module_lifecycle_fn start_up;   // 启动
    module_lifecycle_fn shut_down;  // 关闭
    module_lifecycle_fn clean_up;   // 清理
    const char* dependencies[BTCORE_MAX_MODULE_DEPENDENCIES]; // 依赖模块
} module_t;
```

**生命周期**：`NONE → init() → INITIALIZED → start_up() → STARTED → shut_down() → INITIALIZED → clean_up() → NONE`

**模块管理**([module.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btcore/src/module.cc))：
- `get_module(name)` — 通过 `dlsym(RTLD_DEFAULT, name)` 动态查找模块符号
- `module_init()` — 拓扑排序后按序初始化所有依赖
- `module_start_up()` — 按序启动所有模块

**GD模块作为module_t注册**（[shim.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/main/shim/shim.cc)）：
```cpp
EXPORT_SYMBOL extern const module_t gd_shim_module = {
    .name = GD_SHIM_MODULE,
    .start_up = ShimModuleStartUp,
    .shut_down = GeneralShutDown,
    .dependencies = {kUnusedModuleDependencies}
};
```

---

## 3. GD OS抽象层

### 3.1 Thread — 线程抽象

源码：[thread.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/os/thread.h)

```cpp
class Thread {
public:
    enum class Priority { REAL_TIME, NORMAL };
    Thread(const std::string& name, Priority priority);
    bool IsSameThread() const;         // 判断当前是否在此线程
    Reactor* GetReactor() const;      // 获取Reactor
private:
    std::string name_;
    mutable Reactor reactor_;          // 每个线程拥有独立Reactor
    std::thread running_thread_;       // 底层std::thread
};
```

**车载关键**：`REAL_TIME`优先级确保蓝牙音频的低延迟。

### 3.2 Handler — 事件处理器

源码：[handler.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/os/handler.h)

```cpp
class Handler {
public:
    explicit Handler(Thread* thread);
    
    // 投递任务到目标线程
    void Post(OnceClosure closure);
    
    // 延迟投递
    bool PostWithDelay(OnceClosure closure, milliseconds delay);
    
    // 便捷模板: 绑定对象+方法
    template <typename T, typename Functor, typename... Args>
    void CallOn(T* obj, Functor&& functor, Args&&... args);
    
private:
    std::queue<OnceClosure>* tasks_;     // 任务队列
    Thread* thread_;
    Reactor::Reactable* reactable_;      // eventfd注册
    DelayedTaskQueue* delayed_tasks_;    // 延迟任务优先队列
    Alarm* alarm_;                       // timerfd驱动延迟任务
};
```

**消息分发机制**：
```
1. Handler::Post(closure)
   → 放入 tasks_ 队列
   → event_->Notify() → 写 eventfd

2. eventfd 可读 → Reactor唤醒
   → 从 epoll_wait 返回
   → 回调 handle_next_event()
   → 从 tasks_ 弹出 closure 并执行

3. PostWithDelay(closure, 100ms)
   → 放入 delayed_tasks_ 优先队列
   → alarm_->Schedule(now+100ms) → 设置 timerfd

4. timerfd到期 → Reactor唤醒
   → handle_delayed_event()
   → 到期任务移到 tasks_ → event_->Notify() → 执行
```

**车载应用**：整个GD栈运行在`gd_stack_thread`（REAL_TIME优先级），所有HCI事件/数据通过Handler::Post分发，保证实时性。

### 3.3 Reactor — epoll事件循环

源码：[reactor.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/os/reactor.h)

```cpp
class Reactor {
public:
    Reactor();
    void Run();    // 阻塞在 epoll_wait 循环
    void Stop();   // 从其他线程调用停止
    
    // 注册fd监听
    Reactable* Register(int fd, Closure on_read, Closure on_write);
    void Unregister(Reactable*);
    
    // Event: eventfd封装 (跨线程通知)
    class Event {
        void Notify(uint64_t n = 1);  // write(eventfd) → 唤醒epoll
        bool Read();                   // read(eventfd) → 清除事件
    };
    unique_ptr<Event> NewEvent() const;
    
private:
    int epoll_fd_;      // epoll文件描述符
    int control_fd_;    // eventfd用于Stop信号
    atomic<bool> is_running_;
};
```

### 3.4 Alarm — 定时器

```cpp
class Alarm {
    // 基于 timerfd_create / timerfd_settime
    // 到期 → fd可读 → Reactor回调 → 执行定时任务
};
```

---

## 4. GD Packet框架

### 4.1 PacketView — 零拷贝解析

```cpp
template <bool little_endian>
class PacketView {
    explicit PacketView(shared_ptr<const vector<uint8_t>> packet);
    Iterator<little_endian> begin() const;  // 结构化迭代器
    Iterator<little_endian> end() const;
    size_t size() const;
};
// 使用: auto view = CommandCompleteView::Create(PacketView<kLittleEndian>(bytes));
//       uint16_t handle = view.GetConnectionHandle();  // 类型安全, 直接解析
```

### 4.2 PacketBuilder — 类型安全构建

```cpp
template <bool little_endian>
class PacketBuilder : public BasePacketBuilder {
    vector<uint8_t> SerializeToBytes() const;
};
// 使用: auto cmd = CreateConnectionBuilder().SetBdAddr(addr).SetPacketType(0xCC18);
//       hci_layer->EnqueueCommand(move(cmd), callback);
```

### 4.3 PDL代码生成器

```
packet/parser/
  ├── gen_cpp.cc  → 从PDL定义生成C++代码
  └── main.cc     → 入口

PDL定义 → 自动生成:
  ├── *Builder 类 (命令构建)
  ├── *View 类    (事件解析)
  ├── *Enum 类型  (枚举安全)
  └── *Struct     (嵌套结构体)
```

**生成的类型示例**：
```
hci_packets.h → 
  CommandBuilder, AclCommandBuilder, SecurityCommandBuilder
  EventView, CommandCompleteView, ConnectionCompleteView
  LeMetaEventView, VendorSpecificEventView
```

### 4.4 BidiQueue — 双向队列

```cpp
// HciLayer中三个BidiQueue:
BidiQueueEnd<AclBuilder, AclView>*  GetAclQueueEnd();   // ACL数据
BidiQueueEnd<ScoBuilder, ScoView>*  GetScoQueueEnd();   // SCO数据
BidiQueueEnd<IsoBuilder, IsoView>*  GetIsoQueueEnd();   // ISO数据

// 每个队列有两个端点: upper(栈内) + lower(HAL)
// 深度=3, 实现流控
```

---

## 5. Stack单例（GD依赖注入中心）

源码：[stack.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/main/shim/stack.h)

```cpp
class Stack {
public:
    static Stack* GetInstance();
    void StartEverything();  // 启动所有GD组件
    void Stop();
    bool IsRunning();

    // 获取各GD组件 (依赖注入的访问点)
    storage::StorageModule*     GetStorage();
    hal::SnoopLogger*           GetSnoopLogger();
    hci::HciInterface*          GetHciLayer();
    hci::Controller*            GetController();
    hci::acl_manager::AclManagerClassic* GetAclManagerClassic();
    hci::AclManagerLe*          GetAclManagerLe();
    hci::LeScanningManager*     GetLeScanningManager();
    hci::LeAdvertisingManager*  GetLeAdvertisingManager();
    hci::DistanceMeasurementManager* GetDistanceMeasurementManager();
    lpp::LppOffloadInterface*   GetLppOffloadInterface();
    hci::MsftExtensionManager*  GetMsftExtensionManager();
};
```

**依赖注入的构建链**（[stack.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/main/shim/stack.cc)）：

```
StorageModule → SnoopLogger → HciHalImpl → HciLayer → Controller
                  ↓                         ↓
              (所有数据包)            GetAclQueueEnd()
                                              ↓
                                    RoundRobinScheduler
                                     ↓              ↓
                              AclManagerClassic  AclManagerLe
                                                    ↓
                                             LeAddressManager
```

**创建两个线程**：
- `gd_stack_thread` (REAL_TIME优先级) — 主GD工作线程
- `management_thread` (NORMAL优先级) — 异步启停

---

## 6. 对车载开发的影响

### 6.1 已迁移到GD的模块

```
✅ HCI层 (aclmgr/scan/adv/controller/security) → 全部GD
✅ SnoopLogger → GD hal/
✅ Storage → GD storage/
✅ BLE扫描/广播 → 通过shim从btif调用GD
✅ Channel Sounding/Ranging → GD hal/ranging_hal
```

### 6.2 仍在旧架构的模块

```
❌ A2DP (a2dp_sink.cc/source.cc) → btif+bta, 通过shim.acl转发ACL数据
❌ HFP (bta_ag_*) → 完全旧架构, 通过btif_hf→bta→stack
❌ AVRCP → 旧架构
❌ GATT Server/Client → 旧bta_gattc + 新GD HCI
❌ SDP → 旧stack/sdp
❌ RFCOMM → 旧stack/rfcomm
❌ PBAP/MAP/HID/PAN → 旧架构
```

### 6.3 车载避坑指南

```
1. A2DP音频数据通过shim.acl → GD ACL Manager转发
   → GD的ACL队列流控可能影响音频延迟
   → 关注 BidiQueue 的队列深度(3)是否够用

2. Vendor Command (VSC)发送
   → 旧HCI层有直接的 vendor_send_command()
   → GD层通过 HciHal::sendHciCommand() 发送
   → 注意OGF=0x3F的特殊处理

3. gd_stack_thread REAL_TIME优先级
   → 确保调度延迟 < 2ms (音频场景)
   → 避免在gd_stack_thread上做耗时操作

4. Storage迁移
   → 旧配置在 /data/misc/bluedroid/bt_config.conf
   → 新配置在 GD StorageModule
   → 存在双写/迁移兼容期
```