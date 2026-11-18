"""Friend cleaner: idle-friend cleanup, whitelist and chat archiving.

The control center lists friends with no incoming private message for five
days.  Only friends the owner confirms (and that are not whitelisted) are
removed through the OneBot ``delete_friend`` action.  Before removal their
conversation, memory and relationship profile are copied to
``data/friend_archive/<qq>/`` for mirror-only training, then removed from the
production data.  New messages from a re-added friend are observed again.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Star, register

PLUGIN_NAME = "dafeiyu_friend_cleaner"
OWNER = "1000000001"
SELF = "1000000000"
IDLE_SECONDS = 5 * 24 * 3600
SCAN_INTERVAL = 6 * 3600
TZ = timezone(timedelta(hours=8))


def _now_text() -> str:
    """Return the local timestamp used in metadata files."""
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


def _read_json(path: Path, default):
    """Read a JSON file and fall back to a default on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    """Write JSON atomically so readers never see a partial file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
    except OSError as exc:
        logger.warning("Friend cleaner write failed for %s: %s", path.name, type(exc).__name__)


@register(PLUGIN_NAME, "Local", "5 天未联系好友清理、白名单与聊天封存", "1.1.0")
class FriendCleaner(Star):
    """Track friend activity, archive removed friends and honour a whitelist."""

    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.friends_path = self.data / "dafeiyu_friends.json"
        self.activity_path = self.data / "dafeiyu_friend_activity.json"
        self.state_path = self.data / "dafeiyu_friend_activity_state.json"
        self.whitelist_path = self.data / "dafeiyu_friend_whitelist.json"
        self.scan_request = self.data / "dafeiyu_friend_scan_request.json"
        self.clean_request = self.data / "dafeiyu_friend_clean_request.json"
        self.clean_result = self.data / "dafeiyu_friend_clean_result.json"
        self.archive_dir = self.data / "friend_archive"
        self.db_path = self.data / "data_v4.db"
        self._scan_lock = asyncio.Lock()
        self._clean_lock = asyncio.Lock()
        self._tasks: list[asyncio.Task] = []

    async def initialize(self) -> None:
        """Create the whitelist, start the watcher and schedule one scan."""
        self._ensure_whitelist()
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self._tasks.append(asyncio.create_task(self._watch_requests()))
        self._tasks.append(asyncio.create_task(self._scan_loop()))

    async def terminate(self) -> None:
        """Cancel background tasks."""
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE, priority=1)
    async def on_private_message(self, event) -> None:
        """Record the latest incoming message time for one friend."""
        if event.get_platform_id() != "dafeiyu-qq":
            return
        sender = str(event.get_sender_id())
        if sender in (OWNER, SELF):
            return
        text = str(getattr(event, "message_str", "") or "").strip()
        activity = _read_json(self.activity_path, {})
        if not isinstance(activity, dict):
            activity = {}
        entry = activity.get(sender) if isinstance(activity.get(sender), dict) else {}
        entry.update({
            "last_user_at": time.time(),
            "last_text": text[:60],
            "name": str(event.get_sender_name() or entry.get("name") or ""),
        })
        activity[sender] = entry
        _write_json(self.activity_path, activity)
        self._mark_re_added(sender)

    def _ensure_whitelist(self) -> None:
        """Create the whitelist and always keep the owner on it."""
        data = _read_json(self.whitelist_path, None)
        if not isinstance(data, dict):
            data = {}
        if OWNER not in data:
            data[OWNER] = {"name": "主人", "at": _now_text()}
        _write_json(self.whitelist_path, data)

    def _mark_re_added(self, qq: str) -> None:
        """Stamp an archived friend when a new message proves a re-add."""
        folder = self.archive_dir / qq
        meta_path = folder / "meta.json"
        if not meta_path.exists():
            return
        meta = _read_json(meta_path, {})
        if not isinstance(meta, dict) or meta.get("re_added_at"):
            return
        meta["re_added_at"] = _now_text()
        _write_json(meta_path, meta)
        logger.info("Friend cleaner: archived friend %s re-added", qq)

    async def _client(self):
        """Return the aiocqhttp client, waiting briefly for connection."""
        for _ in range(8):
            try:
                platform = self.context.get_platform_inst("dafeiyu-qq")
                getter = getattr(platform, "get_client", None)
                bot = getter() if callable(getter) else None
                if bot is not None:
                    return bot
            except Exception:
                pass
            await asyncio.sleep(2)
        return None

    async def _watch_requests(self) -> None:
        """Poll scan and cleanup drop files written by the control center."""
        await asyncio.sleep(3)
        while True:
            try:
                if self.scan_request.exists():
                    payload = _read_json(self.scan_request, {})
                    try:
                        self.scan_request.unlink()
                    except OSError:
                        pass
                    reason = str(payload.get("reason") or "request") if isinstance(payload, dict) else "request"
                    asyncio.create_task(self.scan_all(reason))
                if self.clean_request.exists():
                    payload = _read_json(self.clean_request, {})
                    try:
                        self.clean_request.unlink()
                    except OSError:
                        pass
                    if isinstance(payload, dict):
                        await self.clean_friends(payload)
            except Exception as exc:
                logger.warning("Friend cleaner watcher failed: %s", type(exc).__name__)
            await asyncio.sleep(1.5)

    async def _scan_loop(self) -> None:
        """Scan activity shortly after start, then every six hours."""
        await asyncio.sleep(25)
        while True:
            state = _read_json(self.state_path, {})
            last = float((state or {}).get("last_scan_at") or 0)
            if time.time() - last > SCAN_INTERVAL:
                await self.scan_all("periodic")
            await asyncio.sleep(600)

    async def scan_all(self, reason: str = "manual") -> None:
        """Scan every friend's history and update the activity index."""
        if self._scan_lock.locked():
            return
        async with self._scan_lock:
            friends = _read_json(self.friends_path, {})
            if not isinstance(friends, dict):
                friends = {}
            activity = _read_json(self.activity_path, {})
            if not isinstance(activity, dict):
                activity = {}
            _write_json(self.state_path, {
                "running": True, "last_scan_at": float((_read_json(self.state_path, {}) or {}).get("last_scan_at") or 0),
                "scanned": 0, "total": len(friends), "error": "", "reason": reason, "started_at": time.time(),
            })
            bot = await self._client()
            if bot is None:
                _write_json(self.state_path, {
                    "running": False, "last_scan_at": 0, "scanned": 0,
                    "total": len(friends), "error": "QQ 未连接", "reason": reason,
                })
                return
            # Drop friends that were deleted elsewhere (or removed in an earlier
            # cleanup) so the control center does not keep offering ghosts.
            try:
                live = await asyncio.wait_for(bot.get_friend_list(), timeout=20)
            except Exception:
                live = None
            if isinstance(live, list) and live:
                live_ids = {str(item.get("user_id")) for item in live if isinstance(item, dict)}
                stale = [qq for qq in friends if qq not in live_ids and qq != SELF]
                for qq in stale:
                    friends.pop(qq, None)
                if stale:
                    _write_json(self.friends_path, friends)
                    logger.info("Friend cleaner pruned %d stale friend(s)", len(stale))
            semaphore = asyncio.Semaphore(4)
            counter = {"done": 0}

            async def scan_one(qq: str) -> None:
                """Read one friend's recent history for the newest incoming time."""
                async with semaphore:
                    latest, text = 0.0, ""
                    try:
                        history = await bot.call_action(
                            action="get_friend_msg_history", user_id=int(qq), count=10)
                        messages = history.get("messages") if isinstance(history, dict) else None
                        if messages is None and isinstance(history, dict):
                            messages = (history.get("data") or {}).get("messages")
                        if isinstance(messages, list):
                            for message in messages:
                                if not isinstance(message, dict):
                                    continue
                                sender = str((message.get("sender") or {}).get("user_id") or "")
                                if sender != qq:
                                    continue
                                stamp = float(message.get("time") or 0)
                                if stamp > latest:
                                    latest = stamp
                                    chain = message.get("message")
                                    if isinstance(chain, list):
                                        for part in chain:
                                            if isinstance(part, dict) and part.get("type") == "text":
                                                text = str((part.get("data") or {}).get("text") or "")[:60]
                                                break
                    except Exception as exc:
                        logger.info("Friend cleaner history failed for %s: %s", qq, type(exc).__name__)
                    entry = activity.get(qq) if isinstance(activity.get(qq), dict) else {}
                    if latest:
                        entry["last_user_at"] = latest
                        entry["last_text"] = text
                    entry["checked_at"] = time.time()
                    info = friends.get(qq) if isinstance(friends.get(qq), dict) else {}
                    entry["name"] = str(info.get("remark") or info.get("nick") or entry.get("name") or "")
                    activity[qq] = entry
                    counter["done"] += 1
                    if counter["done"] % 10 == 0:
                        _write_json(self.state_path, {
                            "running": True,
                            "last_scan_at": float((_read_json(self.state_path, {}) or {}).get("last_scan_at") or 0),
                            "scanned": counter["done"], "total": len(friends),
                            "error": "", "reason": reason, "started_at": time.time(),
                        })

            await asyncio.gather(*(scan_one(str(qq)) for qq in friends if str(qq) != SELF))
            current = _read_json(self.activity_path, {})
            if not isinstance(current, dict):
                current = {}
            for qq, entry in activity.items():
                old = current.get(qq) if isinstance(current.get(qq), dict) else {}
                if float(old.get("last_user_at") or 0) > float(entry.get("last_user_at") or 0):
                    entry["last_user_at"] = old["last_user_at"]
                    entry["last_text"] = old.get("last_text") or entry.get("last_text") or ""
                if old.get("name") and not entry.get("name"):
                    entry["name"] = old["name"]
                current[qq] = entry
            _write_json(self.activity_path, current)
            _write_json(self.state_path, {
                "running": False, "last_scan_at": time.time(), "scanned": counter["done"],
                "total": len(friends), "error": "", "reason": reason,
            })
            logger.info("Friend cleaner scanned %d friend(s): %s", counter["done"], reason)

    async def clean_friends(self, payload: dict) -> None:
        """Delete the requested friends, archive their data and report results.

        A delete call is only counted after the live friend list no longer
        contains the QQ; accepted-but-ignored calls are retried a few times.
        """
        if self._clean_lock.locked():
            return
        async with self._clean_lock:
            request_id = str(payload.get("request_id") or "")
            requested = [str(qq) for qq in (payload.get("qqs") or []) if str(qq).strip()]
            if not requested:
                # A half-written request (or a stray file) must not wipe the
                # previous result and leave the control center waiting.
                logger.warning("Friend cleaner ignored an empty clean request")
                return
            friends = _read_json(self.friends_path, {})
            if not isinstance(friends, dict):
                friends = {}
            whitelist = _read_json(self.whitelist_path, {})
            if not isinstance(whitelist, dict):
                whitelist = {}
            activity = _read_json(self.activity_path, {})
            if not isinstance(activity, dict):
                activity = {}
            bot = await self._client()
            deleted, skipped, failed = [], [], []
            if bot is None:
                _write_json(self.clean_result, {
                    "request_id": request_id, "requested": len(requested), "deleted": [],
                    "skipped": [{"qq": qq, "reason": "QQ 未连接"} for qq in requested],
                    "failed": [], "finished_at": time.time(),
                })
                return
            for qq in requested:
                if qq in (OWNER, SELF):
                    skipped.append({"qq": qq, "reason": "主人或机器人"})
                    continue
                if qq in whitelist:
                    skipped.append({"qq": qq, "reason": "白名单"})
                    continue
                info = friends.get(qq) if isinstance(friends.get(qq), dict) else None
                if info is None:
                    skipped.append({"qq": qq, "reason": "已不是好友"})
                    continue
                entry = activity.get(qq) if isinstance(activity.get(qq), dict) else {}
                reference = float(entry.get("last_user_at") or info.get("added_at") or 0)
                if not reference or time.time() - reference < IDLE_SECONDS:
                    skipped.append({"qq": qq, "reason": "最近有消息"})
                    continue
                # QQ may acknowledge delete_friend while silently ignoring it
                # (observed when several friends are removed in one burst), so
                # every call is checked against the live friend list and retried.
                error = ""
                for attempt in range(3):
                    error = ""
                    try:
                        reply = await asyncio.wait_for(
                            bot.call_action(action="delete_friend", user_id=int(qq)), timeout=30)
                    except Exception as exc:
                        error = type(exc).__name__
                    else:
                        if isinstance(reply, dict):
                            if reply.get("valid") is False:
                                error = str(reply.get("message") or "接口拒绝")
                            elif reply.get("result") not in (None, 0):
                                error = "result=%s %s" % (
                                    reply.get("result"), reply.get("errMsg") or "")
                    await asyncio.sleep(2.0)
                    try:
                        live = await asyncio.wait_for(bot.get_friend_list(), timeout=20)
                    except Exception:
                        live = None
                    if isinstance(live, list):
                        ids = {str(item.get("user_id")) for item in live if isinstance(item, dict)}
                        if qq not in ids:
                            error = ""
                            break
                        error = error or "删除后仍在好友列表"
                    elif not error:
                        # No list to verify against: trust the accepted reply.
                        break
                    await asyncio.sleep(2.0 + attempt)
                if error:
                    logger.warning("Friend cleaner delete failed for %s: %s", qq, error)
                    failed.append({"qq": qq, "error": error})
                    continue
                name = str(info.get("remark") or info.get("nick") or entry.get("name") or qq)
                self._archive(qq, name, info, entry)
                friends.pop(qq, None)
                _write_json(self.friends_path, friends)
                deleted.append({"qq": qq, "name": name})
                await asyncio.sleep(1.0)
            _write_json(self.friends_path, friends)
            _write_json(self.clean_result, {
                "request_id": request_id,
                "requested": len(requested),
                "deleted": deleted,
                "skipped": skipped,
                "failed": failed,
                "finished_at": time.time(),
            })
            logger.info("Friend cleaner removed %d/%d friend(s)", len(deleted), len(requested))

    def _archive(self, qq: str, name: str, info: dict, activity: dict) -> None:
        """Copy one friend's conversation, memory and profile to the archive."""
        folder = self.archive_dir / qq
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("Friend cleaner archive mkdir failed: %s", type(exc).__name__)
            return
        user_id = "dafeiyu-qq:FriendMessage:" + qq
        try:
            with sqlite3.connect(self.db_path, timeout=3) as db:
                row = db.execute(
                    "SELECT content FROM conversations WHERE user_id = ?", (user_id,)).fetchone()
                if row and row[0]:
                    (folder / "conversation.json").write_text(str(row[0]), encoding="utf-8")
                db.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
                db.commit()
        except sqlite3.Error as exc:
            logger.warning("Friend cleaner conversation archive failed: %s", type(exc).__name__)
        for source, target in (
            (self.data / "memory" / ("friend_" + qq + ".md"), "memory.md"),
            (self.data / "profiles" / ("friend_" + qq + ".md"), "profile.md"),
            (self.data / "profiles" / "published" / ("friend_" + qq + ".md"), "profile_published.md"),
        ):
            if not source.exists():
                continue
            try:
                shutil.copy2(source, folder / target)
                source.unlink()
            except OSError as exc:
                logger.warning("Friend cleaner archive copy failed: %s", type(exc).__name__)
        meta = {
            "qq": qq,
            "name": name,
            "removed_at": _now_text(),
            "last_user_at": float(activity.get("last_user_at") or 0),
            "added_at": float(info.get("added_at") or 0),
            "nick": str(info.get("nick") or ""),
            "remark": str(info.get("remark") or ""),
            "re_added_at": "",
            "note": "只用于镜像版本训练；生产侧不再读取",
        }
        _write_json(folder / "meta.json", meta)
        try:
            with (self.archive_dir / "index.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(meta, ensure_ascii=False) + "\n")
        except OSError:
            pass
