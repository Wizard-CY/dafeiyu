# 大肥鱼 · 安装与使用说明

大肥鱼是一个运行在 QQ 上的 AI 聊天角色，基于 AstrBot、NapCat（OneBot v11）和 DeepSeek 兼容接口。

这个安装包提供完整运行框架，但不包含任何现成账号、聊天记录、好友记忆或登录凭据。QQ、群聊、API Key、后台密码和 OneBot token 都需要安装者自己填写。

维护与整理：**YunShan You**

> 本项目仅供个人学习、研究和自用，不保证可用性，也不对账号、数据或第三方服务承担责任。完整条款见 [DISCLAIMER.md](DISCLAIMER.md)。

> 开始前请先读第 4 节。未替换占位符、未填 API Key 时启动，机器人不会正常聊天。

## 文档索引

- [安装指南](docs/INSTALL.md)
- [配置说明](docs/CONFIGURATION.md)
- [常见问题](docs/TROUBLESHOOTING.md)
- [免责声明](DISCLAIMER.md)

## 完整运行包

本仓库只放源码、配置、脚本和文档。包含 `.venv`、NapCat、ffmpeg、内置表情等大文件的完整运行包，请在 Release 下载：

`https://github.com/Wizard-CY/dafeiyu/releases/tag/v1.0.0`

---

## 1. 功能

### 私聊

- 自然聊天、情绪回应、日常吐槽、简单问答
- 每位好友每天 75 条回复额度，按实际发出的回复计数
- 固定口径：加群、新功能、投喂、主人身份、技术问题、token、联系方式
- 被夸可爱/漂亮时短暂傲娇，最多两个来回
- 私聊戳一戳会戳回去或回一句
- 表情包、语音条、点歌

### 群聊

只支持一个群。

- 群名占位符：`**群`
- 群号占位符：`1000000002`
- 只在被 @、被引用回复、或消息里叫「大肥鱼 / 哦鲸鲸 / 鲸鲸」时回应
- 每日 200 条、每小时 30 条上限
- 群记忆独立于私聊
- 群内不报联系方式、不聊主人隐私、不接技术细节
- 群戳一戳会戳回去或回一句

### 其他

- 人设：哦鲸鲸，DeepSeek 拟人蓝鲸娘
- 语音：Edge TTS + ffmpeg
- 表情包：自动收集、内置表情、手动目录
- 点歌：本地曲库 → QQ 音乐后端 → B 站兜底
- 空间动态：每天 21:00 生成并发布
- 记忆：22:00 提炼私聊好友记忆和群记忆
- 备份：手动/定时 zip 备份
- 状态中心：托盘运行，点图标打开
- 断线重连、看门狗、联网搜索、听语音

---

## 2. 目录结构

```text
D:\JingJing
├─ README.md
├─ DISCLAIMER.md
├─ .gitignore
├─ docs
│  ├─ INSTALL.md
│  ├─ CONFIGURATION.md
│  └─ TROUBLESHOOTING.md
├─ assets
│  ├─ icon.ico
│  └─ persona.md
├─ scripts
│  ├─ start.ps1
│  ├─ start.cmd
│  ├─ stop.ps1
│  ├─ status.pyw
│  └─ backup.py
├─ runtime
│  ├─ AstrBot-4.29.3
│  │  ├─ main.py
│  │  ├─ .venv
│  │  ├─ requirements.txt
│  │  └─ data
│  │     ├─ cmd_config.json
│  │     ├─ plugins
│  │     ├─ dafeiyu_character.md
│  │     ├─ dafeiyu_quota_config.json
│  │     ├─ dafeiyu_voice.json
│  │     ├─ dafeiyu_reconnect.json
│  │     ├─ stickers
│  │     └─ collected_stickers
│  ├─ napcat-shell
│  └─ bin
├─ backend
│  └─ qqmusic
└─ data
   └─ music_library
```

### 群设置位置

- 群号：`runtime/AstrBot-4.29.3/data/plugins/dafeiyu_group/main.py` 的 `GROUP`
- 群名占位符：同文件 `GROUP_NAME`
- 群聊权限：`runtime/AstrBot-4.29.3/data/plugins/dafeiyu_guard/main.py` 的 `ALLOWED_GROUPS`
- 群限流：`dafeiyu_group/main.py` 的 `GROUP_HOURLY` / `GROUP_DAILY`

