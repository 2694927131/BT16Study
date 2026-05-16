# T34 SDP与L2CAP详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：
> 1. SDP是蓝牙**服务发现**协议，通过7种PDU类型实现ServiceSearch→ServiceAttr→ServiceSearchAttr三层查询，数据元素采用(Tag|Size)+Value的TLV编码
> 2. L2CAP是**链路适配层**协议，负责将上层数据拆分为小于MTU的分片，通过CID区分不同上层协议通道，提供Basic/ERTM/Streaming/LE CoC四种可靠性模式
> 3. L2CAP控制块采用CCB(通道)→LCB(链路)→CB(全局)三层树形结构，RoundRobin调度确保多通道公平性
> 4. LE Credit Based CoC(5.2)实现一对多通道+流控信用值机制，车载OTA/传感器场景重要

---

## 一、SDP (Service Discovery Protocol) 服务发现协议

### 1.1 协议栈位置与角色

```
Application层 (A2DP/HFP/PBAP/MAP/OPP...)
        ↑ 通过SDP注册服务 | 通过SDP发现服务 ↓
┌──────────────────────────────────────────┐
│  SDP 层                                   │
│  ┌──────────────────────────────────────┐│
│  │ sdp_discovery.cc  ─ 远程服务发现     ││
│  │ sdp_server.cc     ─ 本地服务请求响应 ││
│  │ sdp_db.cc         ─ 本地服务数据库   ││
│  │ sdp_utils.cc      ─ 数据元素编解码   ││
│  └──────────────────────────────────────┘│
├──────────────────────────────────────────┤
│  L2CAP (通过CID 0x0001信令通道)          │
└──────────────────────────────────────────┘
```

**核心源码文件**：
| 文件 | 路径 |
|------|------|
| sdpint.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdpint.h) |
| sdp_discovery_db.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_discovery_db.h) |
| sdpdefs.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/sdpdefs.h) |
| sdp_api.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/sdp_api.h) |
| sdp_status.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/sdp_status.h) |
| sdp_discovery.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_discovery.cc) |
| sdp_server.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_server.cc) |
| sdp_db.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_db.cc) |

---

### 1.2 PDU类型 — 服务发现的4种请求

