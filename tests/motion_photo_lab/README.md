# Motion Photo Compatibility Lab

This folder contains only experiment tooling and generated reports. The four
Xiaomi/Redmi golden samples remain in `C:\Users\TOM\Downloads` and are never
moved, overwritten, or deleted.

Run from the project root:

```powershell
python tools\motion_photo_lab.py status
python tools\motion_photo_lab.py control --serial ce8df63f --sample C:\Users\TOM\Downloads\MVIMG_20260715_055104.jpg
python tools\motion_photo_lab.py prepare-exif --sample C:\Users\TOM\Downloads\MVIMG_20260715_055104.jpg
python tools\motion_photo_lab.py prepare-jpeg-xmp --sample C:\Users\TOM\Downloads\MVIMG_20260715_055104.jpg
python tools\motion_photo_lab.py prepare --sample C:\Users\TOM\Downloads\MVIMG_20260715_055104.jpg
python tools\motion_photo_lab.py push --report tests\motion_photo_lab\reports\experiment_001.json
```

Run `control` first for a new phone. It pushes an unchanged native sample and
records its local and remote SHA-256 values. Wait for the HyperOS Gallery
control result before generating the next experiment round.

`prepare` performs only the first single-variable experiment:

- Variant A: Xiaomi legacy metadata with `MicroVideoPresentationTimestampUs=0`.
- Variant B: the same extracted JPEG and byte-identical MP4 with the timestamp
  set to half of the measured MP4 duration.

The `push` command refuses non-Xiaomi/Redmi devices, never overwrites an
existing file in `/sdcard/DCIM/Camera/`, and records the selected device and
remote paths in the experiment JSON. Human HyperOS results are intentionally
left as `null` until the user checks the two files in the system Gallery.

Generated files are ignored by Git; keep the JSON reports when preserving an
experiment record.

## Final Xiaomi / HyperOS result

The complete G–L experiment summary is in
`reports/experiment_004_minimal_exif.md`. The Redmi K60 control and H/I/J/L
variants were recognized and playable with audio. K was deliberately given a
102-byte synthetic EXIF APP1 and was not recognized by HyperOS, while
third-party apps still played it. The v5.3.0 Xiaomi Profile therefore avoids
fabricating or duplicating EXIF APP1 segments.
