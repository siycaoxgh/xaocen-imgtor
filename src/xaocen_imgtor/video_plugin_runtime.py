"""Small core-side launcher for the optional, plugin-local FFmpeg binary."""

import os
from pathlib import Path

from .plugin_manager import resolve_plugin


def find_video_ffmpeg():
    """Find FFmpeg only inside the validated video-plugin directory."""
    resolved = resolve_plugin('video-recorder-ffmpeg')
    if not resolved or os.name != 'nt':
        return None
    folder, _manifest = resolved
    for relative in ('ffmpeg/bin/ffmpeg.exe', 'bin/ffmpeg.exe', 'ffmpeg.exe'):
        candidate = folder / relative
        if candidate.is_file():
            return candidate
    return None


def build_gdigrab_command(ffmpeg, bbox, fps, duration_seconds, output_path):
    """Build a list-only FFmpeg command for an immutable virtual-screen bbox."""
    left, top, right, bottom = (int(value) for value in bbox)
    width, height = right - left, bottom - top
    # libx264 with yuv420p requires even dimensions. Tk selection rectangles
    # can legitimately end on an odd pixel, so normalize before invoking
    # FFmpeg instead of letting the encoder fail after the countdown.
    width -= width % 2
    height -= height % 2
    fps = max(1, min(60, int(fps)))
    duration = max(1, min(120, int(duration_seconds)))
    output = Path(output_path)
    if width < 2 or height < 2:
        raise ValueError('video_record_region_invalid')
    return [
        str(ffmpeg), '-y', '-f', 'gdigrab', '-framerate', str(fps),
        '-offset_x', str(left), '-offset_y', str(top), '-video_size', f'{width}x{height}',
        '-i', 'desktop', '-t', str(duration), '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', str(output),
    ]
