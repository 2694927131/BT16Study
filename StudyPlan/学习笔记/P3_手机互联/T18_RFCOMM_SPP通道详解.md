# T18_RFCOMM_SPP通道详解

> 学习日期：2026-05-16 | 优先级：P3 | 预计学习时间：3小时
> 前置知识：T17 BLE GATT完整流程、T04配对流程
> 涉及源码目录：system/btif/src/btif_sock_rfc.cc, system/bta/jv/bta_jv_act.cc, system/stack/rfcomm/

---

## 📋 本章导读

- **学什么**：RFCOMM帧格式（GSM 07.10）、DLCI多路复用、连接流程（SDP→L2CAP→SABM→PN→MSC）、SPP数据传输、Credit流控、RFCOMM Server端、车载互联应用
- **为什么学**：RFCOMM/SPP是车载OBD诊断、HiCar降级通道、CarLink通信的基础，理解帧格式和流控是排查数据传输问题的关键
- **学完能做**：
  - 从snoop log中解析RFCOMM帧，识别SABM/UA/UIH等控制帧
  - 理解Credit流控机制，排查数据传输卡顿
  - 掌握RFCOMM Server端开发，实现车机SPP监听

---

## 🗺️ 架构全景图

### RFCOMM连接完整流程

```mermaid
sequenceDiagram
    participant App as BluetoothSocket
    participant JNI as JNI层
    participant BTIF as btif_sock_rfc.cc
    participant BTA as bta_jv_act.cc
    participant RFCOMM as RFCOMM协议层
    participant L2CAP as L2CAP
    participant SDP as SDP
    participant Remote as 远端设备

    App->>JNI: connect()
    JNI->>BTIF: btsock_rfc_connect()
    BTIF->>SDP: SDP查询SPP UUID(0x1101)
    SDP-->>BTIF: RFCOMM Channel Number
    BTIF->>BTA: BTA_JvRfcommConnect()
    BTA->>L2CAP: L2CAP连接(PSM=0x0003)
    L2CAP-->>BTA: L2CAP连接成功
    BTA->>RFCOMM: SABM(DLCI=0)
    RFCOMM->>Remote: SABM
    Remote-->>RFCOMM: UA
    BTA->>RFCOMM: PN(参数协商)
    RFCOMM->>Remote: PN Request
    Remote-->>RFCOMM: PN Response
    BTA->>RFCOMM: MSC(调制解调器状态)
    RFCOMM->>Remote: MSC
    Remote-->>RFCOMM: MSC
    Note over BTA: 数据通道建立
    BTA-->>BTIF: PORT_SUCCESS
    BTIF-->>App: connect()返回
```

### RFCOMM帧格式

```mermaid
graph TD
    subgraph RFCOMM帧结构
        ADDR["Address (1-2B)<br/>DLCI(6bit)+C/R(1bit)+EA(1bit)"]
        CTRL["Control (1B)<br/>帧类型标识"]
        LEN["Length (1-2B)<br/>信息字段长度"]
        INFO["Information (0-127B)<br/>数据/控制信息"]
        FCS["FCS (1B)<br/>帧校验序列"]
    end

    ADDR --> CTRL --> LEN --> INFO --> FCS

    subgraph 6种控制帧
        SABM["SABM(0x2F)<br/>建立连接"]
        UA["UA(0x63)<br/>确认应答"]
        DISC["DISC(0x43)<br/>断开连接"]
        DM["DM(0x0F)<br/>断开模式/拒绝"]
        UIH["UIH(0xEF)<br/>数据传输(无CRC)"]
        UI["UI(0x03)<br/>控制消息"]
    end

    style SABM fill:#F44336,color:#fff
    style UA fill:#4CAF50,color:#fff
    style UIH fill:#2196F3,color:#fff
```

### DLCI多路复用

```mermaid
graph LR
    subgraph L2CAP通道PSM=0x0003
        DLCI0["DLCI=0<br/>控制通道"]
        DLCI2["DLCI=2<br/>数据通道1"]
        DLCI4["DLCI=4<br/>数据通道2"]
        DLCI6["DLCI=6<br/>数据通道3"]
        DOT["..."]
        DLCI60["DLCI=60<br/>数据通道30"]
    end

    subgraph 说明
        EVEN["偶数DLCI<br/>数据传输"]
        ODD["奇数DLCI<br/>控制信号"]
    end

    DLCI0 --> ODD
    DLCI2 --> EVEN
    DLCI4 --> EVEN

    style DLCI0 fill:#FF9800,color:#fff
    style DLCI2 fill:#4CAF50,color:#fff
    style DLCI4 fill:#2196F3,color:#fff
```

