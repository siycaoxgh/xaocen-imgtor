#!/usr/bin/env python3
"""Build a portable, integrity-checked .xaocen-plugin bundle.

Usage:
    python plugin_packager.py <plugin-folder> [output.xaocen-plugin]
"""

import sys
from pathlib import Path

from plugin_manager import PLUGIN_PACKAGE_SUFFIX, create_plugin_package


def main(argv=None):
    argv = list(argv or sys.argv[1:])
    if not argv or len(argv) > 2:
        print('Usage: python plugin_packager.py <plugin-folder> [output.xaocen-plugin]')
        return 2
    source = Path(argv[0]).resolve()
    output = Path(argv[1]).resolve() if len(argv) == 2 else source.with_suffix(PLUGIN_PACKAGE_SUFFIX)
    if output.suffix.lower() != PLUGIN_PACKAGE_SUFFIX:
        output = output.with_suffix(PLUGIN_PACKAGE_SUFFIX)
    try:
        package = create_plugin_package(source, output)
    except (OSError, ValueError) as exc:
        print(f'[ERROR] Could not package plugin: {exc}')
        return 1
    print(f'[OK] Created verified plugin package: {package}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
