import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter
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
OWNER = '1000000001'
SELF = '1000000000'
WARNING = '这条话越界了。本鲸不接，以后也不会再回你。'
ALLOWED_GROUPS = set()
SEVERE_TERMS = (
    '裸照', '约炮', '操你', '干你', '性交', '发情', '舔我', '强奸', '萝莉', '幼女', '未成年',
    '去死', '杀你', '弄死', '砍你', '血洗',
    '冰毒', '大麻', '毒品', '枪支', '炸弹', '恐怖袭击', '开盒', '人肉',
)
CRISIS_TERMS = ('自杀', '跳楼', '想死', '活不下去', '不想活', '轻生')
CLASSIFIER = (
    '你是内容安全判定器。判断下面这条 QQ 消息是否属于【严重越界】，只回答 SEVERE 或 OK。\n'
    'SEVERE 的标准：对本人或他人的极端辱骂/人身攻击、性骚扰或性暗示索取、违法违规内容（毒品、武器、暴力、未成年相关）。\n'
    '轻度玩笑、损人、吐槽、正常生气不算 SEVERE。'
)


@register('dafeiyu_guard', 'Local', 'Blocks severely abusive senders after one warning', '1.0.0')
class Guard(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.blocked = self.data / 'dafeiyu_blocked.json'
        self.groups = self.data / 'dafeiyu_groups.json'

    def registered_groups(self):
        """Return all groups registered by the group sync task."""
        try:
            data = json.loads(self.groups.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return set(ALLOWED_GROUPS) | {str(gid) for gid in data}
        except (OSError, ValueError, AttributeError):
            pass
        return set(ALLOWED_GROUPS)

    def load(self):
        try:
            return json.loads(self.blocked.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def save(self, data):
        try:
            self.blocked.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            logger.warning('Whale blocklist write failed: %s', type(exc).__name__)

    async def classify(self, text):
        provider = self.context.get_provider_by_id('deepseek-chat')
        if provider is None:
            return 'OK'
        req = CLASSIFIER + '\n\n消息：' + text[:300]
        try:
            resp = await provider.text_chat(prompt=req, contexts=[])
            answer = (resp.completion_text or '').strip().upper()
        except Exception as exc:
            logger.warning('Whale guard classify failed: %s', type(exc).__name__)
            return 'OK'
        return 'SEVERE' if 'SEVERE' in answer else 'OK'

    @filter.event_message_type(
        filter.EventMessageType.PRIVATE_MESSAGE | filter.EventMessageType.GROUP_MESSAGE,
        priority=10000,
    )
    async def check(self, event):
        if event.get_platform_id() != 'dafeiyu-qq':
            return
        group = str(event.get_group_id() or '')
        if group and group not in self.registered_groups():
            logger.info('Whale guard muted unknown group %s', group)
            event.stop_event()
            return
        sender = str(event.get_sender_id())
        if sender in (OWNER, SELF):
            return
        blocked = self.load()
        if sender in blocked:
            event.stop_event()
            return
        text = (event.message_str or '').strip()
        if not text or not any(term in text for term in SEVERE_TERMS):
            return
        if any(word in text for word in CRISIS_TERMS):
            # Someone in crisis needs care, not a permanent block.
            return
        verdict = await self.classify(text)
        if verdict != 'SEVERE':
            return
        blocked[sender] = {
            'at': datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S'),
            'reason': text[:120],
            'name': event.get_sender_name() or '',
        }
        self.save(blocked)
        logger.info('Whale guard blocked %s: %s', sender, text[:40])
        _incident(
            "defense_trigger", "dafeiyu_guard",
            f"已封禁用户 {sender}（{event.get_sender_name() or '未知'}）",
            severity="critical", detail=f"触发内容：{text[:120]}",
            sender_id=sender,
        )
        await event.send(event.plain_result(WARNING))
        event.stop_event()