SDP协议定义7种PDU ([sdpint.h:L51-L57](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdpint.h#L51-L57))：

| PDU ID | 名称 | 方向 | 用途 |
|--------|------|------|------|
| `0x01` | SDP_ErrorResponse | S→C | 错误响应 |
| `0x02` | **ServiceSearchReq** | C→S | 按UUID搜索服务记录句柄 |
| `0x03` | ServiceSearchRsp | S→C | 返回匹配的Record Handle列表 |
| `0x04` | **ServiceAttrReq** | C→S | 按Handle+AttrID获取属性值 |
| `0x05` | ServiceAttrRsp | S→C | 返回属性值列表 |
| `0x06` | **ServiceSearchAttrReq** | C→S | 搜索+属性查询合并（最常用） |
| `0x07` | ServiceSearchAttrRsp | S→C | 返回Handle+Attr对 |

**发现流程对比**：

```
方式A：两步法（传统）
  ① ServiceSearchReq → 获取Handle列表
  ② ServiceAttrReq   → 按Handle获取属性

方式B：一步法（推荐）
  ① ServiceSearchAttrReq → 一步获取Handle+所有属性
     (UUID搜索 + 属性过滤 + 内容直接返回)
```

**ServiceSearchAttrReq 协议格式**：

```cpp
// [sdp_discovery.cc] - 构建ServiceSearchAttrReq
static void sdp_snd_service_search_attr_req(tCONN_CB* p_ccb, uint8_t cont_len, uint8_t* p_cont) {
  BT_HDR* p_cmd = (BT_HDR*)osi_malloc(SDP_DATA_BUF_SIZE);
  p_cmd->offset = L2CAP_MIN_OFFSET;
  uint8_t* p = p_cmd->data + L2CAP_MIN_OFFSET;
  uint8_t* p_start = p;

  // PDU ID
  UINT8_TO_BE_STREAM(p, SDP_PDU_SERVICE_SEARCH_ATTR_REQ);
  // Transaction ID
  UINT16_TO_BE_STREAM(p, p_ccb->transaction_id);
  // Parameter Length (占位，稍后回填)
  UINT16_TO_BE_STREAM(p, 0);
  // UUID Sequence (DATA_ELE_SEQ of UUIDs)
  p = sdpu_build_uuid_seq(p, p_ccb->p_db->num_uuid_filters, p_ccb->p_db->uuid_filters, ...);
  // Max Attribute Byte Count
  UINT16_TO_BE_STREAM(p, 0xFFFF);
  // Attribute ID Sequence (DATA_ELE_SEQ)
  p = sdpu_build_attrib_seq(p, p_ccb->p_db->p_attr_list, p_ccb->p_db->num_attr_filters, ...);
  // Continuation (分页)
  *p++ = cont_len;
  ...
}
```

---

### 1.3 数据元素编码 (Data Element) — TLV格式

SDP每条属性都采用**DES (Data Element Sequence)** 编码 ([sdpdefs.h:L130-L140](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/sdpdefs.h#L130-L140))：

**编码格式**: `(Type高5位 | Size低3位) [Size字节] [数据]`

**描描述符类型** (Type, 高5位)：

| Type值 | 常量 | 含义 |
|--------|------|------|
| 0 | NIL_DESC_TYPE | 空值 |
| 1 | UINT_DESC_TYPE | 无符号整数 |
| 2 | TWO_COMP_INT_DESC_TYPE | 有符号整数（二进制补码） |
| 3 | UUID_DESC_TYPE | UUID |
| 4 | TEXT_STR_DESC_TYPE | 文本字符串 |
| 5 | BOOLEAN_DESC_TYPE | 布尔值 |
| 6 | DATA_ELE_SEQ_DESC_TYPE | 数据元素序列（嵌套） |
| 7 | DATA_ELE_ALT_DESC_TYPE | 数据元素替代（二选一） |
| 8 | URL_DESC_TYPE | URL字符串 |

**尺寸指示** (Size, 低3位)：

| Size值 | 常量 | 数据长度范围 |
|--------|------|------------|
| 0 | SIZE_ONE_BYTE | 1字节(仅对NIL) |
| 1 | SIZE_TWO_BYTES | 2字节(UUID16) |
| 2 | SIZE_FOUR_BYTES | 4字节(UUID32) |
| 3 | SIZE_EIGHT_BYTES | 8字节 |
| 4 | SIZE_SIXTEEN_BYTES | 16字节(UUID128) |
| 5 | SIZE_IN_NEXT_BYTE | 下1字节=长度 |
| 6 | SIZE_IN_NEXT_WORD | 下2字节=长度 |
| 7 | SIZE_IN_NEXT_LONG | 下4字节=长度 |

**编码示例**：

```
UUID16 0x110B (A2DP Sink UUID):
  字节0: (UUID_DESC_TYPE=3 << 3) | SIZE_TWO_BYTES=1 = 0x19
  字节1-2: 0x11 0x0B
  → 完整编码: 19 11 0B

数据元素序列 (含3个UUID16):
  字节0: (SEQ=6 << 3) | SIZE_IN_NEXT_BYTE=5 = 0x35
  字节1: 0x09 (序列总长9字节)
  字节2-10: 三个UUID各占3字节 (19 11 0B, 19 11 0D, ...)
```

---

### 1.4 属性体系 — 标准Attribute ID

每个服务记录包含一组属性，标准属性ID定义在 [sdpdefs.h:L35-L45](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/sdpdefs.h#L35-L45)：

| Attribute ID | 常量 | 含义 | 示例值 |
|-------------|------|------|--------|
| `0x0000` | SERVICE_RECORD_HDL | 服务记录句柄 | `0x00010001` |
| `0x0001` | **SERVICE_CLASS_ID_LIST** | 服务类UUID列表 | `{0x110B(A2DP_Sink), 0x110D(AVRCP_Target)}` |
| `0x0002` | SERVICE_RECORD_STATE | 记录状态 | `0x00000001` |
| `0x0003` | SERVICE_ID | 服务实例ID | `0x00010001` |
| `0x0004` | **PROTOCOL_DESC_LIST** | 协议栈描述（核心！） | `{L2CAP{PSM}, RFCOMM{CH}, OBEX{...}}` |
| `0x0005` | BROWSE_GROUP_LIST | 浏览组列表 | `{0x1002(PublicBrowseRoot)}` |
| `0x0006` | LANGUAGE_BASE_ATTR_ID_LIST | 语言基础属性 | `{0x656E, 0x006A, 0x0100(en+UTF-8)}` |
| `0x0009` | **BT_PROFILE_DESC_LIST** | Profile描述列表 | `{0x110B, 0x0103(A2DP v1.3)}` |
| `0x0100`+ | 自定义属性 | 服务名/描述/Provider名 | `"Car Bluetooth"` |

**PROTOCOL_DESC_LIST 结构** — 每条服务记录最重要的属性：

```
Attribute ID = 0x0004 (PROTOCOL_DESC_LIST)
Value = DATA_ELE_SEQ of:
  DATA_ELE_SEQ {                  ← 第1层协议
    UUID: 0x0100 (L2CAP)          ← 协议UUID
    UINT16: 0x0019 (PSM=25)      ← 协议参数 (AVDTP PSM)
  }
  DATA_ELE_SEQ {                  ← 第2层协议
    UUID: 0x0019 (AVDTP)          ← 协议UUID
    UINT16: 0x0103 (Version 1.3)  ← 协议参数
  }
```

**车载各Profile的SDP注册示例**：

| Profile | 第一层UUID | 参数 | 第二层UUID | 参数 |
|---------|-----------|------|-----------|------|
| A2DP Sink | L2CAP(0x0100) | PSM=0x0019 | AVDTP(0x0019) | version |
| A2DP Source | L2CAP(0x0100) | PSM=0x0019 | AVDTP(0x0019) | version |
| HFP-AG | L2CAP(0x0100) | PSM=none | RFCOMM(0x0003) | Channel=N |
| HFP-HF | L2CAP(0x0100) | PSM=none | RFCOMM(0x0003) | Channel=N |
| PBAP PSE | L2CAP(0x0100) | PSM=none | RFCOMM(0x0003) | Channel=N → OBEX |
| MAP MAS | L2CAP(0x0100) | PSM=none | RFCOMM(0x0003) | Channel=N → OBEX |

---

### 1.5 发现数据库 — tSDP_DISCOVERY_DB

[SDP发现数据库](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_discovery_db.h#L66-L78) 是客户端存储SDP搜索结果的缓冲区：

```cpp
typedef struct {
  uint16_t mem_size;      // 总缓冲区大小
  uint16_t mem_free;      // 剩余可用空间
  uint8_t* p_first_rec;   // 第一条服务记录
  uint8_t* p_free_mem;    // 空闲区指针
  uint32_t timestamp;     // 记录创建时间戳
  Uuid* uuid_filters;    // UUID过滤条件（sizeof(Uuid)=16）
  uint16_t num_uuid_filters;
  uint16_t num_attr_filters;   // 属性过滤条件
  uint16_t attr_filters[];     // 属性ID数组
} tSDP_DISCOVERY_DB;
```

**子结构 — tSDP_DISC_REC** (单个服务记录)：
```cpp
typedef struct {
  tSDP_DISC_ATTR* p_first_attr;    // 属性链表头
  tSDP_DISC_ATTR* p_next_attr;     // 迭代器指针
  bool free_pad_ptr;                // 填充信息
  uint8_t* p_sub_attr;             // 子属性设置
} tSDP_DISC_REC;
```

**子结构 — tSDP_DISC_ATTR** (单个属性)：
```cpp
typedef struct {
  tSDP_DISC_ATTR* p_next_attr;    // 链表下一个
  uint16_t attr_id;                // Attribute ID
  uint16_t attr_len_type;          // 属性长度(高12位)|类型(低4位)
  uint32_t attr_value;             // 属性值指针值
} tSDP_DISC_ATTR;
```

**查询示例** — 从Discovery DB中提取属性：
```cpp
// sdp_utils.cc - 根据Attribute ID查找值
bool SDP_FindAttributeInRec(const tSDP_DISC_REC* p_rec, uint16_t attr_id) {
  for (tSDP_DISC_ATTR* p_attr = p_rec->p_first_attr; p_attr; p_attr = p_attr->p_next_attr) {
    if (p_attr->attr_id == attr_id) {
      // 找到属性
      return true;
    }
  }
  return false;
}
```

---

### 1.6 连接控制块 — tCONN_CB

[SDP连接控制块](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdpint.h#L177-L212) 管理一次SDP会话：

```cpp
typedef struct {
  uint8_t* p_start;                   // 缓冲区起始指针
  uint16_t transaction_id;            // 事务ID（每次搜索递增）
  RawAddress device_address;          // 远程设备地址
  tSDP_DISCOVERY_DB* p_db;           // 发现数据库指针
  tSDP_DISC_CMPL_CB* p_cb;           // 搜索完成回调
  tSDP_DISC_CMPL_CB2* p_cb2;         // 搜索完成回调（新接口）
  uint32_t ticks;                     // 连接创建时间戳
  uint16_t rem_mtu_size;              // 远程MTU大小
  uint16_t request_cont_offset;       // 连续请求偏移
  tSDP_STATE_TBL state;               // 连接状态
  uint8_t sdp_disc_connected;         // 连接标志
} tCONN_CB;
```

---

### 1.7 完整调用链 — App→Native

```
Java层 SdpManager.java
  └→ sdpSearch(address, uuid) → 加入搜索队列
       └→ SdpManagerNativeInterface.sdpSearchNative()

JNI层 com_android_bluetooth_sdp.cpp
  └→ sdp_interface->sdp_search(address, uuid_list)

BTIF层 btif_sdp.cc
  └→ btif_sdp_search → BTA_SdpSearch()

BTA层 bta_sdp/
  └→ bta_sdp_search → SDP_ServiceSearchRequest()

Stack层 sdp_discovery.cc
  └→ sdp_snd_service_search_attr_req()
       └→ L2CA_DataWrite(CID=L2CAP_SIGNALLING_CID)
          (SDP通过L2CAP信令通道传输)

// 响应回调 — 反向链路：
Stack层 sdp_server.cc → sdp_process_service_search_attr_req()
  └→ BTA → BTIF → JNI Callback → Java Intent广播
```

---

### 1.8 车载SDP关键场景

| 场景 | SDP操作 | 关键UUID | 常见问题 |
|------|---------|---------|---------|
| **车机发现手机A2DP** | ServiceSearchAttrReq→UUID 0x110B | A2DP_Sink=0x110B, A2DP_Source=0x110A | SDP Record PSM不是标准值25 |
| **车机发现手机HFP** | ServiceSearchAttrReq→UUID 0x111E/0x111F | AG=0x111F, HF=0x111E | RFCOMM Channel不是标准值 |
| **车机发现手机PBAP** | ServiceSearchAttrReq→UUID 0x1130 | PSE=0x1130 | SDP中missing PBAP v1.2特性位 |
| **车机发现手机MAP** | ServiceSearchAttrReq→UUID 0x1132 | MAS=0x1132 | SDP中missing MAP version→没有SMS能力 |
| **手机发现车机服务** | ServiceSearchAttrReq→车机所有服务 | 全部Profile UUID | 车机SDP未能正确列出所有服务 |

---

## 二、L2CAP (Logical Link Control and Adaptation Protocol)

### 2.1 协议栈位置与角色

```
┌─────────────────────────────────────────┐
│  RFCOMM / AVDTP / AVRCP / ATT / SMP     │  上层协议
├─────────────────────────────────────────┤
│  L2CAP (Logical Link Control &         │
│         Adaptation Protocol)            │
│  ┌─────────────────────────────────────┐│
│  │ 通道多路复用 (CID)                   ││
│  │ 分片与重组 (SAR)                     ││
│  │ 协议复用 (PSM区分上层协议)           ││
│  │ QoS / 流控 / ERTM重传               ││
│  └─────────────────────────────────────┘│
├─────────────────────────────────────────┤
│  HCI ACL (Asynchronous Connection-Less) │  下层链路
└─────────────────────────────────────────┘
```

**核心源码文件**：
| 文件 | 路径 |
|------|------|
| l2c_int.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_int.h) |
| l2cdefs.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h) |
| l2c_csm.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_csm.cc) |
| l2c_fcr.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_fcr.cc) |
| l2cap_interface.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cap_interface.h) |
| l2c_link.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_link.cc) |
| l2c_utils.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_utils.cc) |

