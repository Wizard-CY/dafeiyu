# 参与开发

谢谢你看这个项目。它是个人项目，节奏不快，但 Issue 和 PR 都会看。

## 先跑起来

普通使用不用看这里：直接下 [Releases](https://github.com/Wizard-CY/dafeiyu/releases/latest) 的完整包，按 [README](README.md) 走。

要改代码，需要：

- Windows 10/11 x64；
- Python 3.12（完整包里的 `runtime\python\python.exe` 也能用）；
- 一份完整运行包。仓库不带 Python、Node、ffmpeg、NapCat，这些只在 Release 里。

插件源码在 `plugins/`，运行时在 `runtime\AstrBot-4.29.3\data\plugins\`。改完插件后同步过去：

```powershell
python tools\sync_plugins.py          # 复制 plugins/ 到运行目录
python tools\sync_plugins.py --check  # 只检查有没有同步，不写文件
```

`dafeiyu_state.py` 会被复制到 `runtime\AstrBot-4.29.3\data\`，插件里的 `from data.dafeiyu_state import ...` 靠它。

## 可以提什么

- **Bug**：用 [Bug 模板](.github/ISSUE_TEMPLATE/bug_report.yml)，附版本、日志和复现步骤。
- **新功能**：先开 Issue 说清楚场景，别直接写大 PR。这个项目很小，方向不对的 PR 双方都累。
- **文档修正**：直接 PR，不用先开 Issue。
- **插件兼容性**：AstrBot / NapCat 升级导致的问题，注明版本。

## 不要提交

- `scripts/paths.local.ps1`、`backend/qqmusic/cookie.json`、`runtime/` 下的日志、数据库、备份、缓存；
- API Key、QQ 号、聊天记录、`诊断报告.txt`；
- 从 Release 包里复制出来的 `runtime/` 二进制（Python、Node、ffmpeg、NapCat）。

`.gitignore` 已经挡了大部分，提交前还是看一眼 `git status`。

## 代码风格

- Python 3.12，4 空格；能过 `python -m compileall scripts plugins` 是底线。
- PowerShell 尽量过 `Invoke-ScriptAnalyzer -Severity Error`。
- 提交信息用 `type: summary`：`feat` / `fix` / `docs` / `chore` / `ci` / `test`。
- 一次 commit 只做一件事，别顺手格式化整个文件。

## PR

- 写清楚改了什么、为什么、怎么验证。
- 行为有变化就更新 README、`docs/` 或 `CHANGELOG.md`。
- 不要提交与主题无关的改动；diff 越小，看得越快。
