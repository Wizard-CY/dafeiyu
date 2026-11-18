# 安全

## 报告问题

请用 GitHub 的私密漏洞报告：仓库 **Security** 标签页 → **Report a vulnerability**。

如果看不到这个入口，先开一个不含细节的 Issue，只说“有安全问题，需要一个私密渠道”，维护者会联系你。**不要**在公开 Issue 里贴利用细节、API Key、cookie 或聊天记录。

## 请不要贴出来

- DeepSeek / OpenAI 兼容接口的 API Key；
- `backend/qqmusic/cookie.json`、OneBot token、NapCat WebUI token；
- dashboard 密码、`cmd_config.json` 里的 `jwt_secret`；
- 聊天记录、好友记忆、`诊断报告.txt` 里的本机路径和 QQ 号。

发日志或诊断报告前，至少把 `sk-` 开头的 Key、10 位 QQ 号和 `C:\Users\...` 这类路径打码。

## 支持范围

- 2.0.x：会修安全问题。
- 1.x：不再维护。

## 已知边界

- dashboard（6185）、NapCat WebUI（6099）、OneBot（6199）、QQ 音乐后端（3311）默认只监听 `127.0.0.1`。不要映射到公网，也不要做端口转发。
- 机器人 QQ 请用小号。用程序登录 QQ 有被限制或封号的风险，这不是安全问题，但后果一样由使用者承担。
- 完整包里的第三方组件（NapCat、QQ、ffmpeg 等）有各自的许可和安全边界，见 [NOTICE.md](NOTICE.md)。
