# T21 SPP/OBD设备详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：SPP Client/Server完整连接流程 | RFCOMM slot管理(Max=7) | OBD-II AT/CAN双模式 | BTA JV 7状态机 | 多SPP连接管理 | 车载OBD实战
> 待回顾问题：无

---

## 1. SPP架构总览

SPP (Serial Port Profile) 基于RFCOMM协议，提供模拟串口功能。UUID = `0x1101`。

```
Android App
  │ BluetoothSocket / BluetoothServerSocket (Java API)
  ▼
BTIF层
  │ btif_sock_rfc.cc → RFCOMM Socket管理层
  │ btif_sock_sdp.cc → SDP Service Record管理
  ▼
BTA JV层 (Java Vendor)
  │ bta_jv_act.cc → L2CAP/RFCOMM连接管理
  │ bta_jv_api.cc → 公共API入口
  ▼
Stack层
  │ port_api.cc → RFCOMM端口API
  │ rfc_port_if.cc → GSM 07.10帧处理
  ▼
L2CAP → HCI
```

**关键常量** ([btif_sock_rfc.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_sock_rfc.cc))：

```cpp
#define MAX_RFC_CHANNEL  30   // RFCOMM最大通道数(DLCI范围)
#define MAX_RFC_SESSION   7   // 最大并发RFCOMM会话数
```

---

## 2. SPP Client 连接流程（车机作为Host）

### 2.1 完整连接序列

```
阶段1: 扫描设备
  BluetoothAdapter.startDiscovery()
    → 发现目标设备（OBD/手机）
  
阶段2: SDP查询（获取RFCOMM Channel Number）
  device.createRfcommSocketToServiceRecord(UUID_SPP)
    → SDP Service Search Request (UUID=0x1101 → SPP)
    → SDP Service Attribute Request (获取ProtocolDescriptorList)
    → 解析出 RFCOMM Channel Number (SCN)
  
阶段3: 创建Socket
  btif_sock_rfc.cc: alloc_rfc_slot()
    → 分配 rfc_slot_t，创建socketpair(fd, app_fd)
    → app_fd返回给Java层(BluetoothSocket.getInputStream/OutputStream)
    → fd用于BTIF→BTA通信
  
阶段4: RFCOMM连接
  bta_jv_rfcomm_connect(sec_mask, role, remote_scn, bd_addr)
    → BTA JV层: bta_jv_rfcomm_connect() 
      → 状态: BTA_JV_ST_CL_OPENING
    → Stack: PORT_Open() → RFCOMM SABM(DLCI=X) → 等待UA
    → 状态: BTA_JV_ST_CL_OPEN (连接成功)
  
阶段5: 数据通信
  InputStream.read(byte[])  ← app_fd ← fd ← uipc ← RFCOMM
  OutputStream.write(byte[]) → app_fd → fd → uipc → RFCOMM
```

### 2.2 rfc_slot_t 管理

源码：[btif_sock_rfc.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_sock_rfc.cc)

```cpp
struct rfc_slot_t {
    int id;                    // Slot ID
    RawAddress remote_addr;    // 远端地址
    uint16_t security;         // 安全级别
    uint8_t scn;              // Server Channel Number
    Uuid service_uuid;        // 服务UUID(SPP=0x1101)
    int fd;                   // BTIF端socket fd
    int app_fd;               // App端socket fd(给Java)
    uint16_t rfc_handle;      // RFCOMM handle
    uint16_t rfc_port_handle; // RFCOMM port handle
};
```

**RFCOMM Slot分配**（最多7个并发）：
```cpp
alloc_rfc_slot() {
    1. find_free_slot() → 在 rfc_slots[MAX_RFC_SESSION] 中找空闲
    2. socketpair(AF_LOCAL, SOCK_STREAM, 0, sv) → 创建fd对
    3. fd = sv[0];  app_fd = sv[1];
    4. 返回slot pointer
}
```

### 2.3 SDP Service Record注册

源码：[btif_sock_sdp.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_sock_sdp.cc)

```cpp
static int add_spp_sdp(const char* name, const int channel) {
    // 创建SPP SDP Record:
    //   Protocol: L2CAP + RFCOMM(channel)
    //   Service Class: UUID_SERVCLASS_SERIAL_PORT (0x1101)
    //   Profile Descriptor: SPP v1.02
    //   Service Name: name参数
}
```

---

## 3. SPP Server 流程（车机作为Device监听）

### 3.1 Server连接序列

```
阶段1: 创建ServerSocket + 注册SDP
  BluetoothServerSocket = adapter.listenUsingRfcommWithServiceRecord(name, UUID_SPP)
    → btif_sock_rfc.cc: 分配slot
    → SDP: add_spp_sdp() → 注册Service Record(含RFCOMM Channel)
    → RFCOMM: 开始监听分配的SCN
    → 状态: BTA_JV_ST_SR_LISTEN
  
阶段2: 等待客户端连接
  BluetoothServerSocket.accept()
    → 阻塞等待RFCOMM连接
    → 客户端SDP查询 → 获取Channel → RFCOMM SABM → UA
  
阶段3: 接受连接
  状态: BTA_JV_ST_SR_OPEN
    → 返回 BluetoothSocket 给 App
    → InputStream/OutputStream 就绪
  
阶段4: 双向数据通信
  与SPP Client相同
```

