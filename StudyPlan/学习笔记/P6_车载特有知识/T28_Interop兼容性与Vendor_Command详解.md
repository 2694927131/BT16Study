# T28 Interop兼容性与Vendor Command详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：Interop 55+ feature枚举+6种匹配方式 | 动态Interop运行时学习 | Vendor Specific Command (OGF=0x3F) | Qualcomm/Broadcom VSC | 车载Interop实战Top10 | 自定义VSC集成
> 待回顾问题：无

---

## 1. Interop系统架构

### 1.1 设计理念

Interop (Interoperability) 系统解决**不同厂商蓝牙设备的兼容性问题**：当某个手机/车机的蓝牙实现不符合标准规范时，通过Interop feature为其设置特定的工作区（Workaround）。

```
interop_database.conf (静态配置文件)
  │ 启动时加载
  ▼
interop.cc (匹配引擎)
  │ interop_match_addr / interop_match_name / interop_match_addr_or_name
  ▼
各模块代码 (消费Feature)
  │ btm_pm.cc: INTEROP_DISABLE_SNIFF
  │ bta_ag_act.cc: INTEROP_DELAY_SCO_FOR_MT_CALL
  │ avrc_api.cc: INTEROP_AVRCP_1_3_ONLY
  │ ...
  ▼
运行时动态学习
  │ interop_database_add_addr() → 发现新不兼容设备
  ▼
interop_database.conf (可选持久化)
```

---

## 2. Interop Feature 枚举

### 2.1 全部Feature (55+)

源码：[interop.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/device/include/interop.h)

```
车载高频使用的Interop Features:

┌─────────────────────────────────────────────────────────────────┐
│ Feature                               │ 说明                   │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_DISABLE_ABSOLUTE_VOLUME       │ 禁用Absolute Volume    │
│                                       │ 应对不支持AVRCP 1.4+   │
│                                       │ 的手机/车机            │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_DISABLE_ROLE_SWITCH           │ 禁用角色切换           │
│                                       │ 某些车机切换Master/Slave│
│                                       │ 后出现异常             │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_DISABLE_SNIFF                 │ 禁用Sniff省电模式      │
│                                       │ 某些设备进入Sniff后    │
│                                       │ 无法正常唤醒           │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_DISABLE_SNIFF_DURING_CALL     │ 通话期间禁用Sniff      │
│                                       │ 防止SCO与Sniff冲突     │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_DISABLE_SNIFF_DURING_SCO      │ SCO活动期间禁用Sniff   │
│                                       │ HID设备Sniff冲突SCO    │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_DISABLE_CODEC_NEGOTIATION     │ 跳过Codec协商          │
│                                       │ 慢速设备超时, 直接SBC  │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_INCREASE_AG_CONN_TIMEOUT      │ 增加AG连接超时         │
│                                       │ 车机启动AT协商较慢时   │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_HFP_FAKE_INCOMING_CALL_       │ 修正MT来电指示         │
│   INDICATOR                           │ 解决carkit来电显示异常 │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_HFP_SEND_CALL_INDICATORS_     │ 背靠背发送呼叫指示     │
│   BACK_TO_BACK                        │ VOIP场景解决时序问题   │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_DELAY_SCO_FOR_MT_CALL         │ 来电时延迟SCO建链      │
│                                       │ 先完成CIEV再SCO        │
│                                       │ 解决BSA音频无声音问题  │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_AVRCP_1_3_ONLY                │ 强制AVRCP 1.3          │
│ INTEROP_AVRCP_1_4_ONLY                │ 强制AVRCP 1.4          │
│                                       │ 兼容老车机的AVRCP版本  │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_A2DP_DELAY_DISCONNECT         │ 延迟A2DP断开           │
│                                       │ 避免A2DP→HFP切换时     │
│                                       │ A2DP过早断开           │
├─────────────────────────────────────────────────────────────────┤
│ INTEROP_DYNAMIC_ROLE_SWITCH           │ 动态角色切换denylist   │
│                                       │ 运行时自动添加         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Feature启用示例

**interop_database.conf 配置**（[interop_database.conf](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/conf/interop_database.conf)）：

```ini
# 示例1: 某品牌旧款车机不支持Absolute Volume
[INTEROP_DISABLE_ABSOLUTE_VOLUME]
XX:XX:XX = Address_Based       # 匹配特定BD_ADDR的3字节前缀
"OLD-CAR-KIT" = Name_Based     # 匹配设备名称

