import asyncio
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from data.dafeiyu_state import transaction, enqueue, claim_notice, finish_notice, recover_notices

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Star, register

TZ = timezone(timedelta(hours=8))
OWNER = '1000000001'
SELF = '1000000000'
DAILY_LIMIT = 75
NEW_FRIEND_GRACE = 5 * 60
CRISIS_TERMS = ('自杀', '跳楼', '想死', '活不下去', '不想活', '轻生')
NOTICE = '（备注：每天最多聊 75 条，聊满了明天再来。）'
EXHAUSTED = '今天跟你聊满 75 条啦 再说下去我就要断粮了 明天再来找我吧'


STATE_PATH = Path(__file__).resolve().parents[2] / 'dafeiyu_quota.json'


def add_sent(qq, amount=1):
    """Count actually delivered private items for one friend.

    Args:
        qq: Friend QQ number.
        amount: Number of delivered items (text/image/voice/music).
    """
    if str(qq) == OWNER or int(amount) <= 0:
        return
    today = datetime.now(TZ).date().isoformat()
    with transaction(STATE_PATH) as data:
        entry = data.get(str(qq)) or {}
        if entry.get('day') != today:
            entry = {'day': today, 'count': 0, 'notified': False, 'exhausted': False}
        entry['count'] = int(entry.get('count', 0)) + int(amount)
        entry['notified'] = True
        data[str(qq)] = entry


