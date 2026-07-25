# MP4 Video Recorder plugin prototype

This optional Windows plugin records a desktop region with FFmpeg `gdigrab`.
It is intentionally outside the drawru-imgter core because FFmpeg dominates
the package size.

## Installation layout

Copy this folder to:

```text
%LOCALAPPDATA%\drawru-imgter\plugins\video-recorder-ffmpeg\
```

Place a Windows FFmpeg binary at either:

```text
ffmpeg/bin/ffmpeg.exe
bin/ffmpeg.exe
ffmpeg.exe
```

The plugin first runs `ffmpeg -version` and reports a clear missing/unusable
status; it never relies on a system-wide FFmpeg installation.

## Current boundary

The main app now reuses its DPI-aware interactive selection overlay, ratio and
fixed-size controls, 3/2/1 countdown and recording start/stop shortcuts for
the MP4 path. FFmpeg receives the immutable virtual-desktop selection box.

The prototype still needs real Windows validation at 100%, 125% and 150%
display scaling, including multiple monitors with negative coordinates. It is
Windows-only and records video without system audio in this release.

FFmpeg's official `gdigrab` documentation defines `framerate`, `video_size`,
`offset_x` and `offset_y`, including negative offsets for displays left/above
the primary monitor: https://ffmpeg.org/ffmpeg-devices.html