# 示例2: 某手机需要跳过Codec协商
[INTEROP_DISABLE_CODEC_NEGOTIATION]
0017 = Manufacturer_Based      # 匹配LMP Manufacturer ID

# 示例3: 动态角色切换黑名单
[INTEROP_DYNAMIC_ROLE_SWITCH]
XX:XX:XX = Address_Based       # 运行时动态添加
```

**6种匹配方式**：

| 匹配方式 | 格式 | 说明 |
|----------|------|------|
| `Address_Based` | AA:BB:CC | 匹配BD_ADDR前3字节(厂商OUI) |
| `Name_Based` | "Device Name" | 完全匹配设备名称 |
| `Manufacturer_Based` | 0017 | LMP Manufacturer ID (2字节hex) |
| `Vndr_Prdt_Based` | 0013:1200 | DID VendorID:ProductID |
| `Version_Based` | DID Version | 匹配DID Version |
| `Address_Range_Based` | AA:BB:CC:DD:EE→FF | 匹配完整地址范围 |

---

## 3. Interop API

### 3.1 查询API

```cpp
// 按BD_ADDR匹配(3字节前缀)
bool interop_match_addr(const interop_feature_t feature, const RawAddress* addr);

// 按设备名称匹配
bool interop_match_name(const interop_feature_t feature, const char* name);

// 组合匹配(先name再addr, 简化调用)
bool interop_match_addr_or_name(const interop_feature_t feature, const RawAddress* addr);
```

### 3.2 动态添加API

```cpp
// 运行时动态添加到Interop数据库(内存中, 不持久化)
void interop_database_add_addr(const interop_feature_t feature, 
                                const RawAddress* addr, int length);

// 清除动态Interop
void interop_database_clear();
```

### 3.3 使用示例

**示例1：在Sniff控制中使用**

```cpp
// btm_pm.cc - 决定是否允许进入Sniff
if (interop_match_addr(INTEROP_DISABLE_SNIFF, &remote_bda)) {
    log::warn("Sniff disabled for {} due to interop", remote_bda);
    return;  // 不进入Sniff模式
}
```

**示例2：在AVRCP中使用**

```cpp
// sdp_utils.cc - 限制AVRCP版本
if (interop_match_addr(INTEROP_AVRCP_1_3_ONLY, &remote_bda)) {
    avrcp_version = AVRC_1_3_STRING;  // 强制1.3版本
}
if (interop_match_addr(INTEROP_AVRCP_1_4_ONLY, &remote_bda)) {
    avrcp_version = AVRC_1_4_STRING;  // 强制1.4版本
}
```

**示例3：动态学习（运行时添加）**

```cpp
// btm_acl.cc - 检测到设备拒绝Role Switch → 动态添加到黑名单
if (!interop_match_addr(INTEROP_DYNAMIC_ROLE_SWITCH, &bd_addr)) {
    // 设备拒绝角色切换 → 永久禁止对该设备发起Role Switch
    interop_database_add_addr(INTEROP_DYNAMIC_ROLE_SWITCH, &bd_addr, 3);
}
```

---

## 4. Vendor Specific Command (VSC)

### 4.1 HCI VSC格式

```
OGF (Opcode Group Field) = 0x3F (Vendor-Specific)
OCF (Opcode Command Field) = 厂商自定义 (0x0000-0x03FF)

完整HCI命令:
  Opcode: 0xXXXX | (0x3F << 10)
  即: Opcode = (OGF << 10) | OCF = 0xFC00 | OCF
```

**VSC发送流程**：

```cpp
// 封装Vendor Command
uint8_t ogf = 0x3F;  // Vendor-Specific OGF
uint16_t ocf = vendor_ocf;