---

### 2.2 帧结构

```
┌──────────────────────────────────────────────────┐
│ Basic L2CAP Frame (无FCS)                         │
│ ┌──────────┬──────────┬──────────┬──────────────┐│
│ │ Length(2)│ CID(2)   │ Payload  │              ││
│ │ 小端序   │ 通道ID   │ (≤MTU)   │              ││
│ └──────────┴──────────┴──────────┴──────────────┘│
├──────────────────────────────────────────────────┤
│ Standard L2CAP Frame (含FCS+Control)              │
│ ┌──────────┬──────────┬──────────┬─────┬────────┐│
│ │ Length(2)│ CID(2)   │ Control  │ FCS │ Payload│ │
│ │          │          │ Word(2/4)│ (2) │        │ │
│ └──────────┴──────────┴──────────┴─────┴────────┘│
│ Control Word bits (ERTM模式):                     │
│ ┌──────────┬──────────┬──────────┬──────────────┐│
│ │ SAR(2)   │ ReqSeq(6)│ F(1)     │ TxSeq(6)  R(1)││
│ └──────────┴──────────┴──────────┴──────────────┘│
└──────────────────────────────────────────────────┘
```

**SAR (Segmentation And Reassembly) 分段指示** ([l2cdefs.h:L488-L498](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L488-L498))：

