#!/usr/bin/env python3
"""CLI wrapper for building a .xaocen-plugin package from source."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from xaocen_imgtor.plugin_packager import main


if __name__ == '__main__':
    raise SystemExit(main())
