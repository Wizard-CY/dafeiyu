import asyncio
import base64
from difflib import SequenceMatcher
import json
import random
import shutil
import sqlite3
import subprocess
import re
import time

import aiohttp
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import File, Image, Record
from astrbot.core.message.message_event_result import MessageChain
from astrbot.api.star import Star, register
from data.plugins.dafeiyu_quota.main import add_sent

MUSIC_PLUGIN = 'astrbot_plugin_listen_music'
WINDOW_SECONDS = 5
COOLDOWN_SECONDS = 90
HOURLY_SONGS = 6
PEER_AIS = {'1000000008', '1000000009', '1000000010', '1000000011'}
_PACKAGE = Path(__file__).resolve().parents[5]
LIBRARY_DIR = _PACKAGE / 'data' / 'music_library'
LIBRARY_INDEX = LIBRARY_DIR / 'index.json'
FFMPEG = _PACKAGE / 'runtime' / 'bin' / 'ffmpeg.exe'
QQ_BACKEND = 'http://127.0.0.1:3311'
OWNER = '1000000001'
LOGIN_REQUEST = _PACKAGE / 'data' / 'qqmusic_login.request'
BACKEND_DIR = _PACKAGE / 'backend' / 'qqmusic'
_NODE = shutil.which('node')
NODE_EXE = Path(_NODE) if _NODE else _PACKAGE / 'runtime' / 'bin' / 'node.exe'
INTENT = re.compile(
    r'(点歌|放首歌|放一首歌|放个歌|放一下|放首|搜索音乐|搜音乐|来一首|来首|想听|听一下|听个|唱首歌|唱一首|唱首|放歌|听歌|搜歌|搜一下|搜索歌曲|播放|播一下|播个|来一个|整一首|整一个|来点歌|放点歌|给我放|帮我放|给我来|来点音乐|放点音乐)'
)
CLEAN = re.compile(r'[@＠]\S+|大肥鱼|哦鲸鲸|鲸鲸|鲸鱼|帮我|给我|我想|想听|我|一下|听个|一首|一个|首歌|吧|呗|呀|啊|呢|嘛|谢谢|请|麻烦|来|放|唱|点|搜索|播放|听')
CONTEXT_CUES = re.compile(
    r'(这首|那首|刚才|刚刚|上一首|前面那首|换一?首|再换|再来一首|再放一首|'
    r'就这个|就它|这个歌|那个歌|继续放|再放|还要听|再来点|换个歌|换首歌|'
    r'应景|适合|那种|类似|昨天|上次|之前|她的|他的)'
)
CONTEXT_TRIGGER = re.compile(
    r'(这首|那首|刚才那首|上一首|换一?首|再换|再来一首|再放一首|就这个|就它|'
    r'继续放|再放|换首歌|换个歌)'
)
DISCUSSION_GUARD = ('你说', '你解释', '你讲', '意见', '想法', '看法', '建议', '分析', '八卦', '新闻')
RESOLVER_SYSTEM = (
    '你是大肥鱼的点歌意图解析器。结合最近对话判断用户是不是在要求放歌，并给出搜索关键词。'
    '只输出一个 JSON：{"play": true 或 false, "query": "歌手 歌名 版本", "reason": "简短理由"}。'
    '规则：只有明确想听、要放、要换歌才算 play=true；单纯讨论歌词、歌手、音乐话题算 false。'
    '指代要结合上下文：这首、刚才那首、就这个 → 最近提到或她刚放过的歌；'
    '换一首、再来一首 → 同歌手或同风格的另一首，不要重复刚放过的；只说歌手 → 选该歌手一首合适的。'
    'query 直接用于音乐搜索，不要带“来一首”“放一下”等指令词。'
)


def _duration_seconds(candidate):
    """Parse the plugin's "m:ss" duration into seconds.

    Args:
        candidate: One candidate dict from find_music.

    Returns:
        Duration in seconds, or 0 when unknown.
    """
    text = str(candidate.get('duration') or '')
    parts = text.split(':')
    try:
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        return int(text)
    except (TypeError, ValueError):
        return 0


def _clean_title(text):
    """Lower-case and strip punctuation so titles can be compared.

    Args:
        text: Raw title text.

    Returns:
        A compact comparison string.
    """
    return re.sub(r'[^0-9a-zA-Z\u4e00-\u9fff]', '', str(text or '').lower())


BAD_VERSION_WORDS = ('翻唱', 'cover', 'dj', '抖音', '网红', '女声', '男声', '童声', '钢琴',
                    '吉他', '伴奏', '纯音乐', '现场', 'live', '演唱会', '片段', '慢速', '加速',
                    '8d', 'remix', '鬼畜', '整活', '恶搞', '教学', '谱', 'ktv', '人声提取', 'ai')
