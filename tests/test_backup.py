"""backup.py 的备份范围测试。"""
from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


backup = load('dafeiyu_backup', ROOT / 'scripts' / 'backup.py')


def test_backup_keeps_chat_and_drops_cookie(tmp_path, monkeypatch) -> None:
    data = tmp_path / 'runtime' / 'AstrBot-4.29.3' / 'data'
    (data / 'plugins' / 'dafeiyu_quota').mkdir(parents=True)
    (data / 'plugins' / 'dafeiyu_quota' / 'main.py').write_text('# plugin\n', encoding='utf-8')
    (data / 'cmd_config.json').write_text('{"platform": []}\n', encoding='utf-8')
    (data / 'memory').mkdir()
    (data / 'memory' / 'note.txt').write_text('remember\n', encoding='utf-8')
    (data / 'collected_stickers').mkdir()
    (data / 'collected_stickers' / 'a.png').write_bytes(b'png')

    (tmp_path / 'scripts').mkdir()
    (tmp_path / 'scripts' / 'status.pyw').write_text('# ui\n', encoding='utf-8')
    (tmp_path / 'docs').mkdir()
    (tmp_path / 'docs' / 'INSTALL.md').write_text('# install\n', encoding='utf-8')
    (tmp_path / 'backend' / 'qqmusic' / 'vendor').mkdir(parents=True)
    (tmp_path / 'backend' / 'qqmusic' / 'server.mjs').write_text('// backend\n', encoding='utf-8')
    (tmp_path / 'backend' / 'qqmusic' / 'cookie.json').write_text('{"cookie": "secret"}\n', encoding='utf-8')
    (tmp_path / 'README.md').write_text('# readme\n', encoding='utf-8')

    monkeypatch.setattr(backup, 'BASE', tmp_path)
    monkeypatch.setattr(backup, 'DATA', data)
    monkeypatch.setattr(backup, 'SCRIPTS', tmp_path / 'scripts')
    monkeypatch.setattr(backup, 'DEST', tmp_path / 'runtime' / 'backups')

    backup.main()

    archives = list((tmp_path / 'runtime' / 'backups').glob('dafeiyu_*.zip'))
    assert len(archives) == 1
    names = zipfile.ZipFile(archives[0]).namelist()

    assert 'data/plugins/dafeiyu_quota/main.py' in names
    assert 'data/cmd_config.json' in names
    assert 'data/memory/note.txt' in names
    assert 'scripts/status.pyw' in names
    assert 'backend/qqmusic/server.mjs' in names
    assert not any('cookie.json' in name for name in names)
