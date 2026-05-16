# T33 PBAP与MAP详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：
> 1. PBAP基于OBEX协议通过RFCOMM/L2CAP传输，Phonebook访问路径 `/telecom/pb`(联系人)、`/telecom/fav`(收藏)、`/telecom/{ich|och|mch|cch}`(通话记录)
> 2. PBAP Client采用5状态机（Disconnected→Connecting→Connected→Downloading→Disconnecting），通过SDP发现PSE服务后下载联系人和通话记录
> 3. MAP提供完整的SMS/MMS/Email访问能力，MAS多实例架构支持SMS+多个Email账号，MNS负责新消息实时推送通知
> 4. 车载场景重点是PBAP Server让车机读取手机通讯录+通话记录、MAP让车机收发短信邮件

---

## 一、PBAP (Phone Book Access Profile) 概述

### 1.1 协议栈分层

```
手机端 (PSE - Phonebook Server Equipment)
    车机端 (PCE - Phonebook Client Equipment)

┌──────────────────────────────────┐
│  Java App (PSE / PCE)            │
│  ┌────────────────────────────┐  │
│  │ BluetoothPbapService       │  │  ← PSE入口
│  │ PbapClientService          │  │  ← PCE入口
│  └────────────────────────────┘  │
├──────────────────────────────────┤
│  OBEX (Object Exchange)          │  ← RFC2045风格的对象交换
│  ┌────────────────────────────┐  │
│  │ ServerRequestHandler       │  │  ← BluetoothPbapObexServer
│  │ ClientSession              │  │  ← PbapClientObexClient
│  └────────────────────────────┘  │
├──────────────────────────────────┤
│  传输层: RFCOMM / L2CAP          │
│  ┌────────────────────────────┐  │
│  │ ObexServerSockets          │  │
│  │ BluetoothSocket            │  │
│  └────────────────────────────┘  │
└──────────────────────────────────┘
```

**PBAP Target UUID**: `796135f0-f0c5-11d8-0966-0800200c9a66`

**SDP注册信息**（PSE端）:
- 版本: v1.2 (0x0102)
- 支持仓库(With SIM): `0x000B` (LocalPhonebook + SIM)
- 支持仓库(Without SIM): `0x0009` (仅LocalPhonebook)
- 支持特性: `0x021F` (Download + Browse + ...)