如果只做私聊，可以把 `ALLOWED_GROUPS` 留成占位，不把机器人拉进群。

---

## 3. 运行环境

### 必需

- Windows 10 / 11 64 位
- Python 3.11（3.10+）
- QQ NT 客户端
- 一个单独的机器人 QQ 小号
- DeepSeek 或 OpenAI 兼容 API Key
- Node.js 18+（QQ 音乐后端）
- 管理员权限（NapCat 挂载 QQ）

### 自带

- AstrBot 4.29.3 和虚拟环境
- NapCat / OneBot 框架
- ffmpeg（`runtime/bin`）
- 内置表情和表情收集框架

### 端口

| 服务 | 默认端口 |
|---|---:|
| AstrBot 后台 | 6185 |
| NapCat WebUI | 6099 |
| OneBot WebSocket | 6199 |
| QQ 音乐后端 | 3311 |

只监听本机，不要把 6185 / 6099 映射到公网。

---

## 4. 首次配置

### 4.1 替换三个占位符

| 占位符 | 含义 | 建议 |
|---|---|---|
| `1000000000` | 机器人 QQ 号 | 单独小号 |
| `1000000001` | 主人 QQ 号 | 你自己的号 |
| `1000000002` | 群号 | 要接入的群 |

用 VS Code 打开整个目录，全局替换：

```text
1000000000  →  机器人 QQ
1000000001  →  主人 QQ
1000000002  →  群号
```

不要替换 `README.md` 里的说明文字。

运行时主要会命中：

```text
scripts/start.ps1
scripts/status.pyw
data/plugins/dafeiyu_group/main.py
data/plugins/dafeiyu_guard/main.py
data/plugins/dafeiyu_memory/main.py
data/plugins/dafeiyu_style/main.py
data/plugins/dafeiyu_quota/main.py
data/plugins/dafeiyu_diary/main.py
data/plugins/dafeiyu_voice/main.py
data/plugins/dafeiyu_reconnect/main.py
data/plugins/dafeiyu_watchdog/main.py
```

群名在 `dafeiyu_group/main.py`：

```python
GROUP_NAME = '**群'
```

把 `**群` 改成你的群名称即可，只影响提示和状态显示。

### 4.2 填 API Key

打开：

```text
runtime/AstrBot-4.29.3/data/cmd_config.json
```

找到 `provider_sources`：

```json
"provider_sources": [
  {
    "id": "deepseek",
    "provider": "deepseek",
    "key": [],
    "api_base": "https://api.deepseek.com/v1",
    "enable": true
  }
]
```

改成：

```json
"key": ["sk-你的APIKey"]
```

检查：

- `provider_sources[0].enable` 为 `true`
- `provider[0].enable` 为 `true`
- `provider[0].model` 是你要用的模型名

### 4.3 后台账号

安装包内置临时后台账号：

```text
用户名：admin
密码：JingJing@2026
```

打开 `http://127.0.0.1:6185` 后立刻修改。

`cmd_config.json` 中的 `admins_id` 默认为空，填上主人 QQ：

```json
"admins_id": ["1000000001"]
```

替换占位符后这里会变成真实主人 QQ。

### 4.4 OneBot token

安装包不内置固定 token。

打开 NapCat WebUI：`http://127.0.0.1:6099`，设置一个随机 token。

然后打开 `cmd_config.json`：

```json
"platform": [
  {
    "id": "dafeiyu-qq",
    "type": "aiocqhttp",
    "ws_reverse_port": 6199,
    "ws_reverse_token": ""
  }
]
```

把 `ws_reverse_token` 填成和 NapCat 一致。也可以两边留空，仅本机使用。

### 4.5 本机路径

打开 `scripts/start.ps1`，改：

```powershell
$qqPath = 'E:\QQ\QQ.exe'
$nodeExe = 'C:\...\node.exe'
$pythonw = 'C:\Users\...\Python311\pythonw.exe'
```

- `$qqPath`：QQ NT 的 QQ.exe
- `$nodeExe`：Node.js
- `$pythonw`：系统 Python 的 pythonw，用来启动托盘状态中心

---

## 5. 安装 AstrBot 环境

### 5.1 检查自带环境

```powershell
D:\JingJing\runtime\AstrBot-4.29.3\.venv\Scripts\python.exe -c "import astrbot; print('ok')"
```

显示 `ok` 即可用。

### 5.2 重建虚拟环境

如果换机器后报错：

