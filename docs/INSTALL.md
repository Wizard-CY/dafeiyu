# 安装指南

本文件是根目录 [README.md](../README.md) 的安装部分索引。完整步骤、截图和注意事项以根 README 为准。

## 1. 环境

- Windows 10 / 11 64 位
- Python 3.11
- QQ NT 客户端
- 一个单独的机器人 QQ 小号
- DeepSeek 或 OpenAI 兼容 API Key
- Node.js 18+（QQ 音乐后端，可选）
- 管理员权限（NapCat 需要）

## 2. 目录

```text
runtime/AstrBot-4.29.3      AstrBot 主程序
runtime/napcat-shell        NapCat / OneBot
runtime/bin                 ffmpeg 等
backend/qqmusic             QQ 音乐后端
data/music_library          本地曲库
scripts/start.ps1           一键启动
scripts/stop.ps1            结束下线
scripts/status.pyw          状态中心
scripts/backup.py           备份
assets/icon.ico             托盘图标
assets/persona.md           人设卡
```

## 3. 首次启动前

1. 替换占位符：
   - `1000000000` → 机器人 QQ
   - `1000000001` → 主人 QQ
   - `1000000002` → 群号
   - `**群` → 群名
2. 在 `runtime/AstrBot-4.29.3/data/cmd_config.json` 填 API Key。
3. 把 `admins_id` 改成主人 QQ。
4. 设置 OneBot token，并让 NapCat 与 AstrBot 保持一致。
5. 修改 `scripts/start.ps1` 里的 QQ、Node、pythonw 路径。

## 4. 启动

```powershell
D:\JingJing\scripts\start.ps1
```

或双击：

```text
scripts\start.cmd
```

启动后状态中心在系统托盘，单击鲸鱼图标打开。

## 5. NapCat

1. 安装 QQ NT。
2. 用机器人小号登录。
3. 打开 `http://127.0.0.1:6099`。
4. 配置 WebSocket 客户端：`ws://127.0.0.1:6199/ws`。
5. Token 与 `cmd_config.json` 的 `ws_reverse_token` 一致。

参考配置：

```text
runtime/napcat-shell/config/onebot11.example.json
```

## 6. 验证

AstrBot 日志应出现：

```text
aiocqhttp(OneBot v11) 适配器已连接
```

状态中心「QQ 接入」变绿即完成。

---

维护与整理：**YunShan You**
