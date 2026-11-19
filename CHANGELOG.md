# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号按 [SemVer](https://semver.org/lang/zh-CN/)。

## [2.0.1] - 2026-11-19

### Added

- `plugins/`：18 个 `dafeiyu_*` 插件的源码，以及 `dafeiyu_state.py`。发版时由 `tools/build_release.py` 复制进运行目录。
- `tools/sync_plugins.py`：把 `plugins/` 同步到 `runtime/AstrBot-4.29.3/data/plugins/`，支持 `--check`。
- `CONTRIBUTING.md`、`SECURITY.md`、`docs/PRIVACY.md`、`docs/UPGRADE.md`、`docs/RELEASING.md`。
- `.github/ISSUE_TEMPLATE/`、`FUNDING.yml`、CI（编译、测试、PowerShell 语法检查、密钥扫描）。
- `.gitattributes`、`.editorconfig`、`pyproject.toml`、`requirements-dev.txt`、`tests/`。

### Changed

- README 重写：先讲这是什么，再讲怎么跑；安装细节移到 `docs/INSTALL.md`。
- 爱发电链接移到 README 末尾，改由 `.github/FUNDING.yml` 提供 Sponsor 入口。
- 2.0.1 发布包目录名改为 `dafeiyu-2.0.1`，默认不再附带 QQ 安装包和 `listen_music`。
- 包内 README/docs 与仓库同步，修复旧 README 里的本机路径。

### Removed

- 完整包不再附带 QQ 9.9.36 安装包；使用者自己准备同版本官方包。
- 不再附带 `astrbot_plugin_listen_music`（上游未声明许可证）；B 站点歌兜底需要自行安装。

### Security

- 新增 `tools/check_secrets.py`，CI 扫描当前文件中的 Key、密码和本机路径。
- 已用 `git filter-repo` 清理历史里的旧 dashboard 密码和本机路径，并 force push `main` 和 tags。

## [2.0.0] - 2026-11-18

### Added

- 2.0 可移植整合包：自带 Python 3.12、Node、ffmpeg、NapCat 4.18.42。
- 18 个 `dafeiyu_*` 插件：私聊、群聊、记忆、表情、语音、点歌、空间动态、好友清理、广播、错误邮箱等。
- 托盘控制中心：总览、私聊额度、群聊状态、好友清理、广播。
- 首次配置向导 `scripts/setup.cmd`、诊断脚本 `scripts/diagnose.cmd`、一键下线 `scripts/stop.cmd`。
- 断线重连、看门狗、破甲防护、每日记忆提炼、备份保留 8 份。

### Changed

- 包目录为 `2.0版本\`；QQ 固定使用 9.9.36。
- dashboard 密码不再预置，首次启动生成随机密码。
- 运行包与源码分开发布：仓库保留源码和文档，完整运行包在 Releases。

## [1.0.1] - 2026-11-05

### Fixed

- 移除预置的 dashboard 密码，改为首次启动生成。
- 移除个人路径和本地聊天数据库 `data_v4.db`。
- 启动脚本改为自动探测路径。

### Added

- AGPL-3.0 `LICENSE`、`NOTICE.md`、`LICENSES/` 和截图说明。