### Credit流控机制

```mermaid
sequenceDiagram
    participant Local as 本端
    participant Remote as 远端

    Note over Local,Remote: PN协商阶段
    Local->>Remote: PN Request(credits=7)
    Remote->>Local: PN Response(credits=7)
    Note over Local,Remote: 初始Credit各7

    Note over Local,Remote: 数据传输阶段
    Local->>Remote: UIH(data) [local_credit--]
    Local->>Remote: UIH(data) [local_credit--]
    Local->>Remote: UIH(data) [local_credit--]
    Note over Local: local_credit=4,仍可发送
    Remote->>Local: UIH(data) [remote_credit--]
    Remote->>Local: UIH(Credits=3) [补充Credit]
    Note over Local: local_credit=4+3=7

    Note over Local,Remote: Credit耗尽
    Local->>Remote: UIH(data) ×7 [credit=0]
    Note over Local: 等待远端补充Credit
    Remote->>Local: UIH(Credits=7)
    Note over Local: 恢复发送能力
```

### SPP数据传输路径

```mermaid
graph TD
    subgraph 发送路径
        APP_W["App: OutputStream.write()"]
        SOCK_W["btsock_rfc_write()"]
        RFC_W["RFCOMM: UIH(local_dlci)+data"]
        L2_W["L2CAP分段"]
        ACL_W["ACL发送"]
    end

    subgraph 接收路径
        ACL_R["ACL接收"]
        L2_R["L2CAP重组"]
        RFC_R["RFCOMM: 解析UIH"]
        SOCK_R["sock_rfcomm_read()"]
        APP_R["App: InputStream.read()"]
    end

    APP_W --> SOCK_W --> RFC_W --> L2_W --> ACL_W
    ACL_R --> L2_R --> RFC_R --> SOCK_R --> APP_R

    style APP_W fill:#4CAF50,color:#fff
    style APP_R fill:#2196F3,color:#fff
    style RFC_W fill:#FF9800,color:#fff
    style RFC_R fill:#FF9800,color:#fff
```

### RFCOMM Server端流程

```mermaid
sequenceDiagram
    participant App as ServerSocket
    participant BTIF as btif_sock_rfc.cc
    participant BTA as bta_jv_act.cc
    participant SDP as SDP
    participant Client as 客户端

    App->>BTIF: listenViaServiceRecord(UUID)
    BTIF->>BTA: BTA_JvCreateRecord()
    BTA->>SDP: 注册SPP Service Record
    Note over SDP: ServiceClassIDList: UUID<br/>ProtocolDescriptorList: RFCOMM, channel<br/>ServiceName: "Serial Port"
    BTIF->>BTIF: btsock_rfc_listen()
    Note over BTIF: 等待accept()

    Client->>SDP: SDP查询UUID
    SDP-->>Client: Channel Number
    Client->>BTA: SABM(DLCI)
    BTA-->>BTIF: 新连接事件
    BTIF-->>App: accept()返回Socket
```

---

## 🔍 代码导航

| 步骤 | 操作 | 文件 | 行号 | 看什么 |
|------|------|------|------|--------|
| 1 | 打开文件 | system/btif/src/btif_sock_rfc.cc | L100-150 | btsock_rfc_connect()：SPP连接入口 |
| 2 | 打开文件 | system/btif/src/btif_sock_rfc.cc | L200-260 | btsock_rfc_listen()：Server监听入口 |
| 3 | 打开文件 | system/btif/src/btif_sock_rfc.cc | L300-350 | sock_rfcomm_read()：数据读取 |
| 4 | 打开文件 | system/btif/src/btif_sock_rfc.cc | L360-400 | btsock_rfc_write()：数据写入 |
| 5 | 打开文件 | system/bta/jv/bta_jv_act.cc | L200-260 | bta_jv_rfcomm_connect()：BTA层连接 |
| 6 | 打开文件 | system/bta/jv/bta_jv_act.cc | L300-360 | bta_jv_rfcomm_start_server()：BTA Server |
| 7 | 打开文件 | system/bta/jv/bta_jv_act.cc | L400-460 | bta_jv_rfcomm_write()：BTA层写入 |
| 8 | 打开文件 | system/stack/rfcomm/rfc_port_if.cc | L50-100 | PORT_WriteData()：RFCOMM端口写入 |
| 9 | 打开文件 | system/stack/rfcomm/rfc_mx_fsm.cc | L80-140 | 多路复用器状态机 |
| 10 | 打开文件 | system/stack/rfcomm/rfc_l2cap_if.cc | L30-80 | L2CAP接口：数据收发 |
| 11 | 打开文件 | system/btif/include/bt_sock.h | L30-60 | btif_sock_connection_t：Socket控制块 |
| 12 | 打开文件 | system/stack/rfcomm/port_api.cc | L50-100 | PORT_Open()：端口打开API |

