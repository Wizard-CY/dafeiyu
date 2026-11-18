"""setup.py 的占位符替换测试。"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


setup = load('dafeiyu_setup', ROOT / 'scripts' / 'setup.py')


def make_tree(base: Path) -> Path:
    data = base / 'runtime' / 'AstrBot-4.29.3' / 'data'
    data.mkdir(parents=True)
    (base / 'scripts').mkdir()
    (base / 'assets').mkdir()
    (base / 'backend').mkdir()
    (data / 'cmd_config.json').write_text(
        json.dumps({
            'provider_sources': [{'id': 'deepseek', 'key': []}],
            'provider': [{'id': 'deepseek-chat', 'model': 'deepseek-flash'}],
            'platform': [{'id': 'dafeiyu-qq', 'ws_reverse_token': ''}],
            'admins_id': [],
            'dashboard': {'password': ''},
        }, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    (data / 'dafeiyu_character.md').write_text('主人 QQ：1000000001\n', encoding='utf-8')
    (base / 'scripts' / 'probe.ps1').write_text('$bot = 1000000000\n', encoding='utf-8')
    return data


def test_validate_qq_rejects_short_number() -> None:
    with pytest.raises(SystemExit):
        setup.validate_qq('123')


def test_main_replaces_placeholders(tmp_path, monkeypatch) -> None:
    data = make_tree(tmp_path)
    monkeypatch.setattr(setup, 'BASE', tmp_path)
    monkeypatch.setattr(setup, 'DATA', data)
    monkeypatch.setattr(
        sys, 'argv',
        ['setup.py', '--bot', '123456789', '--owner', '987654321', '--api', 'sk-test-key'],
    )

    setup.main()

    config = json.loads((data / 'cmd_config.json').read_text(encoding='utf-8'))
    assert config['provider_sources'][0]['key'] == ['sk-test-key']
    assert config['admins_id'] == ['987654321']
    assert '987654321' in (data / 'dafeiyu_character.md').read_text(encoding='utf-8')
    assert '1000000000' not in (tmp_path / 'scripts' / 'probe.ps1').read_text(encoding='utf-8')


def test_dry_run_does_not_write(tmp_path, monkeypatch, capsys) -> None:
    data = make_tree(tmp_path)
    before = (data / 'cmd_config.json').read_text(encoding='utf-8')
    monkeypatch.setattr(setup, 'BASE', tmp_path)
    monkeypatch.setattr(setup, 'DATA', data)
    monkeypatch.setattr(
        sys, 'argv',
        ['setup.py', '--bot', '123456789', '--owner', '987654321', '--api', 'sk-test-key', '--dry-run'],
    )

    setup.main()

    assert (data / 'cmd_config.json').read_text(encoding='utf-8') == before
    assert 'dry-run' in capsys.readouterr().out