// 通过HCI层发送
btsnd_hcic_vendor_spec_cmd(
    opcode,              // OGF|OCF组合
    param_len,           // 参数长度
    params               // 参数数据
);

// 等待Controller返回
// HCI Event: Vendor_Specific_Event (0xFF)
```

### 4.2 车载常用VSC

#### Qualcomm (LMP MFID=0x001D/0x0017)

```cpp
// QCA VSC列表 (部分):
VS_QCA_Set_Sleep_Mode         // 设置休眠模式寄存器
VS_QCA_Write_BD_ADDR          // 写入蓝牙地址(量产烧录)
VS_QCA_Update_Baud_Rate       // 更新UART波特率(3M→4M)
VS_QCA_Set_COD                // 设置Class of Device
VS_QCA_Set_WBS_Config         // 配置WBS(宽带语音)参数
VS_QCA_Configure_LP_ASSERT    // 配置低功耗断言

// 车载场景: 设置TX Power
VS_QCA_Set_TX_Power_Table → 
  针对不同国家/地区法规设置RF发射功率
  EU: Class 1 (max 20dBm) → 调低至10dBm
  US: Class 1 (max 20dBm) → 保持20dBm
```

#### Broadcom/Cypress (LMP MFID=0x000F)

```cpp
// Broadcom/Infineon VSC:
VS_BCM_Set_Sleep_Mode         // Sleep模式配置
VS_BCM_Write_BD_ADDR          // 蓝牙地址写入
VS_BCM_Set_UART_Clock         // UART时钟配置
VS_BCM_Enable_WBS             // 启用WBS
VS_BCM_Set_SCO_PCM_Config     // SCO PCM/I2S配置
VS_BCM_AFH_Channel_Map        // AFH(自适应跳频)信道映射
VS_BCM_Coex_Config            // WiFi/BT共存配置
```

#### Realtek (LMP MFID=0x005D)

```cpp
// RTK VSC:
VS_RTK_Set_COD                // CoD配置
VS_RTK_Write_BD_ADDR          // BD_ADDR配置
VS_RTK_Set_AFH_Map            // AFH信道映射
```

### 4.3 Vendor HAL接口

车载芯片厂商需要实现 Vendor HAL：

```
vendor/<soc_manufacturer>/bluetooth/
  ├── vendor_hci.cpp       → VSC发送/响应处理
  ├── vendor_fw.cpp        → 固件下载/校验
  └── vendor_audio.cpp     → SCO PCM/I2S配置

主要接口:
  vendor_send_command(opcode, params, len) → 发送VSC
  vendor_recv_event(opcode, data, len)     → 接收VSE
  vendor_download_firmware()              → 下载固件patch
  vendor_configure_audio()                → 配置音频接口(PCM/I2S/TDM)