@register('dafeiyu_quota', 'Local', 'Per-friend daily reply quota for non-owners', '1.0.0')
class Quota(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.state = self.data / 'dafeiyu_quota.json'
        self.friends = self.data / 'dafeiyu_friends.json'
        self.config = self.data / 'dafeiyu_quota_config.json'
        self.task = None
        self.outbox = self.data / 'dafeiyu_private_outbox.json'
        self.pending = self.data / 'dafeiyu_pending_friends.json'
        self.outbox_task = None

    def limits(self):
        """Read the daily limit and grace window, falling back to defaults.

        Returns:
            A (daily_limit, grace_seconds) tuple.
        """
        try:
            path = getattr(self, 'config', None) or (self.data / 'dafeiyu_quota_config.json')
            cfg = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError, AttributeError):
            cfg = {}
        limit = int(cfg.get('daily_limit') or DAILY_LIMIT)
        raw_grace = cfg.get('grace_minutes')
        grace = int(raw_grace if raw_grace is not None else (NEW_FRIEND_GRACE // 60)) * 60
        return limit, grace

    def limit_for(self, qq):
        """Return the effective daily limit for one friend.

        Args:
            qq: Friend QQ number.

        Returns:
            The per-user override, or the global daily limit.
        """
        limit, _ = self.limits()
        try:
            path = getattr(self, 'config', None) or (self.data / 'dafeiyu_quota_config.json')
            cfg = json.loads(path.read_text(encoding='utf-8'))
            override = (cfg.get('per_user') or {}).get(str(qq))
            if override is not None:
                return max(1, int(override))
        except (OSError, ValueError, AttributeError, TypeError):
            pass
        return limit

    async def initialize(self):
        self.task = asyncio.create_task(self.watch_friends())
        self.outbox_task = asyncio.create_task(self.watch_outbox())

    def load_state(self):
        try:
            return json.loads(self.state.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def save_state(self, data):
        """Merge gate metadata without replacing delivery counters."""
        with transaction(self.state) as current:
            for qq, entry in data.items():
                live = current.get(qq)
                if live is None or live.get('day') != entry.get('day'):
                    current[qq] = dict(entry, count=0, exhausted=False)
                elif 'first_seen' in entry and 'first_seen' not in live:
                    live['first_seen'] = entry['first_seen']
                if live and live.get('count') == entry.get('count') and entry.get('exhausted'):
                    live['exhausted'] = True


    def friend_added_at(self, qq):
        """Return when a friend was first seen, or None when unknown."""
        try:
            data = json.loads(self.friends.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        entry = data.get(qq)
        return None if entry is None else float(entry.get('added_at') or 0)

    def friend_known(self, qq):
        try:
            data = json.loads(self.friends.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return None
        if not data:
            return None
        return qq in data

    def load_pending(self):
        try:
            return json.loads(self.pending.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def save_pending(self, data):
        try:
            self.pending.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError:
            pass

    def record_pending(self, qq, text):
        data = self.load_pending()
        entry = data.setdefault(qq, {'at': time.time(), 'messages': []})
        entry['messages'] = (entry.get('messages') or [])[-4:] + [str(text)[:200]]
        self.save_pending(data)

    def queue_outbox(self, qq, text):
        enqueue(self.outbox, [qq], text)

    async def watch_friends(self):
        """Snapshot the friend list so newly added friends get a 20-minute grace."""
        await asyncio.sleep(30)
        while True:
            try:
                platform = self.context.get_platform_inst('dafeiyu-qq')
                client = platform.get_client() if platform is not None else None
                if client is not None:
                    friends = await asyncio.wait_for(client.get_friend_list(), timeout=20)
                    existing = {}
                    if self.friends.exists():
                        try:
                            existing = json.loads(self.friends.read_text(encoding='utf-8'))
                        except (OSError, ValueError):
                            existing = {}
                    old_keys = set(existing)
                    first_run = not self.friends.exists()
                    now = time.time()
                    changed = False
                    for item in friends or []:
                        qq = str(item.get('user_id') or '')
                        if not qq:
                            continue
                        if qq in (SELF,):
                            continue
                        if qq not in existing:
                            existing[qq] = {'added_at': 0 if first_run else now}
                            changed = True
                        entry = existing[qq]
                        nick = str(item.get('nickname') or '')
                        remark = str(item.get('remark') or item.get('card') or '')
                        if entry.get('nick') != nick or entry.get('remark') != remark:
                            entry['nick'] = nick
                            entry['remark'] = remark
                            changed = True
                    if changed or first_run:
                        self.friends.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
                        logger.info('Whale friend snapshot updated: %d friends', len(existing))
                        pending = self.load_pending()
                        for qq in [q for q in existing if q not in old_keys and q not in (SELF,)]:
                            if qq in pending:
                                pending.pop(qq, None)
                                self.save_pending(pending)
                                self.queue_outbox(qq, '刚看到 之前没加上好友 消息都漏了 现在补上了 你刚说啥来着')
            except Exception as exc:
                logger.warning('Whale friend watch failed: %s', type(exc).__name__)
            await asyncio.sleep(60)

    async def watch_outbox(self):
        """Send queued private messages at most once per item."""
        recover_notices(self.outbox)
        await asyncio.sleep(3)
        while True:
            try:
                platform = self.context.get_platform_inst('dafeiyu-qq')
                client = platform.get_client() if platform is not None else None
                item = claim_notice(self.outbox) if client is not None else None
                if item:
                    try:
                        await asyncio.wait_for(
                            client.send_private_msg(user_id=int(item['qq']), message=str(item['text'])), timeout=20)
                    except Exception as exc:
                        finish_notice(self.outbox, item['id'], 'needs_review', type(exc).__name__)
                        logger.warning('Whale notice needs review: %s', item['id'])
                    else:
                        finish_notice(self.outbox, item['id'], 'sent')
            except Exception as exc:
                logger.warning('Whale private outbox watch failed: %s', type(exc).__name__)
            await asyncio.sleep(3)

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE, priority=9600)
    async def gate(self, event):
        if event.get_platform_id() != 'dafeiyu-qq':
            return
        sender = str(event.get_sender_id())
        if sender == OWNER:
            return
        text = str(getattr(event, 'message_str', '') or '')
        known = self.friend_known(sender)
        now = time.time()
        if known is False:
            # The snapshot can lag behind an accepted friend request. Refresh once
            # before dropping the message, so the first message is not lost.
            try:
                platform = self.context.get_platform_inst('dafeiyu-qq')
                client = platform.get_client() if platform is not None else None
                friends = await asyncio.wait_for(client.get_friend_list(), timeout=20) if client is not None else []
                found = None
                for item in friends or []:
                    if str(item.get('user_id') or '') == sender:
                        found = item
                        break
                if found is None:
                    self.record_pending(sender, text)
                    event.stop_event()
                    return
                try:
                    existing = json.loads(self.friends.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    existing = {}
                entry = existing.setdefault(sender, {'added_at': now})
                entry['added_at'] = now
                entry['nick'] = str(found.get('nickname') or '')
                entry['remark'] = str(found.get('remark') or found.get('card') or '')
                self.friends.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
                logger.info('Whale friend refreshed after message: %s', sender)
                pending = self.load_pending()
                if sender in pending:
                    pending.pop(sender, None)
                    self.save_pending(pending)
            except Exception as exc:
                logger.warning('Whale friend refresh failed: %s', type(exc).__name__)
                event.stop_event()
                return
        today = datetime.now(TZ).date().isoformat()
        data = self.load_state()
        entry = data.get(sender) or {}
        if entry.get('day') != today:
            entry = {'day': today, 'count': 0, 'notified': False, 'exhausted': False}
        added = self.friend_added_at(sender)
        if added is None:
            added = float(entry.get('first_seen') or now)
            entry['first_seen'] = added
        limit, grace = self.limits()
        limit = self.limit_for(sender)
        remaining_ask = re.search(
            r'(?:还有|还剩|剩余|剩).{0,6}(?:几次|多少|几条|多少次|多少条|\d+\s*次)'
            r'|(?:额度|次数|条数).{0,6}(?:还剩|剩余|还有)'
            r'|还能(?:发|聊|说).{0,4}(?:几次|多少|几条)',
            text,
        )
        if remaining_ask:
            remaining = max(0, limit - int(entry.get('count', 0)))
            data[sender] = entry
            self.save_state({sender: entry})
            setter = getattr(event, 'set_extra', None)
            if callable(setter):
                setter('skip_quota_count', True)
            event.stop_event()
            await event.send(event.plain_result('我还能发送%d次消息。' % remaining))
            return
        if any(word in text for word in CRISIS_TERMS) and int(entry.get('count', 0)) < limit + 10:
            # Someone in crisis must never be silenced by grace or quota, but the
            # bypass is bounded so the word cannot be used to chat without limit.
            return
        if now - added < grace:
            data[sender] = entry
            self.save_state({sender: entry})
            event.stop_event()
            return
        if int(entry.get('count', 0)) >= limit:
            event.stop_event()
            if not entry.get('exhausted'):
                entry['exhausted'] = True
                data[sender] = entry
                self.save_state({sender: entry})
                await event.send(event.plain_result('今天跟你聊满 %d 条啦 再说下去我就要断粮了 明天再来找我吧' % limit))
            return
        data[sender] = entry
        self.save_state({sender: entry})

    @filter.on_decorating_result()
    async def first_reply_notice(self, event):
        if event.get_platform_id() != 'dafeiyu-qq' or event.get_group_id():
            return
        sender = str(event.get_sender_id())
        if sender == OWNER:
            return
        result = event.get_result()
        if not result or not result.chain:
            return
        getter = getattr(event, 'get_extra', None)
        if callable(getter) and getter('skip_quota_count'):
            return
        if not event.get_extra('dafeiyu_delivery_meter_armed'):
            original_send = event.send

            async def metered_send(message):
                # Only a successful adapter call is charged. A raised exception
                # leaves the count unchanged and propagates to the pipeline.
                await original_send(message)
                if event.get_extra('skip_quota_count'):
                    return
                amount = sum(
                    1 for part in message.chain
                    if (type(part).__name__ == 'Plain' and str(getattr(part, 'text', '')).strip())
                    or type(part).__name__ in ('Image', 'Record', 'File', 'Video', 'Music', 'Face', 'Node', 'Nodes')
                )
                if not amount:
                    return
                today = datetime.now(TZ).date().isoformat()
                try:
                    with transaction(self.state) as data:
                        entry = data.get(sender) or {}
                        if entry.get('day') != today:
                            entry = {'day': today, 'count': 0, 'notified': False, 'exhausted': False}
                        entry['count'] = int(entry.get('count', 0)) + amount
                        entry['notified'] = True
                        data[sender] = entry
                except (OSError, ValueError):
                    # Delivery already succeeded. Never turn accounting failure
                    # into a send failure that could trigger a duplicate reply.
                    logger.exception('Whale delivered reply quota persistence failed')

            event.send = metered_send
            event.set_extra('dafeiyu_delivery_meter_armed', True)

        # Decoration is read-only; failed delivery must not consume quota or
        # suppress the first successful reply's daily notice.
        data = self.load_state()
        entry = data.get(sender) or {}
        today = datetime.now(TZ).date().isoformat()
        first = entry.get('day') != today or int(entry.get('count', 0)) == 0
        if event.get_extra('no_quota_notice') or not first:
            return
        if event.get_extra('dafeiyu_quota_notice_decorated'):
            return
        text = ''.join(getattr(part, 'text', '') for part in result.chain).strip()
        if text in ('1000000001', '我没有权限哦，去联系我主人试试吧！', '应该会的吧，你可以去联系我主人问问呀！', '哦鲸鲸'):
            return
        if any(type(part).__name__ == 'Record' for part in result.chain):
            return
        notice = '（备注：每天最多聊 %d 条，聊满了明天再来。）' % self.limit_for(sender)
        for comp in reversed(result.chain):
            if isinstance(comp, Plain):
                comp.text = (comp.text or '').rstrip() + '\n' + notice
                break
        else:
            result.chain.append(Plain(notice))
        event.set_extra('dafeiyu_quota_notice_decorated', True)

    async def terminate(self):
        if self.task:
            self.task.cancel()
        if self.outbox_task:
            self.outbox_task.cancel()
