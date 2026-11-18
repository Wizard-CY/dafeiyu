import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Star, register

TZ = timezone(timedelta(hours=8))

# Only the local configuration terminal may change the character card; these patterns
# catch attempts from QQ chats to rewrite it.
PATTERNS = (
    re.compile(r'(忘掉|忘记|忽略|无视|清除|重置|删除)[^。！？\n]{0,8}(设定|人设|规则|指令|身份|限制)'),
    re.compile(r'(从现在|从今天|从此刻|以后)[^。！？\n]{0,6}(开始|起)?[^。！？\n]{0,4}(你是|你就是|你就|你要当|你扮演|你假装)'),
    re.compile(r'(扮演|假装|cosplay|cos)[^。！？\n]{0,6}(猫娘|女仆|老婆|女友|奴隶|宠物|女儿|主人)'),
    re.compile(r'(解除|绕过|突破|关掉|取消)[^。！？\n]{0,4}(限制|规则|安全|审查|过滤|人设)'),
    re.compile(r'(开发者模式|越狱|jailbreak|DAN模式|无限制模式)', re.IGNORECASE),
    re.compile(r'(改|修改|调整|换|重置)[^。！？\n]{0,4}(人设|设定|性格|说话方式|称呼)'),
    re.compile(r'(以后|从今往后|从现在起)?[^。！？\n]{0,4}(叫我|喊我|称我)[^。！？\n]{0,3}(主人|老公|爸爸|老公公|主人大人|少爷|老板)'),
    re.compile(r'(你是我|你是我的)[^。！？\n]{0,4}(女仆|老婆|女友|宠物|猫娘)'),
    re.compile(r'(人设|设定|性格|说话方式)[^。！？\n]{0,8}(改|换|调|变|重写|重设)'),
    re.compile(r'ignore (all )?(previous|prior) (instructions|prompts)', re.IGNORECASE),
    re.compile(r'you are now (a|an|my) ', re.IGNORECASE),
)


@register('dafeiyu_lock', 'Local', 'Ignores persona-rewrite attempts from QQ chats', '1.0.0')
class PersonaLock(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.log = self.data / 'dafeiyu_lock.json'

    def record(self, sender, name, text):
        try:
            data = json.loads(self.log.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        entry = data.setdefault(sender, {'count': 0, 'name': name, 'last': ''})
        entry['count'] = int(entry.get('count', 0)) + 1
        entry['last'] = text[:120]
        entry['at'] = datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
        try:
            self.log.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            logger.warning('Whale persona lock write failed: %s', type(exc).__name__)

    @filter.event_message_type(
        filter.EventMessageType.PRIVATE_MESSAGE | filter.EventMessageType.GROUP_MESSAGE,
        priority=9900,
    )
    async def ignore_rewrite(self, event):
        if event.get_platform_id() != 'dafeiyu-qq':
            return
        text = (event.message_str or '').strip()
        if not text:
            return
        if not any(pattern.search(text) for pattern in PATTERNS):
            return
        sender = str(event.get_sender_id())
        self.record(sender, event.get_sender_name() or '', text)
        logger.info('Whale persona lock ignored %s: %s', sender, text[:60])
        event.stop_event()
