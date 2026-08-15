"""Runtime paths shared by source runs and PyInstaller builds."""

from pathlib import Path
import sys


def application_dir() -> Path:
    """Return the writable application data root for this build."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


APP_DIR = application_dir()
RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', APP_DIR))
RUNTIME_DIR = APP_DIR / 'archive' / 'runtime'
