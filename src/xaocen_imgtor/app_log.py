"""Small, dependency-free diagnostic log for recoverable desktop errors."""

from __future__ import annotations

import os
import time
import traceback
from pathlib import Path

from .paths import APP_DIR, RUNTIME_DIR


BASE_DIR = APP_DIR
LOG_DIR = RUNTIME_DIR
LOG_PATH = LOG_DIR / 'xaocen-imgtor.log'
MAX_LOG_BYTES = 1_000_000
_LAST_EVENT = {}


def log_exception(code: str, message: str, exc: BaseException | None = None) -> None:
    """Append one compact diagnostic event; logging must never break the app."""
    try:
        now = time.monotonic()
        if now - _LAST_EVENT.get(code, 0.0) < 3.0:
            return
        _LAST_EVENT[code] = now
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if LOG_PATH.exists() and LOG_PATH.stat().st_size >= MAX_LOG_BYTES:
            backup = LOG_PATH.with_suffix('.previous.log')
            try:
                os.replace(LOG_PATH, backup)
            except OSError:
                pass
        stamp = time.strftime('%Y-%m-%d %H:%M:%S')
        detail = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc else ''
        with LOG_PATH.open('a', encoding='utf-8') as stream:
            stream.write(f'[{stamp}] [{code}] {message}\n')
            if detail:
                stream.write(detail.rstrip() + '\n')
    except OSError:
        pass
