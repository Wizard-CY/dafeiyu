"""Persistent illustration library for the daily Qzone post.

The library keeps normalised JPEG photos with a small caption and tags.  It is
filled from Bing's public-domain-filtered image search once, then topped up by
the plugin in the background.  The daily post asks the language model to pick
one entry, so the picture follows the text instead of always taking the first
search result.  Local images can be added by dropping them into ``inbox``.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import random
import re
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image

TZ = timezone(timedelta(hours=8))
BING_IMAGES = 'https://cn.bing.com/images/async'
HOT_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
)
IMAGE_HOSTS = (
    'pixnio.com', 'pixabay.com', 'picdn.net', 'goodfreephotos.com',
    'pexels.com', 'unsplash.com',
)
MAX_IMAGES = 120
MIN_WIDTH = 640
MIN_HEIGHT = 480
LOCAL_MIN_WIDTH = 300
LOCAL_MIN_HEIGHT = 240
RECENT_DAYS = 14

# Search phrase, caption shown to the model, tags, and moods the scene fits.
# English search phrases return many more public-domain results than Chinese
# ones, while the caption stays Chinese for the selection prompt.
QUERY_SPECS = (
    ('ocean sunset', '海边日落', ('海', '日落', '傍晚', '橘色'), ('喜欢', '开心', '困')),
    ('ocean waves', '海浪', ('海', '浪', '蓝色'), ('开心', '日常')),
    ('whale', '鲸鱼', ('鲸鱼', '海'), ('喜欢', '惊讶')),
    ('dolphin', '海豚', ('海豚', '海'), ('开心', '打招呼')),
    ('jellyfish', '水母', ('水母', '海'), ('惊讶', '害羞')),
    ('coral reef', '珊瑚', ('珊瑚', '海底'), ('喜欢', '害羞')),
    ('beach footprints', '沙滩脚印', ('沙滩', '脚印', '海'), ('日常', '开心')),
    ('starry sky', '星空', ('星空', '夜', '星星'), ('困', '喜欢')),
    ('moon', '月亮', ('月亮', '夜'), ('困', '委屈')),
    ('clouds', '云朵', ('云', '天空'), ('疑惑', '日常')),
    ('rain window', '雨天窗户', ('雨', '窗', '玻璃'), ('委屈', '无语')),
    ('coffee cup', '咖啡杯', ('咖啡', '杯子', '桌子'), ('摸鱼', '困')),
    ('pancakes', '早餐', ('早餐', '面包', '牛奶'), ('开心', '日常')),
    ('home cooking', '家常菜', ('饭', '菜', '吃饭'), ('摸鱼', '开心')),
    ('hot pot', '火锅', ('火锅', '吃饭'), ('开心', '喜欢')),
    ('bubble tea', '奶茶', ('奶茶', '饮料'), ('开心', '摸鱼')),
    ('desk books', '书桌', ('书', '桌子', '学习'), ('困', '摸鱼')),
    ('bookshelf', '书店', ('书', '书店'), ('喜欢', '日常')),
    ('park walk', '公园散步', ('公园', '散步', '树'), ('摸鱼', '开心')),
    ('cat', '猫咪', ('猫', '可爱'), ('喜欢', '开心')),
    ('puppy', '小狗', ('狗', '可爱'), ('开心', '打招呼')),
    ('flowers', '花', ('花', '植物'), ('喜欢', '害羞')),
    ('snow', '雪', ('雪', '冬天'), ('惊讶', '日常')),
    ('autumn leaves', '秋天落叶', ('秋天', '落叶'), ('日常', '困')),
    ('city night', '城市夜景', ('城市', '夜', '灯'), ('困', '日常')),
    ('subway', '地铁', ('地铁', '通勤'), ('摸鱼', '无语')),
    ('lighthouse', '灯塔', ('灯塔', '海', '夜'), ('困', '喜欢')),
    ('small boat', '小船', ('船', '海'), ('日常', '开心')),
    ('mountain lake', '山湖', ('山', '湖'), ('喜欢', '困')),
    ('forest', '森林', ('森林', '树'), ('日常', '疑惑')),
    ('cozy room', '温暖房间', ('房间', '家', '灯'), ('困', '开心')),
    ('tea cup', '茶杯', ('茶', '杯子'), ('摸鱼', '日常')),
    ('ramen', '面条', ('面', '吃饭'), ('摸鱼', '开心')),
    ('dessert', '甜点', ('甜点', '蛋糕'), ('开心', '喜欢')),
    ('sunrise', '日出', ('日出', '早晨', '光'), ('困', '打招呼')),
    ('rainy street', '雨街', ('雨', '街'), ('委屈', '日常')),
    ('seashells', '贝壳', ('贝壳', '沙滩'), ('喜欢', '惊讶')),
    ('window sunlight', '窗边阳光', ('阳光', '窗'), ('开心', '日常')),
    ('open book', '看书', ('书', '阅读'), ('困', '摸鱼')),
    ('balcony plants', '阳台植物', ('植物', '阳台'), ('日常', '喜欢')),
)


# Daily scenes are fetched first so the first few seed runs already cover the
# topics the diary talks about most often.
PRIORITY_QUERIES = (
    'coffee cup', 'rain window', 'pancakes', 'home cooking', 'hot pot',
    'bubble tea', 'tea cup', 'ramen', 'dessert', 'desk books', 'bookshelf',
    'open book', 'cat', 'puppy', 'park walk', 'cozy room',
    'window sunlight', 'flowers', 'balcony plants', 'city night', 'subway',
)


def _ordered_specs() -> list[tuple]:
    """Return query specs with the daily-life scenes first."""
    by_search = {spec[0]: spec for spec in QUERY_SPECS}
    ordered = [by_search[query] for query in PRIORITY_QUERIES if query in by_search]
    ordered.extend(spec for spec in QUERY_SPECS if spec[0] not in PRIORITY_QUERIES)
    return ordered


def catalog_path(base: Path) -> Path:
    """Return the catalog file for a library root."""
    return Path(base) / 'catalog.json'


def load_catalog(base: Path) -> list[dict]:
    """Read usable catalog entries, dropping rows whose file disappeared."""
    path = catalog_path(base)
    try:
        items = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return []
    if not isinstance(items, list):
        return []
    usable = []
    for item in items:
        if not isinstance(item, dict) or not item.get('file'):
            continue
        if not (Path(base) / 'images' / str(item['file'])).is_file():
            continue
        usable.append(item)
    return usable


def save_catalog(base: Path, items: list[dict]) -> None:
    """Write the catalog atomically."""
    path = catalog_path(base)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def count(base: Path) -> int:
    """Return the number of usable images in the library."""
    return len(load_catalog(base))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dhash(image: Image.Image) -> int:
    """Return a 64-bit difference hash used to catch near-duplicate photos."""
    gray = image.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.getdata())
    bits = 0
    for row in range(8):
        offset = row * 9
        for column in range(8):
            bits = (bits << 1) | (pixels[offset + column] > pixels[offset + column + 1])
    return bits


def _distance(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _download(url: str) -> Image.Image | None:
    """Download one image and return it as a normalised RGB image."""
    try:
        with requests.get(url, headers={'User-Agent': HOT_UA}, timeout=8,
                          stream=True) as response:
            if response.status_code != 200:
                return None
            raw = response.raw.read(8 * 1024 * 1024 + 1)
    except Exception:
        return None
    if not raw or len(raw) > 8 * 1024 * 1024:
        return None
    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
        image = image.convert('RGB')
    except Exception:
        return None
    if image.width < MIN_WIDTH or image.height < MIN_HEIGHT:
        return None
    image.thumbnail((1400, 1400))
    return image


def _host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except ValueError:
        return ''


def _allowed(url: str) -> bool:
    host = _host(url)
    return any(item in host for item in IMAGE_HOSTS)


def _save_image(base: Path, image: Image.Image, stem: str) -> tuple[str, str, int]:
    """Save a normalised image and return (file name, sha, dhash)."""
    folder = Path(base) / 'images'
    folder.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG', quality=88, optimize=True)
    raw = buffer.getvalue()
    sha = _sha256(raw)
    path = folder / (stem + '_' + sha[:8] + '.jpg')
    path.write_bytes(raw)
    return path.name, sha, _dhash(image)


def seed_library(base: Path, target: int = MAX_IMAGES, budget_seconds: int = 300,
                 log=None, specs=None) -> int:
    """Download new, deduplicated photos from the public-domain image search.

    Args:
        base: Library root holding ``images`` and ``catalog.json``.
        target: Stop once the library holds this many usable entries.
        budget_seconds: Wall-clock budget for the whole seed run.
        log: Optional callable receiving one short progress line.
        specs: Optional query specs; defaults to the ordered built-in list.

    Returns:
        The number of newly added images.
    """
    base = Path(base)
    catalog = load_catalog(base)
    known = {str(item.get('sha256') or '') for item in catalog}
    hashes = [int(str(item.get('dhash') or '0'), 16) for item in catalog]
    started = time.time()
    added = 0
    for search, caption, tags, moods in (specs or _ordered_specs()):
        if len(catalog) >= target or time.time() - started > budget_seconds:
            break
        if sum(1 for item in catalog if item.get('query') == caption) >= 2:
            continue
        for first in (0, 8):
            if len(catalog) >= target or time.time() - started > budget_seconds:
                break
            try:
                response = requests.get(
                    BING_IMAGES,
                    headers={'User-Agent': HOT_UA, 'Accept-Language': 'zh-CN,zh;q=0.9'},
                    params={
                        'q': search, 'first': str(first), 'count': '12',
                        'mmasync': '1', 'qft': '+filterui:license-L1',
                    },
                    timeout=8,
                )
                blobs = re.findall(r'm="([^"]+)"', response.text)
            except Exception:
                continue
            for raw in blobs[:8]:
                if len(catalog) >= target or time.time() - started > budget_seconds:
                    break
                try:
                    item = json.loads(html.unescape(raw))
                except ValueError:
                    continue
                url = str(item.get('murl') or '')
                page = str(item.get('purl') or '')
                if not url.startswith('http') or not _allowed(url):
                    continue
                image = _download(url)
                if image is None:
                    continue
                buffer = io.BytesIO()
                image.save(buffer, 'JPEG', quality=88, optimize=True)
                sha = _sha256(buffer.getvalue())
                if sha in known:
                    continue
                fingerprint = _dhash(image)
                if any(_distance(fingerprint, old) <= 5 for old in hashes):
                    continue
                stem = hashlib.sha1(caption.encode('utf-8')).hexdigest()[:6]
                filename, sha, fingerprint = _save_image(base, image, stem)
                entry = {
                    'id': filename[:-4],
                    'file': filename,
                    'caption': caption,
                    'tags': list(tags),
                    'moods': list(moods),
                    'query': caption,
                    'search': search,
                    'source': page or url,
                    'license': 'Bing 公共领域过滤',
                    'sha256': sha,
                    'dhash': format(fingerprint, '016x'),
                    'added_at': datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S'),
                }
                catalog.append(entry)
                known.add(sha)
                hashes.append(fingerprint)
                save_catalog(base, catalog)
                added += 1
                if callable(log):
                    log('library + %s (%s)' % (caption, filename))
    return added


def sync_inbox(base: Path, log=None) -> int:
    """Import user-supplied images from ``inbox`` into the library.

    The file name becomes the caption, so names like ``海边_日落.jpg`` are
    useful tags.  Imported originals are moved to ``inbox/imported``.
    """
    base = Path(base)
    inbox = base / 'inbox'
    inbox.mkdir(parents=True, exist_ok=True)
    done = inbox / 'imported'
    done.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog(base)
    known = {str(item.get('sha256') or '') for item in catalog}
    added = 0
    for path in sorted(inbox.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            continue
        try:
            with Image.open(path) as source:
                source.load()
                image = source.convert('RGB')
        except Exception:
            continue
        if image.width < LOCAL_MIN_WIDTH or image.height < LOCAL_MIN_HEIGHT:
            continue
        image.thumbnail((1400, 1400))
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=88, optimize=True)
        sha = _sha256(buffer.getvalue())
        if sha in known:
            path.replace(done / path.name)
            continue
        stem = re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]+', '_', path.stem).strip('_') or 'local'
        filename = 'local_%s_%s.jpg' % (stem[:24], sha[:8])
        (base / 'images').mkdir(parents=True, exist_ok=True)
        (base / 'images' / filename).write_bytes(buffer.getvalue())
        caption = re.sub(r'[_-]+', ' ', path.stem).strip() or '本地图片'
        entry = {
            'id': filename[:-4],
            'file': filename,
            'caption': caption[:40],
            'tags': [part for part in re.split(r'[\s_-]+', path.stem) if part][:6],
            'moods': [],
            'query': '本地',
            'source': '本地图库',
            'license': '用户提供',
            'sha256': sha,
            'dhash': format(_dhash(image), '016x'),
            'added_at': datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S'),
        }
        catalog.append(entry)
        known.add(sha)
        save_catalog(base, catalog)
        path.replace(done / path.name)
        added += 1
        if callable(log):
            log('library imported %s' % filename)
    return added


def recent_ids(state: dict, days: int = RECENT_DAYS, today: date | None = None) -> set[str]:
    """Return image IDs used within the repeat guard window."""
    current = today or datetime.now(TZ).date()
    cutoff = current - timedelta(days=days)
    used = set()
    for item in state.get('recent_images') or []:
        if not isinstance(item, dict):
            continue
        try:
            when = date.fromisoformat(str(item.get('at') or '')[:10])
        except ValueError:
            continue
        if when >= cutoff and item.get('id'):
            used.add(str(item['id']))
    return used


def remember(state: dict, image_id: str, day: str, keep: int = 40) -> None:
    """Record one used image in the state for the repeat guard."""
    recent = [item for item in state.get('recent_images') or [] if isinstance(item, dict)]
    recent = [item for item in recent if str(item.get('id')) != image_id]
    recent.append({'id': image_id, 'at': day})
    state['recent_images'] = recent[-keep:]


def candidates(base: Path, text: str, mood: str, used_ids: set[str],
               limit: int = 12) -> list[dict]:
    """Rank library images for one post, preferring unused and text-matching ones.

    Args:
        base: Library root.
        text: Generated post body.
        mood: Mood tag chosen by the model.
        used_ids: Image IDs to avoid while enough alternatives remain.
        limit: Maximum number of candidates returned.

    Returns:
        A list of catalog entries, best first.
    """
    catalog = load_catalog(base)
    if not catalog:
        return []
    fresh = [item for item in catalog if str(item.get('id')) not in used_ids]
    pool = fresh if len(fresh) >= limit else catalog
    scored = []
    for item in pool:
        score = random.random() * 0.8
        for tag in item.get('tags') or []:
            if tag and str(tag) in text:
                score += 3
        caption = str(item.get('caption') or '')
        if caption and caption in text:
            score += 2
        if mood and mood in (item.get('moods') or []):
            score += 2
        scored.append((score, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    picked = []
    per_query = {}
    for _, item in scored:
        query = str(item.get('query') or '')
        if per_query.get(query, 0) >= 2:
            continue
        picked.append(item)
        per_query[query] = per_query.get(query, 0) + 1
        if len(picked) >= limit:
            return picked
    for _, item in scored:
        if item not in picked:
            picked.append(item)
        if len(picked) >= limit:
            break
    return picked