**源码**: [BluetoothPbapService.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbap/BluetoothPbapService.java#L123-L127)

---

### 1.2 文件架构

```
pbap/ (PSE - 手机端)
├── BluetoothPbapService.java       ← PSE服务入口，继承ConnectableProfile
├── PbapStateMachine.java           ← 单连接状态机
├── BluetoothPbapObexServer.java    ← OBEX服务端（处理Pull请求）
├── BluetoothPbapVcardManager.java  ← VCard生成器
├── BluetoothPbapCallLogComposer.java ← 通话记录VCard生成
├── BluetoothPbapConfig.java        ← 配置（ownerVCard/照片）
├── BluetoothPbapUtils.java         ← 版本计数器管理
├── BluetoothPbapSimVcardManager.java ← SIM卡VCard管理
└── BluetoothPbapAuthenticator.java  ← OBEX认证

pbapclient/ (PCE - 车机端)
├── PbapClientService.java          ← PCE服务入口
├── PbapClientStateMachine.java     ← 客户端5状态机（核心）
├── PbapClientContactsStorage.java  ← 联系人存储到Contacts DB
├── PbapSdpRecord.java              ← SDP记录解析
├── PbapClientAccountManager.java   ← Account管理器
└── obex/
    ├── PbapClientObexClient.java   ← OBEX客户端连接管理
    ├── PullPhonebookRequest.java   ← Pull Phonebook请求
    ├── PullPhonebookMetadataRequest.java ← 元数据请求
    ├── PbapPhonebook.java          ← Phonebook解析(路径+VCard)
    ├── PbapPhonebookMetadata.java  ← 元数据解析
    └── PbapApplicationParameters.java ← OBEX参数Tag定义
```

---

## 二、PBAP PSE (Server) — 手机端完整流程

### 2.1 服务启动流程

[BluetoothPbapService](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbap/BluetoothPbapService.java#L169-L220) 启动时执行以下操作：

```
构造流程:
1. 注册 ACTION_USER_SWITCHED / ACTION_USER_UNLOCKED 广播
2. 创建 PbapHandlerThread (独立线程)
3. 注册 ContactChangeObserver (监听联系人变化 → 更新版本计数器)
4. → GET_LOCAL_TELEPHONY_DETAILS (获取本机号码和名称)
5. → LOAD_CONTACTS (加载联系人到内存)
6. → START_LISTENER:
   ├── ObexServerSockets.create() (绑定RFCOMM+L2CAP)
   ├── createSdpRecord() (注册SDP)
   └── fetchPbapParams() (读取数据库版本信息，决定是否需要版本更新)
```

**OBEX服务端口**: RFCOMM Channel + L2CAP PSM 均由 `ObexServerSockets.create()` 自动分配

### 2.2 连接流程

```java
// 手机端收到车机OBEX连接时的回调
public boolean onConnect(BluetoothDevice remoteDevice, BluetoothSocket socket) {
    // 1. 创建 PbapStateMachine（一对一映射，每设备一个状态机）
    PbapStateMachine sm = new PbapStateMachine(..., remoteDevice, socket, ...);
    mPbapStateMachineMap.put(remoteDevice, sm);

    // 2. 发送 REQUEST_PERMISSION → 触发权限检查
    sm.sendMessage(PbapStateMachine.REQUEST_PERMISSION);
}
```

**权限检查流程**:
```
PbapStateMachine.REQUEST_PERMISSION
  → checkOrGetPhonebookPermission()
    ├── 权限=ACCESS_ALLOWED → 直接 AUTHORIZED
    ├── 权限=ACCESS_REJECTED → 直接 REJECTED
    └── 权限=ACCESS_UNKNOWN → 弹出权限请求UI
        ├── 用户确认 → AUTHORIZED → 开始OBEX会话
        ├── 用户拒绝 → REJECTED → 断开
        └── 30秒超时 → REJECTED (USER_TIMEOUT)
```

### 2.3 OBEX Server处理 — Phonebook路径体系

[BluetoothPbapObexServer](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbap/BluetoothPbapObexServer.java) 支持的虚拟文件系统路径：

| 路径 | 内容类型 | 说明 |
|------|---------|------|
| `/telecom` | 根目录 | 不包含数据，仅用于导航 |
| `/telecom/pb` | `TYPE_PHONEBOOK` | 手机通讯录（索引从0开始，0.vcf=本机号码） |
| `/telecom/fav` | `TYPE_FAVORITES` | 收藏联系人 |
| `/telecom/ich` | `TYPE_INCOMING_CALL_HISTORY` | 来电记录 |
| `/telecom/och` | `TYPE_OUTGOING_CALL_HISTORY` | 去电记录 |
| `/telecom/mch` | `TYPE_MISSED_CALL_HISTORY` | 未接来电（含NEW标记计数） |
| `/telecom/cch` | `TYPE_COMBINED_CALL_HISTORY` | 合并通话记录 |
| `/SIM1/telecom/pb` | `TYPE_SIM_PHONEBOOK` | SIM卡通讯录（仅SIM功能开启时） |
| `/SIM1/telecom/{ich,och,mch}` | `TYPE_SIM_CALL_HISTORY` | SIM卡通话记录 |

**合法的OBEX操作**:
```java
@Override
public int onConnect(HeaderSet request, HeaderSet reply)    // 验证PBAP Target UUID
@Override
public int onSetPath(...)                                    // 浏览/切换目录
@Override
public int onGet(Operation op) {                             // 获取数据
    // 三种请求类型
    if (type.equals("x-bt/vcard-listing"))  → pullVcardListing()  // XML列表
    if (type.equals("x-bt/vcard"))          → pullVcardEntry()    // 单个vCard
    if (type.equals("x-bt/phonebook"))      → pullPhonebook()     // 批量下载
}
@Override
public void onClose()                                        // 会话关闭
@Override
public int onAbort(HeaderSet request, HeaderSet reply)       // 中断传输
```

### 2.4 三种拉取操作详解

#### ① Vcard Listing (`x-bt/vcard-listing`)

返回XML格式列表：
```xml
<?xml version="1.0"?>
<!DOCTYPE vcard-listing SYSTEM "vcard-listing.dtd">
<vCard-listing version="1.0">
  <card handle="1.vcf" name="张三"/>
  <card handle="2.vcf" name="李四"/>
  ...
</vCard-listing>
```
支持参数: `searchValue`(搜索), `searchAttr`(按名字/号码), `order`(按索引/字母序), `maxListCount`(分页最大数), `listStartOffset`(分页起始偏移)

#### ② Vcard Entry (`x-bt/vcard`) 

按索引拉取单个vCard文件（如 `1.vcf`）:
- `0.vcf`(pb路径) = 本机号码Owner VCard
- `1.vcf` ~ `N.vcf` = 通讯录或通话记录条目

#### ③ Pull Phonebook (`x-bt/phonebook`)

批量拉取vCard数据流，支持分页参数:
- `maxListCount=0` → 只返回Phonebook大小(仅Header不含Body)
- 索引范围: pb/ich/och/mch/cch 通过 `listStartOffset` + `maxListCount` 分页
- 通话记录限量: 50条(CALLLOG_NUM_LIMIT)

---

### 2.5 版本计数器机制（增量同步优化）

PSE通过**DatabaseIdentifier + Primary/Secondary VersionCounter**告知PCE数据是否有变化，避免全量重传。

```java
// BluetoothPbapObexServer.java
byte[] getDatabaseIdentifier() {
    // 基于 BluetoothPbapUtils.sDbIdentifier — 数据库唯一标识
    // 如果联系人数据库发生结构性变化，此值改变
}

byte[] getPBPrimaryFolderVersion() {
    // 基于 BluetoothPbapUtils.sPrimaryVersionCounter
    // 联系人增删改 → Counter递增
}

byte[] getPBSecondaryFolderVersion() {
    // 基于 BluetoothPbapUtils.sSecondaryVersionCounter
    // 用于滚动计数器检测（Counter溢出检查）
}
```

**车载场景意义**: 车机PCE发起连接后先检查版本计数器，如果和上次下载一致则跳过下载，避免大量VCard重复传输。如果支持 `FOLDER_VERSION_COUNTER` 特性位（需要连接时在 `supportedFeature` 参数中声明），PSE才会在响应头中返回这些计数器。

---

## 三、PBAP PCE (Client) — 车机端完整流程

### 3.1 5状态机设计

[PbapClientStateMachine](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbapclient/PbapClientStateMachine.java) 定义了5个状态：

```
Disconnected → Connecting → Connected → Downloading → Disconnecting → Disconnected
                   ↑                                    ↓
                   └────────── 超时/失败 ─────────────────┘
```

| 状态 | 触发进入 | 核心操作 |
|------|---------|---------|
| **Disconnected** | 初始状态 | 仅接受 MSG_CONNECT |
| **Connecting** | MSG_CONNECT | 发起SDP搜索(PBAP_PSE UUID)→等待SDP记录→L2CAP或RFCOMM连接OBEX Client→12秒超时 |
| **Connected** | OBEX Client连接成功 | 注册Storage Callback→创建Account→触发下载 |
| **Downloading** | Storage Ready | 按优先级下载: Favorites→LocalPB→SIM→MCH→ICH→OCH (每个phonebook先取metadata再分批250条下载) |
| **Disconnecting** | 断开/超时/错误 | 断开OBEX→清理Account→释放Storage Callback→3秒超时 |

### 3.2 SDP发现过程

```java
// Connecting.enter()
mDevice.sdpSearch(BluetoothUuid.PBAP_PSE);  // 搜索UUID: 0x1130

// SDP结果处理
case MSG_SDP_COMPLETE:
    mSdpRecord = (PbapSdpRecord) message.obj;
    // 根据SDP记录决定连接方式
    if (mSdpRecord.getL2capPsm() != -1)    mObexClient.connectL2cap(psm);
    else if (mSdpRecord.getRfcommChannelNumber() != -1) mObexClient.connectRfcomm(channel);
```

**SDP记录包含信息**:
- 版本 (v1.1/v1.2)
- 支持仓库 (Local/SIM)
- 支持特性位

根据SDP记录中的仓库，决定哪些Phonebook需要下载：`fav`, `pb`, `ich`, `och`, `mch`, `sim_pb`, `sim_ich`, `sim_och`, `sim_mch`

### 3.3 下载流程详解

```
Downloading.enter():
├── initializePhonebooksToDownload()   ← 按优先级排列表
│   优先级: Favorites > LocalPB > SIM > MCH > ICH > OCH > SIM_MCH > SIM_ICH > SIM_OCH
│
└── downloadPhonebookMetadata(path)
    ├── 构造 PbapApplicationParameters(FORMAT_VCARD_30, RETURN_SIZE_ONLY)
    ├── 发送 PullPhonebookRequest → PSE响应包含: phonebookSize, databaseIdentifier, versionCounters
    │
    ├── 如果 size > 0:
    │   └── downloadPhonebook(path, batchStart=0, batchSize=250)
    │       ├── 构造 PbapApplicationParameters(properties, FORMAT_VCARD_30, count=250, offset=N)
    │       ├── 发送 PullPhonebookRequest → PSE响应 vCard流
    │       ├── parse vCard → 存入 Contacts DB
    │       ├── 如果 totalDownloaded < totalExpected:
    │       │   └── 继续 downloadPhonebook(path, batchStart+250, 250)
    │       └── 如果 totalDownloaded >= totalExpected:
    │           └── setNextPhonebookOrComplete()
    │
    └── 如果 size == 0: 跳过该phonebook → setNextPhonebookOrComplete()
```

**默认下载属性**（VCard 3.0 vCard 字段选择）:
```java
DEFAULT_PROPERTIES = VERSION | FN(姓名) | N(结构化名称) | PHOTO(照片)
                   | ADR(地址) | TEL(电话) | EMAIL(邮箱) | NICKNAME(昵称)
```

### 3.4 联系人存储

下载的vCard通过 [PbapClientContactsStorage](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbapclient/PbapClientContactsStorage.java) 存储到`ContactsContract`:

```java
// 根据Phonebook类型分别存储
storeDownloadedContacts(phonebook, contacts):
├── FAVORITES_PATH    → insertFavorites(account, contacts)
├── LOCAL_PHONEBOOK_PATH → insertLocalContacts(account, contacts)
├── SIM_PHONEBOOK_PATH   → insertSimContacts(account, contacts)
├── MCH_PATH / SIM_MCH_PATH → insertMissedCallHistory(account, contacts)
├── ICH_PATH / SIM_ICH_PATH → insertIncomingCallHistory(account, contacts)
└── OCH_PATH / SIM_OCH_PATH → insertOutgoingCallHistory(account, contacts)
```

断开连接时自动清理: `cleanupContactsDataAndAccounts()` → `removeAllContacts + removeCallHistory + removeAccount`

---

## 四、MAP (Message Access Profile) 概述

### 4.1 协议栈分层与UUID

MAP是一个更复杂的Profile，支持SMS/MMS/Email的远程访问和通知。

```
┌────────────────────────────────────────┐
│  角色:                                   │
│  MAS (Message Access Server)  = 手机端  │
│  MCE (Message Client Equipment) = 车机端 │
│  MNS (Message Notification Service)     │
│    = 车机注册通知，手机推送事件          │
├────────────────────────────────────────┤
│  UUID体系:                               │
│  MAS: 00001132-0000-1000-8000-00805F9B34FB │
│  MNS: 00001133-0000-1000-8000-00805F9B34FB │
│  MAP: 00001134-0000-1000-8000-00805F9B34FB │
├────────────────────────────────────────┤
│  Target UUID (OBEX连接时验证):          │
│  BB582B40-420C-11DB-B0DE-0800200C9A66  │
└────────────────────────────────────────┘
```

**源码**: [BluetoothMapObexServer.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapObexServer.java#L70-L104)

### 4.2 MAP文件架构

```
map/
├── BluetoothMapService.java            ← MAP服务主入口
├── BluetoothMapObexServer.java         ← OBEX服务端（处理所有OBEX请求类型）
├── BluetoothMapContent.java            ← 消息内容Provider
├── BluetoothMapContentObserver.java    ← 监听SMS/MMS/Email数据库变化→触发MNS通知
├── BluetoothMnsObexClient.java         ← MNS OBEX客户端（连接到车机的MNS Server）
├── BluetoothMapMasInstance.java        ← MAS实例管理(多账户)
├── BluetoothMapAccountLoader.java      ← 扫描系统Email/IM Provider
├── BluetoothMapAccountItem.java        ← 账号项
├── BluetoothMapAppParams.java          ← MAP OBEX应用参数解析(40+参数)
├── BluetoothMapUtils.java              ← 工具类
├── BluetoothMapbMessage.java           ← bMessage抽象基类
├── BluetoothMapbMessageSms.java        ← SMS bMessage
├── BluetoothMapbMessageEmail.java      ← Email bMessage
├── BluetoothMapbMessageMime.java       ← MIME bMessage(MMS)
├── BluetoothMapFolderElement.java      ← 文件夹元素
├── BluetoothMapConvoListing.java       ← 对话列表
├── BluetoothMapMessageListing.java     ← 消息列表
├── BluetoothMapSmsPdu.java             ← SMS PDU处理
├── BluetoothMapConvoContactElement.java ← 对话联系人元素
└── MapContact.java / SmsMmsContacts.java ← 联系人工具
```

---

### 4.3 MAS多实例架构

MAP区别于PBAP的关键特性之一：**MAS (Message Access Service) 多实例**。

```java
// BluetoothMapService.java
// MAS_ID 0 = SMS/MMS (固定)
private static final int MAS_ID_SMS_MMS = 0;

// MAS_ID 1+ = 各种Email/IM账号（动态）
// 通过 BluetoothMapAccountLoader 扫描系统已安装的Email/IM app
// (Gmail, Outlook, 等等)
```

**MAS实例结构**:
```
mMasInstances (SparseArray<BluetoothMapMasInstance>):
  MAS_ID=0 → SMS/MMS
  MAS_ID=1 → Email Account 1 (如 Gmail)
  MAS_ID=2 → Email Account 2 (如 Exchange)
  MAS_ID=3 → IM Account 1
```

每个MAS实例拥有独立的OBEX Server连接和ContentObserver。

---

### 4.4 MAP OBEX操作类型

[BluetoothMapObexServer](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapObexServer.java#L96-L107) 支持10种OBEX操作：

| OBEX Type | 操作 | 说明 |
|-----------|------|------|
| `x-obex/folder-listing` | **文件夹列表** | 返回OBEX文件夹结构(inbox/sent/outbox/draft...) |
| `x-bt/MAP-msg-listing` | **消息列表** | 返回指定文件夹的消息列表 |
| `x-bt/MAP-convo-listing` | **对话列表** | 返回按联系人分组的对话列表 |
| `x-bt/message` | **获取消息** | 拉取单条消息的完整内容(bMessage格式) |
| `x-bt/messageStatus` | **设置消息状态** | 标记已读/删除 |
| `x-bt/MAP-NotificationRegistration` | **通知注册** | 车机注册MNS通知(新消息推送) |
| `x-bt/MAP-messageUpdate` | **消息更新** | 推送消息变更到车机 |
| `x-bt/MASInstanceInformation` | **MAS实例信息** | 获取服务实例的能力描述 |
| `x-bt/participant` | **设置在线状态** | IM在线状态管理 |
| `x-bt/MAP-notification-filter` | **通知过滤器** | 设置消息通知过滤条件 |

### 4.5 MAP核心操作流程

#### ① Message Listing

```
MCE→MAS: GET /telecom/msg/inbox?type="x-bt/MAP-msg-listing"
         AppParams: {MaxListCount, StartOffset, FilterMessageType,
                     FilterPeriodBegin/End, FilterReadStatus, ...}

MAS→MCE: bMessage listing in <MAP-msg-listing> format
         (不带完整消息内容，只含摘要信息)
```

#### ② 单条消息获取 (bMessage格式)

```
MCE→MAS: GET /telecom/msg/inbox/1234?type="x-bt/message"
         AppParams: {Charset=UTF-8, FractionRequest=1(不拆分)}

MAS→MCE: bMessage body:
         BEGIN:BMSG
         VERSION:1.0
         STATUS:UNREAD
         TYPE:SMS_GSM
         FOLDER:/telecom/msg/inbox
         BEGIN:VCARD ... END:VCARD         ← 发送者
         BEGIN:VCARD ... END:VCARD         ← 接收者
         BEGIN:BENV
         BEGIN:VCARD ... END:VCARD         ← 抄送
         BEGIN:BBODY
         ENCODING:G-7BIT                  ← GSM 7-bit编码
         CHARSET:UTF-8
         LENGTH:45
         BEGIN:MSG
         你好，今天见面吗？                ← 消息正文
         END:MSG
         END:BBODY
         END:BMSG
```

**MAP消息类型**:
```java
// BluetoothMapUtils.java
TYPE {
  SMS_GSM,       // GSM SMS
  SMS_CDMA,      // CDMA SMS
  MMS,            // MMS (多媒体消息)
  EMAIL,          // Email
  IM              // Instant Message (即时消息)
}
```

---

### 4.6 MNS (Message Notification Service) — 实时消息推送

**MNS架构**:
```
                    车机(MCE+MNS Server)         手机(MAS+MNS Client)
                    ←────────────────────              ←────────────────────
                    1. 车机注册MNS通知
                                                      2. 手机收到新短信
                    3. ← Event Report                  ── 推送通知
                        "NewMessage"
```

**MNS连接流程**:
```java
// BluetoothMapService.java - 收到MAS连接后启动MNS
MSG_MAS_CONNECT:
  → mBluetoothMnsObexClient = new BluetoothMnsObexClient(device, mnsRecord)
  → 搜索 MNS SDP (UUID: 00001133)

// BluetoothMnsObexClient.java - MNS SDP搜索完成
MSG_MNS_SDP_SEARCH:
  → 连接车机的MNS OBEX Server (RFCOMM)
  → 连接成功 → MNS就绪

// 车机发送 MNS Registration
MSG_MNS_NOTIFICATION_REGISTRATION:
  → OBEX PUT "x-bt/MAP-NotificationRegistration" {MAS_INSTANCE_ID, NOTIFICATION_STATUS=ON}

// 手机收到新短信后 → ContentObserver触发
→ BluetoothMapContentObserver.onChange()
→ MNS发送事件: PUT "x-bt/MAP-event-report"
  {TYPE=NewMessage, MAS_INSTANCE_ID, HANDLE}
```

**MNS事件类型**:
- `NewMessage` — 新消息到达
- `DeliverySuccess` — 发送成功
- `SendingSuccess` / `SendingFailure` — 发送成功/失败
- `DeliveryFailure` — 投递失败
- `MessageShift` — 消息移动（inbox→其他）
- `MessageDeleted` — 消息删除
- `MemoryFull` / `MemoryAvailable` — 存储状态

**源码**: [BluetoothMnsObexClient.java](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMnsObexClient.java#L62-L64)

---

### 4.7 MAP AppParams (40+参数)

[BluetoothMapAppParams](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapAppParams.java#L40-L79) 定义了MAP规范的OBEX应用参数：

| Tag | 名称 | 字节长度 | 说明 |
|-----|------|---------|------|
| 0x01 | MaxListCount | 2 | 分页元素数 |
| 0x02 | StartOffset | 2 | 分页起始偏移 |
| 0x03 | FilterMessageType | 1 | 消息类型过滤(SMS/MMS/Email/IM) |
| 0x04/0x05 | FilterPeriod Begin/End | 字符串 | 时间段过滤 |
| 0x06 | FilterReadStatus | 1 | 已读/未读过滤 |
| 0x07/0x08 | FilterRecipient/Originator | 字符串 | 发送者/接收者过滤 |
| 0x09 | FilterPriority | 1 | 优先级过滤 |
| 0x0A | Attachment | 1 | 附件处理方式 |
| 0x0C | Retry | 1 | 失败重试次数 |
| 0x0E | NotificationStatus | 1 | 通知开关(ON/OFF) |
| 0x14 | Charset | 1 | 字符集(UTF-8/UTF-16/native) |
| 0x15 | FractionRequest | 1 | 是否拆分长消息 |
| 0x17/0x18 | StatusIndicator/Value | 1 | 消息状态(Read/Deleted) |
| 0x1A | DatabaseIdentifier | 16 | 数据库标识(增量同步) |
| 0x23 | FolderVersionCounter | 16 | 文件夹版本计数器 |
| 0x22 | FilterConvoId | 16 | 按对话过滤 |
| 0x36 | ConvoListingSize | 2 | 对话列表大小 |
| 0x25 | NotificationFilter | 4 | 通知过滤位掩码 |

---

## 五、PBAP vs MAP 对比

| 维度 | PBAP | MAP |
|------|------|------|
| **用途** | 读取通讯录、通话记录 | 收发短信(SMS/MMS/Email/IM) |
| **方向** | Pull only (单向下拉) | Pull + Push (双向+通知) |
| **传输协议** | OBEX over RFCOMM/L2CAP | OBEX over RFCOMM/L2CAP |
| **对象格式** | vCard (2.1/3.0) | bMessage (SMS/MMS/Email) |
| **多实例** | 单一PSE | MAS多实例(SMS+Email×N) |
| **通知机制** | 无实时通知 | MNS实时推送 |
| **文件夹结构** | 固定7个路径 | 动态OBEX文件夹(支持服务端文件夹浏览) |
| **OBEX操作** | 5种(Connect,SetPath,Get,Abort,Disconnect) | 10种(含SET操作如MNS Registration/MessageStatus) |
| **版本控制** | DB识别符+版本计数器 | DB识别符+Folder版本计数器 |
| **车载常见问题** | VCard格式兼容性、联系人照片过大 | bMessage编码、MNS连接保持、通知风暴 |

---

## 六、车载开发实战

### 6.1 PBAP常见问题与对策

| 问题 | 原因 | 对策 |
|------|------|------|
| **Pull Phonebook慢** | batchSize=250、VCard含照片 | ①减少DEFAULT_PROPERTIES过滤字段 ②VCard 2.1体积小于3.0 ③使用vCard Selector只拉增量 |
| **版本计数器不一致** | PSE联系人变化后未同步 | 利用`FOLDER_VERSION_COUNTER`特性位，仅下载变化的phonebook |
| **认证超时** | 用户体验30秒确认超时 | `USER_CONFIRM_TIMEOUT_VALUE=30000`，车机可在配对阶段提前设置`ACCESS_ALLOWED` |
| **联系人0.vcf缺失** | OwnerCard由`BluetoothPbapConfig`控制 | `isProfileEnabled()`=false时不生成Owner vCard |
| **VCard编码乱码** | 部分车机仅支持ASCII | 确保`vcard21`模式使用QUOTED-PRINTABLE编码非ASCII字符 |

### 6.2 MAP常见问题与对策

| 问题 | 原因 | 对策 |
|------|------|------|
| **MNS连接断开** | 车机MNS Server异常关闭 | MNS Client检测`onConnectionStateChanged(DISCONNECTED)`后自动重连 |
| **bMessage编码错乱** | GSM 7-bit vs UTF-8不匹配 | 检查`ENCODING:`和`CHARSET:`头部，优先使用`Charset=UTF-8` |
| **通知风暴** | SMS快速接收+N条→MNS多次推送 | MNS有`MNS_NOTIFICATION_DELAY=10ms`防抖，但不能根本解决 |
| **长消息分片** | FractionRequest/Response | `FractionRequest=0`(不拆分)→单次获取完整消息 |
| **SMS不支持** | `mSmsCapable=false` | 检查TelephonyManager.isSmsCapable() |

### 6.3 车载配置建议

```
// PBAP:
- 车机(PCE) → 开启PBAP Client
  - 下载属性: 去掉PHOTO减少传输量 (车机屏幕大不一定要照片)
  - 下载批大小: 250条/批，通话记录优先(fav→pb→ich/och/mch)
  - 版本计数器: 使用增量更新，启动时快速检查

- 手机(PSE) → 开启PBAP Server
  - SDP特性: 0x021F (Download+Browse)
  - SIM: 如果不需要读取SIM联系人，关闭isSimEnabled()

// MAP:
- 车机(MCE+MNS Server) → 开启MAP Client
  - MAS实例: 如需读取Email,注册MAS_ID=1+
  - MNS: 必须注册NotificationRegistration才能收到新短信推送
  - 过滤器: FilterMessageType=SMS_GSM (只收SMS,过滤邮件垃圾)

- 手机(MAS+MNS Client) → 开启MAP Server
  - 配置Email Provider (Gmail/Exchange等)
  - SMS/MMS始终可用(MAS_ID=0)
```

### 6.4 调试命令

```bash
# PBAP PSE Server开关
adb shell svc bluetooth enable/disable pbap

# MAP Server开关
adb shell svc bluetooth enable/disable map

# 查看PBAP/MAP SDP记录
adb shell dumpsys bluetooth_manager | grep -A 20 "PBAP\|MAP"

# PBAP 日志
adb shell setprop log.tag.BluetoothPbapService VERBOSE
adb shell setprop log.tag.BluetoothPbapObexServer VERBOSE

# MAP 日志
adb shell setprop log.tag.BluetoothMapService VERBOSE
adb shell setprop log.tag.BluetoothMapObexServer VERBOSE
adb shell setprop log.tag.BluetoothMnsObexClient VERBOSE
```

---

## 七、关键源代码文件索引

### PBAP Server (PSE)

| 文件 | 路径 |
|------|------|
| BluetoothPbapService.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbap/BluetoothPbapService.java) |
| PbapStateMachine.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbap/PbapStateMachine.java) |
| BluetoothPbapObexServer.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbap/BluetoothPbapObexServer.java) |
| BluetoothPbapConfig.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbap/BluetoothPbapConfig.java) |

### PBAP Client (PCE)

| 文件 | 路径 |
|------|------|
| PbapClientStateMachine.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbapclient/PbapClientStateMachine.java) |
| PbapSdpRecord.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbapclient/PbapSdpRecord.java) |
| PullPhonebookRequest.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbapclient/obex/PullPhonebookRequest.java) |
| PbapApplicationParameters.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbapclient/obex/PbapApplicationParameters.java) |
| PbapClientContactsStorage.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/pbapclient/PbapClientContactsStorage.java) |

### MAP

| 文件 | 路径 |
|------|------|
| BluetoothMapService.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapService.java) |
| BluetoothMapObexServer.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapObexServer.java) |
| BluetoothMapContent.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapContent.java) |
| BluetoothMapContentObserver.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapContentObserver.java) |
| BluetoothMnsObexClient.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMnsObexClient.java) |
| BluetoothMapAppParams.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapAppParams.java) |
| BluetoothMapbMessage.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapbMessage.java) |
| BluetoothMapUtils.java | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/android/app/src/com/android/bluetooth/map/BluetoothMapUtils.java) |

### Framework API

| 文件 | 路径 |
|------|------|
| BluetoothPbap.java (PSE API) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothPbap.java) |
| BluetoothPbapClient.java (PCE API) | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/framework/java/android/bluetooth/BluetoothPbapClient.java) |

### Native C/C++层

| 文件 | 路径 |
|------|------|
| bta_pbs_int.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/pb/bta_pbs_int.h) |
| btif_storage.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_storage.cc) |
| btif_profile_storage.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/include/btif_profile_storage.h) |