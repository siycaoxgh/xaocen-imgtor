#!/usr/bin/env python3
"""Single source of truth for configuration, validation and migrations."""

import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from .paths import APP_DIR, RUNTIME_DIR
from .ratio_presets import normalize_ratio
from .presets import GIF_FORMATS, GIF_MODES, IMAGE_FORMATS, SELECTION_MODES

BASE_DIR = APP_DIR
CONFIG_PATH = BASE_DIR / 'config.json'
LOCK_TIMEOUT_SECONDS = 5.0
CURRENT_CONFIG_VERSION = 4
DEFAULT_CONFIG = {
    'config_version': CURRENT_CONFIG_VERSION,
    'hotkey': 'ctrl+shift+x',
    'default_mode': 'ratio',
    'default_ratio': '16:9',
    'fixed_width_str': '400px',
    'fixed_height_str': '320px',
    'fixed_width': 400,
    'fixed_height': 320,
    'save_directory': '',
    'auto_save': True,
    'auto_clipboard': True,
    'file_format': 'png',
    'file_prefix': 'screenshot_',
    'language': 'zh',
    'gif_format': 'gif',
    'gif_fps': 10,
    'gif_ratio': 'free',
    'gif_mode': None,
    'gif_fixed_width_str': '400px',
    'gif_fixed_height_str': '320px',
    'record_start_key': 'enter',
    'record_stop_key': 'f9',
    'theme': 'light',
    'shortcut_capture': False,
    'start_with_windows': False,
    # Empty means the stable per-user directory under LOCALAPPDATA.  A custom
    # absolute directory is useful for portable installs, e.g. <app>\plugins.
    'plugin_directory': '',
}

_FORMATS = set(IMAGE_FORMATS)
_GIF_FORMATS = set(GIF_FORMATS)
_MODES = set(SELECTION_MODES)
_GIF_MODES = set(GIF_MODES)


def migrate_config(data):
    """Upgrade config while preserving future fields except retired markers."""
    migrated = dict(data or {})
    # Removed in v4.6.5: native overlays no longer navigate the web UI.
    migrated.pop('ui_panel_request', None)
    try:
        version = int(migrated.get('config_version', 0))
    except (TypeError, ValueError):
        version = 0

    # Version 0 was the pre-migration format. Preserve common legacy names.
    if version < 1:
        aliases = {
            'save_dir': 'save_directory',
            'format': 'file_format',
            'gif_output_format': 'gif_format',
            'record_end_key': 'record_stop_key',
        }
        for old, new in aliases.items():
            if new not in migrated and old in migrated:
                migrated[new] = migrated[old]
        migrated['config_version'] = 1

    if version < 2:
        migrated.setdefault('gif_fixed_width_str', '400px')
        migrated.setdefault('gif_fixed_height_str', '320px')

    if version < 4:
        migrated.setdefault('plugin_directory', '')

    migrated['config_version'] = CURRENT_CONFIG_VERSION
    return migrated


def _valid_shortcuts(config):
    from .shortcuts import validate_all

    values, errors = validate_all(
        config.get('hotkey', DEFAULT_CONFIG['hotkey']),
        config.get('record_start_key', DEFAULT_CONFIG['record_start_key']),
        config.get('record_stop_key', DEFAULT_CONFIG['record_stop_key']),
    )
    defaults = {
        'hotkey': DEFAULT_CONFIG['hotkey'],
        'record_start_key': DEFAULT_CONFIG['record_start_key'],
        'record_stop_key': DEFAULT_CONFIG['record_stop_key'],
    }
    if errors.get('record_stop_key') == 'same_as_start':
        config['record_start_key'] = defaults['record_start_key']
        config['record_stop_key'] = defaults['record_stop_key']
    else:
        for field, value in values.items():
            if not errors.get(field):
                config[field] = value
        for field in errors:
            if field in defaults:
                config[field] = defaults[field]

    values, errors = validate_all(
        config['hotkey'], config['record_start_key'], config['record_stop_key'])
    if errors:
        config.update(defaults)
    else:
        config.update(values)


