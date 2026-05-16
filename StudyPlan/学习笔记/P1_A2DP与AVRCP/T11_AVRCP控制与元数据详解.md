# T11_AVRCP控制与元数据详解

> 学习日期：2026-05-16 | 工具：Trae+DS-v4-pro | 状态：已完成

## 关键收获
1. AVRCP角色: CT(Controller=控制端)→车机控制手机播放，TG(Target=被控端)→手机控制车机状态，车机通常同时实现CT和TG
2. 控制命令: send_passthrough_cmd→BTA_AvRemoteCmd→AVCT→手机，支持PLAY/PAUSE/STOP/NEXT/PREV/FF/REW
3. 元数据通过AVRC_PDU_GET_ELEMENT_ATTR获取(BTRC_MEDIA_ATTR_ID_TITLE/ARTIST/ALBUM/PLAYING_TIME等)
4. Absolute Volume(车载关键): set_volume_rsp [L3124] 响应手机SetAbsoluteVolume→车机调整音量→volume_change_notification_rsp同步回手机
5. 新旧实现: btif_rc.cc(旧)+avrcp_service.cc(新,Android13+)共存，车机通过Feature Flag启用新实现

## 详细笔记

### 一、AVRCP 角色和版本

**CT vs TG**:
| 角色 | 全称 | 职责 | 车机场景 |
|------|------|------|----------|
| CT | Controller | 发送控制命令(Play/Pause/Next) | 车机控制手机播放 |
| TG | Target | 响应控制命令+上报状态 | 手机控制车机(音量等) |

车机通常是 CT+TG 双角色：播放控制用CT，音量同步用TG(Absolute Volume)。

**AVRCP版本特性** (bt_rc.h L86-L92):
```cpp
BTRC_FEAT_NONE = 0x00           // AVRCP 1.0 基本控制
BTRC_FEAT_METADATA = 0x01       // AVRCP 1.3 元数据(歌曲信息)
BTRC_FEAT_ABSOLUTE_VOLUME = 0x02 // TG角色+音量同步
BTRC_FEAT_BROWSE = 0x04         // AVRCP 1.4+ 浏览功能
BTRC_FEAT_COVER_ARTWORK = 0x08  // AVRCP 1.6+ 封面艺术
```

### 二、AVRCP 控制命令

**btrc_ctrl_interface_t 接口表 [L3292-L3310]**:
```cpp
static const btrc_ctrl_interface_t bt_rc_ctrl_interface = {
    init_ctrl,
    send_passthrough_cmd,        // Play/Pause/Stop/Next/Previous
    send_groupnavigation_cmd,    // 上/下/左/右/确定
    change_player_app_setting,   // 更改播放器设置(Shuffle/Repeat)
    play_item_cmd,               // 播放指定曲目
    get_current_metadata_cmd,    // 获取当前歌曲元数据
    get_playback_state_cmd,      // 获取播放状态
    get_now_playing_list_cmd,    // 获取正在播放列表
    get_folder_list_cmd,         // 获取文件夹列表(Browsing)
    get_player_list_cmd,         // 获取播放器列表
    change_folder_path_cmd,      // 切换文件夹路径
    set_browsed_player_cmd,      // 设置浏览的播放器
    set_addressed_player_cmd,    // 设置目标播放器
    set_volume_rsp,              // 响应 SetAbsoluteVolume
    volume_change_notification_rsp, // 音量变化通知响应
    cleanup_ctrl,
};
```

**完整调用链**:
```
App: 车机点击播放/暂停/上一首
→ BluetoothAvrcpController.sendPassThroughCmd(keyCode, keyState)
→ btif_rc.cc: send_passthrough_cmd [L2200+]
  → CHECK_RC_CONNECTED 验证连接状态
  → AVRC_PassThroughCmd → AVRC_PDU_PASS_THROUGH
  → BTA_AvRemoteCmd(rc_handle, p_msg)
→ AVCTP 信令通道 (L2CAP PSM=0x0017)
→ 手机收到 → 执行操作 → 返回响应
→ 回调: bt_rc_ctrl_callbacks.passthrough_rsp_cb
  → JNI → Java: onPassthroughRsp
```

**PASSTHROUGH vs KEY_EVENT**: PASSTHROUGH用于基础控制(Play/Pause)，KEY_EVENT用于媒体按键

### 三、AVRCP 元数据

