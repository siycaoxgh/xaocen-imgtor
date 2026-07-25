#!/usr/bin/env python3
"""Standalone GIF recorder entry point."""
import os, sys

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from screen_utils import set_process_dpi_awareness
set_process_dpi_awareness()

import tkinter as tk
from config_manager import load_config
config = load_config()

save_dir = config.get('save_directory', '')
if not save_dir:
    save_dir = os.path.join(os.path.expanduser('~'), 'Pictures', 'drawru-imgter')
os.makedirs(save_dir, exist_ok=True)

from gifrecorder import GIFRecorder

root = tk.Tk()
root.withdraw()
r = GIFRecorder(config, save_dir)
try:
    r.run()
finally:
    # GIFRecorder owns its nested Tk event loop; do not leave a hidden root
    # mainloop running after the recorder window has been closed.
    root.destroy()
