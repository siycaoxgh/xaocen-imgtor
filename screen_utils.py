#!/usr/bin/env python3
"""Platform-safe virtual desktop geometry helpers."""

import ctypes
import os

from app_log import log_exception


def set_process_dpi_awareness():
    """Use the same system-DPI coordinate space for Tk and Pillow capture.

    The screenshot listener and the GIF recorder run in separate processes.
    Windows otherwise allows each process to receive different logical
    coordinates when display scaling is enabled, which makes a drawn Tk
    rectangle differ from the Pillow capture rectangle.
    """
    if os.name != 'nt':
        return False
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return True
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            return True
        except (AttributeError, OSError):
            return False


def virtual_screen_bounds(window=None):
    """Return (left, top, width, height) for the complete virtual desktop."""
    if os.name == 'nt':
        user32 = ctypes.windll.user32
        return (
            int(user32.GetSystemMetrics(76)),
            int(user32.GetSystemMetrics(77)),
            int(user32.GetSystemMetrics(78)),
            int(user32.GetSystemMetrics(79)),
        )

    target = window
    try:
        import tkinter as tk
        target = target or tk._default_root
    except Exception as exc:
        log_exception('SCR-VRT-01', 'Could not query the Tk virtual desktop bounds.', exc)
        target = None
    if target is not None:
        try:
            return (
                int(target.winfo_vrootx()),
                int(target.winfo_vrooty()),
                int(target.winfo_vrootwidth()),
                int(target.winfo_vrootheight()),
            )
        except Exception as exc:
            log_exception('SCR-VRT-02', 'Could not read Tk virtual desktop geometry.', exc)
    return (0, 0, 0, 0)


def place_window(window, x, y, width, height):
    """Place a borderless overlay at an absolute virtual-desktop position."""
    x, y, width, height = int(x), int(y), int(width), int(height)
    # On the normal primary-screen path Tk can position the window directly.
    # Setting +0+0 first and then relying on SetWindowPos creates a visible
    # race after toolbar controls rebuild: Tk may retain the temporary origin.
    if os.name == 'nt' and x >= 0 and y >= 0:
        window.geometry(f'{width}x{height}+{x}+{y}')
        window.update_idletasks()
        return
    window.geometry(f'{width}x{height}+0+0')
    window.update_idletasks()
    if os.name == 'nt':
        # Tk treats negative coordinates as offsets from the right/bottom.
        flags = 0x0040 | 0x0010  # SWP_SHOWWINDOW | SWP_NOACTIVATE
        ctypes.windll.user32.SetWindowPos(
            window.winfo_id(), -1, x, y, width, height, flags)
    else:
        window.geometry(f'{width}x{height}{x:+d}{y:+d}')


def monitor_bounds_at(window=None):
    """Return the monitor bounds containing the current pointer."""
    fallback = virtual_screen_bounds(window)
    if os.name != 'nt':
        return fallback
    try:
        from ctypes import wintypes

        class Point(ctypes.Structure):
            _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

        class Rect(ctypes.Structure):
            _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                        ('right', ctypes.c_long), ('bottom', ctypes.c_long)]

        class MonitorInfo(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', Rect),
                        ('rcWork', Rect), ('dwFlags', wintypes.DWORD)]

        if window is not None:
            point = Point(int(window.winfo_pointerx()), int(window.winfo_pointery()))
        else:
            point = Point()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        monitor = ctypes.windll.user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
        info = MonitorInfo()
        info.cbSize = ctypes.sizeof(MonitorInfo)
        if monitor and ctypes.windll.user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            rect = info.rcMonitor
            return (int(rect.left), int(rect.top),
                    int(rect.right - rect.left), int(rect.bottom - rect.top))
    except Exception as exc:
        log_exception('SCR-MON-01', 'Could not read monitor bounds at pointer.', exc)
    return fallback


def configure_transparent_overlay(window, color='#fe01fe'):
    """Configure a transparent overlay with a safe platform fallback."""
    if os.name == 'nt':
        try:
            window.attributes('-transparentcolor', color)
            return True
        except Exception as exc:
            log_exception('SCR-ALPHA-01', 'Windows transparent overlay setup failed.', exc)
    try:
        # Some Tk backends cannot make a color transparent. Keep the fallback
        # visible enough for selection feedback, while documenting that it is
        # not equivalent to Windows color-key transparency.
        window.attributes('-alpha', 0.22)
    except Exception as exc:
        log_exception('SCR-ALPHA-02', 'Fallback overlay transparency setup failed.', exc)
    return False


def round_window(window, width, height, radius=12):
    """Apply a native rounded region where the platform supports it."""
    if os.name != 'nt':
        return
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        create_region = gdi32.CreateRoundRectRgn
        create_region.argtypes = [ctypes.c_int] * 6
        create_region.restype = ctypes.c_void_p
        set_region = user32.SetWindowRgn
        set_region.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool]
        set_region.restype = ctypes.c_int
        hwnd = window.winfo_id()
        # Tk can retain the previous region while it commits a new geometry.
        # Clear it first so shrinking a toolbar cannot leave a rectangular
        # right-hand remnant from its former, wider mode.
        set_region(hwnd, None, True)
        region = create_region(
            0, 0, int(width) + 1, int(height) + 1, int(radius) * 2, int(radius) * 2)
        if not region:
            return
        # On success Windows owns the region. On failure we still own it and
        # must release it, otherwise repeated toolbar rebuilds leak GDI handles.
        if not set_region(hwnd, region, True):
            gdi32.DeleteObject(ctypes.c_void_p(region))
    except (AttributeError, OSError) as exc:
        log_exception('SCR-ROUND-01', 'Rounded native window region setup failed.', exc)


def center_combobox_popup(combo):
    """Center text in the native ttk combobox popup list when available."""
    try:
        popdown = combo.tk.call('ttk::combobox::PopdownWindow', str(combo))
        combo.tk.call(f'{popdown}.f.l', 'configure', '-justify', 'center')
    except Exception as exc:
        log_exception('SCR-COMBO-01', 'Could not center native combobox popup text.', exc)
