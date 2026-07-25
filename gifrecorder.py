#!/usr/bin/env python3
"""
drawru-imgter — GIF / APNG / WebP 动图录制
支持比例约束、固定尺寸、自定义 FPS
"""

import os, subprocess, tempfile, tkinter as tk, threading, time
from datetime import datetime
from collections import deque
from PIL import ImageGrab, Image
from config_manager import DEFAULT_CONFIG, load_config, update_config
from shortcuts import to_tk_event, validate_pair
from screen_utils import (configure_transparent_overlay, place_window,
                          virtual_screen_bounds)
from native_toolbar import NativeToolbar, NativeStatusChip
from ratio_presets import is_valid_ratio, normalize_ratio, ratio_options
from presets import GIF_FORMATS, GIF_FPS, GIF_MODES
from design_tokens import ACCENT_BLUE


def clamp(v, lo, hi):
    return max(lo, min(v, hi))


def parse_ratio(ratio_str):
    normalized = normalize_ratio(ratio_str)
    if normalized:
        parts = normalized.split(':')
        return float(parts[0]), float(parts[1])
    return None


def compute_constrained_size(sw, sh, constraint):
    if not constraint:
        return sw, sh
    if constraint[0] == 'ratio':
        wr, hr = constraint[1], constraint[2]
        if sw / sh > wr / hr:
            return int(sh * wr / hr), sh
        else:
            return sw, int(sw * hr / wr)
    elif constraint[0] == 'fixed':
        return constraint[1], constraint[2]
    return sw, sh


def max_record_frames(fps, max_duration=15):
    return max(1, int(fps) * int(max_duration))


def selection_bbox(x, y, width, height):
    """Return an immutable capture rectangle for one recording session."""
    return (int(x), int(y), int(x + width), int(y + height))


def outside_border_segments(left, top, width, height, virtual_width,
                            virtual_height, gap=3):
    """Return only border segments that are outside the capture rectangle."""
    right = left + width
    bottom = top + height
    segments = []
    if top >= gap:
        segments.append((left, top - gap, right, top - gap))
    if bottom + gap <= virtual_height:
        segments.append((left, bottom + gap, right, bottom + gap))
    if left >= gap:
        segments.append((left - gap, top, left - gap, bottom))
    if right + gap <= virtual_width:
        segments.append((right + gap, top, right + gap, bottom))
    return tuple(segments)


