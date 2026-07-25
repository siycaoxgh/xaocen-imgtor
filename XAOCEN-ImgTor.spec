# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['webapp.py'],
    pathex=[],
    binaries=[],
    datas=[('ui', 'ui'), ('main.py', '.'), ('gifrecorder_standalone.py', '.'), ('video_recorder_standalone.py', '.'), ('xaocen-imgtor.ico', '.')],
    # Worker entry points are bundled as data and executed through runpy, so
    # PyInstaller cannot discover their imports from webapp.py automatically.
    hiddenimports=[
        'screen_utils', 'overlay', 'gifrecorder', 'native_toolbar',
        'rounded_controls', 'design_tokens', 'config_manager', 'instance_lock',
        'shortcuts', 'ratio_presets', 'presets', 'dimensions', 'i18n',
        'clipboard_utils', 'app_log', 'runtime_status', 'video_plugin_runtime',
        'pynput.keyboard', 'pynput.keyboard._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='XAOCEN-ImgTor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['xaocen-imgtor.ico'],
)
