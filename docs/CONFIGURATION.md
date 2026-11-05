# 配置说明

## 占位符

| 占位符 | 含义 |
|---|---|
| `1000000000` | 机器人 QQ |
| `1000000001` | 主人 QQ |
| `1000000002` | 群号 |
| `**群` | 群名占位符 |

主要位置：

```text
runtime/AstrBot-4.29.3/data/plugins/dafeiyu_group/main.py   GROUP / GROUP_NAME
runtime/AstrBot-4.29.3/data/plugins/dafeiyu_guard/main.py  ALLOWED_GROUPS
scripts/start.ps1                                          机器人 QQ（'1000000000'）
scripts/status.pyw                                         状态中心显示
```

## API

文件：

```text
runtime/AstrBot-4.29.3/data/cmd_config.json
```

需要修改：

```json
"provider_sources": [
  {
    "id": "deepseek",
    "key": ["sk-你的Key"],
    "enable": true
  }
]
```

以及：

- `provider[0].model`
- `provider[0].enable`
- `admins_id`

## 后台

默认临时账号：

```text
用户名：admin
密码：JingJing@2026
```

首次登录 `http://127.0.0.1:6185` 后立即修改。

## OneBot

AstrBot：

```json
"platform": [
  {
    "id": "dafeiyu-qq",
    "type": "aiocqhttp",
    "ws_reverse_port": 6199,
    "ws_reverse_token": "你的token"
  }
]
```

NapCat WebUI：

```text
http://127.0.0.1:6099
```

两边 token 必须一致。

## 私聊额度

```text
runtime/AstrBot-4.29.3/data/dafeiyu_quota_config.json
```

```json
{"daily_limit": 75, "grace_minutes": 0}
```

按实际发出的文字、图片、语音、音乐等回复计数。

## 单群

```python
# runtime/AstrBot-4.29.3/data/plugins/dafeiyu_group/main.py
GROUP = '1000000002'
GROUP_NAME = '**群'
GROUP_HOURLY = 30
GROUP_DAILY = 200
```

群白名单：

```python
# runtime/AstrBot-4.29.3/data/plugins/dafeiyu_guard/main.py
ALLOWED_GROUPS = {'1000000002'}
```

只支持一个群，不响应其他群。

## 语音

```text
runtime/AstrBot-4.29.3/data/dafeiyu_voice.json
```

依赖 Edge TTS 和 `runtime/bin/ffmpeg.exe`。

## 表情包

- 内置：`runtime/AstrBot-4.29.3/data/stickers`
- 自动收集：`runtime/AstrBot-4.29.3/data/collected_stickers`
- 手动：`runtime/AstrBot-4.29.3/data/collected_stickers/大肥鱼表情包`

## 音乐

- 后端：`backend/qqmusic`
- 曲库：`data/music_library`
- 状态中心登录 QQ 音乐

## 备份

```powershell
D:\JingJing\runtime\AstrBot-4.29.3\.venv\Scripts\python.exe D:\JingJing\scripts\backup.py
```

输出：`runtime/backups`，保留最近 8 份。

---

维护与整理：**YunShan You**