def normalize_config(data):
    """Merge defaults, migrate old values, and normalize all known fields."""
    config = {**DEFAULT_CONFIG, **migrate_config(data)}
    config['config_version'] = CURRENT_CONFIG_VERSION

    if config.get('default_mode') not in _MODES:
        config['default_mode'] = DEFAULT_CONFIG['default_mode']
    default_ratio = normalize_ratio(config.get('default_ratio'))
    if not default_ratio:
        config['default_ratio'] = DEFAULT_CONFIG['default_ratio']
    else:
        config['default_ratio'] = default_ratio
    if config.get('file_format') not in _FORMATS:
        config['file_format'] = DEFAULT_CONFIG['file_format']
    if config.get('gif_format') not in _GIF_FORMATS:
        config['gif_format'] = DEFAULT_CONFIG['gif_format']
    if config.get('theme') not in {'light', 'dark'}:
        config['theme'] = DEFAULT_CONFIG['theme']
    if config.get('language') not in {'zh', 'en'}:
        config['language'] = DEFAULT_CONFIG['language']
    if config.get('gif_ratio') != 'free':
        gif_ratio = normalize_ratio(config.get('gif_ratio'))
        config['gif_ratio'] = gif_ratio or DEFAULT_CONFIG['gif_ratio']
    if config.get('gif_mode') not in _GIF_MODES:
        config['gif_mode'] = 'free' if config.get('gif_ratio') == 'free' else 'ratio'

    try:
        config['gif_fps'] = max(1, min(60, int(config.get('gif_fps', DEFAULT_CONFIG['gif_fps']))))
    except (TypeError, ValueError):
        config['gif_fps'] = DEFAULT_CONFIG['gif_fps']
    config['auto_save'] = bool(config.get('auto_save'))
    config['auto_clipboard'] = bool(config.get('auto_clipboard'))
    config['shortcut_capture'] = bool(config.get('shortcut_capture'))
    plugin_directory = config.get('plugin_directory', '')
    if not isinstance(plugin_directory, str) or not plugin_directory.strip():
        config['plugin_directory'] = ''
    else:
        candidate = Path(plugin_directory).expanduser()
        # Plugin code must never be discovered from a relative working path.
        config['plugin_directory'] = str(candidate.resolve()) if candidate.is_absolute() else ''
    _valid_shortcuts(config)
    return config


def _read_raw_config():
    try:
        with CONFIG_PATH.open('r', encoding='utf-8') as stream:
            data = json.load(stream)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


@contextmanager
def _config_write_lock():
    """Serialize read-modify-write updates from the web and native processes."""
    lock_path = (RUNTIME_DIR / 'config.json.lock'
                 if CONFIG_PATH.resolve() == (BASE_DIR / 'config.json').resolve()
                 else CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + '.lock'))
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a+b') as stream:
        deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    stream.seek(0)
                    if not stream.read(1):
                        stream.seek(0)
                        stream.write(b'0')
                        stream.flush()
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Timed out waiting for the configuration write lock.')
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                if os.name == 'nt':
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            except (OSError, UnboundLocalError):
                pass


def _write_config_atomic(merged):
    """Atomically replace config.json. Caller must hold _config_write_lock."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f'.{CONFIG_PATH.stem}.', suffix='.tmp', dir=str(CONFIG_PATH.parent)
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(merged, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, CONFIG_PATH)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def load_config():
    """Read, migrate and normalize configuration safely."""
    raw = _read_raw_config()
    config = normalize_config(raw)
    if raw and raw.get('config_version') != CURRENT_CONFIG_VERSION:
        return update_config({})
    return config


def save_config(data):
    """Compatibility full save. New code should prefer update_config(changes)."""
    return update_config(data)


def update_config(changes):
    """Merge a small settings patch while holding an inter-process write lock."""
    if not isinstance(changes, dict):
        raise TypeError('Configuration changes must be a dictionary.')
    with _config_write_lock():
        current = normalize_config(_read_raw_config())
        current.update(changes)
        merged = normalize_config(current)
        _write_config_atomic(merged)
        return merged


def config_lock_error_message() -> str:
    """Stable UI text for a recoverable cross-process configuration timeout."""
    return 'Configuration is busy; please try again.'
