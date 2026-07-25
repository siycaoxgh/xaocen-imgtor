"""Tiny cross-process status handoff for native capture engines and the web UI."""

import json
import os
import tempfile
import time
import uuid
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STATUS_PATH = BASE_DIR / 'archive' / 'runtime' / '.xaocen-status.json'
_LEVELS = {'success', 'error', 'warning', 'info', 'progress'}


def publish_status(level, message, path=''):
    """Atomically publish the latest native-operation result."""
    event = {
        'id': uuid.uuid4().hex,
        'level': level if level in _LEVELS else 'info',
        'message': str(message),
        'path': str(path or ''),
        'timestamp': time.time(),
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.xaocen-status-', suffix='.tmp',
                                     dir=str(STATUS_PATH.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(event, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, STATUS_PATH)
    finally:
        if os.path.exists(temporary):
            try:
                os.unlink(temporary)
            except OSError:
                pass
    return event


def read_status():
    """Read the most recent status event; invalid or missing data is ignored."""
    try:
        event = json.loads(STATUS_PATH.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(event, dict) or not event.get('id') or not event.get('message'):
        return None
    event['level'] = event.get('level') if event.get('level') in _LEVELS else 'info'
    return event
