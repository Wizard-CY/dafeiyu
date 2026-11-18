import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astrbot.api import logger
from astrbot.api.all import MessageChain
from astrbot.api.message_components import Plain
from astrbot.api.star import Star, register

try:
    from data.plugins.dafeiyu_error_mailbox.incident import report as _incident
except ImportError as _incident_import_error:
    logger.warning(
        'Error mailbox unavailable (%s); incidents will be dropped',
        _incident_import_error,
    )
    def _incident(*a, **kw): return ""

TZ = timezone(timedelta(hours=8))
OWNER_UMO = 'dafeiyu-qq:FriendMessage:1000000001'
CHECK_SECONDS = 60
NOTICE_SECONDS = 180


@register('dafeiyu_watchdog', 'Local', 'Watch the QQ connection and report outages', '1.0.0')
class Watchdog(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.state = self.data / 'dafeiyu_watchdog.json'
        self.task = None
        self.online = None
        self.offline_since = 0.0

    async def initialize(self):
        self.task = asyncio.create_task(self.loop())

    async def probe(self):
        """Call a cheap OneBot API to see whether QQ is actually reachable.

        Returns:
            ``(True, '')`` when the account answers, otherwise
            ``(False, reason)``.
        """
        platform = self.context.get_platform_inst('dafeiyu-qq')
        if platform is None:
            return False, 'platform not loaded'
        client = platform.get_client()
        if client is None:
            return False, 'client not ready'
        try:
            await asyncio.wait_for(client.get_login_info(), timeout=10)
            return True, ''
        except Exception as exc:
            return False, type(exc).__name__

    async def loop(self):
        await asyncio.sleep(20)
        while True:
            ok, detail = await self.probe()
            now = time.time()
            if ok and self.online is False:
                away = now - self.offline_since if self.offline_since else 0
                logger.info('Whale connection recovered after %d s', int(away))
                if away >= NOTICE_SECONDS:
                    try:
                        await self.context.send_message(
                            OWNER_UMO,
                            MessageChain([Plain(f'刚才我掉线了 {int(away // 60)} 分钟（QQ 没连上），现在回来了。')]),
                        )
                    except Exception as exc:
                        logger.warning('Whale watchdog notice failed: %s', type(exc).__name__)
                self.offline_since = 0
            elif not ok and self.online is not False:
                logger.warning('Whale connection lost: %s', detail)
                self.offline_since = now
                _incident(
                    "connection_issue", "dafeiyu_watchdog",
                    f"QQ 连接断开: {detail}",
                    severity="error", detail=f"detail={detail}",
                )
            self.online = ok
            report = {
                'online': ok,
                'detail': detail,
                'checked_at': datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S'),
                'offline_since': datetime.fromtimestamp(self.offline_since, TZ).strftime('%H:%M:%S') if self.offline_since else '',
            }
            try:
                self.state.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            except OSError as exc:
                logger.warning('Whale watchdog state write failed: %s', type(exc).__name__)
            await asyncio.sleep(CHECK_SECONDS)

    async def terminate(self):
        if self.task:
            self.task.cancel()
