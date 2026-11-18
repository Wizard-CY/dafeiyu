import asyncio
import hashlib
import json
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import edge_tts

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.message_components import Plain, Record
from astrbot.api.star import Star, register

TZ = timezone(timedelta(hours=8))
OWNER = '1000000001'
FAMILY_GROUP = '1000000002'
DEFAULTS = {
    'enable': False,
    'voice': 'zh-CN-XiaoyiNeural',
    'rate': '+6%',
    'pitch': '+18Hz',
    'private_chance': 0.25,
    'group_chance': 0.05,
    'family_chance': 0.15,
    'max_chars': 40,
    'daily_cap': 30,
}


@register('dafeiyu_voice', 'Local', 'Edge TTS voice replies, disabled by default', '1.0.0')
class Voice(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.config = self.data / 'dafeiyu_voice.json'
        self.group_settings = self.data / 'dafeiyu_group_settings.json'
        self.cache = self.data / 'voice_cache'
        self.count_file = self.data / 'dafeiyu_voice_count.json'
        self.test_flag = self.data / 'dafeiyu_voice.test'
        self.task = None

    async def initialize(self):
        self.cache.mkdir(exist_ok=True)
        self.task = asyncio.create_task(self.test_loop())

    def cfg(self):
        try:
            data = json.loads(self.config.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            data = {}
        merged = dict(DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in DEFAULTS})
        return merged

    def usable(self, text):
        """Tell whether a reply is worth turning into a voice message.

        Args:
            text: Reply text.

        Returns:
            True when the text is short, clean and speakable.
        """
        if not text:
            return False
        limit = int(self.cfg().get('max_chars', 40))
        if len(text) > limit or len(text) < 2:
            return False
        if 'http' in text or 'wx.' in text or text.count('[') > 0:
            return False
        return True

    def day_count(self):
        try:
            data = json.loads(self.count_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return 0
        today = datetime.now(TZ).date().isoformat()
        return int(data.get('count', 0)) if data.get('day') == today else 0

    def bump(self):
        today = datetime.now(TZ).date().isoformat()
        count = self.day_count() + 1
        try:
            self.count_file.write_text(json.dumps({'day': today, 'count': count}, ensure_ascii=False), encoding='utf-8')
        except OSError as exc:
            logger.warning('Whale voice count write failed: %s', type(exc).__name__)

    async def synth(self, text):
        """Synthesize text into a cached mp3 file.

        Args:
            text: Text to speak.

        Returns:
            Path string, or '' when synthesis failed.
        """
        cfg = self.cfg()
        digest = hashlib.md5((cfg['voice'] + cfg['rate'] + cfg['pitch'] + text).encode('utf-8')).hexdigest()[:16]
        path = self.cache / (digest + '.mp3')
        if path.exists() and path.stat().st_size > 2000:
            return str(path)
        try:
            await edge_tts.Communicate(text, cfg['voice'], rate=cfg['rate'], pitch=cfg['pitch']).save(str(path))
        except Exception as exc:
            logger.warning('Whale voice synth failed: %s', type(exc).__name__)
            return ''
        return str(path) if path.exists() and path.stat().st_size > 2000 else ''

    def quiet(self):
        """Return whether the scheduled silent window is active.

        Returns:
            Always False; the bot stays available around the clock.
        """
        return False

    def group_voice_rate(self, gid):
        """Return a group's voice percentage, where 100 keeps the default."""
        try:
            data = json.loads(self.group_settings.read_text(encoding='utf-8'))
        except (OSError, ValueError, AttributeError):
            return 100
        base = int((data.get('defaults') or {}).get('voice_rate', 100))
        try:
            return max(0, min(200, int((data.get('per_group') or {}).get(str(gid), {}).get('voice_rate', base))))
        except (TypeError, ValueError):
            return max(0, min(200, base))

    VOICE_REQUEST = re.compile(r'(?:发|来|整|说|录|唱).{0,4}(?:条|句|个)?语音|语音条|听听你(?:的)?声音|说句话')


    @filter.on_decorating_result()
    async def maybe_voice(self, event):
        if event.get_platform_id() != 'dafeiyu-qq':
            return
        result = event.get_result()
        if result is None or not result.chain:
            return
        getter = getattr(event, 'get_extra', None)
        if callable(getter) and getter('no_voice'):
            return
        if not event.get_group_id() and self.VOICE_REQUEST.search(str(getattr(event, 'message_str', '') or '')):
            path = await self.synth('哦鲸鲸')
            if path:
                result.chain = [Record(file=path, text='哦鲸鲸')]
                self.bump()
                logger.info('Whale forced voice reply: 哦鲸鲸')
            else:
                result.chain = [Plain('哦鲸鲸')]
            setter = getattr(event, 'set_extra', None)
            if callable(setter):
                setter('no_quota_notice', True)
            return
        cfg = self.cfg()
        if not cfg.get('enable'):
            return
        text = ''.join(part.text for part in result.chain if isinstance(part, Plain)).strip()
        if text in ('我没有权限哦，去联系我主人试试吧！', '应该会的吧，你可以去联系我主人问问呀！'):
            return
        if any(word in text for word in ('主人', '家庭群', '1000000002', '1000000001', '阿姨')) or text.strip().isdigit():
            # Let the text privacy guard handle this instead of speaking it.
            return
        if not self.usable(text):
            return
        if self.day_count() >= int(cfg.get('daily_cap', 30)):
            return
        group = event.get_group_id()
        if group and self.quiet():
            return
        chance = float(cfg.get('group_chance' if group else 'private_chance', 0.1))
        if group == FAMILY_GROUP:
            chance = float(cfg.get('family_chance', 0.15))
        if group:
            voice_rate = self.group_voice_rate(group)
            if voice_rate <= 0:
                return
            chance *= voice_rate / 100
        if random.random() >= chance:
            return
        path = await self.synth(text)
        if not path:
            return
        chain = []
        replaced = False
        for part in result.chain:
            if isinstance(part, Plain) and not replaced:
                chain.append(Record(file=path, text=text[:80]))
                replaced = True
            else:
                chain.append(part)
        result.chain = chain
        self.bump()
        logger.info('Whale voice reply sent as record (%d chars)', len(text))

    async def test_loop(self):
        """Send a one-off voice message when the test flag appears."""
        while True:
            await asyncio.sleep(5)
            if not self.test_flag.exists():
                continue
            try:
                text = self.test_flag.read_text(encoding='utf-8').strip() or '主人，我在呢。'
                self.test_flag.unlink()
                path = await self.synth(text)
                if not path:
                    logger.warning('Whale voice test: synth failed')
                    continue
                client = self.context.get_platform_inst('dafeiyu-qq').get_client()
                uri = 'file:///' + path.replace('\\', '/')
                result = await client.call_action('send_private_msg', user_id=int(OWNER), message=[{'type': 'record', 'data': {'file': uri}}])
                logger.info('Whale voice test sent: %s', str(result)[:120])
            except Exception as exc:
                logger.warning('Whale voice test failed: %s %s', type(exc).__name__, exc)

    async def terminate(self):
        if self.task:
            self.task.cancel()
