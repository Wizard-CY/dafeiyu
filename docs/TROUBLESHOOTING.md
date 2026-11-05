# 常见问题

## 启动后没有窗口

状态中心默认在系统托盘。

1. 看任务栏右下角 `^`。
2. 单击鲸鱼图标。
3. 如果托盘不出现，安装系统 Python 依赖：

```powershell
C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\python.exe -m pip install pystray Pillow
```

4. 手动运行：

```powershell
C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\pythonw.exe D:\JingJing\scripts\status.pyw
```

## QQ 没连上

检查：

1. QQ 是否已登录机器人小号。
2. `http://127.0.0.1:6099` 能否打开。
3. NapCat 的 WebSocket 地址是否为 `ws://127.0.0.1:6199/ws`。
4. 两边 token 是否一致。
5. `cmd_config.json` 平台 id 是否仍为 `dafeiyu-qq`。

## 私聊不回复

1. 机器人 QQ 和主人 QQ 是否填反。
2. 好友额度是否用完。
3. 新好友宽限时间是否还没过（默认 0）。
4. 状态中心「聊天程序」「QQ 接入」是否正常。

## 群聊不回复

1. `GROUP` 是否替换成真实群号。
2. 机器人是否在群里。
3. 是否 @、引用或叫「大肥鱼 / 哦鲸鲸 / 鲸鲸」。
4. `ALLOWED_GROUPS` 是否包含该群号。
5. 群限流是否达到每小时 30 条或每日 200 条。

## 点歌没声音

1. `backend/qqmusic` 的 Node 服务 3311 是否运行。
2. 状态中心 QQ 音乐是否登录。
3. `runtime/bin/ffmpeg.exe` 是否存在。

## 语音不出现

1. `dafeiyu_voice.json` 的 `enable` 是否为 true。
2. 是否超过 `daily_cap`。
3. 是否命中隐私/主人/技术等不转语音规则。
4. 检查 Edge TTS 依赖：

```powershell
D:\JingJing\runtime\AstrBot-4.29.3\.venv\Scripts\python.exe -m pip install edge-tts
```

## 想恢复空白状态

删除运行时数据后重启：

```text
runtime/AstrBot-4.29.3/data/memory/*
runtime/AstrBot-4.29.3/data/dafeiyu_group_memory*
runtime/AstrBot-4.29.3/data/dafeiyu_friends.json
runtime/AstrBot-4.29.3/data/dafeiyu_quota.json
runtime/AstrBot-4.29.3/data/dafeiyu_private_outbox.json
runtime/AstrBot-4.29.3/data/data_v4.db
```

不要删除：

```text
data/cmd_config.json
data/dafeiyu_character.md
data/dafeiyu_quota_config.json
data/dafeiyu_voice.json
data/dafeiyu_reconnect.json
```

---

维护与整理：**YunShan You**