```powershell
cd D:\JingJing\runtime\AstrBot-4.29.3
Remove-Item .venv -Recurse -Force
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

有 uv 的话：

```powershell
uv sync
```

### 5.3 插件依赖

```powershell
.\.venv\Scripts\python.exe -m pip install edge-tts aiohttp requests
```

状态中心使用系统 Python：

```powershell
C:\Users\你的用户名\AppData\Local\Programs\Python\Python311\python.exe -m pip install pystray Pillow
```

### 5.4 测试 AstrBot

```powershell
cd D:\JingJing\runtime\AstrBot-4.29.3
.\.venv\Scripts\python.exe main.py
```

能启动后先停掉，再继续配置 NapCat。

---

## 6. 安装 QQ / NapCat

### 6.1 安装 QQ NT

安装官方 QQ NT，把 `QQ.exe` 路径填到 `scripts/start.ps1` 的 `$qqPath`。

用机器人小号登录，不要把主号交给机器人。

### 6.2 启动 NapCat

管理员运行：

```powershell
D:\JingJing\scripts\start.ps1
```

它会启动：

1. AstrBot
2. QQ 音乐后端
3. NapCat（QQ 登录窗口）
4. 状态中心托盘

第一次启动按提示扫码登录机器人 QQ。

### 6.3 配置 OneBot

打开 `http://127.0.0.1:6099`，在 NapCat 的「网络配置」里设置：

```text
WebSocket 客户端
URL: ws://127.0.0.1:6199/ws
Token: 与 cmd_config.json 的 ws_reverse_token 一致
```

参考：

```text
runtime/napcat-shell/config/onebot11.example.json
```

登录后 NapCat 会自动生成账号配置，不需要手动放账号配置文件。

### 6.4 验证

AstrBot 日志出现：

```text
aiocqhttp(OneBot v11) 适配器已连接
```

状态中心「QQ 接入」变绿即可。

---

## 7. 启动、托盘和下线

### 7.1 启动

```powershell
D:\JingJing\scripts\start.ps1
```

或双击 `scripts/start.cmd`。

启动后状态中心默认缩到系统托盘，不弹大窗口。

### 7.2 打开状态中心

单击右下角鲸鱼图标。

看不到时点任务栏右下角的 `^` 展开。

关闭按钮只收回托盘；右键托盘 →「退出托盘」才是退出。

### 7.3 状态中心功能

- 启动上线 / 结束下线
- 立即刷新
- 取 QQ 登录二维码
- QQ 音乐登录
- 重置所有好友私聊额度
- 打开插件管理页面
- 打开日志
- 表情包管理

### 7.4 下线

「结束下线」会：

1. 给近 12 小时私聊过的好友发下线通知
2. 提炼记忆
3. 备份
4. 关闭 AstrBot / NapCat / QQ 音乐后端

---

## 8. 功能配置

### 8.1 人设

```text
runtime/AstrBot-4.29.3/data/dafeiyu_character.md
assets/persona.md
```

角色称主人为「主人」，不再使用其他称呼。

### 8.2 私聊额度

```text
runtime/AstrBot-4.29.3/data/dafeiyu_quota_config.json
```

默认 75 条/天，按实际发出的回复计数。

### 8.3 群聊

只有一个群：

```text
runtime/AstrBot-4.29.3/data/plugins/dafeiyu_group/main.py
```

关键设置：

```python
GROUP = '1000000002'
GROUP_NAME = '**群'
GROUP_HOURLY = 30
GROUP_DAILY = 200
```

群名占位符也在状态中心显示。若要在状态中心显示真实群名，把 `scripts/status.pyw` 里的 `**群` 一起替换。

行为：

- 只在这个群工作
- 只在 @、引用、叫名字时回复
- 群记忆只写 `dafeiyu_group_memory.md`

### 8.4 语音

```text
runtime/AstrBot-4.29.3/data/dafeiyu_voice.json
```

参数：

- `private_chance`：私聊转语音概率
- `group_chance`：群聊转语音概率
- `daily_cap`：每日语音上限
- `voice`：Edge TTS 音色

### 8.5 表情包

- 内置：`data/stickers`
- 自动收集：`data/collected_stickers`
- 手动目录：`data/collected_stickers/大肥鱼表情包`

手动目录不参与自动淘汰。

### 8.6 点歌

需要：

- Node.js 18+
- `backend/qqmusic/server.mjs`
- 状态中心登录 QQ 音乐
- 可选本地曲库 `data/music_library`

