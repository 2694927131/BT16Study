# T20 HID设备详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：HID双通道(Control 0x0011+Interrupt 0x0013)连接 | HOGP BLE HID UUID体系 | 5种Report类型+8种Transaction | HIDD车机做键盘的7步注册 | 车载HID典型场景分析
> 待回顾问题：无

---

## 1. HID架构总览

HID (Human Interface Device) Profile支持两种传输方式：

```
HID Profile
├── BR/EDR HID (Classic)
│   ├── Control Channel (L2CAP PSM=0x0011) → 控制命令(HANDSHAKE/GET-SET/VC_UNPLUG)
│   └── Interrupt Channel (L2CAP PSM=0x0013) → 数据上报(按键/鼠标移动)
│
└── HOGP (HID over GATT Profile) → BLE
    ├── HID Service (UUID 0x1812)
    │   ├── Protocol Mode (0x2A4E) → Boot/Report模式
    │   ├── Report Map (0x2A4B) → Report Descriptor
    │   ├── Report (0x2A4D) → 数据Report
    │   ├── HID Information (0x2A4A) → 设备信息
    │   ├── HID Control Point (0x2A4C) → 控制点
    │   ├── Boot Keyboard Input (0x2A22) → 键盘输入
    │   ├── Boot Keyboard Output (0x2A32) → 键盘输出(LED)
    │   └── Boot Mouse Input (0x2A33) → 鼠标输入
    └── Battery Service (UUID 0x180F) → 电量上报
```

**源码文件架构**：

```
App/Framework (Java)
    ↓ JNI
BTIF层
├── btif_hh.cc    → HID Host接口(车机连接外部HID设备)
└── btif_hd.cc    → HID Device接口(车机作为HID设备)
    ↓ btif_transfer_context
BTA层
├── bta/hh/       → BTA HID Host (bta_hh_act.cc, bta_hh_main.cc, bta_hh_le.cc)
└── (HIDD通过BTA JV直接调用Stack)
    ↓
Stack层
├── stack/hid/hidh_conn.cc → L2CAP双通道管理
└── stack/hid/hidd_api.cc  → HID Device SDP注册
```

---

## 2. BR/EDR HID — Classic连接

### 2.1 双通道架构

HID设备使用**两个L2CAP通道**，分别处理控制和数据：

| 通道 | PSM | 功能 | 数据方向 |
|------|-----|------|----------|
| Control | 0x0011 (HID_PSM_CONTROL) | GET/SET protocol、idle、report、VC Unplug | Host↔Device双向 |
| Interrupt | 0x0013 (HID_PSM_INTERRUPT) | 输入报告(按键/鼠标/传感器) | Device→Host为主 |

### 2.2 L2CAP连接状态机

源码：[hidh_conn.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/hid/hidh_conn.cc)

```
HID_CONN_STATE_UNUSED
  │ Control channel L2CAP Connect Request → PSM=0x0011
  ▼
HID_CONN_STATE_CONNECTING_CTRL
  │ Control connect confirm → L2CAP Config
  ▼
HID_CONN_STATE_CONFIG
  │ Control channel configured → 发起Interrupt channel连接
  ▼
HID_CONN_STATE_CONNECTING_INTR
  │ Interrupt connect confirm → L2CAP Config
  ▼
HID_CONN_STATE_CONFIG
  │ 双通道均配置完成
  ▼
HID_CONN_STATE_CONNECTED  ← 正常通信状态
  │ Disconnect
  ▼
HID_CONN_STATE_DISCONNECTING → UNUSED
```

