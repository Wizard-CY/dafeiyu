#!/usr/bin/env python3
"""把 plugins/ 同步到运行目录。

用法：
    python tools/sync_plugins.py
    python tools/sync_plugins.py --check

只同步 dafeiyu_* 插件和 dafeiyu_state.py，不动 astrbot_plugin_listen_music。
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'plugins'
DATA = ROOT / 'runtime' / 'AstrBot-4.29.3' / 'data'
DEST = DATA / 'plugins'
STATE = DATA / 'dafeiyu_state.py'
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store', 'Thumbs.db')


def files(root: Path) -> dict[str, str]:
    """Return relative path -> sha1 for every file under root."""
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        if any(part in {'__pycache__'} for part in path.parts):
            continue
        if path.suffix == '.pyc':
            continue
        rel = path.relative_to(root).as_posix()
        out[rel] = hashlib.sha1(path.read_bytes()).hexdigest()
    return out


def diff() -> list[str]:
    """Return human-readable differences between SRC and DEST."""
    problems: list[str] = []
    for src_dir in sorted(SRC.glob('dafeiyu_*')):
        if not src_dir.is_dir():
            continue
        name = src_dir.name
        want = files(src_dir)
        have = files(DEST / name)
        for rel in sorted(set(want) | set(have)):
            if rel not in have:
                problems.append(f'missing  {name}/{rel}')
            elif rel not in want:
                problems.append(f'extra    {name}/{rel}')
            elif want[rel] != have[rel]:
                problems.append(f'changed  {name}/{rel}')
    src_state = SRC / 'dafeiyu_state.py'
    if src_state.is_file():
        if not STATE.is_file():
            problems.append('missing  data/dafeiyu_state.py')
        elif src_state.read_bytes() != STATE.read_bytes():
            problems.append('changed  data/dafeiyu_state.py')
    return problems


def apply() -> None:
    """Copy plugins and state file into the runtime data directory."""
    DEST.mkdir(parents=True, exist_ok=True)
    for stale in DEST.glob('dafeiyu_*'):
        if stale.is_dir() and not (SRC / stale.name).is_dir():
            shutil.rmtree(stale)
            print(f'removed {stale.name}')
    for src_dir in sorted(SRC.glob('dafeiyu_*')):
        if not src_dir.is_dir():
            continue
        target = DEST / src_dir.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(src_dir, target, ignore=IGNORE)
        print(f'copied  {src_dir.name}')
    src_state = SRC / 'dafeiyu_state.py'
    if src_state.is_file():
        DATA.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_state, STATE)
        print('copied  dafeiyu_state.py -> data/')


def main() -> int:
    parser = argparse.ArgumentParser(description='同步 plugins/ 到运行目录')
    parser.add_argument('--check', action='store_true', help='只检查，不写文件')
    args = parser.parse_args()

    if not SRC.is_dir():
        print(f'plugins/ 不存在：{SRC}', file=sys.stderr)
        return 1

    if args.check:
        problems = diff()
        if problems:
            print(f'未同步（{len(problems)} 处）：')
            for item in problems[:40]:
                print('  ' + item)
            print('\n运行 python tools/sync_plugins.py 同步。')
            return 1
        print('已同步。')
        return 0

    apply()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