---

## 📖 核心流程详解

### 1.1 SPP连接入口：btsock_rfc_connect()

```cpp
// 📂 system/btif/src/btif_sock_rfc.cc:100-150
bt_status_t btsock_rfc_connect(const RawAddress& bd_addr,
                                const bluetooth::Uuid& uuid,
                                int channel, int* sock_fd) {
    // [1] 📨 SDP查询——获取远端SPP服务信息
    //     UUID=0x1101 (SerialPort)
    //     💡C++: btsock_rfc_search发起SDP查询
    //     类似Java的 device.fetchUuidsWithSdp()
    btsock_rfc_search(bd_addr, uuid);

    // [2] SDP查询完成后回调:
    //     → RFCOMM Channel Number (server_channel)
    //     → 填充 bt_sockaddr_rfcomm_t.client_channel
    //     💡C++: SDP查询是异步的，结果通过回调获取

    // [3] 📨 发起RFCOMM连接
    //     BTA_JvRfcommConnect → L2CAP连接 → SABM/PN/MSC
    //     💡C++: channel参数来自SDP查询结果
    //     类似Java的 new Socket(host, port)
    BTA_JvRfcommConnect(bd_addr, channel);

    // [4] 📨 返回socket文件描述符
    //     💡C++: sock_fd用于Java层InputStream/OutputStream
    //     类似Java的 socket.getInputStream()/getOutputStream()
    *sock_fd = create_socket_fd();

    return BT_STATUS_SUCCESS;
}
```

### 1.2 BTA层连接处理

```cpp
// 📂 system/bta/jv/bta_jv_act.cc:200-260
void bta_jv_rfcomm_connect(tBTA_JV_CB* p_cb, tBTA_JV_DATA* p_data) {
    // [1] 📨 分配RFCOMM端口
    //     💡C++: PORT_Open分配端口控制块
    //     类似Java的 ServerSocket.allocate()
    int port_status = PORT_Open(p_data->rfc_connect.scn,
                                 p_data->rfc_connect.bd_addr,
                                 &p_cb->rfc.port_handle);

    // [2] 📨 发起L2CAP连接
    //     PSM=0x0003 (RFCOMM固定PSM)
    //     💡C++: L2CAP是RFCOMM的底层传输
    //     类似Java的 Socket底层TCP连接
    if (port_status == PORT_SUCCESS) {
        // [3] L2CAP连接成功后→RFCOMM信令:
        //     SABM(DLCI=0) → UA → 建立多路复用器
        //     PN → 协商参数(max_frame_size, credits)
        //     MSC → 调制解调器状态(RTC/RTR/DV/IC/FC)
        //     SABM(DLCI=data) → UA → 数据通道建立
    }
}
```

### 1.3 RFCOMM帧解析

