import random
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Star, register

NOTICE_GAP = 1800
LINES = ('语音听不了 你打字呗', '我这边听不了语音 打字说吧', '耳朵不好使 打字吧')


@register('dafeiyu_hearing', 'Local', 'Tell people once that voice messages cannot be heard', '1.0.0')
class Hearing(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.last_notice = {}

    def quiet(self):
        """Return whether the scheduled silent window is active.

        Returns:
            Always False; the bot stays available around the clock.
        """
        return False

    @filter.event_message_type(
        filter.EventMessageType.PRIVATE_MESSAGE | filter.EventMessageType.GROUP_MESSAGE,
        priority=9700,
    )
    async def notice(self, event):
        if event.get_platform_id() != 'dafeiyu-qq':
            return
        parts = event.get_messages()
        if not any(type(part).__name__ == 'Record' for part in parts):
            return
        if event.get_group_id() and self.quiet():
            return
        key = event.unified_msg_origin
        now = time.time()
        if now - self.last_notice.get(key, 0) < NOTICE_GAP:
            return
        self.last_notice[key] = now
        await event.send(event.plain_result(random.choice(LINES)))
        event.stop_event()
        logger.info('Whale voice notice sent')
