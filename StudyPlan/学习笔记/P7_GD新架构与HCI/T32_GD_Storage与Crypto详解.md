# T32 GD Storage与Crypto详解

> 学习日期：2026-05-16
> 使用工具：Trae+DS-v4-pro
> 关键收获：
> 1. Storage采用**三层ConfigCache架构**（information_sections + persistent_devices + LRU temporary_devices）实现持久化与临时数据分离
> 2. 通过**Mutation模式**实现事务性配置修改，Mutation.Commit()原子提交所有变更
> 3. Crypto Toolbox实现蓝牙规范定义的完整SMP安全函数链（c1→s1→f4→f5→f6→g2→h6→h7）
> 4. BidiQueue是GD层间通信核心数据结构，实现栈层次间的双向生产者-消费者队列
> 5. Metrics提供蓝牙全生命周期度量日志接口（适配器状态/绑定/Profile连接/ACL连接/芯片信息/LE隐私/Mmc转码）

---

## 1. GD Storage 模块

### 1.1 架构总览

Storage模块是GD栈的**设备配置持久化存储后端**，负责管理配对设备信息、Link Key、设备属性等数据。核心设计采用**内存缓存 + 延迟写磁盘**策略：

```
StorageModule (入口层)
├── impl (PIMPL隐藏实现)
│   ├── ConfigCache cache_              ← 持久化配置缓存 (写磁盘)
│   ├── ConfigCache memory_only_cache_  ← 仅内存配置缓存 (不写磁盘，上限10000设备)
│   └── Alarm config_save_alarm_        ← 延迟保存定时器 (默认3秒)
├── Device / ClassicDevice / LeDevice   ← 类型化设备访问接口
├── Mutation / MutationEntry            ← 事务性配置修改
└── ConfigCacheHelper                   ← 类型安全的配置读写包装器
```

