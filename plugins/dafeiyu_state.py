"""Serialized, atomic JSON updates shared by the bot and its control panels."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
import time
import msvcrt

@contextmanager
def transaction(path, default=dict):
    """Lock a state file across processes and commit an atomic replacement.

    Args:
        path: State file path.
        default: Factory used only when the file does not exist.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(path) + '.lock', 'a+b') as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        deadline = time.monotonic() + 5
        while True:
            try:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('State is busy: ' + path.name)
                time.sleep(0.02)
        temp = None
        try:
            value = json.loads(path.read_text(encoding='utf-8')) if path.exists() else default()
            if not isinstance(value, type(default())):
                raise ValueError('Invalid state format: ' + path.name)
            yield value
            fd, temp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump(value, out, ensure_ascii=False, indent=2)
                out.flush(); os.fsync(out.fileno())
            os.replace(temp, path)
        finally:
            if temp and os.path.exists(temp):
                os.unlink(temp)
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

def enqueue(path, recipients, text):
    """Append deduplicated pending notices in one transaction.

    Args:
        path: Queue file.
        recipients: Synthetic or configured recipient identifiers.
        text: Exact notice text.
    """
    import uuid
    added = 0
    with transaction(path, list) as items:
        queued = {(str(x.get('qq')), x.get('text')) for x in items if x.get('status', 'pending') in ('pending', 'sending')}
        for qq in recipients:
            if (str(qq), text) not in queued:
                items.append({'id': uuid.uuid4().hex, 'qq': str(qq), 'text': text, 'status': 'pending'})
                queued.add((str(qq), text))
                added += 1
    return added


def claim_notice(path):
    """Durably claim a notice before any network operation.

    Args:
        path: Queue file.
    """
    import uuid
    with transaction(path, list) as items:
        for item in items:
            if item.get('status', 'pending') == 'pending':
                item.setdefault('id', uuid.uuid4().hex)
                item.update(status='sending', attempted_at=time.time())
                return dict(item)
    return None


def finish_notice(path, notice_id, status, reason=''):
    """Record a delivery result without retrying ambiguous sends.

    Args:
        path: Queue file.
        notice_id: Claimed item identifier.
        status: Sent or needs_review.
        reason: Non-sensitive error category.
    """
    with transaction(path, list) as items:
        for item in items:
            if item.get('id') == notice_id:
                item.update(status=status, reason=reason, finished_at=time.time())
                break
        sent = [x for x in items if x.get('status') == 'sent']
        keep = {x.get('id') for x in sent[-200:]}
        items[:] = [x for x in items if x.get('status') != 'sent' or x.get('id') in keep]


def recover_notices(path):
    """Mark interrupted sends for review on service initialization.

    Args:
        path: Queue file.
    """
    with transaction(path, list) as items:
        for item in items:
            if item.get('status') == 'sending':
                item.update(status='needs_review', reason='interrupted')