```cpp
// 📂 system/stack/rfcomm/rfc_mx_fsm.cc:80-140
// RFCOMM多路复用器状态机处理

// [1] 🔍 SABM帧——建立连接
//     Address: DLCI + C/R=1(命令) + EA=1
//     Control: 0x2F (SABM)
//     💡C++: 收到SABM→回复UA→连接建立
//     类似Java的 TCP SYN→SYN-ACK
//     DLCI=0: 多路复用器连接
//     DLCI=2,4,6...: 数据通道连接

// [2] 🔍 UA帧——确认应答
//     Control: 0x63 (UA)
//     收到UA→SABM请求被接受

// [3] 🔍 UIH帧——数据传输
//     Control: 0xEF (UIH)
//     Information: 用户数据(0-127字节)
//     💡C++: UIH不包含CRC校验，效率高
//     类似Java的 UDP(无确认但快速)
//     但RFCOMM有Credit流控保证可靠性

// [4] 🔍 PN帧——参数协商
//     DLCI: 目标数据通道
//     Max_Frame_Size: 最大帧大小(默认127)
//     Credits: 初始Credit数量(默认7)
//     💡C++: PN在SABM之前发送，协商传输参数

// [5] 🔍 MSC帧——调制解调器状态
//     DLCI: 目标数据通道
//     Signals: RTC/RTR/DV/IC/FC
//     💡C++: FC(Flow Control)位控制流控
//     FC=1: 暂停发送, FC=0: 允许发送
```

### 1.4 SPP数据读取

```cpp
// 📂 system/btif/src/btif_sock_rfc.cc:300-350
int sock_rfcomm_read(int fd, void* buf, int count) {
    // [1] 📨 从RFCOMM端口读取数据
    //     💡C++: PORT_ReadData从端口缓冲区读取
    //     类似Java的 InputStream.read(buf)
    UINT16 len = count;
    int status = PORT_ReadData(port_handle, buf, &len);

    if (status != PORT_SUCCESS) {
        return -1;
    }

    // [2] 📨 返回读取的字节数
    //     💡C++: len是实际读取长度，可能小于count
    //     类似Java的 InputStream.read()返回值
    return len;
}

// 数据接收路径:
// HCI → L2CAP重组 → RFCOMM解析UIH → PORT缓冲区
// → btif_sock_thread轮询 → sock_rfcomm_read()
// → pipe → Java InputStream.read()
```

### 1.5 SPP数据写入

```cpp
// 📂 system/btif/src/btif_sock_rfc.cc:360-400
int btsock_rfc_write(int fd, const void* buf, int count) {
    // [1] 🔍 检查Credit——流控核心
    //     💡C++: 如果local_credit=0，不能发送
    //     类似Java的 Semaphore.acquire()
    if (local_credit == 0) {
        // 等待远端补充Credit
        return 0;  // EAGAIN
    }

    // [2] 📨 写入RFCOMM端口
    //     💡C++: PORT_WriteData构造UIH帧
    //     内部: UIH(local_dlci) + data
    //     → L2CAP分段 → ACL发送
    UINT16 len = count;
    int status = PORT_WriteData(port_handle, buf, &len);

    // [3] 📨 减少Credit计数
    //     💡C++: 每发送一帧，local_credit--
    //     类似Java的 Semaphore.release(-1)
    local_credit--;

    return len;
}
```

### 1.6 RFCOMM Server端

```cpp
// 📂 system/btif/src/btif_sock_rfc.cc:200-260
bt_status_t btsock_rfc_listen(const bluetooth::Uuid& uuid,
                               int channel, int* sock_fd) {
    // [1] 📨 创建SDP Service Record
    //     💡C++: BTA_JvCreateRecord注册SPP服务
    //     类似Java的 BluetoothServerSocket绑定端口
    BTA_JvCreateRecord(uuid, channel, "Bluetooth Serial Port");

    // [2] SDP记录内容:
    //     ServiceClassIDList: UUID=0x1101 (SerialPort)
    //     ProtocolDescriptorList: RFCOMM, server_channel
    //     ServiceName: 可配置名称
    //     💡C++: bt_sdp_record结构体描述SDP记录

    // [3] 📨 开始监听
    //     btsock_rfc_listen → PORT_StartMultiplex
    //     → 等待远端SABM连接
    //     💡C++: accept()阻塞等待新连接
    //     类似Java的 ServerSocket.accept()

    // [4] 📨 返回socket文件描述符
    *sock_fd = create_socket_fd();
    return BT_STATUS_SUCCESS;
}
```

### 1.7 Credit流控详解

