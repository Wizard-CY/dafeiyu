"""Tell friends she is back online after a real outage and answer what they sent meanwhile."""

import asyncio
import json
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import Star, register

TZ = timezone(timedelta(hours=8))
OWNER = '1000000001'
SELF = '1000000000'
MIN_DOWNTIME = 5 * 60
# Recoveries longer than this are no longer "刚才掉线了".  The mirror supervisor
# handles them with the "我上线啦" notice instead.
MAX_DOWNTIME = 60 * 60
VARIANTS = (
    '刚上线看到你发的 我这边断线了 才收到 不是不理你',
    '刚才掉线了一会儿 你这条才看到 现在在了',
    '我掉线了 刚爬回来 你发的看到了 接着说',
)
OWNER_VARIANTS = (
    '主人 我刚才断线了 才看到你消息 现在回来了',
    '刚才掉线了 没看到你发的 现在好了 你说',
)
LONG_VARIANTS = (
    '我这边断线挺久了 刚恢复 你之前发的才看到 不是不理你',
    '断了半天 刚爬回来 你发的现在才看到 接着说',
)
OWNER_LONG_VARIANTS = (
    '主人 我断线挺久了 刚恢复 之前没看到你消息 现在在了',
    '断了挺久 刚回来 你之前发的才看到 现在好了',
)
NEW_FRIEND_VARIANTS = (
    '刚看到你加我 我是大肥鱼 一个AI 平时就在这儿蹭饭',
    '哟 新朋友 我是大肥鱼 一个AI 平时就在这儿蹭饭 有事说事',
)


