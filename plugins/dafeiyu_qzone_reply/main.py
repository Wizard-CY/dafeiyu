import asyncio
import json
import random
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from astrbot.api import logger
from astrbot.api.star import Star, register

TZ = timezone(timedelta(hours=8))
SELF = '1000000000'
MAX_PER_RUN = 3
MAX_PER_DAY = 12
POLL_SECONDS = 180
LOOKBACK_DAYS = 7

PROMPT = (
    '你在回复自己 QQ 空间动态下面的评论。像网友一样回一句，10~30 字，最多两句；'
    '口语、放松，不要客服腔，不要长篇解释，不要反问连击。'
    '可以用 1~2 个 emoji 让语气更软，但别堆。对不认识的人礼貌些；对主人可以嘴硬一点。'
    '回复里不要提「主人」「家人」「群友」，也不要写任何人的账号或身份。'
    '不要透露私聊内容，不要编造现实经历。只输出回复正文。'
)

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36'


@register('dafeiyu_qzone_reply', 'Local', 'Replies once per user under her own Qzone posts', '1.0.0')
class QzoneReply(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.state = self.data / 'dafeiyu_qzone_reply.json'
        self.flag = self.data / 'dafeiyu_qzone_reply.flag'
        self.test_flag = self.data / 'dafeiyu_qzone_reply.test'
        self.task = None

    async def initialize(self):
        self.task = asyncio.create_task(self.loop())

    async def loop(self):
        await asyncio.sleep(40)
        while True:
            try:
                forced = self.flag.exists()
                if forced:
                    self.flag.unlink()
                if self.test_flag.exists():
                    mode = self.test_flag.read_text(encoding='utf-8-sig').strip()
                    self.test_flag.unlink()
                    if mode == 'cleanup':
                        await self.cleanup()
                    else:
                        await self.roundtrip()
                await self.run_once(verbose=forced)
            except Exception as exc:
                logger.warning('Whale qzone reply loop failed: %s', type(exc).__name__)
            await asyncio.sleep(POLL_SECONDS)

    def gtk(self, cookie):
        """Compute Qzone g_tk from the login cookie.

        Args:
            cookie: Raw cookie string.

        Returns:
            Integer g_tk value.
        """
        skey = ''
        for key in ('p_skey', 'skey', 'media_p_skey'):
            match = re.search(r'(?:^|;\s*)' + key + r'=([^;]+)', cookie)
            if match:
                skey = match.group(1)
                break
        value = 5381
        for ch in skey:
            value += (value << 5) + ord(ch)
        return value & 0x7FFFFFFF

    async def cookie(self):
        platform = self.context.get_platform_inst('dafeiyu-qq')
        client = platform.get_client() if platform is not None else None
        if client is None:
            return ''
        merged = {}
        for domain in ('user.qzone.qq.com', 'qzone.qq.com', 'qq.com'):
            try:
                part = (await client.get_cookies(domain=domain) or {}).get('cookies', '') or ''
            except Exception:
                part = ''
            for pair in part.split(';'):
                key, _, value = pair.partition('=')
                if key.strip() and value.strip():
                    merged[key.strip()] = value.strip()
        return '; '.join(f'{key}={value}' for key, value in merged.items())

    def _headers(self, cookie):
        return {
            'cookie': cookie,
            'user-agent': UA,
            'referer': 'https://user.qzone.qq.com/%s/main' % SELF,
        }

    def fetch_recent(self, cookie):
        """List her recent posts from the message list API.

        Args:
            cookie: Raw cookie string.

        Returns:
            Parsed payload dict or None.
        """
        gtk = self.gtk(cookie)
        url = 'https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6'
        params = {
            'uin': SELF, 'pos': 0, 'num': 20, 'g_tk': gtk, 'format': 'json',
            'inCharset': 'utf-8', 'outCharset': 'utf-8', 'ref': 'feeds', 'feedversion': '1',
        }
        res = requests.get(url, params=params, headers=self._headers(cookie), timeout=20)
        return self._parse(res.text or '')

    def fetch_comments(self, cookie, tid):
        """Fetch comments of one post.

        Args:
            cookie: Raw cookie string.
            tid: Post id.

        Returns:
            List of comment dicts.
        """
        gtk = self.gtk(cookie)
        url = 'https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msgdetail_v6'
        params = {
            'uin': SELF, 'pos': 0, 'num': 50, 'tid': tid, 'g_tk': gtk, 'format': 'fs',
            'inCharset': 'utf-8', 'outCharset': 'utf-8', 'ref': 'feeds', 'feedversion': '1',
        }
        res = requests.get(url, params=params, headers=self._headers(cookie), timeout=20)
        payload = self._parse(res.text or '')
        if not isinstance(payload, dict):
            return []
        return payload.get('commentlist') or payload.get('comments') or []

    def post_comment(self, cookie, tid, text):
        """Post one comment under her own post.

        Args:
            cookie: Raw cookie string.
            tid: Post id.
            text: Comment text.

        Returns:
            True when the API reported success.
        """
        gtk = self.gtk(cookie)
        url = ('https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_addcomment_ugc'
               '?&g_tk=%d' % gtk)
        data = {
            'g_tk': str(gtk), 'topicId': '%s_%s__1' % (SELF, tid), 'feedsType': '100',
            'inCharset': 'utf-8', 'outCharset': 'utf-8', 'plat': 'qzone', 'source': 'ic',
            'hostUin': SELF, 'isSignIn': '', 'platformid': '50', 'uin': SELF, 'format': 'fs',
            'ref': 'feeds', 'content': text, 'richval': '', 'richtype': '', 'private': '0',
            'paramstr': '1', 'qzreferrer': 'https://user.qzone.qq.com/%s/infocenter?via=toolbar' % SELF,
            'rand': str(int(time.time() * 1000)) + str(random.randint(100, 999)),
        }
        headers = self._headers(cookie)
        headers['content-type'] = 'application/x-www-form-urlencoded;charset=UTF-8'
        res = requests.post(url, data=data, headers=headers, timeout=20)
        return self._ok(res.text or '')

    def delete_comment(self, cookie, tid, comment_id, comment_uin):
        """Delete one comment under her own post.

        Args:
            cookie: Raw cookie string.
            tid: Post id.
            comment_id: Comment id.
            comment_uin: Author uin.

        Returns:
            True when the API reported success.
        """
        gtk = self.gtk(cookie)
        url = ('https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_delcomment_ugc'
               '?&g_tk=%d' % gtk)
        data = {
            'g_tk': str(gtk), 'topicId': '%s_%s__1' % (SELF, tid), 'commentId': str(comment_id),
            'commentUin': str(comment_uin), 'uin': SELF, 'format': 'fs',
            'qzreferrer': 'https://user.qzone.qq.com/%s/infocenter?via=toolbar' % SELF,
        }
        res = requests.post(url, data=data, headers=self._headers(cookie), timeout=20)
        return self._ok(res.text or '')

    def _parse(self, text):
        match = re.search(r'_Callback\(\s*(\{.*\})\s*\)\s*;?\s*$', text, re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except ValueError:
                return None
        try:
            return json.loads(text)
        except ValueError:
            return None

    def _ok(self, text):
        payload = self._parse(text)
        if isinstance(payload, dict):
            return str(payload.get('code')) == '0'
        return '"code":0' in text.replace(' ', '')

    def load_state(self):
        try:
            return json.loads(self.state.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def save_state(self, data):
        try:
            self.state.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            logger.warning('Whale qzone reply state write failed: %s', type(exc).__name__)

    async def compose(self, nickname, content):
        provider = self.context.get_provider_by_id('deepseek-chat')
        if provider is None:
            return ''
        try:
            from data.plugins.dafeiyu_group.helper import STYLE, character
            system = character() + '\n' + STYLE + '\n' + PROMPT
        except Exception:
            system = PROMPT
        prompt = '评论者：%s\n评论内容：%s\n请回复。' % (nickname, content[:120])
        try:
            resp = await provider.text_chat(prompt=prompt, system_prompt=system, contexts=[])
            text = str(resp.completion_text or '').strip()
        except Exception as exc:
            logger.warning('Whale qzone reply compose failed: %s', type(exc).__name__)
            return ''
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'@\S+', '', text)
        text = re.sub(r'^(回复|评论|答|回答)[:：]\s*', '', text)
        for phrase, replacement in (('我一直在', '我在'), ('我一直都在', '我在'), ('一直在线', '在线'), ('随时找我', '找我')):
            text = text.replace(phrase, replacement)
        text = text.strip('“”"\'')
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:80]

    async def run_once(self, verbose=False):
        cookie = await self.cookie()
        if not cookie:
            if verbose:
                logger.warning('Whale qzone reply: cookie unavailable')
            return
        posts = await asyncio.to_thread(self.fetch_recent, cookie)
        if not isinstance(posts, dict):
            if verbose:
                logger.info('Whale qzone reply: msglist unavailable')
            return
        msgs = posts.get('msglist') or []
        if verbose:
            logger.info('Whale qzone reply: posts=%d', len(msgs))
        cutoff = time.time() - LOOKBACK_DAYS * 86400
        try:
            blocked = json.loads((self.data / 'dafeiyu_blocked.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            blocked = {}
        state = self.load_state()
        day = datetime.now(TZ).date().isoformat()
        if state.get('day') != day:
            # Keep per-post reply history; only the daily counter resets.
            state['day'] = day
            state['count'] = 0
            state.setdefault('posts', {})
        sent = 0
        for post in msgs[:3]:
            tid = str(post.get('tid') or '')
            created = 0.0
            for key in ('created_time', 'createTime'):
                value = post.get(key)
                try:
                    created = float(value)
                    break
                except (TypeError, ValueError):
                    continue
            if not tid or created < cutoff:
                continue
            comments = await asyncio.to_thread(self.fetch_comments, cookie, tid)
            if verbose:
                logger.info('Whale qzone reply: tid=%s cmt=%d first=%s', tid, len(comments),
                            json.dumps(comments[0], ensure_ascii=False)[:400] if comments else '')
            if not comments:
                continue
            entry = state['posts'].setdefault(tid, {'uins': [], 'names': {}})
            entry.setdefault('uins', [])
            entry.setdefault('names', {})
            entry.setdefault('comments', [])
            for item in comments:
                if state['count'] >= MAX_PER_DAY or sent >= MAX_PER_RUN:
                    break
                uin = str(item.get('uin') or '')
                name = str(item.get('name') or item.get('nickname') or uin)
                content = str(item.get('content') or '').strip()
                cid = str(item.get('tid') or item.get('commentid') or item.get('id') or '')
                if not uin or uin == SELF or uin in blocked or not content or uin in entry['uins']:
                    continue
                if cid and cid in entry['comments']:
                    continue
                if len(re.findall(r'\d', content)) >= 11:
                    continue
                reply = await self.compose(name, content)
                if not reply:
                    continue
                body = '回复 %s：%s' % (name, reply)
                ok = await asyncio.to_thread(self.post_comment, cookie, tid, body)
                if verbose:
                    logger.info('Whale qzone reply: -> %s ok=%s text=%s', name, ok, body[:60])
                if not ok:
                    continue
                entry['uins'].append(uin)
                entry['names'][uin] = name
                if cid:
                    entry['comments'].append(cid)
                state['count'] += 1
                sent += 1
                self.save_state(state)
                await asyncio.sleep(2)
        self.save_state(state)

    async def cleanup(self):
        """Delete every self-test comment left on her newest posts."""
        cookie = await self.cookie()
        if not cookie:
            return
        posts = await asyncio.to_thread(self.fetch_recent, cookie)
        msgs = (posts or {}).get('msglist') or []
        for post in msgs[:3]:
            tid = str(post.get('tid') or '')
            for _ in range(6):
                comments = await asyncio.to_thread(self.fetch_comments, cookie, tid)
                targets = [c for c in comments if '自测评论-' in str(c.get('content') or '')]
                if not targets:
                    break
                item = targets[0]
                cid = str(item.get('tid') or '')
                ok = await asyncio.to_thread(self.delete_comment, cookie, tid, cid, SELF)
                logger.info('Whale qzone reply cleanup: tid=%s cid=%s ok=%s', tid, cid, ok)
                if not ok:
                    break
                await asyncio.sleep(1)

    async def roundtrip(self):
        """Post a throwaway comment, read it back, then delete it."""
        cookie = await self.cookie()
        if not cookie:
            logger.warning('Whale qzone reply roundtrip: no cookie')
            return
        posts = await asyncio.to_thread(self.fetch_recent, cookie)
        msgs = (posts or {}).get('msglist') or []
        if not msgs:
            logger.warning('Whale qzone reply roundtrip: no posts')
            return
        tid = str(msgs[0].get('tid') or '')
        mark = '自测评论-%d' % int(time.time())
        ok = await asyncio.to_thread(self.post_comment, cookie, tid, mark)
        logger.info('Whale qzone reply roundtrip: post ok=%s tid=%s', ok, tid)
        comments = await asyncio.to_thread(self.fetch_comments, cookie, tid)
        logger.info('Whale qzone reply roundtrip: sample=%s', json.dumps(comments[0], ensure_ascii=False)[:500] if comments else '')
        hit = [c for c in comments if mark in str(c.get('content') or '')]
        logger.info('Whale qzone reply roundtrip: readback=%d comments=%d', len(hit), len(comments))
        for item in hit:
            candidates = []
            for key in ('commentid', 'id', 'cid', 'comment_id', 'tid', 'create_time'):
                value = item.get(key)
                if value not in (None, '', 0):
                    candidates.append(str(value))
            for cid in candidates:
                deleted = await asyncio.to_thread(self.delete_comment, cookie, tid, cid, SELF)
                logger.info('Whale qzone reply roundtrip: delete cid=%s ok=%s', cid, deleted)
                if deleted:
                    break

    async def terminate(self):
        if self.task:
            self.task.cancel()