| SAR值 | 常量 | 含义 |
|-------|------|------|
| `0x0000` | UNSEG_SDU | 不分段的完整SDU |
| `0x4000` | START_SDU | 分段SDU的第一片 |
| `0x8000` | END_SDU | 分段SDU的最后一片 |
| `0xC000` | CONT_SDU | 分段SDU的中间片 |

**S帧类型（监督帧）**：
| 值 | 常量 | 含义 |
|----|------|------|
| `0x0000` | SUP_RR | Receiver Ready（确认接收） |
| `0x0001` | SUP_REJ | Reject（拒绝，请求选择性重传） |
| `0x0002` | SUP_RNR | Receiver Not Ready |
| `0x0003` | SUP_SREJ | Selective Reject |

**序列号范围**: 0-63 (`L2CAP_FCR_SEQ_MODULO = 0x3F`)，6bit窗口

**默认MTU**: `L2CAP_DEFAULT_MTU = 672` ([l2cdefs.h:L402](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L402))

**SDU最大长度**: Classic ≈ 8080, LE = 0xFFFF ([l2cdefs.h:L484-L486](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L484-L486))

---

### 2.3 CID体系 — 通道标识

[CID](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L306-L315) 长度为16位，分为固定CID和动态CID：

**固定CID (0x0001-0x003F)**：

| CID | 名称 | 用途 | 适用传输 |
|-----|------|------|---------|
| `0x0001` | SIGNALLING_CID | L2CAP信令通道（连接/配置/断开） | BR/EDR |
| `0x0002` | CONNECTIONLESS_CID | 无连接数据通道 | BR/EDR |
| `0x0004` | ATT_CID | ATT协议通道 (GATT) | LE |
| `0x0005` | BLE_SIGNALLING_CID | BLE信令通道 | LE |
| `0x0006` | SMP_CID | SMP安全管理通道 | LE |
| `0x0007` | SMP_BR_CID | SMP over BR/EDR | BR/EDR |

**标志位掩码表示** ([l2cdefs.h:L331-L349](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L331-L349))：

```cpp
#define L2CAP_FIXED_CHNL_SIG_BIT      (1 << L2CAP_SIGNALLING_CID)   // 0x02
#define L2CAP_FIXED_CHNL_ATT_BIT      (1 << L2CAP_ATT_CID)          // 0x10
#define L2CAP_FIXED_CHNL_BLE_SIG_BIT  (1 << L2CAP_BLE_SIGNALLING_CID) // 0x20
#define L2CAP_FIXED_CHNL_SMP_BIT      (1 << L2CAP_SMP_CID)          // 0x40
```

**动态CID (0x0040-0xFFFF)**：
- 范围：`L2CAP_BASE_APPL_CID = 0x0040` 开始
- 分配方式：客户端发起连接请求时携带SourceCID，服务端返回DestinationCID
- 每链路最多 `MAX_L2CAP_CHANNELS` 个（约200+）

**车载Profile的典型CID使用**：

