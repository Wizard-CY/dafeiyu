# 故障排查

先记住几个日志位置：

| 日志 | 位置 |
|---|---|
| 启动 / 停止 | `runtime\logs\launcher.log`、`runtime\logs\启动.log`、`runtime\logs\下线记录.txt` |
| 控制中心异常 | `runtime\logs\control_center_error.log`、`runtime\logs\重启控制中心.log` |
| 聊天程序 | `runtime\AstrBot-4.29.3\startup.log`、`startup-error.log` |
| QQ 接入 | `runtime\napcat-shell\startup.log` |
| 破甲 | `data\dafeiyu_armor_log.jsonl` |

`data/` 指 `runtime\AstrBot-4.29.3\data\`。

---

## 双击 start.cmd 一闪而过 / 没反应

先不要反复双击。按顺序做：

1. 确认是**解压后的文件夹**，不是压缩包预览窗口里直接双击。路径可以带中文和空格，但别太深。
2. 运行环境检查（不会启动任何服务）：

```text
scripts\start.cmd check
```

它会把 Python、AstrBot、NapCat、Node、QQ 路径、QQ 版本、API Key、机器人 QQ 占位符逐项打印出来。

3. 如果检查也说不出原因，运行：

```text
scripts\diagnose.cmd
```

会生成 `诊断报告.txt`。把这个文件和 `runtime\logs\launcher.log` 一起发给维护的人。

4. 看日志最后几行：

```text
runtime\logs\launcher.log
runtime\logs\启动.log
```

5. 常见原因：
   - **QQ 不是 9.9.36**：`start.ps1` 会拒绝启动 QQ 接入；按 README 第 3 节重装。
   - **没替换机器人 QQ / 主人 QQ**：跑 `scripts\setup.cmd`。
   - **API Key 没填**：`cmd_config.json` 里 `provider_sources[0].key` 还是空的。
   - **杀软删了 `NapCatWinBootHook.dll` 或 `python.exe`**：看隔离区，恢复后加白名单。
   - **没有管理员权限**：NapCat 需要 UAC 授权；右键 `start.cmd` 用管理员运行一次。
   - **路径/QQ 安装路径里有空格**：2.0 当前这版已经修好；如果朋友手里是旧包，用新包的 `scripts` 目录覆盖过去。

> 如果提示「找不到 PowerShell」或 `start.ps1` 根本打不开，把 `scripts\diagnose.cmd` 也发不过去时，直接看 `runtime\logs\launcher.log` 里 `powershell.exe` 的报错。

## 控制中心不见了 / 打不开

1. 任务栏右下角 `^` 里找鲸鱼图标，单击。
2. 运行 `scripts\restart-ui.ps1`。
3. 还不行，用没有窗口的方式手动跑一遍，看报错：

```powershell
runtime\python\python.exe scripts\status.pyw
```

报错会写到 `runtime\logs\control_center_error.log`。

## QQ 一直连不上

按顺序查：

1. QQ 是不是 9.9.36：

```powershell
Get-ItemProperty HKCU:\Software\Tencent\QQNT -Name version
```

2. 6099 / 6199 有没有监听：

```powershell
netstat -ano | findstr "6099 6199"
```

3. NapCat WebUI 能不能打开：`http://127.0.0.1:6099`。
4. OneBot 地址是不是 `ws://127.0.0.1:6199/ws`。
5. NapCat 和 `cmd_config.json` 的 token 是否一致（都为空也可以）。
6. `cmd_config.json` 里平台 id 还是不是 `dafeiyu-qq`。
7. 看 `runtime\napcat-shell\startup.log` 有没有 `KickedOffLine`、`LoginError`。
8. 确认 NapCat 的 chunk 在：`runtime\napcat-shell\conout-wiJ7YKRd.js`。`napcat.mjs` 第一行会 `import` 它，缺了会卡在 QQ 注入阶段；这个文件不能删。旧包缺这个文件的话，用完整的 2.0版本 重新解压。

