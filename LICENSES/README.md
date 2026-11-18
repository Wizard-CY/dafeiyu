# 许可证文本

这里放的是随包第三方组件的许可证，和根目录的 [LICENSE](../LICENSE)（本项目 AGPL-3.0）不是一回事。

| 文件 | 对应组件 | 说明 |
|---|---|---|
| `NapCat-LICENSE.txt` | NapCat | 再分发必须附带全文 |
| `ffmpeg-LICENSE.txt` | ffmpeg | 构建信息和简短声明 |
| `GPL-3.0.txt` | ffmpeg 的 GPLv3 构建 | GPLv3 全文 |
| `Node-LICENSE.txt` | Node.js | MIT 及 Node 自带第三方组件许可 |
| `Apache-2.0.txt` | qqmusic-api-enhanced 的 Apache-2.0 部分 | 与 MIT 部分一起遵守 |

其它组件的许可证留在原处：

- AstrBot：`runtime/AstrBot-4.29.3/LICENSE`
- CPython：`runtime/python/LICENSE.txt`
- qqmusic-api-enhanced：`backend/qqmusic/vendor/qqmusic-api-enhanced/LICENSE`
- Python 包：`runtime/python/Lib/site-packages/*.dist-info`
- NapCat 的 node_modules：`runtime/napcat-shell/node_modules/*/LICENSE`

打包 Release 时，把这个目录一起带上。
