# 大肥鱼备份脚本 · packaged by YunShan You
"""Package the running bot's settings, plugins and memory into a daily zip."""

import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'runtime' / 'AstrBot-4.29.3' / 'data'
OUTPUTS = BASE / 'assets'
DEST = BASE / 'runtime' / 'backups'
KEEP = 8
SKIP_NAMES = {'__pycache__', 'dafeiyu_media', 'temp'}


def add_tree(archive, root, arc_prefix):
    """Add a directory tree while skipping caches and generated media."""
    for path in sorted(root.rglob('*')):
        if any(part in SKIP_NAMES for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            archive.write(path, arc_prefix + '/' + path.relative_to(root).as_posix())


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / f'dafeiyu_{datetime.now():%Y%m%d_%H%M}.zip'
    snapshot = DEST / '_group_memory.sqlite'
    if (DATA / 'dafeiyu_group_memory.db').exists():
        with sqlite3.connect(DATA / 'dafeiyu_group_memory.db') as source:
            with sqlite3.connect(snapshot) as copy:
                source.backup(copy)
            copy.close()
    conv_snapshot = DEST / '_conversations.sqlite'
    if (DATA / 'data_v4.db').exists():
        with sqlite3.connect(DATA / 'data_v4.db') as source:
            with sqlite3.connect(conv_snapshot) as copy:
                source.backup(copy)
            copy.close()
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        add_tree(archive, DATA / 'plugins', 'data/plugins')
        for name in ('cmd_config.json', 'skills.json', 'mcp_server.json'):
            if (DATA / name).exists():
                archive.write(DATA / name, 'data/' + name)
        for path in sorted(DATA.glob('dafeiyu_*')):
            if path.is_file() and path.name not in ('dafeiyu_group_memory.db', 'dafeiyu_feed_snippet.txt'):
                archive.write(path, 'data/' + path.name)
        if (DATA / 'stickers' / 'catalog.json').exists():
            archive.write(DATA / 'stickers' / 'catalog.json', 'data/stickers/catalog.json')
        add_tree(archive, OUTPUTS, 'assets')
        add_tree(archive, BASE / 'scripts', 'scripts')
        for doc in sorted(BASE.glob('*.md')):
            archive.write(doc, doc.name)
        core_media = BASE / 'runtime' / 'AstrBot-4.29.3' / 'astrbot' / 'core' / 'utils' / 'media_utils.py'
        if core_media.exists():
            archive.write(core_media, 'astrbot/core/utils/media_utils.py')
        core_image = BASE / 'runtime' / 'AstrBot-4.29.3' / 'astrbot' / 'core' / 'utils' / 'image_input.py'
        if core_image.exists():
            archive.write(core_image, 'astrbot/core/utils/image_input.py')
        backend = BASE / 'backend/qqmusic'
        if (backend / 'server.mjs').exists():
            archive.write(backend / 'server.mjs', 'backend/qqmusic/server.mjs')
        if (backend / 'vendor').is_dir():
            add_tree(archive, backend / 'vendor', 'backend/qqmusic/vendor')
        if (DATA / 'memory').is_dir():
            add_tree(archive, DATA / 'memory', 'data/memory')
        if (DATA / 'collected_stickers').is_dir():
            add_tree(archive, DATA / 'collected_stickers', 'data/collected_stickers')
        if snapshot.exists():
            archive.write(snapshot, 'data/dafeiyu_group_memory.db')
        if conv_snapshot.exists():
            archive.write(conv_snapshot, 'data/data_v4.db')
    archive.close()
    for leftover in (snapshot, conv_snapshot):
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