class GIFRecorder:
    def __init__(self, config, save_dir, record_kind='motion'):
        self.config = config
        self.save_dir = save_dir
        self.record_kind = record_kind
        self.fps = int(config.get('gif_fps', DEFAULT_CONFIG['gif_fps']))
        self.max_duration = 15
        self.output_format = 'mp4' if record_kind == 'video' else config.get('gif_format', DEFAULT_CONFIG['gif_format'])

        # 选区
        self._drag_sx = self._drag_sy = 0
        self._drag_ex = self._drag_ey = 0
        self._sel_cx = self._sel_cy = 0
        self._sel_cw = self._sel_ch = 0

        # 窗口
        self._mask_win = None
        self._canvas_win = None
        self.canvas = None
        self.toolbar = None
        self.status_label = None
        self._current_cursor = 'crosshair'
        self._phase = 'idle'
        self._move_ox = self._move_oy = 0
        self._mode_var = None
        self._ratio_var = None
        self._cw_var = None
        self._ch_var = None
        self._ratio_frame = None
        self._fixed_frame = None
        self._gif_ratio_values = ratio_options(config.get('gif_ratio'))
        self._ratio_menu = None
        self._fps_var = None
        self._fmt_var = None
        self._virtual_x = self._virtual_y = 0
        self._virtual_w = self._virtual_h = 0

        # 录制状态
        self.recording = False
        self.frames = deque()
        self._frames_lock = threading.Lock()
        self._record_state_lock = threading.Lock()
        self._elapsed = 0.0
        self._record_done = False
        self._record_frame_count = 0
        self._stop_listener = None
        self._recording_border = False
        self._countdown_win = None
        self._record_cancelled = False
        self._record_pending = False
        self._config_poll_id = None
        self._record_bbox = None
        self._record_status_win = None
        self._record_status_label = None
        self._record_status_chip = None
        self._record_status_after = None
        self._recording_event = threading.Event()
        self._stop_requested = threading.Event()
        self._record_done_event = threading.Event()
        self._video_process = None
        self._video_output_path = ''
        self._video_error = ''
        self._video_stderr = ''
        self._escape_bind_id = None

        from i18n import get as _t
        self.t = lambda k, **kw: _t(config, k, **kw)

    def _set_record_state(self, *, elapsed=None, frame_count=None, done=None,
                          video_error=None, video_stderr=None):
        """Exchange recorder progress between worker and Tk threads safely."""
        with self._record_state_lock:
            if elapsed is not None:
                self._elapsed = elapsed
            if frame_count is not None:
                self._record_frame_count = frame_count
            if done is not None:
                self._record_done = done
            if video_error is not None:
                self._video_error = video_error
            if video_stderr is not None:
                self._video_stderr = video_stderr

    def _record_state(self):
        with self._record_state_lock:
            return (self._elapsed, self._record_frame_count,
                    self._record_done, self._video_error)

    def run(self):
        start_key, stop_key, errors = validate_pair(
            self.config.get('record_start_key', DEFAULT_CONFIG['record_start_key']),
            self.config.get('record_stop_key', DEFAULT_CONFIG['record_stop_key']))
        if errors:
            raise ValueError(f'invalid recording shortcuts: {errors}')
        self._mask_win = tk.Toplevel()
        self._mask_win.overrideredirect(True)
        self._mask_win.attributes('-topmost', True)
        self._mask_win.attributes('-alpha', 0.45)
        self._mask_win.configure(bg='black')
        self._mask_win.title('')

        self._canvas_win = tk.Toplevel()
        self._canvas_win.overrideredirect(True)
        self._canvas_win.attributes('-topmost', True)
        configure_transparent_overlay(self._canvas_win)
        self._canvas_win.configure(bg='#fe01fe')
        self._virtual_x, self._virtual_y, self._virtual_w, self._virtual_h = virtual_screen_bounds(self._canvas_win)
        place_window(self._mask_win, self._virtual_x, self._virtual_y, self._virtual_w, self._virtual_h)
        place_window(self._canvas_win, self._virtual_x, self._virtual_y, self._virtual_w, self._virtual_h)
        self._canvas_win.title('GIF Recorder')

        self.canvas = tk.Canvas(self._canvas_win, highlightthickness=0,
                                bg='#fe01fe', cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)

        try:
            self._build_toolbar()
        except Exception as exc:
            from app_log import log_exception
            from runtime_status import publish_status
            log_exception('REC-TB-01', 'Recording toolbar could not be created.', exc)
            publish_status('error', 'Recording toolbar could not be created. [REC-TB-01]')
            for window in (self._canvas_win, self._mask_win, self.toolbar):
                try:
                    if window is not None:
                        window.destroy()
                except tk.TclError:
                    pass
            raise

        # 事件绑定
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.canvas.bind('<Motion>', self._on_motion)
        self._mask_win.bind('<ButtonPress-1>', self._on_press)
        self._mask_win.bind('<B1-Motion>', self._on_drag)
        self._mask_win.bind('<ButtonRelease-1>', self._on_release)
        self._mask_win.bind('<Motion>', self._on_motion)

        for win in (self._canvas_win, self._mask_win, self.toolbar):
            if win is None:
                continue
            win.bind('<Escape>', self._on_cancel)
            win.bind(self._event_key(start_key), self._start_recording)
            win.bind(self._event_key(stop_key), self._stop_recording)

        # Ensure Esc works when focus is inside a toolbar dropdown or entry.
        self._escape_bind_id = self._canvas_win.bind_all(
            '<Escape>', self._on_cancel, add='+')

        self._schedule_config_poll()
        self._canvas_win.focus_force()
        self._canvas_win.wait_window()
        self._stop_global_stop_listener()
        self._destroy_countdown_window()
        self._destroy_record_status_window()
        self._destroy_record_windows()

    # ── 工具栏 ────────────────────────────────────────
    def _build_toolbar(self):
        t = self.t
        toolbar = NativeToolbar(self._canvas_win, self._canvas_win, self.config)
        self.toolbar = toolbar
        toolbar.label('视频录制' if self.record_kind == 'video' else t('gif.title'), color='primary', bold=True).grid(
            row=0, column=0, padx=(10, 6), pady=6)

        # 模式
        toolbar.label(t('overlay.mode')).grid(row=0, column=1, padx=4)
        configured_ratio = self.config.get('gif_ratio', DEFAULT_CONFIG['gif_ratio'])
        self._gif_ratio_values = ratio_options(configured_ratio)
        configured_mode = self.config.get('gif_mode')
        if configured_mode not in GIF_MODES:
            configured_mode = 'free' if configured_ratio == 'free' else 'ratio'
        self._mode_var = tk.StringVar(value=configured_mode)
        mm = toolbar.dropdown(
            toolbar.window, self._mode_var, GIF_MODES,
            command=self._on_mode_change,
            labels={'free': '自由大小', 'ratio': '固定比例', 'fixed': '固定尺寸'},
        )
        mm.grid(row=0, column=2, padx=3, pady=6)

        # 比例选择
        self._ratio_frame = toolbar.frame()
        ratio_value = configured_ratio if configured_ratio in self._gif_ratio_values else self._gif_ratio_values[0]
        self._ratio_var = tk.StringVar(value=ratio_value)
        rm = toolbar.dropdown(
            self._ratio_frame, self._ratio_var, self._gif_ratio_values,
            command=self._on_ratio_change)
        rm.grid(row=0, column=0, padx=3)
        self._ratio_menu = rm
        # 初始显示状态由已保存的录制模式决定。
        self._ratio_frame.grid(row=0, column=3, padx=3, pady=6)
        self._ratio_frame.grid_remove()

        # 固定尺寸
        self._fixed_frame = toolbar.frame()
        self._cw_var = tk.StringVar(value=self.config.get('gif_fixed_width_str', '400px'))
        self._ch_var = tk.StringVar(value=self.config.get('gif_fixed_height_str', '320px'))
        toolbar.label('W', master=self._fixed_frame, size=8).pack(side='left')
        toolbar.entry(self._fixed_frame, self._cw_var).pack(side='left', padx=2)
        toolbar.label('H', master=self._fixed_frame, size=8).pack(side='left')
        toolbar.entry(self._fixed_frame, self._ch_var).pack(side='left', padx=2)
        self._fixed_frame.grid(row=0, column=3, padx=3, pady=6)
        self._fixed_frame.grid_remove()

        # FPS
        toolbar.label('FPS').grid(row=0, column=4, padx=(8, 3))
        fps_value = str(self.config.get('gif_fps', DEFAULT_CONFIG['gif_fps']))
        fps_values = tuple(str(value) for value in GIF_FPS)
        if fps_value not in fps_values:
            fps_value = str(GIF_FPS[0])
        self._fps_var = tk.StringVar(value=fps_value)
        fm = toolbar.dropdown(
            toolbar.window, self._fps_var, fps_values,
            command=self._on_fps_change)
        fm.grid(row=0, column=5, padx=3, pady=6)

        # 输出格式
        toolbar.label(t('gif.format')).grid(row=0, column=6, padx=(8, 3))
        self._fmt_var = tk.StringVar(value=self.output_format)
        fmtm = toolbar.dropdown(
            toolbar.window, self._fmt_var, ('mp4',) if self.record_kind == 'video' else GIF_FORMATS,
            command=self._on_format_change)
        fmtm.grid(row=0, column=7, padx=3, pady=6)

        self.status_label = toolbar.label(
            f'{t("gif.drag_hint")} · {t("gif.start_hint")}', color='muted', size=8)
        self.status_label.grid(row=0, column=8, padx=(10, 12), pady=6)

        self._apply_mode_layout(self._mode_var.get(), place=False)
        toolbar.bind('<Escape>', self._on_cancel)
        toolbar.bind(self._event_key(self.config.get('record_start_key', DEFAULT_CONFIG['record_start_key'])), self._start_recording)
        toolbar.bind(self._event_key(self.config.get('record_stop_key', DEFAULT_CONFIG['record_stop_key'])), self._stop_recording)
        toolbar.place()

    def _on_mode_change(self, val):
        values = {'gif_mode': val}
        if val == 'free':
            values['gif_ratio'] = 'free'
        elif val == 'ratio':
            values['gif_ratio'] = self._ratio_var.get()
        elif val == 'fixed':
            values.update({
                'gif_fixed_width_str': self._cw_var.get(),
                'gif_fixed_height_str': self._ch_var.get(),
            })
        self.config.update(values)
        self._persist_gif_settings(values)

        # A fresh Toplevel is more reliable than resizing an existing borderless
        # Region after fixed/ratio controls are removed.
        if self.toolbar:
            self.toolbar.destroy()
        self._build_toolbar()
        self._refresh_selection_constraint()
        self._redraw()

    def _apply_mode_layout(self, val, *, place=True):
        self._ratio_frame.grid_remove()
        self._fixed_frame.grid_remove()
        if val == 'ratio':
            self._ratio_frame.grid()
        elif val == 'fixed':
            self._fixed_frame.grid()
        if place and self.toolbar:
            self.toolbar.place()

    def _refresh_selection_constraint(self):
        """Recalculate and clamp the current selection after a setting change."""
        if self._sel_cw < 2 or self._sel_ch < 2:
            return
        constraint = self._get_constraint()
        if constraint:
            width, height = compute_constrained_size(
                self._sel_cw, self._sel_ch, constraint)
            self._sel_cw = min(max(1, width), max(1, self._virtual_w))
            self._sel_ch = min(max(1, height), max(1, self._virtual_h))
        self._sel_cx = clamp(
            self._sel_cx, self._virtual_x,
            self._virtual_x + self._virtual_w - self._sel_cw)
        self._sel_cy = clamp(
            self._sel_cy, self._virtual_y,
            self._virtual_y + self._virtual_h - self._sel_ch)

    def _on_ratio_change(self, value):
        self._persist_gif_setting('gif_ratio', value)
        if self._mode_var.get() == 'ratio':
            self._refresh_selection_constraint()
            self._redraw()

    def _on_fps_change(self, value):
        self.fps = int(value)
        self._persist_gif_setting('gif_fps', self.fps)

    def _on_format_change(self, value):
        self.output_format = value
        if self.record_kind != 'video':
            self._persist_gif_setting('gif_format', value)

    @staticmethod
    def _persist_gif_setting(key, value):
        GIFRecorder._persist_gif_settings({key: value})

    @staticmethod
    def _persist_gif_settings(values):
        try:
            update_config(values)
        except TimeoutError as exc:
            from app_log import log_exception
            from runtime_status import publish_status
            log_exception('CFG-LOCK-01', 'GIF settings were not saved because configuration is busy.', exc)
            publish_status('warning', 'Settings are busy; please try again. [CFG-LOCK-01]')
        except (OSError, ValueError, TypeError) as exc:
            print(f'[WARN] Cannot persist GIF settings: {exc}')

    def _schedule_config_poll(self):
        if not self._window_exists(self._canvas_win):
            return
        self._config_poll_id = self._canvas_win.after(700, self._poll_external_config)

    def _poll_external_config(self):
        if not self._window_exists(self._canvas_win):
            return
        if not self.recording:
            try:
                config = load_config()
                theme = config.get('theme', self.config.get('theme', 'light'))
                if theme != self.config.get('theme', 'light'):
                    self.config.update(config)
                    if self.toolbar:
                        self.toolbar.destroy()
                    self._build_toolbar()
                fps = str(config.get('gif_fps', self._fps_var.get()))
                fmt = 'mp4' if self.record_kind == 'video' else config.get('gif_format', self._fmt_var.get())
                ratio = config.get('gif_ratio', DEFAULT_CONFIG['gif_ratio'])
                desired_mode = config.get('gif_mode')
                if desired_mode not in GIF_MODES:
                    desired_mode = 'free' if ratio == 'free' else 'ratio'
                fixed_width = config.get('gif_fixed_width_str', '400px')
                fixed_height = config.get('gif_fixed_height_str', '320px')
                if fps != self._fps_var.get():
                    self._fps_var.set(fps)
                    self.fps = int(fps)
                valid_formats = ('mp4',) if self.record_kind == 'video' else GIF_FORMATS
                if fmt in valid_formats and fmt != self._fmt_var.get():
                    self._fmt_var.set(fmt)
                    self.output_format = fmt
                if desired_mode != self._mode_var.get():
                    self.config.update(config)
                    if self.toolbar:
                        self.toolbar.destroy()
                    self._build_toolbar()
                if ratio != 'free' and is_valid_ratio(ratio):
                    if ratio not in self._gif_ratio_values:
                        self._gif_ratio_values = ratio_options(ratio)
                        if self._ratio_menu:
                            self._ratio_menu.set_values(self._gif_ratio_values)
                    if ratio != self._ratio_var.get():
                        self._ratio_var.set(ratio)
                        if self._mode_var.get() == 'ratio':
                            self._refresh_selection_constraint()
                            self._redraw()
                if fixed_width != self._cw_var.get() or fixed_height != self._ch_var.get():
                    self._cw_var.set(fixed_width)
                    self._ch_var.set(fixed_height)
                    if self._mode_var.get() == 'fixed':
                        self._refresh_selection_constraint()
                        self._redraw()
            except (OSError, tk.TclError):
                pass
        self._schedule_config_poll()

    @staticmethod
    def _window_exists(window):
        try:
            return bool(window and window.winfo_exists())
        except tk.TclError:
            return False

    def _get_constraint(self):
        mode = self._mode_var.get()
        if mode == 'ratio':
            r = parse_ratio(self._ratio_var.get())
            return ('ratio', r[0], r[1]) if r else None
        elif mode == 'fixed':
            from dimensions import parse_dimension
            try:
                w = parse_dimension(self._cw_var.get().strip())
                h = parse_dimension(self._ch_var.get().strip())
                return ('fixed', max(1, w), max(1, h))
            except ValueError:
                pass
        return None

    # ── 鼠标事件 ──────────────────────────────────────
    def _on_cancel(self, event=None):
        self._unbind_escape()
        self.recording = False
        self._recording_event.clear()
        self._stop_requested.set()
        self._record_pending = False
        self._record_cancelled = True
        self._record_bbox = None
        self._stop_global_stop_listener()
        self._recording_border = False
        try:
            self._canvas_win.grab_release()
        except tk.TclError:
            pass
        self._destroy_countdown_window()
        self._destroy_record_status_window()
        self._destroy_record_windows()

    def _unbind_escape(self):
        if self._escape_bind_id is None or self._canvas_win is None:
            return
        try:
            self._canvas_win.unbind_all('<Escape>')
        except tk.TclError:
            pass
        self._escape_bind_id = None

    def _destroy_countdown_window(self):
        window = self._countdown_win
        self._countdown_win = None
        if self._window_exists(window):
            try:
                window.destroy()
            except tk.TclError:
                pass

    def _destroy_record_status_window(self):
        if self._record_status_after and self._canvas_win:
            try:
                self._canvas_win.after_cancel(self._record_status_after)
            except tk.TclError:
                pass
        self._record_status_after = None
        chip = self._record_status_chip
        self._record_status_chip = None
        window = self._record_status_win
        self._record_status_win = None
        self._record_status_label = None
        if chip is not None:
            chip.destroy()
        elif self._window_exists(window):
            try:
                window.destroy()
            except tk.TclError:
                pass

    def _destroy_record_windows(self):
        if self._config_poll_id and self._window_exists(self._canvas_win):
            try:
                self._canvas_win.after_cancel(self._config_poll_id)
            except tk.TclError:
                pass
        self._config_poll_id = None
        for window in (self._canvas_win, self._mask_win, self.toolbar):
            if self._window_exists(window):
                try:
                    window.destroy()
                except tk.TclError:
                    pass

    def _on_motion(self, event):
        x, y = event.x_root, event.y_root
        if self._sel_cw > 0 and self._point_in_selection(x, y):
            cur = 'fleur'
        else:
            cur = 'crosshair'
        if cur != self._current_cursor:
            self._current_cursor = cur
            self.canvas.configure(cursor=cur)

    def _point_in_selection(self, px, py):
        return (self._sel_cx <= px <= self._sel_cx + self._sel_cw and
                self._sel_cy <= py <= self._sel_cy + self._sel_ch)

    def _on_press(self, event):
        if self._record_pending or self.recording:
            return
        x, y = event.x_root, event.y_root
        self._drag_sx = x
        self._drag_sy = y
        if self._sel_cw > 0 and self._point_in_selection(x, y):
            self._phase = 'moving'
            self._move_ox = x - self._sel_cx
            self._move_oy = y - self._sel_cy
        else:
            self._phase = 'drawing'
            self._sel_cw = self._sel_ch = 0

    def _on_drag(self, event):
        if self._record_pending or self.recording:
            return
        x, y = event.x_root, event.y_root
        self._drag_ex = x
        self._drag_ey = y
        if self._phase == 'drawing':
            self._draw_new()
        elif self._phase == 'moving':
            self._move_sel()
            self._redraw()

    def _on_release(self, event):
        if self._record_pending or self.recording:
            return
        if self._phase == 'drawing':
            self._finalize()
            self._redraw()
        self._phase = 'idle'

    def _draw_new(self):
        rx = min(self._drag_sx, self._drag_ex)
        ry = min(self._drag_sy, self._drag_ey)
        rw = abs(self._drag_ex - self._drag_sx)
        rh = abs(self._drag_ey - self._drag_sy)
        if rw < 2 or rh < 2:
            return
        cst = self._get_constraint()
        cw, ch = compute_constrained_size(rw, rh, cst)
        self._sel_cx, self._sel_cy = rx, ry
        self._sel_cw, self._sel_ch = cw, ch
        self._redraw()

    def _finalize(self):
        rx = min(self._drag_sx, self._drag_ex)
        ry = min(self._drag_sy, self._drag_ey)
        rw = abs(self._drag_ex - self._drag_sx)
        rh = abs(self._drag_ey - self._drag_sy)
        if rw < 5 or rh < 5:
            self._sel_cw = self._sel_ch = 0
            return
        cst = self._get_constraint()
        cw, ch = compute_constrained_size(rw, rh, cst)
        self._sel_cx, self._sel_cy = rx, ry
        self._sel_cw, self._sel_ch = cw, ch

    def _move_sel(self):
        x, y = self._drag_ex, self._drag_ey
        sw = self._virtual_w
        sh = self._virtual_h
        self._sel_cx = clamp(x - self._move_ox, self._virtual_x,
                             self._virtual_x + sw - self._sel_cw)
        self._sel_cy = clamp(y - self._move_oy, self._virtual_y,
                             self._virtual_y + sh - self._sel_ch)

    def _redraw(self):
        self.canvas.delete('selection')
        t = self.t
        if self._sel_cw < 2 or self._sel_ch < 2:
            return
        cx, cy = self._sel_cx, self._sel_cy
        cw, ch = self._sel_cw, self._sel_ch
        lx, ly = cx - self._virtual_x, cy - self._virtual_y

        if self._recording_border:
            # Keep the transparent canvas visible while recording, but draw
            # the frame outside the immutable capture bbox whenever possible.
            # This lets the user see the active area without baking the frame
            # into the recorded pixels.
            # The frame is deliberately drawn only outside the immutable
            # capture rectangle.  At a desktop edge there may be no outside
            # pixel available; omitting that side is safer than drawing it
            # inside the area and recording the UI into every frame.
            for x1, y1, x2, y2 in outside_border_segments(
                    lx, ly, cw, ch, self._virtual_w, self._virtual_h):
                self.canvas.create_line(x1, y1, x2, y2,
                                        fill=ACCENT_BLUE, width=3, tags='selection')
        else:
            self.canvas.create_rectangle(lx, ly, lx + cw, ly + ch,
                                         outline='#e74c3c', width=2,
                                         tags='selection')
            self.canvas.create_oval(lx + cw - 16, ly + 4, lx + cw - 4, ly + 12,
                                   fill='#e74c3c', outline='', tags='selection')
            self.canvas.create_line(lx, ly, lx + cw, ly + ch, fill='#e74c3c',
                                    dash=(4, 4), width=1, tags='selection')
            self.canvas.create_line(lx + cw, ly, lx, ly + ch, fill='#e74c3c',
                                    dash=(4, 4), width=1, tags='selection')
            # 尺寸标签只在选区阶段显示，避免录制时叠加到屏幕或输出中。
            label = f'{cw} x {ch}'
            label_y = ly - 16 if ly > 40 else ly + ch + 20
            label_x = lx + cw // 2
            self.canvas.create_rectangle(label_x - 40, label_y - 10,
                                         label_x + 40, label_y + 10,
                                         fill='#e74c3c', outline='', tags='selection')
            self.canvas.create_text(label_x, label_y, text=label,
                                   fill='white', font=('Consolas', 9, 'bold'), tags='selection')
            self.status_label.config(
                text=f'{cw} × {ch} · {t("gif.start_hint")}')

    # ── 录制 ──────────────────────────────────────────
    def _video_record_loop(self, record_bbox):
        """Record the immutable DPI-aware selection with plugin-local FFmpeg."""
        from runtime_status import publish_status
        try:
            from video_plugin_runtime import build_gdigrab_command, find_video_ffmpeg
            ffmpeg = find_video_ffmpeg()
            if not ffmpeg:
                self._set_record_state(video_error='FFmpeg video plugin is unavailable.')
                return
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
            self._video_output_path = os.path.join(self.save_dir, f'video_{timestamp}.mp4')
            command = build_gdigrab_command(
                ffmpeg, record_bbox, self.fps, self.max_duration, self._video_output_path)
            with tempfile.TemporaryFile(mode='w+b') as stderr_file:
                self._video_process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                                        stdout=subprocess.DEVNULL,
                                                        stderr=stderr_file)
                start_time = time.time()
                requested_stop = False
                while self._video_process.poll() is None:
                    self._set_record_state(elapsed=time.time() - start_time)
                    if (not requested_stop and
                            (not self._recording_event.is_set() or self._stop_requested.is_set())):
                        requested_stop = True
                        try:
                            self._video_process.stdin.write(b'q\n')
                            self._video_process.stdin.flush()
                        except (AttributeError, BrokenPipeError, OSError):
                            self._video_process.terminate()
                    time.sleep(0.08)
                try:
                    self._video_process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    self._video_process.kill()
                    self._video_process.communicate()
                stderr_file.seek(0, os.SEEK_END)
                stderr_file.seek(max(0, stderr_file.tell() - 4096))
                stderr_tail = stderr_file.read().decode('utf-8', 'replace').strip()
                self._set_record_state(video_stderr=stderr_tail)
            if (self._video_process.returncode == 0 and
                    os.path.isfile(self._video_output_path) and
                    os.path.getsize(self._video_output_path) > 0):
                self._set_record_state(frame_count=1)
                publish_status('success', 'Video saved', self._video_output_path)
            else:
                detail = stderr_tail[-600:] if stderr_tail else ''
                self._set_record_state(video_error=(
                    'FFmpeg capture failed or produced an empty MP4 file.' +
                    (f' {detail}' if detail else '')))
        except Exception as exc:
            self._set_record_state(video_error=str(exc))
        finally:
            self._video_process = None
            self._set_record_state(done=True)
            self._record_done_event.set()

    def _start_recording(self, event=None):
        if self.recording:
            return
        if self._sel_cw < 10 or self._sel_ch < 10:
            return
        # Re-apply the latest mode/ratio/size constraint immediately before
        # taking the immutable recording snapshot.  This prevents a stale
        # default-sized bbox from being used after a live settings change.
        self._refresh_selection_constraint()
        if self._sel_cw < 10 or self._sel_ch < 10:
            return

        self.fps = int(self._fps_var.get())
        self.output_format = self._fmt_var.get()
        self.recording = True
        self._recording_event.set()
        self._stop_requested.clear()
        self._record_done_event.clear()
        self._record_pending = True
        with self._frames_lock:
            self.frames.clear()
        self._set_record_state(elapsed=0.0, done=False, frame_count=0,
                               video_error='', video_stderr='')
        self._video_output_path = ''
        self._record_cancelled = False
        self._recording_border = True
        record_bbox = selection_bbox(
            self._sel_cx, self._sel_cy, self._sel_cw, self._sel_ch)
        self._record_bbox = record_bbox

        self.toolbar.withdraw()
        self._mask_win.withdraw()
        self._canvas_win.deiconify()
        self._canvas_win.lift()
        self._redraw()

        cd_win = tk.Toplevel()
        cd_win.attributes('-topmost', True)
        cd_win.attributes('-alpha', 0.85)
        cd_win.overrideredirect(True)
        cd_win.configure(bg='#e74c3c')
        self._countdown_win = cd_win
        cd_lbl = tk.Label(cd_win, text='3', fg='white', bg='#e74c3c',
                         width=4, anchor='center', font=('Microsoft YaHei', 10, 'bold'))
        cd_lbl.pack(padx=8, pady=2)
        cd_win.update_idletasks()
        place_window(cd_win, record_bbox[0] + 4, record_bbox[1] + 4,
                     cd_win.winfo_reqwidth(), cd_win.winfo_reqheight())

        interval = 1.0 / self.fps
        max_frames = max_record_frames(self.fps, self.max_duration)

        self._start_global_stop_listener(self.config.get('record_stop_key', DEFAULT_CONFIG['record_stop_key']))

        def poll_finish():
            if self._record_pending and self._stop_requested.is_set():
                self._record_cancelled = True
            if self._record_cancelled:
                self._recording_event.clear()
                self._record_pending = False
                self._stop_global_stop_listener()
                self._destroy_countdown_window()
                self._destroy_record_status_window()
                self._destroy_record_windows()
                return
            if self._record_done_event.is_set():
                self._finish_recording()
                return
            try:
                if self._canvas_win.winfo_exists():
                    self._canvas_win.after(50, poll_finish)
            except tk.TclError:
                pass

        self._canvas_win.after(50, poll_finish)

        def record_loop():
            frame_count = 0
            start_time = time.time()
            try:
                while self._recording_event.is_set() and frame_count < max_frames:
                    tick = time.time()
                    try:
                        grab_args = {'bbox': record_bbox}
                        if os.name == 'nt':
                            grab_args['all_screens'] = True
                        img = ImageGrab.grab(**grab_args)
                        with self._frames_lock:
                            self.frames.append(img.copy())
                    except Exception as exc:
                        from app_log import log_exception
                        log_exception('REC-GRAB-01', 'A recording frame could not be captured.', exc)
                        # Avoid turning a transient failed frame into a hard stop.
                    frame_count += 1
                    self._set_record_state(elapsed=time.time() - start_time)
                    st = max(0, interval - (time.time() - tick))
                    if st > 0:
                        time.sleep(st)
            finally:
                # 录制线程只更新状态；Tk 清理由主线程的 poll_finish 完成。
                self._set_record_state(frame_count=frame_count, done=True)
                self._record_done_event.set()

        def begin_capture():
            if not self._recording_event.is_set() or self._record_cancelled or self._stop_requested.is_set():
                return
            self._record_pending = False
            # Keep the transparent canvas alive so the active frame remains
            # visible.  Its recording border is drawn outside the capture bbox;
            # only the countdown and dark mask are removed before grabbing.
            self._destroy_countdown_window()
            try:
                self._mask_win.withdraw()
                self._mask_win.update_idletasks()
                self._canvas_win.deiconify()
                self._canvas_win.update_idletasks()
            except tk.TclError:
                return
            self._show_recording_status(record_bbox)

            # Give Tk one short turn to commit the hidden countdown/mask before
            # the first frame is grabbed.
            def start_thread():
                if self._recording_event.is_set() and not self._record_cancelled:
                    target = (lambda: self._video_record_loop(record_bbox)) if self.record_kind == 'video' else record_loop
                    threading.Thread(target=target, daemon=True).start()
            self._canvas_win.after(120, start_thread)

        countdown = {'value': 3}

        def update_countdown():
            if not self._recording_event.is_set() or self._record_cancelled or self._stop_requested.is_set():
                return
            try:
                if countdown['value'] <= 0:
                    begin_capture()
                    return
                cd_lbl.config(text=str(countdown['value']))
                cd_win.update_idletasks()
                countdown['value'] -= 1
                cd_win.after(1000, update_countdown)
            except (tk.TclError, RuntimeError):
                pass

        update_countdown()

    def _show_recording_status(self, record_bbox):
        """Show a recording chip outside the immutable capture rectangle."""
        if not self._window_exists(self._canvas_win):
            return
        chip = NativeStatusChip(self._canvas_win, self.config,
                                 text='● 录制中 00:00')
        virtual_bounds = (
            self._virtual_x, self._virtual_y,
            self._virtual_w, self._virtual_h,
        )
        if not chip.place_outside(record_bbox, virtual_bounds):
            # A full-screen selection has no safe place for a desktop status
            # window. Hiding it keeps the recording free of UI pixels.
            chip.destroy()
            return
        self._record_status_chip = chip
        self._record_status_win = chip.window
        self._record_status_label = chip.label

        def update_status():
            if not chip.winfo_exists() or not self._recording_event.is_set():
                return
            elapsed, _frames, _done, _error = self._record_state()
            elapsed = min(self.max_duration, max(0.0, elapsed))
            chip.update(f'● 录制中 {int(elapsed // 60):02d}:{int(elapsed % 60):02d}')
            try:
                self._record_status_after = self._canvas_win.after(200, update_status)
            except tk.TclError:
                self._record_status_after = None

        update_status()

    def _stop_recording(self, event=None):
        # This callback may run on pynput's worker thread.  Only signal the
        # Tk thread; it owns window destruction and recorder state cleanup.
        if self._recording_event.is_set():
            self._stop_requested.set()
            self._recording_event.clear()

    def _finish_recording(self):
        """Finish exactly once on the Tk main thread."""
        if self._record_cancelled:
            return
        self.recording = False
        self._recording_event.clear()
        self._record_pending = False
        self._recording_border = False
        self._stop_global_stop_listener()
        self._destroy_countdown_window()
        self._destroy_record_status_window()
        try:
            _elapsed, frame_count, _done, video_error = self._record_state()
            if self.record_kind == 'video' and video_error:
                raise RuntimeError(video_error)
            if frame_count > 0 and self.record_kind != 'video':
                self._save_output()
        except Exception as exc:
            print(f'[ERROR] Motion save failed: {exc}')
            from runtime_status import publish_status
            publish_status('error', f'Motion save failed: {exc}')
        finally:
            self._record_bbox = None
            self._record_done_event.clear()
            self._stop_requested.clear()
            self._destroy_record_windows()

    def _start_global_stop_listener(self, stop_key):
        """Keep the stop shortcut active after the selection windows are hidden."""
        try:
            from pynput import keyboard as pynput_keyboard
            from shortcuts import to_pynput
            hotkey = to_pynput(stop_key, require_modifier=False)
            self._stop_listener = pynput_keyboard.GlobalHotKeys({
                hotkey: self._stop_recording,
            })
            self._stop_listener.start()
        except Exception as exc:
            self._stop_listener = None
            print(f'[WARN] Global recording stop shortcut unavailable: {exc}')

    def _stop_global_stop_listener(self):
        listener = self._stop_listener
        self._stop_listener = None
        if listener is not None:
            try:
                listener.stop()
            except Exception:
                pass

    @staticmethod
    def _event_key(key):
        return to_tk_event(key)

    def _save_output(self):
        with self._frames_lock:
            frames = list(self.frames)
        if not frames:
            return

        fmt = self.output_format
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        ext_map = {'gif': 'gif', 'apng': 'png', 'webp': 'webp'}
        ext = ext_map.get(fmt, 'gif')
        filename = f'motion_{timestamp}.{ext}'
        filepath = os.path.join(self.save_dir, filename)

        interval = int(1.0 / self.fps * 1000)
        max_w, max_h = 800, 600
        output_frames = []
        for frame in frames:
            w, h = frame.size
            scale = min(max_w / w, max_h / h, 1.0)
            if scale < 1.0:
                frame = frame.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            output_frames.append(frame)

        if fmt == 'gif':
            qf = [f.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
                  for f in output_frames]
            qf[0].save(filepath, save_all=True, append_images=qf[1:],
                      duration=interval, loop=0, optimize=True)
        elif fmt == 'apng':
            rf = [f.convert('RGBA') for f in output_frames]
            rf[0].save(filepath, save_all=True, append_images=rf[1:],
                      duration=interval, loop=0, format='PNG', optimize=True)
        elif fmt == 'webp':
            wf = [f.convert('RGB') for f in output_frames]
            wf[0].save(filepath, save_all=True, append_images=wf[1:],
                      duration=interval, loop=0, format='WEBP', optimize=True,
                      quality=80)

        print(f'[OK] Motion saved: {filepath}')
        print(f'      {len(output_frames)} frames, {self.fps} fps, '
              f'{os.path.getsize(filepath) // 1024} KB')
        from runtime_status import publish_status
        publish_status('success', f'Motion saved: {filepath}', filepath)
