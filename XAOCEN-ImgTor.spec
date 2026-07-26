# -*- mode: python ; coding: utf-8 -*-

APP_VERSION = '5.0.1'


a = Analysis(
    ['webapp.py'],
    pathex=['.', 'src'],
    binaries=[],
    datas=[('ui', 'ui'), ('xaocen-imgtor.ico', '.')],
    # Worker entry points are bundled as data and executed through runpy, so
    # PyInstaller cannot discover their imports from webapp.py automatically.
    hiddenimports=[
        'pynput.keyboard', 'pynput.keyboard._win32',
        'xaocen_imgtor',
        'xaocen_imgtor.app_log', 'xaocen_imgtor.clipboard_utils',
        'xaocen_imgtor.config_manager', 'xaocen_imgtor.design_tokens',
        'xaocen_imgtor.dimensions', 'xaocen_imgtor.i18n',
        'xaocen_imgtor.instance_lock', 'xaocen_imgtor.native_toolbar',
        'xaocen_imgtor.plugin_host', 'xaocen_imgtor.plugin_manager',
        'xaocen_imgtor.plugin_packager', 'xaocen_imgtor.presets',
        'xaocen_imgtor.ratio_presets', 'xaocen_imgtor.rounded_controls',
        'xaocen_imgtor.runtime_status', 'xaocen_imgtor.screen_utils',
        'xaocen_imgtor.shortcuts', 'xaocen_imgtor.tray',
        'xaocen_imgtor.video_plugin_runtime',
        'xaocen_imgtor.paths',
        'xaocen_imgtor.overlay', 'xaocen_imgtor.gifrecorder',
        'xaocen_imgtor.workers', 'xaocen_imgtor.workers.screenshot',
        'xaocen_imgtor.workers.gifrecorder', 'xaocen_imgtor.workers.video',
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
    name=f'XAOCEN-ImgTor-v{APP_VERSION}',
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