```
车机→手机 ACL连接:
  ├── CID=0x0001 (Signalling)    ← 连接/断开/配置命令
  ├── CID=0x0040 (AVDTP)         ← A2DP音频流控制+数据
  ├── CID=0x0041 (AVRCP)         ← AVRCP控制命令
  ├── CID=0x0042 (RFCOMM)        ← HFP/PBAP/MAP (RFCOMM在L2CAP之上)
  ├── CID=0x0043 (HID Control)   ← HID控制通道
  └── CID=0x0044 (HID Interrupt) ← HID数据通道

BLE连接:
  ├── CID=0x0004 (ATT)           ← GATT服务发现+属性读写
  ├── CID=0x0005 (BLE Signalling)← BLE信令
  └── CID=0x0006 (SMP)           ← BLE安全配对
```

---

### 2.4 命令体系

L2CAP共定义**23种命令码** ([l2cdefs.h:L31-L53](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L31-L53))，通过CID=0x0001/0x0005传输：

#### Classic信令命令 (CID=0x0001)

| 命令码 | 命令 | 方向 | 功能 |
|--------|------|------|------|
| 0x01 | CMD_REJECT | 双向 | 拒绝未知命令 |
| 0x02 | **CONN_REQ** | C→S | 请求建立通道（含PSM+SCID） |
| 0x03 | **CONN_RSP** | S→C | 连接响应（含DCID+Result） |
| 0x04 | **CONFIG_REQ** | 双向 | 协商通道参数(MTU/FCR/QoS) |
| 0x05 | **CONFIG_RSP** | 双向 | 配置响应 |
| 0x06 | **DISC_REQ** | 双向 | 断开通道请求 |
| 0x07 | DISC_RSP | 双向 | 断开通道响应 |
| 0x08/09 | ECHO_REQ/RSP | 双向 | 链路质量检测(Ping) |
| 0x0A/0x0B | INFO_REQ/RSP | 双向 | 查询对端特性(ExtendedFeatures/FixedChannels) |

#### BLE信令命令 (CID=0x0005)

| 命令码 | 命令 | 功能 |
|--------|------|------|
| 0x12/0x13 | BLE_UPDATE_REQ/RSP | **连接参数更新** (Interval/Latency/Timeout) |
| 0x14/0x15 | BLE_CREDIT_BASED_CONN_REQ/RES | BLE CoC连接 (单通道) |
| 0x16 | BLE_FLOW_CTRL_CREDIT | CoC流控信用值 |
| 0x17/0x18 | CREDIT_BASED_CONN_REQ/RES | **Enhanced CoC** (多通道, 5.2) |
| 0x19/0x1A | CREDIT_BASED_RECONFIG_REQ/RES | CoC重配置(MTU/MPS变更) |

---

### 2.5 通道建立流程

```
Client (发起方)                           Server (接受方)
────────────────                    ────────────────
L2CA_ConnectReq(PSM, ...)
    ↓
    CONN_REQ ───────────────────────────→
      [PSM=0x0019(AVDTP), SCID=0x0040]
                                         ↓ 检查PSM是否有listener
                                         ←──────────────── CONN_RSP
                                           [DCID=0x0041, SCID=0x0040, Result=OK]
    ↓ 收到CONN_RSP
    通道进入 CONFIG 状态
    ↓
    CONFIG_REQ ──────────────────────────→
      [DCID=0x0041, MTU=895, FCR_Mode=Basic]
                                         ↓ 协商参数
                                         ←──────────────── CONFIG_RSP
                                           [Result=OK, MTU=895]
    ↓ 收到CONFIG_RSP
    ↓
    CONFIG_REQ ←──────────────────────────
      [SCID=0x0040, MTU=895, FCR_Mode=Basic]
    ↓ 处理对端配置
    CONFIG_RSP ──────────────────────────→
    ↓
    通道进入 OPEN 状态 ← 数据可传输

断开:
    DISC_REQ ───────────────────────────→
                                         ←──────────────── DISC_RSP
    通道进入 CLOSED 状态
```

**关键各命令包格式**：

```cpp
// CONN_REQ = PSM(2) + SCID(2)          = 4字节 [l2cdefs.h:L64]
// CONN_RSP = DCID(2) + SCID(2) + Result(2) + Status(2) = 8字节 [l2cdefs.h:L66]
// CONFIG_REQ = DCID(2) + Flags(2) + Options...  [l2cdefs.h:L68]
// DISC_REQ = DCID(2) + SCID(2)         = 4字节 [l2cdefs.h:L72]
```

---

### 2.6 配置选项

L2CAP配置协商通过6种配置选项进行 ([l2cdefs.h:L374-L379](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L374-L379))：

| Option ID | 名称 | 长度(字节) | 说明 |
|-----------|------|-----------|------|
| `0x01` | **MTU** | 2 | 最大传输单元，默认672 |
| `0x02` | FLUSH_TOUT | 2 | 刷新超时 |
| `0x03` | QOS | 22 | 服务质量参数（服务类型/Token速率/Pool大小/延迟） |
| `0x04` | **FCR** | 9 | 流控/重传模式（Mode/TxWindow/MaxTransmit/RetransTimeout/MonitorTimeout/MPS） |
| `0x05` | **FCS** | 1 | 帧校验序列开关（0=跳过,1=使用） |
| `0x06` | EXT_FLOW | 16 | 扩展流规格 |

