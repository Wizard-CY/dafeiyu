"""Error mailbox plugin — collects and displays incidents in the dashboard.

Incident types:
- defense_trigger: guard blocked a sender
- plugin_error: plugin exception prevented normal response
- llm_failure: LLM API call failed
- content_guard: reply was modified by privacy/tech-talk guard
- connection_issue: watchdog detected offline period

Provides REST APIs for the dashboard view and a shared incident module
that other plugins can import to report incidents.
"""

from __future__ import annotations

from astrbot.api.star import Star, register
from astrbot.api.web import request

from . import incident

PLUGIN_NAME = "dafeiyu_error_mailbox"


@register(PLUGIN_NAME, "Local", "Error mailbox for incident tracking", "1.0.0")
class ErrorMailboxPlugin(Star):
    def __init__(self, context):
        super().__init__(context)

    async def initialize(self):
        self.context.register_web_api(
            f"/{PLUGIN_NAME}/incidents",
            self.get_incidents,
            ["GET"],
            "List recent incidents",
        )
        self.context.register_web_api(
            f"/{PLUGIN_NAME}/unread_count",
            self.get_unread_count,
            ["GET"],
            "Count unread incidents",
        )
        self.context.register_web_api(
            f"/{PLUGIN_NAME}/mark_read",
            self.mark_read,
            ["POST"],
            "Mark an incident as read",
        )
        self.context.register_web_api(
            f"/{PLUGIN_NAME}/clear",
            self.clear_incident,
            ["GET"],
            "Remove a single incident",
        )
        self.context.register_web_api(
            f"/{PLUGIN_NAME}/clear_all",
            self.clear_all,
            ["GET"],
            "Remove all incidents",
        )

    async def terminate(self):
        routes = self.context.registered_web_apis
        routes[:] = [
            route for route in routes
            if not (route[0].startswith(f"/{PLUGIN_NAME}") and getattr(route[1], "__self__", None) is self)
        ]

    async def get_incidents(self):
        try:
            limit = max(1, min(500, int(request.query.get("limit", "100"))))
        except (TypeError, ValueError):
            limit = 100
        return {"incidents": incident.load_incidents(limit=limit)}

    async def get_unread_count(self):
        return {"count": incident.count_unread()}

    async def mark_read(self):
        body = await request.json(default=None)
        if not isinstance(body, dict):
            return {"success": False, "error": "Invalid JSON"}
        incident_id = body.get("id", "")
        if not incident_id:
            return {"success": False, "error": "Missing id"}
        ok = incident.mark_read(incident_id)
        return {"success": ok}

    async def clear_incident(self):
        incident_id = request.query.get("id", "")
        if not incident_id:
            return {"success": False, "error": "Missing id"}
        ok = incident.clear_incident(incident_id)
        return {"success": ok}

    async def clear_all(self):
        count = incident.clear_all_incidents()
        return {"success": True, "cleared": count}
