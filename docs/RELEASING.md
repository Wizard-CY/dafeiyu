# 发版

这份是维护者自己的清单，不是给普通用户看的。

## 0. 日常更新（不发版）

```powershell
cd D:\dafeiyu
git add <改过的文件>          # 按需 add，别把本地图/日志/诊断报告带进去
git commit -m "docs: ..."
git push origin main
```

`git push` 用的是本机 `gh` 保存的 token（Windows 凭据管理器），不需要每次登录。

检查 token 有没有 `workflow` 权限：

```powershell
gh auth status
# Token scopes 里应该有 'workflow'
```

没有的话，做一次（VPN 开着）：

```powershell
$env:HTTPS_PROXY = 'http://127.0.0.1:7890'
gh auth refresh -h github.com -s workflow
```

授权一次后，本机会记住，以后 push 不用再授权。`gh` 命令报网络错误时，也可以先设置这个 `HTTPS_PROXY`。

push 后 CI 会自动跑：

```powershell
gh run list
gh run watch
```

## 1. 发布前

- 改 `VERSION`，同步 `CHANGELOG.md`。
- `python tools/sync_plugins.py --check` 应该通过；不通过就先同步。
- `python -m compileall -q scripts plugins tests`。
- `python -m pytest -q`。
- `python tools/check_secrets.py`。

## 2. 组装

先准备一份干净的完整运行目录（从上一版 release 解压，或者从本机运行目录复制）。然后：

```powershell
python tools\build_release.py --runtime "D:\path\to\clean\runtime-package" --out dist --zip
```

脚本会：

- 复制运行时的 `runtime\`、`backend\`、`data\music_library\`；
- 用仓库里的 `scripts\`、`docs\`、`assets\`、`LICENSES\`、根目录文档覆盖；
- 把 `plugins\dafeiyu_*` 和 `dafeiyu_state.py` 放进 `runtime\AstrBot-4.29.3\data\`；
- 默认排除 `runtime\installer\`（QQ 安装包）、聊天数据库、记忆、日志、备份、cookie、`paths.local.ps1`；
- 检查 `cmd_config.json` 里没有 Key / 密码；
- `--zip` 时生成 `dist\dafeiyu-<version>-full.zip` 和 `.sha256`。

如果脚本报“发现疑似密钥”，不要绕过，先把运行目录清干净。

## 3. 发布

- tag 用 annotated tag：`git tag -a v2.0.1 -m "2.0.1"`。
- release note 写清楚：改了什么、包名、大小、SHA-256、是否包含 QQ 安装包。
- 上传 zip 和 `.sha256`。
- 确认 release 里没有 `QQ_9.9.36...exe`、没有 `data_v4.db`、没有 `cookie.json`。

## 4. 如果还要发 2.0.0 的修订

2.0.0 的资产名还是 `JingJing-full-2.0.0.zip`，包目录是 `2.0版本\`。改名和换目录会影响已经下载的人，所以放在下一个小版本做，不要偷偷替换资产。

## 5. 清历史里的旧密码

旧 commit 里有一个已经失效的 dashboard 密码。当前文件已经删了，但 `v1.0.0` tag 和 git 历史还能看到。清理步骤（会改写所有 commit hash，做之前先备份仓库）：

```bash
# 1. 安装 git-filter-repo（需要 Python）
pip install git-filter-repo

# 2. 在仓库外建一个私密替换文件，别提交
cat > ../scrub.txt <<'EOF'
旧密码的原文==>***REMOVED***
D:\旧目录==>D:\dafeiyu
EOF

# 3. 重写
git filter-repo --replace-text ../scrub.txt

# 4. 检查
git log --all -S '旧密码的原文' --oneline   # 应该没有输出
git log --all -S 'JingJing@' --oneline      # 应该没有输出

# 5. 重新打 tag、force push
git tag -a v2.0.0 -m "2.0.0"
git push --force --tags origin main
```

注意事项：

- 这会改写公开历史。先确认没有别人基于这些 commit 在工作。
- GitHub 上的 release 指向旧 tag 的话，要重新发或改指向。
- 清完之后，把 CI 里的 `tools/check_secrets.py` 扩展成扫历史（现在只扫当前文件）。
- 改掉 dashboard 密码，并确认新密码没有在别处复用。

## 6. 第三方组件

- `astrbot_plugin_listen_music` 上游没有许可证。2.0.0 的包里还在，下个版本要移除或替换；没解决之前不要再发带它的包。
- QQ 安装包不要再随包发。README 指向官方下载页和版本校验方法。
- 发版前跑一遍 `NOTICE.md` 的清单，确认版本号和实际文件对得上。
