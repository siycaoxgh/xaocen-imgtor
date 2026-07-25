"""
drawru-imgter 单位解析工具
"""

import platform
import ctypes


def get_screen_dpi():
    """获取当前主屏幕的 DPI。"""
    if platform.system() == 'Windows':
        try:
            hdc = ctypes.windll.user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
            ctypes.windll.user32.ReleaseDC(0, hdc)
            return dpi
        except Exception:
            pass
    return 96  # 默认


def parse_dimension(value_str):
    """
    解析尺寸字符串，支持 px / in / cm 后缀。
    - "400px" → 400
    - "4in"   → 4 * DPI
    - "10cm"  → 10 / 2.54 * DPI
    - "400"   → 400（无单位默认 px）
    返回 int 像素值。
    """
    s = value_str.strip().lower()
    if not s:
        raise ValueError('empty dimension')

    dpi = get_screen_dpi()

    if s.endswith('px'):
        return int(float(s[:-2]))
    elif s.endswith('in'):
        return round(float(s[:-2]) * dpi)
    elif s.endswith('cm'):
        return round(float(s[:-2]) / 2.54 * dpi)
    elif s.endswith('mm'):
        return round(float(s[:-2]) / 25.4 * dpi)
    else:
        # 无单位，默认 px
        return int(float(s))