**配置结果码**：
| Result | 含义 |
|--------|------|
| L2CAP_CFG_OK=0 | 配置接受 |
| L2CAP_CFG_UNACCEPTABLE_PARAMS=1 | 参数不可接受 |
| L2CAP_CFG_FAILED_NO_REASON=2 | 未知原因失败 |
| L2CAP_CFG_UNKNOWN_OPTIONS=3 | 未知选项 |
| L2CAP_CFG_PENDING=4 | 挂起(等待上层决定) |

---

### 2.7 FCR 重传模式

[FCR选项结构](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cap_types.h#L80-L92)：

```cpp
typedef struct {
  uint8_t  mode;             // FCR模式
  uint8_t  tx_win_sz;        // 发送窗口大小 (1-63)
  uint8_t  max_transmit;     // 最大重传次数
  uint16_t rtrans_tout;      // 重传超时 (ms)
  uint16_t mon_tout;         // 监视超时 (ms)
  uint16_t mps;              // 最大PDU负载大小
} tL2CAP_FCR_OPTS;
```

**三种可靠性模式**：

| 模式 | mode值 | 重传 | 顺序保证 | 适用场景 |
|------|--------|------|---------|---------|
| **Basic Mode** | 0x00 | ❌ 无 | ❌ 无 | A2DP音频流/SDP（丢包无所谓） |
| **ERTM** (Enhanced Retransmission) | 0x03 | ✅ 自动重传 | ✅ 保证 | AVRCP控制命令/蓝牙HID/ATT(GATT) |
| **Streaming Mode** | 0x04 | ❌ 无 | ❌ 无但有FCS检测 | 单向音频/视频流 |
| **LE CoC** | 0x05 | ❌ 无 | ❌ 无但支持流控(Credit) | BLE大文件传输/OTA |

**ERTM关键机制**：

```
发送窗口 (tx_win_sz，默认10):
  ┌───┬───┬───┬───┬───┬───┬───┬───┬───┬───┐
  │ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │ 7 │ 8 │ 9 │ ← 10个PDU可同时发出不等ACK
  └───┴───┴───┴───┴───┴───┴───┴───┴───┴───┘
  ↑ TxSeq                            ↑ TxSeq+Win-1

接收确认 (RR S-Frame):
  ReqSeq=5 → 确认0-4已收到，窗口滑动到5-14

选择性重传 (SREJ):
  ReqSeq=5, SREJ=3 → 0-2、4已确认，需重传第3号PDU
```

---

### 2.8 三层控制块体系

L2CAP采用**CCB→LCB→CB**三层树形控制块结构：

```
tL2C_CB (全局控制块, 单例)
├── lcb_pool[MAX_L2CAP_LINKS]        ← Link Control Block 池
│   ├── tL2C_LCB[0]                  ← 连接设备A的链路
│   │   ├── ccb_queue                ← Channel Control Block 链表
│   │   │   ├── tL2C_CCB (CID=0x0040, AVDTP)
│   │   │   ├── tL2C_CCB (CID=0x0041, AVRCP)
│   │   │   └── tL2C_CCB (CID=0x0042, RFCOMM)
│   │   └── link_xmit_data_q         ← 链路发送队列
│   ├── tL2C_LCB[1]                  ← 连接设备B的链路
│   │   └── ...
│   └── ...
└── controller_xmit_window           ← ACL全局发送窗口
```

#### T2C_CB (全局控制块) — [l2c_int.h:L589-L609](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_int.h#L589-L609)

```cpp
struct tL2C_CB {
  uint16_t controller_xmit_window;   // 总ACL窗口
  uint16_t round_robin_quota;        // Round-Robin链路配额
  uint16_t round_robin_unacked;      // Round-Robin未确认包数
  bool check_round_robin;            // 下一轮是否执行RR检查
  tL2C_LCB lcb_pool[MAX_L2CAP_LINKS]; // LCB池
  tL2C_CCB ccb_pool[MAX_L2CAP_CHANNELS]; // CCB池
  ...
};
```

#### T2C_LCB (链路控制块)

[LCB](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_int.h#L413-L585) 管理一条ACL链路上的所有通道：

```cpp
struct tL2C_LCB {
  tL2C_LINK_STATE link_state;            // DISCONNECTED/CONNECTING/CONNECTED/DISCONNECTING
  RawAddress remote_bd_addr;             // 远程设备MAC
  uint16_t handle;                       // HCI Connection Handle

  // 固定通道
  tL2C_CCB* p_fixed_ccbs[L2CAP_NUM_FIXED_CHNLS];

  // 动态通道
  tL2C_CCB_Q ccb_queue;                 // 通道链表
  uint16_t link_xmit_quota;             // 链路发送配额
  uint16_t sent_not_acked;              // 已发送未确认包数

  // 流量控制
  tL2CAP_PRIORITY acl_priority;         // NORMAL/HIGH
  tL2CAP_LATENCY acl_latency;           // NORMAL/LOW

  // BLE特有
  uint16_t min_interval, max_interval;  // BLE连接间隔
  uint16_t latency, timeout;            // BLE延迟和超时
  uint8_t conn_update_mask;             // 连接更新阻塞掩码

  // Credit Based CoC 挂起状态
  tL2CAP_LE_CFG_INFO pending_ecoc_reconfig_cfg;
  uint16_t pending_ecoc_connection_cids[5];  // 最多5个通道
  ...
};
```

#### T2C_CCB (通道控制块)

[CCB](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_int.h#L267-L366) 管理一个逻辑通道：

```cpp
struct tL2C_CCB {
  tL2C_CHNL_STATE chnl_state;     // 通道状态（CLOSED→...→OPEN）
  tL2C_LCB* p_lcb;                // 所属链路
  uint16_t local_cid;             // 本地CID
  uint16_t remote_cid;            // 远端CID

  // 配置
  uint16_t peer_conn_mtu;         // 对方MTU
  tL2CAP_CH_CFG_BITS our_cfg;    // 我方配置
  tL2CAP_CH_CFG_BITS peer_cfg;   // 对方配置

  // FCR (仅ERTM模式)
  tL2CAP_FCRB fcrb;               // FCR接收缓冲
  uint8_t bypass_fcs;             // FCS过滤标志

  // 回调
  tL2CAP_APPL_INFO* p_rcb;       // 注册回调（pL2CA_ConnectCfm_Cb等）
};
```

**通道状态机** ([l2c_int.h:L73-L122](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_int.h#L73-L122))：

```
CST_CLOSED ─→ CST_ORIG_W4_SEC_COMP ─→ CST_ORIG_W4_SEC_COMP_CL
    ↑                                      ↓
    │                                CST_W4_L2CAP_CONNECT_RSP
    │                                      ↓
    │                                CST_W4_L2CA_CONNECT_RSP
    │                                      ↓
    │                                CST_CONFIG ─→ CST_OPEN
    │                                      ↓
    │                                CST_DISCONNECTING
    │                                      ↓
    └──────────────────────────────────←────┘
```

---

### 2.9 Round-Robin 调度

L2CAP全局层实现了多链路的**Round-Robin公平调度** ([l2c_int.h:L466-L468](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_int.h#L466-L468))：

```cpp
uint16_t link_xmit_quota;    // 0 = 启用RoundRobin
bool is_round_robin_scheduling() const { return link_xmit_quota == 0; }

// 全局层
bool is_classic_round_robin_quota_available() const {
  return round_robin_unacked < round_robin_quota;
}
```

**工作原理**：
1. 每条链路link_xmit_quota=0时启用RR
2. 全局`round_robin_quota`限制一轮中每条链路的最大发送包数
3. 每轮遍历所有活跃链路，`check_round_robin`标志位驱动下一轮
4. 优先级队列：每个优先级组内部采用Round-Robin

**车载多Profile场景中的意义**：
```
车机同时有 A2DP(HIGH) + AVRCP(NORMAL) + PBAP(NORMAL) 三个L2CAP通道

RoundRobin调度:
  轮1: A2DP发送N个包 → AVRCP发送M个包 → PBAP发送K个包
  轮2: A2DP发送N个包 → AVRCP发送M个包 → PBAP发送K个包
  ...
确保高优先级A2DP音频不被低优先级PBAP联系人下载阻塞
```

---

### 2.10 LE Credit Based CoC (L2CAP Connection Oriented Channel over LE)

BLE 4.2引入的Credit Based CoC，允许在LE传输上建立面向连接的L2CAP通道：

**建立流程** ([l2cdefs.h:L87-L92](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L87-L92))：

```
LE Credit Based Connection Request:
  [LE_PSM(2) + SCID(2) + MTU(2) + MPS(2) + Initial_Credits(2)]
   = 10字节

LE Credit Based Connection Response:
  [DCID(2) + MTU(2) + MPS(2) + Initial_Credits(2) + Result(2)]
   = 10字节
```

**Credit流控机制**：
```
连接建立时分配 Initial_Credits (如10个)
每发送一个LE帧 → Credit -1
对端发送 LE_FLOW_CTRL_CREDIT → Credit +N
Credit=0 → 停止发送，等待补充
```

**Enhanced CoC (BLE 5.2)** ([l2cdefs.h:L50-L53](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h#L50-L53))：
- 一条请求可创建**最多5个通道** (`L2CAP_CREDIT_BASED_MAX_CIDS = 5`)
- 支持运行时重配置（`CREDIT_BASED_RECONFIG_REQ`）
- 重配置结果：不允许缩减MTU/MPS

**LE CoC配置结构**：
```cpp
struct tL2CAP_LE_CFG_INFO {
  tL2CAP_CFG_RESULT result;
  uint16_t mtu;         // 默认 100 (kDefaultL2capMtu)
  uint16_t mps;         // 默认 100 (kDefaultL2capMps)
  uint16_t credits;     // 初始信用值
  uint8_t  number_of_channels; // 默认 5
};
```

---

### 2.11 拓展特性信息交换

当对端支持Fixed Channels或Extended Features时，通过Info Req/Rsp交换：

```cpp
// L2CAP信息请求类型 [l2cdefs.h:L422-L427]
#define L2CAP_CONNLESS_MTU_INFO_TYPE      0x0001  // 无连接MTU
#define L2CAP_EXTENDED_FEATURES_INFO_TYPE 0x0002  // 扩展特性位
#define L2CAP_FIXED_CHANNELS_INFO_TYPE    0x0003  // 固定通道掩码

// 扩展特性位 [l2cdefs.h:L438-L451]
#define L2CAP_EXTFEA_ENH_RETRANS   0x00000008  // ERTM
#define L2CAP_EXTFEA_STREAM_MODE   0x00000010  // Streaming Mode
#define L2CAP_EXTFEA_NO_CRC        0x00000020  // 可选FCS(关)
#define L2CAP_EXTFEA_EXT_FLOW_SPEC 0x00000040  // 扩展流规格
#define L2CAP_EXTFEA_FIXED_CHNLS  0x00000080  // 固定通道支持
#define L2CAP_EXTFEA_EXT_WINDOW   0x00000100  // 扩展窗口(ERTM)
```

**车载Info交换常见问题**：
- 部分旧手机不支持ExtendedFeatures→车机无法使用ERTM→AVRCP控制丢帧
- 手机FixedChannels掩码缺少SMP_BR_CID→BR/EDR上的安全协商失败

---

## 三、车载开发实战

### 3.1 SDP常见问题

| 问题 | 根因 | 排查方法 |
|------|------|---------|
| 手机搜不到车机A2DP | SDP未注册或UUID不匹配 | `sdptool browse` 查看车机SDP Record |
| 车机发现手机PBAP慢 | ServiceSearchAttrReq超时 | 降低SDP超时或先用ServiceSearch缩小范围 |
| SDP Buffer溢出 | discovery_db太小 | 增大`SDP_DISC_DB_SIZE`或分多次SDP搜索 |
| PBAP PSE SDP无版本信息 | 旧手机SDP只写v1.1 | 检查interop_database.conf中的`INTEROP_ADV_PBAP_VER_1_2`互操作标记 |

### 3.2 L2CAP常见问题

| 问题 | 根因 | 排查方法 |
|------|------|---------|
| A2DP卡顿(高频) | L2CAP MTU不匹配导致分片过多 | 检查HCI Log中L2CAP帧的MTU协商结果 |
| AVRCP控制延迟大 | ERTM未启用→Basic模式丢帧→应用层重传 | 查看InfoRsp ExtendedFeatures是否有0x08(ERTM) |
| 车机多个Profile同时连接慢 | RR调度quota不均匀 | 检查`round_robin_quota`和`round_robin_unacked` |
| 连接被拒: CONN_NO_PSM | PSM未注册listener | 确认上层Profile是否正确调用了`L2CA_RegisterLECoc()`或RFCOMM创建 |
| BLE GATT服务发现失败 | FixedChannels缺少ATT_CID | 查看InfoRsp FixedChannels掩码是否有0x10位 |
| CONN_TIMEOUT (0xEEEE) | 对方长时间无响应 | 排查手机端L2CAP层是否卡住(如BT_HCI_ERR_CONNECTION_TIMEOUT) |

### 3.3 调试命令

```bash
# SDP - 发现远程设备服务
sdptool browse <MAC>                    # 浏览所有服务
sdptool search --bdaddr <MAC> A2SNK    # 搜索A2DP Sink
sdptool search --bdaddr <MAC> HFAG     # 搜索HFP AG

# L2CAP - 连接状态
adb shell cat /sys/kernel/debug/bluetooth/l2cap
adb shell dumpsys bluetooth_manager | grep -A 5 "l2cap"
```

---

## 四、关键源代码文件索引

### SDP 核心 (9个文件)

| 文件 | 路径 |
|------|------|
| sdpint.h (内部定义) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdpint.h) |
| sdpdefs.h (常量定义) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/sdpdefs.h) |
| sdp_discovery_db.h (发现DB) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_discovery_db.h) |
| sdp_discovery.cc (远程发现) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_discovery.cc) |
| sdp_server.cc (服务端) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_server.cc) |
| sdp_db.cc (本地DB) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_db.cc) |
| sdp_utils.cc (工具) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/sdp/sdp_utils.cc) |
| sdp_api.h (API声明) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/sdp_api.h) |
| sdp_status.h (状态码) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/sdp_status.h) |

