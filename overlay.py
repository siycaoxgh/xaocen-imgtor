#!/usr/bin/env python3
"""
ScreenshotOverlay — 半透明遮罩层（双层窗口） + 截图框选与保存
遮罩策略：底层 → 半透明暗色全屏窗口
         顶层 → 全透明 Canvas 画选择框

交互：拖拽画框 → 框内按住拖拽平移微调 → Enter 确认截图
"""

import os
import io
import ctypes
import tkinter as tk
from datetime import datetime
from screen_utils import (configure_transparent_overlay, place_window,
                          virtual_screen_bounds)
from native_toolbar import NativeToolbar
from config_manager import DEFAULT_CONFIG
from ratio_presets import is_valid_ratio, normalize_ratio, ratio_options

# ── 工具函数 ──────────────────────────────────────────
def clamp(v, lo, hi):
    return max(lo, min(v, hi))


def parse_ratio(ratio_str):
    normalized = normalize_ratio(ratio_str)
    if normalized:
        parts = normalized.split(':')
        return float(parts[0]), float(parts[1])
    return None


def compute_constrained_size(sw, sh, constraint):
    if constraint[0] == 'ratio':
        w_ratio, h_ratio = constraint[1], constraint[2]
        if sw / sh > w_ratio / h_ratio:
            return int(sh * w_ratio / h_ratio), sh
        else:
            return sw, int(sw * h_ratio / w_ratio)
    elif constraint[0] == 'fixed':
        return constraint[1], constraint[2]
    return sw, sh


def image_for_save_format(image, save_format):
    """Return an image mode accepted by the selected Pillow output format."""
    if save_format in {'JPEG', 'BMP'} and image.mode not in {'RGB', 'L'}:
        return image.convert('RGB')
    return image