### 3.2 Android API使用

```java
// 车机作为Server(telnet/调试/升级)
BluetoothServerSocket serverSocket = adapter
    .listenUsingRfcommWithServiceRecord("OBDServer", 
        UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"));

while (true) {
    BluetoothSocket socket = serverSocket.accept(); // 阻塞等待
    InputStream in = socket.getInputStream();
    OutputStream out = socket.getOutputStream();
    // ... 处理数据
}
```

---

## 4. BTA JV层（Java Vendor）

### 4.1 7状态连接状态机

源码：[bta_jv_int.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/jv/bta_jv_int.h)

```cpp
enum {
    BTA_JV_ST_NONE = 0,        // 未初始化
    BTA_JV_ST_CL_OPENING,      // Client打开中
    BTA_JV_ST_CL_OPEN,         // Client已打开
    BTA_JV_ST_CL_CLOSING,      // Client关闭中
    BTA_JV_ST_SR_LISTEN,       // Server监听中
    BTA_JV_ST_SR_OPEN,         // Server已接受连接
    BTA_JV_ST_SR_CLOSING       // Server关闭中
};
```

**Client路径**：`NONE → CL_OPENING → CL_OPEN → CL_CLOSING → NONE`
**Server路径**：`NONE → SR_LISTEN → SR_OPEN → SR_CLOSING → NONE`

### 4.2 BTA JV关键API

源码：[bta/include/bta_jv_api.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/include/bta_jv_api.h)

```cpp
// RFCOMM
void bta_jv_rfcomm_connect(...);      // Client发起连接
void bta_jv_rfcomm_close(...);        // 关闭连接
void bta_jv_rfcomm_start_server(...); // Server开始监听
void bta_jv_rfcomm_stop_server(...);  // Server停止监听

// L2CAP (直接L2CAP连接，不用RFCOMM)
void bta_jv_l2cap_connect(...);
void bta_jv_l2cap_start_server(...);

// SDP
void bta_jv_start_discovery(...);     // 启动SDP查询
void bta_jv_create_record(...);       // 创建SDP Record
void bta_jv_delete_record(...);       // 删除SDP Record
```

---

## 5. OBD-II蓝牙诊断仪

### 5.1 OBD-II协议概述

OBD-II (On-Board Diagnostics) 是车辆诊断标准接口。

```
OBD-II物理层 (16针接口，通常在方向盘下方)
  │
  ▼
OBD-II蓝牙适配器 (ELM327/STN1110等芯片)
  │ SPP over Bluetooth (RFCOMM)
  ▼
车机/手机App
  │ 发送AT命令/OBD PID → 接收响应
```

### 5.2 两种通信模式

#### AT命令模式（ELM327兼容）

```
初始化:
  ATZ     → Reset → "ELM327 v1.5"
  ATE0    → Echo Off → "OK"
  ATL0    → Linefeed Off → "OK"
  ATSP0   → Auto Protocol → "OK"

读取数据:
  ATS0    → 打印空格(分隔字节)
  010C    → Mode 01 PID 0C (发动机转速)
    → "41 0C 1A F8" 
    → 解析: 41=Mode01响应, 0C=PID, 1AF8=6904, 6904/4=1726 RPM

  ATS1    → 打印额外信息
  010D    → Mode 01 PID 0D (车速)
    → "41 0D 42" → 0x42=66 km/h

关闭:
  ATPC    → Protocol Close
```

#### CAN模式（直接CAN通信）

```
直接发送CAN帧:
  11-bit ID: 0x7DF (OBD请求)
  29-bit ID: 0x18DB33F1 (扩展CAN)
  
请求:
  CAN ID=0x7DF, Data=[02 01 0D 00 00 00 00 00]
  
响应:
  CAN ID=0x7E8, Data=[03 41 0D 42 00 00 00 00]
  → 0x42 = 66 km/h
```

### 5.3 常用OBD-II PID速查

| Mode | PID | 参数 | 公式 |
|------|-----|------|------|
| 01 | 0C | 发动机转速 | ((A*256)+B)/4 RPM |
| 01 | 0D | 车速 | A km/h |
| 01 | 05 | 冷却液温度 | A-40 °C |
| 01 | 0F | 进气温度 | A-40 °C |
| 01 | 10 | MAF空气流量 | ((A*256)+B)/100 g/s |
| 01 | 11 | 节气门位置 | A/2.55 % |
| 01 | 04 | 发动机负荷 | A/2.55 % |
| 01 | 0B | 进气歧管压力 | A kPa |
| 01 | 0A | 燃油压力 | A*3 kPa |
| 01 | 2F | 燃油剩余 | A/2.55 % |
| 03 | — | 故障码(DTC) | 读取所有存储故障码 |
| 09 | 02 | VIN码 | 17位车架号 |