**关键源码**：[storage_module.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/storage_module.h#L49-L197)，[storage_module.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/storage_module.cc#L84-L138)

---

### 1.2 ConfigCache — 内存中的Section-Key-Value结构

[ConfigCache](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/config_cache.h#L54-L157) 是Storage的**内存数据核心**，采用INI风格的 Section→Key→Value 三层结构。

#### 三个数据分区：

| 分区 | 数据结构 | 用途 | 是否持久化 |
|------|----------|------|-----------|
| `information_sections_` | `ListMap<string, ListMap<string, string>>` | 通用配置（适配器信息、时间戳等） | ✅ 写磁盘 |
| `persistent_devices_` | `ListMap<string, ListMap<string, string>>` | 已配对设备信息 | ✅ 写磁盘 |
| `temporary_devices_` | `LruCache<string, ListMap<string, string>>` | 未配对临时设备（LRU淘汰） | ❌ 仅内存 |

```cpp
// config_cache.h 核心成员
class ConfigCache {
private:
  mutable std::recursive_mutex mutex_;
  std::function<void()> persistent_config_changed_callback_;
  std::unordered_set<std::string_view> persistent_property_names_;

  common::ListMap<std::string, common::ListMap<std::string, std::string>> information_sections_;
  common::ListMap<std::string, common::ListMap<std::string, std::string>> persistent_devices_;
  common::LruCache<std::string, common::ListMap<std::string, std::string>> temporary_devices_;
};
```

#### Persistent vs Temporary 判定逻辑：

- **Section变为Persistent**：当该Section的某个Property在 `persistent_property_names_` 集合中（如 LinkKey 属性）
- **Section变为Temporary**：当该Section中所有 `persistent_property_names_` 属性被移除
- **Temporary Devices上限**：默认10000个设备，基于LRU自动淘汰

#### 核心API：

```cpp
// 观察者
virtual bool HasSection(const std::string& section) const;
virtual bool HasProperty(const std::string& section, const std::string& property) const;
virtual std::optional<std::string> GetProperty(const std::string& section, const std::string& property) const;
virtual std::vector<std::string> GetPersistentSections() const;
virtual std::string SerializeToLegacyFormat() const;

// 修改器
virtual void Commit(std::queue<MutationEntry>& mutation);  // 原子提交变更队列
virtual void SetProperty(std::string section, std::string property, std::string value);
virtual bool RemoveSection(const std::string& section);
virtual void SetPersistentConfigChangedCallback(std::function<void()> callback);
```

---

### 1.3 StorageModule — 存储模块主入口

[StorageModule](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/storage_module.h#L49-L197) 是外部访问存储层的**唯一入口**，负责：

#### 构造函数 — 初始化流程：

```cpp
// storage_module.cc:L84-L138
StorageModule::StorageModule(os::Handler* handler, std::string config_file_path, ...)
{
  // 1. 检查 Factory Reset 标志 → 删除配置文件
  if (os::GetSystemProperty("persist.bluetooth.factoryreset") == "true") {
    LegacyConfigFile::FromPath(config_file_path_).Delete();
  }

  // 2. 校验 config checksum → 不通过则删除配置
  if (!is_config_checksum_pass(kConfigFileComparePass)) {
    LegacyConfigFile::FromPath(config_file_path_).Delete();
  }

  // 3. 从磁盘读取配置 or 创建新配置
  auto config = LegacyConfigFile::FromPath(config_file_path_).Read(temp_devices_capacity_);
  if (!config || !config->HasSection(kAdapterSection)) {
    config.emplace(temp_devices_capacity_, Device::kLinkKeyProperties);
    config->SetProperty(kInfoSection, kTimeCreatedProperty, "2026-05-16 ...");
  }

  // 4. 设置 PersistentConfigChanged 回调 → 每次持久配置变更自动触发延迟保存
  pimpl_->cache_.SetPersistentConfigChangedCallback(
    [this] { handler_->CallOn(this, &StorageModule::SaveDelayed); });

  // 5. FixDeviceTypeInconsistencies (修复旧栈遗留的DeviceType不一致问题)
  pimpl_->cache_.FixDeviceTypeInconsistencies();
}
```

#### 三种设备寻址方式：

| 方法 | 寻址方式 | 适用场景 |
|------|----------|----------|
| `GetDeviceByLegacyKey(address)` | 旧版Key MAC地址（包含随机地址） | 迁移兼容、LE设备尚未配对时 |
| `GetDeviceByClassicMacAddress(address)` | BR/EDR 固定MAC地址 | 经典蓝牙设备 |
| `GetDeviceByLeIdentityAddress(address)` | LE Identity地址（解析后的静态地址） | LE设备配对后 |

```cpp
Device GetDeviceByLegacyKey(hci::Address legacy_key_address);
Device GetDeviceByClassicMacAddress(hci::Address classic_address);
Device GetDeviceByLeIdentityAddress(hci::Address le_identity_address);
std::vector<Device> GetBondedDevices();  // 获取全部已配对设备
```

#### 延迟保存机制（防抖写入）：

```cpp
static const std::chrono::milliseconds kDefaultConfigSaveDelay = std::chrono::milliseconds(3000);
static const std::chrono::milliseconds kMinConfigSaveDelay = std::chrono::milliseconds(20);

void StorageModule::SaveDelayed() {
  // 如果已有pending操作，跳过（防抖）
  if (pimpl_->has_pending_config_save_) return;
  // 设置3秒后延迟保存
  pimpl_->config_save_alarm_.Schedule(
    common::BindOnce(&StorageModule::SaveImmediately, common::Unretained(this)),
    config_save_delay_);
  pimpl_->has_pending_config_save_ = true;
}

void StorageModule::SaveImmediately() {
  // 取消pending alarm
  pimpl_->config_save_alarm_.Cancel();
  pimpl_->has_pending_config_save_ = false;
  // 序列化写入磁盘
  LegacyConfigFile::FromPath(config_file_path_).Write(pimpl_->cache_);
  // Common Criteria模式写入checksum
  if (IsCommonCriteriaMode()) {
    GetBtKeystoreInterface()->set_encrypt_key_or_remove_key(kConfigFilePrefix, kConfigFileHash);
  }
}
```

**设计精妙之处**：3秒延迟防抖 —— 连续多次配置变更不会导致多次写磁盘，而是合并一次写入。析构函数中如果有pending save会强制 `SaveImmediately()`。

---

### 1.4 Device / ClassicDevice / LeDevice — 类型化设备抽象

#### Device (通用设备)

[Device](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/device.h#L122-L224) 提供与设备类型无关的通用属性访问。

**宏驱动的属性生成器**：

```cpp
#define GENERATE_PROPERTY_GETTER_SETTER_REMOVER(NAME, RETURN_TYPE, PROPERTY_KEY)
public:
  std::optional<RETURN_TYPE> Get##NAME() const {
    return ConfigCacheHelper(*config_).Get<RETURN_TYPE>(section_, PROPERTY_KEY);
  }
  MutationEntry Set##NAME(const RETURN_TYPE& value) {
    return MutationEntry::Set<RETURN_TYPE>(..., section_, PROPERTY_KEY, value);
  }
  MutationEntry Remove##NAME() {
    return MutationEntry::Remove(..., section_, PROPERTY_KEY);
  }
```

Device通过宏自动生成以下属性方法：

| 属性 | Get/Set/Remove | 类型 |
|------|---------------|------|
| Name | GetName/SetName/RemoveName | std::string |
| ClassOfDevice | GetClassOfDevice/SetClassOfDevice | hci::ClassOfDevice |
| DeviceType | GetDeviceType/SetDeviceType (OR运算) | hci::DeviceType |
| ServiceUuids/ServiceUuidsLe | Get/Set/Remove | vector<hci::Uuid> |
| ManufacturerCode/LmpVersion/LmpSubVersion | ... | uint16_t/uint8_t/uint16_t |
| MetricsId/PinLength/CreationUnixTimestamp | ... | int/int/int |

**三种Property类型宏**：

| 宏 | 属性类型 | 持久化 | 适用范围 |
|----|---------|--------|---------|
| `GENERATE_PROPERTY_GETTER_SETTER_REMOVER` | NORMAL | ✅ 写磁盘 | 固定属性 |
| `GENERATE_TEMP_PROPERTY_GETTER_SETTER_REMOVER` | MEMORY_ONLY | ❌ 不写磁盘 | 临时属性，重启丢失 |
| `GENERATE_PROPERTY_GETTER_SETTER_REMOVER_WITH_CUSTOM_SETTER` | NORMAL+自定义Setter | ✅ | DeviceType(OR累加) |

#### ClassicDevice — 经典蓝牙专属

[ClassicDevice](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/classic_device.h#L31-L90) 管理经典蓝牙特有属性：

```cpp
class ClassicDevice {
public:
  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(LinkKey, hci::LinkKey, "LinkKey");
  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(LinkKeyType, hci::KeyType, "LinkKeyType");
  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(SdpDiManufacturer, uint16_t, "SdpDiManufacturer");
  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(SdpDiModel, uint16_t, "SdpDiModel");
  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(SdpDiHardwareVersion, uint16_t, "SdpDiHardwareVersion");
  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(SdpDiVendorIdSource, uint16_t, "SdpDiVendorIdSource");

  bool IsPaired() const;  // 检查是否有LinkKey属性 → 判定已配对
  hci::Address GetAddress() const;
};
```

#### LeDevice — LE设备专属

[LeDevice](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/le_device.h#L29-L92) 管理LE设备特有安全信息：

```cpp
class LeDevice {
public:
  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(AddressType, hci::AddressType, BTIF_STORAGE_KEY_ADDR_TYPE);
  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(PeerId, std::string, BTIF_STORAGE_KEY_LE_KEY_PID);
  // PeerId = IRK + Identity Address Type + Identity Address

  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(PeerEncryptionKeys, std::string, BTIF_STORAGE_KEY_LE_KEY_PENC);
  // PeerEncryptionKeys = LTK + RAND + EDIV + Security Level + Key Length

  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(PeerSignatureResolvingKeys, std::string, BTIF_STORAGE_KEY_LE_KEY_PCSRK);
  // PeerCSRK = counter + CSRK + Security Level

  GENERATE_PROPERTY_GETTER_SETTER_REMOVER(LegacyPseudoAddress, hci::Address, "LeLegacyPseudoAddr");

  bool IsPaired() const;
};
```

**存储的关键安全信息**：
- **PeerId**：IRK（Identity Resolving Key）+ 身份地址类型 + 身份地址 → LE隐私地址解析
- **PeerEncryptionKeys**：LTK（Long Term Key）+ RAND + EDIV + 安全等级 + Key长度 → LE加密
- **PeerSignatureResolvingKeys**：CSRK（Connection Signature Resolving Key）+ counter → 数据签名

---

### 1.5 Mutation模式 — 事务性配置修改

[MutationEntry](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/mutation_entry.h#L28-L117) + [Mutation](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/mutation.h#L26-L38) 提供**原子性批量配置修改**。

```cpp
class Mutation {
public:
  Mutation(ConfigCache* config, ConfigCache* memory_only_config);
  void Add(MutationEntry entry);  // 添加一个变更条目
  void Commit();                  // 原子提交所有pending变更

private:
  ConfigCache* config_;
  ConfigCache* memory_only_config_;
  std::queue<MutationEntry> normal_config_entries_;       // 持久化配置变更队列
  std::queue<MutationEntry> memory_only_config_entries_;  // 仅内存配置变更队列
};

class MutationEntry {
public:
  enum EntryType { SET, REMOVE_PROPERTY, REMOVE_SECTION };
  enum PropertyType { NORMAL, MEMORY_ONLY };

  // 模板型Set方法 —— 支持int/enum/bool/string/Serializable/vector<Serializable>
  template<typename T> static MutationEntry Set(PropertyType, section, property, value);
  static MutationEntry Remove(PropertyType, section);           // REMOVE_SECTION
  static MutationEntry Remove(PropertyType, section, property); // REMOVE_PROPERTY
};
```

#### 使用示例：

```cpp
// 获取Mutation句柄
auto mutation = storage_module->Modify();

// 添加多个变更操作
mutation.Add(device.SetClassOfDevice(cod_value));
mutation.Add(device.Classic().SetLinkKey(peer_link_key));
mutation.Add(device.Classic().SetLinkKeyType(link_key_type));

// 一次性原子提交 —— ConfigCache::Commit() 持锁处理所有变更
mutation.Commit();

// Commit后 → PersistentConfigChangedCallback → SaveDelayed() → 3秒后写磁盘
```

**Mutation的价值**：
- 原子性：Commit()过程中持有 `recursive_mutex`，中间状态不会被读线程看到
- 类型安全：Set<T>模板 + `std::enable_if` SFINAE，编译期检查类型合法性
- 分离Normal/MemoryOnly：持久配置变更自动触发写磁盘；内存变更不持久化

---

### 1.6 ConfigCacheHelper — 类型安全配置包装器

[ConfigCacheHelper](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/config_cache_helper.h#L39-L151) 在 ConfigCache（仅支持string Get/Set）之上提供类型化访问。

**支持的Get<T>模板特化**：

| T | 实现方式 |
|---|----------|
| 有符号整数 (int, int64_t, ...) | GetInt64 → 范围检查 → static_cast |
| 无符号整数 (uint32_t, ...) | GetUint64 → 范围检查 → static_cast |
| std::string | 透传 GetProperty |
| std::vector<uint8_t> | GetBin |
| bool | GetBool |
| Serializable<T> | GetProperty → T::FromLegacyConfigString() |
| 枚举类型 | GetProperty → FromLegacyConfigString<T>() |
| vector<Serializable<T::value_type>> | StringSplit(" ") → 逐个 FromLegacyConfigString |

**范围安全性**：
```cpp
template<typename T>
std::optional<T> Get(const std::string& section, const std::string& property) {
  auto value = GetInt64(section, property);  // 底层存int64
  if (!value) return std::nullopt;
  if (!common::IsNumberInNumericLimits<T>(*value)) return std::nullopt;
  return static_cast<T>(*value);  // 安全截断
}
```

---

### 1.7 存储持久化架构总结

```
ConfigCache (内存)                     LegacyConfigFile (磁盘)
┌─────────────────────────────┐       ┌─────────────────────┐
│  information_sections_      │───→   │ [Info]              │
│    {section→{key→value}}    │       │ TimeCreated=...     │
│                             │       │                     │
│  persistent_devices_        │───→   │ [AA:BB:CC:DD:EE:FF] │
│    {MAC→{LinkKey=..., ...}} │       │ LinkKey=...         │
│                             │       │ DevType=1           │
│  temporary_devices_ (LRU)   │  ❌   │ Name=MyCar          │
│    {RandomMAC→{Name=...}}   │(不写) │                     │
└─────────────────────────────┘       └─────────────────────┘
         ↑ 变更触发 ↑                       ↑ 序列化 ↑
    PersistentConfigChanged    ──→    SaveDelayed (3s防抖)
        Callback                      SaveImmediately
```

---

## 2. GD Crypto Toolbox

### 2.1 模块架构

```
crypto_toolbox/
├── aes.h / aes.cc        ← Brian Gladman AES-128/256实现 (纯8-bit操作)
├── aes_cmac.cc           ← AES-CMAC (基于AES-128的CBC-MAC)
└── crypto_toolbox.h/cc   ← 蓝牙SMP安全函数 (c1, s1, f4, f5, f6, g2, h6, h7)
```

**源码文件**：[crypto_toolbox.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/crypto_toolbox.h)，[crypto_toolbox.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/crypto_toolbox.cc)

---

### 2.2 AES实现 ([aes.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/aes.h))

采用 **Brian Gladman** 的经典AES实现，特点：**纯8-bit字节操作加密状态**（`uint_8t`），不依赖硬件加速。

**编译选项（全部开启）**：
```cpp
#define AES_ENC_PREKEYED  // 预计算密钥表加密
#define AES_DEC_PREKEYED  // 预计算密钥表解密
#define AES_ENC_128_OTFK  // On-The-Fly 128-bit key加密
#define AES_DEC_128_OTFK  // On-The-Fly 128-bit key解密
#define AES_ENC_256_OTFK  // On-The-Fly 256-bit key加密
#define AES_DEC_256_OTFK  // On-The-Fly 256-bit key解密
```

**两种密钥模式**：

| 模式 | 描述 | 适用场景 |
|------|------|---------|
| **PREKEYED** | 先调用 `aes_set_key()` 预计算密钥表，后续加解密快速 | 重复使用同一密钥（如批量数据加解密） |
| **OTFK (On The Fly)** | 每次加解密时动态计算密钥表，返回解密所需密钥 | 一次性操作（蓝牙配对多为一次性密钥） |

**核心API**：
```cpp
// 预计算模式
return_type aes_set_key(const unsigned char key[], length_type keylen, aes_context ctx[1]);
return_type aes_encrypt(const unsigned char in[16], unsigned char out[16], const aes_context ctx[1]);
return_type aes_decrypt(const unsigned char in[16], unsigned char out[16], const aes_context ctx[1]);

// OTFK模式 — 同时返回解密密钥
void aes_encrypt_128(const unsigned char in[16], unsigned char out[16],
                     const unsigned char key[16], uint_8t o_key[16]);
```

---

### 2.3 蓝牙SMP安全函数链

[crypto_toolbox.cc](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/crypto_toolbox.cc) 实现了蓝牙核心规范定义的完整安全函数。

#### 基础加密原语：

```cpp
Octet16 aes_128(const Octet16& key, const Octet16& message);      // AES-128加密
Octet16 aes_cmac(const Octet16& key, const uint8_t* msg, uint16_t len);  // AES-CMAC签名
Octet16 h6(const Octet16& w, std::array<uint8_t, 4> keyid);       // W → aes_cmac(W, keyID)
Octet16 h7(const Octet16& salt, const Octet16& w);                // W → aes_cmac(salt, W)
```

#### SMP安全函数及其用途：

| 函数 | 签名 | 蓝牙规范用途 | 算法要点 |
|------|------|-------------|---------|
| **c1** | `c1(k, r, pres, preq, iat, ia, rat, ra) → Octet16` | **配对确认值** (Pairing Confirm) | r ← p1 XOR; p1bis = aes_128(k, p1); p2 ← p1bis XOR; → aes_128(k, p2) |
| **s1** | `s1(k, r1, r2) → Octet16` | **STK生成** (Secure Temporary Key) | 取r1前半+r2后半拼接 → aes_128(k, text) |
| **f4** | `f4(U, V, X, Z=0) → Octet16` | **DHKey Check** — 验证双方拥有相同DHKey | msg = Z‖V‖U → aes_cmac(X, msg) |
| **f5** | `f5(W, N1, N2, A1, A2, *mac_key, *ltk)` | **LTK与MAC Key生成** (LE Legacy配对) | T = aes_cmac(salt, W); counter=0→MAC_Key; counter=1→LTK |
| **f6** | `f6(W, N1, N2, R, IOcap, A1, A2) → Octet16` | **配对确认/检查值** (LE Secure Connections) | msg = A2‖A1‖IOcap‖R‖N2‖N1 → aes_cmac(W, msg) |
| **g2** | `g2(U, V, X, Y) → uint32_t` | **配对6位数字比较值** | msg = Y‖V‖U → aes_cmac(X, msg) → le32 → mod 1000000 (取低6位) |
| **h6** | `h6(W, keyID) → Octet16` | **密钥推导** — 从主密钥派生子密钥 | aes_cmac(W, keyID) |
| **h7** | `h7(salt, W) → Octet16` | **密钥推导** — 带salt的密钥派生 | aes_cmac(salt, W) |

#### f5详细流程（LTK+MAC Key生成）：

```cpp
void f5(const uint8_t* w, const Octet16& n1, const Octet16& n2,
        uint8_t* a1, uint8_t* a2, Octet16* mac_key, Octet16* ltk) {
  // Step 1: T = aes_cmac(salt, W)
  const Octet16 salt{0xBE, 0x83, 0x60, 0x5A, 0xDB, 0x0B, 0x37, 0x60,
                     0x38, 0xA5, 0xF5, 0xAA, 0x91, 0x83, 0x88, 0x6C};
  Octet16 t = aes_cmac(salt, w, kOctet32Length);

  const uint8_t key_id[4] = {0x65, 0x6c, 0x74, 0x62}; // "btle"小端
  const uint8_t length[2] = {0x00, 0x01};              // 0x0100

  // Step 2: counter=0 → MAC_Key = aes_cmac(T, 0‖keyID‖N1‖N2‖A1‖A2‖Length)
  *mac_key = calculate_mac_key_or_ltk(t, 0, key_id, n1, n2, a1, a2, length);

  // Step 3: counter=1 → LTK = aes_cmac(T, 1‖keyID‖N1‖N2‖A1‖A2‖Length)
  *ltk = calculate_mac_key_or_ltk(t, 1, key_id, n1, n2, a1, a2, length);
}
```

#### g2 — 6位数字验证码：

```cpp
uint32_t g2(const uint8_t* u, const uint8_t* v, const Octet16& x, const Octet16& y) {
  // msg = Y ‖ V ‖ U (共80字节)
  Octet16 cmac = aes_cmac(x, msg);
  // vres = cmac的低32位 mod 1,000,000 → 6位数字
  return le32toh(*(uint32_t*)cmac.data()) % 1000000;
}
```

**车载场景意义**：g2生成的6位数字比较值就是用户在手机和车机上看到的**配对PIN码**，双方比较一致才确认配对。

---

### 2.4 Key转换 — LE ↔ Classic

```cpp
Octet16 ltk_to_link_key(const Octet16& ltk, bool use_h7);  // LE LTK → Classic LinkKey
Octet16 link_key_to_ltk(const Octet16& link_key, bool use_h7);  // Classic LinkKey → LE LTK
```

**转换路径**：
```
ltk_to_link_key:
  if (use_h7): ILK = h7("1pmt...", ltk)
  else:         ILK = h6(ltk, "tmp1")
  LinkKey = h6(ILK, "lebr")

link_key_to_ltk:
  if (use_h7): ILTK = h7("2pmt...", link_key)
  else:         ILTK = h6(link_key, "tmp2")
  LTK = h6(ILTK, "brle")
```

**车载意义**：车机连接手机时可能同时使用BR/EDR（A2DP/HFP）和BLE（GATT/手机互联），需要在LE生成的LTK和Classic需要的LinkKey之间互相转换。在Dual Mode设备场景中至关重要。

---

## 3. GD Common 工具

### 3.1 BidiQueue — 双向通信队列

[BidiQueue](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/bidi_queue.h) 是GD架构**层次间数据通信的核心数据结构**。

```cpp
template <typename TUP, typename TDOWN>
class BidiQueue {
public:
  BidiQueueEnd<TDOWN, TUP>* GetUpEnd();    // 上层端点
  BidiQueueEnd<TUP, TDOWN>* GetDownEnd();  // 下层端点

private:
  os::Queue<TUP>    up_queue_;     // 上行: 下层→→→→→→→上层 (数据向上)
  os::Queue<TDOWN>  down_queue_;   // 下行: 上层→→→→→→→下层 (数据向下)
  BidiQueueEnd<TDOWN, TUP>   up_end_;   // 上层看到的TX=down_queue, RX=up_queue
  BidiQueueEnd<TUP, TDOWN>    down_end_; // 下层看到的TX=up_queue, RX=down_queue
};
```

**数据流向图解**：

```
    上层 (Host)
      │  RX: 从 up_queue_ 取   TX: 写入 down_queue_
      │
  ┌───┴──────────────┐
  │  BidiQueueEnd    │  ← up_end_ (上端点)
  │  TX=down_queue   │
  │  RX=up_queue     │
  └──────────────────┘
         │  │
  up_queue(TUP)  down_queue(TDOWN)
         │  │
  ┌──────┴──┴────────┐
  │  BidiQueueEnd    │  ← down_end_ (下端点)
  │  TX=up_queue     │
  │  RX=down_queue   │
  └──────────────────┘
      │
    下层 (Controller)
      │  RX: 从 down_queue_ 取   TX: 写入 up_queue_
```

**在GD中的使用**：
- **HCI Layer ↔ ACL Manager**：ACL数据包双向传递
- **HCI Layer ↔ SCO Manager**：SCO音频数据双向传递
- **L2CAP ↔ HCI Layer**：L2CAP PDU双向封装/解封装

```cpp
// BidiQueueEnd提供注册回调机制
void RegisterEnqueue(os::Handler* handler, EnqueueCallback callback);  // 有数据可发送时回调
void RegisterDequeue(os::Handler* handler, DequeueCallback callback);  // 有新数据到达时回调
std::unique_ptr<TDEQUEUE> TryDequeue();  // 非阻塞取数据
```

---

### 3.2 BlockingQueue — 阻塞队列

[BlockingQueue](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/blocking_queue.h#L28-L74) 基于 `std::condition_variable` 实现线程安全的生产者-消费者模式。

```cpp
template <typename T>
class BlockingQueue {
public:
  void push(T data) {
    std::unique_lock<std::mutex> lock(mutex_);
    queue_.push(std::move(data));
    if (queue_.size() == 1) not_empty_.notify_all();  // 仅首次push通知
  }

  T take() {
    std::unique_lock<std::mutex> lock(mutex_);
    while (queue_.empty()) not_empty_.wait(lock);  // 阻塞等待
    T data = queue_.front(); queue_.pop();
    return data;
  }

  bool wait_to_take(std::chrono::milliseconds time) {
    std::unique_lock<std::mutex> lock(mutex_);
    while (queue_.empty()) {
      if (not_empty_.wait_for(lock, time) == std::cv_status::timeout) return false;
    }
    return true;
  }
};
```

**关键设计**：
- `push` 只在队列从空变为非空时 `notify_all()`（而非每次都通知）
- `take` 阻塞等待直到有数据
- `wait_to_take` 带超时的等待，用于优雅关闭

---

### 3.3 CircularBuffer — 环形缓冲区

[CircularBuffer](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/circular_buffer.h) 基于 `std::deque` 实现固定大小的环形缓冲区。

```cpp
template <typename T>
class CircularBuffer {
public:
  explicit CircularBuffer(size_t size);
  void Push(T item);                   // Push+自动淘汰旧元素
  std::vector<T> Pull() const;        // 快照拷贝，不清理
  std::vector<T> Drain();             // Move取出并清空

private:
  const size_t size_;
  std::deque<T> queue_;
  mutable std::mutex mutex_;
};

// Push实现 → 超过size自动pop_front
template <typename T>
void CircularBuffer<T>::Push(const T item) {
  std::unique_lock<std::mutex> lock(mutex_);
  queue_.push_back(item);
  while (queue_.size() > size_) queue_.pop_front();
}
```

**派生类 — TimestampedCircularBuffer**：

```cpp
template <typename T>
struct TimestampedEntry {
  uint64_t timestamp;
  T entry;
};

template <typename T>
class TimestampedCircularBuffer : public CircularBuffer<TimestampedEntry<T>> {
  void Push(T item) {
    TimestampedEntry<T> entry{timestamper_->GetTimestamp(), item};
    CircularBuffer<TimestampedEntry<T>>::Push(entry);
  }
};
```

**实用场景**：`TimestampedStringCircularBuffer` — 带时间戳的日志环形缓冲区，Push时自动截断到255字符。在Snoop Logger和调试日志中常用。

---

### 3.4 LruCache — LRU缓存

[LruCache](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/lru_cache.h#L34-L198) 实现**最近最少使用淘汰策略**的键值缓存。

```cpp
template <typename Key, typename T>
class LruCache {
public:
  explicit LruCache(size_t capacity);  // capacity不能为0（assert检查）

  // find/contains 会 "预热" key → 将key移到List头部
  iterator find(const Key& key);
  bool contains(const Key& key) const;

  // insert_or_assign → key存在则更新值；不存在则插入头部，capacity满则淘汰尾部
  std::optional<node_type> insert_or_assign(const Key& key, T value);

  // try_emplace → 原地构造value，key已存在则返回false不覆盖
  std::tuple<iterator, bool, std::optional<node_type>> try_emplace(const Key& key, Args&&...);

  std::optional<node_type> extract(const Key& key);
  iterator erase(const_iterator iter);

private:
  size_t capacity_;
  ListMap<Key, T> list_map_;  // List → 保持插入/访问顺序；Map → O(1)查找
};
```

**LRU语义**：
- `find(key)` → 将key移到List头部（warm up）
- `insert_or_assign(key, val)` → key存在则更新值并移到头部；不存在且capacity满则淘汰List尾部
- 遍历不会warm up key；`splice`操作不触发warm up

**在Storage中的使用**：`ConfigCache::temporary_devices_` 使用LruCache管理临时设备，上限10000。

---

### 3.5 Callback / Bind — Chromium回调封装

```cpp
// callback.h
using base::Callback;       // 可多次调用的回调
using base::Closure;        // 无参数的Callback<void()>
using base::OnceCallback;   // 只能调用一次的回调
using base::OnceClosure;    // 无参数的OnceCallback<void()>
```

GD的异步编程模型**大量依赖chromium base库的回调机制**：
- `Callback` → 可拷贝，多次调用
- `OnceCallback` → 只可移动，调用一次后失效（更安全）

---

### 3.6 StopWatch — 性能计时器

[StopWatch](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/stop_watch.h#L23-L64) 用于**HCI HAL收发性能测量**。

```cpp
class StopWatch {
public:
  static StopWatchBuffer hciHalTxBuffer_;  // HCI发送性能缓冲
  static StopWatchBuffer hciHalRxBuffer_;  // HCI接收性能缓冲

  StopWatch(StopWatchBuffer& buffer, std::string text);  // 构造时记录start
  ~StopWatch();  // 析构时记录end → 写入buffer
};

struct StopWatchLog {
  std::chrono::system_clock::time_point timestamp;       // 发生时间
  std::chrono::high_resolution_clock::time_point start_timestamp;
  std::chrono::high_resolution_clock::time_point end_timestamp;
  std::string message;
};
```

**使用方式（RAII自动计时）**：
```cpp
void HciHalImpl::send_hci_command(...) {
  StopWatch stop_watch(StopWatch::hciHalTxBuffer_, "HCI CMD: " + bytes);
  // ... 发送操作 ...
}  // stop_watch析构 → 自动记录耗时
```

---

### 3.7 其他Common工具一览

| 文件 | 功能 | 要点 |
|------|------|------|
| [contextual_callback.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/contextual_callback.h) | 绑定到执行上下文的回调 | `ContextualOnceCallback` / `ContextualCallback`，调用时通过 `IPostableContext::Post()` 投递 |
| [strings.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/strings.h) | 字符串工具 | ToHexString/FromHexString/StringTrim/StringSplit/StringJoin/StringFormat |
| [numbers.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/numbers.h) | 数值范围检查 | `IsNumberInNumericLimits<T>` 模板 |
| [type_helper.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/type_helper.h) | 类型特征 | `is_specialization_of<T, Template>` — 判断是否某模板的特化 |
| [byte_array.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/byte_array.h) | 固定字节数组 | 继承 `packet::CustomFieldFixedSizeInterface` + `storage::Serializable` |
| [multi_priority_queue.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/multi_priority_queue.h) | 多优先级队列 | 高优先级项优先出队 |
| [sync_map_count.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/sync_map_count.h) | 线程安全计数Map | 支持按计数排序 |
| [audit_log.h](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/audit_log.h) | 连接审计日志 | 记录蓝牙连接历史 |

---

## 4. GD Metrics — 蓝牙性能度量

[Metrics](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/metrics/metrics.h#L24-L53) 提供**蓝牙全生命周期度量日志接口**，用于统计分析和性能监控。

```cpp
namespace bluetooth::metrics {

// 适配器状态变化 (ON/OFF/TURNING_ON/TURNING_OFF)
void LogMetricsAdapterStateChanged(uint32_t state);

// 配对创建尝试
void LogMetricsBondCreateAttempt(RawAddress* addr, uint32_t device_type);

// 配対状态变化 (包括失败原因)
void LogMetricsBondStateChanged(RawAddress* addr, uint32_t device_type,
  uint32_t status, uint32_t bond_state, int32_t fail_reason);

// 设备信息上报 (CoD/Appearance/Vendor/Product/Version)
void LogMetricsDeviceInfoReport(RawAddress* addr, uint32_t device_type,
  uint32_t class_of_device, uint32_t appearance, uint32_t vendor_id,
  uint32_t vendor_id_src, uint32_t product_id, uint32_t version);

// Profile连接状态变化 (A2DP/HFP/AVRCP/HID/...)
void LogMetricsProfileConnectionStateChanged(RawAddress* addr,
  uint32_t profile, uint32_t status, uint32_t state);

// ACL连接尝试
void LogMetricsAclConnectAttempt(RawAddress* addr, uint32_t acl_state);

// ACL连接状态变化 (transport/status/state/direction/hci_reason)
void LogMetricsAclConnectionStateChanged(RawAddress* addr, uint32_t transport,
  uint32_t status, uint32_t acl_state, uint32_t direction, uint32_t hci_reason);

// 芯片信息上报
void LogMetricsChipsetInfoReport();

// Suspend Id状态
void LogMetricsSuspendIdState(uint32_t state);

// LE隐私状态 (llp_state + rpa_state)
void LogMetricsLLPrivacyState(uint32_t llp_state, uint32_t rpa_state);

// Mmc转码RTT统计 (max_rtt/mean_rtt/num_requests/codec_type)
void LogMetricMmcTranscodeRttStats(int maximum_rtt, double mean_rtt,
  int num_requests, int codec_type);

}
```

**Metrics监控维度总结**：

| 监控维度 | 函数 | 车载关注点 |
|---------|------|------------|
| **适配器状态** | LogMetricsAdapterStateChanged | 蓝牙开关频率/异常关机 |
| **配对事件** | LogMetricsBondCreateAttempt + BondStateChanged | 配对成功率/失败原因分布 |
| **设备信息** | LogMetricsDeviceInfoReport | 连接设备类型统计（手机/手表/OBD...） |
| **Profile连接** | LogMetricsProfileConnectionStateChanged | A2DP/HFP连接成功率 |
| **ACL连接** | LogMetricsAclConnectionStateChanged | 底层连接异常（HCI reason） |
| **芯片信息** | LogMetricsChipsetInfoReport | 芯片型号/固件版本 |
| **LE隐私** | LogMetricsLLPrivacyState | LE RPA旋转频率 |
| **音频转码** | LogMetricMmcTranscodeRttStats | Mmc转码延迟（车载WBS/SWB） |

---

## 5. 对车载开发的启示

### 5.1 Storage相关

| 场景 | 建议 |
|------|------|
| **配对设备上限** | ConfigCache默认`temp_devices_capacity=10000`，但persistent_devices无硬上限。车载如需要限制配对数量，应在App层控制 |
| **配置文件损坏** | StorageModule构造时会做checksum校验，不通过自动删除重建。切勿手动修改bt_config.conf |
| **Factory Reset** | 设置 `persist.bluetooth.factoryreset=true` 然后重启蓝牙，配置自动清空 |
| **LinkKey丢失** | `ClassicDevice::IsPaired()` 检查是否存在LinkKey属性。丢失会导致重新配对 |

### 5.2 Crypto相关

| 场景 | 建议 |
|------|------|
| **g2配对码验证** | 6位数字对比是配对安全的关键环节。如果车机和手机显示不同PIN码，说明中间人攻击（MITM） |
| **LTK ↔ LinkKey转换** | Dual Mode设备（同时BR/EDR+LE）配对时，LTK和LinkKey需要正确转换。转换失败会导致BLE服务无法使用但Classic正常 |
| **LE隐私地址** | LeDevice.PeerId存储IRK用于解析RPA。IRK丢失会导致无法识别已配对LE设备（每次显示为陌生设备） |

### 5.3 Common工具在车载中的应用

| 工具 | 车载场景 |
|------|---------|
| **BidiQueue** | HCI层→ACL管理器→L2CAP层之间，A2DP音频数据+HFP AT命令同时传递 |
| **BlockingQueue** | SCO音频编解码线程 → HAL层写数据 |
| **LruCache** | 临时设备列表（OBD/TPMS等频繁上下的IoT设备，避免占用持久存储） |
| **StopWatch** | HCI HAL Tx/Rx延迟监控——车载芯片延迟排查关键工具 |

---

## 6. 源码文件参考

### Storage模块 (20个文件)

| 文件 | 路径 |
|------|------|
| storage_module.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/storage_module.h) |
| storage_module.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/storage_module.cc) |
| device.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/device.h) |
| device.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/device.cc) |
| classic_device.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/classic_device.h) |
| classic_device.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/classic_device.cc) |
| le_device.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/le_device.h) |
| le_device.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/le_device.cc) |
| config_cache.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/config_cache.h) |
| config_cache.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/config_cache.cc) |
| config_cache_helper.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/config_cache_helper.h) |
| config_cache_helper.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/config_cache_helper.cc) |
| mutation.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/mutation.h) |
| mutation.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/mutation.cc) |
| mutation_entry.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/mutation_entry.h) |
| mutation_entry.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/mutation_entry.cc) |
| legacy_config_file.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/legacy_config_file.h) |
| legacy_config_file.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/legacy_config_file.cc) |
| serializable.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/serializable.h) |
| config_keys.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/storage/config_keys.h) |

### Crypto Toolbox模块 (5个文件)

| 文件 | 路径 |
|------|------|
| crypto_toolbox.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/crypto_toolbox.h) |
| crypto_toolbox.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/crypto_toolbox.cc) |
| aes.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/aes.h) |
| aes.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/aes.cc) |
| aes_cmac.cc | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/crypto_toolbox/aes_cmac.cc) |

### Common工具模块 (4个核心文件)

| 文件 | 路径 |
|------|------|
| bidi_queue.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/bidi_queue.h) |
| blocking_queue.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/blocking_queue.h) |
| circular_buffer.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/circular_buffer.h) |
| lru_cache.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/lru_cache.h) |
| callback.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/callback.h) |
| stop_watch.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/common/stop_watch.h) |

### Metrics模块 (1个文件)

| 文件 | 路径 |
|------|------|
| metrics.h | [link](file:///d:/AndroidWorkspace/claudeProject/BT16Study/Bluetooth/system/gd/metrics/metrics.h) |