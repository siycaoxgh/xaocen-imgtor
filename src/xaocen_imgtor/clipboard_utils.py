#!/usr/bin/env python3
"""Platform-specific image clipboard adapters."""

import os
import platform
import subprocess
import tempfile


def copy_image(image, filepath=None):
    """Copy a PIL image using the platform adapter, returning success status."""
    # Always hand the clipboard adapter a fresh PNG. Reusing the final BMP/JPG
    # path is unreliable on Windows because Pillow may still hold the file and
    # GDI+ has different decoder/alpha behavior for each source format.
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='drawru-imgter-clipboard-', suffix='.png')
        os.close(fd)
        clipboard_image = image
        if image.mode not in {'1', 'L', 'P', 'RGB', 'RGBA', 'LA', 'I;16'}:
            clipboard_image = image.convert('RGBA')
        clipboard_image.save(temporary, format='PNG')
        filepath = temporary
        system = platform.system()
        if system == 'Windows':
            script = (
                'Add-Type -AssemblyName System.Windows.Forms;'
                'Add-Type -AssemblyName System.Drawing;'
                '$path=$env:DRAWRU_CLIPBOARD_PATH;'
                '$source=[System.Drawing.Image]::FromFile($path);'
                '$img=New-Object System.Drawing.Bitmap($source);'
                '$source.Dispose();'
                '[System.Windows.Forms.Clipboard]::SetDataObject($img, $true);'
                '$img.Dispose()'
            )
            env = os.environ.copy()
            env['DRAWRU_CLIPBOARD_PATH'] = filepath
            run_options = {'env': env}
            if os.name == 'nt':
                run_options['creationflags'] = subprocess.CREATE_NO_WINDOW
            result = subprocess.run(
                ['powershell', '-NoProfile', '-STA', '-Command', script],
                capture_output=True, timeout=8, check=False, **run_options)
            if result.returncode:
                raise RuntimeError(result.stderr.decode(errors='replace').strip() or 'PowerShell clipboard failed')
        elif system == 'Darwin':
            subprocess.run([
                'osascript', '-e',
                f'set the clipboard to (read (POSIX file "{filepath}") as «class PNGf»)',
            ], check=True, timeout=8)
        else:
            with open(filepath, 'rb') as stream:
                subprocess.run(
                    ['xclip', '-selection', 'clipboard', '-t', 'image/png', '-i'],
                    stdin=stream, check=True, timeout=8)
        return True
    except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
        print(f'[WARN] Clipboard unavailable on {platform.system()}: {exc}')
        return False
    finally:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass
