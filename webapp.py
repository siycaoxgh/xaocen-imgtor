#!/usr/bin/env python3
"""Modern lightweight HTML/CSS launcher hosted by pywebview."""
import base64, binascii, heapq, io, mimetypes, os, platform, re, subprocess, sys, tempfile, threading, tkinter as tk
from collections import OrderedDict
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parent / 'src'
if _SRC_ROOT.is_dir() and str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

from xaocen_imgtor.config_manager import (DEFAULT_CONFIG, config_lock_error_message,
                                           load_config, update_config)
from xaocen_imgtor.ratio_presets import RATIO_PRESETS
from xaocen_imgtor.presets import (GIF_FORMATS, GIF_FPS, GIF_MODES, ICO_ALLOWED_SIZES,
                                   ICO_RECOMMENDED_SIZES, IMAGE_FORMATS, SELECTION_MODES)
from xaocen_imgtor.plugin_manager import (discover_plugins, ensure_plugin_root,
                                           install_plugin_package, plugin_root,
                                           validate_plugin_root)
from xaocen_imgtor.plugin_host import run_plugin
from xaocen_imgtor.runtime_status import read_status
from xaocen_imgtor.shortcuts import validate_all
from xaocen_imgtor.instance_lock import InstanceLock
from xaocen_imgtor.startup import set_enabled as set_startup_enabled

# In a PyInstaller build, UI assets and worker entry points are unpacked into
# _MEIPASS.  Keep user data/plugins beside the executable instead of writing
# into that temporary directory.
BASE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else BASE
UI = BASE / 'ui' / 'index.html'
ICON_PATH = BASE / 'resources' / 'xaocen-imgtor.ico'
APP_TITLE = 'XAOCEN ImgTor v5.3.2'
MAX_CROP_SOURCES = 256
MAX_PREVIEW_EDGE = 2048
MAX_IMAGE_PREVIEW_BYTES = 16 * 1024 * 1024
MAX_ANIM_PREVIEW_EDGE = 960
MAX_ANIM_PREVIEW_FRAMES = 20
MAX_VIDEO_PREVIEW_BYTES = 100 * 1024 * 1024
MAX_CROP_SOURCE_BYTES = 64 * 1024 * 1024
PENDING_ITEMS = 4


def _find_native_window(title):
    """Find the top-level app window without touching pywebview/WebView2."""
    if os.name != 'nt':
        return 0
    import ctypes
    user32 = ctypes.windll.user32
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    user32.FindWindowW.restype = ctypes.c_void_p
    return user32.FindWindowW(None, title) or 0


def _show_main_window(title):
    """Show/focus the window from a tray thread using Win32 messages only."""
    if os.name != 'nt':
        return False
    import ctypes
    hwnd = _find_native_window(title)
    if not hwnd:
        return False
    user32 = ctypes.windll.user32
    user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True


def _request_main_window_close(api, title, tray):
    """Ask the GUI thread to close; never call window.destroy from the tray thread."""
    api.exit_requested = True
    if tray:
        tray.stop()
    if os.name == 'nt':
        import ctypes
        hwnd = _find_native_window(title)
        if hwnd:
            ctypes.windll.user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
            return True
    return False

def save_dir(cfg):
    return Path(cfg['save_directory']) if cfg.get('save_directory') else Path.home() / 'Pictures' / 'drawru-imgter'

def reveal(path):
    path = str(path)
    if os.name == 'nt': subprocess.Popen(['explorer', path])
    elif platform.system() == 'Darwin': subprocess.Popen(['open', path])
    else: subprocess.Popen(['xdg-open', path])

class API:
    def __init__(self):
        self.processes = {}
        self._exit_event = threading.Event()
        self._thumb_cache = OrderedDict()
        self._thumb_cache_bytes = 0
        self._video_thumb_cache = OrderedDict()
        self._crop_sources = OrderedDict()
        self._motion_video_sources = OrderedDict()
        # Keep the native pywebview window private.  Public attributes on a
        # JS API object may be reflected by pywebview; exposing Window.native
        # makes WinForms walk AccessibilityObject recursively and can freeze
        # the app during startup.
        self._window = None
        previous_status = read_status() or {}
        self._last_runtime_status_id = previous_status.get('id', '')

    @property
    def exit_requested(self):
        return self._exit_event.is_set()

    @exit_requested.setter
    def exit_requested(self, value):
        if value:
            self._exit_event.set()
        else:
            self._exit_event.clear()

    @staticmethod
    def _ratio_text(width, height):
        from math import gcd
        divisor = gcd(int(width), int(height)) or 1
        return f'{int(width) // divisor}:{int(height) // divisor}'

    @staticmethod
    def _motion_photo_info(path):
        """Recognize JPEG+MP4 Motion Photos without loading the full file."""
        if path.suffix.lower() not in {'.jpg', '.jpeg'}:
            return {'motion_photo': False, 'video_length': 0}
        try:
            with path.open('rb') as handle:
                head = handle.read(65_536)
                match = re.search(rb'(?:GCamera:)?MicroVideoOffset="(\d+)"', head)
                if not match:
                    match = re.search(rb'Item:Length="(\d+)"', head)
                length = int(match.group(1)) if match else 0
                if length <= 12 or length >= path.stat().st_size:
                    return {'motion_photo': False, 'video_length': 0}
                handle.seek(-length, os.SEEK_END)
                return {'motion_photo': handle.read(12)[4:8] == b'ftyp', 'video_length': length}
        except (OSError, ValueError):
            return {'motion_photo': False, 'video_length': 0}

    def _make_thumbnail(self, path):
        key = str(path.resolve())
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self._thumb_cache.get(key)
        if cached and cached[:2] == signature:
            self._thumb_cache.move_to_end(key)
            return cached[2]

        from PIL import Image, ImageSequence
        try:
            with Image.open(path) as image:
                width, height = image.size
                animated = bool(getattr(image, 'is_animated', False))
                frames = int(getattr(image, 'n_frames', 1))
                metadata = {
                    'format': image.format or path.suffix.lstrip('.').upper(),
                    'width': width,
                    'height': height,
                    'ratio': self._ratio_text(width, height),
                    'animated': animated,
                    'frames': frames if animated else 1,
                    'duration': int(image.info.get('duration', 0) or 0),
                }
                metadata.update(self._motion_photo_info(path))
                if animated:
                    thumb_frames = []
                    durations = []
                    for index, frame in enumerate(ImageSequence.Iterator(image)):
                        if index >= MAX_ANIM_PREVIEW_FRAMES:
                            break
                        frame = frame.convert('RGBA')
                        frame.thumbnail((320, 220), Image.Resampling.LANCZOS)
                        thumb_frames.append(frame.copy())
                        durations.append(int(frame.info.get('duration', image.info.get('duration', 100)) or 100))
                    if not thumb_frames:
                        thumb_frames = [image.convert('RGBA')]
                        durations = [100]
                    output = io.BytesIO()
                    thumb_frames[0].save(output, format='GIF', save_all=True,
                                         append_images=thumb_frames[1:], loop=0,
                                         duration=durations, optimize=False)
                    payload = output.getvalue()
                    metadata['thumb'] = 'data:image/gif;base64,' + base64.b64encode(payload).decode('ascii')
                    poster = io.BytesIO()
                    thumb_frames[0].convert('RGB').save(poster, format='JPEG', quality=82)
                    metadata['poster'] = 'data:image/jpeg;base64,' + base64.b64encode(poster.getvalue()).decode('ascii')
                else:
                    image.thumbnail((320, 220), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.convert('RGB').save(output, format='JPEG', quality=82)
                    payload = output.getvalue()
                    data_url = 'data:image/jpeg;base64,' + base64.b64encode(payload).decode('ascii')
                    metadata['thumb'] = data_url
                    metadata['poster'] = data_url
                old = self._thumb_cache.pop(key, None)
                if old:
                    self._thumb_cache_bytes -= old[3]
                entry_size = len(metadata.get('thumb', '')) + len(metadata.get('poster', ''))
                self._thumb_cache[key] = (signature[0], signature[1], metadata, entry_size)
                self._thumb_cache_bytes += entry_size
                while len(self._thumb_cache) > 256 or self._thumb_cache_bytes > 32 * 1024 * 1024:
                    old_key, old_value = self._thumb_cache.popitem(last=False)
                    self._thumb_cache_bytes -= old_value[3]
                return metadata
        except Exception:
            return {'thumb': '', 'poster': '', 'format': path.suffix.lstrip('.').upper(),
                    'width': 0, 'height': 0, 'ratio': '', 'animated': False,
                    'frames': 1, 'duration': 0, 'motion_photo': False, 'video_length': 0}
    def state(self):
        cfg = load_config(); folder = save_dir(cfg)
        files = []
        if folder.is_dir():
            candidates = []
            for path in folder.iterdir():
                if path.suffix.lower() not in {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.ico', '.tif', '.tiff', '.mp4'}:
                    continue
                try:
                    candidates.append((path.stat().st_mtime, path))
                except OSError:
                    pass
            for mtime, path in heapq.nlargest(100, candidates, key=lambda item: item[0]):
                try:
                    stat = path.stat()
                    item = {'name': path.name, 'path': str(path), 'size': stat.st_size,
                            'mtime': mtime}
                    if path.suffix.lower() == '.mp4':
                        key = str(path.resolve())
                        signature = (stat.st_mtime_ns, stat.st_size)
                        cached_video_thumb = self._video_thumb_cache.get(key)
                        if cached_video_thumb and cached_video_thumb[:2] == signature:
                            self._video_thumb_cache.move_to_end(key)
                            poster = cached_video_thumb[2]
                        else:
                            poster = ''
                        item.update({'thumb': '', 'poster': '', 'format': 'MP4', 'width': 0,
                                      'height': 0, 'ratio': '', 'animated': False, 'video': True,
                                      'frames': 1, 'duration': 0})
                        if poster:
                            item.update({'thumb': poster, 'poster': poster})
                    else:
                        item.update(self._make_thumbnail(path))
                        item['video'] = False
                    files.append(item)
                except OSError:
                    continue
        listener = self.processes.get('screenshot')
        generated_dirs = {'__pycache__', '.git', 'archive', 'logs'}
        project_files = sum(
            1 for path in BASE.rglob('*')
            if path.is_file() and not any(part in generated_dirs for part in path.parts)
            and path.name not in {'.drawru-imgter-main.lock', '.drawru-imgter-status.json', 'config.json.lock'}
        )
        return {'config': cfg, 'ratio_presets': list(RATIO_PRESETS),
                'image_formats': list(IMAGE_FORMATS), 'gif_formats': list(GIF_FORMATS),
                'gif_fps': list(GIF_FPS), 'selection_modes': list(SELECTION_MODES),
                'gif_modes': list(GIF_MODES), 'files': files[:100],
                'listener_running': bool(listener and listener.poll() is None),
                # Discovery is manifest-only: the core never imports or runs
                # optional plugin code.
                'plugins': discover_plugins(), 'plugin_root': str(plugin_root()),
                'project_stats': {'completed_items': 8, 'project_files': project_files,
                                  'pending_items': PENDING_ITEMS,
                                  'automated_tests': self._automated_test_count()}}

    def gif_settings(self):
        cfg = load_config()
        return {key: cfg.get(key) for key in (
            'gif_fps', 'gif_format', 'gif_ratio', 'gif_mode',
            'gif_fixed_width_str', 'gif_fixed_height_str')}

    @staticmethod
    def _supported_image_suffix(path):
        return path.suffix.lower() in {
            '.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp',
            '.ico', '.tif', '.tiff', '.mp4',
        }

    def _gallery_target(self, path):
        """Resolve a path only when it is a file in the configured gallery."""
        if not path:
            return None
        folder = save_dir(load_config()).resolve()
        target = Path(path).expanduser().resolve()
        if target.parent != folder or not self._supported_image_suffix(target):
            return None
        return target

    @staticmethod
    def _automated_test_count():
        """Count test cases in the repository so About stays accurate."""
        tests_dir = BASE / 'tests'
        total = 0
        try:
            for path in tests_dir.glob('test_*.py'):
                total += sum(
                    1 for line in path.read_text(encoding='utf-8').splitlines()
                    if line.strip().startswith('def test_')
                )
        except (OSError, UnicodeError):
            return 0
        return total

    def save_settings(self, data):
        data = dict(data or {})
        try:
            data['gif_fps'] = max(1, min(60, int(data.get('gif_fps', DEFAULT_CONFIG['gif_fps']))))
        except (TypeError, ValueError):
            return {'ok': False, 'errors': {'gif_fps': 'invalid_number'}, 'config': load_config()}
        values, shortcut_errors = validate_all(
            data.get('hotkey', DEFAULT_CONFIG['hotkey']),
            data.get('record_start_key', DEFAULT_CONFIG['record_start_key']),
            data.get('record_stop_key', DEFAULT_CONFIG['record_stop_key']))
        if shortcut_errors:
            return {'ok': False, 'errors': shortcut_errors, 'config': load_config()}
        data.update(values)
        shortcuts = {field: data[field] for field in (
            'hotkey', 'record_start_key', 'record_stop_key') if field in data}
        try:
            return {'ok': True, 'config': self.state_after(update_config(shortcuts))['config']}
        except TimeoutError:
            return {'ok': False, 'errors': {'config': 'config_busy'}, 'message': config_lock_error_message(),
                    'config': load_config()}

    def set_shortcut_capture(self, enabled):
        try:
            update_config({'shortcut_capture': bool(enabled)})
            return {'ok': True}
        except TimeoutError:
            return {'ok': False, 'error': 'config_busy', 'message': config_lock_error_message()}

    def poll_runtime_status(self):
        """Return each native-engine status event at most once per web session."""
        event = read_status()
        if not event or event.get('id') == self._last_runtime_status_id:
            return None
        self._last_runtime_status_id = event['id']
        return event

    def save_shortcut(self, field, value):
        fields = {'hotkey', 'record_start_key', 'record_stop_key'}
        if field not in fields:
            return {'ok': False, 'errors': {field: 'invalid_field'}, 'config': load_config()}
        return self.save_settings({field: value})

    def save_other_settings(self, data):
        """Persist non-shortcut settings without overwriting pending shortcut edits."""
        current = {}
        for field in ('gif_fps', 'gif_format', 'gif_ratio', 'gif_mode', 'gif_fixed_width_str',
                      'gif_fixed_height_str', 'language', 'save_directory', 'theme',
                      'auto_save', 'auto_clipboard', 'default_mode',
                      'default_ratio', 'fixed_width_str', 'fixed_height_str',
                      'file_format', 'file_prefix', 'start_with_windows'):
            if field in data:
                current[field] = data[field]
        try:
            if 'gif_fps' in current:
                current['gif_fps'] = max(1, min(60, int(current['gif_fps'])))
        except (TypeError, ValueError):
            return {'ok': False, 'errors': {'gif_fps': 'invalid_number'}, 'config': load_config()}
        try:
            if 'start_with_windows' in current:
                set_startup_enabled(bool(current['start_with_windows']))
            return {'ok': True, 'config': self.state_after(update_config(current))['config']}
        except TimeoutError:
            return {'ok': False, 'errors': {'config': 'config_busy'}, 'message': config_lock_error_message(),
                    'config': load_config()}
        except OSError as exc:
            if str(exc) == 'startup_not_supported':
                return {'ok': False, 'errors': {'start_with_windows': 'unsupported'},
                        'message': '开机自启动仅支持 Windows。', 'config': load_config()}
            return {'ok': False, 'errors': {'start_with_windows': 'startup_failed'},
                    'message': '开机自启动设置失败，请检查系统权限。', 'config': load_config()}

    def state_after(self, cfg):
        folder = save_dir(cfg); folder.mkdir(parents=True, exist_ok=True)
        return self.state()

    def open_file(self, path):
        target = self._gallery_target(path)
        if target is None or not target.is_file():
            return {'ok': False, 'error': 'invalid_gallery_path'}
        reveal(target)
        return {'ok': True}
    def open_folder(self):
        folder = save_dir(load_config()); folder.mkdir(parents=True, exist_ok=True); reveal(folder); return True

    def plugins_state(self):
        """Return validated plugin manifests without loading plugin code."""
        return {'plugins': discover_plugins(), 'plugin_root': str(plugin_root())}

    def open_plugin_directory(self):
        """Create and reveal the external per-user plugin location."""
        root = ensure_plugin_root()
        reveal(root)
        return {'ok': True, 'path': str(root)}

    def choose_plugin_directory(self):
        """Choose a writable external plugin root; never use _MEIPASS."""
        if self._window is None:
            return None
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not paths:
            return None
        root, error = validate_plugin_root(paths[0])
        if root is None:
            return {'ok': False, 'error': error}
        try:
            config = update_config({'plugin_directory': str(root)})
        except TimeoutError:
            return {'ok': False, 'error': 'config_busy', 'message': config_lock_error_message()}
        return {'ok': True, 'path': str(root), 'config': config,
                'plugins': discover_plugins()}

    def reset_plugin_directory(self):
        try:
            config = update_config({'plugin_directory': ''})
        except TimeoutError:
            return {'ok': False, 'error': 'config_busy', 'message': config_lock_error_message()}
        return {'ok': True, 'path': str(plugin_root()), 'config': config,
                'plugins': discover_plugins()}

    def install_plugin_package(self):
        """Pick and safely install a verified .xaocen-plugin bundle."""
        if self._window is None:
            return {'ok': False, 'error': 'window_unavailable'}
        import webview
        paths = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            file_types=('XAOCEN plugin (*.xaocen-plugin)', 'All files (*.*)'),
        )
        if not paths:
            return {'ok': False, 'error': 'cancelled'}
        result = install_plugin_package(paths[0])
        result['plugins'] = discover_plugins()
        result['plugin_root'] = str(plugin_root())
        return result

    def run_plugin(self, plugin_id, command, payload=None):
        """Run one declared command after an explicit web UI action."""
        return run_plugin(plugin_id, command, payload)

    def choose_save_directory(self):
        if self._window is None:
            return None
        import webview
        paths = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        if not paths:
            return None
        path = paths[0]
        result = self.save_other_settings({'save_directory': path})
        return {'ok': True, 'path': path, 'config': result.get('config', load_config())}

    def _preview_data_url(self, target):
        """Build a bounded preview instead of loading an unbounded original."""
        from PIL import Image, ImageSequence

        with Image.open(target) as image:
            animated = bool(getattr(image, 'is_animated', False))
            if not animated and max(image.size) <= MAX_PREVIEW_EDGE \
                    and image.width * image.height <= 12_000_000 \
                    and target.stat().st_size <= MAX_IMAGE_PREVIEW_BYTES:
                mime = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                return mime, target.read_bytes()

            if animated:
                frames, durations = [], []
                for index, frame in enumerate(ImageSequence.Iterator(image)):
                    if index >= MAX_ANIM_PREVIEW_FRAMES:
                        break
                    duration = int(frame.info.get('duration', image.info.get('duration', 100)) or 100)
                    frame = frame.convert('RGBA')
                    frame.thumbnail((MAX_ANIM_PREVIEW_EDGE, MAX_ANIM_PREVIEW_EDGE), Image.Resampling.LANCZOS)
                    frames.append(frame.copy())
                    durations.append(duration)
                if frames:
                    output = io.BytesIO()
                    frames[0].save(output, format='GIF', save_all=True,
                                   append_images=frames[1:], loop=0,
                                   duration=durations, optimize=False)
                    return 'image/gif', output.getvalue()

            image.thumbnail((MAX_PREVIEW_EDGE, MAX_PREVIEW_EDGE), Image.Resampling.LANCZOS)
            output = io.BytesIO()
            if 'A' in image.getbands():
                image.save(output, format='PNG', optimize=True)
                return 'image/png', output.getvalue()
            image.convert('RGB').save(output, format='JPEG', quality=88, optimize=True)
            return 'image/jpeg', output.getvalue()

    def read_image(self, path):
        """Return a bounded preview for the in-app image viewer."""
        target = self._gallery_target(path)
        if target is None:
            return {'ok': False, 'error': 'invalid_gallery_path'}
        try:
            mime, raw = self._preview_data_url(target)
            payload = base64.b64encode(raw).decode('ascii')
            return {'ok': True, 'data_url': f'data:{mime};base64,{payload}'}
        except (OSError, ValueError) as exc:
            return {'ok': False, 'error': str(exc)}

    def read_video(self, path):
        """Return a bounded MP4 data URL for the in-app gallery player."""
        target = self._gallery_target(path)
        if target is None or target.suffix.lower() != '.mp4':
            return {'ok': False, 'error': 'invalid_gallery_path'}
        try:
            if target.stat().st_size > MAX_VIDEO_PREVIEW_BYTES:
                return {'ok': False, 'error': 'video_too_large'}
            return {'ok': True, 'data_url': 'data:video/mp4;base64,' +
                    base64.b64encode(target.read_bytes()).decode('ascii')}
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}

    def video_thumbnail(self, path):
        """Generate one small MP4 poster on demand through the optional plugin."""
        target = self._gallery_target(path)
        if target is None or target.suffix.lower() != '.mp4':
            return {'ok': False, 'error': 'invalid_gallery_path'}
        try:
            stat = target.stat()
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}
        key = str(target.resolve())
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self._video_thumb_cache.get(key)
        if cached and cached[:2] == signature:
            self._video_thumb_cache.move_to_end(key)
            return {'ok': True, 'data_url': cached[2]}
        result = run_plugin('video-recorder-ffmpeg', 'thumbnails', {
            'input_path': str(target), 'timestamps': [0.1],
        })
        items = result.get('data', {}).get('thumbnails', []) if result.get('ok') else []
        if not items or not items[0].get('data_url'):
            return {'ok': False, 'error': result.get('error', 'thumbnail_unavailable')}
        data_url = items[0]['data_url']
        self._video_thumb_cache[key] = (signature[0], signature[1], data_url)
        while len(self._video_thumb_cache) > 64:
            self._video_thumb_cache.popitem(last=False)
        return {'ok': True, 'data_url': data_url}

    def read_motion_photo_video(self, path):
        """Extract only the embedded MP4 of a gallery Motion Photo for playback."""
        target = self._gallery_target(path)
        if target is None:
            return {'ok': False, 'error': 'invalid_gallery_path'}
        info = self._motion_photo_info(target)
        if not info['motion_photo']:
            return {'ok': False, 'error': 'not_motion_photo'}
        try:
            with target.open('rb') as handle:
                handle.seek(-info['video_length'], os.SEEK_END)
                payload = handle.read(info['video_length'])
            return {'ok': True, 'data_url': 'data:video/mp4;base64,' +
                    base64.b64encode(payload).decode('ascii')}
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}

    def delete_file(self, path):
        target = self._gallery_target(path)
        if target is None:
            return {'ok': False, 'error': 'invalid_gallery_path'}
        try:
            target.unlink()
            old = self._thumb_cache.pop(str(target), None)
            if old:
                self._thumb_cache_bytes -= old[3]
            return {'ok': True}
        except OSError as exc:
            return {'ok': False, 'error': str(exc)}

    def choose_crop_image(self):
        # JS API methods run on a pywebview worker thread.  Tk's native file
        # dialog may only run from Tk's main loop, so use the webview-owned
        # dialog which marshals correctly to the GUI backend.
        if self._window is None:
            return None
        import webview
        paths = self._window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=False,
            file_types=(
                'Image files (*.png;*.jpg;*.jpeg;*.bmp;*.gif;*.webp;*.ico;*.tif;*.tiff)',
                'All files (*.*)',
            ),
        )
        if not paths:
            return None
        source = Path(paths[0]).resolve()
        if not source.is_file() or source.stat().st_size > MAX_CROP_SOURCE_BYTES:
            return {'ok': False, 'error': 'crop_source_too_large'}
        source_key = str(source)
        self._crop_sources[source_key] = None
        self._crop_sources.move_to_end(source_key)
        while len(self._crop_sources) > MAX_CROP_SOURCES:
            self._crop_sources.popitem(last=False)
        try:
            mime, preview = self._preview_data_url(source)
            from PIL import Image
            with Image.open(source) as image:
                source_size = {'width': image.width, 'height': image.height}
        except (OSError, ValueError):
            return {'ok': False, 'error': 'crop_source_invalid'}
        return {'path': str(source), 'name': source.name,
                'data_url': f'data:{mime};base64,{base64.b64encode(preview).decode("ascii")}',
                'source_size': source_size}

    def choose_motion_video(self):
        """Choose an existing MP4 for the optional Motion Photo exporter."""
        if self._window is None:
            return None
        import webview
        paths = self._window.create_file_dialog(
            webview.FileDialog.OPEN, allow_multiple=False,
            file_types=('MP4 video (*.mp4)', 'All files (*.*)'),
        )
        if not paths:
            return None
        source = Path(paths[0]).resolve()
        if source.suffix.lower() != '.mp4' or not source.is_file():
            return {'ok': False, 'error': 'motion_video_invalid'}
        self._motion_video_sources[str(source)] = None
        self._motion_video_sources.move_to_end(str(source))
        while len(self._motion_video_sources) > MAX_CROP_SOURCES:
            self._motion_video_sources.popitem(last=False)
        return {'ok': True, 'path': str(source), 'name': source.name}

    def read_motion_video(self, video_path):
        """Load a user-selected MP4 only when its timeline thumbnail is opened."""
        if not isinstance(video_path, str):
            return {'ok': False, 'error': 'motion_video_invalid'}
        target = Path(video_path).expanduser().resolve()
        if str(target) not in self._motion_video_sources or not target.is_file():
            return {'ok': False, 'error': 'motion_video_invalid'}
        try:
            if target.stat().st_size > MAX_VIDEO_PREVIEW_BYTES:
                return {'ok': False, 'error': 'video_too_large'}
            return {'ok': True, 'data_url': 'data:video/mp4;base64,' +
                    base64.b64encode(target.read_bytes()).decode('ascii')}
        except OSError as exc:
            return {'ok': False, 'error': 'motion_video_read_failed', 'detail': str(exc)}

    def inspect_motion_video(self, video_path):
        """Return MP4 duration through the optional FFmpeg plugin."""
        if not isinstance(video_path, str) or Path(video_path).suffix.lower() != '.mp4':
            return {'ok': False, 'error': 'motion_video_invalid'}
        return run_plugin('video-recorder-ffmpeg', 'probe', {'input_path': str(Path(video_path).resolve())})

    def motion_video_thumbnails(self, video_path, duration_seconds):
        """Request four small timeline stills; never send the source video to JS."""
        if not isinstance(video_path, str) or Path(video_path).suffix.lower() != '.mp4':
            return {'ok': False, 'error': 'motion_video_invalid'}
        try:
            duration = max(0.1, float(duration_seconds))
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'motion_video_invalid'}
        timestamps = [round(duration * point, 3) for point in (0.0, .33, .66, .95)]
        return run_plugin('video-recorder-ffmpeg', 'thumbnails', {
            'input_path': str(Path(video_path).resolve()), 'timestamps': timestamps,
        })

    def export_android_motion_photo(self, image_data_url, image_name, video_path,
                                    profile='google', clip_start=0, clip_duration=0):
        """Delegate a cropped JPEG + user-chosen MP4 to the optional plugin."""
        from PIL import Image
        if (not isinstance(video_path, str) or Path(video_path).suffix.lower() != '.mp4'
                or profile not in {'google', 'xiaomi'}):
            return {'ok': False, 'error': 'motion_video_invalid'}
        try:
            clip_start, clip_duration = max(0.0, float(clip_start)), float(clip_duration)
        except (TypeError, ValueError):
            return {'ok': False, 'error': 'motion_clip_invalid'}
        if clip_duration < 0 or clip_duration > 15:
            return {'ok': False, 'error': 'motion_clip_invalid'}
        try:
            _header, payload = image_data_url.split(',', 1)
            raw = base64.b64decode(payload, validate=True)
            image = Image.open(io.BytesIO(raw)).convert('RGB')
        except (AttributeError, ValueError, binascii.Error, OSError):
            return {'ok': False, 'error': 'invalid_crop_data'}
        folder = save_dir(load_config())
        folder.mkdir(parents=True, exist_ok=True)
        stem = ''.join(char if char.isalnum() or char in ('-', '_') else '_' for char in Path(image_name or 'image').stem)
        stem = stem.strip('._') or 'image'
        suffix = '_Xiaomi_MP' if profile == 'xiaomi' else '_MP'
        target = folder / f'{stem}{suffix}.jpg'
        number = 2
        while target.exists():
            target = folder / f'{stem}{suffix}_{number}.jpg'
            number += 1
        temporary = clipped_video = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpg', prefix='.drawru-motion-', delete=False) as handle:
                temporary = Path(handle.name)
            image.save(temporary, format='JPEG', quality=95)
            video_input = Path(video_path).resolve()
            effective_clip_duration = clip_duration
            if profile == 'xiaomi' and effective_clip_duration == 0:
                # Xiaomi-recognized reference files contain an AAC stream.
                # Re-encode the full (1–15 second) source with local silence.
                probe = run_plugin('video-recorder-ffmpeg', 'probe', {
                    'input_path': str(video_input),
                })
                if not probe.get('ok'):
                    return probe
                effective_clip_duration = float(probe.get('data', {}).get('duration_seconds', 0))
                if not 0 < effective_clip_duration <= 15:
                    return {'ok': False, 'error': 'motion_video_duration_invalid'}
            if effective_clip_duration > 0:
                with tempfile.NamedTemporaryFile(suffix='.mp4', prefix='.drawru-motion-clip-', delete=False) as handle:
                    clipped_video = Path(handle.name)
                clipped = run_plugin('video-recorder-ffmpeg', 'clip', {
                    'input_path': str(video_input), 'output_path': str(clipped_video),
                    'start_seconds': clip_start, 'duration_seconds': effective_clip_duration,
                    'ensure_audio': profile == 'xiaomi',
                })
                if not clipped.get('ok'):
                    return clipped
                video_input = clipped_video
            result = run_plugin('android-motion-photo', 'create', {
                'image_path': str(temporary), 'video_path': str(video_input),
                'output_path': str(target), 'profile': profile,
            })
            if not result.get('ok'):
                return result
            return {'ok': True, 'path': result.get('data', {}).get('output_path', str(target)),
                    'profile': profile, 'clip_duration': effective_clip_duration}
        except (OSError, ValueError) as error:
            return {'ok': False, 'error': 'motion_export_failed', 'detail': str(error)}
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
            if clipped_video:
                clipped_video.unlink(missing_ok=True)

    @staticmethod
    def _save_animated_crop(source, target, crop_rect):
        """Crop GIF, APNG, or animated WebP frames without flattening them."""
        from PIL import Image, ImageSequence

        temporary = None
        with Image.open(source) as original:
            if not bool(getattr(original, 'is_animated', False)):
                return False
            output_format = (original.format or '').upper()
            if output_format not in {'GIF', 'PNG', 'WEBP'}:
                return False
            left = max(0, int(round(crop_rect.get('x', 0))))
            top = max(0, int(round(crop_rect.get('y', 0))))
            right = min(original.width, left + max(1, int(round(crop_rect.get('width', 1)))))
            bottom = min(original.height, top + max(1, int(round(crop_rect.get('height', 1)))))
            if right <= left or bottom <= top:
                raise ValueError('invalid_crop_rect')
            frames, durations = [], []
            for frame in ImageSequence.Iterator(original):
                frames.append(frame.convert('RGBA').crop((left, top, right, bottom)))
                durations.append(int(frame.info.get('duration', original.info.get('duration', 100)) or 100))
            if not frames:
                return False
            encoded = ([frame.convert('P', palette=Image.Palette.ADAPTIVE) for frame in frames]
                       if output_format == 'GIF' else frames)
            with tempfile.NamedTemporaryFile(
                    suffix=target.suffix, prefix=f'.{target.stem}_', dir=target.parent,
                    delete=False) as handle:
                temporary = Path(handle.name)
            try:
                options = {'format': output_format, 'save_all': True,
                           'append_images': encoded[1:], 'duration': durations,
                           'loop': int(original.info.get('loop', 0))}
                if output_format == 'GIF':
                    options.update(disposal=2, optimize=False)
                elif output_format == 'PNG':
                    options.update(disposal=2, blend=0)
                else:
                    options.update(lossless=True, quality=95, method=6)
                encoded[0].save(temporary, **options)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        # The source file is closed before replacement, which is required on
        # Windows when target and source are the same animation.
        os.replace(temporary, target)
        return True

    @staticmethod
    def _save_ico_crop(source, target, crop_rect):
        """Crop every source ICO representation and preserve the size set."""
        from PIL import Image

        temporary = None
        with Image.open(source) as original:
            ico = getattr(original, 'ico', None)
            sizes = tuple(ico.sizes()) if ico else ()
            if len(sizes) < 2:
                return False
            base_width, base_height = original.size
            left = max(0, int(round(crop_rect.get('x', 0))))
            top = max(0, int(round(crop_rect.get('y', 0))))
            right = min(base_width, left + max(1, int(round(crop_rect.get('width', 1)))))
            bottom = min(base_height, top + max(1, int(round(crop_rect.get('height', 1)))))
            if right <= left or bottom <= top:
                raise ValueError('invalid_crop_rect')
            frames = []
            for size in sorted(set(sizes), key=lambda value: value[0] * value[1]):
                layer = ico.getimage(size).convert('RGBA')
                scale_x, scale_y = layer.width / base_width, layer.height / base_height
                box = (
                    max(0, round(left * scale_x)), max(0, round(top * scale_y)),
                    min(layer.width, round(right * scale_x)),
                    min(layer.height, round(bottom * scale_y)),
                )
                if box[2] > box[0] and box[3] > box[1]:
                    frames.append(layer.crop(box))
            if len(frames) < 2:
                return False
            primary = max(frames, key=lambda frame: frame.width * frame.height)
            with tempfile.NamedTemporaryFile(
                    suffix='.ico', prefix=f'.{target.stem}_', dir=target.parent,
                    delete=False) as handle:
                temporary = Path(handle.name)
            try:
                primary.save(temporary, format='ICO', append_images=frames,
                             sizes=[frame.size for frame in frames])
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        os.replace(temporary, target)
        return True

    @staticmethod
    def _save_static_crop(source, target, crop_rect):
        """Crop a selected source at original resolution, not preview resolution."""
        from PIL import Image

        temporary = None
        with Image.open(source) as original:
            left = max(0, int(round(crop_rect.get('x', 0))))
            top = max(0, int(round(crop_rect.get('y', 0))))
            right = min(original.width, left + max(1, int(round(crop_rect.get('width', 1)))))
            bottom = min(original.height, top + max(1, int(round(crop_rect.get('height', 1)))))
            if right <= left or bottom <= top:
                raise ValueError('invalid_crop_rect')
            image = original.convert('RGBA').crop((left, top, right, bottom))
            with tempfile.NamedTemporaryFile(
                    suffix=target.suffix, prefix=f'.{target.stem}_', dir=target.parent,
                    delete=False) as handle:
                temporary = Path(handle.name)
            try:
                suffix = target.suffix.lower()
                if suffix in {'.jpg', '.jpeg'}:
                    image.convert('RGB').save(temporary, format='JPEG', quality=95)
                elif suffix == '.bmp':
                    image.convert('RGB').save(temporary, format='BMP')
                elif suffix == '.webp':
                    image.save(temporary, format='WEBP', quality=95)
                elif suffix in {'.tif', '.tiff'}:
                    image.save(temporary, format='TIFF')
                else:
                    image.save(temporary, format='PNG')
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
        os.replace(temporary, target)
        return True

    @staticmethod
    def _rounded_image(source, radius_percent):
        """Return a full-size RGBA image with an antialiased rounded mask.

        The source alpha is multiplied by the mask instead of being replaced,
        so transparent pixels in the original PNG/WebP remain transparent.
        """
        from PIL import Image, ImageChops, ImageDraw

        with Image.open(source) as opened:
            if bool(getattr(opened, 'is_animated', False)) and int(getattr(opened, 'n_frames', 1) or 1) > 1:
                raise ValueError('rounded_animation_unsupported')
            source_info = dict(opened.info)
            if (opened.format or '').upper() == 'ICO' and getattr(opened, 'ico', None):
                sizes = tuple(opened.ico.sizes())
                if sizes:
                    largest = max(sizes, key=lambda size: size[0] * size[1])
                    image = opened.ico.getimage(largest).convert('RGBA')
                else:
                    image = opened.convert('RGBA')
            else:
                image = opened.convert('RGBA')

        width, height = image.size
        try:
            percent = float(radius_percent)
        except (TypeError, ValueError):
            raise ValueError('invalid_rounded_radius')
        if not 0 <= percent <= 50:
            raise ValueError('invalid_rounded_radius')

        # Use one rounded integer pixel radius for both UI and export.  The
        # high-resolution mask gives the final edge a stable antialias.
        radius_px = round(min(width, height) * percent / 100)
        scale = 4
        mask_large = Image.new('L', (width * scale, height * scale), 0)
        ImageDraw.Draw(mask_large).rounded_rectangle(
            (0, 0, width * scale - 1, height * scale - 1),
            radius=radius_px * scale,
            fill=255,
        )
        mask = mask_large.resize((width, height), Image.Resampling.LANCZOS)
        combined_alpha = ImageChops.multiply(image.getchannel('A'), mask)
        image.putalpha(combined_alpha)
        return image, source_info, radius_px, percent

    def save_rounded_image(self, data_url, filename, radius_percent=12,
                           output_format='png', source_path='', ico_sizes=None):
        """Apply a full-size rounded Alpha mask and export PNG, WebP or ICO."""
        output_format = str(output_format or '').lower()
        if output_format not in {'png', 'webp', 'ico'}:
            return {'ok': False, 'error': 'rounded_output_format_invalid'}

        selected_ico_sizes = None
        if output_format == 'ico':
            if ico_sizes is None:
                selected_ico_sizes = list(ICO_RECOMMENDED_SIZES)
            else:
                try:
                    selected_ico_sizes = sorted({int(size) for size in ico_sizes})
                except (TypeError, ValueError):
                    return {'ok': False, 'error': 'ico_size_invalid'}
                if not selected_ico_sizes:
                    return {'ok': False, 'error': 'ico_sizes_empty'}
                if any(size not in ICO_ALLOWED_SIZES for size in selected_ico_sizes):
                    return {'ok': False, 'error': 'ico_size_invalid'}

        source = Path(source_path).expanduser().resolve() if source_path else None
        if source:
            if str(source) not in self._crop_sources or not source.is_file():
                return {'ok': False, 'error': 'source_path_unavailable'}
        else:
            try:
                _header, payload = data_url.split(',', 1)
                raw = base64.b64decode(payload, validate=True)
                source = None
                image_data = io.BytesIO(raw)
            except (AttributeError, ValueError, binascii.Error):
                return {'ok': False, 'error': 'rounded_source_invalid'}

        folder = save_dir(load_config())
        folder.mkdir(parents=True, exist_ok=True)
        stem = Path(filename or 'image').stem or 'image'
        safe_stem = ''.join(char if char.isalnum() or char in ('-', '_') else '_'
                             for char in stem).strip('._') or 'image'
        target = folder / f'{safe_stem}_rounded.{output_format}'
        number = 2
        while target.exists():
            target = folder / f'{safe_stem}_rounded_{number}.{output_format}'
            number += 1

        temporary = None
        try:
            rounded, source_info, radius_px, percent = self._rounded_image(
                source if source else image_data, radius_percent)
            with tempfile.NamedTemporaryFile(
                    suffix=target.suffix, prefix=f'.{target.stem}_',
                    dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
            if output_format == 'ico':
                frames = self._build_ico_frames(rounded, selected_ico_sizes)
                frames[0].save(
                    temporary,
                    format='ICO',
                    append_images=frames[1:],
                    sizes=[frame.size for frame in frames],
                )
            else:
                options = {'format': output_format.upper()}
                if source_info.get('icc_profile'):
                    options['icc_profile'] = source_info['icc_profile']
                if output_format == 'png':
                    options['optimize'] = True
                else:
                    options.update(lossless=True, method=6)
                rounded.save(temporary, **options)
            os.replace(temporary, target)
            result = {
                'ok': True,
                'path': str(target),
                'width': rounded.width,
                'height': rounded.height,
                'radius_percent': percent,
                'radius_px': radius_px,
                'format': output_format,
            }
            if selected_ico_sizes is not None:
                result['sizes'] = selected_ico_sizes
            return result
        except ValueError as exc:
            if temporary:
                temporary.unlink(missing_ok=True)
            error = str(exc)
            if error == 'rounded_animation_unsupported':
                return {'ok': False, 'error': error}
            if error == 'invalid_rounded_radius':
                return {'ok': False, 'error': 'rounded_radius_invalid'}
            return {'ok': False, 'error': 'rounded_save_failed', 'detail': error}
        except OSError as exc:
            if temporary:
                temporary.unlink(missing_ok=True)
            return {'ok': False, 'error': 'rounded_save_failed', 'detail': str(exc)}

    @staticmethod
    def _build_ico_frames(image, sizes):
        """Create square RGBA ICO frames directly from the full-size master."""
        from PIL import Image

        frames = []
        for size in sizes:
            canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            scale = min(size / image.width, size / image.height)
            width = max(1, round(image.width * scale))
            height = max(1, round(image.height * scale))
            resized = image.resize((width, height), Image.Resampling.LANCZOS)
            position = ((size - width) // 2, (size - height) // 2)
            canvas.paste(resized, position, resized)
            frames.append(canvas)
        # Pillow's ICO writer only considers requested sizes up to the first
        # image's dimensions, so keep the largest frame first while retaining
        # every requested frame in the same file.
        return sorted(frames, key=lambda frame: frame.width * frame.height, reverse=True)

    def save_crop(self, data_url, filename, overwrite=False, source_path='', crop_rect=None):
        from PIL import Image
        try:
            _header, payload = data_url.split(',', 1)
            raw = base64.b64decode(payload, validate=True)
            image = Image.open(io.BytesIO(raw)).convert('RGBA')
        except (AttributeError, ValueError, binascii.Error, OSError):
            return {'ok': False, 'error': 'invalid_crop_data'}
        try:
            name = Path(filename).name or 'image.png'
            source = ''
            if overwrite:
                source = str(Path(source_path).expanduser().resolve()) if source_path else ''
                if source not in self._crop_sources or not Path(source).is_file():
                    return {'ok': False, 'error': 'source_path_unavailable'}
                target = Path(source)
            else:
                folder = save_dir(load_config()); folder.mkdir(parents=True, exist_ok=True)
                target = folder / f'{Path(name).stem}_cropped.png'
            suffix = target.suffix.lower()
            original_source = Path(source_path).expanduser().resolve() if source_path else None
            source_available = original_source and str(original_source) in self._crop_sources \
                and original_source.is_file()
            if source_available and crop_rect and self._save_animated_crop(original_source, target, crop_rect):
                pass
            elif source_available and suffix == '.ico' and crop_rect and self._save_ico_crop(original_source, target, crop_rect):
                pass
            elif source_available and crop_rect and self._save_static_crop(original_source, target, crop_rect):
                pass
            elif suffix in {'.jpg', '.jpeg'}:
                image.convert('RGB').save(target, format='JPEG', quality=95)
            elif suffix == '.bmp':
                image.convert('RGB').save(target, format='BMP')
            elif suffix == '.webp':
                image.save(target, format='WEBP', quality=95)
            elif suffix == '.gif':
                image.convert('P', palette=Image.Palette.ADAPTIVE).save(target, format='GIF')
            elif suffix == '.ico':
                image.save(target, format='ICO', sizes=[image.size])
            elif suffix in {'.tif', '.tiff'}:
                image.save(target, format='TIFF')
            else:
                image.save(target, format='PNG')
        except (OSError, ValueError) as exc:
            return {'ok': False, 'error': 'crop_save_failed', 'detail': str(exc)}
        old = self._thumb_cache.pop(str(target.resolve()), None)
        if old:
            self._thumb_cache_bytes -= old[3]
        return {'ok': True, 'path': str(target)}

    def launch(self, kind):
        # Screenshot and recording use the native overlay as an engine.
        # Gallery and crop are rendered inside the single web UI.
        files = {'screenshot': 'main.py', 'gif': 'gifrecorder_standalone.py',
                 'video': 'video_recorder_standalone.py'}
        modules = {'screenshot': 'xaocen_imgtor.workers.screenshot',
                   'gif': 'xaocen_imgtor.workers.gifrecorder',
                   'video': 'xaocen_imgtor.workers.video'}
        if kind in files:
            # A GIF recorder is a one-shot selection session. Always replace an
            # older idle/hidden recorder so it reads the latest configuration.
            old = self.processes.get(kind)
            if kind in {'gif', 'video'} and old is not None and old.poll() is None:
                self._terminate_process(kind, old)
                old = None
            if old is None or old.poll() is not None:
                if getattr(sys, 'frozen', False):
                    command = [sys.executable, '--worker', kind]
                    workdir = APP_DIR
                else:
                    command = [sys.executable, '-m', modules[kind]]
                    workdir = BASE
                popen_options = {'cwd': str(workdir)}
                if not getattr(sys, 'frozen', False):
                    child_env = os.environ.copy()
                    child_env['PYTHONPATH'] = os.pathsep.join(
                        item for item in (str(BASE / 'src'), child_env.get('PYTHONPATH', '')) if item
                    )
                    popen_options['env'] = child_env
                if os.name == 'nt':
                    popen_options['creationflags'] = subprocess.CREATE_NO_WINDOW
                self.processes[kind] = subprocess.Popen(command, **popen_options)
        return True

    @staticmethod
    def _terminate_process(kind, process):
        try:
            process.terminate()
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        except OSError:
            pass

    def restart_screenshot(self):
        process = self.processes.pop('screenshot', None)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        return self.launch('screenshot')

    def close_processes(self):
        """Stop child tools when the webview window is closed."""
        try:
            self.set_shortcut_capture(False)
        except OSError:
            pass
        for kind, process in list(self.processes.items()):
            if process.poll() is not None:
                continue
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
        self.processes.clear()

def _run_main():
    try:
        import webview
    except ImportError:
        from tkinter import messagebox, Tk
        root = Tk(); root.withdraw(); messagebox.showerror('xaocen-imgtor', '请先安装 pywebview：python -m pip install pywebview'); root.destroy(); return
    api = API()
    # Never inherit a stale key-capture mode from an interrupted/forced close.
    api.set_shortcut_capture(False)
    api.launch('screenshot')
    # pywebview accepts the application icon on start(), not create_window().
    # Passing it to create_window raises TypeError on the Windows backend.
    window = webview.create_window(APP_TITLE, str(UI), js_api=api, width=1120, height=760,
                                   min_size=(860, 600), background_color='#141518')
    api._window = window

    try:
        from xaocen_imgtor.tray import TrayController
        tray_controller = TrayController(lambda: _show_main_window(APP_TITLE), api.restart_screenshot,
                                         lambda: _request_main_window_close(api, APP_TITLE, tray))
        tray = tray_controller if tray_controller.start() else None
        if tray is not None:
            print('[INFO] System tray ready: xaocen-imgtor icon is running.')
    except Exception as exc:
        tray = None
        print(f'[WARN] System tray unavailable: {exc}')

    def on_closing():
        if tray is not None and tray.available and not api.exit_requested:
            window.hide()
            return False
        api.exit_requested = True
        return True

    window.events.closing += on_closing
    webview.start(icon=str(ICON_PATH) if ICON_PATH.is_file() else None)
    api.close_processes()
    if tray:
        tray.stop()


def main():
    """Start one launcher instance and never create duplicate tray icons."""
    lock_path = APP_DIR / 'archive' / 'runtime' / '.xaocen-app.lock'
    app_lock = InstanceLock(lock_path)
    if not app_lock.acquire():
        print('[INFO] XAOCEN ImgTor is already running; ignoring duplicate launch.')
        return
    try:
        _run_main()
    finally:
        app_lock.release()
if __name__ == '__main__':
    # Frozen builds also host optional plugins through this same EXE.  The
    # plugin host passes ``-I <plugin.py> --request``; dispatch it directly to
    # the external plugin instead of opening another GUI instance.
    plugin_entry = next((value for value in sys.argv[1:]
                         if value.lower().endswith('.py') and Path(value).is_file()), None)
    if getattr(sys, 'frozen', False) and '--request' in sys.argv and plugin_entry:
        import runpy
        runpy.run_path(plugin_entry, run_name='__main__')
    else:
        # PyInstaller one-file bootstrapping may prepend an internal ``-I``
        # extraction argument before user arguments.  Looking only at argv[1]
        # makes worker processes fall back into the GUI entry point and recursively
        # spawn more workers/windows.
        worker_index = next((index for index, value in enumerate(sys.argv)
                             if value == '--worker'), -1)
        if getattr(sys, 'frozen', False) and worker_index >= 0 and worker_index + 1 < len(sys.argv):
            import runpy
            worker = {'screenshot': 'xaocen_imgtor.workers.screenshot',
                      'gif': 'xaocen_imgtor.workers.gifrecorder',
                      'video': 'xaocen_imgtor.workers.video'}.get(sys.argv[worker_index + 1])
            if worker:
                runpy.run_module(worker, run_name='__main__')
            else:
                raise SystemExit(2)
        else:
            main()
