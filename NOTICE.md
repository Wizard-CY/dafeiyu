# NOTICE · 许可与第三方组件

大肥鱼（DaFeiYu）
Copyright (C) 2026 YunShan_You（悠云山）

本项目按 **GNU Affero General Public License v3.0** 发布，全文见 [LICENSE](LICENSE)。

## 1. 许可范围

- 作者原创的部分：`plugins/`、`scripts/`、`tools/`、`docs/`、`README.md`、`DISCLAIMER.md` 等，按 AGPL-3.0 授权。
- `runtime/AstrBot-4.29.3/`：来自 AstrBot 4.29.3，版权归 Soulter 及贡献者，同样按 AGPL-3.0 授权，许可证文本在 `runtime/AstrBot-4.29.3/LICENSE`。
- 下面列出的第三方组件不适用本项目的 AGPL-3.0，各自按自己的许可证授权。

## 2. 组件清单

| 组件 | 版本 | 许可证 | 版权 / 来源 | 许可文本 |
|---|---|---|---|---|
| AstrBot | 4.29.3 | AGPL-3.0 | Soulter 及贡献者 · https://github.com/AstrBotDevs/AstrBot | `runtime/AstrBot-4.29.3/LICENSE` |
| NapCat（NapCatQQ） | 4.18.42 | Limited Redistribution License（禁止商用） | © 2024 Mlikiowa · https://github.com/NapNeko/NapCatQQ | `LICENSES/NapCat-LICENSE.txt` |
| CPython | 3.12.14 | Python Software Foundation License | Python Software Foundation · https://www.python.org | `runtime/python/LICENSE.txt` |
| Python 依赖 | 随包 | 各自许可 | 各作者 | `runtime/python/Lib/site-packages/*.dist-info` |
| ffmpeg | 7.1 essentials_build（gyan.dev） | GPL-3.0 | FFmpeg developers / Gyan Doshi · https://ffmpeg.org | `LICENSES/ffmpeg-LICENSE.txt` |
| Node.js | 随包 | MIT + 第三方 | Node.js contributors · https://nodejs.org | `LICENSES/Node-LICENSE.txt` |
| astrbot_plugin_listen_music | 0.1.3 | 未声明许可证 | 57Darling02 · https://github.com/57Darling02/astrbot_plugin_listen_music；仅 2.0.0 完整包含有 | 无 |
| edge-tts | 7.3.1 | MIT + LGPL-3.0 | Christopher Dow / rany2 · https://github.com/rany2/edge-tts | `runtime/python/Lib/site-packages/edge_tts-*.dist-info` |
| qqmusic-api-enhanced | 1.0.8 | MIT AND Apache-2.0 | © 2026 BakaGame | `backend/qqmusic/vendor/qqmusic-api-enhanced/LICENSE`、`LICENSES/Apache-2.0.txt` |
| dafeiyu_diary（空间动态） | 1.2.0 | MIT | © 2026 cube-lover；本仓库保留许可文本 | `plugins/dafeiyu_diary/LICENSE` |
| QQ NT | 9.9.36 | 腾讯软件许可 | 腾讯 | 不授予任何再分发许可，见第 3.6 条 |

## 3. 再分发时要注意

1. **AstrBot（AGPL-3.0）**：保留版权声明和许可证；如果改过源码，按第 5 条标注修改内容和日期；通过网络提供服务时，要向用户提供对应源码。AstrBot 源码在 `runtime/AstrBot-4.29.3/`，完整包里也带了一份。
2. **NapCat（Limited Redistribution License）**：再分发必须附上完整许可文本、注明来源和版权；禁止商用；修改后的代码不得公开。许可文本在 `LICENSES/NapCat-LICENSE.txt`。
3. **ffmpeg（GPLv3 构建）**：构建参数里有 `--enable-gpl --enable-version3`，属于 GPLv3。再分发要附 GPLv3 全文，并提供对应源码的获取方式。源码用 ffmpeg 7.1 官方 tarball：https://ffmpeg.org/releases/ffmpeg-7.1.tar.xz ；构建来自 gyan.dev，构建信息在 `LICENSES/ffmpeg-LICENSE.txt`，GPLv3 全文在 `LICENSES/GPL-3.0.txt`。
4. **CPython 和 Python 包**：CPython 的许可文本在 `runtime/python/LICENSE.txt`；第三方包各自许可见 `dist-info`，打包时别删。
5. **astrbot_plugin_listen_music**：上游仓库没有声明许可证，严格说没有明确授权。2.0.0 的完整包里还带着它；2.0.1 起不再随包。你需要 B 站兜底的话可以自己装，但再分发前先确认许可。
6. **QQ NT 9.9.36 安装包**：腾讯的专有软件。2.0.0 的完整包附带安装包，只是为了在 NapCat 只支持 9.9.36 时方便装旧版，不构成任何授权或再分发许可。2.0.1 起不再附带；使用者自己准备同版本安装包。
7. **QQ 音乐 / QQ 空间**：腾讯服务，账号和登录凭据由使用者自己提供，cookie 不随包分发。

## 4. 修改说明

如果对 AstrBot 源码做过修改，按 AGPL-3.0 第 5 条在发布时标注修改内容和日期。截至 2.0.1，仓库里没有记录对 AstrBot 的本地补丁；如果你改了，请在这里列出日期、文件和改了什么。

## 5. 说明

本文件只用于说明许可信息，不构成法律意见。
