# T09_A2DP编解码器协商详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. 编解码器优先级: SBC(必选)→AAC→aptX→aptX-HD→LDAC→LC3→Opus，由 btif_av_co.cc 的 bta_av_co_init 加载
2. 协商流程: AVDT GET_CAPABILITIES(双方能力)→取交集→选最高优先级→AVDT SET_CONFIGURATION(参数)→OPEN
3. Offload 模式编解码在DSP完成，通过 audio_hal_interface/a2dp_encoding.cc 管理，不经过CPU
4. 运行时切换: setCodecConfigPreference→btif_av_reconfig_req_t→BTIF_AV_RECONFIGURE_REQ_EVT→AVDT Reconfigure
5. 车载强制编解码: bta_av_co_set_codec_user_config + MandatoryCodecPreferred 标记

## 详细笔记

### 编解码器列表与优先级

Android 支持的编解码器 (stack/include/a2dp_codec_api.h):

| 编解码器 | codec_index | 采样率 | 声道 | 比特率范围 | 优先级 |
|----------|------------|--------|------|-----------|--------|
| SBC | BTAV_A2DP_CODEC_INDEX_SOURCE_SBC | 16/32/44.1/48kHz | Mono/Stereo | 192-345kbps | 必选(最低) |
| AAC | BTAV_A2DP_CODEC_INDEX_SOURCE_AAC | 44.1/48kHz | Stereo | 128-320kbps | 高 |
| aptX | BTAV_A2DP_CODEC_INDEX_SOURCE_APTX | 44.1/48kHz | Stereo | 352kbps | 高 |
| aptX-HD | BTAV_A2DP_CODEC_INDEX_SOURCE_APTX_HD | 44.1/48kHz | Stereo | 576kbps | 很高 |
| LDAC | BTAV_A2DP_CODEC_INDEX_SOURCE_LDAC | 44.1/48/88.2/96kHz | Stereo | 330/660/990kbps | 很高 |
| LC3 | BTAV_A2DP_CODEC_INDEX_SOURCE_LC3 | 8/16/24/32/44.1/48kHz | Mono/Stereo | 16-320kbps | 中(LE Audio) |
| Opus | BTAV_A2DP_CODEC_INDEX_SOURCE_OPUS | 48kHz | Stereo | 32-510kbps | 中 |

优先级通过 bta_av_co_init [btif_av_co.h L74]:
```cpp
void bta_av_co_init(const std::vector<btav_a2dp_codec_config_t>& codec_priorities,
                    std::vector<btav_a2dp_codec_info_t>* supported_codecs);
```
codec_priorities 从 Java 层传入，可用户配置

### 协商流程

```
1. 本地编解码器列表 (按优先级排序)
2. AVDT: GET_CAPABILITIES → 获取远端支持的编解码器列表
3. bta_av_co.cc 取交集: 本地列表 ∩ 远端列表
4. 选择交集中优先级最高的编解码器
5. 确定参数: 采样率/声道模式/比特率/帧长度等
6. AVDT: SET_CONFIGURATION → 配置选定的编解码器
7. 远端确认 → 协商完成
8. AVDT: OPEN → 媒体通道建立

协商失败 → 降级到 SBC (必选编解码器)
```

**btif_av_co.cc 选择逻辑**:
- `bta_av_co_audio_getconfig()` — 获取音频配置
- `bta_av_co_audio_setconfig()` — 设置音频配置
- `bta_av_co_get_codec_cap()` — 获取编解码器能力
- `bta_av_co_set_codec_user_config()` — 设置用户偏好编解码器

### A2DP Offload 模式下的编解码协商

Offload 编解码器通过 HAL 注册:
```
audio_hal_interface/a2dp_encoding.cc → 注册 Offload 编解码器能力
→ btif_a2dp_audio_interface.cc → 将 Offload 编解码器加入本地能力列表
```

Offload vs Software 协商差异:
| 对比项 | Software | Offload |
|--------|----------|---------|
| 能力来源 | A2DP Codec 库 | HAL 注册 + Vendor 配置 |
| 协商代码路径 | btif_av_co.cc | btif_av_co.cc (能力列表不同) |
| 选择逻辑 | 同 Software | 同，但可能多出 Vendor 专用编解码器 |
| 配置位置 | SBC/AAC encoder 参数 | DSP 编解码器参数 |

**ro.bluetooth.a2dp_offload.supported** → 决定是否走 Offload 路径

### 编解码器切换 (Reconfigure)

```
App: BluetoothA2dp.setCodecConfigPreference(config)
→ btif_av.cc: btif_av_reconfig_req_t [L122]
  → codec_preferences: vector<btav_a2dp_codec_config_t>
  → reconf_ready_promise: 同步等待
→ do_in_main_thread → ProcessEvent(BTIF_AV_RECONFIGURE_REQ_EVT)
→ StateMachine → AVDT Reconfigure
  → 远端重新 GET_CAPABILITIES
  → 重新 SET_CONFIGURATION
  → 成功 → 新编解码器生效
  → 失败 → 保持当前编解码器
```

**MandatoryCodecPreferred** [L343]:
```cpp
void SetMandatoryCodecPreferred(bool preferred);
bool IsMandatoryCodecPreferred() const;
// 车载场景: 强制使用特定编解码器(如SBC)而不是自动选择最优
```

### 车载特殊场景

1. **强制编解码器**: `bta_av_co_set_codec_user_config()` + `SetMandatoryCodecPreferred(true)` → 忽略优先级，强制使用指定编解码器
2. **编解码器白名单**: 通过 `btav_a2dp_codec_config_t.codec_priority` 和 `codec_type` 限制可用编解码器
3. **DSP 离线编解码**: Vendor HAL 提供 Offload 编解码器，优先级通常最高

### 常见问题定位

- 协商结果不符合预期: 检查 bta_av_co.cc 日志，看 `peer_sink_capabilities` 和 `selectable_codec`
- 编解码器参数不兼容: SBC Bitpool 范围不一致 → 降级到双方最小范围
- Offload 初始化失败: 检查 audio_hal_interface 日志 → 降级到 Software