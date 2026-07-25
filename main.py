#!/usr/bin/env python3
"""
drawru-imgter — lightweight cross-platform screenshot tool
i18n-aware (zh/en), ratio/fixed constraints, auto-save, clipboard
"""

import sys, os, queue, platform

from screen_utils import set_process_dpi_awareness
set_process_dpi_awareness()

import tkinter as tk
from tkinter import messagebox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overlay import ScreenshotOverlay
from config_manager import CONFIG_PATH, DEFAULT_CONFIG, load_config
from instance_lock import InstanceLock
from shortcuts import to_pynput, validate


def resolve_save_dir(config):
    d = config.get('save_directory', '')
    if not d:
        d = os.path.join(os.environ.get('USERPROFILE', ''), 'Pictures', 'drawru-imgter') if platform.system() == 'Windows' else os.path.join(os.path.expanduser('~'), 'Pictures', 'drawru-imgter')
    os.makedirs(d, exist_ok=True)
    return d


def setup_hotkey(hotkey_str, callback):
    from pynput import keyboard as pynput_keyboard
    canonical, error = validate(hotkey_str, require_modifier=True)
    if error:
        raise ValueError(f'invalid screenshot shortcut: {error}')
    pynput_str = to_pynput(canonical)
    hotkey = pynput_keyboard.HotKey(pynput_keyboard.HotKey.parse(pynput_str), callback)

    def for_canonical(f):
        return lambda k: f(listener.canonical(k))

    listener = pynput_keyboard.Listener(
        on_press=for_canonical(hotkey.press),
        on_release=for_canonical(hotkey.release))
    return listener, hotkey


def main():
    lock = InstanceLock()
    if not lock.acquire():
        print('[drawru-imgter] Existing screenshot listener found; taking over it.')
        if not lock.takeover_existing() or not lock.acquire():
            print('[drawru-imgter] Could not safely take over the existing listener.')
            return
    try:
        _run()
    finally:
        lock.release()


def _run():
    config = load_config()
    from i18n import get as _t
    t = lambda k, **kw: _t(config, k, **kw)

    trigger_queue = queue.Queue()
    root = tk.Tk()
    root.withdraw()
    root.title('XAOCEN ImgTor')

    def on_hotkey():
        if state.get('shortcut_capture', False):
            return
        trigger_queue.put(True)

    try:
        config_mtime = CONFIG_PATH.stat().st_mtime_ns
    except OSError:
        config_mtime = None
    state = {'listener': None, 'hotkey_str': '',
             'shortcut_capture': bool(config.get('shortcut_capture', False)),
             'config_mtime': config_mtime}

    def start_listener(hotkey_str):
        if state['listener']:
            state['listener'].stop()
        try:
            lst, _ = setup_hotkey(hotkey_str, on_hotkey)
            lst.start()
            state['listener'] = lst
            state['hotkey_str'] = hotkey_str
        except Exception as e:
            messagebox.showerror(t('main.hotkey_error'), str(e))

    start_listener(config['hotkey'])

    hotkey_d = config['hotkey'].replace('ctrl', 'Ctrl').replace('shift', 'Shift')
    mode_l = t('main.mode_ratio') if config.get('default_mode') == 'ratio' else t('main.mode_fixed')
    save_d = resolve_save_dir(config)
    print(f'[XAOCEN ImgTor] {t("main.status")}: {hotkey_d} | {mode_l} | {t("main.save_to")}: {save_d}')

    def check_queue():
        nonlocal config
        try:
            trigger_queue.get_nowait()
            config = load_config()
            state['shortcut_capture'] = bool(config.get('shortcut_capture', False))
            try:
                state['config_mtime'] = CONFIG_PATH.stat().st_mtime_ns
            except OSError:
                pass
            if config['hotkey'] != state['hotkey_str']:
                start_listener(config['hotkey'])
            save_dir = resolve_save_dir(config)
            overlay = ScreenshotOverlay(config, save_dir)
            overlay.run()
        except queue.Empty:
            pass
        except tk.TclError:
            pass
        except Exception as exc:
            # Keep the listener alive after a single capture/save failure.
            # Previously an uncaught Pillow or clipboard exception stopped
            # this polling callback, making the second shortcut appear dead.
            print(f'[WARN] Screenshot action failed: {exc}')
        finally:
            try:
                root.after(80, check_queue)
            except tk.TclError:
                pass

    def check_config_changes():
        """Refresh the global listener even when the old shortcut is no longer pressed."""
        nonlocal config
        try:
            try:
                latest_mtime = CONFIG_PATH.stat().st_mtime_ns
            except OSError:
                latest_mtime = None
            if latest_mtime == state.get('config_mtime'):
                root.after(300, check_config_changes)
                return
            latest = load_config()
            state['config_mtime'] = latest_mtime
            state['shortcut_capture'] = bool(latest.get('shortcut_capture', False))
            if latest.get('hotkey') != state['hotkey_str']:
                start_listener(latest.get('hotkey', DEFAULT_CONFIG['hotkey']))
                config = latest
        except (OSError, ValueError, tk.TclError):
            pass
        root.after(300, check_config_changes)

    root.after(80, check_queue)
    root.after(300, check_config_changes)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        if state['listener']:
            state['listener'].stop()


if __name__ == '__main__':
    main()
