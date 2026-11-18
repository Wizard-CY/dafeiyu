#!/usr/bin/env python3
"""扫描当前仓库文件里的密钥、密码和个人路径。

只扫项目自己的文件，不扫 runtime/、backend vendor 和 2.0版本/。
历史扫描在 docs/RELEASING.md 里单独说明。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOTS = ('scripts', 'plugins', 'docs', 'tools', 'tests', '.github', 'assets')
ROOT_FILES = ('README.md', 'NOTICE.md', 'DISCLAIMER.md', 'CONTRIBUTING.md', 'SECURITY.md', 'CHANGELOG.md')
SKIP_DIRS = {'__pycache__', '.git', 'node_modules', 'site-packages', 'vendor', 'dist', '2.0版本'}
SKIP_NAMES = {'paths.local.ps1'}
TEXT_SUFFIXES = {'.py', '.pyw', '.ps1', '.cmd', '.md', '.json', '.yml', '.yaml', '.txt', '.toml', '.ini', '.cfg'}

PATTERNS = (
    (re.compile(r'sk-[A-Za-z0-9]{20,}'), 'API Key'),
    (re.compile(r'D:\\JingJing', re.IGNORECASE), '本机路径'),
    (re.compile(r'C:\\Users\\[A-Za-z0-9][A-Za-z0-9_.-]*'), '本机路径'),
    (re.compile(r'(password|passwd|pwd)\s*[:=]\s*["\'][^"\']{6,}["\']', re.IGNORECASE), '疑似写死的密码'),
    (re.compile(r'(api[_-]?key|token|secret)\s*[:=]\s*["\'][A-Za-z0-9_\-]{24,}["\']', re.IGNORECASE), '疑似写死的凭据'),
)

ALLOW = (
    'sk-你的Key',
    'sk-test',
    'sk-bay-abc123',
    'your-token',
)


def iter_files():
    """Yield text files inside the project-owned directories."""
    seen: set[Path] = set()
    for name in ROOTS:
        root = ROOT / name
        if not root.is_dir():
            continue
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.name in SKIP_NAMES:
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            seen.add(path)
            yield path
    for name in ROOT_FILES:
        path = ROOT / name
        if path.is_file() and path not in seen:
            yield path


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    problems: list[tuple[Path, int, str, str]] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(token in line for token in ALLOW):
                continue
            for pattern, label in PATTERNS:
                if pattern.search(line):
                    problems.append((path, lineno, label, line.strip()[:140]))

    if not problems:
        print('check_secrets: ok')
        return 0

    print(f'check_secrets: 发现 {len(problems)} 处可疑内容', file=sys.stderr)
    for path, lineno, label, line in problems:
        rel = path.relative_to(ROOT)
        print(f'  {rel}:{lineno}: {label}: {line}', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
