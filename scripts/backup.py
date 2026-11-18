"""把运行中的配置、插件、记忆和表情打包成每日备份 zip。

整理 / 维护：YunShan_You（悠云山）
"""

import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'runtime' / 'AstrBot-4.29.3' / 'data'
SCRIPTS = BASE / 'scripts'
DEST = BASE / 'runtime' / 'backups'
KEEP = 8
SKIP_NAMES = {'__pycache__', 'dafeiyu_media', 'temp', 'logs', 'dist'}
SKIP_SUFFIXES = ('.lock',)


def add_tree(archive, root, arc_prefix):
    """递归写入目录，跳过缓存和运行中的锁文件。"""
    if not root.is_dir():
        return
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if any(part in SKIP_NAMES for part in rel.parts):
            continue
        if path.name.endswith(SKIP_SUFFIXES):
            continue
        if path.is_file():
            archive.write(path, arc_prefix + '/' + rel.as_posix())


def sqlite_snapshot(source, target):
    """用 SQLite 在线备份接口取一致快照。"""
    with sqlite3.connect(source) as src:
        with sqlite3.connect(target) as dst:
            src.backup(dst)


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / f'dafeiyu_{datetime.now():%Y%m%d_%H%M%S_%f}.zip'
    group_snapshot = DEST / '_group_memory.sqlite'
    conv_snapshot = DEST / '_conversations.sqlite'
    for snapshot, source in (
        (group_snapshot, DATA / 'dafeiyu_group_memory.db'),
        (conv_snapshot, DATA / 'data_v4.db'),
    ):
        if source.exists():
            sqlite_snapshot(source, snapshot)

    partial = target.with_suffix('.zip.partial')
    with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as archive:
        add_tree(archive, DATA / 'plugins', 'data/plugins')
        for name in ('cmd_config.json', 'skills.json', 'mcp_server.json'):
            if (DATA / name).exists():
                archive.write(DATA / name, 'data/' + name)
        for path in sorted(DATA.glob('dafeiyu_*')):
            if path.is_file() and path.name not in ('dafeiyu_group_memory.db', 'dafeiyu_feed_snippet.txt'):
                archive.write(path, 'data/' + path.name)
        if (DATA / 'stickers' / 'catalog.json').exists():
            archive.write(DATA / 'stickers' / 'catalog.json', 'data/stickers/catalog.json')
        add_tree(archive, SCRIPTS, 'scripts')
        add_tree(archive, BASE / 'docs', 'docs')
        if (BASE / 'README.md').exists():
            archive.write(BASE / 'README.md', 'README.md')
        backend = BASE / 'backend' / 'qqmusic'
        if (backend / 'server.mjs').exists():
            archive.write(backend / 'server.mjs', 'backend/qqmusic/server.mjs')
        add_tree(archive, backend / 'vendor', 'backend/qqmusic/vendor')
        for folder in ('memory', 'profiles', 'collected_stickers'):
            if (DATA / folder).is_dir():
                add_tree(archive, DATA / folder, 'data/' + folder)
        if group_snapshot.exists():
            archive.write(group_snapshot, 'data/dafeiyu_group_memory.db')
        if conv_snapshot.exists():
            archive.write(conv_snapshot, 'data/data_v4.db')
    partial.replace(target)

    for leftover in (group_snapshot, conv_snapshot):
        if leftover.exists():
            try:
                leftover.unlink()
            except OSError:
                pass
    old = sorted(DEST.glob('dafeiyu_*.zip'))[:-KEEP]
    for item in old:
        item.unlink()
    print(target)


if __name__ == '__main__':
    main()
