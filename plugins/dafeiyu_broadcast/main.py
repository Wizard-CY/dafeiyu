"""Broadcast plugin - send messages to selected friends or groups.

Provides a dashboard view for composing and sending messages to
multiple private chat users or group chats at once.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.all import MessageChain
from astrbot.api.message_components import Plain
from astrbot.api.star import Star, register
from astrbot.api.web import request

PLUGIN_NAME = "dafeiyu_broadcast"


@register(PLUGIN_NAME, "Local", "Send broadcast messages to friends or groups", "1.0.0")
class BroadcastPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.friends_path = self.data / "dafeiyu_friends.json"
        self.groups_path = self.data / "dafeiyu_groups.json"
        self.controls_path = self.data / "dafeiyu_group_controls.json"

    async def initialize(self):
        self.request_path = self.data / "dafeiyu_broadcast_request.json"
        self.result_path = self.data / "dafeiyu_broadcast_result.json"
        self.context.register_web_api(
            f"/{PLUGIN_NAME}/targets",
            self.get_targets,
            ["GET"],
            "List available broadcast targets",
        )
        self.context.register_web_api(
            f"/{PLUGIN_NAME}/send",
            self.send_broadcast,
            ["POST"],
            "Send broadcast message",
        )
        self._watch_task = asyncio.create_task(self._watch_requests())

    async def terminate(self):
        task = getattr(self, "_watch_task", None)
        if task:
            task.cancel()
        routes = self.context.registered_web_apis
        routes[:] = [
            route for route in routes
            if not (route[0].startswith(f"/{PLUGIN_NAME}") and getattr(route[1], "__self__", None) is self)
        ]

    async def _watch_requests(self):
        """Run broadcasts requested by the control center through a drop file."""
        await asyncio.sleep(3)
        while True:
            try:
                if self.request_path.exists():
                    payload = json.loads(self.request_path.read_text(encoding="utf-8"))
                    self.request_path.unlink(missing_ok=True)
                    if isinstance(payload, dict):
                        await self._run_broadcast(payload)
            except Exception as exc:
                logger.warning("Broadcast request failed: %s", type(exc).__name__)
            await asyncio.sleep(1.5)

    async def _run_broadcast(self, payload):
        """Send one queued broadcast and record the per-target result."""
        message = str(payload.get("message") or "").strip()
        targets = payload.get("targets") or []
        request_id = str(payload.get("request_id") or "")
        results = []
        if message:
            chain = MessageChain([Plain(message)])
            for target in targets:
                target_id = str(target.get("id", ""))
                kind = str(target.get("type", ""))
                if not target_id or kind not in ("friend", "group"):
                    results.append({"id": target_id, "success": False, "error": "Invalid target"})
                    continue
                session = "FriendMessage" if kind == "friend" else "GroupMessage"
                uo = f"dafeiyu-qq:{session}:{target_id}"
                try:
                    ok = await self.context.send_message(uo, chain)
                    results.append({"id": target_id, "type": kind, "success": bool(ok)})
                except Exception as exc:
                    results.append({"id": target_id, "type": kind, "success": False,
                                    "error": type(exc).__name__})
        sent = sum(1 for item in results if item.get("success"))
        report = {
            "request_id": request_id,
            "sent": sent,
            "total": len(targets),
            "results": results,
            "finished_at": time.time(),
            "error": "" if message else "消息为空",
        }
        try:
            self.result_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Broadcast result write failed: %s", type(exc).__name__)
        logger.info("Broadcast from control center: %d/%d", sent, len(targets))

    def _load_json(self, path: Path, default=None):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return default if default is not None else {}

    async def get_targets(self):
        friends_raw = self._load_json(self.friends_path, {})
        groups_raw = self._load_json(self.groups_path, {})
        controls_raw = self._load_json(self.controls_path, {})

        friends = []
        if isinstance(friends_raw, dict):
            for fid, info in friends_raw.items():
                if isinstance(info, dict):
                    name = (
                        info.get("remark")
                        or info.get("nick")
                        or info.get("name")
                        or info.get("nickname")
                        or fid
                    )
                else:
                    name = fid
                friends.append({"id": str(fid), "name": str(name), "type": "friend"})

        groups = []
        if isinstance(groups_raw, dict):
            for gid, info in groups_raw.items():
                name = info.get("name") or info.get("original") or gid if isinstance(info, dict) else gid
                enabled = controls_raw.get(str(gid), True) if isinstance(controls_raw, dict) else True
                groups.append({
                    "id": str(gid),
                    "name": str(name),
                    "type": "group",
                    "enabled": bool(enabled),
                })

        return {"friends": friends, "groups": groups}

    async def send_broadcast(self):
        body = await request.json(default=None)
        if not isinstance(body, dict):
            return {"success": False, "error": "Invalid JSON body"}

        targets = body.get("targets", [])
        message = (body.get("message") or "").strip()

        if not targets:
            return {"success": False, "error": "No targets selected"}
        if not message:
            return {"success": False, "error": "Message is empty"}

        results = []
        chain = MessageChain([Plain(message)])

        for target in targets:
            target_id = str(target.get("id", ""))
            target_type = target.get("type", "")

            if target_type == "friend":
                uo = f"dafeiyu-qq:FriendMessage:{target_id}"
            elif target_type == "group":
                uo = f"dafeiyu-qq:GroupMessage:{target_id}"
            else:
                results.append({"id": target_id, "success": False, "error": "Unknown type"})
                continue

            try:
                ok = await self.context.send_message(uo, chain)
                results.append({"id": target_id, "success": ok})
            except Exception as exc:
                logger.warning("Broadcast send failed for %s: %s", uo, type(exc).__name__)
                results.append({"id": target_id, "success": False, "error": str(exc)})

        sent = sum(1 for r in results if r.get("success"))
        return {"success": True, "sent": sent, "total": len(results), "results": results}