@register('dafeiyu_reconnect', 'Local', 'Answer private messages missed during downtime and explain the disconnect', '1.2.0')
class Reconnect(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.state = self.data / 'dafeiyu_online_state.json'
        self.config = self.data / 'dafeiyu_reconnect.json'
        self.friends = self.data / 'dafeiyu_friends.json'
        self.supervisor = self.data / 'dafeiyu_supervisor_state.json'
        self.task = None
        self.last_outage = None

    def load_json(self, path):
        try:
            return json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError):
            return {}

    def save_state(self, payload):
        try:
            self.state.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            logger.warning('Whale reconnect state write failed: %s', type(exc).__name__)

    def settings(self):
        """Read the reconnect settings, falling back to safe defaults.

        Returns:
            A dict with enable and dry_run keys.
        """
        cfg = self.load_json(self.config)
        return {
            'enable': cfg.get('enable', True),
            'dry_run': cfg.get('dry_run', False),
        }

    async def supervisor_mode(self, since, wait=0):
        """Read the mirror supervisor's decision for the current outage.

        The mirror control center runs even while the main bot is down.  It
        decides whether a recovery is a short reconnect or a fresh start.  A
        decision is accepted only when the supervisor heartbeat is fresh and
        the decision was made after this outage began; otherwise the caller
        falls back to the local 60-minute rule.

        Args:
            since: Epoch seconds when this outage began.
            wait: Seconds to wait for a pending decision to appear.

        Returns:
            "reconnect", "startup", or None when no fresh decision exists.
        """
        supervisor = getattr(self, 'supervisor', None)
        if supervisor is None:
            return None
        since = float(since or 0)
        deadline = time.time() + max(0.0, float(wait))
        while True:
            state = self.load_json(supervisor)
            try:
                beat = float(state.get('heartbeat') or 0)
                mode_at = float(state.get('mode_at') or 0)
            except (TypeError, ValueError):
                beat = 0
                mode_at = 0
            fresh = bool(beat) and time.time() - beat <= 120
            if not fresh:
                return None
            mode = str(state.get('mode') or '')
            if mode in ('reconnect', 'startup') and mode_at >= since - 5:
                return mode
            if time.time() >= deadline:
                return None
            await asyncio.sleep(1)

    async def reachable(self, bot):
        """Return whether QQ answers a login probe.

        Args:
            bot: OneBot client, or None.

        Returns:
            True when get_login_info succeeds within 8 seconds.
        """
        if bot is None:
            return False
        try:
            await asyncio.wait_for(bot.call_action(action='get_login_info'), timeout=8)
            return True
        except Exception:
            return False

    def outage_payload(self, start, end, downtime, mode, friends, sent):
        """Build the last_outage record shown by the control center.

        Args:
            start: Epoch seconds when the outage started.
            end: Epoch seconds when it ended.
            downtime: Seconds spent offline.
            mode: "reconnect" or "startup".
            friends: Number of friends waiting for an answer.
            sent: Number of friends actually messaged.

        Returns:
            A dict suitable for dafeiyu_online_state.json.
        """
        return {
            'start': float(start),
            'end': end,
            'minutes': round(downtime / 60),
            'friends': int(friends),
            'sent': int(sent),
            'mode': mode,
            'day': datetime.now(TZ).date().isoformat(),
        }

    def mark_outage_day(self, state):
        """Increment today's outage counter, resetting it on a new day.

        Args:
            state: Mutable online-state dict.
        """
        day = datetime.now(TZ).date().isoformat()
        if state.get('outage_day') != day:
            state['outage_day'] = day
            state['outages_today'] = 0
        state['outages_today'] = int(state.get('outages_today') or 0) + 1

    async def client(self):
        """Return the OneBot client once the platform is ready.

        Returns:
            The CQHttp client, or None when the platform is not up yet.
        """
        for _ in range(60):
            platform = self.context.get_platform_inst('dafeiyu-qq')
            if platform is not None:
                getter = getattr(platform, 'get_client', None)
                bot = getter() if callable(getter) else None
                if bot is not None:
                    return bot
            await asyncio.sleep(5)
        return None

    def message_text(self, message):
        """Extract the plain text of one OneBot history message.

        Args:
            message: One message dict from get_friend_msg_history.

        Returns:
            A short text preview, or a placeholder for non-text messages.
        """
        chain = message.get('message')
        if isinstance(chain, str):
            return chain.strip()[:40]
        if isinstance(chain, list):
            for part in chain:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text = str((part.get('data') or {}).get('text') or '').strip()
                    if text:
                        return text[:40]
        return '[非文字消息]'

    async def missed_friends(self, bot, since):
        """Find friends whose messages arrived during the outage and never got an answer.

        Args:
            bot: OneBot client.
            since: Epoch seconds when the connection was lost.

        Returns:
            A list of (QQ, last message text) pairs, newest first.
        """
        friends = self.load_json(self.friends)
        found = []
        checked = 0
        for qq in list(friends.keys()):
            if qq == SELF:
                continue
            try:
                history = await bot.call_action(action='get_friend_msg_history', user_id=int(qq), count=20)
            except Exception as exc:
                logger.info('Whale reconnect history failed for %s: %s', qq, type(exc).__name__)
                continue
            checked += 1
            messages = history.get('messages') if isinstance(history, dict) else None
            if messages is None and isinstance(history, dict):
                messages = (history.get('data') or {}).get('messages')
            if not isinstance(messages, list):
                continue
            pending = []
            for message in messages:
                if not isinstance(message, dict):
                    continue
                sender = str((message.get('sender') or {}).get('user_id') or '')
                try:
                    stamp = float(message.get('time') or 0)
                except (TypeError, ValueError):
                    continue
                if stamp <= since:
                    continue
                if sender == qq:
                    pending.append((stamp, self.message_text(message)))
                elif sender == SELF:
                    # Anything before her own line already has an answer.
                    pending = []
            if pending:
                pending.sort()
                found.append((qq, pending[-1][1], pending[-1][0]))
        found.sort(key=lambda item: item[2], reverse=True)
        logger.info('Whale reconnect scanned %d friend(s), %d waiting for an answer', checked, len(found))
        return [(qq, text) for qq, text, _ in found]

    async def reply_unanswered(self, bot, targets, dry_run, downtime=0):
        """Answer every friend whose message was swallowed by the outage.

        Args:
            bot: OneBot client.
            targets: (QQ, message text) pairs returned by missed_friends.
            dry_run: When True, only log what would be sent.
            downtime: Seconds spent offline, used to pick a matching excuse.
        """
        friends = self.load_json(self.friends)
        sent = []
        for qq, _text in [item for item in targets if item[0] in friends][:8]:
            added = float((friends.get(qq) or {}).get('added_at') or 0)
            if added and time.time() - added < 3600:
                pool = ('刚看到你加我 我是大肥鱼 一个AI 平时就在这儿蹭饭',)
            elif downtime >= 3600:
                pool = OWNER_LONG_VARIANTS if qq == OWNER else LONG_VARIANTS
            else:
                pool = OWNER_VARIANTS if qq == OWNER else VARIANTS
            text = random.choice(pool)
            if dry_run:
                logger.info('Whale reconnect dry-run would message %s: %s', qq, text)
                continue
            try:
                await bot.call_action(action='send_private_msg', user_id=int(qq), message=text)
                sent.append(qq)
                logger.info('Whale reconnect answered %s', qq)
            except Exception as exc:
                logger.warning('Whale reconnect send to %s failed: %s', qq, type(exc).__name__)
            await asyncio.sleep(1.5)
        return sent

    async def run(self):
        """Check one outage, then keep the heartbeat fresh."""
        cfg = self.settings()
        state = self.load_json(self.state)
        previous = state.get('last_seen') or 0
        await asyncio.sleep(40)
        now = time.time()
        keep_since = 0
        if cfg.get('enable') and previous:
            downtime = max(0.0, now - float(previous))
            mode = await self.supervisor_mode(previous, wait=10)
            if mode == 'startup':
                bot = await self.client()
                if await self.reachable(bot):
                    logger.info('Whale startup after %.0f min; mirror owns the online notice',
                                downtime / 60)
                    self.last_outage = self.outage_payload(
                        previous, now, downtime, 'startup', 0, 0)
                else:
                    keep_since = previous
                    logger.info('Whale reconnect: platform not reachable yet, keep last_seen for the tick')
            elif mode == 'reconnect' or (mode is None and MIN_DOWNTIME <= downtime <= MAX_DOWNTIME):
                if downtime < MIN_DOWNTIME:
                    logger.info('Whale reconnect: quick drop %.0f s, stay quiet', downtime)
                else:
                    bot = await self.client()
                    if await self.reachable(bot):
                        targets = await self.missed_friends(bot, previous)
                        logger.info('Whale reconnect: downtime %.0f min, %d friend(s) waiting',
                                    downtime / 60, len(targets))
                        sent = []
                        if targets:
                            sent = await self.reply_unanswered(
                                bot, targets, cfg.get('dry_run', False), downtime)
                        self.last_outage = self.outage_payload(
                            previous, now, downtime, 'reconnect', len(targets), len(sent))
                    else:
                        # Keep the outage start so the tick can finish this scan once QQ is back.
                        keep_since = previous
                        logger.info('Whale reconnect: platform not reachable yet, keep last_seen for the tick')
            elif mode is None and downtime < MIN_DOWNTIME:
                logger.info('Whale reconnect: quick drop %.0f s, stay quiet', downtime)
            else:
                logger.info('Whale reconnect: no mirror decision after %.0f h, stay quiet',
                            downtime / 3600)
        payload = {'last_seen': previous if keep_since else now,
                   'booted_at': datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')}
        if keep_since:
            payload['offline_since'] = keep_since
        if getattr(self, 'last_outage', None):
            payload['last_outage'] = self.last_outage
            prior = self.load_json(self.state)
            day = datetime.now(TZ).date().isoformat()
            count = int(prior.get('outages_today') or 0)
            if prior.get('outage_day') != day:
                count = 0
            payload['outage_day'] = day
            payload['outages_today'] = count + 1
        self.save_state(payload)
        while True:
            await asyncio.sleep(30)
            try:
                await self.tick()
            except Exception as exc:
                logger.warning('Whale reconnect heartbeat failed: %s', type(exc).__name__)

    async def tick(self, bot=None, now=None):
        """Refresh the online heartbeat and greet friends after a reconnect.

        A dropped websocket never restarts the process, so this tick is the only
        place that can notice "offline -> online" transitions during a run.

        Args:
            bot: Optional OneBot client override, mainly for drills.
            now: Optional epoch seconds override, mainly for drills.
        """

        now = time.time() if now is None else float(now)
        state = self.load_json(self.state)
        if bot is None:
            platform = self.context.get_platform_inst('dafeiyu-qq')
            getter = getattr(platform, 'get_client', None) if platform is not None else None
            bot = getter() if callable(getter) else None
        reachable = await self.reachable(bot)
        if reachable:
            offline_since = state.get('offline_since') or 0
            if offline_since:
                downtime = max(0.0, now - float(offline_since))
                cfg = self.settings()
                mode = await self.supervisor_mode(float(offline_since), wait=5)
                send = bool(cfg.get('enable')) and (
                    mode == 'reconnect'
                    or (mode is None and MIN_DOWNTIME <= downtime <= MAX_DOWNTIME))
                if send and downtime >= MIN_DOWNTIME:
                    targets = await self.missed_friends(bot, float(offline_since))
                    logger.info('Whale reconnect: back after %.0f min, %d friend(s) waiting',
                                downtime / 60, len(targets))
                    sent = []
                    if targets:
                        sent = await self.reply_unanswered(
                            bot, targets, cfg.get('dry_run', False), downtime)
                    state['last_outage'] = self.outage_payload(
                        float(offline_since), now, downtime, 'reconnect', len(targets), len(sent))
                    self.mark_outage_day(state)
                elif cfg.get('enable') and mode == 'startup':
                    logger.info('Whale startup after %.0f min; mirror owns the online notice',
                                downtime / 60)
                    state['last_outage'] = self.outage_payload(
                        float(offline_since), now, downtime, 'startup', 0, 0)
                    self.mark_outage_day(state)
                elif downtime < MIN_DOWNTIME:
                    logger.info('Whale reconnect: quick drop %.0f s, stay quiet', downtime)
                elif mode is None:
                    logger.info('Whale reconnect: no mirror decision after %.0f h, stay quiet',
                                downtime / 3600)
                state.pop('offline_since', None)
            state['last_seen'] = now
        else:
            if not state.get('offline_since'):
                state['offline_since'] = now
                logger.info('Whale reconnect: connection lost, keep last_seen=%s', state.get('last_seen'))
        state['beat'] = datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')
        self.save_state(state)

    async def initialize(self):
        """Start the outage check as a background task."""
        self.task = asyncio.create_task(self.run())