class ScreenshotOverlay:
    def __init__(self, config, save_dir):
        self.config = config
        self.save_dir = save_dir

        # 拖拽状态
        self._drag_start_x = self._drag_start_y = 0
        self._drag_end_x = self._drag_end_y = 0

        # 当前选区的锚点（左上角屏幕坐标）和尺寸
        self._sel_cx = self._sel_cy = 0
        self._sel_cw = self._sel_ch = 0

        # 当前鼠标光标
        self._current_cursor = 'crosshair'

        # 交互阶段
        # 'drawing'  = 正在拖拽画框
        # 'moving'   = 框内按住拖拽平移
        # 'idle'     = 有选区，未在操作中
        self._phase = 'idle'

        # 平移时的锚点偏移
        self._move_offset_x = 0
        self._move_offset_y = 0

        # 窗口
        self._mask_win = None
        self._canvas_win = None
        self.canvas = None
        self.toolbar = None
        self.status_label = None
        self.mode_var = None
        self.ratio_var = None
        self.ratio_menu = None
        self.custom_w_var = None
        self.custom_h_var = None
        self.ratio_frame = None
        self.fixed_frame = None
        self._virtual_x = self._virtual_y = 0
        self._virtual_w = self._virtual_h = 0
        self._config_poll_id = None
        self._last_config = dict(config)
        self._escape_bind_id = None

    def run(self):
        # 底层：半透明暗色遮罩
        self._mask_win = tk.Toplevel()
        self._mask_win.overrideredirect(True)
        self._mask_win.attributes('-topmost', True)
        self._mask_win.attributes('-alpha', 0.45)
        self._mask_win.configure(bg='black')
        self._mask_win.title('')

        # 顶层：透明 Canvas
        self._canvas_win = tk.Toplevel()
        self._canvas_win.overrideredirect(True)
        self._canvas_win.attributes('-topmost', True)
        configure_transparent_overlay(self._canvas_win)
        self._canvas_win.configure(bg='#fe01fe')
        self._virtual_x, self._virtual_y, self._virtual_w, self._virtual_h = virtual_screen_bounds(self._canvas_win)
        place_window(self._mask_win, self._virtual_x, self._virtual_y, self._virtual_w, self._virtual_h)
        place_window(self._canvas_win, self._virtual_x, self._virtual_y, self._virtual_w, self._virtual_h)
        self._canvas_win.title('XAOCEN ImgTor')

        self.canvas = tk.Canvas(self._canvas_win, highlightthickness=0,
                                bg='#fe01fe', cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)

        try:
            self._build_toolbar()
        except Exception as exc:
            from app_log import log_exception
            from runtime_status import publish_status
            log_exception('OVR-TB-01', 'Screenshot toolbar could not be created.', exc)
            publish_status('error', 'Screenshot toolbar could not be created. [OVR-TB-01]')
            for window in (self._canvas_win, self._mask_win, self.toolbar):
                try:
                    if window is not None:
                        window.destroy()
                except tk.TclError:
                    pass
            raise

        # ── 事件绑定 ──
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
            win.bind('<Return>', self._on_confirm)

        # Toolbar entries/dropdowns are separate Tk widgets/windows.  A global
        # binding keeps Esc reliable even when focus is inside one of them.
        self._escape_bind_id = self._canvas_win.bind_all(
            '<Escape>', self._on_cancel, add='+')

        self._canvas_win.focus_force()
        self._schedule_config_poll()
        self._canvas_win.wait_window()
        self._unbind_escape()
        self._stop_config_poll()
        for window in (self._mask_win, self.toolbar):
            try:
                window.destroy()
            except tk.TclError:
                pass

    def _on_cancel(self, event=None):
        self._unbind_escape()
        self._stop_config_poll()
        try:
            self._canvas_win.grab_release()
        except tk.TclError:
            pass
        if self._canvas_win:
            self._canvas_win.destroy()
        if self._mask_win:
            self._mask_win.destroy()
        if self.toolbar:
            try:
                self.toolbar.destroy()
            except tk.TclError:
                pass

    def _unbind_escape(self):
        if self._escape_bind_id is None or self._canvas_win is None:
            return
        try:
            self._canvas_win.unbind_all('<Escape>')
        except tk.TclError:
            pass
        self._escape_bind_id = None

    # ── 工具栏 ────────────────────────────────────────
    def _build_toolbar(self):
        from i18n import get as _t
        self.t = lambda k, **kw: _t(self.config, k, **kw)
        t = self.t
        toolbar = NativeToolbar(self._canvas_win, self._canvas_win, self.config)
        self.toolbar = toolbar

        toolbar.label(t('overlay.mode')).grid(
            row=0, column=0, padx=(10, 3), pady=6)

        configured_mode = self.config.get('default_mode', DEFAULT_CONFIG['default_mode'])
        if configured_mode not in {'free', 'ratio', 'fixed'}:
            configured_mode = DEFAULT_CONFIG['default_mode']
        self.mode_var = tk.StringVar(value=configured_mode)
        mode_menu = toolbar.dropdown(
            toolbar.window, self.mode_var, ('free', 'ratio', 'fixed'),
            command=self._on_mode_change,
            labels={'free': '自由大小', 'ratio': '固定比例', 'fixed': '固定尺寸'},
        )
        mode_menu.grid(row=0, column=1, padx=3, pady=6)

        self.ratio_var = tk.StringVar(value=self.config.get('default_ratio', DEFAULT_CONFIG['default_ratio']))
        self.ratio_frame = toolbar.frame()
        toolbar.label(t('overlay.ratio'), master=self.ratio_frame).grid(
            row=0, column=0, padx=(10, 3))
        ratio_values = ratio_options(self.ratio_var.get())
        ratio_menu = toolbar.dropdown(
            self.ratio_frame, self.ratio_var, ratio_values,
            command=self._on_ratio_change)
        ratio_menu.grid(row=0, column=1, padx=3)
        self.ratio_menu = ratio_menu
        self.ratio_frame.grid(row=0, column=2, padx=3, pady=6)

        self.fixed_frame = toolbar.frame()
        self.custom_w_var = tk.StringVar(value=self.config.get('fixed_width_str', DEFAULT_CONFIG['fixed_width_str']))
        self.custom_h_var = tk.StringVar(value=self.config.get('fixed_height_str', DEFAULT_CONFIG['fixed_height_str']))
        toolbar.label(t('overlay.width'), master=self.fixed_frame).grid(
            row=0, column=0, padx=(10, 2))
        toolbar.entry(self.fixed_frame, self.custom_w_var).grid(
            row=0, column=1, padx=2)
        toolbar.label(t('overlay.height'), master=self.fixed_frame).grid(
            row=0, column=2, padx=2)
        toolbar.entry(self.fixed_frame, self.custom_h_var).grid(
            row=0, column=3, padx=2)
        toolbar.label(t('overlay.unit_hint'), master=self.fixed_frame,
                      color='muted', size=8).grid(row=0, column=4, padx=2)

        self.status_label = toolbar.label(
            f'{t("overlay.drag_hint")} · Enter / Esc', color='muted', size=8)
        self.status_label.grid(row=0, column=3, padx=(10, 12), pady=6)

        self._apply_mode_layout(self.mode_var.get(), place=False)
        # Rebind every time the toolbar is rebuilt (for example after a theme
        # change).  The old implementation lost Enter/Esc here.
        toolbar.bind('<Escape>', self._on_cancel)
        toolbar.bind('<Return>', self._on_confirm)
        toolbar.place()

    def _schedule_config_poll(self):
        if self._canvas_win and self._canvas_win.winfo_exists():
            self._config_poll_id = self._canvas_win.after(250, self._poll_config)

    def _stop_config_poll(self):
        if self._config_poll_id and self._canvas_win:
            try:
                self._canvas_win.after_cancel(self._config_poll_id)
            except tk.TclError:
                pass
            self._config_poll_id = None

    def _poll_config(self):
        """Apply web settings to an already-open overlay without reopening it."""
        try:
            from config_manager import load_config
            latest = load_config()
            fields = ('default_mode', 'default_ratio', 'fixed_width_str',
                      'fixed_height_str', 'file_format', 'auto_save',
                      'auto_clipboard', 'file_prefix', 'theme', 'shortcut_capture')
            if any(latest.get(key) != self._last_config.get(key) for key in fields):
                if latest.get('shortcut_capture', False):
                    self._on_cancel()
                    return
                theme_changed = latest.get('theme') != self.config.get('theme')
                self.config.update(latest)
                self._last_config = dict(latest)
                if theme_changed and self.toolbar:
                    self.toolbar.destroy()
                    self._build_toolbar()
                self.mode_var.set(self.config.get('default_mode', DEFAULT_CONFIG['default_mode']))
                ratio_value = self.config.get('default_ratio', DEFAULT_CONFIG['default_ratio'])
                if is_valid_ratio(ratio_value) and self.ratio_menu:
                    self.ratio_menu.set_values(ratio_options(ratio_value))
                self.ratio_var.set(ratio_value)
                self.custom_w_var.set(self.config.get('fixed_width_str', DEFAULT_CONFIG['fixed_width_str']))
                self.custom_h_var.set(self.config.get('fixed_height_str', DEFAULT_CONFIG['fixed_height_str']))
                self._on_mode_change(self.mode_var.get())
                self._refresh_selection_constraint()
                self._redraw()
        except (OSError, ValueError, tk.TclError):
            pass
        self._schedule_config_poll()

    def _refresh_selection_constraint(self):
        if self._sel_cw < 2 or self._sel_ch < 2:
            return
        constraint = self._get_constraint()
        if constraint:
            self._sel_cw, self._sel_ch = compute_constrained_size(
                self._sel_cw, self._sel_ch, constraint)
        self._sel_cx = clamp(self._sel_cx, self._virtual_x,
                             self._virtual_x + self._virtual_w - self._sel_cw)
        self._sel_cy = clamp(self._sel_cy, self._virtual_y,
                             self._virtual_y + self._virtual_h - self._sel_ch)

    # ── 模式 / 比例切换 ────────────────────────────────
    def _apply_mode_layout(self, val, *, place=True):
        if val == 'ratio':
            self.ratio_frame.grid(row=0, column=2, padx=3, pady=6)
            self.fixed_frame.grid_forget()
        elif val == 'fixed':
            self.ratio_frame.grid_forget()
            self.fixed_frame.grid(row=0, column=2, padx=3, pady=6)
        else:
            self.ratio_frame.grid_forget()
            self.fixed_frame.grid_forget()
        if place and self.toolbar:
            self.toolbar.place()

    def _on_mode_change(self, val):
        """Recreate the borderless toolbar instead of shrinking its Win32 region."""
        self.config.update({
            'default_mode': val,
            'default_ratio': self.ratio_var.get(),
            'fixed_width_str': self.custom_w_var.get(),
            'fixed_height_str': self.custom_h_var.get(),
        })
        if self.toolbar:
            self.toolbar.destroy()
        self._build_toolbar()
        self._refresh_selection_constraint()
        self._redraw()

    def _on_ratio_change(self, val):
        self._redraw()

    def _get_constraint(self):
        mode = self.mode_var.get()
        if mode == 'ratio':
            r = parse_ratio(self.ratio_var.get())
            return ('ratio', r[0], r[1]) if r else None
        elif mode == 'fixed':
            from dimensions import parse_dimension
            try:
                w = parse_dimension(self.custom_w_var.get().strip())
                h = parse_dimension(self.custom_h_var.get().strip())
                return ('fixed', max(1, w), max(1, h))
            except ValueError:
                return ('fixed', 400, 320)
        return None

    # ── 鼠标事件 ──────────────────────────────────────
    def _on_motion(self, event):
        """鼠标移动：根据是否在选区内切换光标。"""
        x, y = event.x_root, event.y_root
        if self._sel_cw > 0 and self._point_in_selection(x, y):
            new_cursor = 'fleur'
        else:
            new_cursor = 'crosshair'
        if new_cursor != self._current_cursor:
            self._current_cursor = new_cursor
            self.canvas.configure(cursor=new_cursor)

    def _point_in_selection(self, px, py):
        return (self._sel_cx <= px <= self._sel_cx + self._sel_cw and
                self._sel_cy <= py <= self._sel_cy + self._sel_ch)

    def _on_press(self, event):
        x, y = event.x_root, event.y_root
        self._drag_start_x = x
        self._drag_start_y = y

        # 判断：点中了已有选区 → 平移模式；否则 → 画框模式
        if self._sel_cw > 0 and self._point_in_selection(x, y):
            self._phase = 'moving'
            self._move_offset_x = x - self._sel_cx
            self._move_offset_y = y - self._sel_cy
        else:
            self._phase = 'drawing'
            self._sel_cx = self._sel_cy = self._sel_cw = self._sel_ch = 0

    def _on_drag(self, event):
        x, y = event.x_root, event.y_root
        self._drag_end_x = x
        self._drag_end_y = y

        if self._phase == 'drawing':
            self._draw_new_selection()
        elif self._phase == 'moving':
            self._move_selection()
            self._redraw()

    def _on_release(self, event):
        if self._phase == 'drawing':
            self._finalize_selection()
            self._redraw()
        self._phase = 'idle'

    # ── 画新选区 ──────────────────────────────────────
    def _draw_new_selection(self):
        rx = min(self._drag_start_x, self._drag_end_x)
        ry = min(self._drag_start_y, self._drag_end_y)
        rw = abs(self._drag_end_x - self._drag_start_x)
        rh = abs(self._drag_end_y - self._drag_start_y)

        if rw < 2 or rh < 2:
            return

        constraint = self._get_constraint()
        if constraint:
            cw, ch = compute_constrained_size(rw, rh, constraint)
        else:
            cw, ch = rw, rh

        self._sel_cx, self._sel_cy = rx, ry
        self._sel_cw, self._sel_ch = cw, ch
        self._redraw()

    def _finalize_selection(self):
        """鼠标释放时锁定选区尺寸（宽高可能受比例约束）。"""
        rx = min(self._drag_start_x, self._drag_end_x)
        ry = min(self._drag_start_y, self._drag_end_y)
        rw = abs(self._drag_end_x - self._drag_start_x)
        rh = abs(self._drag_end_y - self._drag_start_y)

        if rw < 5 or rh < 5:
            self._sel_cw = self._sel_ch = 0
            return

        constraint = self._get_constraint()
        if constraint:
            cw, ch = compute_constrained_size(rw, rh, constraint)
        else:
            cw, ch = rw, rh

        self._sel_cx, self._sel_cy = rx, ry
        self._sel_cw, self._sel_ch = cw, ch

    # ── 平移选区 ──────────────────────────────────────
    def _move_selection(self):
        x, y = self._drag_end_x, self._drag_end_y
        screen_w = self._virtual_w
        screen_h = self._virtual_h

        new_cx = x - self._move_offset_x
        new_cy = y - self._move_offset_y

        # 边界裁剪
        new_cx = clamp(new_cx, self._virtual_x,
                       self._virtual_x + screen_w - self._sel_cw)
        new_cy = clamp(new_cy, self._virtual_y,
                       self._virtual_y + screen_h - self._sel_ch)

        self._sel_cx = new_cx
        self._sel_cy = new_cy

    # ── 绘制 ──────────────────────────────────────────
    def _redraw(self):
        """（模式/比例切换或平移后）重绘当前选区。"""
        self.canvas.delete('selection')

        if self._sel_cw < 2 or self._sel_ch < 2:
            self.canvas.configure(cursor='crosshair')
            return

        cx, cy = self._sel_cx, self._sel_cy
        cw, ch = self._sel_cw, self._sel_ch
        lx, ly = cx - self._virtual_x, cy - self._virtual_y

        # 高亮框边线
        self.canvas.create_rectangle(lx, ly, lx + cw, ly + ch,
                                     outline='#00d4ff', width=2,
                                     tags='selection')
        # 十字参考线
        self.canvas.create_line(lx, ly, lx + cw, ly + ch, fill='#00d4ff',
                                dash=(4, 4), width=1, tags='selection')
        self.canvas.create_line(lx + cw, ly, lx, ly + ch, fill='#00d4ff',
                                dash=(4, 4), width=1, tags='selection')

        # 四角标记
        corner_len = min(20, cw // 4, ch // 4)
        for (x0, y0, xn, yn) in [
            (lx, ly, lx + corner_len, ly), (lx, ly, lx, ly + corner_len),
            (lx + cw, ly, lx + cw - corner_len, ly), (lx + cw, ly, lx + cw, ly + corner_len),
            (lx, ly + ch, lx + corner_len, ly + ch), (lx, ly + ch, lx, ly + ch - corner_len),
            (lx + cw, ly + ch, lx + cw - corner_len, ly + ch),
            (lx + cw, ly + ch, lx + cw, ly + ch - corner_len),
        ]:
            self.canvas.create_line(x0, y0, xn, yn, fill='white', width=3,
                                    tags='selection')

        # 尺寸标签
        label_text = f'{cw} x {ch}'
        label_y = ly - 16 if ly > 40 else ly + ch + 20
        label_x = lx + cw // 2
        self.canvas.create_rectangle(label_x - 40, label_y - 10,
                                     label_x + 40, label_y + 10,
                                     fill='#00d4ff', outline='', tags='selection')
        self.canvas.create_text(label_x, label_y,
                                text=label_text, fill='black',
                                font=('Consolas', 9, 'bold'), tags='selection')
        self.status_label.config(
            text=f'{cw} × {ch} · {self.t("overlay.enter_confirm")} / {self.t("overlay.esc_cancel")}')

    # ── 确认截图 ──────────────────────────────────────
    def _on_confirm(self, event=None):
        if self._sel_cw < 5 or self._sel_ch < 5:
            return

        self.toolbar.withdraw()
        self._canvas_win.withdraw()
        self._mask_win.withdraw()

        try:
            self._capture_and_save(self._sel_cx, self._sel_cy,
                                   self._sel_cw, self._sel_ch)
        except Exception as exc:
            # A failed screen grab or clipboard adapter must not leave the
            # overlay alive and block the next global shortcut.
            print(f'[WARN] Screenshot failed: {exc}')
            from runtime_status import publish_status
            publish_status('error', f'Screenshot failed: {exc}')
        finally:
            self._stop_config_poll()
            try:
                self._canvas_win.grab_release()
            except tk.TclError:
                pass
            for window in (self._canvas_win, self._mask_win, self.toolbar):
                try:
                    window.destroy()
                except tk.TclError:
                    pass

    def _capture_and_save(self, x, y, w, h):
        from PIL import ImageGrab

        screen_w = self._virtual_w
        screen_h = self._virtual_h
        x = clamp(x, self._virtual_x, self._virtual_x + screen_w - 1)
        y = clamp(y, self._virtual_y, self._virtual_y + screen_h - 1)
        w = min(w, self._virtual_x + screen_w - x)
        h = min(h, self._virtual_y + screen_h - y)

        grab_args = {'bbox': (x, y, x + w, y + h)}
        if os.name == 'nt':
            grab_args['all_screens'] = True
        img = ImageGrab.grab(**grab_args)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        prefix = self.config.get('file_prefix', DEFAULT_CONFIG['file_prefix'])
        fmt = self.config.get('file_format', DEFAULT_CONFIG['file_format']).lower()
        save_format = {'png': 'PNG', 'jpg': 'JPEG', 'bmp': 'BMP'}.get(fmt, 'PNG')
        filename = f'{prefix}{timestamp}.{fmt}'
        filepath = os.path.join(self.save_dir, filename)

        saved_path = None
        save_error = None
        if self.config.get('auto_save', True):
            try:
                os.makedirs(self.save_dir, exist_ok=True)
                output = image_for_save_format(img, save_format)
                output.save(filepath, format=save_format)
                saved_path = filepath
                print(f'[OK] Screenshot saved: {filepath}')
                print(f'      Size: {w}x{h}')
            except (OSError, ValueError) as exc:
                save_error = exc
                print(f'[WARN] Screenshot save failed: {exc}')
        else:
            print('[INFO] Auto-save disabled')

        clipboard_ok = None
        if self.config.get('auto_clipboard', True):
            clipboard_ok = self._copy_to_clipboard(img, saved_path)

        from runtime_status import publish_status
        if saved_path and clipboard_ok is True:
            publish_status('success', f'Screenshot saved and copied: {saved_path}', saved_path)
        elif saved_path:
            level = 'info' if clipboard_ok is False else 'success'
            suffix = ' (clipboard copy failed)' if clipboard_ok is False else ''
            publish_status(level, f'Screenshot saved: {saved_path}{suffix}', saved_path)
        elif clipboard_ok is True:
            publish_status('success', 'Screenshot copied to clipboard')
        elif save_error:
            publish_status('error', f'Screenshot save failed: {save_error}')
        else:
            publish_status('info', 'Screenshot captured')

    def _copy_to_clipboard(self, img, filepath=None):
        """Copy independently of auto-save through the platform adapter."""
        from clipboard_utils import copy_image
        copied = copy_image(img, filepath)
        if not copied:
            print('[WARN] Screenshot was not copied to the clipboard')
        return copied
