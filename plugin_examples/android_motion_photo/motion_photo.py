#!/usr/bin/env python3
"""Pure-Python reference writer for JPEG + MP4 Android Motion Photos.

This prototype deliberately does *not* encode video.  It packages an already
valid JPEG and MP4 into Google's Motion Photo 1.0 layout: XMP in the JPEG plus
the original MP4 appended as the last container item.  Keeping video encoding
outside this module is what lets the main application remain lightweight.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
from pathlib import Path


XMP_HEADER = b'http://ns.adobe.com/xap/1.0/\x00'
MAX_APP1_PAYLOAD = 65_533
_VIDEO_LENGTH = re.compile(rb'Item:Length="(\d+)"')


class MotionPhotoError(ValueError):
    """A source file cannot safely be packaged or extracted."""


def _require_jpeg(data: bytes) -> None:
    if len(data) < 4 or not data.startswith(b'\xff\xd8'):
        raise MotionPhotoError('The primary image must be a JPEG file.')


def _require_mp4(data: bytes) -> None:
    # ISO BMFF begins with a box size followed by its four-byte type.  The
    # first box normally is ftyp; accepting only this form avoids appending an
    # arbitrary file while still supporting common MP4 writers.
    if len(data) < 12 or data[4:8] != b'ftyp':
        raise MotionPhotoError('The motion video must be an MP4 file with an ftyp box.')


def _require_mp4_file(path: Path) -> int:
    """Validate an MP4 header without copying the complete video into memory."""
    try:
        size = path.stat().st_size
        with path.open('rb') as stream:
            _require_mp4(stream.read(12))
    except OSError as error:
        raise MotionPhotoError(f'Unable to read motion video: {error}') from error
    return size


def _google_xmp_payload(video_length: int, presentation_timestamp_us: int = -1) -> bytes:
    packet = f'''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
   xmlns:Camera="http://ns.google.com/photos/1.0/camera/"
   Camera:MotionPhoto="1"
   Camera:MotionPhotoVersion="1"
   Camera:MotionPhotoPresentationTimestampUs="{presentation_timestamp_us}">
   <Container:Directory xmlns:Container="http://ns.google.com/photos/1.0/container/"
    xmlns:Item="http://ns.google.com/photos/1.0/container/item/">
    <rdf:Seq>
     <rdf:li rdf:parseType="Resource"><Container:Item Item:Mime="image/jpeg" Item:Semantic="Primary"/></rdf:li>
     <rdf:li rdf:parseType="Resource"><Container:Item Item:Mime="video/mp4" Item:Semantic="MotionPhoto" Item:Length="{video_length}"/></rdf:li>
    </rdf:Seq>
   </Container:Directory>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''.encode('utf-8')
    payload = XMP_HEADER + packet
    if len(payload) > MAX_APP1_PAYLOAD:
        raise MotionPhotoError('Motion Photo metadata exceeds the JPEG APP1 limit.')
    return payload


def _xiaomi_xmp_payload(video_length: int, presentation_timestamp_us: int = -1) -> bytes:
    """Legacy GCamera MicroVideo XMP used by the Redmi K60 reference file.

    This is deliberately an experimental compatibility profile.  It preserves
    the same JPEG + appended MP4 container but writes the legacy offset fields
    expected by older OEM gallery readers instead of the modern Container XMP.
    """
    packet = f'''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.1.0-jc003">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:GCamera="http://ns.google.com/photos/1.0/camera/"
      GCamera:MicroVideoVersion="1"
      GCamera:MicroVideo="1"
      GCamera:MicroVideoOffset="{video_length}"
      GCamera:MicroVideoPresentationTimestampUs="{presentation_timestamp_us}"/>
  </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''.encode('utf-8')
    payload = XMP_HEADER + packet
    if len(payload) > MAX_APP1_PAYLOAD:
        raise MotionPhotoError('Motion Photo metadata exceeds the JPEG APP1 limit.')
    return payload


def _strip_xmp_segments(jpeg: bytes) -> bytes:
    """Remove existing standard XMP APP1 segments but leave EXIF intact."""
    _require_jpeg(jpeg)
    output = bytearray(jpeg[:2])
    pos = 2
    while pos < len(jpeg):
        if jpeg[pos] != 0xFF:
            # Entropy-coded data starts after SOS; copy the remainder exactly.
            output.extend(jpeg[pos:])
            break
        marker_start = pos
        while pos < len(jpeg) and jpeg[pos] == 0xFF:
            pos += 1
        if pos >= len(jpeg):
            output.extend(jpeg[marker_start:])
            break
        marker = jpeg[pos]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            output.extend(jpeg[marker_start:pos + 1])
            pos += 1
            continue
        if marker == 0xDA:  # Start of Scan: remaining bytes are image data.
            output.extend(jpeg[marker_start:])
            break
        if pos + 2 >= len(jpeg):
            raise MotionPhotoError('JPEG marker segment is truncated.')
        segment_length = struct.unpack('>H', jpeg[pos + 1:pos + 3])[0]
        end = pos + 1 + segment_length
        if segment_length < 2 or end > len(jpeg):
            raise MotionPhotoError('JPEG marker segment has an invalid length.')
        payload = jpeg[pos + 3:end]
        if not (marker == 0xE1 and payload.startswith(XMP_HEADER)):
            output.extend(jpeg[marker_start:end])
        pos = end
    return bytes(output)


def _insert_xmp(jpeg: bytes, payload: bytes) -> bytes:
    """Insert a standard XMP APP1 segment immediately after JPEG SOI."""
    clean = _strip_xmp_segments(jpeg)
    segment = b'\xff\xe1' + struct.pack('>H', len(payload) + 2) + payload
    return clean[:2] + segment + clean[2:]


def _jpeg_size(jpeg: bytes) -> tuple[int, int]:
    """Read baseline/progressive JPEG dimensions without an image dependency."""
    _require_jpeg(jpeg)
    pos = 2
    while pos + 9 <= len(jpeg) and jpeg[pos] == 0xFF:
        marker = jpeg[pos + 1]
        if marker == 0xDA:
            break
        length = struct.unpack('>H', jpeg[pos + 2:pos + 4])[0]
        if marker in {0xC0, 0xC1, 0xC2} and length >= 8:
            height, width = struct.unpack('>HH', jpeg[pos + 5:pos + 9])
            if width and height:
                return width, height
        pos += 2 + length
    raise MotionPhotoError('JPEG dimensions are unavailable.')


def _minimal_exif_segment(width: int, height: int) -> bytes:
    """Build the APP1 EXIF shape retained by WeChat/Xiaomi reference files."""
    tiff = b'MM\x00*\x00\x00\x00\x08' + struct.pack('>H', 4)
    tiff += struct.pack('>HHII', 0x0100, 4, 1, width)
    tiff += struct.pack('>HHII', 0x0101, 4, 1, height)
    tiff += struct.pack('>HHII', 0x8769, 4, 1, 62)
    tiff += struct.pack('>HHII', 0x0112, 4, 1, 0)
    tiff += b'\x00\x00\x00\x00'
    tiff += struct.pack('>H', 2)
    tiff += struct.pack('>HHII', 0xA001, 3, 1, 0x00010000)
    tiff += struct.pack('>HHII', 0x9208, 4, 1, 0)
    tiff += b'\x00\x00\x00\x00'
    payload = b'Exif\x00\x00' + tiff
    return b'\xff\xe1' + struct.pack('>H', len(payload) + 2) + payload


def _insert_xiaomi_metadata(jpeg: bytes, xmp_payload: bytes) -> bytes:
    """Write EXIF then XMP, matching the recognized Redmi/K60 file ordering."""
    clean = _strip_xmp_segments(jpeg)
    width, height = _jpeg_size(clean)
    xmp_segment = b'\xff\xe1' + struct.pack('>H', len(xmp_payload) + 2) + xmp_payload
    # The cropped web canvas has no EXIF.  A minimal EXIF block makes the
    # JPEG structurally match Xiaomi/WeChat-recognized Motion Photos.
    return clean[:2] + _minimal_exif_segment(width, height) + xmp_segment + clean[2:]


def create_motion_photo(image_path: str | Path, video_path: str | Path,
                        output_path: str | Path, presentation_timestamp_us: int = -1,
                        profile: str = 'google') -> Path:
    """Package JPEG + MP4 with a Google or experimental Xiaomi XMP profile."""
    image = Path(image_path)
    video = Path(video_path)
    output = Path(output_path)
    jpeg = image.read_bytes()
    _require_jpeg(jpeg)
    mp4_length = _require_mp4_file(video)
    # Redmi K60 / Xiaomi Gallery reference files use 0 rather than the
    # Android convention's unknown sentinel (-1).  Keep Google unchanged.
    if profile == 'xiaomi' and presentation_timestamp_us < 0:
        presentation_timestamp_us = 0
    if profile == 'google':
        xmp = _google_xmp_payload(mp4_length, presentation_timestamp_us)
    elif profile == 'xiaomi':
        xmp = _xiaomi_xmp_payload(mp4_length, presentation_timestamp_us)
    else:
        raise MotionPhotoError('Unsupported Motion Photo compatibility profile.')
    metadata_jpeg = (_insert_xiaomi_metadata(jpeg, xmp)
                     if profile == 'xiaomi' else _insert_xmp(jpeg, xmp))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('wb') as destination:
        destination.write(metadata_jpeg)
        with video.open('rb') as source:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
    return output


def inspect_motion_photo(path: str | Path) -> dict:
    """Return bounded, parser-independent information about a packaged JPEG."""
    source = Path(path)
    with source.open('rb') as stream:
        data = stream.read(256 * 1024)
    _require_jpeg(data)
    xmp_start = data.find(XMP_HEADER)
    if xmp_start < 0:
        return {'motion_photo': False, 'video_length': 0}
    xmp_end = data.find(b'<?xpacket end=', xmp_start)
    if xmp_end < 0:
        return {'motion_photo': False, 'video_length': 0}
    xmp_end = data.find(b'?>', xmp_end)
    metadata = data[xmp_start:xmp_end + 2] if xmp_end >= 0 else b''
    match = _VIDEO_LENGTH.search(metadata)
    length = int(match.group(1)) if match else 0
    is_google = b'Camera:MotionPhoto="1"' in metadata
    legacy = re.search(rb'(?:GCamera:)?MicroVideoOffset="(\d+)"', metadata)
    if legacy:
        length = int(legacy.group(1))
    is_motion = (is_google or legacy is not None) and length > 0 and source.stat().st_size >= length
    return {'motion_photo': is_motion, 'video_length': length,
            'profile': 'xiaomi' if legacy is not None else ('google' if is_google else '')}


def extract_motion_photo(path: str | Path, image_output: str | Path,
                         video_output: str | Path) -> tuple[Path, Path]:
    """Extract the original JPEG container and appended MP4 from a Motion Photo."""
    source = Path(path)
    info = inspect_motion_photo(source)
    length = info['video_length']
    if not info['motion_photo'] or length <= 0:
        raise MotionPhotoError('No valid Motion Photo video was found.')
    image_size = source.stat().st_size - length
    with source.open('rb') as stream:
        image = _strip_xmp_segments(stream.read(image_size))
        video_header = stream.read(12)
    _require_mp4(video_header)
    image_out = Path(image_output)
    video_out = Path(video_output)
    image_out.parent.mkdir(parents=True, exist_ok=True)
    video_out.parent.mkdir(parents=True, exist_ok=True)
    image_out.write_bytes(image)
    with source.open('rb') as stream, video_out.open('wb') as destination:
        stream.seek(-length, 2)
        shutil.copyfileobj(stream, destination, length=1024 * 1024)
    return image_out, video_out


def process_request(request: dict) -> dict:
    """Handle the stable JSON protocol used by the core plugin host."""
    if not isinstance(request, dict) or request.get('protocol') != 1:
        return {'ok': False, 'error': 'protocol_unsupported'}
    command = request.get('command')
    payload = request.get('payload')
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'payload_invalid'}
    try:
        if command == 'inspect':
            return {'ok': True, 'data': inspect_motion_photo(payload['input_path'])}
        if command == 'create':
            output = create_motion_photo(payload['image_path'], payload['video_path'],
                                         payload['output_path'],
                                         int(payload.get('presentation_timestamp_us', -1)),
                                         str(payload.get('profile', 'google')))
            return {'ok': True, 'data': {'output_path': str(output)}}
        if command == 'extract':
            image, video = extract_motion_photo(payload['input_path'], payload['image_output'],
                                                payload['video_output'])
            return {'ok': True, 'data': {'image_path': str(image), 'video_path': str(video)}}
        return {'ok': False, 'error': 'command_unsupported'}
    except (KeyError, TypeError, ValueError, OSError, MotionPhotoError) as error:
        return {'ok': False, 'error': 'operation_failed', 'detail': str(error)[:500]}


def _main() -> int:
    # Handle protocol mode before constructing the regular required-subcommand
    # parser, otherwise argparse would reject ``--request`` without a CLI verb.
    if '--request' in __import__('sys').argv[1:]:
        try:
            request = json.loads(__import__('sys').stdin.buffer.read().decode('utf-8'))
        except (UnicodeError, json.JSONDecodeError):
            print(json.dumps({'ok': False, 'error': 'request_invalid'}))
            return 2
        response = process_request(request)
        print(json.dumps(response, ensure_ascii=False))
        return 0 if response.get('ok') else 2

    parser = argparse.ArgumentParser(description='Android Motion Photo reference plugin')
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('create', help='package JPEG and MP4 into a Motion Photo')
    create.add_argument('--image', required=True)
    create.add_argument('--video', required=True)
    create.add_argument('--output', required=True)
    create.add_argument('--timestamp-us', type=int, default=-1)
    inspect = sub.add_parser('inspect', help='inspect a Motion Photo')
    inspect.add_argument('--input', required=True)
    extract = sub.add_parser('extract', help='split a Motion Photo into JPEG and MP4')
    extract.add_argument('--input', required=True)
    extract.add_argument('--image-output', required=True)
    extract.add_argument('--video-output', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'create':
            print(create_motion_photo(args.image, args.video, args.output, args.timestamp_us))
        elif args.command == 'inspect':
            print(inspect_motion_photo(args.input))
        else:
            print(extract_motion_photo(args.input, args.image_output, args.video_output))
    except (OSError, MotionPhotoError) as error:
        parser.exit(2, f'error: {error}\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(_main())
