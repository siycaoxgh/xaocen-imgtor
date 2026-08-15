"""Translations used by the active native capture/recording engines.

The launcher, browser, cropper and settings windows are legacy Tk entry
points.  Their old translation tables are intentionally no longer kept here;
the active UI is translated by ``ui/app.js`` and the native overlays only
need the small set below.
"""

LANG = {
    'zh': {
        'main.status': '已启动',
        'main.mode_ratio': '比例',
        'main.mode_fixed': '固定尺寸',
        'main.save_to': '保存到',
        'main.hotkey_error': '快捷键注册失败',
        'overlay.mode': '模式',
        'overlay.ratio': '固定比例',
        'overlay.width': '宽',
        'overlay.height': '高',
        'overlay.unit_hint': 'px/in/cm/mm',
        'overlay.drag_hint': '拖拽框选区域',
        'overlay.enter_confirm': 'Enter 确认',
        'overlay.esc_cancel': 'Esc 取消',
        'gif.title': '动图录制',
        'gif.format': '输出格式',
        'gif.drag_hint': '拖拽选择录制区域',
        'gif.start_hint': 'Enter 开始录制',
    },
    'en': {
        'main.status': 'Started',
        'main.mode_ratio': 'Ratio',
        'main.mode_fixed': 'Fixed size',
        'main.save_to': 'Save to',
        'main.hotkey_error': 'Shortcut registration failed',
        'overlay.mode': 'Mode',
        'overlay.ratio': 'Fixed ratio',
        'overlay.width': 'W',
        'overlay.height': 'H',
        'overlay.unit_hint': 'px/in/cm/mm',
        'overlay.drag_hint': 'Drag to select an area',
        'overlay.enter_confirm': 'Enter confirm',
        'overlay.esc_cancel': 'Esc cancel',
        'gif.title': 'Motion recorder',
        'gif.format': 'Output format',
        'gif.drag_hint': 'Drag to select a record area',
        'gif.start_hint': 'Enter to start recording',
    },
}


def get(config, key, **kwargs):
    """Return a translated active-engine string with optional formatting."""
    language = config.get('language', 'zh') if isinstance(config, dict) else 'zh'
    if language not in LANG:
        language = 'zh'
    text = LANG[language].get(key, LANG['en'].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass
    return text


def get_lang(config):
    """Return the configured language code."""
    language = config.get('language', 'zh') if isinstance(config, dict) else 'zh'
    return language if language in LANG else 'zh'
