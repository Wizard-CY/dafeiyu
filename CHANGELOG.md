# Changelog

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号按 [SemVer](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- `plugins/`：18 个 `dafeiyu_*` 插件的源码，以及 `dafeiyu_state.py`。发版时由 `tools/build_release.py` 复制进运行目录。
- `tools/sync_plugins.py`：把 `plugins/` 同步到 `runtime/AstrBot-4.29.3/data/plugins/`，支持 `--check`。
- `CONTRIBUTING.md`、`SECURITY.md`、`docs/PRIVACY.md`、`docs/UPGRADE.md`。
- `.github/ISSUE_TEMPLATE/`、`FUNDING.yml`、CI（编译、测试、PowerShell 静态检查、密钥扫描）。
- `.gitattributes`、`.editorconfig`、`pyproject.toml`、`requirements-dev.txt`、`tests/`。

### Changed

- README 重写：先讲这是什么，再讲怎么跑；安装细节移到 `docs/INSTALL.md`。
- 爱发电链接移到 README 末尾，改由 `.github/FUNDING.yml` 提供 Sponsor 入口。
- 版本历史和发布流程移到 `docs/RELEASING.md`。

### Fixed

- `README.md` 和 `docs/TROUBLESHOOTING.md` 里的本机路径，改成相对路径 / 通用示例。

### Security

- 新增 `tools/check_secrets.py`，CI 扫描当前文件中的 Key、密码和本机路径。
- 历史里的旧 dashboard 密码需要单独清理，步骤见 `docs/RELEASING.md`；这一步没有自动执行。

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