### 5.4 车载OBD蓝牙连接实战

```
1. 扫描OBD设备:
   device.createRfcommSocketToServiceRecord(
       UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"));
   socket.connect();

2. 发送初始化:
   socket.getOutputStream().write("ATZ\r".getBytes());
   读取响应: socket.getInputStream() 读取 "ELM327 v1.5"

3. 定时读取数据:
   每500ms读取一次:
     发送 "010C\r" → 读取响应 → 解析RPM
     发送 "010D\r" → 读取响应 → 解析车速
```

**常见问题**：
- OBD响应不完整 → 用ATS0+ATS1调试 → 检查响应分隔符
- 波特率不匹配 → 发送ATPP命令协商
- 连接后无数据 → 检查OBD设备是否CAS认证（部分车型需要）

---

## 6. 多SPP连接管理

### 6.1 连接限制

```
MAX_RFC_SESSION = 7    → 最多7个并发RFCOMM设备
MAX_RFC_CHANNEL = 30   → 最多30个RFCOMM DLCI(逻辑通道)

每个设备可占用1个或多个DLCI
  单SPP: 1个DLCI
  带Audio: 1个SPP DLCI + 1个HFP DLCI
```

### 6.2 多设备管理策略

```cpp
// rfc_slots 数组管理
rfc_slot_t rfc_slots[MAX_RFC_SESSION];

// 分配策略
int alloc_slot_idx() {
    for (int i = 0; i < MAX_RFC_SESSION; i++) {
        if (rfc_slots[i].state == SLOT_FREE) return i;
    }
    return -1;  // 无可用槽位
}

// 数据分发
void on_data(uint16_t rfc_handle, uint8_t* data, int len) {
    int slot = find_slot_by_handle(rfc_handle);
    write(slots[slot].fd, data, len);  // → 通过socketpair传给App
}
```

**多OBD设备场景**：
```
车机同时连接:
  Slot 0: OBD诊断仪 → 定时读取车速/RPM/故障码
  Slot 1: TPMS (胎压) → 轮询胎压/温度
  Slot 2: 行车记录仪 SPP → 传输视频缩略图
```

### 6.3 数据分流

```java
// 每个Socket独立线程
Map<String, BluetoothSocket> sockets = new HashMap<>();
Map<String, Thread> readers = new HashMap<>();

for (BluetoothDevice device : devices) {
    BluetoothSocket socket = connectSPP(device);
    sockets.put(device.getAddress(), socket);
    
    Thread reader = new Thread(() -> {
        byte[] buffer = new byte[1024];
        while (socket.isConnected()) {
            int len = socket.getInputStream().read(buffer);
            handleData(device.getAddress(), buffer, len);
        }
    });
    reader.start();
    readers.put(device.getAddress(), reader);
}
```

---

## 7. SPP常见问题

### 7.1 连接被拒绝

```
现象: socket.connect() 抛出 IOException

排查:
1. Snoop → 查看 RFCOMM SABM → UA 响应
   UA未返回 → 设备不支持RFCOMM
   UA返回但随后DM → Channel不对(SDP查询的SCN不匹配)

2. 日志:
   adb logcat -s bt_btif_sock_rfcomm bt_port_api rfcomm

3. 常见原因:
   - SDP查询到的SCN与实际不匹配 → 重新SDP查询
   - 对方RFCOMM Server未启动
   - 安全级别不足(需要配对Bond但未配对)
```

### 7.2 数据传输丢包

```
现象: InputStream.read() 数据不完整

排查:
1. RFCOMM流控: 检查FCC(Flow Control Credit)是否耗尽
2. L2CAP MTU: 检查L2CAP Configuration Request的MTU值
3. 应用层: 确保read()使用正确的缓冲区大小

解决:
- 使用更大的MTU (默认672 → 可设到1017)
- 应用层添加帧头+长度+校验(类似TLV)
```

### 7.3 端口冲突

```
现象: 连接第2个SPP设备时第1个断线

原因: MAX_RFC_SESSION=7, 超出限制时关闭旧连接

排查:
adb logcat -s bt_btif_sock_rfcomm
日志: "All slots are full"

解决:
- 主动管理连接池, 及时关闭不用的连接
- 使用同一个RFCOMM DLCI的多路复用(不同SCN)
```

---

## 8. RFCOMM/SPP调试速查

### 日志TAG
```bash
# SPP全链路日志
adb logcat -s bt_btif_sock_rfcomm bt_btif_sock_sdp bt_port_api rfcomm
```

### Snoop过滤器
```
# RFCOMM帧 (HFP + SPP)
btrfcomm

# SPP的SDP查询
btsdp && bt.addr == XX:XX:XX:XX:XX:XX

# 特定L2CAP CID (RFCOMM)
btl2cap.cid == 0x0040
```

### 常见OBD命令调试

```bash
# 直接测试OBD连接
adb shell
cat /dev/ttyHS0  # 假设OBD串口, 但蓝牙OBD用SPP

# logcat过滤OBD
adb logcat | grep -i "obd\|ELM\|010C\|010D"
```