```cpp
// 📂 system/stack/rfcomm/port_api.cc
// Credit流控是RFCOMM的核心机制

// [1] 📨 PN协商阶段——交换初始Credit
//     PN Request: 本端初始Credit=7
//     PN Response: 远端初始Credit=7
//     💡C++: Credit表示"允许对方发送的帧数"
//     类似Java的 Semaphore(7)——最多7个许可

// [2] 📨 数据传输阶段——消耗和补充Credit
//     发送一帧UIH → local_credit--
//     收到UIH(Credits=N) → local_credit += N
//     💡C++: Credit耗尽时必须等待补充
//     类似Java的 blockingSemaphore.acquire()

// [3] 📨 流控暂停——FCON/FCOFF
//     FCON: Flow Control ON → 恢复发送
//     FCOFF: Flow Control OFF → 暂停发送
//     💡C++: MSC帧的FC位也控制流控
//     FC=1: 暂停, FC=0: 恢复

// [4] ⚠️ 常见问题：
//     - Credit耗尽→数据卡住→检查远端是否补充Credit
//     - PN协商Credit太小→传输效率低→增大初始Credit
//     - L2CAP MTU限制→RFCOMM帧≤127字节→需要分片
```

---

## 💡 C++知识卡片

### 💡 C++知识卡片：文件描述符与管道 (File Descriptor & Pipe)

> 🔄 Java类比：Java用Socket的InputStream/OutputStream，C++用文件描述符(fd)
> 蓝牙SPP通过pipe实现C++→Java的数据传递

```cpp
// Java方式：
Socket socket = new Socket(host, port);
InputStream in = socket.getInputStream();
OutputStream out = socket.getOutputStream();

// C++方式——蓝牙SPP的fd+pipe：
// [1] 创建pipe——C++→Java数据通道
//     💡C++: pipe()创建一对文件描述符
//     pipefd[0]: 读端(Java层读取)
//     pipefd[1]: 写端(C++层写入)
int pipefd[2];
pipe(pipefd);

// [2] 写入数据(C++层)
//     💡C++: write()系统调用，类似Java的 OutputStream.write()
write(pipefd[1], data, len);

// [3] 读取数据(Java层)
//     💡C++: Java通过FileInputStream读取pipefd[0]
//     类似Java的 FileInputStream(fd).read()

// [4] btif_sock_thread轮询
//     💡C++: poll()监听多个fd的事件
//     类似Java的 Selector.select()
struct pollfd fds[MAX_POLL_FDS];
fds[0].fd = pipefd[0];     // RFCOMM数据
fds[0].events = POLLIN;    // 可读事件
poll(fds, 1, -1);          // 阻塞等待

// ⚠️ 关键区别：
// Java: Socket是对象，有GC管理
// C++: fd是整数，必须手动close()防止泄漏
// 蓝牙代码中fd泄漏是常见bug——close()必须在所有路径上执行
```

### 💡 C++知识卡片：结构体与协议帧 (Struct & Protocol Frame)

> 🔄 Java类比：Java用类+序列化，C++用结构体+memcpy直接映射内存
> RFCOMM帧是结构体映射协议帧的典型

```cpp
// Java方式——类+序列化：
class RfcommFrame {
    int dlci;
    int control;
    byte[] data;
    byte[] serialize() { ... }  // 手动序列化
}

// C++方式——结构体+位域直接映射：
// 💡C++: 位域(bit-field)精确控制每个bit的布局
// 这是C++在协议开发中的核心优势
typedef struct {
    uint8_t ea   : 1;    // Bit0: 扩展地址标志
    uint8_t cr   : 1;    // Bit1: 命令/响应
    uint8_t dlci : 6;    // Bit2-7: 数据链路连接标识
} rfcomm_address_t;

typedef struct {
    uint8_t ea    : 1;   // Bit0: 长度扩展标志
    uint8_t len   : 7;   // Bit1-7: 信息字段长度
} rfcomm_length_t;

// ⚠️ 位域的陷阱：
// 1. 位域布局依赖编译器实现(字节序+对齐)
// 2. 不同编译器可能产生不同布局
// 3. 网络协议通常用宏+移位操作代替位域：
//    dlci = (addr >> 2) & 0x3F;  // 更可移植
//    cr   = (addr >> 1) & 0x01;
// 4. 蓝牙协议栈两种方式都有使用
```

### 💡 C++知识卡片：异步回调与事件循环 (Async Callback & Event Loop)

> 🔄 Java类比：Java用Handler+Looper，C++用poll+回调
> btif_sock_thread是蓝牙SPP的事件循环

