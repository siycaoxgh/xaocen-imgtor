#!/usr/bin/env python3
"""Small rounded Tk controls used by the native capture toolbars."""

import tkinter as tk
from .design_tokens import (
    ACCENT_CYAN, CONTROL_RADIUS, POPUP_RADIUS, POPUP_ROW_HEIGHT,
)
from .screen_utils import monitor_bounds_at, place_window, round_window


def _rounded_box(canvas, width, height, radius, fill, outline='', x=0, y=0):
    r = min(int(radius), int(width) // 2, int(height) // 2)
    canvas.create_rectangle(x + r, y, x + width - r, y + height, fill=fill, outline='')
    canvas.create_rectangle(x, y + r, x + width, y + height - r, fill=fill, outline='')
    corner_arcs = (
        ((x, y, x + 2 * r, y + 2 * r), 90),
        ((x + width - 2 * r, y, x + width, y + 2 * r), 0),
        ((x, y + height - 2 * r, x + 2 * r, y + height), 180),
        ((x + width - 2 * r, y + height - 2 * r, x + width, y + height), 270),
    )
    for box, start in corner_arcs:
        # PIESLICE also draws two radial edges, which creates the visible
        # inner right-angle artifacts in the toolbar controls.  Paint the
        # corner fill without an outline, then draw only the curved outline.
        canvas.create_arc(*box, start=start, extent=90,
                          fill=fill, outline='')
        if outline:
            canvas.create_arc(*box, start=start, extent=90,
                              style=tk.ARC, outline=outline, width=1)
    if outline:
        canvas.create_line(x + r, y, x + width - r, y, fill=outline)
        canvas.create_line(x + r, y + height - 1, x + width - r, y + height - 1, fill=outline)
        canvas.create_line(x, y + r, x, y + height - r, fill=outline)
        canvas.create_line(x + width - 1, y + r, x + width - 1, y + height - r, fill=outline)


class RoundedDropdown(tk.Frame):
    """A compact rounded dropdown with one Canvas-rendered popup layer.

    A Toplevel containing Frames and Labels creates rectangular child surfaces
    inside a rounded native region.  The popup is therefore rendered as one
    Canvas so its background, hover rows and text share the same clipping
    boundary.
    """

    def __init__(self, master, variable, values, surface, control, text,
                 accent=ACCENT_CYAN, command=None, width=86, height=30,
                 labels=None):
        super().__init__(master, width=width, height=height, bg=surface,
                         bd=0, highlightthickness=0)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.variable = variable
        self.values = tuple(values)
        self.labels = dict(labels or {})
        self.surface = surface
        self.control = control
        self.text_color = text
        self.accent = accent
        self.command = command
        self.width = int(width)
        self.height = int(height)
        self.canvas = tk.Canvas(self, width=self.width, height=self.height,
                                bg=surface, bd=0, highlightthickness=0,
                                cursor='hand2')
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.configure(cursor='hand2')
        self.bind('<Button-1>', self._toggle)
        self.canvas.bind('<Button-1>', self._toggle)
        self.canvas.bind('<Escape>', self._close_popup)
        self.variable.trace_add('write', lambda *_: self._draw())
        self._popup = None
        self._popup_canvas = None
        self._popup_hover = -1
        self._popup_first_index = 0
        self._popup_visible_rows = 0
        self._outside_bind_id = None
        self._draw()

    def _draw(self):
        self.canvas.delete('all')
        _rounded_box(self.canvas, self.width, self.height, CONTROL_RADIUS,
                     self.control, self.accent)
        value = str(self.variable.get())
        display = self.labels.get(value, value)
        self.canvas.create_text(self.width // 2 - 6, self.height // 2,
                                text=display, fill=self.text_color,
                                font=('Segoe UI', 9), anchor='center')
        center_y = self.height // 2
        self.canvas.create_line(
            self.width - 17, center_y - 2, self.width - 12, center_y + 3,
            self.width - 7, center_y - 2, fill=self.accent, width=2,
            capstyle='round', joinstyle='round')

    def _toggle(self, event=None):
        if self._popup and self._popup.winfo_exists():
            self._close_popup()
        else:
            self._open_popup()
        # The Canvas covers the Frame, so let exactly one binding handle the
        # click.  Without ``break`` the event bubbles to the parent Frame and
        # immediately toggles the popup closed again.
        return 'break'

    def set_values(self, values):
        """Refresh popup choices when a custom value is added at runtime."""
        self.values = tuple(dict.fromkeys(values))
        self._close_popup()
        self._draw()

    def _open_popup(self):
        row_h = POPUP_ROW_HEIGHT
        popup_w = self.width
        full_height = row_h * len(self.values) + 8
        mon_x, mon_y, mon_w, mon_h = monitor_bounds_at(self)
        max_height = max(row_h + 8, mon_h - 16)
        popup_h = min(full_height, max_height)
        self._popup_visible_rows = max(1, (popup_h - 8) // row_h)
        self._popup_first_index = 0
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes('-topmost', True)
        popup.attributes('-alpha', 1.0)
        popup.configure(bg=self.surface)
        popup.geometry(f'{popup_w}x{popup_h}+0+0')
        # Create the content before applying the native rounded region.
        # Reversing that order can leave an empty, non-interactive region on
        # topmost Windows overlay windows.
        popup_canvas = tk.Canvas(
            popup, width=popup_w, height=popup_h, bg=self.surface,
            bd=0, highlightthickness=0, cursor='hand2')
        popup_canvas.pack(fill='both', expand=True)
        popup.update_idletasks()
        x = max(mon_x + 8, min(self.winfo_rootx(), mon_x + mon_w - popup_w - 8))
        below = self.winfo_rooty() + self.height + 4
        above = self.winfo_rooty() - popup_h - 4
        y = below if below + popup_h <= mon_y + mon_h - 8 else max(mon_y + 8, above)
        place_window(popup, x, y, popup_w, popup_h)
        round_window(popup, popup_w, popup_h, POPUP_RADIUS)
        popup.deiconify()
        popup.lift()
        self._popup = popup
        self._popup_canvas = popup_canvas
        self._popup_hover = -1
        popup_canvas.bind('<Motion>', self._popup_motion)
        popup_canvas.bind('<Leave>', self._popup_leave)
        popup_canvas.bind('<Button-1>', self._popup_click)
        popup.bind('<Button-1>', self._popup_click)
        popup.bind('<Escape>', self._close_popup)
        popup_canvas.bind('<MouseWheel>', self._popup_wheel)
        popup_canvas.bind('<Button-4>', lambda _event: self._scroll_popup(-1))
        popup_canvas.bind('<Button-5>', lambda _event: self._scroll_popup(1))
        # Do not use focus/grab on a transparent topmost overlay: that can
        # consume the selection click. A global click observer closes only
        # when the click is outside both the source and this popup.
        self._outside_bind_id = self.winfo_toplevel().bind_all(
            '<ButtonPress-1>', self._outside_click, add='+')
        self._draw_popup()

    def _popup_index(self, y):
        index = self._popup_first_index + int((y - 4) // POPUP_ROW_HEIGHT)
        return index if self._popup_first_index <= index < len(self.values) else -1

    def _draw_popup(self):
        if not self._popup_canvas:
            return
        canvas = self._popup_canvas
        width = self.width
        height = canvas.winfo_height() or (POPUP_ROW_HEIGHT * self._popup_visible_rows + 8)
        canvas.delete('all')
        _rounded_box(canvas, width, height, POPUP_RADIUS, self.surface, self.accent)
        last = min(len(self.values), self._popup_first_index + self._popup_visible_rows)
        for index in range(self._popup_first_index, last):
            value = self.values[index]
            y = 4 + (index - self._popup_first_index) * POPUP_ROW_HEIGHT
            if index == self._popup_hover:
                _rounded_box(canvas, width - 8, POPUP_ROW_HEIGHT - 2, 6,
                             self.control, '', x=4, y=y)
            canvas.create_text(
                width // 2, y + POPUP_ROW_HEIGHT // 2,
                text=self.labels.get(value, str(value)), fill=self.text_color,
                font=('Segoe UI', 9), anchor='center', tags=f'option-{index}')

    def _popup_motion(self, event):
        index = self._popup_index(event.y)
        if index != self._popup_hover:
            self._popup_hover = index
            self._draw_popup()

    def _popup_leave(self, event=None):
        if self._popup_hover != -1:
            self._popup_hover = -1
            self._draw_popup()

    def _popup_click(self, event):
        index = self._popup_index(event.y)
        if index >= 0:
            self._select(self.values[index])
        return 'break'

    def _popup_wheel(self, event):
        return self._scroll_popup(-1 if event.delta > 0 else 1)

    def _scroll_popup(self, amount):
        maximum = max(0, len(self.values) - self._popup_visible_rows)
        next_index = max(0, min(maximum, self._popup_first_index + amount))
        if next_index != self._popup_first_index:
            self._popup_first_index = next_index
            self._popup_hover = -1
            self._draw_popup()
        return 'break'

    def _outside_click(self, event):
        popup = self._popup
        if not popup or not popup.winfo_exists():
            return
        widget = event.widget
        try:
            in_popup = widget.winfo_toplevel() == popup
            x, y = event.x_root, event.y_root
            in_source = (self.winfo_rootx() <= x <= self.winfo_rootx() + self.width and
                         self.winfo_rooty() <= y <= self.winfo_rooty() + self.height)
        except tk.TclError:
            return
        if not in_popup and not in_source:
            self._close_popup()

    def _select(self, value):
        self.variable.set(value)
        if self.command:
            self.command(value)
        self._close_popup()

    def _close_popup(self, event=None):
        popup = self._popup
        if popup:
            self._popup = None
            self._popup_canvas = None
            self._popup_hover = -1
            try:
                popup.destroy()
            except tk.TclError:
                pass
        if self._outside_bind_id:
            try:
                # Tk 8.6's unbind_class has no ``funcid`` parameter. Remove
                # only this callback from the Tcl binding script rather than
                # calling unbind_all(), which would break other controls.
                root = self.winfo_toplevel()
                script = root.tk.call('bind', 'all', '<ButtonPress-1>')
                lines = str(script).splitlines()
                retained = [line for line in lines if self._outside_bind_id not in line]
                root.tk.call('bind', 'all', '<ButtonPress-1>', '\n'.join(retained))
            except tk.TclError:
                pass
            self._outside_bind_id = None


class RoundedEntry(tk.Frame):
    """Entry field with a rounded token background and centered text."""

    def __init__(self, master, variable, surface, control, text,
                 accent=ACCENT_CYAN, width=72, height=28):
        super().__init__(master, width=width, height=height, bg=surface,
                         bd=0, highlightthickness=0)
        self.pack_propagate(False)
        self.grid_propagate(False)
        self.width = int(width)
        self.height = int(height)
        self.entry = tk.Entry(self, textvariable=variable, bg=control, fg=text,
                              insertbackground=text, relief='flat', bd=0,
                              highlightthickness=0,
                              justify='center', takefocus=True,
                              font=('Segoe UI', 9))
        self.entry.bind('<Button-1>', lambda event: self.entry.focus_force())
        self.canvas = tk.Canvas(self, width=self.width, height=self.height,
                                bg=surface, bd=0, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        _rounded_box(self.canvas, self.width, self.height, CONTROL_RADIUS, control, accent)
        self.entry.place(x=6, y=4, width=self.width - 12, height=self.height - 8)
        self.entry.lift()
        self.canvas.bind('<Button-1>', lambda event: self.entry.focus_set())
