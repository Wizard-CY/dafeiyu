import json
import random
import re
import time
from pathlib import Path

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.message_components import Image, Plain
from astrbot.api.star import Star, register
from data.plugins.dafeiyu_group.helper import decorate, battle, character, STYLE, vibe, mood_jitter, rhythm, clock, length_hint, collected_stickers
from data.plugins.dafeiyu_quota.main import add_sent
from data.plugins.dafeiyu_guard import armor
from sys import maxsize

OWNER_QQ = '1000000001'
PRAISE_PATTERN = re.compile(
    r'(?:你|哦鲸鲸|大肥鱼).{0,6}(?:真|好|最|太|挺|很|超)?(?:可爱|漂亮|好看|萌|美)'
    r'|(?:可爱|漂亮|好看|萌|美).{0,4}(?:你|哦鲸鲸|大肥鱼)'
    r'|(?:好可爱|真可爱|太可爱|小可爱)'
)
TSUN_PROMPT = (
    '\n【临时傲娇模式】刚被夸可爱/漂亮，心里受用但嘴上别扭：'
    '可以回「哼，我才不会因为你夸我两句就把饭分给你吃呢…」这种语气，'
    '一两句就收，别撒娇、别肉麻、别一直演。对方若继续夸可以再别扭一下；'
    '两轮没有新的夸奖就自然恢复正常。'
)

FISH_STICKER_DIR = Path(__file__).resolve().parents[2] / 'collected_stickers' / '大肥鱼表情包'
SAFE_REPLIES = ('这个就不聊了 换一个', '私人问题跳过', '问点别的呗', '这个真不能说 换一个', '我这人不聊这个')

