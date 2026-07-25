#!/usr/bin/env python3
"""Standalone DPI-aware MP4 recorder using the optional FFmpeg plugin."""

import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from screen_utils import set_process_dpi_awareness
set_process_dpi_awareness()

from video_plugin_runtime import find_video_ffmpeg

if not find_video_ffmpeg():
    print('[WARN] Video recorder plugin is unavailable or missing its local FFmpeg binary.')
    raise SystemExit(2)

import tkinter as tk
from config_manager import load_config
from gifrecorder import GIFRecorder

config = load_config()
save_dir = config.get('save_directory') or os.path.join(
    os.path.expanduser('~'), 'Pictures', 'drawru-imgter')
os.makedirs(save_dir, exist_ok=True)

root = tk.Tk()
root.withdraw()
recorder = GIFRecorder(config, save_dir, record_kind='video')
try:
    recorder.run()
finally:
    root.destroy()