**L2CAP回调表**（[hidh_conn.cc:L81-L96](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/hid/hidh_conn.cc#L81-L96)）：

```cpp
static const tL2CAP_APPL_INFO hst_reg_info = {
    .pL2CA_ConnectInd_Cb = hidh_l2cif_connect_ind,
    .pL2CA_ConnectCfm_Cb = hidh_l2cif_connect_cfm,
    .pL2CA_ConfigInd_Cb  = hidh_l2cif_config_ind,
    .pL2CA_ConfigCfm_Cb  = hidh_l2cif_config_cfm,
    .pL2CA_DisconnectInd_Cb = hidh_l2cif_disconnect_ind,
    .pL2CA_DisconnectCfm_Cb = hidh_l2cif_disconnect_cfm,
    .pL2CA_DataInd_Cb    = hidh_l2cif_data_ind,
    .pL2CA_CongestionStatus_Cb = hidh_l2cif_cong_ind,
};
```

### 2.3 BTA状态机（上层）

源码：[bta_hh_int.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/hh/bta_hh_int.h)

```
4个状态：
BTA_HH_IDLE_ST     → 空闲，等待API_OPEN
BTA_HH_W4_CONN_ST  → 等待连接（SDP查询中/L2CAP连接中）
BTA_HH_CONN_ST     → 已连接，处理数据
BTA_HH_W4_SEC      → 等待加密完成

17个事件，关键事件：
BTA_HH_API_OPEN_EVT    → 应用层发起连接
BTA_HH_SDP_CMPL_EVT    → SDP查询完成（BR/EDR）
BTA_HH_GATT_OPEN_EVT   → GATT连接完成（HOGP）
BTA_HH_INT_DATA_EVT    → Interrupt通道收到数据
BTA_HH_INT_CTRL_DATA   → Control通道收到数据
BTA_HH_INT_HANDSK_EVT  → 收到HANDSHAKE消息
```

### 2.4 HID数据帧格式

**HID Protocol事务类型** ([hiddefs.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/stack/include/hiddefs.h))：

| 类型 | 值 | 说明 | 方向 |
|------|-----|------|------|
| HANDSHAKE | 0x00 | 握手确认 | Device→Host |
| CONTROL | 0x01 | 控制命令(含参数) | Host→Device |
| GET_REPORT | 0x04 | 请求Report | Host→Device |
| SET_REPORT | 0x05 | 设置Report | Host→Device |
| GET_PROTOCOL | 0x06 | 查询协议模式 | Host→Device |
| SET_PROTOCOL | 0x07 | 设置协议模式 | Host→Device |
| GET_IDLE | 0x08 | 查询空闲率 | Host→Device |
| SET_IDLE | 0x09 | 设置空闲率 | Host→Device |
| DATA | 0x0A | 数据(Interrupt通道) | Device→Host |
| DATAC | 0x0B | 数据(Control通道) | Device→Host |

**控制命令参数**：

| 参数 | 值 | 说明 |
|------|-----|------|
| NOP | 0x00 | 空操作 |
| HARD_RESET | 0x01 | 硬复位 |
| SOFT_RESET | 0x02 | 软复位 |
| SUSPEND | 0x03 | 挂起 |
| EXIT_SUSPEND | 0x04 | 退出挂起 |
| VIRTUAL_CABLE_UNPLUG | 0x05 | 虚拟拔线 |

### 2.5 BTIF层连接流程

源码：[btif_hh.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_hh.cc)

```
1. btif_hh_connect(bd_addr)                    ← Framework调用
   │ btif_transfer_context → BTIF线程
   ▼
2. hh_open_handler()                           ← 检查连接策略
   │ 检查是否允许HID连接(车机可能禁止输入设备)
   ▼
3. BTA_HhOpen(link_spec, direct)               ← BTA层
   │ → bta_hh_sm_execute(BTA_HH_API_OPEN_EVT)
   ▼
4. BR/EDR路径: SDP查询 → L2CAP双通道连接
   HOGP路径: GATT连接 → 服务发现 → 特征订阅
   ▼
5. hh_open_handler() 收到OPEN完成
   │ 添加设备到hh_dev_cb列表
   │ 打开UHID驱动(/dev/uhid) → Linux内核收到HID设备
   ▼
6. 后续数据: HID_DATA_EVT → UHID write → 内核输入子系统
```

**关键日志**：
```bash
adb logcat -s bt_btif_hh bt_bta_hh  # HID Host
adb logcat -s BTIF_HD               # HID Device
```

---

## 3. HOGP — BLE HID实现

### 3.1 BLE连接流程

源码：[bta_hh_le.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/hh/bta_hh_le.cc)

```
阶段1: BLE扫描发现
  HOGP设备广播 → AD中包含 HID Service UUID (0x1812)

阶段2: BLE连接
  GATT连接 → bta_hh_gatt_open()

阶段3: GATT服务发现
  发现HID Service (0x1812)
    ├── 发现 HID Information Characteristic (0x2A4A)
    ├── 发现 Report Map Characteristic (0x2A4B) → 读取Report Descriptor
    ├── 发现 Report Characteristic (0x2A4D) → 订阅Notification
    ├── 发现 Boot Keyboard Input (0x2A22) → 订阅Notification
    └── 发现 Battery Service (0x180F) → 读取电量

阶段4: 数据上报
  GATT Notification → Report数据 → UHID → 内核输入系统
```

### 3.2 HOGP关键UUID映射

**UUID→Report类型映射表**（[bta_hh_le.cc:L84-L89](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/hh/bta_hh_le.cc#L84-L89)）：

```cpp
static const uint16_t bta_hh_uuid_to_rtp_type[][2] = {
    {GATT_UUID_HID_REPORT,          BTA_HH_RPTT_INPUT},   // 通用Report
    {GATT_UUID_HID_BT_KB_INPUT,     BTA_HH_RPTT_INPUT},   // 键盘输入
    {GATT_UUID_HID_BT_KB_OUTPUT,    BTA_HH_RPTT_OUTPUT},  // 键盘输出(LED)
    {GATT_UUID_HID_BT_MOUSE_INPUT,  BTA_HH_RPTT_INPUT},   // 鼠标输入
    {GATT_UUID_BATTERY_LEVEL,       BTA_HH_RPTT_INPUT}};  // 电量
```

**HOGP协议模式**（[bta_hh_le.cc:L72-L73](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/bta/hh/bta_hh_le.cc#L72-L73)）：

| 模式 | 值 | 说明 |
|------|-----|------|
| Boot Mode | 0x00 | 固定8字节Report，兼容BIOS级别 |
| Report Mode | 0x01 | 自定义Report格式，功能完整 |

### 3.3 Report Reference Descriptor

每个Report Characteristic通过 **Report Reference Descriptor**（0x2908）关联到Report Map中的具体Report ID：

```
Report Characteristic (0x2A4D)
  ├── Properties: Read | Notify
  ├── Value: 原始Report数据
  └── Descriptor: Report Reference (0x2908)
        ├── Report ID: 0x01  ← 对应Report Map中的report_id=1
        └── Report Type: Input/Output/Feature
```

---

## 4. HID设备类型与Report Descriptor

### 4.1 键盘 (Keyboard)

```
Usage Page: 0x07 (Keyboard/Keypad)
Usage: 0x06 (Keyboard)

Report Descriptor (典型8字节):
  Byte 0: Modifier keys (Ctrl/Shift/Alt/GUI, bitmask)
  Byte 1: Reserved
  Bytes 2-7: Key codes (6键同时按下, 0x00=无按键)

按键值示例:
  0x04 = 'a', 0x1A = 'w', 0x28 = Enter, 0x29 = Esc
  Modifier: bit0=LCtrl, bit1=LShift, bit2=LAlt, bit3=LGUI
```

**车载应用**：蓝牙键盘输入（浏览器/导航搜索）、HVAC物理按键映射

### 4.2 鼠标 (Mouse)

```
Usage Page: 0x01 (Generic Desktop)
Usage: 0x02 (Mouse)

Report Descriptor (典型4-5字节):
  Byte 0: Buttons (bitmask: Left/Middle/Right)
  Byte 1-2: X位移 (有符号, -127~127)
  Byte 3-4: Y位移 (有符号)
  (可选) Wheel: 1字节滚轮值
```

### 4.3 遥控器 (Remote Control)

```
Usage Page: 0x0C (Consumer)
Usage: 0x01 (Consumer Control)

Report Descriptor (2-3字节):
  Usage ID示例:
    0xB0 = Play, 0xB1 = Pause, 0xB3 = Fast Forward
    0xB5 = Next Track, 0xB6 = Previous Track
    0xE9 = Volume Up, 0xEA = Volume Down, 0xE2 = Mute
```

**车载应用**：后排娱乐系统遥控器

### 4.4 游戏手柄 (Gamepad)

```
Usage Page: 0x01 (Generic Desktop)
Usage: 0x05 (Gamepad)

Report包含:
  - 方向键 (D-Pad): 4方向(0-7共8种组合)
  - 模拟摇杆: X/Y轴 (0-255)
  - 按钮: 最多16个按钮bitmask
  - 触发器: 模拟值
```

---

## 5. 车机作为HID Device (btif_hd.cc)

### 5.1 HIDD架构

源码：[btif_hd.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_hd.cc)，HAL接口：[bt_hd.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/include/hardware/bt_hd.h)

```
车机(Android Auto)→扮演HID Device→连接手机/平板
    角色: 触摸屏模拟鼠标 + 虚拟键盘
```

### 5.2 HIDD注册流程（7步）

```
1. init() → btif_config检查已配对HIDD
   │ 加载bonded HIDD device
   ▼
2. register_app(name, description, descriptor)
   │ BTA_HdRegisterApp → 注册App参数
   │ 包含: Report Descriptor全文(HID Parser能力描述)
   ▼
3. register_app回调 → application_state_cb(REGISTERED)
   │
   ▼
4. HID_Host端SDP查询 → 发现HIDD SDP Record
   │ HID_DevAddRecord() 注册的SDP Record包含：
   │   服务类: UUID_SERVCLASS_HUMAN_INTERFACE (0x1124)
   │   协议: L2CAP PSM=HIDC + HIDP，附加L2CAP PSM=HIDI
   │   属性: 设备名/描述/Provider/Subclass/CountryCode/VirtualCable
   │   描述符: HID Report Descriptor全文
   │
   ▼
5. Host发起连接 → BTA_HD_OPEN_EVT
   │ connection_state_cb(CONNECTED)
   ▼
6. 数据交互:
   │ Host→Device(BTA_HD_GET_REPORT_EVT): Host请求获取Report
   │ Host→Device(BTA_HD_SET_REPORT_EVT): Host设置指示灯/功能
   │ Device→Host(send_report): 发送按键/坐标数据
   │
   ▼
7. Host断开(BTA_HD_CLOSE_EVT)或VC_Unplug
   │ connection_state_cb(DISCONNECTED)
```

### 5.3 Class of Device (COD)配置

源码：[btif_hd.cc:L62-L65](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/btif/src/btif_hd.cc#L62-L65)

```cpp
#define COD_HID_KEYBOARD 0x0540  // 键盘
#define COD_HID_POINTING 0x0580  // 指点设备(鼠标/触控)
#define COD_HID_COMBO    0x05C0  // 复合设备(键盘+鼠标)
#define COD_HID_MAJOR    0x0500  // HID大类
```

**车载应用场景**：
- **CarPlay/Android Auto模式**：车机注册为HIDD触控设备 → iPhone连接后可以操作车机屏幕
- **副驾/后排投屏控制**：车机转发触摸事件给手机
- **车载键盘输入**：车机模拟蓝牙键盘给手机

### 5.4 HID Host ↔ HID Device 角色互斥

HID Host和HID Device**不能同时启用**，存在互相切换机制：

```
启用HIDD时: btif_hh_service_registration(FALSE) → 关闭HID Host
关闭HIDD时: btif_hh_service_registration(TRUE)  → 恢复HID Host
```

---

## 6. 车载HID实战场景

### 6.1 蓝牙遥控器连接

```
场景: 后排娱乐屏配蓝牙遥控器

连接流程:
1. 遥控器进入配对模式
2. 车机扫描 → 发现HID设备(COD=0x0540)
3. 配对Bond → 自动连接
4. 按键通过Interrupt通道上报

常见问题:
- 遥控器按键映射错误 → 检查Report Descriptor中的Usage定义
- 休眠后无法唤醒 → BLE HID需要正确配置Connection Interval
```

### 6.2 BLE HID 休眠唤醒问题

```
BLE HID常见休眠模式:
  Boot Mode → 低功耗, 固定8字节, 适合BIOS/唤醒场景
  Report Mode → 全功能, 自定义Report, 适合正常使用

问题: 手机休眠后BLE HID断连
原因: Connection Interval过大 + Latency过高 → 链路超时

解决方案:
  → 调整LE连接参数: Interval=7.5ms, Latency=0, Timeout=2000ms
  → 启用HID Control Point(0x2A4C) → Suspend/Exit Suspend控制
```

### 6.3 车机作为HIDD的触控场景

```
场景: CarPlay触控反向控制

车机(HIDD) → iPhone(HID Host)
  触摸事件 → send_report(type=INPUT, data=[buttons, X, Y])
  多点触控 → 多个Report, 含Contact Count + 各点坐标

关键: Report Descriptor必须声明为 Multi-Touch Digitizer:
  Usage Page: 0x0D (Digitizer)
  Usage: 0x04 (Touch Screen)
  支持: Contact Count, Contact ID, X/Y Position
```

---

## 7. HID调试速查

### 日志TAG
```bash
adb logcat -s bt_btif_hh bt_bta_hh BTIF_HD  # 全HID日志
```

### Snoop过滤器
```
# BR/EDR HID: L2CAP PSM 0x0011/0x0013
bthci_acl && (btl2cap.psm == 0x0011 || btl2cap.psm == 0x0013)

# HOGP: GATT HID Service 
btatt.service_uuid16 == 0x1812

# HID SDP查询
btsdp
```

### 常见问题速查

| 问题 | 排查要点 |
|------|----------|
| HID连接后无响应 | 检查UHID驱动是否打开(`ls /dev/uhid`) |
| 按键映射错误 | 对比Report Descriptor与内核keymap |
| BLE HID经常断连 | 检查Connection Interval是否过大 |
| HIDD注册失败 | 检查是否已关闭HID Host（互斥） |
| VirtualCableUnplug | Host发送了VC_Unplug→需要重新配对 |