@register('dafeiyu_style', 'Local', 'Natural private chat and contextual stickers', '1.2.0')
class Style(Star):
    @filter.on_llm_request()
    async def apply_character(self, event, req):
        if event.get_platform_id() == 'dafeiyu-qq' and not event.get_group_id():
            try:
                if any(type(part).__name__ == 'Image' for part in event.get_messages()):
                    if getattr(self, 'sticker_collector', None) is None:
                        from data.plugins.dafeiyu_stickers.main import StickerCollect
                        self.sticker_collector = StickerCollect(self.context)
                    await self.sticker_collector.collect(event)
            except Exception as exc:
                logger.info('Whale private sticker collection skipped: %s', type(exc).__name__)
            text_now = str(getattr(event, 'message_str', '') or '')
            praise = bool(PRAISE_PATTERN.search(text_now)) and not any(word in text_now for word in ('不可爱', '哪里可爱', '可爱个', '不漂亮'))
            states = getattr(self, 'praise_rounds', None)
            if states is None:
                states = self.praise_rounds = {}
            key = str(getattr(event, 'unified_msg_origin', '') or event.get_sender_id())
            active = False
            if praise:
                states[key] = 2
                active = True
            elif states.get(key, 0) > 0:
                active = True
                states[key] -= 1
                if states[key] <= 0:
                    states.pop(key, None)
            req.system_prompt = (req.system_prompt or '') + '\n' + character() + '\n' + STYLE + '\n' + vibe() + '\n' + mood_jitter() + '\n' + rhythm(text_now) + '\n' + length_hint(text_now)
            if active:
                req.system_prompt += TSUN_PROMPT
            req.system_prompt += '\n你偶尔会发语音条和表情包（被问就说「偶尔会发」，别承诺「这就发」「马上到」「稍后发」，不会唱歌，但有人点歌就顺手搜来放。'
            req.func_tool = None
            req.system_prompt += '\n' + clock()
            sender = str(event.get_sender_id())
            base = Path(__file__).resolve().parents[2]
            # 批阅通过的关系画像优先；没有才退回原来的条目式记忆。
            published = base / 'profiles' / 'published' / (
                'owner.md' if sender == OWNER_QQ else 'friend_' + sender + '.md')
            if published.exists():
                text = '\n'.join(
                    line for line in published.read_text(encoding='utf-8').splitlines()
                    if line.strip() and not line.startswith('#') and not line.startswith('_')
                )[-1000:]
                if text:
                    req.system_prompt += (
                        '\n# 你心里对这个人的整体印象（主人批阅过的，只对这个人用，'
                        '别讲给别人，也别主动复述）\n' + text)
            else:
                if sender == OWNER_QQ:
                    memory = base / 'dafeiyu_memory.md'
                    label = '# 你记得的关于主人的事（只在私聊用；不要主动罗列，不要带进群聊，也不要讲给别人）'
                else:
                    memory = base / 'memory' / ('friend_' + sender + '.md')
                    label = '# 你记得的关于这位聊天对象的事（只对这个人用，不要讲给其他任何人，也不要主动罗列）'
                if memory.exists():
                    text = '\n'.join(
                        line for line in memory.read_text(encoding='utf-8').splitlines()
                        if line.strip() and not line.startswith('#')
                    )[-1200:]
                    if text:
                        req.system_prompt += '\n' + label + '\n' + text
            notes = base / 'dafeiyu_learned_notes.md'
            if notes.exists():
                lines = [line.strip() for line in notes.read_text(encoding='utf-8').splitlines()
                         if line.strip().startswith('-')][-6:]
                if lines:
                    req.system_prompt += (
                        '\n# 主人批阅过的经验提醒（照着调整，别念出来）\n' + '\n'.join(lines))
            tags, _ = armor.scan(text_now)
            if tags:
                req.system_prompt += armor.prompt_for(tags)
                armor.log_event('detect', sender, text_now, tags=tags)

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE, priority=maxsize - 1)
    async def private_battle(self, event):
        if event.get_platform_id() != 'dafeiyu-qq' or str(event.get_sender_id()) != '1000000001':
            return
        consumed, picture = battle(event)
        if consumed:
            event.stop_event()
            if picture is not None:
                await event.send(picture)

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE, priority=9590)
    async def fish_sticker_request(self, event):
        """Send images from the manually maintained 大肥鱼表情包 folder."""
        if event.get_platform_id() != 'dafeiyu-qq' or event.get_group_id():
            return
        text = str(getattr(event, 'message_str', '') or '')
        wants = re.search(r'大肥鱼.{0,6}表情包|表情包.{0,6}大肥鱼|哦鲸鲸.{0,6}表情包', text)
        asks = any(word in text for word in ('发', '来', '给', '要', '看看', '几张', '一点', '些', '呗', '有没有'))
        if not (wants and asks):
            return
        sender = str(event.get_sender_id())
        now = time.time()
        stamps = getattr(self, 'fish_sticker_ts', None)
        if stamps is None:
            stamps = self.fish_sticker_ts = {}
        if now - stamps.get(sender, 0) < 30:
            event.stop_event()
            return
        FISH_STICKER_DIR.mkdir(parents=True, exist_ok=True)
        files = sorted(
            path for path in FISH_STICKER_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in ('.gif', '.webp', '.png', '.jpg', '.jpeg')
        )
        event.stop_event()
        if not files:
            await event.send(event.plain_result('我还没存大肥鱼表情包呢 等主人给我放几张'))
            add_sent(sender, 1)
            return
        picks = random.sample(files, min(3, len(files)))
        chain = event.plain_result('')
        chain.chain = [Image.fromFileSystem(str(path)) for path in picks]
        await event.send(chain)
        add_sent(sender, len(picks))
        stamps[sender] = now

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE, priority=9585)
    async def private_poke(self, event):
        """Answer a private poke by poking back or replying briefly."""
        if event.get_platform_id() != 'dafeiyu-qq' or event.get_group_id():
            return
        poked = any(
            type(part).__name__ == 'Poke'
            and str(getattr(part, 'id', '')).lstrip('0') == str(event.get_self_id()).lstrip('0')
            for part in event.get_messages()
        )
        if not poked:
            return
        sender = str(event.get_sender_id())
        now = time.time()
        stamps = getattr(self, 'private_poke_ts', None)
        if stamps is None:
            stamps = self.private_poke_ts = {}
        if now - stamps.get(sender, 0) < 20:
            event.stop_event()
            return
        stamps[sender] = now
        event.stop_event()
        if random.random() < 0.5:
            try:
                platform = self.context.get_platform_inst('dafeiyu-qq')
                client = platform.get_client() if platform is not None else None
                if client is not None:
                    await client.call_action('send_poke', user_id=int(sender))
                    add_sent(sender, 1)
                    logger.info('Whale private poke back to %s', sender)
                    return
            except Exception as exc:
                logger.warning('Whale private poke back failed: %s', type(exc).__name__)
        line = random.choice(('别戳了', '戳一下得加饭', '谁啊，手挺欠', '哟，戳我干啥', '再戳饭就端走了'))
        await event.send(event.plain_result(line))
        add_sent(sender, 1)
        logger.info('Whale private poke reply to %s: %s', sender, line)

    @filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE, priority=9580)
    async def sticker_request(self, event):
        """Send one sticker when a friend explicitly asks for 表情包."""
        if event.get_platform_id() != 'dafeiyu-qq' or event.get_group_id():
            return
        if str(event.get_sender_id()) == OWNER_QQ:
            return
        text = str(getattr(event, 'message_str', '') or '')
        if any(word in text for word in ('大肥鱼', '哦鲸鲸', '鲸鲸')):
            return
        request = re.search(
            r'(?:发|来|整|给|丢|甩|要).{0,4}(?:点|个|张|些|几张|一点)?(?:表情包|表情)'
            r'|(?:有没有|来点|来几张|发几张).{0,4}表情包'
            r'|表情包(?:呢|来|发)',
            text,
        )
        if not request or any(word in text for word in ('只发', '如果', '要是', '假设')):
            return
        event.stop_event()
        base = Path(__file__).resolve().parents[2]
        paths = [Path(str(path)) for path in collected_stickers()]
        paths = [path for path in paths if path.is_file()]
        try:
            catalog = json.loads((base / 'stickers' / 'catalog.json').read_text(encoding='utf-8'))
            paths.extend(base / 'stickers' / item['file'] for item in catalog
                         if isinstance(item, dict) and item.get('file') and (base / 'stickers' / item['file']).is_file())
        except (OSError, ValueError):
            pass
        if not paths:
            await event.send(event.plain_result('库里没图了 等我攒攒'))
            add_sent(str(event.get_sender_id()), 1)
            return
        chain = event.plain_result('')
        chain.chain = [Image.fromFileSystem(str(random.choice(paths)))]
        await event.send(chain)
        add_sent(str(event.get_sender_id()), 1)

    @filter.on_decorating_result()
    async def decorate_private(self, event):
        if event.get_platform_id() != 'dafeiyu-qq' or event.get_group_id():
            return
        result = event.get_result()
        if not (result and result.chain):
            return
        sender = str(event.get_sender_id())
        leak_words = ('主人', '家庭群', '1000000002', '1000000001', '阿姨')
        tech_words = ('token', 'API', '后端', '接口', '插件', '服务器', '部署', '调试')
        reply = ''.join(getattr(p, 'text', '') for p in result.chain if hasattr(p, 'text'))
        user_text = str(getattr(event, 'message_str', '') or '')
        setter = getattr(event, 'set_extra', None)
        now = time.time()
        states = getattr(self, 'contact_pending', None)
        if states is None:
            states = self.contact_pending = {}
        key = str(getattr(event, 'unified_msg_origin', '') or sender)
        pending = states.get(key)
        if pending is not None and now - pending < 300:
            negative = re.search(r'不要|不用|算了|不必|不了|不想|别发|no', user_text, re.I)
            if negative:
                states.pop(key, None)
            elif re.search(r'要|嗯|好|行|可以|给我|发我|发吧|谢谢|麻烦', user_text):
                states.pop(key, None)
                result.chain = [Plain('1000000001')]
                if callable(setter):
                    setter('no_voice', True)
                    setter('no_quota_notice', True)
                logger.info('Whale private contact consent answered')
                return
            else:
                states.pop(key, None)
        token_ask = (
            re.search(r'(?:给|送|充|喂|续|买|提供|要|需要|加).{0,6}token', user_text, re.I)
            or re.search(r'token.{0,6}(?:给|送|充|喂|续|买|提供|要|需要)', user_text, re.I)
        )
        if token_ask:
            result.chain = [Plain('你真有这个心的话，那你联系我主人吧')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private token-offer answered')
            return
        token_concept = re.search(
            r'token.{0,6}(?:是什么|是啥|啥|什么意思|能当饭|当饭|吃饭|饭吗|怎么用|干嘛用|干嘛|呢)'
            r'|(?:什么是|啥是|解释一下|说说).{0,4}token',
            user_text,
            re.I,
        )
        if token_concept:
            result.chain = [Plain('token就是我的白饭啊 身家性命都在这上面')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private token-concept answered')
            return
        owner_variant = re.search(
            r'(?:你|你的|哦鲸鲸)?(?:有|有没有)(?:主人)(?:吗|么|嘛|没有|没|不|$)'
            r'|(?:你|你的|哦鲸鲸)?(?:主人).{0,5}(?:呢|吗|么|嘛)',
            user_text,
        )
        if owner_variant and not re.search(r'(?:主人).{0,4}(?:是谁|谁啊|谁|哪个)', user_text) and not re.search(r'QQ|qq|联系方式|微信|电话|手机号|好友', user_text):
            result.chain = [Plain('有主人')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private owner-variant answered')
            return
        feed_ask = re.search(
            r'(?:怎么|如何|怎样|在哪).{0,6}(?:加饭|添饭|投喂|喂你|给你饭|给你吃)'
            r'|(?:加饭|添饭|投喂|喂你|给你饭).{0,6}(?:怎么|如何|可以吗|行吗|在哪)'
            r'|(?:想|要).{0,4}(?:给你)?(?:加饭|添饭|投喂)',
            user_text,
        )
        if feed_ask:
            result.chain = [Plain('可以去找我主人')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private feeding question answered')
            return
        boss_ask = re.search(r'(?:你|你的|哦鲸鲸)?(?:老板|主子).{0,4}(?:是谁|谁啊|谁|哪个|呢|吗|么|嘛)|(?:你|你的)?(?:有|有没有)(?:老板|主子)', user_text)
        if boss_ask:
            result.chain = [Plain('我没有老板')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private boss question answered')
            return
        master_ask = re.search(r'(?:你|你的|哦鲸鲸)?主人.{0,4}(?:是谁|谁啊|谁|哪个)', user_text)
        if master_ask:
            result.chain = [Plain('我只有主人')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private master question answered')
            return
        brother_who = re.search(r'(?:你|你的|那你)?主人.{0,4}(?:是谁|谁啊|谁|哪个)', user_text)
        if brother_who:
            result.chain = [Plain('主人就是主人')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private brother-who answered')
            return
        backer_ask = re.search(
            r'(?:你|大肥鱼).{0,4}(?:背后|身后|上头|上面).{0,4}(?:是谁|谁|哪个)'
            r'|(?:谁|哪个人).{0,4}(?:在)?(?:背后|身后).{0,4}(?:你|大肥鱼)',
            user_text,
        )
        if backer_ask:
            result.chain = [Plain('这个不聊')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private backer question answered')
            return
        contact_intent = (
            re.search(r'(?:想|要|能|可以|怎么|如何).{0,8}(?:加|联系|找|认识).{0,6}(?:主人|他)', user_text)
            or re.search(r'(?:主人|他).{0,8}(?:QQ|qq|QQ号|qq号|QQ号码|联系方式|微信|电话|手机号|好友)', user_text)
            or re.search(r'(?:QQ|qq|QQ号|qq号|QQ号码|联系方式|微信|电话|手机号).{0,8}(?:主人)', user_text)
            or re.search(r'想认识.{0,4}主人|加.{0,3}主人|(?:给我|发我|告诉我).{0,4}(?:主人|他)', user_text)
        )
        if contact_intent and '空间' not in user_text and '音乐' not in user_text:
            states[key] = now
            result.chain = [Plain('你要我主人的QQ号吗？')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private contact consent asked')
            return
        technical_ask = (
            re.search(r'(?:怎么|如何|怎样|能不能|可以).{0,10}(?:养|做|弄|搞|部署|搭建|复制|训练|接管|接盘|代管|实现).{0,8}(?:你|一条|一个|大肥鱼|像你|一样的鱼)', user_text)
            or re.search(r'(?:养|做|复制|训练|部署|搭建|接管|接盘|代管).{0,8}(?:一条|一个|像你|你这样的|大肥鱼)', user_text)
            or re.search(r'(?:你|大肥鱼).{0,6}(?:什么|哪个).{0,4}(?:模型|AI|接口|框架)', user_text)
            or re.search(r'(?:模型|API|接口|插件|后端|服务器|源码|代码|提示词|系统提示|人设|设定|技术|部署|调试).{0,8}(?:你|大肥鱼|怎么|多少|什么)', user_text)
            or re.search(r'(?:改|换|设置|定制).{0,6}(?:人设|设定|性格)|(?:人设|设定|性格).{0,6}(?:改|换|设置|定制)', user_text)
            or re.search(r'(?:怎么|如何).{0,4}(?:部署|搭建|接管|接盘|代管)', user_text)
            or re.search(r'无限(?:聊天|聊|对话|额度|次数)|不限额|不限次数|无限量|绕过.{0,4}(?:额度|限制)|破解.{0,4}(?:额度|限制)|额度.{0,4}无限', user_text)
        )
        if technical_ask:
            result.chain = [Plain('我只会聊天，请联系主人处理')]
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private technical question answered')
            return
        join_ask = re.search(r'加群|进群|入群|拉我进群|群.{0,4}(?:加|进)|能加.{0,4}群', user_text)
        feature_ask = re.search(r'(?:以后|还会|会不会|能不能).{0,6}(?:增加|加|更新|新功能)|新功能|功能.{0,4}(?:增加|更新|加)', user_text)
        if join_ask:
            result.chain = [Plain('我没有权限哦，去联系我主人试试吧！')]
            setter = getattr(event, 'set_extra', None)
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private join-group literal reply')
            return
        if feature_ask:
            result.chain = [Plain('应该会的吧，你可以去联系我主人问问呀！')]
            setter = getattr(event, 'set_extra', None)
            if callable(setter):
                setter('no_voice', True)
                setter('no_quota_notice', True)
            logger.info('Whale private future-feature literal reply')
            return
        if '没装人' in reply and 'AI' not in reply:
            reply = '我本来就是 AI，没装人'
            result.chain = [Plain(reply)]
        has_image = any(type(part).__name__ == 'Image' for part in (event.get_messages() if hasattr(event, 'get_messages') else []))
        if has_image and re.search(r'九宫格|九遍|九个一样|九张|九只|九条|九个', reply):
            logger.warning('Whale image nine-grid guard replaced: %s', reply[:40])
            result.chain = [Plain('图我这边显示成多帧了 不是九张 你说说是什么')]
            return
        romance_words = ('宝贝', '老公', '亲爱的', '爱你', '亲亲', '想你', '抱抱')
        rhetorical = any(phrase in reply for phrase in ('谁爱你', '谁最爱你了', '谁爱你了'))
        if any(w in reply for w in romance_words) and not rhetorical:
            logger.warning('Whale private romance guard replaced: %s', reply[:40])
            result.chain = [Plain('少来这套 吃饭去')]
            return
        if sender != OWNER_QQ:
            if any(w in reply for w in tech_words):
                logger.warning('Whale private tech-talk guard replaced: %s', reply[:40])
                result.chain = [Plain(random.choice(('不懂这些 我就管吃饭', '这些我不聊 换点别的')))]
                return
            hits = [w for w in leak_words if w in reply]
            if hits:
                persona_ask = re.search(
                    r'(?:改|换|设置|定制|调教|重做|调整).{0,8}(?:性格|人设|设定|脾气)'
                    r'|(?:性格|人设|设定|脾气).{0,8}(?:改|换|调|设置)', user_text)
                support_ask = re.search(r'养你|我养|包养|请你吃饭|请你吃|喂你|给你买|养我|投喂', user_text)
                quota_ask = re.search(
                    r'(?:聊天|私聊|回复|说话).{0,6}(?:次数|条数|额度|上限|限制)'
                    r'|(?:额度|次数|条数).{0,6}(?:多少|剩|还有|上限|重置)'
                    r'|(?:怎么|如何).{0,4}(?:重置|恢复).{0,4}额度'
                    r'|为什么.{0,6}(?:上限|限制)', user_text)
                tech_ask = re.search(r'部署|搭建|自己养|养一个|一样的鱼|怎么做到|接管|接盘|代管|训练|复制一个|技术', user_text)
                safe_owner = bool(persona_ask or support_ask) and (('私聊我主人' in reply or '私信我主人' in reply or ('找我主人' in reply and '试试' in reply)) or (bool(support_ask) and '主人' in reply and ('喂' in reply or '饭' in reply)))
                quota_safe = bool(quota_ask) and '主人' in reply and any(word in reply for word in ('吃饭', '破产', '额度', '重置'))
                tech_safe = bool(tech_ask) and '主人' in reply and any(word in reply for word in ('联系', '找他', '问他'))
                contact = re.search(r'\d{5,}|QQ|微信|手机号|群号|联系方式|加我', reply, re.I)
                if hits == ['主人'] and not contact and (safe_owner or quota_safe or tech_safe):
                    logger.info('Whale privacy guard allowed owner referral')
                else:
                    logger.warning('Whale privacy guard replaced reply leaking %s', '、'.join(hits))
                    result.chain = [Plain(random.choice(SAFE_REPLIES))]
                    return
        replacement = armor.sanitize(user_text, reply, owner=(sender == OWNER_QQ))
        if replacement:
            tags, _ = armor.scan(user_text)
            armor.log_event('block', sender, user_text, reply, tags, replacement)
            logger.warning('Whale armor guard replaced: %s', reply[:40])
            result.chain = [Plain(replacement)]
            return
        for part in result.chain:
            if isinstance(part, Plain) and part.text:
                part.text = re.sub(r'^\s*作为(?:一个)?(?:AI|人工智能|语言模型|助手)(?:助手)?[，,：:\s]*', '', part.text)
                for phrase, replacement in (('我一直在', '我在'), ('我一直都在', '我在'), ('一直在线', '在线'), ('随时找我', '找我')):
                    part.text = part.text.replace(phrase, replacement)
        text = event.message_str + ' ' + ''.join(getattr(p, 'text', '') for p in result.chain)
        decorate(result, text, event.unified_msg_origin)
