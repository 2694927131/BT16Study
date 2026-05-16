# T18_RFCOMM_SPP通道详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. RFCOMM 帧格式: Address(DLCI+C/R+EA)+Control+Length+Info+FCS→一个L2CAP通道支持30个DLCI多路复用
2. 连接流程: SDP查询SPP UUID→RFCOMM Channel→btif_sock_rfc→BTA_JvRfcommStart→L2CAP连接→SABM/DISC/UA→RFCOMM建立→PN/MSC协商→数据通道
3. SPP: InputStream/OutputStream→RFCOMM Data+Credit流控→L2CAP分段→ACL数据传输
4. RFCOMM Server(车机监听): createRfcommSocket→listenViaServiceRecord→SDP注册→accept
5. 车载互联: HiCar RFCOMM数据通道、CarLink通信、OBD诊断 AT over RFCOMM

## 详细笔记

### 一、RFCOMM协议基础

**帧格式 (基于GSM 07.10):**
```
┌─────────┬─────────┬─────────┬──────────────┬──────┬─────┐
│ Address │ Control │ Length  │ Information  │ FCS  │ ... │
│ (1-2B)  │ (1B)    │ (1-2B)  │ (0-127 bytes)│ (1B) │     │
└─────────┴─────────┴─────────┴──────────────┴──────┴─────┘

Address field: DLCI(6bit)+C/R(1bit)+EA(1bit)
Control: 6种类型:
  - SABM(0x2F): 建立异步平衡模式 → 连接请求
  - UA(0x63): 未确认应答 → 接受连接
  - DISC(0x43): 断开 → 拆链
  - DM(0x0F): 断开模式 → 拒绝
  - UIH(0xEF): 未确认信息 → 数据(无CRC)+Length标识
  - UI(0x03): 无编号帧 → 控制消息
```

**DLCI**: 6bit→0-60共60个可寻址通道→实际支持30个双向通道(偶数为数据,奇数为控制)

**多路复用**: 一个L2CAP PSM=0x0003通道上可承载最多30路RFCOMM DLCI

### 二、RFCOMM连接流程

```
App: BluetoothSocket.connect()
→ btif_sock_rfc.cc: btsock_rfc_connect()
  → 1. SDP 查询: 获取远端 SPP Service Record
     → UUID: 0x1101 (SPP) → RFCOMM Channel Number → PSM 0x0003
  → 2. L2CAP 连接
  → 3. RFCOMM 建立:
     DLC → SABM → ← UA → (双方各发一次)
     DLC → PN(Request) → ← PN(Response) →  (协商参数:max_frame_size, credit)
     DLC → MSC → ← MSC → (调制解调器状态, RTC/RTR/DV/IC/FC)
  → 4. 数据通道建立
→ bt_socket_connect() → BTA_JvRfcommConnect()
→ bta_jv_act.cc: bta_jv_rfcomm_connect() → PORT_Success
→ Java: connect() 返回, InputStream/OutputStream 可用
```

**btif_sock_rfc 核心结构**:
```
btif_sock_connection_t: socket → sock_rfcomm_read/sock_rfcomm_write
btif_sock_thread: 轮询端口状态 → 投递事件到 JNI 线程
```

### 三、SDP查询

```
SDP 查询 SPP Service Record:
1. ServiceClassIDList → UUID=0x1101 (SerialPort)
2. ProtocolDescriptorList → RFCOMM → channel_id
3. BT_ADDR → 确认目标设备

btif_sock_rfc → btsock_rfc_search → BTA_JvGetRecords → SDP_ServiceSearch
→ RFCOMM channel number → 填充 bt_sockaddr_rfcomm_t.client_channel
```

### 四、SPP数据传输

**from 蓝牙→应用**:
```
RFCOMM Data帧 → btif_sock_thread 解析 → sock_rfcomm_read()
→ HIDL_event → 写pipe→Java InputStream.read() → 传输到应用层
```

**应用→蓝牙**:
```
OutputStream.write(data)
→ btsock_rfc_write(data)
→ RFCOMM: UIH(local_dlci) + data
→ L2CAP 分段 → ACL 发送
```

**流控机制**:
- Credit-based: 每次 PN 协商初始 credit (默认7)
- Local credit 耗尽 → 暂停写
- Remote FCON/FCOFF → 从端口协商
- RFCOMM MSC: FC bit 控制

**大数据优化**:
- L2CAP MTU: 最大 1691 bytes (bt_target.h)
- RFCOMM 帧: 建议 ≤ 127 bytes → 多帧分片
- 应用层: 写缓冲区重组

### 五、RFCOMM Server (车机监听)

```
createRfcommSocketToServiceRecord(UUID)
→ listenViaServiceRecord()
  → 1. 创建 ServerSocket → bind
  → 2. BTA_JvCreateRecord() → SDP 注册
     → ServiceClassIDList: UUID
     → ProtocolDescriptorList: RFCOMM, server_channel
     → ServiceName: 可配置
  → 3. 监听: btsock_rfc_listen() → 等待 accept
→ accept() → 阻塞等待 → 新连接 → Java Socket
```

**SDP记录结构**:
```
bt_sdp_record:
- service_uuid: SPP UUID
- service_name: "Bluetooth Serial Port"
- rfcomm_channel: dynamic
```

### 六、车载互联 RFCOMM 应用

- **HiCar**: BLE 握手后通过 RFCOMM 传输控制、音频流 (当WiFi不可用时)
- **CarLink**: RFCOMM 作为数据通道 → 视频流控制、触摸事件上报
- **OBD 诊断**: ELM327/OBD-II 协议 → AT 命令 through RFCOMM → ATZ/ATE0/ATSP0/ATMA
- **Vendor AT**: 车机专用扩展 AT over RFCOMM

### 七、常见问题

| 问题 | 原因 | 定位 |
|------|------|------|
| RFCOMM连接失败 | SDP查询不到→无SPP服务/channel冲突 | Snoop btsdp + btrfcomm SABM |
| 传输中断 | RFCOMM MSC credit耗尽/L2CAP断开 | logcat bt_btif_sock |
| 端口冲突 | 同一RFCOMM channel被占用 | SDP重新分配
| 大数据慢 | Credit negotiation 不足 | PN negotiate higher credit |