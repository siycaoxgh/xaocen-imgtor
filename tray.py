#!/usr/bin/env python3
"""Small optional system-tray controller for the background listener."""

import threading
from pathlib import Path

from PIL import Image, ImageDraw


def make_icon():
    icon_path = Path(__file__).resolve().parent / 'xaocen-imgtor.ico'
    if icon_path.is_file():
        try:
            with Image.open(icon_path) as source:
                return source.convert('RGBA').resize((64, 64))
        except (OSError, ValueError):
            pass
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 60, 60), radius=16,
                           fill='#ffbd4a', outline='#2eb3ff', width=2)
    draw.rounded_rectangle((18, 18, 46, 46), radius=6,
                           outline='#123047', width=4)
    draw.rectangle((26, 26, 38, 38), fill='#44d9e6')
    return image


class TrayController:
    def __init__(self, on_open, on_restart, on_exit):
        self.on_open = on_open
        self.on_restart = on_restart
        self.on_exit = on_exit
        self.icon = None
        self.thread = None
        self.available = False
        self._ready = threading.Event()
        self._failure = None

    def start(self):
        try:
            import pystray
        except ImportError as exc:
            print(f'[WARN] System tray unavailable: pystray is not installed ({exc})')
            return False

        menu = pystray.Menu(
            pystray.MenuItem('打开 XAOCEN ImgTor', lambda icon, item: self.on_open()),
            pystray.MenuItem('重启截图监听', lambda icon, item: self.on_restart()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('退出程序', lambda icon, item: self.on_exit()),
        )
        self.icon = pystray.Icon('XAOCEN ImgTor', make_icon(),
                                 'XAOCEN ImgTor · 快速截图已启用', menu)
        self._ready.clear()
        self._failure = None
        try:
            # ``run_detached`` is pystray's integration path for applications
            # that already have another GUI message loop (pywebview here).
            # A custom setup must explicitly make the icon visible; merely
            # reaching the callback only proves that the Win32 loop is ready.
            self.icon.run_detached(setup=self._show_icon)
        except Exception as exc:
            self._failure = exc
            self._ready.set()
        self._ready.wait(timeout=2.0)
        if self._failure:
            print(f'[WARN] System tray unavailable: {self._failure}')
            return False
        self.available = self._ready.is_set()
        return self.available

    def _show_icon(self, icon):
        try:
            icon.visible = True
        except Exception as exc:
            self._failure = exc
            self.available = False
            print(f'[WARN] System tray stopped: {exc}')
        finally:
            self._ready.set()

    def stop(self):
        self.available = False
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None
