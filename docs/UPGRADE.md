# 从 1.0.1 升级到 2.0

2.0 是新的目录结构和新的包，不能直接覆盖 1.0.1。按下面做，旧包先留着，出问题可以退回去。

## 1. 先备份

```powershell
# 在旧包根目录
.\runtime\python\python.exe scripts\backup.py
```

或者用旧版控制中心「结束下线」，它会先提炼记忆再备份。备份在 `runtime\backups\`。

## 2. 解压 2.0 到新目录

不要把 2.0 解压到 1.0.1 上面。2.0 的顶层目录是 `2.0版本\`（1.0.1 是 `JingJing\`），结构已经不一样了。

## 3. 迁移配置

先关掉旧包。只复制配置和你想保留的数据，**不要**把旧 `data\plugins` 整个复制过去——2.0 自带 18 个插件，旧插件可能不兼容。

建议复制：

- `runtime\AstrBot-4.29.3\data\cmd_config.json`：API Key、平台、dashboard 配置。复制后检查 `provider_sources` 里的 Key 和 `platform` 里的 OneBot token。
- `data\dafeiyu_character.md`：人设。2.0 的默认人设改过，想用旧的就覆盖。
- `data\dafeiyu_*.json`：额度、语音、断线重连、群设置等。
- `data\music_library\`（可选）：曲库。
- `data\collected_stickers\`（可选）：收集的表情包。
- `data\diary_library\`（可选）：空间动态图库。
- `data\data_v4.db`（可选）：旧的聊天记录。想保留历史就复制；AstrBot 的库结构可能变，先备份再试。

不要复制：

- `scripts\paths.local.ps1`：旧机器的路径。
- `backend\qqmusic\cookie.json`：到新包重新扫码登录。
- `runtime\backups\`：旧备份留在旧包，别混进新包。
- `runtime\python\`、`runtime\bin\`、`runtime\napcat-shell\`：用 2.0 自带的。

## 4. QQ 和 NapCat

- 2.0 只支持 QQ **9.9.36**。先卸载机器上更高版本的 QQ，装 2.0 包里的安装包（或同版本官方包），关掉自动更新。
- NapCat WebUI 还是 `http://127.0.0.1:6099`，OneBot 地址还是 `ws://127.0.0.1:6199/ws`。token 两边要一致。

## 5. 第一次启动

1. 运行 `scripts\start.cmd`。
2. 2.0 的 `cmd_config.json` 里 dashboard 密码是空的，第一次启动会生成随机密码，打在 `runtime\AstrBot-4.29.3\startup.log`：

   ```powershell
   Select-String runtime\AstrBot-4.29.3\startup.log "Initial password"
   ```

3. 登录 `http://127.0.0.1:6185`，按提示改密码。
4. 扫码登录机器人 QQ。
5. 私聊发一条，群聊 @ 一下，确认两边都通。

## 6. 检查

- `runtime\AstrBot-4.29.3\startup.log` 里有没有 `aiocqhttp(OneBot v11) 适配器已连接`。
- 控制中心「总览」的聊天程序 / QQ 接入是不是绿的。
- 额度、群设置有没有迁过来。
- 空间动态要重启一次 AstrBot 才拿得到 cookie，这是正常的。

## 回滚

旧包没删的话，直接停掉 2.0，回去跑旧包的 `scripts\start.cmd`。旧的 API Key、QQ 号、OneBot token 还在旧包里。

## 还是不行

跑 `scripts\diagnose.cmd`，把 `诊断报告.txt` 和 `runtime\logs\launcher.log` 发到 [Issues](https://github.com/Wizard-CY/dafeiyu/issues)。发之前把 Key、QQ 号、路径打码。
