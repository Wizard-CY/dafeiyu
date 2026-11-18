# 隐私说明

大肥鱼是自托管的：数据在你的电脑上，不经过维护者的服务器。这个项目没有遥测，也不会把聊天记录上传到作者这边。

但“自托管”不等于“没有数据”。下面是你运行时会产生的东西，以及它们会去哪。

## 本机存了什么

| 数据 | 位置 | 说明 |
|---|---|---|
| 私聊 / 群聊记录 | `runtime/AstrBot-4.29.3/data/data_v4.db` | AstrBot 的会话库 |
| 好友记忆、用户画像 | `data/memory/`、`data/profiles/` | 每天 22:00 提炼，下线前也会提炼一次 |
| 群聊记忆 | `data/dafeiyu_group_memory.db` | 每个群独立，和私聊隔离 |
| 额度、群设置、好友列表 | `data/dafeiyu_*.json` | 运行状态 |
| 删掉的好友的聊天记录 | `data/friend_archive/` | 「好友清理」时封存 |
| 收集的表情包、语音缓存 | `data/collected_stickers/`、`data/voice_cache/` | 会自动清理/去重 |
| 空间动态图库 | `data/diary_library/` | 发动态时选图 |
| 曲库 | `data/music_library/` | 点歌下载的音频 |
| QQ 音乐登录 cookie | `backend/qqmusic/cookie.json` | 只在本机；不进备份 |
| 运行日志、破甲日志 | `runtime/logs/`、`startup.log`、`data/dafeiyu_armor_log.jsonl` | 排障用 |
| 备份 | `runtime/backups/*.zip` | 保留最近 8 份，里面有聊天记录 |

## 会发给谁

- **模型服务商**：你填的 DeepSeek 或 OpenAI 兼容接口会收到当前对话、人设和必要的上下文。它的隐私政策由服务商决定。
- **腾讯 / NapCat**：QQ 消息本身经过腾讯的服务器；NapCat 在本机接管 QQ 客户端。
- **Edge TTS**：发语音时，要朗读的文本会发给微软的语音服务。
- **QQ 音乐 / B 站 / 搜索服务**：点歌、查资料时，相关关键词会发给对应的服务。
- **QQ 空间**：发动态和回评论走腾讯的接口。

除此之外，没有别的出站请求。

## 默认会把主人 QQ 给出去

`assets/persona.md` 第 31 行：私聊里对方明确索要主人的联系方式时，她会先问一句，对方说要就发。这是默认行为。

不想这样的话，把第 31 行删掉，或者在 `data/dafeiyu_character.md` 里改掉。改完下次请求生效。

## 保留和删除

- 备份保留最近 8 份，旧的自动删。
- 聊天记录、记忆、归档没有自动过期，除非你自己删。
- 想彻底清掉，先停掉大肥鱼，再删这些：

```text
data/data_v4.db
data/dafeiyu_group_memory.db
data/memory/
data/profiles/
data/friend_archive/
data/collected_stickers/
data/voice_cache/
data/diary_library/
data/dafeiyu_friends.json
data/dafeiyu_quota.json
data/dafeiyu_private_outbox.json
data/dafeiyu_group_memory*
data/dafeiyu_group_counts.json
data/dafeiyu_online_state.json
data/dafeiyu_watchdog.json
runtime/backups/
runtime/logs/
```

删之前确认没有要留的聊天记录。这些文件删了不能恢复。

## 群聊里的人

如果你把机器人拉进群，群消息会被它看到，并可能写进群记忆。你有责任告诉群里的人，或者别在有隐私预期的群里用。

## 备份

`runtime/backups/*.zip` 里有聊天记录和记忆，别传到网盘、别发到群里。QQ 音乐 cookie 不在备份里。