```

### 4.4 车载VSC实战场景

#### 场景1：UART波特率升级

```cpp
// 出厂默认: 3Mbps → 升级到 4Mbps (提升A2DP+SCO并发带宽)
void upgrade_baud_rate() {
    uint8_t param[] = {0x04}; // 4Mbps
    send_vsc(VS_QCA_Update_Baud_Rate, param, 1);
    // 等待确认 → 两侧切换波特率
}
```

#### 场景2：WiFi共存配置

```cpp
// 车载同时使用BT+WiFi(手机互联) → 需要共存配置
void config_bt_wifi_coex() {
    // 配置信道跳过(避免2.4GHz WiFi干扰)
    struct coex_config {
        uint8_t wifi_channel;     // WiFi信道 1-14
        uint8_t bt_skip_mask[10]; // BT跳过的频率mask
        uint8_t priority;         // BT优先(通话) / WiFi优先(数据)
    };
    send_vsc(VS_BCM_Coex_Config, &config, sizeof(config));
}
```

#### 场景3：SCO PCM时钟配置

```cpp
// I2S/PCM接口时钟 → 确保与车载DSP匹配
void config_sco_pcm() {
    struct pcm_config {
        uint8_t clock_rate;   // 128/256/512 kHz
        uint8_t frame_sync;   // 短帧/长帧同步
        uint8_t data_format;  // 16bit linear / 8bit A-law / 8bit µ-law
    };
    send_vsc(VS_BCM_Set_SCO_PCM_Config, &config, sizeof(config));
}
```

---

## 5. 自定义Interop (车载私有扩展)

### 5.1 车载特有Interop场景

```
手机品牌      │ 已知问题                │ Interop           │ 是否需要
──────────────┼─────────────────────────┼───────────────────┼──────────
iPhone 12+   │ AVRCP Absolute Volume异常 │ DISABLE_ABS_VOL   │ 视iOS版本
Samsung S23  │ LE Audio断开后无法恢复    │ DISABLE_LE_AUDIO  │ 是
Xiaomi MIUI  │ HFP服务发现返回额外字段   │ 兼容性SDP解析      │ 是
Huawei EMUI  │ A2DP编解码协商SBC参数异常 │ DISABLE_CODEC_NEG │ 已修复
OPPO/OnePlus │ 快连机制异常              │ INCREASE_CONN_TIMEO │ 是
Google Pixel │ 频繁断开LE连接            │ DISABLE_LE_COC    │ 偶发
```

### 5.2 添加自定义Interop Feature

```cpp
// 1. 在 interop.h 中添加新Feature
// system/device/include/interop.h
enum interop_feature_t {
    // ... 已有的Features ...
    INTEROP_OEM_FIRST = 0x1000,  // 厂商自定义起始值
    INTEROP_OEM_DISABLE_A2DP_CODEC_NEG = 0x1001,
    INTEROP_OEM_INCREASE_HFP_TIMEOUT = 0x1002,
};

// 2. 在 interop_database.conf 中添加匹配规则
[INTEROP_OEM_DISABLE_A2DP_CODEC_NEG]
XX:XX:XX = Address_Based  // 匹配特定手机OUI

// 3. 在代码中使用
if (interop_match_addr(INTEROP_OEM_DISABLE_A2DP_CODEC_NEG, &bd_addr)) {
    // 跳过A2DP codec协商, 强制使用SBC
    skip_codec_negotiation();
}
```

---

## 6. 车载Interop调试流程

### 6.1 新增设备兼容性问题

```
发现: 新增XX品牌手机, A2DP连接后无声

排查流程:
1. logcat收集 → 确认A2DP状态: state=Started
2. Snoop分析 → SET_CONFIG选择了AAC
   → 但Audio HAL反馈无数据

3. 测试其他codec:
   在btif_av.cc中强制SBC → 声音正常
   → 确认是AAC编解码不兼容

4. 添加Interop:
   → 将该手机OUI加入 INTEROP_DISABLE_CODEC_NEGOTIATION
   → 或添加自定义 Feature OEM_FORCE_SBC_FOR_XX
   → 在 btif_av.cc codec选择逻辑中检查并强制SBC
```

### 6.2 Interop验证流程

```
1. 修改 interop_database.conf → 加入匹配规则

2. 编译蓝牙协议栈
   → mmm system/bt -j32

3. 推送so文件
   → adb push *.so /vendor/lib64/

4. 重启蓝牙进程
   → adb shell svc bluetooth disable
   → adb shell svc bluetooth enable

5. 验证:
   [ ] 目标手机功能正常
   [ ] 其他手机不受影响 (未错误匹配)
   [ ] Snoop log验证协议交互正常

6. logcat验证Interop生效:
   adb logcat | grep -i "interop"
   → 确认 interop_match_addr 返回true
```

---

## 7. 调试速查

```bash
# 查看Interop配置
adb shell cat /vendor/etc/bluetooth/interop_database.conf

# 查看Interop匹配日志  
adb logcat | grep -i "interop"

# 强制禁用某个Feature测试
# 方法: 临时注释 interop_database.conf 中的规则 → 重启蓝牙
# 或: adb shell setprop persist.bluetooth.disable_abs_vol true

# Vendor Command日志(HCI层)
adb logcat | grep "hci_vendor"

# 查看蓝牙芯片信息(LMP MFID)
adb shell dumpsys bluetooth_manager | grep -E "manufacturer|lmp_ver"
```