OFFICIAL_WORDS = ('原版', '官方', '专辑', 'mv', '正版', '高清', '无损')


def _version_profile(query):
    """Split a request into song text and an explicit version cue.

    Args:
        query: The user's song request.

    Returns:
        A (base text, version text, version tokens) tuple.
    """
    text = str(query or '').strip()
    version = ''
    base = text
    match = re.search(r'[（(]([^）)]{1,24})[）)]', text)
    if match:
        version = match.group(1).strip()
        base = (text[:match.start()] + text[match.end():]).strip()
    else:
        match = re.search(r'(?i)([A-Za-z0-9]{1,8}版)$', text)
        if not match:
            match = re.search(r'([\u4e00-\u9fff]{1,2}版)$', text)
        if not match:
            match = re.search(r'(?i)(live|dj|翻唱|伴奏|现场|女声|男声)$', text)
        if match:
            version = match.group(1).strip()
            base = text[:match.start()].strip()
    tokens = set()
    if version:
        cleaned = _clean_title(version).replace('版', '')
        if cleaned:
            tokens.add(cleaned)
        if len(cleaned) > 1:
            tokens.update(cleaned[i:i + 2] for i in range(len(cleaned) - 1))
    return base, version, tokens


def _search_query(query):
    """Build the search keywords for a request, keeping its version cue.

    Args:
        query: The user's song request.

    Returns:
        Search text such as "雨爱 司凤" for a version request.
    """
    base, version, _ = _version_profile(query)
    if not version:
        return str(query or '').strip()
    cleaned = _clean_title(version).replace('版', '')
    return ('%s %s' % (base, cleaned)).strip()


def _rank_candidates(candidates, query=''):
    """Rank candidates by song title and requested version.

    Args:
        candidates: Candidate dicts from find_music or QQ Music search.
        query: The user's song request.

    Returns:
        Positions ordered from best to worst; only relevant ones are kept.
    """
    generic = ('伴奏', '纯音乐', '吉他谱', '曲谱', '教学', '人声提取', 'ktv', '拍摄', '花絮', '解析', '盘点', '混剪', '采访')
    base, version, version_tokens = _version_profile(query)
    clean_query = _clean_title(base)
    bigrams = {clean_query[i:i + 2] for i in range(len(clean_query) - 1)} if len(clean_query) > 1 else set()
    core = clean_query.split('的')[-1] if '的' in clean_query else clean_query
    core_grams = {core[i:i + 2] for i in range(len(core) - 1)} if len(core) > 1 else set()
    requested = _clean_title(version)
    scored = []
    for candidate in candidates:
        seconds = _duration_seconds(candidate)
        if seconds and not 90 <= seconds <= 600:
            continue
        title = _clean_title(' '.join(str(candidate.get(key) or '') for key in ('title', 'search_title', 'page_title')))
        if core_grams:
            coverage = sum(1 for gram in core_grams if gram in title) / len(core_grams)
            if core not in title and coverage < 0.5:
                continue
        if version_tokens:
            if not any(token in title for token in version_tokens):
                continue
        score = sum(1 for gram in bigrams if gram in title) if bigrams else 0
        if clean_query and clean_query in title:
            score += 5
        if version_tokens:
            score += 5 * sum(1 for token in version_tokens if token in title)
            if requested and requested in title:
                score += 5
        else:
            score -= 3 * sum(1 for word in BAD_VERSION_WORDS if word in title)
            score += 2 * sum(1 for word in OFFICIAL_WORDS if word in title)
            score -= 2 * sum(1 for word in generic if word in title)
        position = candidate.get('position') or 1
        scored.append((score, position))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [position for _, position in scored]


def _best_candidate(candidates, query=''):
    """Choose the candidate that best matches the requested song.

    Args:
        candidates: Candidate dicts from find_music.
        query: The user's song request.

    Returns:
        Position of the chosen candidate, or None when nothing matches.
    """
    ranked = _rank_candidates(candidates, query)
    return ranked[0] if ranked else None