### SDP BTA/BTIF层

| 文件 | 路径 |
|------|------|
| bta_sdp_int.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/sdp/bta_sdp_int.h) |
| bta_sdp_act.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/sdp/bta_sdp_act.cc) |
| btif_sdp.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_sdp.cc) |
| btif_sock_sdp.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/include/btif_sock_sdp.h) |
| SdpManager.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/sdp/SdpManager.java) |

### L2CAP 核心 (14个文件)

| 文件 | 路径 |
|------|------|
| l2c_int.h (内部定义-CCB/LCB/CB) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_int.h) |
| l2cdefs.h (协议常量) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cdefs.h) |
| l2c_csm.cc (通道状态机) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_csm.cc) |
| l2c_fcr.cc (FCR重传) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_fcr.cc) |
| l2c_link.cc (链路管理) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_link.cc) |
| l2c_main.cc (主模块) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_main.cc) |
| l2c_utils.cc (工具) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_utils.cc) |
| l2c_ble.cc (BLE信令) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_ble.cc) |
| l2c_ble_conn_params.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_ble_conn_params.cc) |
| l2c_api.h (API声明) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_api.h) |
| l2c_api.cc (API实现) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/l2cap/l2c_api.cc) |
| l2cap_interface.h (Interface虚基类) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cap_interface.h) |
| l2cap_types.h (类型定义) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/l2cap_types.h) |
| l2cap_packets.pdl (PDL定义) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/pdl/l2cap/l2cap_packets.pdl) |