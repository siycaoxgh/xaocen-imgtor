# Motion Photo HyperOS Compatibility — Final Experiment Summary

Date: 2026-08-15
Device: Redmi K60 (`23013RK75C`)
System: Android 15 / HyperOS `V816` (`OS3.0.8.0.VMNCNXM`)
Gallery: Xiaomi system Gallery

## Confirmed device results

| Variant | Experiment | HyperOS | Playback | Audio |
|---|---|---:|---:|---:|
| G | Unchanged Xiaomi native control sample | Recognized | Yes | Yes |
| H | Native JPEG structure, ImgTor Xiaomi Legacy XMP | Recognized | Yes | Yes |
| I | Pillow-regenerated JPEG, native XMP/MP4 retained | Recognized | Yes | Yes |
| J | H with only `MicroVideoPresentationTimestampUs` changed to `1529894` | Recognized | Yes | Yes |
| K | H with only a 102-byte synthetic EXIF APP1 added | Not recognized | No | No |
| L | Formal Xiaomi Profile after removing synthetic EXIF injection | Recognized | Yes | Yes |

K remained playable with audio in third-party applications such as WeChat and
Xiaohongshu, so the failure is specific to the HyperOS Gallery compatibility
path rather than a broken JPEG/MP4 package.

## Structural evidence

The failed C/D/K samples contain an additional synthetic EXIF APP1 before the
original metadata. D also contains the original full EXIF APP1, creating two
EXIF APP1 segments. The successful H/I/J/L candidates do not contain this
synthetic block. L contains exactly one EXIF APP1 when the input contains EXIF.

All candidates passed the local Motion Photo validator for:

- JPEG SOI/EOI;
- Xiaomi Legacy XMP and `MicroVideoOffset`;
- MP4 `ftyp`, `moov`, and `mdat`;
- exact MP4 length;
- MP4 immediately following JPEG EOI and ending at file EOF;
- H.264 video and AAC audio for the native test media.

The J result excludes the exact presentation timestamp value as the decisive
variable. The I result excludes Pillow JPEG re-encoding as a decisive
variable. The K result isolates the synthetic/duplicate EXIF APP1 as the
strongest cause of HyperOS non-recognition.

## Final root cause conclusion

For the tested Redmi K60 / HyperOS environment, the incompatible structure was:

```text
JPEG SOI
→ synthetic minimal EXIF APP1
→ original full EXIF APP1 (when present)
→ Xiaomi Legacy XMP and other metadata
→ JPEG EOI
→ MP4
→ EOF
```

The final compatible structure is:

```text
JPEG SOI
→ Xiaomi Legacy XMP
→ original EXIF APP1, if present
→ remaining original JPEG metadata
→ JPEG EOI
→ MP4
→ EOF
```

This conclusion is evidence-based for the tested device and should not be
presented as a universal requirement for every OEM gallery.

## Final code change

`plugin_examples/android_motion_photo/motion_photo.py` no longer creates a
synthetic minimal EXIF APP1 for the Xiaomi Profile. It strips/replaces only
standard XMP, preserves the input JPEG metadata, and does not add a second
EXIF segment.

Google Motion Photo generation was not changed.

## Automated coverage

The regression tests now cover:

- Xiaomi output without input EXIF does not fabricate EXIF;
- input EXIF is preserved as one EXIF APP1;
- Google Profile behavior remains unchanged;
- existing JPEG/MP4/XMP/EOF validation continues to pass.
