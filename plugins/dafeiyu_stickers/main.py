import base64
import io
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests
from PIL import Image, ImageChops, ImageStat

from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Star, register

TZ_OFFSET = timedelta(hours=8)
MAX_FILES = 600
MAX_BYTES = 360 * 1024 * 1024
GIF_LIMIT = 4 * 1024 * 1024
PHOTO_LIMIT = 800 * 1024
SIDE_LIMIT = 800
MAGIC = {
    b'GIF87a': '.gif',
    b'GIF89a': '.gif',
    b'\x89PNG\r\n\x1a\n': '.png',
    b'\xff\xd8\xff': '.jpg',
}


def sniff(data):
    """Detect the image type from its first bytes.

    Args:
        data: Raw bytes.

    Returns:
        File extension including the dot, or '' when unknown.
    """
    for magic, ext in MAGIC.items():
        if data.startswith(magic):
            return ext
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    return ''


def image_size(data):
    """Read pixel dimensions without keeping the file open.

    Args:
        data: Raw image bytes.

    Returns:
        A (width, height) tuple, or (0, 0) when unreadable.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            return img.size
    except Exception:
        return 0, 0


def visual_rms(raw, other):
    """Compare two images after normalizing them to a small grayscale grid.

    Args:
        raw: Encoded candidate bytes.
        other: Existing image path.

    Returns:
        Root-mean-square pixel difference, or None when unreadable.
    """
    try:
        with Image.open(io.BytesIO(raw)) as candidate, Image.open(other) as existing:
            left = candidate.convert('L').resize((64, 64))
            right = existing.convert('L').resize((64, 64))
            return ImageStat.Stat(ImageChops.difference(left, right)).rms[0]
    except Exception:
        return None


def make_thumb(raw):
    """Build a tiny grayscale thumbnail stored with the sticker index.

    Args:
        raw: Encoded image bytes.

    Returns:
        Base64 text, or '' when the image cannot be decoded.
    """
    try:
        with Image.open(io.BytesIO(raw)) as img:
            pixels = img.convert('L').resize((32, 32)).tobytes()
    except Exception:
        return ''
    return base64.b64encode(pixels).decode('ascii')


def thumb_rms(thumb, raw):
    """Compare a stored thumbnail with a candidate image.

    Args:
        thumb: Base64 32x32 grayscale thumbnail.
        raw: Encoded candidate bytes.

    Returns:
        Root-mean-square difference, or None when unreadable.
    """
    try:
        old = base64.b64decode(thumb)
        with Image.open(io.BytesIO(raw)) as img:
            new = img.convert('L').resize((32, 32)).tobytes()
        if len(old) != len(new):
            return None
        return (sum((a - b) ** 2 for a, b in zip(old, new)) / len(old)) ** 0.5
    except Exception:
        return None


def image_hash(raw):
    """Return a 256-bit difference hash for visual deduplication.

    Args:
        raw: Encoded image bytes.

    Returns:
        An integer fingerprint, or None when the image cannot be decoded.
    """
    try:
        with Image.open(io.BytesIO(raw)) as img:
            pixels = list(img.convert('L').resize((17, 16)).tobytes())
    except Exception:
        return None
    bits = []
    for y in range(16):
        for x in range(16):
            bits.append(1 if pixels[y * 17 + x] > pixels[y * 17 + x + 1] else 0)
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    return value


@register('dafeiyu_stickers', 'Local', 'Collect stickers from chats into a shared library', '1.0.0')
class StickerCollect(Star):
    def __init__(self, context):
        super().__init__(context)
        self.data = Path(__file__).resolve().parents[2]
        self.folder = self.data / 'collected_stickers'
        self.daily = self.folder / 'daily'
        self.index = self.folder / 'index.json'
        self.block = self.data / 'dafeiyu_sticker_blocked.json'

    async def initialize(self):
        self.folder.mkdir(exist_ok=True)
        self.daily.mkdir(parents=True, exist_ok=True)
        self.block_missing()
        logger.info('Whale sticker plugin initialized, folder=%s daily=%s', self.folder, self.daily)

    def load_index(self):
        try:
            return json.loads(self.index.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def save_index(self, data):
        try:
            self.index.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            logger.warning('Whale sticker index write failed: %s', type(exc).__name__)

    def load_block(self):
        try:
            return json.loads(getattr(self, 'block', self.data / 'dafeiyu_sticker_blocked.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def save_block(self, data):
        try:
            getattr(self, 'block', self.data / 'dafeiyu_sticker_blocked.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            logger.warning('Whale sticker block write failed: %s', type(exc).__name__)

    def block_missing(self):
        """Move index entries whose files were deleted into the block list."""
        index = self.load_index()
        block = self.load_block()
        changed = False
        for key, entry in list(index.items()):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get('file') or '')
            if not name or (self.folder / name).is_file():
                continue
            digest = str(entry.get('md5') or key)
            block[digest] = {
                'md5': digest,
                'hash': entry.get('hash') or '',
                'thumb': entry.get('thumb') or '',
                'file': name,
                'at': datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S'),
            }
            index.pop(key, None)
            changed = True
            logger.info('Whale sticker tombstoned: %s', name)
        if changed:
            self.save_index(index)
            self.save_block(block)

    def is_blocked(self, digest, fingerprint, raw):
        for entry in self.load_block().values():
            if not isinstance(entry, dict):
                continue
            if str(entry.get('md5') or '') == digest:
                return True
            old_hash = entry.get('hash') or ''
            if not old_hash or fingerprint is None:
                continue
            try:
                distance = (int(old_hash, 16) ^ fingerprint).bit_count()
            except ValueError:
                continue
            if distance > 16:
                continue
            thumb = entry.get('thumb') or ''
            if thumb:
                rms = thumb_rms(thumb, raw)
                if rms is not None and rms <= 8:
                    return True
            elif distance <= 8:
                return True
        return False

    async def fetch_async(self, part):
        """Resolve one image component to raw bytes via AstrBot's resolver.

        Args:
            part: AstrBot Image component.

        Returns:
            Raw bytes, or b'' when unavailable.
        """
        try:
            encoded = await part.convert_to_base64()
            return base64.b64decode(encoded)
        except Exception:
            return self.fetch(part)

    def fetch(self, part):
        """Read the raw bytes of one image component.

        Args:
            part: AstrBot Image component.

        Returns:
            Raw bytes, or b'' when unavailable.
        """
        path = getattr(part, 'path', '') or ''
        if path and Path(path).is_file():
            try:
                return Path(path).read_bytes()
            except OSError:
                return b''
        for candidate in (getattr(part, 'url', '') or '', getattr(part, 'file', '') or ''):
            if candidate.startswith('http'):
                try:
                    return requests.get(candidate, timeout=15).content
                except requests.RequestException:
                    continue
            if candidate.startswith('file:///'):
                local = Path(unquote(urlparse(candidate).path.lstrip('/')))
                try:
                    return local.read_bytes()
                except OSError:
                    continue
            if candidate.startswith('base64://'):
                try:
                    return base64.b64decode(candidate.split('://', 1)[1])
                except (ValueError, TypeError):
                    continue
            try:
                local = Path(candidate)
                if candidate and local.is_file():
                    return local.read_bytes()
            except OSError:
                continue
        return b''

    @filter.event_message_type(
        filter.EventMessageType.PRIVATE_MESSAGE | filter.EventMessageType.GROUP_MESSAGE,
        priority=9500,
    )
    async def collect(self, event):
        if any(type(part).__name__ == 'Image' for part in event.get_messages()):
            logger.info('Whale sticker entry: platform=%s sender=%s', event.get_platform_id(), event.get_sender_id())
        if event.get_platform_id() != 'dafeiyu-qq':
            return
        if str(event.get_sender_id()) == str(event.get_self_id()):
            return
        images = [p for p in event.get_messages() if type(p).__name__ == 'Image']
        if not images:
            return
        logger.info('Whale sticker candidate: %d image(s) from %s', len(images), event.get_sender_id())
        self.block_missing()
        stored = self.load_index()
        for part in images[:3]:
            raw = await self.fetch_async(part)
            if not raw:
                logger.info('Whale sticker skip: could not read image (%s)', getattr(part, 'file', '')[:60])
                continue
            ext = sniff(raw)
            if not ext:
                logger.info('Whale sticker skip: unknown type (%d bytes)', len(raw))
                continue
            if ext in ('.gif', '.webp'):
                if len(raw) > GIF_LIMIT:
                    logger.info('Whale sticker skip: %s too large (%d bytes)', ext, len(raw))
                    continue
            else:
                width, height = image_size(raw)
                if not width or not height or max(width, height) > SIDE_LIMIT or len(raw) > PHOTO_LIMIT:
                    logger.info('Whale sticker skip: photo-like %s (%dx%d, %d bytes)', ext, width, height, len(raw))
                    continue
            digest = hashlib.md5(raw).hexdigest()[:16]
            fingerprint = image_hash(raw)
            name = digest + ext
            day = datetime.now(timezone(TZ_OFFSET)).strftime('%Y-%m-%d')
            day_folder = self.daily / day
            day_folder.mkdir(parents=True, exist_ok=True)
            target = day_folder / name
            if digest in stored or target.exists():
                continue
            duplicate = False
            for entry in stored.values():
                if not isinstance(entry, dict):
                    continue
                old_hash = entry.get('hash')
                if not old_hash:
                    old_file = self.folder / str(entry.get('file') or '')
                    if old_file.is_file():
                        old_value = image_hash(old_file.read_bytes())
                        if old_value is not None:
                            entry['hash'] = format(old_value, '064x')
                            old_hash = entry['hash']
                if old_hash and fingerprint is not None:
                    try:
                        if (int(old_hash, 16) ^ fingerprint).bit_count() <= 16:
                            old_file = self.folder / str(entry.get('file') or '')
                            if old_file.is_file():
                                rms = visual_rms(raw, old_file)
                                if rms is not None and rms <= 8:
                                    duplicate = True
                                    break
                    except ValueError:
                        pass
            if duplicate:
                logger.info('Whale sticker duplicate skipped: %s', name)
                continue
            if self.is_blocked(digest, fingerprint, raw):
                logger.info('Whale sticker tombstone skipped: %s', name)
                continue
            try:
                target.write_bytes(raw)
            except OSError as exc:
                logger.warning('Whale sticker write failed: %s', type(exc).__name__)
                continue
            stored[digest] = {
                'file': f'daily/{day}/{name}',
                'day': day,
                'size': len(raw),
                'animated': ext in ('.gif', '.webp'),
                'hash': format(fingerprint, '064x') if fingerprint is not None else '',
                'md5': digest,
                'thumb': make_thumb(raw),
                'group': event.get_group_id() or '',
                'at': datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S'),
            }
            logger.info('Whale sticker collected: %s (%d bytes)', name, len(raw))
        self.save_index(stored)
        self.trim()

    def trim(self):
        files = sorted(self.folder.glob('*.*'), key=lambda p: p.stat().st_mtime)
        removable = [path for path in files if path.suffix != '.json']
        total = sum(path.stat().st_size for path in removable)
        overflow = max(0, len(files) - MAX_FILES)
        removed = set()
        for path in removable:
            if overflow <= 0 and total <= MAX_BYTES:
                break
            try:
                total -= path.stat().st_size
                path.unlink()
                removed.add(path.name)
                overflow -= 1
            except OSError:
                pass
        if removed:
            stored = self.load_index()
            for key in [k for k, v in stored.items() if isinstance(v, dict) and v.get('file') in removed]:
                stored.pop(key, None)
            self.save_index(stored)