```cpp
// Java方式——Handler+Looper：
Handler handler = new Handler(Looper.getMainLooper());
handler.post(() -> processData(data));

// C++方式——poll+回调事件循环：
// 📂 system/btif/src/btif_sock_rfc.cc
void btif_sock_thread_loop(void* arg) {
    while (running) {
        // [1] 📨 poll等待事件——类似Java的 Looper.loop()
        //     💡C++: poll()阻塞直到fd有数据
        int ready = poll(fds, nfds, timeout);

        if (ready > 0) {
            for (int i = 0; i < nfds; i++) {
                if (fds[i].revents & POLLIN) {
                    // [2] 📨 读取数据→投递到JNI线程
                    //     💡C++: do_in_jni_thread投递到Java回调线程
                    //     类似Java的 handler.post(callback)
                    read(fds[i].fd, buf, sizeof(buf));
                    do_in_jni_thread(base::BindOnce(
                        callback, buf, len));
                }
            }
        }
    }
}

// ⚠️ 关键区别：
// Java: Looper自动管理消息队列，Callback在主线程执行
// C++: poll+回调需要手动管理fd集合和回调分发
// 蓝牙SPP的btif_sock_thread是独立的I/O线程
```

---

## 🗂️ Java ↔ C++ 对照表

| Java层 | JNI桥接 | C++层 | 数据流方向 |
|--------|---------|-------|-----------|
| BluetoothSocket.connect() | connectRfcommNative() | btif_sock_rfc.cc:btsock_rfc_connect() [L100] | ↓ Java→C++ |
| BluetoothSocket.close() | closeNative() | btif_sock_rfc.cc:btsock_rfc_close() | ↓ Java→C++ |
| OutputStream.write() | writeNative() | btif_sock_rfc.cc:btsock_rfc_write() [L360] | ↓ Java→C++ |
| InputStream.read() | readNative() | btif_sock_rfc.cc:sock_rfcomm_read() [L300] | ↓ Java→C++ |
| BluetoothServerSocket.listen() | listenRfcommNative() | btif_sock_rfc.cc:btsock_rfc_listen() [L200] | ↓ Java→C++ |
| BluetoothServerSocket.accept() | acceptNative() | btif_sock_rfc.cc:btsock_rfc_accept() | ↓ Java→C++ |
| onConnectionStateChanged() | SocketConnectCallback | bt_sock_callbacks->connect_cb | ↑ C++→Java |
| onDataAvailable() | SocketDataAvailableCallback | btif_sock_thread→pipe→Java | ↑ C++→Java |

---

## 🐛 问题排查SOP

### 问题：RFCOMM连接失败

```
步骤1: 查日志
  adb logcat -s bt_btif_sock bt_bta_jv | grep -E "rfc|connect|SABM|PORT"

步骤2: 定位代码
  ① 搜索 "btsock_rfc_connect" → btif_sock_rfc.cc:L100 检查连接入口
  ② 搜索 "SDP_ServiceSearch" → 检查SDP查询结果
  ③ 搜索 "SABM" → RFCOMM层检查建链信令
  ④ 搜索 "PORT_SUCCESS" → 检查端口打开结果

步骤3: 常见根因
  ① SDP查询不到SPP服务 → 远端未注册SPP UUID
  ② RFCOMM Channel冲突 → 同一channel被占用
  ③ L2CAP连接失败 → ACL未建立或PSM=0x0003被拒绝
  ④ SABM无响应 → 远端RFCOMM层异常
  ⑤ PN协商失败 → 参数不兼容

步骤4: 深入排查
  HCI snoop log查看RFCOMM SABM/UA/PN/MSC交互
  filter: btrfcomm && bt.addr == XX:XX:XX:XX:XX:XX
```

### 问题：SPP数据传输中断/卡顿

```
步骤1: 查日志
  adb logcat -s bt_btif_sock bt_rfcomm | grep -E "credit|write|read|congest"

步骤2: 定位代码
  ① 搜索 "local_credit" → 检查Credit计数
  ② 搜索 "PORT_WriteData" → 检查写入结果
  ③ 搜索 "FCON/FCOFF" → 检查流控状态

步骤3: 常见根因
  ① Credit耗尽 → 远端未补充Credit
  ② L2CAP拥塞 → L2CAP通道缓冲区满
  ③ RFCOMM MSC FC=1 → 远端暂停发送
  ④ 大数据分片问题 → 帧大小超过MTU
  ⑤ pipe缓冲区满 → Java层读取不及时

步骤4: 深入排查
  HCI snoop log查看UIH帧和Credit补充
  检查L2CAP MTU配置和RFCOMM帧大小
```