如果 6099 / 6199 都正常，但 QQ 窗口一直不出现或者注入失败，先把整个文件夹改成一个短的英文目录（例如 `D:\dafeiyu\JingJing2`）再试。NapCat 的注入 DLL 对少数中文/特殊字符路径不友好；这是路径问题，不是包坏了。

## 被腾讯踢下线 / 频繁掉线

- 日志出现 `KickedOffLine` 只能重新扫码，不要连续重试。
- 换网络、换 IP、短时间多次登录都会被踢。
- 机器人小号平时不要用手机登同一个号。

## 私聊不回

1. 机器人 QQ 和主人 QQ 是不是填反了（`scripts\setup.cmd` 再跑一次或手工查）。
2. API Key 是不是空的、余额还有没有。
3. 额度是不是用完了：控制中心「私聊额度」看这个人今天用了多少。
4. 对方是不是新好友，`grace_minutes` 被调大了。
5. `startup.log` 搜 `[ERRO]`，看模型调用有没有报错。
6. 控制中心「总览」的 QQ 连接是不是绿的。

## 群聊不回

1. 控制中心「群聊状态」里这个群开了没（新群默认关闭）。
2. 机器人在不在群里。
3. 有没有 @、引用，或者叫「大肥鱼 / 哦鲸鲸 / 鲸鲸」。
4. 是不是撞了每日 120 条或每群上限。
5. 群互动强度是不是被拉到 0 了（0 只停主动接话，@ 和引用仍会回）。

## 点歌没声音

1. `http://127.0.0.1:3311` 通不通；`runtime\logs\启动.log` 里 QQ 音乐后端起没起。
2. 控制中心点「QQ音乐登录」，扫码登录；cookie 过期就重登。
3. `runtime\bin\ffmpeg.exe` 在不在。
4. 第一次点的歌要下载，等几秒；版本括注（Live / DJ）只在 B 站找，找不到会直说。
5. 群里只发语音条；私聊才有完整文件。

## 语音不出来

1. `data\dafeiyu_voice.json` 的 `enable` 是不是 `true`。
2. 是不是超过 `daily_cap`。
3. 是不是命中不转语音的规则（隐私、主人、技术问题）。
4. 自带 Python 里已经有 `edge_tts`，如果报缺包，说明 `runtime\python` 被改坏了，重新解压。

## 空间动态没发

1. 第一次登录 QQ 后要重启一次 AstrBot 才能拿空间 cookie。
2. `startup.log` 搜 `Whale diary readiness`，看是不是 `OK`。
3. 看 `data\dafeiyu_diary_state.json` 的 `status` 和 `image_error`。
4. 21:00 才发；图库不足时会自动从公共图库补图。
5. 失败会私聊通知主人。

## 面板打不开

```powershell
netstat -ano | findstr 6185
```

- 没监听：聊天程序没起来，看 `startup.log`。
- 有监听但密码不对：用环境变量重置（见 README 2.3）。
- 浏览器缓存：换无痕窗口。

## 备份失败

1. `runtime\backups` 有没有写权限。
2. 磁盘满没满。
3. 看 `runtime\logs\下线记录.txt` 最后的「备份失败」。
4. 聊天数据库很大时备份会慢，等它跑完再关窗口。

## 换了台电脑 / 换了目录

- 整个文件夹一起拷，路径都是相对的。
- 新机器先装 QQ 9.9.36，重新扫码。
- 如果托盘图标、QQ 路径不对：删掉 `scripts\paths.local.ps1`，让 `start.ps1` 重新探测；或在里面写对 `$qqPath`。
- 备份 zip 可以直接还原到新目录。

## 想回到刚装好的状态

关掉大肥鱼，删这些（别删 `cmd_config.json`、`dafeiyu_character.md` 和配置文件）：

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

再运行 `scripts\start.cmd`。

## 还是不行

把下面三个文件发给维护的人（先确认里面没有 API Key 和 QQ 号）：

- `runtime\logs\启动.log`
- `runtime\AstrBot-4.29.3\startup.log` 最后 100 行
- `runtime\napcat-shell\startup.log` 最后 100 行

---

整理 / 维护：**YunShan_You（悠云山）**
