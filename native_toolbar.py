#!/usr/bin/env python3
"""Shared native toolbar and status-chip primitives for capture overlays.

The launcher uses HTML/CSS, while the selection overlays must remain native
Tk windows so they can stay above the desktop and accept real keyboard input.
This module centralizes the native window lifecycle, palette, rounded region,
position polling, and status-chip placement so screenshot and recording tools
do not drift apart.
"""

import tkinter as tk

from design_tokens import (
    ACCENT_CYAN, CONTROL_DARK, CONTROL_LIGHT, DANGER, MUTED_DARK, PRIMARY,
    MUTED_LIGHT, SURFACE_DARK, SURFACE_LIGHT, TEXT_DARK,
    TEXT_LIGHT, TOOLBAR_RADIUS, TOOLBAR_TOP_GAP, OVERLAY_CONTROL_WIDTH,
)
from rounded_controls import RoundedDropdown, RoundedEntry
from screen_utils import monitor_bounds_at, place_window, round_window


def native_palette(config):
    """Return one theme palette for every native overlay surface."""
    dark = config.get('theme', 'light') == 'dark'
    return {
        'surface': SURFACE_DARK if dark else SURFACE_LIGHT,
        'control': CONTROL_DARK if dark else CONTROL_LIGHT,
        'text': TEXT_DARK if dark else TEXT_LIGHT,
        'muted': MUTED_DARK if dark else MUTED_LIGHT,
        'accent': ACCENT_CYAN,
        'primary': PRIMARY,
    }


class NativeToolbar:
    """One shared rounded Tk toolbar shell used by both overlay engines."""

    def __init__(self, master, reference, config, *, top_gap=TOOLBAR_TOP_GAP,
                 radius=TOOLBAR_RADIUS):
        self.reference = reference
        self.top_gap = int(top_gap)
        self.radius = int(radius)
        self.palette = native_palette(config)
        self.window = tk.Toplevel(master)
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 1.0)
        self.window.overrideredirect(True)
        self.window.configure(bg=self.palette['surface'],
                              bd=0, highlightthickness=0)
        self.window.title('')
        self.window.bind('<ButtonPress-1>', lambda _event: self.focus_force())
        self._position_after = None
        self._last_monitor = None
        self._destroyed = False
        self._schedule_position_poll()

    @property
    def surface(self):
        return self.palette['surface']

    @property
    def control(self):
        return self.palette['control']

    @property
    def text(self):
        return self.palette['text']

    @property
    def muted(self):
        return self.palette['muted']

    @property
    def accent(self):
        return self.palette['accent']

    def label(self, text='', *, master=None, color='text', size=9,
              bold=False, **kwargs):
        weight = 'bold' if bold else 'normal'
        return tk.Label(
            master or self.window,
            text=text,
            fg=self.palette[color],
            bg=self.surface,
            font=('Microsoft YaHei', size, weight),
            **kwargs,
        )

    def frame(self, master=None):
        return tk.Frame(master or self.window, bg=self.surface,
                        bd=0, highlightthickness=0)

    def dropdown(self, master, variable, values, *, command=None, labels=None,
                 width=OVERLAY_CONTROL_WIDTH, height=30):
        return RoundedDropdown(
            master, variable, values, self.surface, self.control, self.text,
            accent=self.accent, command=command, width=width, height=height,
            labels=labels,
        )

    def entry(self, master, variable, *, width=72, height=28):
        return RoundedEntry(
            master, variable, self.surface, self.control, self.text,
            accent=self.accent, width=width, height=height,
        )

    def place(self):
        """Measure and center on the monitor currently containing the pointer."""
        if self._destroyed or not self.winfo_exists():
            return 0, 0
        # ``geometry(WxH)`` pins a Toplevel to its former explicit width.
        # Release that request before measuring so a mode switch that removes
        # ratio/fixed controls also shrinks the native window and its region.
        self.window.geometry('')
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        monitor = monitor_bounds_at(self.reference)
        monitor_x, monitor_y, monitor_w, _ = monitor
        x = monitor_x + (monitor_w - width) // 2
        place_window(self.window, x, monitor_y + self.top_gap,
                     width, height)
        round_window(self.window, width, height, self.radius)
        # Geometry changes from grid_forget/grid_remove settle one idle turn
        # later on Tk/Win32. Reapply the region then to prevent a stale square
        # edge after switching back to the compact free-size toolbar.
        def finalize_rounding():
            if not self._destroyed and self.winfo_exists():
                round_window(self.window, self.window.winfo_width(),
                             self.window.winfo_height(), self.radius)
        self.window.after_idle(finalize_rounding)
        self._last_monitor = monitor
        return width, height

    def _schedule_position_poll(self):
        if self._destroyed or not self.winfo_exists():
            return
        try:
            self._position_after = self.reference.after(500,
                                                         self._poll_position)
        except tk.TclError:
            self._position_after = None

    def _poll_position(self):
        self._position_after = None
        if self._destroyed or not self.winfo_exists():
            return
        try:
            monitor = monitor_bounds_at(self.reference)
            if monitor != self._last_monitor:
                self.place()
        except tk.TclError:
            return
        self._schedule_position_poll()

    def bind(self, sequence, callback, add=None):
        return self.window.bind(sequence, callback, add)

    def focus_force(self):
        return self.window.focus_force()

    def withdraw(self):
        return self.window.withdraw()

    def deiconify(self):
        return self.window.deiconify()

    def winfo_exists(self):
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def update_idletasks(self):
        return self.window.update_idletasks()

    def winfo_reqwidth(self):
        return self.window.winfo_reqwidth()

    def winfo_reqheight(self):
        return self.window.winfo_reqheight()

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        if self._position_after:
            try:
                self.reference.after_cancel(self._position_after)
            except tk.TclError:
                pass
            self._position_after = None
        try:
            self.window.destroy()
        except tk.TclError:
            pass


class NativeStatusChip:
    """Rounded, movable status chip that never overlaps a capture bbox."""

    def __init__(self, master, config, text='', *, background=DANGER):
        self.window = tk.Toplevel(master)
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.configure(bg=background, bd=0, highlightthickness=0)
        self.label = tk.Label(
            self.window, text=text, fg='white', bg=background,
            font=('Microsoft YaHei', 9, 'bold'), padx=10, pady=4,
        )
        self.label.pack()
        self.background = background
        self.radius = TOOLBAR_RADIUS

    def place_outside(self, bbox, virtual_bounds):
        """Place the chip outside bbox; return False if no safe position exists."""
        self.window.update_idletasks()
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        left, top, right, bottom = bbox
        virtual_left, virtual_top, virtual_width, virtual_height = virtual_bounds
        virtual_right = virtual_left + virtual_width
        virtual_bottom = virtual_top + virtual_height
        candidates = (
            (left, top - height - 6),
            (left, bottom + 6),
            (left - width - 6, top),
            (right + 6, top),
        )
        position = next((point for point in candidates
                         if virtual_left <= point[0]
                         and point[0] + width <= virtual_right
                         and virtual_top <= point[1]
                         and point[1] + height <= virtual_bottom
                         and (point[0] + width <= left or point[0] >= right
                              or point[1] + height <= top or point[1] >= bottom)),
                        None)
        if position is None:
            return False
        place_window(self.window, position[0], position[1], width, height)
        round_window(self.window, width, height, self.radius)
        return True

    def update(self, text):
        try:
            self.label.configure(text=text)
        except tk.TclError:
            pass

    def winfo_exists(self):
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def destroy(self):
        try:
            self.window.destroy()
        except tk.TclError:
            pass