def _library_entries():
    """Read the shared song library index.

    Returns:
        A list of song entries.
    """
    try:
        data = json.loads(LIBRARY_INDEX.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    return [item for item in data.get('songs', []) if isinstance(item, dict)]


def _match_library(query):
    """Find the cached song that best matches a request.

    Args:
        query: The user's song request.

    Returns:
        The matching library entry, or None.
    """
    base, version, version_tokens = _version_profile(_query(query) or query)
    wanted = _clean_title(base)
    if len(wanted) < 2:
        return None
    best = None
    for item in _library_entries():
        title = _clean_title(item.get('title'))
        artist = _clean_title(item.get('artist'))
        if not title:
            continue
        target = title + artist
        if version_tokens and not any(token in target for token in version_tokens):
            continue
        if not version_tokens and any(word in target for word in BAD_VERSION_WORDS):
            score = -1.0
        elif wanted == title:
            score = 1.2
        elif wanted in target or title in wanted:
            score = 1.0
        else:
            score = max(SequenceMatcher(None, wanted, title).ratio(),
                        SequenceMatcher(None, wanted, target).ratio())
            grams = {wanted[i:i + 2] for i in range(len(wanted) - 1)}
            if grams:
                score = max(score, sum(1 for gram in grams if gram in target) / len(grams))
        if not (LIBRARY_DIR / str(item.get('file') or '')).exists():
            continue
        better_source = item.get('source') == 'qq' and (best is None or best[1].get('source') != 'qq')
        if best is None or score > best[0] or (score == best[0] and better_source):
            best = (score, item)
    return best[1] if best is not None and best[0] >= 0.55 else None


def _addressed(event):
    """Return whether the message really talks to the bot.

    Args:
        event: Incoming message event.

    Returns:
        True for private chat, an @ of the bot, or a quote of the bot.
    """
    if not event.get_group_id():
        return True
    self_id = str(event.get_self_id()).lstrip('0')
    for part in event.get_messages():
        if type(part).__name__ == 'At' and str(getattr(part, 'qq', '')).lstrip('0') == self_id:
            return True
        if type(part).__name__ == 'Reply' and str(getattr(part, 'sender_id', '')).lstrip('0') == self_id:
            return True
    # Some clients send "@昵称" as plain text instead of an At segment.
    text = str(getattr(event, 'message_str', '') or '')
    return bool(re.search(r'@\s*(大肥鱼|哦鲸鲸|鲸鲸)', text))


def _plain_text(event):
    """Collect only the typed text of a message, excluding @ decorations.

    Args:
        event: Incoming message event.

    Returns:
        The plain text, or the raw message string when no text component exists.
    """
    pieces = []
    for part in event.get_messages():
        text = getattr(part, 'text', None)
        if isinstance(text, str) and text:
            pieces.append(text)
    joined = ''.join(pieces).strip()
    return joined or str(getattr(event, 'message_str', '') or '').strip()


def _query(text):
    """Extract the song request from a chat line.

    Args:
        text: Plain text of the message.

    Returns:
        A cleaned song query, or an empty string when the user did not name one.
    """
    cleaned = INTENT.sub(' ', str(text or ''))
    cleaned = re.sub(r'[，。！？、,.!?]', ' ', cleaned)
    cleaned = CLEAN.sub(' ', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip(' "“”\'')
    if cleaned in ('歌', '曲', '音乐', '歌曲', '歌 曲'):
        return ''
    return cleaned[:60]


@register('dafeiyu_music', 'Local', 'Context-aware song requests with QQ Music and Bilibili fallback', '1.1.0')
class Music(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.pending = {}
        self.last_play = {}
        self.last_hint = {}
        self.song_times = {}
        self.history = {}
        self.last_song = {}
        asyncio.create_task(self.watch_login_requests())

    async def initialize(self):
        """Log the real dispatch order once so priority problems are visible."""
        await asyncio.sleep(3)
        try:
            from astrbot.core.star.star_handler import EventType, star_handlers_registry
            handlers = star_handlers_registry.get_handlers_by_event_type(EventType.AdapterMessageEvent)
            mine = ('dafeiyu_group', 'dafeiyu_music', 'dafeiyu_guard', 'dafeiyu_lock', 'dafeiyu_hearing')
            order = [(h.handler_name, h.extras_configs.get('priority')) for h in handlers
                     if h.handler_module_path.split('.')[-2] in mine]
            logger.info('Whale music dispatch order: %s', order)
        except Exception as exc:
            logger.warning('Whale music order probe failed: %s', type(exc).__name__)

    def music_plugin(self):
        """Return the listening-music plugin instance, when it is loaded.

        Returns:
            The plugin instance, or None.
        """
        try:
            meta = self.context.get_registered_star(MUSIC_PLUGIN)
        except Exception:
            meta = None
        return getattr(meta, 'star_cls', None) if meta is not None else None

    async def send_hint(self, event, text, gap=60):
        """Send a short hint at most once per gap.

        Args:
            event: Incoming message event.
            text: Hint text.
            gap: Seconds before the same session may see another hint.
        """
        session = event.unified_msg_origin
        now = time.time()
        if now - self.last_hint.get(session, 0) < gap:
            return
        self.last_hint[session] = now
        await event.send(event.plain_result(text))
        if not event.get_group_id():
            add_sent(event.get_sender_id(), 1)
        event.stop_event()

    async def watch_login_requests(self):
        """Send a QQ Music login QR to the owner when the status center asks."""
        ticks = 0
        while True:
            await asyncio.sleep(2)
            ticks += 1
            try:
                if ticks % 30 == 0 and await self._qq_get('/health') is None:
                    if NODE_EXE.exists() and (BACKEND_DIR / 'server.mjs').exists():
                        subprocess.Popen([str(NODE_EXE), 'server.mjs'], cwd=str(BACKEND_DIR),
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                         creationflags=0x08000000)
                        logger.warning('Whale qqmusic backend restarted')
                if not LOGIN_REQUEST.exists():
                    continue
                LOGIN_REQUEST.unlink()
                asyncio.create_task(self.send_login_qr())
            except Exception as exc:
                logger.warning('Whale qqmusic login watcher failed: %s', type(exc).__name__)

    async def send_login_qr(self):
        """Push a fresh login QR to the owner's QQ and report the result."""
        payload = await self._qq_get('/login/qr?type=mobile')
        if not payload or not (payload.get('qrcode') or payload.get('qrimg')):
            payload = await self._qq_get('/login/qr')
        if not payload or not (payload.get('qrcode') or payload.get('qrimg')):
            return
        if payload.get('qrcode'):
            text = str(payload['qrcode'])
            if text.startswith('data:image'):
                raw = text.split(',', 1)[-1]
            else:
                try:
                    import io as _io
                    import qrcode as _qrcode
                    image = _qrcode.make(text)
                    buffer = _io.BytesIO()
                    image.save(buffer, format='PNG')
                    raw = base64.b64encode(buffer.getvalue()).decode()
                except Exception:
                    raw = ''
        else:
            raw = str(payload.get('qrimg') or '').split(',', 1)[-1]
        if not raw:
            return
        try:
            import io as _io
            from PIL import Image as _Image, ImageDraw as _Draw
            image = _Image.open(_io.BytesIO(base64.b64decode(raw))).convert('RGB')
            canvas = _Image.new('RGB', (image.width, image.height + 36), 'white')
            canvas.paste(image, (0, 0))
            _Draw.Draw(canvas).text((8, image.height + 10), 'QQ音乐App扫码登录 ' + time.strftime('%H:%M'), fill='black')
            buffer = _io.BytesIO()
            canvas.save(buffer, format='PNG')
            raw = base64.b64encode(buffer.getvalue()).decode()
        except Exception:
            pass
        platform = self.context.get_platform_inst('dafeiyu-qq')
        getter = getattr(platform, 'get_client', None) if platform is not None else None
        client = getter() if callable(getter) else None
        if client is None:
            return
        try:
            await client.call_action('send_private_msg', user_id=int(OWNER),
                                     message='QQ音乐登录二维码来了 2分钟内扫 过点就状态中心再发一次')
            await client.call_action('send_private_msg', user_id=int(OWNER), message=[
                {'type': 'image', 'data': {'file': 'base64://' + raw}},
            ])
            logger.info('Whale qqmusic QR sent to owner')
        except Exception as exc:
            logger.warning('Whale qqmusic QR send failed: %s', type(exc).__name__)
            return
        qrsig = str(payload.get('qrsig') or '')
        for _ in range(100):
            await asyncio.sleep(3)
            state = await self._qq_get('/login/check?qrsig=' + qrsig)
            if not state:
                continue
            if state.get('code') == 200:
                try:
                    await client.call_action('send_private_msg', user_id=int(OWNER),
                                             message='QQ音乐登录成功 以后点歌优先用QQ音乐')
                except Exception:
                    pass
                return
            if state.get('code') == 800:
                try:
                    await client.call_action('send_private_msg', user_id=int(OWNER),
                                             message='二维码过期了 状态中心再点一次「发二维码到QQ」')
                except Exception:
                    pass
                return

    async def _qq_get(self, path):
        """Call the local QQ Music backend.

        Args:
            path: Relative API path such as "/search?key=晴天".

        Returns:
            Parsed JSON, or None when the backend is unavailable.
        """
        try:
            timeout = aiohttp.ClientTimeout(total=25)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(QQ_BACKEND + path) as response:
                    return await response.json(content_type=None)
        except Exception as exc:
            logger.warning('Whale qqmusic backend failed: %s', type(exc).__name__)
            return None

    async def qq_login(self, event):
        """Send a QQ Music login QR and wait for the owner to scan it.

        Args:
            event: Incoming owner message event.
        """
        payload = await self._qq_get('/login/qr')
        if not payload or not payload.get('qrimg'):
            await event.send(event.plain_result('QQ音乐后端没起来 等会儿再试'))
            return
        raw = str(payload.get('qrimg') or '')
        data = raw.split(',', 1)[-1]
        path = _PACKAGE / 'data' / '_qqmusic_login.png'
        try:
            path.write_bytes(base64.b64decode(data))
        except Exception:
            await event.send(event.plain_result('二维码解码失败 再试一次'))
            return
        await event.send(MessageChain([Image.fromFileSystem(str(path))]))
        asyncio.create_task(self._qq_login_wait(event, str(payload.get('qrsig') or '')))

    async def _qq_login_wait(self, event, qrsig):
        """Poll the QQ Music login state and report the result.

        Args:
            event: Owner message event used for feedback.
            qrsig: QR session identifier.
        """
        for _ in range(100):
            await asyncio.sleep(3)
            state = await self._qq_get('/login/check?qrsig=' + qrsig)
            if not state:
                continue
            code = state.get('code')
            if code == 200:
                await event.send(event.plain_result('QQ音乐登录成功 以后点歌优先用QQ音乐'))
                logger.info('Whale qqmusic login saved uin=%s', state.get('uin'))
                return
            if code in (800, 801):
                await event.send(event.plain_result('二维码过期了 再说一次「扫码登录QQ音乐」'))
                return

    def _library_add(self, mid, title, artist, duration_ms, data, suffix='.m4a', source='qq'):
        """Store a downloaded song in the shared library.

        Args:
            mid: QQ Music song mid.
            title: Song title.
            artist: Singer names.
            duration_ms: Duration in milliseconds.
            data: Raw audio bytes.
            suffix: File suffix.
            source: Where the audio came from.

        Returns:
            The index entry that was written.
        """
        LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
        key = 'qq_' + re.sub(r'[^0-9a-zA-Z]', '', str(mid))[:12]
        safe = re.sub(r'[\\/:*?"<>|]', '_', str(title))[:80]
        target = LIBRARY_DIR / ('%s__%s%s' % (safe, key, suffix))
        target.write_bytes(data)
        try:
            index = json.loads(LIBRARY_INDEX.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            index = {}
        songs = [s for s in index.get('songs', []) if s.get('key') != key]
        entry = {'key': key, 'title': title, 'artist': artist,
                 'duration_ms': int(duration_ms or 0), 'file': target.name,
                 'added': int(time.time()), 'source': source}
        songs.append(entry)
        index['songs'] = songs
        tmp = LIBRARY_INDEX.with_suffix('.tmp')
        tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(LIBRARY_INDEX)
        return entry

    async def qq_play(self, event, query):
        """Try to play a song from QQ Music.

        Args:
            event: Incoming message event.
            query: Song request.

        Returns:
            True when a QQ Music song was sent.
        """
        health = await self._qq_get('/health')
        if not health or not health.get('ok'):
            return False
        result = await self._qq_get('/search?limit=8&key=' + _search_query(query).replace('&', ' '))
        songs = (result or {}).get('songs') or []
        if not songs:
            return False
        candidates = [{'position': i + 1, 'title': s.get('name', '') + ' ' + s.get('singers', ''),
                       'duration': '%d:%02d' % (int(s.get('interval') or 0) // 60, int(s.get('interval') or 0) % 60)}
                      for i, s in enumerate(songs)]
        ranked = _rank_candidates(candidates, query)
        if not ranked:
            return False
        logged = bool(health.get('logged'))
        if not logged:
            ranked = ranked[:2]
        song = None
        url = ''
        for position in ranked:
            candidate = songs[position - 1]
            for kind in (('320', '128') if logged else ('128',)):
                audio = await self._qq_get('/song/url?type=%s&mid=%s' % (kind, candidate.get('mid') or ''))
                url = (audio or {}).get('url') or ''
                if url:
                    song = candidate
                    break
            if song is not None:
                break
        if song is None and ranked:
            await asyncio.sleep(1)
            for position in ranked[:2]:
                candidate = songs[position - 1]
                for kind in (('320', '128') if logged else ('128',)):
                    audio = await self._qq_get('/song/url?type=%s&mid=%s' % (kind, candidate.get('mid') or ''))
                    url = (audio or {}).get('url') or ''
                    if url:
                        song = candidate
                        break
                if song is not None:
                    break
        if song is None or not url:
            return False
        data = None
        timeout = aiohttp.ClientTimeout(total=90)
        for attempt in range(2):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            logger.warning('Whale qqmusic download HTTP %s (attempt %s)', response.status, attempt + 1)
                            continue
                        data = await response.read()
                        break
            except Exception as exc:
                logger.warning('Whale qqmusic download failed: %s (attempt %s)', type(exc).__name__, attempt + 1)
                await asyncio.sleep(2)
        if not data:
            return False
        suffix = '.m4a'
        if str(url).lower().endswith('.mp3'):
            suffix = '.mp3'
        entry = self._library_add(song.get('mid'), song.get('name') or query,
                                  song.get('singers') or '', int(song.get('interval') or 0) * 1000,
                                  data, suffix)
        return await self.play_from_library(event, entry)

    async def play_from_library(self, event, song):
        """Send a cached song as a voice message.

        Args:
            event: Incoming message event.
            song: Library entry with a file and duration.

        Returns:
            True when the song was sent.
        """
        path = LIBRARY_DIR / str(song.get('file') or '')
        if not path.exists():
            return False
        clip = path.with_name('_voice_' + path.stem + '.m4a')
        limit = 295 if int(song.get('duration_ms') or 0) > 300_000 else 0
        args = [str(FFMPEG), '-y', '-i', str(path)]
        if limit:
            args += ['-t', str(limit)]
        args += ['-ac', '1', '-ar', '24000', '-b:a', '64k', str(clip)]
        process = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        try:
            if await process.wait() != 0 or not clip.exists():
                raise RuntimeError('voice conversion failed')
            await event.send(MessageChain([Record.fromFileSystem(clip)]))
            if not event.get_group_id():
                await event.send(MessageChain([File(name=path.name, file=str(path))]))
                add_sent(event.get_sender_id(), 2)
            self.last_play[event.unified_msg_origin] = time.time()
            self.song_times.setdefault(event.unified_msg_origin, []).append(time.time())
            self._remember_song(event, song.get('title') or song.get('name'),
                                song.get('artist') or song.get('singers'))
            logger.info('Whale music library hit: %s', song.get('title'))
            return True
        except Exception as exc:
            logger.warning('Whale music library send failed: %s', type(exc).__name__)
            await self.send_hint(event, '这首放不出来 换一首吧')
            return False
        finally:
            try:
                clip.unlink()
            except OSError:
                pass

    async def play_later(self, event, session, queries):
        """Pick one request from a short burst, then search and deliver it.

        Args:
            event: Incoming message event.
            session: Session identifier.
            queries: Song queries collected inside the window.
        """
        await asyncio.sleep(WINDOW_SECONDS)
        batch = self.pending.pop(session, None)
        if not batch:
            return
        now = time.time()
        if now - self.last_play.get(session, 0) < COOLDOWN_SECONDS:
            logger.info('Whale music: burst ignored by cooldown (%d requests)', len(batch))
            return
        history = [stamp for stamp in self.song_times.get(session, []) if now - stamp < 3600]
        self.song_times[session] = history
        if len(history) >= HOURLY_SONGS:
            logger.info('Whale music: hourly cap reached (%d)', len(history))
            await self.send_hint(event, '这个点歌额度先歇会儿 一小时后再来', gap=300)
            return
        raw = ''
        query = ''
        if batch:
            entry = batch[-1]
            if isinstance(entry, dict):
                raw = str(entry.get('raw') or '')
                query = str(entry.get('query') or '')
            else:
                raw = str(entry)
        if not query:
            query = await self._resolve_query(event, raw)
        if not query:
            if INTENT.search(raw):
                await self.send_hint(event, '想听啥 说个歌名')
            return
        cached = _match_library(query)
        if cached is not None and await self.play_from_library(event, cached):
            return
        await event.send(event.plain_result(random.choice(('行 找找', '等会儿', '我翻翻'))))
        if not event.get_group_id():
            add_sent(event.get_sender_id(), 1)
        version = bool(_version_profile(query)[1])
        if version:
            if await self.play_bilibili(event, query):
                return
            await self.send_hint(event, '这个版本没找到 换个说法试试')
            return
        else:
            if await self.qq_play(event, query):
                return
            if await self.play_bilibili(event, query):
                return
        await self.send_hint(event, '这首没找到 换个歌名试试')

    async def play_bilibili(self, event, query):
        """Search and deliver a song from Bilibili.

        Args:
            event: Incoming message event.
            query: The user's song request.

        Returns:
            True when the song was delivered.
        """
        plugin = self.music_plugin()
        if plugin is None:
            return False
        try:
            raw = await plugin.find_music_for_llm(event, _search_query(query))
            payload = json.loads(raw) if isinstance(raw, str) else {}
        except Exception as exc:
            logger.warning('Whale music search failed: %s', type(exc).__name__)
            return False
        candidates = payload.get('candidates') or []
        if payload.get('status') != 'candidates' or not candidates:
            return False
        position = _best_candidate(candidates, query)
        if position is None:
            return False
        try:
            note = random.choice(('行 给你放', '来了', '这首啊 听着', '喏 听听'))
            await plugin.deliver_music_for_llm(event, payload.get('search_id'), position, note=note)
            if not event.get_group_id():
                add_sent(event.get_sender_id(), 1)
            self.last_play[event.unified_msg_origin] = time.time()
            self.song_times.setdefault(event.unified_msg_origin, []).append(time.time())
            try:
                chosen = candidates[position - 1]
            except (IndexError, TypeError):
                chosen = {}
            self._remember_song(event, chosen.get('title') or query)
            logger.info('Whale music bilibili played %s', query)
            return True
        except Exception as exc:
            logger.warning('Whale music delivery failed: %s', type(exc).__name__)
            await self.send_hint(event, '这首放不出来 换一首吧')
            return False
        finally:
            event.stop_event()

    def _remember(self, event, text):
        """Keep a short per-session buffer of incoming text for context."""
        session = event.unified_msg_origin
        history = getattr(self, 'history', None)
        if not isinstance(history, dict):
            self.history = history = {}
        buffer = history.setdefault(session, [])
        try:
            name = str(event.get_sender_name() or '')
        except Exception:
            name = ''
        buffer.append({'name': name or str(event.get_sender_id()),
                       'text': str(text)[:120], 'at': time.time()})
        del buffer[:-12]

    def _recent_music_talk(self, session):
        """Return whether the last few incoming lines were about music."""
        history = getattr(self, 'history', None)
        if not isinstance(history, dict):
            return False
        recent = ' '.join(str(item.get('text') or '')
                          for item in history.get(session, [])[-5:-1])
        return any(word in recent for word in ('歌', '音乐', '听', '放', '唱'))

    def _context_request(self, event, text):
        """Return whether a short contextual line may be a play request."""
        if not CONTEXT_TRIGGER.search(text):
            return False
        last = getattr(self, 'last_song', {})
        if isinstance(last, dict) and last.get(event.unified_msg_origin):
            return True
        return self._recent_music_talk(event.unified_msg_origin)

    def _dialogue_context(self, event, current):
        """Build recent dialogue text for the resolver, preferring AstrBot history."""
        lines = []
        data = getattr(self, 'data', None)
        session = event.unified_msg_origin
        group = event.get_group_id()
        if data:
            if group:
                try:
                    with sqlite3.connect(data / 'dafeiyu_group_memory.db', timeout=1) as db:
                        rows = db.execute(
                            "SELECT sender_name, role, content FROM messages WHERE group_id = ? ORDER BY id DESC LIMIT 12",
                            (str(group),)).fetchall()
                    for sender_name, role, content in reversed(rows):
                        who = '大肥鱼' if role == 'assistant' else str(sender_name or '群友')
                        lines.append('%s：%s' % (who, str(content or '')[:100]))
                except sqlite3.Error:
                    pass
            else:
                user_id = 'dafeiyu-qq:FriendMessage:%s' % event.get_sender_id()
                try:
                    with sqlite3.connect(data / 'data_v4.db', timeout=1) as db:
                        row = db.execute("SELECT content FROM conversations WHERE user_id = ?",
                                         (user_id,)).fetchone()
                    if row and row[0]:
                        payload = json.loads(row[0])
                        for message in (payload if isinstance(payload, list) else [])[-12:]:
                            if not isinstance(message, dict):
                                continue
                            body = message.get('content')
                            if isinstance(body, list):
                                body = ' '.join(str(part.get('text') or '')
                                                for part in body if isinstance(part, dict))
                            body = str(body or '').strip()
                            if body:
                                who = '大肥鱼' if message.get('role') == 'assistant' else '对方'
                                lines.append('%s：%s' % (who, body[:100]))
                except (sqlite3.Error, ValueError, TypeError):
                    pass
        if len(lines) < 3:
            history = getattr(self, 'history', None)
            if isinstance(history, dict):
                for item in history.get(session, [])[-10:]:
                    lines.append('%s：%s' % (item.get('name') or '对方',
                                             str(item.get('text') or '')[:100]))
        lines = [line for line in lines if line.strip()]
        if current and (not lines or not lines[-1].endswith(str(current)[:100])):
            lines.append('当前：%s' % str(current)[:100])
        return '\n'.join(lines[-14:]) or '（无）'

    def _provider(self):
        """Return the chat provider used for intent resolution, or None."""
        try:
            return self.context.get_provider_by_id('deepseek-chat')
        except Exception:
            return None

    def _fallback_query(self, event, raw):
        """Resolve a request without the model, using recent song context."""
        query = _query(raw)
        last = getattr(self, 'last_song', {})
        last = last.get(event.unified_msg_origin) if isinstance(last, dict) else None
        last = last if isinstance(last, dict) else {}
        title = str(last.get('title') or '').strip()
        artist = str(last.get('artist') or '').strip()
        if query in ('这首', '那首', '这个', '那个', '就这个', '就它', '刚才那首',
                     '上一首', '换一首', '再来一首', '再放一首', '继续放'):
            query = ''
        if CONTEXT_CUES.search(raw):
            if any(word in raw for word in ('换', '再来', '继续', '再放')):
                if artist:
                    return artist
                if title:
                    return title
            if title:
                return (title + ' ' + artist).strip()
        return query

    def _needs_llm(self, raw, fallback):
        """Return whether the request needs contextual resolution."""
        if not fallback or CONTEXT_CUES.search(raw) or len(raw) > 24:
            return True
        return False

    async def _resolve_query(self, event, raw):
        """Resolve the song query from the message and recent conversation."""
        raw = str(raw or '').strip()
        fallback = self._fallback_query(event, raw)
        if not self._needs_llm(raw, fallback):
            return fallback
        provider = self._provider()
        if provider is None:
            return fallback
        last = getattr(self, 'last_song', {})
        last = last.get(event.unified_msg_origin) if isinstance(last, dict) else None
        last = last if isinstance(last, dict) else {}
        last_text = ' '.join(part for part in (str(last.get('title') or ''),
                                               str(last.get('artist') or '')) if part)
        prompt = ('最近对话：\n%s\n\n她刚放过的歌：%s\n当前消息：%s' % (
            self._dialogue_context(event, raw), last_text or '（还没放过）', raw[:200]))
        try:
            response = await asyncio.wait_for(
                provider.text_chat(prompt=prompt, system_prompt=RESOLVER_SYSTEM, contexts=[]),
                timeout=6.0,
            )
            text = str(getattr(response, 'completion_text', '') or '').strip()
            match = re.search(r'\{.*\}', text, re.S)
            if not match:
                return fallback
            data = json.loads(match.group(0))
        except Exception as exc:
            logger.info('Whale music resolver fallback: %s', type(exc).__name__)
            return fallback
        if not isinstance(data, dict) or not data.get('play'):
            return ''
        query = str(data.get('query') or '').strip().strip('"“”')
        query = re.sub(r'^(来一首|来首|放一首|放首|点歌|播放|搜索)\s*', '', query).strip()
        return query[:60] if query else fallback

    def _remember_song(self, event, title, artist=''):
        """Remember the last delivered song so context can refer to it."""
        if not title:
            return
        store = getattr(self, 'last_song', None)
        if not isinstance(store, dict):
            self.last_song = store = {}
        store[event.unified_msg_origin] = {'title': str(title)[:80],
                                           'artist': str(artist or '')[:60],
                                           'at': time.time()}

    @filter.event_message_type(filter.EventMessageType.ALL, priority=9800)
    async def on_message(self, event: AstrMessageEvent):
        if event.get_platform_id() != 'dafeiyu-qq':
            return
        if str(event.get_sender_id()) == str(event.get_self_id()):
            return
        if str(event.get_sender_id()) in PEER_AIS:
            return
        text = _plain_text(event)
        if not text:
            return
        self._remember(event, text)
        explicit = bool(INTENT.search(text))
        contextual = (not explicit) and self._context_request(event, text)
        if not (explicit or contextual):
            return
        logger.info('Whale music seen: group=%s addressed=%s text=%s',
                    event.get_group_id(), _addressed(event), text[:40])
        if not _addressed(event):
            return
        if str(event.get_sender_id()) == OWNER and len(text) > 50 and (
                'qm_keyst=' in text or 'qqmusic_key=' in text or ('uin=' in text and 'pgv_pvid=' in text)):
            event.stop_event()
            await self.save_qq_cookie(event, text.strip().strip("'\""))
            return
        if str(event.get_sender_id()) == OWNER and 'qq音乐cookie' in text.lower():
            cookie = re.sub(r'(?i).*?qq音乐cookie[:：\s]*', '', text, count=1).strip()
            event.stop_event()
            await self.save_qq_cookie(event, cookie)
            return
        if str(event.get_sender_id()) == OWNER and text.strip() in ('发码', '二维码', '要码', '扫码'):
            event.stop_event()
            await self.qq_login(event)
            return
        if str(event.get_sender_id()) == OWNER and '扫码' in text and 'qq音乐' in text.lower():
            event.stop_event()
            await self.qq_login(event)
            return
        if any(word in text for word in DISCUSSION_GUARD):
            return
        session = event.unified_msg_origin
        if time.time() - self.last_play.get(session, 0) < COOLDOWN_SECONDS:
            await self.send_hint(event, '刚放过一首 等会儿再点', gap=60)
            return
        logger.info('Whale music request: %s (%s)', text[:60], 'group' if event.get_group_id() else 'private')
        resolved = ''
        if contextual:
            resolved = await self._resolve_query(event, text)
            if not resolved:
                return
        bucket = self.pending.setdefault(session, [])
        bucket.append({'raw': text[:200], 'query': resolved})
        if len(bucket) == 1:
            asyncio.create_task(self.play_later(event, session, bucket))
        event.stop_event()
