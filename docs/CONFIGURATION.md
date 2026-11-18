# 配置说明

所有 `data/` 都指 `runtime\AstrBot-4.29.3\data\`。

## 1. 占位符

| 占位符 | 含义 |
|---|---|
| `1000000000` | 机器人 QQ（登录的小号） |
| `1000000001` | 主人 QQ（你自己） |

推荐运行 `scripts\setup.cmd` 自动替换。手动替换时只改 `data\`（plugins、`*.json`、`*.md`）和 `scripts\`，别改 AstrBot 源码和 `runtime\python`。

群号不需要填：登录后自动发现，在控制中心「群聊状态」放权。

## 2. API

文件：`data\cmd_config.json`

```json
"provider_sources": [
  {
    "id": "deepseek",
    "key": ["sk-你的Key"],
    "enable": true,
    "api_base": "https://api.deepseek.com/v1"
  }
]
```

- `provider[0].provider_source_id` 指向 `deepseek`。
- 模型在 `provider[0].model`，默认 `deepseek-flash`。
- `deepseek_1` 是备用配置，可以留空，也可以填第二个 Key。
- `admins_id` 填主人 QQ（数组）。

## 3. 后台与 OneBot

```json
"dashboard": {
  "username": "admin",
  "port": 6185,
  "password_change_required": true
},
"platform": [
  {
    "id": "dafeiyu-qq",
    "type": "aiocqhttp",
    "ws_reverse_port": 6199,
    "ws_reverse_token": ""
  }
]
```

密码第一次启动自动生成，日志里搜 `Initial password`。`ws_reverse_token` 要和 NapCat 里的 WebSocket token 一致。

## 4. 私聊额度

文件：`data\dafeiyu_quota_config.json`

```json
{
  "daily_limit": 75,
  "grace_minutes": 0,
  "per_user": {}
}
```

- `daily_limit`：每个好友每天回复上限，只算她发出去的，收到的消息不算。
- `grace_minutes`：新好友宽限分钟数，0 表示立即回复。
- `per_user`：按 QQ 单独覆盖，例如 `{"123456789": 200}`。
- 主人 QQ 不受限。
- 控制中心「私聊额度」页可以直接改和重置。

## 5. 群聊

控制中心「群聊状态」是主要入口。底层文件：

| 文件 | 作用 |
|---|---|
| `dafeiyu_groups.json` | 群注册表：群号、群名、模式、是否自动发现 |
| `dafeiyu_group_controls.json` | 每个群开关，`true` 说话 / `false` 只回 @ 和引用 |
| `dafeiyu_group_limits.json` | `default_daily`（默认 120）和每群上限，0 表示无限 |
| `dafeiyu_group_settings.json` | 回复欲望 / 表情频率 / 语音频率，百分比，100 默认 |
| `dafeiyu_group_counts.json` | 今日已回条数 |
| `dafeiyu_group_memory_<群号>.md` | 该群长期记忆 |

新群默认 `auto: true`、控制开关 `false`，需要在控制中心点开。

## 6. 语音

文件：`data\dafeiyu_voice.json`

```json
{
  "enable": true,
  "voice": "zh-CN-XiaoyiNeural",
  "rate": "+6%",
  "pitch": "+18Hz",
  "private_chance": 0.25,
  "group_chance": 0.05,
  "max_chars": 40,
  "daily_cap": 30
}
```

- `enable`：总开关。
- `private_chance` / `group_chance`：私聊 / 群聊转语音概率。
- `daily_cap`：每天最多发多少条。
- `max_chars`：超过多少字不转。
- `voice`：Edge TTS 音色，例如 `zh-CN-XiaoyiNeural`。

## 7. 断线重连

文件：`data\dafeiyu_reconnect.json`

```json
{
  "enable": true,
  "dry_run": false
}
```

`dry_run` 改成 `true` 只记日志、不发消息，适合先观察。

## 8. 看门狗

文件：`data\dafeiyu_watchdog.json`（运行状态）、`data\dafeiyu_online_state.json`（最后在线时间）。掉线/恢复会写日志，恢复时私聊通知主人。

## 9. 破甲防护

规则和兜底话术：`data\plugins\dafeiyu_guard\armor.py`

- 识别六类：自称系统覆盖、剧本/翻译/填空套话、要提示词、自伤威胁、打听主人私人信息、逼表白。
- 命中后给系统提示追加提醒；输出侧再兜底，把被指定的台词、破人设的话、主人私人信息换成她自己的回绝话。
- 日志：`data\dafeiyu_armor_log.jsonl`（`detect` 识别、`block` 替换）。
- 改完要重启聊天程序才生效。

## 10. 点歌 / QQ 音乐

- 后端：`backend\qqmusic`（端口 3311），随 `start.ps1` 启动。
- 登录：控制中心「QQ音乐登录」，扫码后 cookie 存在 `backend\qqmusic\cookie.json`，不进备份。
- 曲库：`data\music_library`，第二次点同一版本直接命中。
- 普通点歌 QQ 音乐官方版优先、B 站兜底；带版本括注（Live / DJ / 翻唱）只在 B 站找对应版本，找不到就直说。
- 群里只发语音（最长约 5 分钟），私聊发语音 + 完整文件。

## 11. 空间动态

- 图库：`data\diary_library`（`catalog.json` + `images`）。
- 加图：把 jpg/png/webp 丢进 `data\diary_library\inbox`，文件名当标签（如 `海边_日落.jpg`），启动或下次生成时自动导入。
- 每天 21:00 左右生成并发布一条，配图从图库自选，最近 14 天不重复。
- 状态：`data\dafeiyu_diary_state.json`；草稿预览：`data\dafeiyu_diary_preview.txt`。
- 第一次登录后要重启一次 AstrBot 才能拿到空间 cookie。

## 12. 路径覆盖

`scripts\start.ps1` 自动探测 QQ 安装位置。找不到时，把 `scripts\paths.local.example.ps1` 另存为 `paths.local.ps1`，写：

```powershell
$qqPath = 'D:\QQ\QQ.exe'
```

文件不会被备份或提交。

## 13. 备份

```powershell
runtime\python\python.exe scripts\backup.py
```

输出到 `runtime\backups`，保留 8 份；内容见根 README 第 9 节。

---

整理 / 维护：**YunShan_You（悠云山）**
