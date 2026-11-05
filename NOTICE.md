# NOTICE · 许可与第三方组件

大肥鱼（DaFeiYu）  
Copyright (C) 2026 YunShan You

本项目按 **GNU Affero General Public License v3.0** 发布，全文见 [LICENSE](LICENSE)。

## 1. 许可范围

- 作者原创的部分：`scripts/`、`data/plugins/dafeiyu_*`、`docs/`、`README.md`、`DISCLAIMER.md` 等，按 AGPL-3.0 授权。
- `runtime/AstrBot-4.29.3/`：来自 AstrBot 4.29.3，版权归 Soulter 及贡献者，同样按 AGPL-3.0 授权，许可证文本在 `runtime/AstrBot-4.29.3/LICENSE`。
- 下面列出的第三方组件不适用本项目的 AGPL-3.0，各自按自己的许可证授权。

## 2. 组件清单

| 组件 | 版本 | 许可证 | 版权 / 来源 | 许可文本 |
|---|---|---|---|---|
| AstrBot | 4.29.3 | AGPL-3.0 | Soulter 及贡献者 · https://github.com/AstrBotDevs/AstrBot | `runtime/AstrBot-4.29.3/LICENSE` |
| NapCat（NapCatQQ） | 随包 | Limited Redistribution License（禁止商用） | © 2024 Mlikiowa · https://github.com/NapNeko/NapCatQQ | `LICENSES/NapCat-LICENSE.txt` |
| ffmpeg | 7.1 essentials_build（gyan.dev） | GPL-3.0 | FFmpeg developers / Gyan Doshi · https://ffmpeg.org | `LICENSES/ffmpeg-LICENSE.txt` |
| astrbot_plugin_listen_music | 0.1.3 | 未声明许可证 | 57Darling02 · https://github.com/57Darling02/astrbot_plugin_listen_music | 无 |
| edge-tts | 7.3.1 | MIT + LGPL-3.0 | Christopher Dow / rany2 · https://github.com/rany2/edge-tts | `.venv` 内 `edge_tts-7.3.1.dist-info` |
| qqmusic-api-enhanced | 1.0.8 | MIT AND Apache-2.0 | © 2026 BakaGame | `backend/qqmusic/vendor/qqmusic-api-enhanced/LICENSE`、`LICENSES/Apache-2.0.txt` |
| Python 依赖（.venv） | 随包 | 各自许可 | 各作者 | `.venv/Lib/site-packages/*.dist-info` |
| QQ NT、QQ 音乐 | — | 腾讯软件许可 | 腾讯 | 需自行安装，不随包分发 |

## 3. 再分发时要注意

1. **AstrBot（AGPL-3.0）**：保留版权声明和许可证；如果改过源码，按第 5 条标注修改内容和日期；通过网络提供服务时，要向用户提供对应源码。本仓库已经带了源码。
2. **NapCat（Limited Redistribution License）**：再分发必须附上完整许可文本、注明来源和版权；禁止商用；修改后的代码不得公开。许可文本已放在 `LICENSES/NapCat-LICENSE.txt`，打包时记得一起带上。
3. **ffmpeg（GPLv3 构建）**：构建参数里有 `--enable-gpl --enable-version3`，属于 GPLv3。再分发要附 GPLv3 全文，并提供对应源码的获取方式。`LICENSES/ffmpeg-LICENSE.txt` 目前只有构建信息和简短声明，完整文本需要另外补（https://www.gnu.org/licenses/gpl-3.0.txt）。
4. **astrbot_plugin_listen_music**：上游仓库没有声明许可证，严格说没有明确授权。再分发前建议联系作者确认，或者把它从包里移除。
5. **.venv 里的 Python 包**：各自许可见 `dist-info`，打包时别把这些目录删掉。
6. **QQ NT、QQ 音乐**：腾讯的软件，不随包分发，按腾讯的条款使用。

## 4. 修改说明

如果对 AstrBot 源码做过修改，按 AGPL-3.0 第 5 条在发布时标注修改内容和日期。仓库里没有单独的修改清单，以 git 记录为准。

## 5. 说明

本文件只用于说明许可信息，不构成法律意见。