**歌曲信息获取**:
```
车机端调用 getPlaybackState() / getMetadata()
→ btif_rc.cc: get_playback_state_cmd / get_current_metadata_cmd
→ AVRC: AVRC_PDU_GET_PLAY_STATUS / AVRC_PDU_GET_ELEMENT_ATTR
→ 手机响应 → parse_play_status_rsp / parse_metadata_rsp
→ 回调 Java: onPlayStatusChanged / onTrackChanged
```

**元数据属性ID** (bt_rc.h L50-L58):
| ID | 常量 | 含义 |
|----|------|------|
| 0x01 | BTRC_MEDIA_ATTR_ID_TITLE | 歌曲名 |
| 0x02 | BTRC_MEDIA_ATTR_ID_ARTIST | 艺术家 |
| 0x03 | BTRC_MEDIA_ATTR_ID_ALBUM | 专辑名 |
| 0x04 | BTRC_MEDIA_ATTR_ID_TRACK_NUM | 曲目号 |
| 0x05 | BTRC_MEDIA_ATTR_ID_NUM_TRACKS | 总曲目数 |
| 0x06 | BTRC_MEDIA_ATTR_ID_GENRE | 风格 |
| 0x07 | BTRC_MEDIA_ATTR_ID_PLAYING_TIME | 时长(ms) |
| 0x08 | BTRC_MEDIA_ATTR_ID_COVER_ARTWORK_HANDLE | 封面资源句柄 |

**元数据变化通知**: 手机播放歌曲变化 → AVRC_PDU_REGISTER_NOTIFICATION(AVRC_EVT_TRACK_CHANGE) → btif_rc.cc 回调 → 车机更新显示

### 四、AVRCP 浏览 (Browsing, 1.4+)

Browsing 通道(L2CAP PSM=0x001B)，独立于Control通道(PSM=0x0017):
- get_folder_list_cmd → 获取文件夹列表(艺术家/专辑/曲目)
- change_folder_path_cmd → 进入子文件夹
- get_now_playing_list_cmd → 获取播放列表
- get_player_list_cmd → 获取可用播放器列表

### 五、Absolute Volume (车载关键)

**工作原理**:
```
1. 车机作为TG端注册volume change notification
2. 手机发送 AVRC_PDU_SET_ABSOLUTE_VOLUME → 0-127(对应0%-100%)
3. btif_rc.cc: set_volume_rsp [L3124]
   → AVRC_BldResponse → avrc_rsp.volume.volume = abs_vol
   → BTA_AvVendorRsp(label, AVRC_RSP_ACCEPT)
4. 车机调整系统音量 → volume_change_notification_rsp同步回手机
   → avrc_rsp.reg_notif.pdu = AVRC_PDU_REGISTER_NOTIFICATION
   → avrc_rsp.reg_notif.event_id = AVRC_EVT_VOLUME_CHANGE
   → AVRC_BldResponse → 通知手机音量已变化
```

**车机音量与手机同步**:
- 车机音量 = MAX_VOLUME(128)级别
- 手机音量 = 0-127
- 双向同步: SetAbsoluteVolume→车机调整+车机音量变化→通知手机

### 六、封面艺术 (Cover Art, AVRCP 1.5/1.6)

```
获取流程:
1. GetElementAttr → get BTRC_MEDIA_ATTR_ID_COVER_ARTWORK_HANDLE
2. Cover Art Client: BIP(OBEX over L2CAP) 或 BLE
3. 通过 Image Handle 获取图片数据
```

### 七、新旧实现对比

| 对比项 | btif_rc.cc (旧) | avrcp_service.cc (新, 13+) |
|--------|----------------|---------------------------|
| 架构 | 扁平函数+C风格结构体 | C++类+service模式 |
| 线程 | 使用btif_transfer_context | 独立service线程 |
| 状态管理 | CHECK_RC_CONNECTED宏 | 对象生命周期管理 |
| 扩展性 | 修改需改多处 | 模块化，易扩展 |
| 迁移 | 原有代码 | 通过Feature Flag逐步启用 |

### 八、常见问题

- 歌曲信息不更新: 检查 AVRC_EVT_TRACK_CHANGE 注册→AVRC_PDU_GET_ELEMENT_ATTR→parse_metadata_rsp
- 控制命令无响应: 检查AVCT通道连接状态→BTA_AvRemoteCmd返回值→AVRC_PassThroughCmd
- 音量不同步: set_volume_rsp是否发送成功→volume_change_notification_rsp是否注册→手机是否支持Absolute Volume