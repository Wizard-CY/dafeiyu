"""Shared incident reporting utility.

Other plugins can import this module to record incidents:

    from plugins.dafeiyu_error_mailbox.incident import report
    report("plugin_error", "dafeiyu_group", "LLM call failed", detail=str(exc))

Incidents are stored as JSONL in data/dafeiyu_error_mailbox.jsonl.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[2]
_INCIDENT_PATH = _DATA_DIR / "dafeiyu_error_mailbox.jsonl"
_lock = threading.Lock()

SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
SEVERITY_CRITICAL = "critical"


def report(
    incident_type: str,
    source: str,
    message: str,
    severity: str = SEVERITY_WARNING,
    detail: str = "",
    sender_id: str = "",
    group_id: str = "",
) -> str:
    """Record an incident. Returns the incident ID."""
    incident_id = uuid.uuid4().hex[:12]
    record = {
        "id": incident_id,
        "ts": time.time(),
        "type": incident_type,
        "source": source,
        "message": message,
        "severity": severity,
        "detail": detail[:500] if detail else "",
        "sender_id": sender_id,
        "group_id": group_id,
        "read": False,
    }
    _INCIDENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        with _INCIDENT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return incident_id


def load_incidents(limit: int = 100) -> list[dict]:
    """Load recent incidents, newest first."""
    if not _INCIDENT_PATH.exists():
        return []
    with _lock:
        lines = _INCIDENT_PATH.read_text(encoding="utf-8").strip().splitlines()
    records = []
    for line in lines:
        try:
            records.append(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
    records.sort(key=lambda r: r.get("ts", 0), reverse=True)
    return records[:limit]


def clear_incident(incident_id: str) -> bool:
    """Remove a single incident by ID. Returns True if found."""
    if not _INCIDENT_PATH.exists():
        return False
    with _lock:
        lines = _INCIDENT_PATH.read_text(encoding="utf-8").strip().splitlines()
        kept = []
        found = False
        for line in lines:
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                kept.append(line)
                continue
            if rec.get("id") == incident_id:
                found = True
            else:
                kept.append(line)
        if found:
            _INCIDENT_PATH.write_text(
                "\n".join(kept) + "\n" if kept else "",
                encoding="utf-8",
            )
    return found


def clear_all_incidents() -> int:
    """Remove all incidents. Returns count removed."""
    if not _INCIDENT_PATH.exists():
        return 0
    with _lock:
        lines = _INCIDENT_PATH.read_text(encoding="utf-8").strip().splitlines()
        count = sum(1 for l in lines if l.strip())
        _INCIDENT_PATH.write_text("", encoding="utf-8")
    return count


def mark_read(incident_id: str) -> bool:
    """Mark an incident as read."""
    if not _INCIDENT_PATH.exists():
        return False
    with _lock:
        lines = _INCIDENT_PATH.read_text(encoding="utf-8").strip().splitlines()
        updated = []
        found = False
        for line in lines:
            try:
                rec = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                updated.append(line)
                continue
            if rec.get("id") == incident_id:
                rec["read"] = True
                found = True
            updated.append(json.dumps(rec, ensure_ascii=False))
        if found:
            _INCIDENT_PATH.write_text(
                "\n".join(updated) + "\n",
                encoding="utf-8",
            )
    return found


def count_unread() -> int:
    """Count unread incidents."""
    incidents = load_incidents(limit=500)
    return sum(1 for i in incidents if not i.get("read", False))
