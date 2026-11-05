# 许可证文本

这里放的是随包第三方组件的许可证，和根目录的 [LICENSE](../LICENSE)（本项目 AGPL-3.0）不是一回事。

| 文件 | 对应组件 | 说明 |
|---|---|---|
| `NapCat-LICENSE.txt` | NapCat | 再分发必须附带全文 |
| `ffmpeg-LICENSE.txt` | ffmpeg | 构建信息和简短声明；完整 GPLv3 文本见 https://www.gnu.org/licenses/gpl-3.0.txt |

其它组件的许可证留在原处：

- AstrBot：`runtime/AstrBot-4.29.3/LICENSE`
- qqmusic-api-enhanced：`backend/qqmusic/vendor/qqmusic-api-enhanced/LICENSE` 和同目录的 `LICENSES/Apache-2.0.txt`
- Python 包：`runtime/AstrBot-4.29.3/.venv/Lib/site-packages/*.dist-info`
- NapCat 的 node_modules：`runtime/napcat-shell/node_modules/*/LICENSE`

打包 Release 时，把这个目录一起带上。
