import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Star, register

from ..dafeiyu_group.helper import format_search, needs_search, search_query, web_search

TZ = timezone(timedelta(hours=8))
DAILY_CAP = 40


@register('dafeiyu_search', 'Local', 'Web search on explicit request (private chats)', '1.0.0')
class WebSearch(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.count_file = self.data / 'dafeiyu_search_count.json'

    def day_count(self):
        try:
            data = json.loads(self.count_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return 0
        today = datetime.now(TZ).date().isoformat()
        return int(data.get('count', 0)) if data.get('day') == today else 0

    def bump(self):
        today = datetime.now(TZ).date().isoformat()
        try:
            self.count_file.write_text(json.dumps({'day': today, 'count': self.day_count() + 1}), encoding='utf-8')
        except OSError as exc:
            logger.warning('Whale search count write failed: %s', type(exc).__name__)

    @filter.on_llm_request()
    async def inject(self, event, req):
        if event.get_platform_id() != 'dafeiyu-qq':
            return
        if event.get_group_id():
            return
        text = getattr(event, 'message_str', '') or ''
        if not needs_search(text):
            return
        query = search_query(text)
        if not query:
            req.system_prompt = (req.system_prompt or '') + '\n# 对方让你联网，但没说搜什么：问一句要查什么，不要瞎编结果。'
            return
        if self.day_count() >= DAILY_CAP:
            return
        results = await asyncio.to_thread(web_search, query)
        block = format_search(results)
        if block:
            req.system_prompt = (req.system_prompt or '') + '\n' + block
            self.bump()
            logger.info('Whale private web search: %s -> %d results', query, len(results))
        else:
            req.system_prompt = (req.system_prompt or '') + '\n# 联网没搜到结果：老实说没查到，不要编。'
