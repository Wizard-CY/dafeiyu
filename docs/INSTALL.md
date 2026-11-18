# 安装指南

这是大肥鱼的安装细则。根目录 [README.md](../README.md) 只做入口；安装细节以本文为准。

## 1. 环境

- Windows 10 / 11，64 位。
- 管理员权限（NapCat 注入 QQ 需要）。
- 机器人 QQ 小号。
- DeepSeek 或 OpenAI 兼容 API Key。
- QQ 音乐账号（可选，点歌用）。

不用装 Python、Node.js、ffmpeg、AstrBot、NapCat。包里 `runtime\python` 是自带 Python 3.12，`runtime\bin` 带 ffmpeg 和 node。

## 2. 目录

```text
runtime\AstrBot-4.29.3      AstrBot 主程序 + data（插件、人设、配置）
runtime\napcat-shell        NapCat / OneBot
runtime\bin                 ffmpeg、node
runtime\python              自带 Python 3.12 + 依赖
runtime\installer           QQ 9.9.36 安装包
backend\qqmusic             QQ 音乐后端
data\music_library          本地曲库（初始为空）
scripts\start.ps1           一键启动
scripts\stop.ps1            结束下线
scripts\setup.py            首次配置向导
scripts\status.pyw          托盘控制中心
scripts\backup.py           备份
```

## 3. 首次启动前

1. 运行 `scripts\setup.cmd`，填机器人 QQ、主人 QQ、API Key。
   - 手动改也行：在 `runtime\AstrBot-4.29.3\data\` 和 `scripts\` 里替换 `1000000000` / `1000000001`。
   - 不要在 `runtime\python`、`runtime\AstrBot-4.29.3\astrbot`、`data\dist`、`node_modules` 里替换。
2. 确认 `runtime\AstrBot-4.29.3\data\cmd_config.json` 里 `provider[0].model`（默认 `deepseek-flash`）和 API Key 对得上。
3. 安装 QQ 9.9.36，见第 4 节。
4. 设 OneBot token（可选），NapCat WebUI 和 `cmd_config.json` 两处要一致。

## 4. 安装 QQ 9.9.36

NapCat 4.18.42 只支持 QQ 9.9.36。

2.0.0 的完整包里带了安装包：

```text
runtime\installer\QQ_9.9.36_260924_x64_01.exe
```

SHA-256：`63255c70c7ff523e7eed7d52d9708ed7a77ea346ece6474c65dded406edb3155`

后续构建默认不再附带安装包，自己找同版本官方安装包即可。装完确认版本是 9.9.36。

1. 退出 QQ，卸载机器上更高版本的 QQ。
2. 运行安装包。
3. 打开 QQ 设置，关闭自动更新。
4. 确认 `HKCU\Software\Tencent\QQNT` 的 `version` 以 `9.9.36` 开头：

```powershell
Get-ItemProperty HKCU:\Software\Tencent\QQNT -Name version
```

## 5. 启动

```powershell
scripts\start.cmd
```

先做一次环境检查（不启动服务）：

```text
scripts\start.cmd check
```

或直接：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start.ps1
```

启动失败时运行 `scripts\diagnose.cmd`，把根目录生成的 `诊断报告.txt` 和 `runtime\logs\launcher.log` 发给维护的人。

启动会拉起：

| 组件 | 端口 | 说明 |
|---|---|---|
| AstrBot 后台 | 6185 | 面板 `http://127.0.0.1:6185` |
| NapCat WebUI | 6099 | `http://127.0.0.1:6099` |
| OneBot WebSocket | 6199 | NapCat 连 AstrBot |
| QQ 音乐后端 | 3311 | 点歌用，没起也不影响聊天 |

启动后首次看后台密码：

```powershell
Select-String runtime\AstrBot-4.29.3\startup.log "Initial password"
```

## 6. NapCat 配置

1. 打开 `http://127.0.0.1:6099`，用 `runtime\napcat-shell\startup.log` 或 `config\webui.json` 里的 token 登录。
2. 「网络配置」新增 WebSocket 客户端：

```text
URL:   ws://127.0.0.1:6199/ws
Token: 与 cmd_config.json 的 ws_reverse_token 一致
```

3. 启用。日志出现 `aiocqhttp(OneBot v11) 适配器已连接` 即成功。
4. QQ 登录窗里用机器人小号扫码。

## 7. 群聊

机器人登录后会自动发现它所在的群，新群默认关闭。打开控制中心「群聊状态」，找到群，点开启；需要时改每日上限（默认 120）和互动强度。

## 8. 停止与重启

```powershell
scripts\stop.cmd       # 结束下线：提炼记忆 → 备份 → 关聊天程序 / QQ
scripts\restart-ui.ps1 # 只重启托盘控制中心
```

## 9. 移动 / 换机器

整个 `2.0版本` 文件夹一起拷走即可，所有路径都是相对的。到新机器后：

1. 装 QQ 9.9.36；
2. 运行 `scripts\start.cmd`；
3. 重新扫码登录 QQ；
4. 如果 QQ 音乐要重新登录，在控制中心点「QQ音乐登录」。

API Key、两个 QQ 号、人设和记忆都跟着文件夹走。

## 10. 卸载

1. 托盘右键「退出托盘」；
2. 运行 `scripts\stop.cmd`；
3. 删除整个 `2.0版本` 文件夹；
4. 需要的话卸载 QQ。
