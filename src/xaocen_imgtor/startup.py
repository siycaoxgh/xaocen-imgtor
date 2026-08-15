"""Windows logon startup integration for XAOCEN ImgTor."""

from __future__ import annotations

import os
import sys
from pathlib import Path


STARTUP_VALUE_NAME = 'XAOCENImgTor'
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'


def _command() -> str:
    """Return a stable command for the current source or frozen build."""
    if getattr(sys, 'frozen', False):
        return f'"{Path(sys.executable).resolve()}"'

    python = Path(sys.executable).resolve()
    pythonw = python.with_name('pythonw.exe')
    interpreter = pythonw if pythonw.is_file() else python
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / 'webapp.py'
    return f'"{interpreter}" "{script}"'


def is_supported() -> bool:
    return os.name == 'nt'


def is_enabled() -> bool:
    if not is_supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_READ) as key:
            value, _kind = winreg.QueryValueEx(key, STARTUP_VALUE_NAME)
        return bool(value)
    except (FileNotFoundError, OSError):
        return False


def set_enabled(enabled: bool) -> None:
    """Create or remove this application's per-user startup entry."""
    if not is_supported():
        raise OSError('startup_not_supported')
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ,
                              _command())
        else:
            try:
                winreg.DeleteValue(key, STARTUP_VALUE_NAME)
            except FileNotFoundError:
                pass