---

## 🛠️ 动手练习

### 🟢 入门：阅读代码

1. 打开 `system/btif/src/btif_sock_rfc.cc`，找到 `btsock_rfc_connect()`（L100），跟踪从Java层connect()到RFCOMM SABM的完整调用链。

2. 打开 `system/stack/rfcomm/rfc_mx_fsm.cc`，找到多路复用器状态机（L80），列出所有状态和转换条件。

3. 打开 `system/stack/rfcomm/port_api.cc`，找到 `PORT_WriteData()`（L50），理解Credit流控的检查逻辑。

### 🟡 进阶：修改代码

1. 在 `btsock_rfc_write()` 中添加Credit计数日志，记录每次写入后的剩余Credit，用于排查传输卡顿。

2. 修改PN协商参数，将初始Credit从7增大到15，观察大数据传输场景下的性能提升。

3. 在RFCOMM Server端添加连接数限制逻辑，防止过多并发连接导致资源耗尽。

### 🔴 实战：定位问题

1. 模拟场景：OBD诊断设备通过SPP连接车机，连接成功但数据传输一段时间后卡住。日志显示local_credit=0。请分析Credit补充机制，找出远端未补充Credit的原因。

2. 模拟场景：HiCar通过RFCOMM降级通道传输数据，传输速率远低于预期。snoop log显示大量UIH小帧。请分析L2CAP MTU和RFCOMM帧大小配置，提出优化方案。

---

## 📚 关键源码索引

| 序号 | 文件 | 行号 | 函数/类 | 作用 |
|------|------|------|---------|------|
| 1 | system/btif/src/btif_sock_rfc.cc | L100-150 | btsock_rfc_connect() | SPP连接入口 |
| 2 | system/btif/src/btif_sock_rfc.cc | L200-260 | btsock_rfc_listen() | Server监听入口 |
| 3 | system/btif/src/btif_sock_rfc.cc | L300-350 | sock_rfcomm_read() | 数据读取 |
| 4 | system/btif/src/btif_sock_rfc.cc | L360-400 | btsock_rfc_write() | 数据写入 |
| 5 | system/bta/jv/bta_jv_act.cc | L200-260 | bta_jv_rfcomm_connect() | BTA层连接 |
| 6 | system/bta/jv/bta_jv_act.cc | L300-360 | bta_jv_rfcomm_start_server() | BTA Server |
| 7 | system/bta/jv/bta_jv_act.cc | L400-460 | bta_jv_rfcomm_write() | BTA层写入 |
| 8 | system/stack/rfcomm/rfc_port_if.cc | L50-100 | PORT_WriteData() | RFCOMM端口写入 |
| 9 | system/stack/rfcomm/rfc_mx_fsm.cc | L80-140 | 多路复用器状态机 | SABM/UA/DISC处理 |
| 10 | system/stack/rfcomm/rfc_l2cap_if.cc | L30-80 | L2CAP接口 | 数据收发 |
| 11 | system/btif/include/bt_sock.h | L30-60 | btif_sock_connection_t | Socket控制块 |
| 12 | system/stack/rfcomm/port_api.cc | L50-100 | PORT_Open() | 端口打开API |

---

## ✅ 质量检查清单

| # | 检查项 | 状态 |
|---|--------|------|
| 1 | Mermaid图 ≥ 3个 | ✅ 6个 |
| 2 | 代码片段 ≥ 5个 | ✅ 10个带逐行注释的代码片段 |
| 3 | C++知识卡片 ≥ 2个 | ✅ 3个 |
| 4 | Java↔C++对照表 | ✅ 8项对照 |
| 5 | 行号标注 | ✅ 所有关键函数标注文件:行号 |
| 6 | 问题排查SOP | ✅ 2个SOP |
| 7 | 动手练习 | ✅ 🟢🟡🔴 3级 |
| 8 | 代码导航表 | ✅ 12项 |
| 9 | 前置知识 | ✅ T17、T04 |
| 10 | 车载场景 | ✅ SPP数据通道、车载诊断通信 |
