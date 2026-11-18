# -*- coding: utf-8 -*-
"""大肥鱼 2.0 首次配置：替换机器人/主人 QQ，填 API Key。

整理 / 维护：YunShan_You（悠云山）

用法（在包根目录运行）：
    runtime\\python\\python.exe scripts\\setup.py
或双击 scripts\\setup.cmd，按提示输入。

只想看会改哪些文件，加 --dry-run。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "runtime" / "AstrBot-4.29.3" / "data"
BOT_PLACEHOLDER = "1000000000"
OWNER_PLACEHOLDER = "1000000001"
GROUP_PLACEHOLDER = "1000000002"
SKIP_DIRS = {
    "python", "dist", "stickers", "diary_library", "node_modules", "vendor",
    "installer", "backups", "logs", "cache", "native", "static", "worker",
    "__pycache__", "collected_stickers", ".venv",
}
SKIP_FILES = {"README.md", "NOTICE.md", "DISCLAIMER.md", "LICENSE"}
TEXT_EXT = {".py", ".pyw", ".ps1", ".cmd", ".bat", ".json", ".md", ".yaml", ".yml", ".txt"}


def ask(prompt: str, default: str = "") -> str:
    """读取一行输入，空输入时返回默认值。"""
    suffix = f"（默认 {default}）" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    return raw or default


def read_text(path: Path):
    """按 UTF-8/BOM 读取文本。"""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8"), True
    return raw.decode("utf-8"), False


def write_text(path: Path, text: str, bom: bool) -> None:
    """按原编码写回文本。"""
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    path.write_bytes(data)


def iter_targets():
    """列出需要替换占位符的文本文件。"""
    self_path = Path(__file__).resolve()
    roots = [DATA, BASE / "scripts", BASE / "assets", BASE / "backend"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if path.resolve() == self_path:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.name in SKIP_FILES or path.suffix.lower() not in TEXT_EXT:
                continue
            yield path


def validate_qq(value: str) -> str:
    """校验 QQ 号格式。"""
    if not re.fullmatch(r"\d{5,12}", value):
        raise SystemExit(f"QQ 号格式不对：{value}（应为 5-12 位数字）")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="大肥鱼 2.0 首次配置 · YunShan_You（悠云山）")
    parser.add_argument("--bot", help="机器人 QQ（要登录的小号）")
    parser.add_argument("--owner", help="主人 QQ（你自己）")
    parser.add_argument("--api", help="DeepSeek / OpenAI 兼容接口的 API Key")
    parser.add_argument("--token", help="OneBot token（可选，需和 NapCat 里填的一致）")
    parser.add_argument("--dry-run", action="store_true", help="只显示将修改的文件")
    args = parser.parse_args()

    print("大肥鱼 2.0 · 首次配置（YunShan_You / 悠云山）")
    bot = validate_qq(args.bot or ask("机器人 QQ（要登录的小号）"))
    owner = validate_qq(args.owner or ask("主人 QQ（你自己）"))
    if bot == owner:
        raise SystemExit("机器人和主人不能是同一个 QQ")
    api = args.api or ask("API Key（可先留空，之后在 cmd_config.json 里填）", "")
    token = args.token or ""

    changed = []
    for path in iter_targets():
        try:
            text, bom = read_text(path)
        except (UnicodeDecodeError, OSError):
            continue
        original = text
        text = text.replace(BOT_PLACEHOLDER, bot).replace(OWNER_PLACEHOLDER, owner)
        if token:
            text = text.replace('"ws_reverse_token": ""', f'"ws_reverse_token": "{token}"')
        if text != original:
            changed.append(str(path.relative_to(BASE)))
            if not args.dry_run:
                write_text(path, text, bom)

    cfg_path = DATA / "cmd_config.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
        if api:
            for source in cfg.get("provider_sources", []):
                source["key"] = [api]
        cfg["admins_id"] = [owner]
        if token:
            for platform in cfg.get("platform", []):
                platform["ws_reverse_token"] = token
        if not args.dry_run:
            cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        changed.append(str(cfg_path.relative_to(BASE)))
    except (OSError, ValueError) as exc:
        print(f"cmd_config.json 没改成功：{exc}")
        sys.exit(1)

    print()
    print("将修改 / 已修改：")
    for name in sorted(set(changed)):
        print("  " + name)
    print()
    if args.dry_run:
        print("（dry-run：没有真的写入）")
        return
    print("完成。")
    if not api:
        print("提醒：还没填 API Key，启动前记得在 cmd_config.json 里补。")
    if not token:
        print("提醒：OneBot token 留空也能用，但建议在 NapCat WebUI 和 cmd_config.json 里设成同一个随机值。")
    print("下一步：按 README 第 4 节安装 QQ 9.9.36，然后运行 scripts\\start.cmd。")


if __name__ == "__main__":
    main()