群聊发语音条；私聊发语音 + 文件。

### 8.7 空间动态

NapCat 登录机器人 QQ 后，AstrBot 通过 NapCat 的 `get_cookies` 获取 `user.qzone.qq.com` cookie。

首次登录后重启一次 AstrBot，日志出现：

```text
Whale diary readiness OK
```

即配置成功。每天 21:00 左右检查并发布。

### 8.8 记忆

- 私聊好友记忆：`data/memory`
- 群记忆：`data/dafeiyu_group_memory.md` / `.db`

每天 22:00 自动提炼。新安装是空记忆。

### 8.9 备份

```powershell
D:\JingJing\runtime\AstrBot-4.29.3\.venv\Scripts\python.exe D:\JingJing\scripts\backup.py
```

输出到 `runtime/backups`，保留最近 8 份，不包含 QQ 音乐 cookie。

---

## 9. 默认固定口径

- 加群：`我没有权限哦，去联系我的主人试试吧！`
- 新功能：`应该会的吧，你可以去联系我的主人问问呀！`
- 加饭/投喂：`可以去找我的主人`
- 主人是谁：`我只有主人`
- 主人称呼：`主人就是主人`
- 技术问题：`我只会聊天，请联系主人处理`
- token 投喂：`你真有这个心的话，那你联系我的主人吧`
- 联系方式：先问「你要我主人的QQ号吗？」，同意后才给主人 QQ
- 剩余额度：`我还能发送N次消息。`

这些规则在私聊结果护栏里直接生效；群聊只使用主人称呼规则，不主动透露主人身份。

---

## 10. 常见问题

### 状态中心没出现

1. 看托盘 `^`
2. 安装系统 Python 的 `pystray Pillow`
3. 手动运行 `pythonw D:\JingJing\scripts\status.pyw`

### QQ 没连上

1. QQ 是否登录
2. NapCat 6099 是否可访问
3. OneBot URL 是否 `ws://127.0.0.1:6199/ws`
4. 两边 token 是否一致
5. `cmd_config.json` 平台 id 是否仍为 `dafeiyu-qq`

### 私聊不回复

1. 机器人 QQ 和主人 QQ 是否填反
2. 是否在新好友宽限时间内
3. 额度是否用完
4. 状态中心连接状态

### 群聊不回复

1. 群号是否替换成真实群号
2. 机器人是否在群里
3. 是否 @、引用或叫了名字
4. `ALLOWED_GROUPS` 是否包含群号

### 点歌没声音

1. Node 后端 3311 是否运行
2. QQ 音乐是否登录
3. ffmpeg 是否存在

### 想恢复空白状态

删除以下内容后重启：

```text
data/memory/*
data/dafeiyu_group_memory*
data/dafeiyu_friends.json
data/dafeiyu_quota.json
data/dafeiyu_private_outbox.json
data/data_v4.db
```

不要删 `dafeiyu_character.md` 和三个配置文件。

---

## 11. 安全

- 后台密码首次登录必须改
- OneBot token、NapCat WebUI token 设随机值
- API Key 只放本机，不要外发
- 6185 / 6099 不要暴露公网
- 机器人 QQ 使用小号
- 不要把主人 QQ 写进群公告或公开文档
- 群聊只保留一个，避免机器人被拉进陌生群

---

## 12. 免责声明

- 本项目由 **YunShan You** 整理，仅供个人学习、研究和技术交流，不是腾讯、QQ、DeepSeek 或任何平台的官方项目。
- 使用自动化程序登录 QQ 存在账号被限制、冻结或封禁的风险，请使用单独的小号，并自行承担相关后果。
- AI 生成内容可能不准确或不完整，不构成医疗、法律、金融等专业建议；API 费用由 Key 持有人承担。
- 本项目按“现状”提供，不附带任何明示或暗示担保；因使用或无法使用本项目造成的损失，作者不承担责任。
- 第三方组件版权归各自作者所有，请遵守其许可证。

完整条款见 [DISCLAIMER.md](DISCLAIMER.md)。

## 13. 第三方组件

- AstrBot 4.29.3
- NapCat / OneBot v11
- astrbot_plugin_listen_music
- edge-tts
- ffmpeg
- QQ 音乐后端

请遵守各组件许可证。QQ 账号、QQ 音乐账号和 API Key 由安装者自行提供。
