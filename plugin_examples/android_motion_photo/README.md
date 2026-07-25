# Android Motion Photo plugin prototype

This is a separately distributable reference plugin, not code loaded by the
drawru-imgter core. It packages an existing **JPEG + MP4** as one Android
Motion Photo (`*_MP.jpg`) and can extract the pair again.

## Test as an external plugin

Copy this entire folder to:

```text
%LOCALAPPDATA%\drawru-imgter\plugins\android-motion-photo\
```

Restart the app or reopen **Settings**. The core will then display its manifest
in the optional-plugin list. The current core intentionally does not launch
plugin entrypoints yet; run the prototype CLI below for this stage.

It implements the JPEG path of Android Motion Photo format 1.0:

- Camera XMP marks the JPEG as a Motion Photo;
- Container XMP declares the final MP4 item and its exact byte length;
- the MP4 is appended as the final bytes of the JPEG container.

It deliberately does not record or re-encode video. A future optional video
plugin can supply MP4 files through FFmpeg without increasing the core app
size.

## Prototype CLI

```powershell
python motion_photo.py create --image still.jpg --video clip.mp4 --output still_MP.jpg
python motion_photo.py inspect --input still_MP.jpg
python motion_photo.py extract --input still_MP.jpg --image-output still.jpg --video-output clip.mp4
```

## Compatibility boundary

The writer uses the documented Google container layout, but device gallery
acceptance still needs real-device verification (Google Photos, Pixel and
Samsung may differ). This prototype supports JPEG + MP4 only; HEIC/AVIF,
metadata tracks, transcoding and Apple Live Photo are intentionally out of
scope for this first plugin.

Specification: https://developer.android.com/media/platform/motion-photo-format
