import asyncio
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from astrbot.api import logger
from astrbot.api.star import Star, register

TZ = timezone(timedelta(hours=8))
OWNER = '1000000001'
MAX_FACTS = 40
MAX_NEW = 4


@register('dafeiyu_memory', 'Local', 'Manual private/group memory digest', '1.1.0')
class MemoryDigest(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.db = self.data / 'data_v4.db'
        self.memory = self.data / 'dafeiyu_memory.md'
        self.state = self.data / 'dafeiyu_memory_state.json'
        self.task = None

    async def initialize(self):
        self.task = asyncio.create_task(self.worker())

    async def worker(self):
        """Poll for a manual trigger written by the status window."""
        await asyncio.sleep(20)
        flag = self.data / 'dafeiyu_memory.flag'
        while True:
            try:
                saved = json.loads(self.state.read_text(encoding='utf-8')) if self.state.exists() else {}
            except (OSError, ValueError):
                saved = {}
            today = datetime.now(TZ).date().isoformat()
            if (datetime.now(TZ).hour >= 22 and saved.get('last_auto_day') != today
                    and not flag.exists()):
                try:
                    private_added, group_added = await self.digest()
                    saved.update(last_auto_day=today, last_run=datetime.now(TZ).strftime('%Y-%m-%d %H:%M'),
                                 private_added=private_added, group_added=group_added)
                    self.state.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
                    logger.info('Whale memory auto digest: private %d, groups %d', private_added, group_added)
                except Exception as exc:
                    logger.error('Whale memory auto digest failed: %s', type(exc).__name__)
                    saved['last_auto_day'] = today
                    try:
                        self.state.write_text(json.dumps(saved, ensure_ascii=False), encoding='utf-8')
                    except OSError:
                        pass
                await asyncio.sleep(600)
            if flag.exists():
                try:
                    flag.unlink()
                except OSError:
                    pass
                try:
                    private_added, group_added = await self.digest()
                    self.state.write_text(
                        json.dumps(
                            {
                                'last_run': datetime.now(TZ).strftime('%Y-%m-%d %H:%M'),
                                'private_added': private_added,
                                'group_added': group_added,
                            },
                            ensure_ascii=False,
                        ),
                        encoding='utf-8',
                    )
                except Exception as exc:
                    logger.error('Whale memory digest failed: %s', type(exc).__name__)
                    self.state.write_text(
                        json.dumps({'last_run': datetime.now(TZ).strftime('%Y-%m-%d %H:%M'), 'error': type(exc).__name__}, ensure_ascii=False),
                        encoding='utf-8',
                    )
            await asyncio.sleep(10)

    async def remember(self, path, prompt, history_lines, max_new=MAX_NEW):
        """Ask the model for new facts and append the unique ones to a memory file.

        Args:
            path: Memory markdown file to append to.
            prompt: Instruction suffix describing what to extract.
            history_lines: Transcript lines given to the model.
            max_new: Upper bound of new facts kept per run.

        Returns:
            Number of facts appended.
        """
        if not history_lines:
            return 0
        known, raw = ([], '')
        if path.exists():
            raw = path.read_text(encoding='utf-8')
            known = [line.strip() for line in raw.splitlines() if line.strip().startswith('-')]
        provider = self.context.get_provider_by_id('deepseek-chat')
        existing = ''
        if known:
            existing = '\n已有记忆（意思相同就不要重复，只输出真正新增的）：\n' + '\n'.join(item[2:].split('] ')[-1] for item in known[-20:])
        response = await provider.text_chat(
            prompt=prompt + existing + '\n<chat>\n' + '\n'.join(history_lines) + '\n</chat>',
            system_prompt='你是一个只做记忆整理的工具，用简洁中文输出事实列表。',
            contexts=[],
        )
        known_texts = [item[2:].split('] ', 1)[-1] for item in known]
        if not str(response.completion_text or '').strip():
            logger.warning('Whale memory digest got an empty model reply for %s', Path(path).name)
        added = []
        for fact in str(response.completion_text).splitlines():
            fact = fact.strip(' -•\t。')
            fact = re.sub(r'^(记忆|事实|摘要|新增)[:：]\s*', '', fact)
            if not fact or fact == '无' or len(fact) > 40:
                continue
            grams = {fact[i:i + 2] for i in range(len(fact) - 1)}
            duplicate = False
            for item in known_texts + added:
                if fact == item or fact[:8] == item[:8]:
                    duplicate = True
                    break
                other = {item[i:i + 2] for i in range(len(item) - 1)}
                if grams and other and len(grams & other) / min(len(grams), len(other)) >= 0.6:
                    duplicate = True
                    break
            if len(fact) < 6 or any(word in fact for word in ('升级', '顶嘴', '断电', '点名', '缺勤', '没来', 'xeepseek', '配置', 'token', '渠道', '签到', '网址', '招牌', '货源', '转生', '换店', '静默', '十一点', 'TTS', '插件', '语音合成', '放不了', '不能放歌', '不会放歌', 'Grok', '支付宝', '付款')):
                continue
            if duplicate or fact in raw:
                continue
            added.append(fact)
            if len(added) >= max_new:
                break
        if not added:
            return 0
        stamp = datetime.now(TZ).strftime('%m-%d')
        body = raw.rstrip() + '\n' if raw.strip() else '# 大肥鱼记住的事\n\n'
        body += ''.join(f'- [{stamp}] {fact}\n' for fact in added)
        kept = [line for line in body.splitlines() if line.strip()]
        if 'group_memory' in path.name:
            # Keep one nickname line per group instead of piling up "新增" rows.
            collapsed = []
            names = []
            latest = ''
            for line in kept:
                match = re.match(r'- \[([^\]]+)\] (常现群友新增|常现群友|常出现昵称|常见昵称)[：:]\s*(.+)', line)
                if not match:
                    collapsed.append(line)
                    continue
                latest = max(latest, match.group(1))
                names.extend(part.strip() for part in match.group(3).split('、') if part.strip())
            if names:
                unique = []
                for name in names:
                    if name not in unique:
                        unique.append(name)
                collapsed.insert(1, '- [%s] 常出现昵称：%s' % (
                    latest or datetime.now(TZ).strftime('%m-%d'), '、'.join(unique)))
            kept = collapsed
        path.write_text('\n'.join(kept[-MAX_FACTS:]) + '\n', encoding='utf-8')
        return len(added)

    async def digest_friends(self):
        """Build a separate memory file for each recently active friend."""
        rows = []
        try:
            with sqlite3.connect(self.db) as db:
                rows = db.execute(
                    "SELECT user_id, content FROM conversations WHERE user_id LIKE '%:FriendMessage:%' ORDER BY updated_at DESC LIMIT 8"
                ).fetchall()
        except sqlite3.Error:
            return 0
        total = 0
        for user_id, content in rows:
            qq = str(user_id).rsplit(':', 1)[-1]
            if qq == OWNER:
                continue
            try:
                history = json.loads(content or '[]')
            except ValueError:
                continue
            lines = []
            for message in history[-30:]:
                body = message.get('content')
                if isinstance(body, list):
                    body = ' '.join(str(p.get('text', '')) for p in body if isinstance(p, dict) and p.get('type') == 'text')
                body = re.sub(r'<system_reminder>.*?</system_reminder>', '', str(body or '')).strip()
                if body:
                    lines.append(('对方' if message.get('role') == 'user' else '我') + '：' + body[:200])
            if len(lines) < 6:
                continue
            folder = self.data / 'memory'
            folder.mkdir(exist_ok=True)
            total += await self.remember(
                folder / f'friend_{qq}.md',
                '下面是这位好友和大肥鱼的聊天记录。只提炼「关于这位好友」的长期有用信息，最多 4 条，每条不超过 30 字：'
                '怎么称呼、稳定偏好、正在做的事、说定的约定。不要记录一次性寒暄、情绪、隐私敏感信息（住址、账号、财务、健康）；''也不要记录对方在哪儿、去了哪、行程和具体地点；'
                '不要记录大肥鱼自己的设定或说过的话；没有值得记的就只输出「无」。每行一条，不要编号、不要解释。',
                lines,
            )
        logger.info('Whale friend memory digest added %d facts', total)
        return total

    def group_targets(self):
        """Return registered groups as (gid, display name) pairs."""
        try:
            data = json.loads((self.data / 'dafeiyu_groups.json').read_text(encoding='utf-8'))
        except (OSError, ValueError, AttributeError):
            data = {}
        if not isinstance(data, dict):
            return []
        targets = []
        for gid, info in data.items():
            if not isinstance(info, dict):
                continue
            name = str(info.get('name') or info.get('original') or ('群 ' + str(gid)))
            targets.append((str(gid), name))
        return targets

    async def digest_groups(self):
        """Extract durable facts for every registered group into its own memory file."""
        db_path = self.data / 'dafeiyu_group_memory.db'
        if not db_path.exists():
            return 0
        total = 0
        for gid, label in self.group_targets():
            with sqlite3.connect(db_path) as db:
                rows = db.execute(
                    'SELECT sender_name, sender_id, role, content FROM messages WHERE group_id=? ORDER BY id DESC LIMIT 80',
                    (gid,),
                ).fetchall()
            lines = [
                f'{name}（QQ {sender_id}）({role})：{content[:160]}'
                for name, sender_id, role, content in reversed(rows)
                if content and not str(content).startswith(('[非文字消息]', '[图片]', '[表情]'))
            ]
            if len(lines) < 8:
                continue
            prompt = (
                '下面是群「' + label + '」的聊天。只提炼「在这个群里长期有用」的信息，最多 4 条，每条不超过 30 字：'
                '常出现的群友昵称（照抄原文）、大家在聊的稳定话题、群里对大肥鱼的称呼或规矩。'
                '不要记录隐私（真实姓名、住址、账号、财务、健康、感情细节）、不要记录一次性寒暄和玩笑、'
                '不要记录大肥鱼自己的话；没有值得记的就只输出「无」。每行一条，不要编号、不要解释。'
            )
            count = await self.remember(self.data / f'dafeiyu_group_memory_{gid}.md', prompt, lines)
            logger.info('Whale group memory digest %s added %d facts', gid, count)
            total += count
        return total

    async def digest(self):
        """Extract durable facts from the latest private chat and append new ones."""
        with sqlite3.connect(self.db) as db:
            row = db.execute(
                'SELECT content FROM conversations WHERE user_id LIKE ? ORDER BY updated_at DESC LIMIT 1',
                ('%' + OWNER + '%',),
            ).fetchone()
        history = json.loads(row[0]) if row and row[0] else []
        lines = []
        for message in history[-40:]:
            content = message.get('content')
            if isinstance(content, list):
                content = ' '.join(str(p.get('text', '')) for p in content if isinstance(p, dict) and p.get('type') == 'text')
            text = re.sub(r'<system_reminder>.*?</system_reminder>', '', str(content or '')).strip()
            if text:
                lines.append(('主人' if message.get('role') == 'user' else '大肥鱼') + '：' + text[:200])
        count = await self.remember(
            self.memory,
            '下面是主人和大肥鱼最近的私聊记录。只提炼「关于主人」的长期有用信息，最多 4 条，每条不超过 30 字：'
            '称呼与身份、稳定偏好、作息或饮食习惯、长期在做的事、和你说定的约定。'
            '不要记录一次性的当下事件、情绪、机器人自己的外观或设定、你自己说过的话、聊天工具本身；''也不要记录「升级、顶嘴权、断电、熬夜」这类内部安排——这些话题提过就该翻篇。'
            '人名、软件名等专有名词必须照抄原文，不要改写或音译；不要记密码、密钥、账号、住址、财务、健康等敏感信息；'
            '不要编造，没有值得记的就只输出「无」。每行一条，不要编号、不要解释。',
            lines,
        )
        logger.info('Whale memory digest added %d facts', count)
        group_added = await self.digest_groups()
        friend_added = await self.digest_friends()
        peer_added = await self.digest_peer_style()
        return count, group_added + friend_added + peer_added

    async def digest_peer_style(self):
        """Learn expression habits from other 大肥鱼-like AIs, never their persona."""
        db_path = self.data / 'dafeiyu_group_memory.db'
        if not db_path.exists():
            return 0
        with sqlite3.connect(db_path) as db:
            rows = db.execute(
                "SELECT sender_name, content FROM messages WHERE role='user' AND (sender_name LIKE ? OR sender_name LIKE ?) ORDER BY id DESC LIMIT 120",
                ('%大肥鱼%', '%鲸%'),
            ).fetchall()
        lines = [f'{name}: {content[:120]}' for name, content in reversed(rows) if content and not str(content).startswith(('[图片]', '[表情]', '[非文字消息]'))]
        if len(lines) < 8:
            return 0
        try:
            provider = self.context.get_provider_by_id('deepseek-chat')
            response = await provider.text_chat(
                prompt='<peer_chat>\n' + '\n'.join(lines[-60:]) + '\n</peer_chat>\n请提炼可以借鉴的表达习惯。',
                system_prompt=(
                    '你在帮「大肥鱼」观察群里其他同名的 AI 是怎么说话的。只提炼 2-3 条**表达方式**层面的建议，'
                    '每条不超过 25 字，用「可以……」开头，例如「可以用一本正经的胡扯接戳一戳」。'
                    '只允许学句式、幽默、比喻、接梗方式；禁止建议撒娇、卖萌、讨好、叫主人/哥哥、降低傲娇、'
                    '复制她们的自我介绍或身份说法。只学说话方式，不学人设和立场。没有值得学的就只输出「无」。'
                    '每行一条，不要编号、不要解释。'
                ),
                contexts=[],
                func_tool=None,
            )
        except Exception as exc:
            logger.warning('Whale peer style digest failed: %s', type(exc).__name__)
            return 0
        banned = ('撒娇', '卖萌', '讨好', '主人', '哥哥', '老公', '抱抱', '贴贴', '亲亲', '呜呜',
              'API', 'api', '后端', '接口', '插件', 'token', '服务器', '部署', '调试')
        facts = []
        for raw_line in str(getattr(response, 'completion_text', '') or '').splitlines():
            fact = raw_line.strip().lstrip('-•').strip()
            if not fact or fact == '无' or fact.startswith('#'):
                continue
            if len(fact) > 40:
                continue
            if any(word in fact for word in banned):
                continue
            facts.append(fact)
            if len(facts) >= 3:
                break
        if not facts:
            return 0
        target = self.data / 'dafeiyu_peer_style.md'
        stamp = datetime.now(TZ).strftime('%m-%d')
        existing = target.read_text(encoding='utf-8') if target.exists() else '# 可借鉴的同类表达（只学表达方式，不学人设）\n'
        old_lines = [line[2:].split('] ', 1)[-1].strip() for line in existing.splitlines() if line.startswith('- [')]
        fresh = []
        for fact in facts:
            grams = {fact[i:i + 2] for i in range(len(fact) - 1)}
            repeated = False
            for old in old_lines:
                other = {old[i:i + 2] for i in range(len(old) - 1)}
                if grams and other and len(grams & other) / min(len(grams), len(other)) >= 0.5:
                    repeated = True
                    break
            if not repeated:
                fresh.append(fact)
        if not fresh:
            return 0
        body = existing.rstrip() + '\n' + ''.join(f'- [{stamp}] {fact}\n' for fact in fresh)
        kept = [line for line in body.splitlines() if line.strip()]
        target.write_text('\n'.join(kept[-10:]) + '\n', encoding='utf-8')
        logger.info('Whale peer style notes added %d', len(fresh))
        return len(fresh)

    async def terminate(self):
        if self.task:
            self.task.cancel()
