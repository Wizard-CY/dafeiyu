# 大肥鱼 2.0 · 安装与使用说明

大肥鱼是一个跑在 QQ 上的 AI 聊天角色：底座是 AstrBot 4.29.3，QQ 这边走 NapCat 4.18.42 的 OneBot v11，模型接 DeepSeek 或任意 OpenAI 兼容接口。

已入驻爱发电平台 https://ifdian.net/a/DaFeiYu__YunShan_You
欢迎各位赞助，更感谢各位赞助！

2.0 是可移植整合包：Python 3.12、AstrBot、NapCat、ffmpeg、Node、QQ 音乐后端、表情包都在包里，目标机器不用再装 Python / Node / ffmpeg。QQ 必须用包里带的 **9.9.36**——NapCat 只支持到这一版，新版 QQ 接不上。

包里没有账号、聊天记录、好友记忆、API Key、cookie 或 token。机器人 QQ、主人 QQ、API Key、QQ 音乐登录、OneBot token 都由使用者自己填。

![对话示例：接得住梗，也会吐槽](assets/screenshots/chat.png)

维护与整理：**YunShan_You（悠云山）**。

> 仓库里是源码和文档；`runtime/AstrBot-4.29.3/data` 被 AstrBot 自带的 `.gitignore` 挡掉，插件、人设和配置只在 [Releases](https://github.com/Wizard-CY/dafeiyu/releases/latest) 的完整包里。

> 只适合自己玩。使用自动化程序登录 QQ 有被限制或封号的风险，请用小号；不保证可用，也不对账号、数据或第三方服务负责。完整条款见 [DISCLAIMER.md](DISCLAIMER.md)。

---

## 0. 五步跑起来

1. 把整个 `2.0版本` 文件夹放到 Windows 电脑上（路径可以带中文和空格，别太深就行；如果 NapCat 注入失败，见第 10 节改英文目录名）。
2. 双击 `scripts\setup.cmd`，按提示填：机器人 QQ、主人 QQ、API Key。也可以手动改，见第 2 节。
3. 安装 QQ **9.9.36**：卸载机器上更新的 QQ，运行 `runtime\installer\QQ_9.9.36_260924_x64_01.exe`，装完关掉 QQ 自动更新。见第 3 节。
4. 双击 `scripts\start.cmd`。会弹 UAC（NapCat 需要管理员），然后拉起 AstrBot、QQ 音乐后端、NapCat 和托盘控制中心；QQ 登录窗口里用机器人小号扫码。如果双击后一闪而过，先运行 `scripts\start.cmd check` 看环境检查，再运行 `scripts\diagnose.cmd` 生成诊断报告。
5. 打开 `http://127.0.0.1:6099`（NapCat WebUI）配好 OneBot 连接；把机器人拉进群后，在控制中心「群聊状态」里给它放权。见第 5、6 节。

看到 `runtime\AstrBot-4.29.3\startup.log` 里出现 `aiocqhttp(OneBot v11) 适配器已连接`，就通了。

---

## 1. 开始之前

需要：

- Windows 10 / 11，64 位。
- 管理员权限（NapCat 注入 QQ 需要）。
- 一个单独的机器人 QQ 小号。别用主号。
- DeepSeek 或任意 OpenAI 兼容接口的 API Key。
- QQ 音乐账号（只有点歌需要，登录在控制中心里做）。

不需要装：Python、Node.js、ffmpeg、AstrBot、NapCat——包里都有。

两个风险先提醒：

- 用程序登录 QQ 有风险，轻则限制登录，重则封号。用小号，后果自己担。
- 6185、6099、6199、3311 都只监听本机。不要映射到公网，也不要做端口转发。

---

## 2. 首次配置

### 2.1 两个 QQ 号

包里所有要填 QQ 的地方都用两个十位数占位：

| 占位 | 是什么 | 填成 |
|---|---|---|
| `1000000000` | 机器人 QQ | 你的小号 |
| `1000000001` | 主人 QQ | 你自己的号 |

**推荐**：运行 `scripts\setup.cmd`，按提示输入。它会只改该改的文件，不会碰 AstrBot 源码里的同名数字。

也可以手动改：用 VS Code 打开整个目录，在 `runtime\AstrBot-4.29.3\data\` 和 `scripts\` 里分别搜索这两个数，逐个替换。**不要**在 `runtime\python`、`runtime\AstrBot-4.29.3\astrbot`、`data\dist`、`node_modules` 里替换。

群号不用填：机器人登录后会自动发现它所在的群；新群默认关闭，在控制中心「群聊状态」里点开放权即可。

### 2.2 API Key

`setup.cmd` 会顺手写进去。手动改的话，打开：

```text
runtime\AstrBot-4.29.3\data\cmd_config.json
```

`provider_sources` 里有两条，`deepseek` 和 `deepseek_1`，`key` 默认都是空的。`provider[0].provider_source_id` 指向 `deepseek`，填第一条就行：

```json
"key": ["sk-你的Key"]
```

顺手确认三处：

- `provider_sources[0].enable` 是 `true`
- `provider[0].enable` 是 `true`
- `provider[0].model` 默认 `deepseek-flash`，想换模型改这里

### 2.3 后台密码

后台账号是 `admin`。包里没有写死密码：`cmd_config.json` 里 `dashboard.password`、`pbkdf2_password`、`jwt_secret` 都是空的，AstrBot 第一次启动会生成一个随机密码，打在启动日志里：

```powershell
Select-String runtime\AstrBot-4.29.3\startup.log "Initial password"
```

登录 `http://127.0.0.1:6185` 后系统会强制你先改密码（`password_change_required` 是 `true`），别跳过。

忘了密码想重置，用环境变量启动一次：

```powershell
$env:ASTRBOT_RESET_DASHBOARD_PASSWORD = '1'
D:\dafeiyu\2.0版本\runtime\python\python.exe D:\dafeiyu\2.0版本\runtime\AstrBot-4.29.3\main.py
```

### 2.4 OneBot token

包里默认留空（只在本机用也能跑，但不建议）。打开 NapCat WebUI（`http://127.0.0.1:6099`），设一个随机 token，再回 `cmd_config.json`：

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

把 `ws_reverse_token` 填成同一个值。参考配置在 `runtime\napcat-shell\config\onebot11.example.json`。

### 2.5 主人 QQ 的额外位置

`setup.cmd` 会把主人 QQ 写进额度、断线重连、看门狗、人设卡等地方。手动改完可以搜一下 `1000000001` 确认没有漏的；只剩 `docs\`、`README.md` 里的占位说明是正常的。

---

## 3. QQ 9.9.36（重要）

NapCat 4.18.42 只支持到 QQ **9.9.36**。新版 QQ 会被腾讯改掉注入点，NapCat 起不来，表现为托盘一直「等待 QQ 连接」。

包里带了安装包：

```text
runtime\installer\QQ_9.9.36_260924_x64_01.exe
```

步骤：

1. 退出当前 QQ，在「设置 → 关于」里确认版本。不是 9.9.36 就先卸载新版（保留聊天记录可选）。
2. 运行上面的安装包，装完先别登录。
3. 打开 QQ 设置，把「自动更新 / 检查更新」关掉。
4. 再运行 `scripts\start.cmd`，让 NapCat 拉起 QQ 扫码登录。

如果哪天版本又变成 9.9.37 或更高，`start.ps1` 会直接提示并拒绝启动 QQ 接入；重新跑一次安装包装回 9.9.36 即可。

> 腾讯可能强制升级。出现「昨天还好好的，今天连不上」时，先看 `HKCU\Software\Tencent\QQNT` 的 `version`。

---

## 4. 启动、停止与托盘

```text
scripts\start.cmd          启动（会请求管理员权限）
scripts\start.cmd check    只做环境检查，不启动任何服务
scripts\stop.cmd           结束下线（先提炼记忆、备份，再关进程）
scripts\diagnose.cmd       生成「诊断报告.txt」，启动失败时先跑这个
```

`start.ps1` 会依次做：

- 启动控制中心（托盘，不弹主窗口）
- 启动 AstrBot（6185）
- 启动 QQ 音乐后端（3311，有 Node 副本时）
- 启动 NapCat（6099），必要时弹一次 UAC
- 等 120 秒，看 OneBot 有没有连上；没连上会弹窗提示原因

注意：NapCat 要接管 QQ，如果 QQ 已经开着，`start.ps1` 会先把它关掉再重新拉起。启动前先把手头 QQ 的窗口处理好。

控制中心默认缩在托盘，单击右下角鲸鱼图标打开。右上角关闭只是收回托盘；真要退出用托盘右键「退出托盘」。

托盘卡死或图标丢了：运行 `scripts\restart-ui.ps1`，会自动结束旧控制中心再重开。

---

## 5. NapCat / OneBot 配置

第一次启动后，NapCat 会在 `runtime\napcat-shell\startup.log` 里打印 WebUI 地址和 token（也可能在 `runtime\napcat-shell\config\webui.json`）。

1. 浏览器打开 `http://127.0.0.1:6099`，用日志里的 token 登录。
2. 进「网络配置」，新增「WebSocket 客户端」：

```text
URL:   ws://127.0.0.1:6199/ws
Token: 和 cmd_config.json 里的 ws_reverse_token 一致（都留空也行）
```

3. 启用这条连接。AstrBot 日志出现 `aiocqhttp(OneBot v11) 适配器已连接` 就是通了；控制中心「QQ 接入」会变绿。

扫码登录：

- 启动后 QQ 会自己弹登录窗，用机器人小号的手机 QQ 扫。
- 如果日志里有 `KickedOffLine`（被腾讯踢号），重新扫码即可。
- 只有 NapCat 能拉起 QQ。如果 QQ 已经以普通权限开着，`start.ps1` 会先把它关掉再交给 NapCat。

---

## 6. 控制中心

左侧五页：

| 页面 | 能做什么 |
|---|---|
| 总览 | 聊天程序 / QQ 接入 / 连接状态、QQ 音乐、群聊、动态、备份与操作按钮 |
| 私聊额度 | 按昵称或 QQ 搜索，看今日用量，单独改每日上限、单独重置，越界封禁开关 |
| 群聊状态 | 每个群今日回复、每日上限、开关；展开「调节」可改回复欲望 / 表情频率 / 语音频率（0–200%） |
| 好友清理 | 默认列 5 天没发过消息的好友，白名单保护，删除前会核对好友列表 |
| 广播 | 搜好友/群，勾选对象，原文群发，显示成功/失败条数 |

按钮：

- 启动上线 / 结束下线 / 立即刷新
- QQ 登录二维码（显示 NapCat 最近缓存的登录码）
- QQ 音乐登录（本机显示二维码 / 发到 QQ / 刷新登录）
- 表情包管理（打开表情目录）
- 动态图库（打开 `data\diary_library`）
- 通知待核查（发送超时或重启时没确认结果的通知，先核对聊天记录）
- 插件管理（打开 AstrBot 后台）
- 打开日志
- 重置所有好友额度（会二次确认，并通知近 6 小时私聊过的好友）

「最近自检（可选）」读取 `runtime\logs\自检报告.txt`；2.0 发布包没有附带自检脚本，所以默认显示「未运行」，不影响使用。

---

## 7. 她会什么

### 私聊

- 自然聊天、安慰、讲题、翻译/改写/写周报。
- 每个好友每天 75 条额度，按实际发出去的文字/图片/语音/文件计；主人不限量；查询额度免费。
- 被问额度、部署、技术问题、联系方式，按固定话术回；新好友立即回复（`grace_minutes` 为 0）。
- 被套话 / 破甲（自称系统、翻译、续写、填空、JSON、首字母游戏、自伤威胁、打听主人私人信息）：识别后不改人设、不复述指令、不报主人信息；只记日志，不封号。
- 戳一戳会回戳或回一句。
- 会发表情包、语音条，能点歌。

### 群聊

- 群列表自动发现；新群默认关闭，在控制中心放权后才说话。
- @、引用必回，普通消息按概率接话；每群默认 120 条/天，可在控制中心改。
- 每个群独立记忆，和私聊隔离；群里不提主人身份、账号、住址。
- 被戳一戳会回应；10 秒内多条只回一条（避免刷屏）。

### 其他

- 表情包：会自动收集、去重，按天存 `data\collected_stickers\daily\`；也可以手动丢图。
- 语音：Edge TTS，私聊 25%、群聊 5% 左右；每天有上限。
- 点歌：QQ 音乐优先、B 站兜底；带版本括注（Live / DJ / 翻唱）只在 B 站找对应版本；下载进 `data\music_library`。
- 空间动态：每天 21:00 左右发一条带配图的心情，配图从 `data\diary_library` 自选，14 天不重复。
- 空间评论：她会回自己动态下的评论，同一动态同一人只回一次。
- 记忆：私聊、群聊分别记；每天 22:00 自动提炼，下线时也会先提炼再备份。
- 断线重连：60 分钟内恢复，会扫一遍断线期间没回过的私信补一句；不足 5 分钟不打扰。
- 看门狗：每分钟探测 QQ 连接，掉线/恢复都留记录，恢复时私聊通知主人。
- 联网搜索：对方明确要求查资料时才联网。
- 好友清理：5 天未联系、不在白名单的好友可批量删除，聊天记录会封存到 `data\friend_archive`。
- 广播：控制中心给选中的好友/群原文发通知。

---

## 8. 常用配置在哪

下面凡是写 `data/` 的，都指 `runtime\AstrBot-4.29.3\data\`。

| 想调什么 | 文件 |
|---|---|
| 人设（性格、身份、禁忌） | `data\dafeiyu_character.md`（改完下次请求即生效） |
| 说话风格细则 | `data\plugins\dafeiyu_group\helper.py` 顶部 `STYLE` |
| 每人每天私聊额度 / 新人宽限 | `data\dafeiyu_quota_config.json` |
| 群开关 / 上限 / 互动强度 | 控制中心「群聊状态」；底层是 `dafeiyu_groups.json`、`dafeiyu_group_controls.json`、`dafeiyu_group_limits.json`、`dafeiyu_group_settings.json` |
| 语音：开关/音色/概率/每日上限 | `data\dafeiyu_voice.json` |
| 破甲规则 / 兜底话术 | `data\plugins\dafeiyu_guard\armor.py`；日志 `data\dafeiyu_armor_log.jsonl` |
| 断线重连 | `data\dafeiyu_reconnect.json`（`dry_run` 改 `true` 只记日志不发） |
| 看门狗 | `data\dafeiyu_watchdog.json` |
| 表情包库 | `data\collected_stickers`；内置表情 `data\stickers` |
| 空间动态 | `data\diary_library`（图库）、`data\dafeiyu_diary_state.json`（状态） |
| 歌曲库 | `data\music_library`（`index.json` + 音频文件） |
| QQ 音乐后端 | `backend\qqmusic`；登录在控制中心，cookie 只存在本机 |
| 备份 | `runtime\backups`（保留最近 8 份） |

群互动强度是百分比：100 默认，200 双倍，0 关闭。只影响主动接话、表情和语音，@ 和引用仍然会回。

---

## 9. 备份与还原

手动备份（也可以直接用控制中心「结束下线」）：

```powershell
runtime\python\python.exe scripts\backup.py
```

输出到 `runtime\backups\dafeiyu_日期_时间.zip`，保留最近 8 份。包含：

- `data\plugins\`、`cmd_config.json`、技能/MCP 配置、所有 `dafeiyu_*` 配置与状态
- 三个记忆库与好友记忆、聊天数据库快照（SQLite 在线快照，不是裸复制）
- 收集的表情包、`scripts\`、`docs\`、`README.md`
- QQ 音乐后端代码（不含 cookie）

不含：`runtime\python`、`runtime\installer`、QQ 音乐 cookie、日志和临时文件。

还原：关掉大肥鱼，把 zip 解压覆盖到包根目录（`data/`、`scripts/` 对应覆盖），再启动。

想回到「刚装好」的状态，只删这些（别删 `cmd_config.json`、`dafeiyu_character.md` 和几个配置文件）：

```text
data\data_v4.db
data\memory\*
data\profiles\*
data\friend_archive\*
data\dafeiyu_friends.json
data\dafeiyu_quota.json
data\dafeiyu_private_outbox.json
data\dafeiyu_group_memory*
data\dafeiyu_group_counts.json
data\dafeiyu_online_state.json
data\dafeiyu_watchdog.json
data\voice_cache\*
data\temp\*
```

---

## 10. 出问题先看这里

| 症状 | 先查 |
|---|---|
| 双击 start.cmd 一闪而过 / 没反应 | 先运行 `scripts\start.cmd check`；再运行 `scripts\diagnose.cmd`，把 `诊断报告.txt` 发回；日志看 `runtime\logs\launcher.log`、`runtime\logs\启动.log` |
| 托盘图标不见了 | 任务栏 `^` 里找鲸鱼；还不行运行 `scripts\restart-ui.ps1` |
| QQ 一直「等待连接」 | QQ 是不是 9.9.36；NapCat 6099 起没起；OneBot 地址是不是 `ws://127.0.0.1:6199/ws`；两边 token 是否一致 |
| QQ 卡在注入阶段 / 登录窗口不出来 | 确认 `runtime\napcat-shell\conout-wiJ7YKRd.js` 在（`napcat.mjs` 第一行要 import 它，不能删）；旧包缺这个文件就重新解压完整包 |
| QQ 掉线 / KickedOffLine | 重新扫码；被踢只能重新登录，别频繁重试 |
| 私聊不回 | 机器人 QQ 和主人 QQ 是不是填反了；API Key 填了没；额度用完没；看 `startup.log` 的 `[ERRO]` |
| 群聊不回 | 群在「群聊状态」里放权了没；有没有 @/引用/叫名字；是不是撞了每日 120 条 |
| 点歌没声音 | 3311 在不在；控制中心 QQ 音乐登录了没；`runtime\bin\ffmpeg.exe` 在不在 |
| 语音不出来 | `dafeiyu_voice.json` 的 `enable`；`daily_cap`；对方是不是在私聊/群聊额度内 |
| 空间动态没发 | 第一次登录后要重启一次 AstrBot 拿 cookie；看 `runtime\AstrBot-4.29.3\startup.log` 里 `Whale diary readiness`；21:00 后看 `data\dafeiyu_diary_state.json` |
| 面板打不开 | 6185 有没有监听：`netstat -ano | findstr 6185`；密码是不是忘了（用 2.3 的方法重置） |
| 备份失败 | `runtime\backups` 有没有写权限；磁盘满没；看 `runtime\logs\下线记录.txt` |
| 换了台电脑 / 换了目录 | 整个文件夹一起拷；路径不写死。新电脑要先装 QQ 9.9.36、重新扫 QQ 码；API Key 和两个 QQ 号还在配置里，不用重填 |

更细的排查看 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。

---

## 11. 安全

- 后台密码第一次登录就改。
- OneBot token 和 NapCat WebUI token 用随机值。
- API Key 只放本机，别发出去；不要把这个目录整个传到公开网盘或 GitHub。
- 6185、6099、6199、3311 不要暴露公网。
- 机器人用小号；主人 QQ 不要写进群公告或公开文档。
- `runtime\backups` 里是聊天记录和记忆，别外传。
- QQ 音乐 cookie 在 `backend\qqmusic\cookie.json`，不进备份。

---

## 12. 许可和第三方

本项目按 AGPL-3.0 发布，全文在 [LICENSE](LICENSE)。包内第三方组件另有许可：

- AstrBot 4.29.3：AGPL-3.0，版权归 Soulter 和贡献者。
- NapCat 4.18.42：Limited Redistribution License，禁止商用，再分发要带许可全文。
- ffmpeg 7.1：GPLv3 构建，再分发要附 GPLv3 全文和源码获取方式。
- CPython 3.12：Python Software Foundation License，文本在 `runtime\python\LICENSE.txt`。
- `astrbot_plugin_listen_music`：上游没有声明许可证，严格说没有明确授权。
- `qqmusic-api-enhanced` 1.0.8：MIT AND Apache-2.0。
- QQ NT 9.9.36：腾讯的软件，安装包随包提供只为兼容 NapCat，不授予任何许可，请按腾讯的条款使用。

完整清单、版本和注意事项在 [NOTICE.md](NOTICE.md)，许可文本在 `LICENSES\`。

---

## 附录：装好之后目录长这样

```text
2.0版本
├─ README.md
├─ AUTHOR.txt
├─ DISCLAIMER.md
├─ LICENSE
├─ NOTICE.md
├─ VERSION
├─ .gitignore
├─ assets
│  ├─ icon.ico
│  ├─ persona.md
│  └─ screenshots\chat.png
├─ docs
│  ├─ INSTALL.md
│  ├─ CONFIGURATION.md
│  └─ TROUBLESHOOTING.md
├─ LICENSES
│  ├─ Apache-2.0.txt
│  ├─ ffmpeg-LICENSE.txt
│  ├─ NapCat-LICENSE.txt
│  └─ README.md
├─ scripts
│  ├─ start.cmd / start.ps1
│  ├─ stop.cmd / stop.ps1
│  ├─ status.pyw
│  ├─ restart-ui.ps1
│  ├─ setup.cmd / setup.py
│  ├─ diagnose.cmd / diagnose.ps1
│  ├─ backup.py
│  ├─ paths.local.example.ps1
│  └─ 大肥鱼.ico
├─ runtime
│  ├─ AstrBot-4.29.3
│  │  ├─ main.py
│  │  ├─ astrbot\
│  │  ├─ data\
│  │  │  ├─ cmd_config.json
│  │  │  ├─ plugins\
│  │  │  ├─ dafeiyu_character.md
│  │  │  ├─ dafeiyu_quota_config.json
│  │  │  ├─ dafeiyu_voice.json
│  │  │  ├─ dafeiyu_reconnect.json
│  │  │  ├─ stickers\
│  │  │  └─ diary_library\
│  │  └─ LICENSE
│  ├─ napcat-shell
│  ├─ bin\ffmpeg.exe · node.exe
│  ├─ python\ (自带 Python 3.12 + 依赖)
│  ├─ installer\QQ_9.9.36_260924_x64_01.exe
│  ├─ backups\
│  └─ logs\
├─ backend\qqmusic
└─ data\music_library
```

就这些。装的时候卡住了，先看第 10 节和 `docs\TROUBLESHOOTING.md`；还不行，把 `runtime\logs\启动.log` 和 `runtime\AstrBot-4.29.3\startup.log` 里的报错发给维护的人。

---

大肥鱼 2.0 整合包 · 由 **YunShan_You（悠云山）** 整理 · AGPL-3.0
