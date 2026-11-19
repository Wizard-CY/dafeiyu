#!/usr/bin/env python3
"""把仓库里的源码和一份完整运行目录组装成发布目录。

示例：
    python tools/build_release.py --runtime "D:/path/to/clean-package" --out dist --zip

它不会下载任何东西；运行时（Python、Node、ffmpeg、NapCat）必须由你提供。
默认不复制 QQ 安装包、listen_music 和任何聊天数据/凭据。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / 'VERSION').read_text(encoding='utf-8').strip()
ZIP_NAME = f'dafeiyu-{VERSION}-full.zip'

COPY_ROOTS = ('assets', 'docs', 'LICENSES', 'scripts')
COPY_FILES = (
    'README.md', 'AUTHOR.txt', 'DISCLAIMER.md', 'LICENSE', 'NOTICE.md', 'VERSION',
    'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md', '.gitignore',
)
IGNORE_NAMES = {
    '__pycache__', '.venv', 'backups', 'logs', 'cookie.json', 'browser_profile',
    'paths.local.ps1', 'data_v4.db', 'memory', 'profiles', 'friend_archive',
    'voice_cache', 'temp', 'dist', 'qr_login.png', 'RELEASING.md',
}
IGNORE_SUFFIXES = ('.pyc', '.pyo', '.log', '.tmp', '.part', '.partial')


def ignore(dirname: str, names: list[str]) -> set[str]:
    """shutil.copytree ignore callback."""
    skipped: set[str] = set()
    for name in names:
        if name in IGNORE_NAMES:
            skipped.add(name)
        elif name.endswith(IGNORE_SUFFIXES):
            skipped.add(name)
        elif name.startswith('data_v4.db'):
            skipped.add(name)
    return skipped


def copy_tree(src: Path, dst: Path) -> None:
    """Copy a directory, skipping runtime state and caches."""
    if not src.is_dir():
        return
    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
    """Copy a file if it exists."""
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def check_no_secrets(root: Path) -> None:
    """Abort if common credential patterns show up in configs."""
    problems: list[str] = []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.json', '.yaml', '.yml', '.md'}:
            continue
        if 'runtime/python' in path.as_posix() or 'node_modules' in path.as_posix():
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        if re.search(r'sk-[A-Za-z0-9]{16,}', text):
            problems.append(f'{path.relative_to(root)}: 疑似 API Key')
        if path.name == 'cmd_config.json':
            try:
                data = json.loads(text)
            except ValueError:
                continue
            dashboard = data.get('dashboard') or {}
            for key in ('password', 'pbkdf2_password', 'jwt_secret'):
                if dashboard.get(key):
                    problems.append(f'{path.relative_to(root)}: dashboard.{key} 非空')
            for source in data.get('provider_sources') or []:
                if source.get('key'):
                    problems.append(f'{path.relative_to(root)}: provider_sources 里有 Key')
    if problems:
        print('发现疑似密钥/密码，已停止：', file=sys.stderr)
        for item in problems:
            print('  ' + item, file=sys.stderr)
        raise SystemExit(2)


def build(runtime: Path, out: Path, force: bool, with_qq: bool, with_listen_music: bool, make_zip: bool) -> Path:
    """Assemble the release directory and optionally zip it."""
    target = out / f'dafeiyu-{VERSION}'
    if target.exists():
        if not force:
            raise SystemExit(f'{target} 已存在；加 --force 才覆盖')
        shutil.rmtree(target)
    target.mkdir(parents=True)

    # 1) runtime and backend from the clean package
    copy_tree(runtime / 'runtime', target / 'runtime')
    copy_tree(runtime / 'backend', target / 'backend')
    copy_tree(runtime / 'data', target / 'data')

    # 2) repo-owned files win over the runtime's copies
    for name in COPY_ROOTS:
        copy_tree(ROOT / name, target / name)
    for name in COPY_FILES:
        copy_file(ROOT / name, target / name)

    # 3) plugin source
    plugins_dst = target / 'runtime' / 'AstrBot-4.29.3' / 'data' / 'plugins'
    plugins_dst.mkdir(parents=True, exist_ok=True)
    for plugin in sorted((ROOT / 'plugins').glob('dafeiyu_*')):
        if plugin.is_dir():
            shutil.copytree(plugin, plugins_dst / plugin.name, ignore=ignore, dirs_exist_ok=True)

    # 2.0.1 起默认不发 listen_music：上游未声明许可证；B 站兜底需自己装。
    listen_music = plugins_dst / 'astrbot_plugin_listen_music'
    if not with_listen_music and listen_music.exists():
        shutil.rmtree(listen_music)
    copy_file(ROOT / 'plugins' / 'dafeiyu_state.py',
              target / 'runtime' / 'AstrBot-4.29.3' / 'data' / 'dafeiyu_state.py')

    # 4) QQ installer: opt-in only, and never from the repo
    installer = target / 'runtime' / 'installer'
    if with_qq and (runtime / 'runtime' / 'installer').is_dir():
        copy_tree(runtime / 'runtime' / 'installer', installer)
    elif installer.exists():
        shutil.rmtree(installer)

    check_no_secrets(target)
    print(f'staged: {target}')
    if not (target / 'runtime' / 'AstrBot-4.29.3' / 'main.py').is_file():
        print('提醒：runtime/AstrBot-4.29.3 不完整，确认 --runtime 指向了完整包。')

    if make_zip:
        archive = out / ZIP_NAME
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for path in sorted(target.rglob('*')):
                if path.is_file():
                    zf.write(path, Path(target.name) / path.relative_to(target))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        (out / f'{ZIP_NAME}.sha256').write_text(f'{digest}  {ZIP_NAME}\n', encoding='utf-8')
        print(f'zip:    {archive}')
        print(f'sha256: {digest}')
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description='组装大肥鱼发布目录')
    parser.add_argument('--runtime', type=Path, required=True, help='干净的完整运行目录（含 runtime/、backend/）')
    parser.add_argument('--out', type=Path, default=ROOT / 'dist', help='输出目录')
    parser.add_argument('--force', action='store_true', help='目标已存在时覆盖')
    parser.add_argument('--with-qq-installer', action='store_true', help='把 QQ 9.9.36 安装包也打进去')
    parser.add_argument('--with-listen-music', action='store_true', help='把未声明许可证的 listen_music 也打进去（不建议）')
    parser.add_argument('--zip', action='store_true', help='同时生成 zip 和 sha256')
    args = parser.parse_args()

    runtime = args.runtime.resolve()
    if not runtime.is_dir():
        print(f'运行目录不存在：{runtime}', file=sys.stderr)
        return 1
    build(runtime, args.out.resolve(), args.force, args.with_qq_installer, args.with_listen_music, args.zip)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
