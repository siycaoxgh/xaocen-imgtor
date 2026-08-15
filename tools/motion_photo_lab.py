#!/usr/bin/env python3
"""Safe, single-variable Motion Photo compatibility experiments.

This tool never edits the supplied Xiaomi samples.  It extracts copies into
``tests/motion_photo_lab`` and records every generated file and hash in JSON.
The ``push`` command is deliberately separate from ``prepare`` and only
accepts a connected Xiaomi/Redmi device.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'tests' / 'motion_photo_lab'
REPORTS = LAB / 'reports'
GENERATED = LAB / 'generated'
EXTRACTED = LAB / 'extracted'
ADB_DIR = LAB / 'adb'
DEFAULT_SAMPLE = Path.home() / 'Downloads' / 'MVIMG_20260715_055104.jpg'

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugin_examples.android_motion_photo.motion_photo import (  # noqa: E402
    XMP_HEADER,
    _find_ffprobe,
    _jpeg_eoi_offset,
    _xiaomi_xmp_payload,
    extract_motion_photo,
    inspect_motion_photo,
    create_motion_photo,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, capture_output=True, text=True, encoding='utf-8',
        errors='replace', timeout=timeout, check=False,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )


def find_adb() -> str | None:
    candidates = []
    for variable in ('ADB', 'ANDROID_HOME', 'ANDROID_SDK_ROOT'):
        value = os.environ.get(variable)
        if value:
            root = Path(value)
            candidates.append(root if root.name.lower() == 'adb.exe' else root / 'platform-tools' / 'adb.exe')
    local_app_data = os.environ.get('LOCALAPPDATA')
    if local_app_data:
        candidates.append(Path(local_app_data) / 'Android' / 'Sdk' / 'platform-tools' / 'adb.exe')
    candidates.append(Path('adb.exe'))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return shutil.which('adb')


def ffprobe_status() -> dict:
    binary = _find_ffprobe()
    result = {'path': binary, 'version': None, 'available': bool(binary)}
    if not binary:
        return result
    completed = _run([binary, '-version'])
    first_line = (completed.stdout or completed.stderr).splitlines()
    result['version'] = first_line[0].strip() if first_line else None
    result['available'] = completed.returncode == 0
    return result


def list_devices(adb: str) -> list[dict]:
    completed = _run([adb, 'devices', '-l'])
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or 'adb devices failed')
    devices = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith('List of devices'):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        item = {'serial': fields[0], 'status': fields[1]}
        for field in fields[2:]:
            if ':' in field:
                key, value = field.split(':', 1)
                item[key] = value
        devices.append(item)
    return devices


def device_properties(adb: str, serial: str) -> dict:
    names = {
        'manufacturer': 'ro.product.manufacturer',
        'brand': 'ro.product.brand',
        'model': 'ro.product.model',
        'device': 'ro.product.device',
        'android': 'ro.build.version.release',
        'sdk': 'ro.build.version.sdk',
        'incremental': 'ro.build.version.incremental',
        'hyperos': 'ro.miui.ui.version.name',
        'miui': 'ro.miui.ui.version.code',
        'build': 'ro.build.display.id',
    }
    result = {'serial': serial}
    for key, prop in names.items():
        completed = _run([adb, '-s', serial, 'shell', 'getprop', prop])
        result[key] = (completed.stdout or '').strip() or None
    return result


def _choose_device(adb: str, serial: str | None) -> tuple[dict, dict]:
    all_devices = list_devices(adb)
    unauthorized = [item for item in all_devices if item['status'] == 'unauthorized']
    if unauthorized:
        serials = ', '.join(item['serial'] for item in unauthorized)
        raise RuntimeError(
            f'ADB device is unauthorized ({serials}); unlock the phone and approve USB debugging.'
        )
    devices = [item for item in all_devices if item['status'] == 'device']
    if serial:
        selected = next((item for item in devices if item['serial'] == serial), None)
        if not selected:
            raise RuntimeError(f'ADB device is not ready: {serial}')
    elif len(devices) == 1:
        selected = devices[0]
    elif not devices:
        raise RuntimeError('No authorized ADB device is connected.')
    else:
        names = ', '.join(f"{item['serial']} ({item.get('model', 'unknown')})" for item in devices)
        raise RuntimeError(f'Multiple ADB devices connected; use --serial. Available: {names}')
    properties = device_properties(adb, selected['serial'])
    return selected, properties


def _require_xiaomi(properties: dict) -> None:
    identity = ' '.join(str(properties.get(key) or '') for key in ('manufacturer', 'brand', 'model'))
    if not any(value in identity.casefold() for value in ('xiaomi', 'redmi')):
        raise RuntimeError(f'Refusing HyperOS push to non-Xiaomi device: {identity.strip() or "unknown"}')


def _probe_duration(video: Path, ffprobe: str) -> float:
    completed = _run([
        ffprobe, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(video),
    ])
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or 'ffprobe duration failed')
    try:
        duration = float(completed.stdout.strip())
    except ValueError as error:
        raise RuntimeError(f'ffprobe returned an invalid duration: {completed.stdout!r}') from error
    if not duration > 0:
        raise RuntimeError(f'ffprobe returned a non-positive duration: {duration}')
    return duration


def _sample_name(sample: Path) -> str:
    # Keep the native-looking MVIMG prefix while ensuring A/B names differ.
    return sample.stem


def _rewrite_jpeg_app1(jpeg: bytes, transform):
    """Rewrite or remove APP1 segments without re-encoding JPEG pixels."""
    if not jpeg.startswith(b'\xff\xd8'):
        raise RuntimeError('The experiment source is not a JPEG.')
    output = bytearray(jpeg[:2])
    position = 2
    while position < len(jpeg):
        if jpeg[position] != 0xff:
            output.extend(jpeg[position:])
            break
        marker_start = position
        while position < len(jpeg) and jpeg[position] == 0xff:
            position += 1
        if position >= len(jpeg):
            output.extend(jpeg[marker_start:])
            break
        marker = jpeg[position]
        if marker == 0xda:
            output.extend(jpeg[marker_start:])
            break
        if marker in (0xd8, 0xd9, 0x01) or 0xd0 <= marker <= 0xd7:
            output.extend(jpeg[marker_start:position + 1])
            position += 1
            continue
        if position + 2 >= len(jpeg):
            raise RuntimeError('JPEG APP header is truncated.')
        segment_length = struct.unpack('>H', jpeg[position + 1:position + 3])[0]
        end = position + 1 + segment_length
        if segment_length < 2 or end > len(jpeg):
            raise RuntimeError('JPEG APP segment has an invalid length.')
        payload = jpeg[position + 3:end]
        replacement = transform(marker, payload, jpeg[marker_start:end])
        if replacement is not None:
            output.extend(replacement)
        position = end
    return bytes(output)


def _remove_exif_segments(jpeg: bytes) -> bytes:
    def transform(marker, payload, raw):
        if marker == 0xe1 and payload.startswith(b'Exif\x00\x00'):
            return None
        return raw
    return _rewrite_jpeg_app1(jpeg, transform)


def _remove_camera_identity_exif(jpeg: bytes) -> tuple[bytes, list[str], list[str]]:
    """Remove only Make/Model/Software from an EXIF APP1 in a JPEG copy."""
    with Image.open(BytesIO(jpeg)) as image:
        exif = image.getexif()
    labels = {0x010f: 'Make', 0x0110: 'Model', 0x0131: 'Software'}
    before = [name for tag, name in labels.items() if exif.get(tag) not in (None, '', b'')]
    for tag in labels:
        exif.pop(tag, None)
    exif_payload = exif.tobytes()
    if not exif_payload.startswith(b'Exif\x00\x00'):
        raise RuntimeError('Could not rebuild the native EXIF block.')
    replaced = False

    def transform(marker, payload, raw):
        nonlocal replaced
        if marker != 0xe1 or not payload.startswith(b'Exif\x00\x00') or replaced:
            return raw
        replaced = True
        return b'\xff\xe1' + struct.pack('>H', len(exif_payload) + 2) + exif_payload

    result = _rewrite_jpeg_app1(jpeg, transform)
    if not replaced:
        raise RuntimeError('Native JPEG did not contain an EXIF APP1 block.')
    return result, before, [name for tag, name in labels.items() if exif.get(tag) not in (None, '', b'')]


def _jpeg_segments(jpeg: bytes):
    """Yield JPEG header segments up to SOS without reading appended MP4."""
    if not jpeg.startswith(b'\xff\xd8'):
        raise RuntimeError('The experiment source is not a JPEG.')
    position = 2
    while position < len(jpeg):
        if jpeg[position] != 0xff:
            return
        marker_start = position
        while position < len(jpeg) and jpeg[position] == 0xff:
            position += 1
        if position >= len(jpeg):
            return
        marker = jpeg[position]
        position += 1
        if marker == 0xda:
            if position + 2 > len(jpeg):
                return
            segment_length = struct.unpack('>H', jpeg[position:position + 2])[0]
            end = position + segment_length
            if segment_length < 2 or end > len(jpeg):
                return
            yield marker_start, marker, jpeg[position + 2:end], jpeg[marker_start:end]
            return
        if marker == 0xd9:
            yield marker_start, marker, b'', jpeg[marker_start:position]
            return
        if marker in (0xd8, 0x01) or 0xd0 <= marker <= 0xd7:
            yield marker_start, marker, b'', jpeg[marker_start:position]
            continue
        if position + 2 > len(jpeg):
            return
        segment_length = struct.unpack('>H', jpeg[position:position + 2])[0]
        end = position + segment_length
        if segment_length < 2 or end > len(jpeg):
            return
        yield marker_start, marker, jpeg[position + 2:end], jpeg[marker_start:end]
        position = end


def _marker_name(marker: int) -> str:
    names = {
        0xd8: 'SOI', 0xd9: 'EOI', 0xda: 'SOS', 0xdb: 'DQT',
        0xc0: 'SOF0 (baseline)', 0xc1: 'SOF1', 0xc2: 'SOF2 (progressive)',
        0xc3: 'SOF3', 0xc4: 'DHT', 0xdd: 'DRI', 0xfe: 'COM',
    }
    if 0xe0 <= marker <= 0xef:
        return f'APP{marker - 0xe0}'
    if 0xd0 <= marker <= 0xd7:
        return f'RST{marker - 0xd0}'
    return names.get(marker, f'MARKER 0x{marker:02X}')


def _payload_type(marker: int, payload: bytes) -> str:
    if marker == 0xe0 and payload.startswith(b'JFIF\x00'):
        return 'JFIF'
    if marker == 0xe1 and payload.startswith(b'Exif\x00\x00'):
        return 'Exif'
    if marker == 0xe1 and payload.startswith(XMP_HEADER):
        return 'XMP'
    if marker == 0xe1 and payload.startswith(b'http://ns.adobe.com/xmp/extension/\x00'):
        return 'Extended XMP'
    if marker == 0xe2 and payload.startswith(b'ICC_PROFILE\x00'):
        return 'ICC Profile'
    if marker == 0xee and payload.startswith(b'Adobe'):
        return 'Adobe'
    return ''


def _sof_details(marker: int, payload: bytes) -> dict:
    if marker < 0xc0 or marker > 0xcf or marker in {0xc4, 0xc8, 0xcc} or len(payload) < 6:
        return {}
    components = payload[5]
    factors = []
    for index in range(components):
        start = 6 + index * 3
        if start + 2 >= len(payload):
            break
        factors.append({'id': payload[start], 'h': payload[start + 1] >> 4,
                        'v': payload[start + 1] & 0x0f})
    return {'components': components, 'sampling_factors': factors}


def analyze_jpeg_markers(path: Path) -> dict:
    data = path.read_bytes()
    entries = [{'index': 0, 'marker': 'SOI', 'offset': 0, 'length': 2,
                'payload_length': 0, 'payload_type': ''}]
    sequence = list(_jpeg_segments(data))
    for index, (offset, marker, payload, raw) in enumerate(sequence, start=1):
        entry = {
            'index': index, 'marker': _marker_name(marker), 'offset': offset,
            'length': len(raw), 'payload_length': len(payload),
            'payload_type': _payload_type(marker, payload),
        }
        entry.update(_sof_details(marker, payload))
        entries.append(entry)
    eoi_end = _jpeg_eoi_offset(data)
    if eoi_end is not None:
        entries.append({'index': len(entries), 'marker': 'EOI', 'offset': eoi_end - 2,
                        'length': 2, 'payload_length': 0, 'payload_type': ''})
    with Image.open(BytesIO(data)) as image:
        info = dict(image.info)
        exif = image.getexif()
        encoding = {
            'format': image.format,
            'mode': image.mode,
            'size': list(image.size),
            'progressive': bool(info.get('progressive') or info.get('progression')),
            'jfif': bool(info.get('jfif')),
            'jfif_version': info.get('jfif_version'),
            'jfif_unit': info.get('jfif_unit'),
            'jfif_density': list(info.get('jfif_density', ())) if info.get('jfif_density') else None,
            'icc_profile_bytes': len(info.get('icc_profile', b'')),
            'adobe': info.get('adobe'),
            'quantization_tables': len(image.quantization or {}),
            'exif_tags': {
                'Make': exif.get(0x010f), 'Model': exif.get(0x0110),
                'Software': exif.get(0x0131), 'DateTime': exif.get(0x0132),
                'Orientation': exif.get(0x0112),
            },
        }
    sof = next((entry for entry in entries if entry['marker'].startswith('SOF')), {})
    encoding.update({key: sof[key] for key in ('components', 'sampling_factors') if key in sof})
    return {'file': str(path), 'size_bytes': len(data), 'markers': entries,
            'encoding': encoding}


def _xmp_payloads(jpeg: bytes) -> list[bytes]:
    return [payload for _offset, marker, payload, _raw in _jpeg_segments(jpeg)
            if marker == 0xe1 and payload.startswith(XMP_HEADER)]


def _xmp_stats(payload: bytes) -> dict:
    packet = payload[len(XMP_HEADER):] if payload.startswith(XMP_HEADER) else payload
    begin_at = packet.find(b'<?xpacket begin=')
    begin_end = packet.find(b'?>', begin_at) + 2 if begin_at >= 0 else -1
    end_at = packet.find(b'<?xpacket end=')
    end_end = packet.find(b'?>', end_at) + 2 if end_at >= 0 else -1
    return {
        'payload_length': len(payload), 'packet_length': len(packet),
        'xpacket_begin': packet[begin_at:begin_end].decode('utf-8', 'replace') if begin_end > 0 else None,
        'xpacket_end': packet[end_at:end_end].decode('utf-8', 'replace') if end_end > 0 else None,
        'padding_bytes': max(0, len(packet) - end_end) if end_end > 0 else None,
    }


def _normalized_xmp(payload: bytes) -> str:
    text = (payload[len(XMP_HEADER):] if payload.startswith(XMP_HEADER) else payload).decode('utf-8', 'replace')
    start = text.find('<x:xmpmeta')
    end = text.rfind('</x:xmpmeta>')
    if start >= 0 and end >= 0:
        text = text[start:end + len('</x:xmpmeta>')]
    try:
        return ET.canonicalize(text, with_comments=False)
    except (ET.ParseError, AttributeError):
        return '\n'.join(line.strip() for line in text.splitlines() if line.strip())


def _replace_standard_xmp(jpeg: bytes, payload: bytes) -> bytes:
    replaced = False

    def transform(marker, current, raw):
        nonlocal replaced
        if marker == 0xe1 and current.startswith(XMP_HEADER) and not replaced:
            replaced = True
            return b'\xff\xe1' + struct.pack('>H', len(payload) + 2) + payload
        return raw

    result = _rewrite_jpeg_app1(jpeg, transform)
    if not replaced:
        raise RuntimeError('Native JPEG did not contain a standard XMP APP1 segment.')
    return result


def _insert_xmp_and_video(jpeg: bytes, xmp_payload: bytes, video: bytes) -> bytes:
    segment = b'\xff\xe1' + struct.pack('>H', len(xmp_payload) + 2) + xmp_payload
    return jpeg[:2] + segment + jpeg[2:] + video


def _regenerate_jpeg(primary: bytes) -> bytes:
    with Image.open(BytesIO(primary)) as image:
        image.load()
        output = BytesIO()
        save_options = {'format': 'JPEG', 'quality': 95, 'optimize': False}
        if image.info.get('exif'):
            save_options['exif'] = image.info['exif']
        image.save(output, **save_options)
    return output.getvalue()


def _write_diff(path: Path, before: str, after: str, before_name: str, after_name: str) -> None:
    path.write_text(''.join(difflib.unified_diff(
        before.splitlines(True), after.splitlines(True),
        fromfile=before_name, tofile=after_name)), encoding='utf-8')


def _load_first_round_timestamp() -> int:
    report_path = REPORTS / 'experiment_001.json'
    try:
        report = json.loads(report_path.read_text(encoding='utf-8'))
        timestamp = int(report['variants']['B']['changes']['GCamera:MicroVideoPresentationTimestampUs'])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError('The first-round Timestamp report is unavailable.') from error
    if timestamp <= 0:
        raise RuntimeError('The first-round positive timestamp is invalid.')
    return timestamp


def prepare_exif(sample_path: Path) -> dict:
    """Create C/D/F after the native control group has passed on HyperOS."""
    sample = sample_path.expanduser().resolve()
    if not sample.is_file():
        raise RuntimeError(f'Golden Sample does not exist: {sample}')
    probe = ffprobe_status()
    if not probe['available']:
        raise RuntimeError('ffprobe.exe is not available.')
    for folder in (REPORTS, GENERATED, EXTRACTED):
        folder.mkdir(parents=True, exist_ok=True)
    stem = _sample_name(sample)
    image_copy = EXTRACTED / f'{stem}_primary.jpg'
    video_copy = EXTRACTED / f'{stem}_motion.mp4'
    if not image_copy.is_file() or not video_copy.is_file():
        extract_motion_photo(sample, image_copy, video_copy)
    timestamp_us = _load_first_round_timestamp()
    native_primary = image_copy.read_bytes()
    no_camera_exif = EXTRACTED / f'{stem}_no_camera_exif.jpg'
    no_camera_exif.write_bytes(_remove_exif_segments(native_primary))
    outputs = {
        'C': GENERATED / 'MVIMG_EXIF_C_20260815.jpg',
        'D': GENERATED / 'MVIMG_EXIF_D_20260815.jpg',
        'F': GENERATED / 'MVIMG_EXIF_F_20260815.jpg',
    }
    create_motion_photo(no_camera_exif, video_copy, outputs['C'], timestamp_us, 'xiaomi')
    create_motion_photo(image_copy, video_copy, outputs['D'], timestamp_us, 'xiaomi')
    native_without_camera, removed, remaining = _remove_camera_identity_exif(sample.read_bytes())
    outputs['F'].write_bytes(native_without_camera)
    analyses = {variant: inspect_motion_photo(path, probe['path'])
                for variant, path in outputs.items()}
    for variant, analysis in analyses.items():
        if not analysis['valid']:
            raise RuntimeError(f'Generated {variant} failed structural validation.')
    with Image.open(BytesIO(native_primary)) as native_image:
        native_exif = native_image.getexif()
        native_exif_summary = {
            'Make': native_exif.get(0x010f),
            'Model': native_exif.get(0x0110),
            'Software': native_exif.get(0x0131),
            'DateTime': native_exif.get(0x0132),
            'Orientation': native_exif.get(0x0112),
        }
    experiment = {
        'experiment': 'exif_identity',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_sample': str(sample),
        'ffprobe': probe,
        'timestamp_us': timestamp_us,
        'control_report': str(REPORTS / 'experiment_002_control.json'),
        'native_exif': native_exif_summary,
        'reverse_experiment': {
            'E': 'reuses the unchanged NATIVE CONTROL file',
            'F_removed_camera_tags': removed,
            'F_remaining_camera_tags': remaining,
        },
        'variants': {},
        'device': None,
        'remote_files': None,
        'hyperos_result': None,
    }
    for variant, output in outputs.items():
        changes = {
            'C': 'no camera identity EXIF; current ImgTor-style output',
            'D': 'copied the native Golden Sample EXIF into the experiment JPEG',
            'F': 'removed only Make, Model and Software from the native Motion Photo',
        }[variant]
        experiment['variants'][variant] = {
            'changes': changes,
            'local_file': str(output),
            'sha256': _sha256(output),
            'analysis': analyses[variant],
        }
    report_path = REPORTS / 'experiment_002_exif.json'
    report_path.write_text(json.dumps(experiment, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'report': str(report_path), 'experiment': experiment}


def prepare_jpeg_xmp(sample_path: Path) -> dict:
    """Create G/H/I while changing only XMP or JPEG encoding per variant."""
    sample = sample_path.expanduser().resolve()
    if not sample.is_file():
        raise RuntimeError(f'Golden Sample does not exist: {sample}')
    probe = ffprobe_status()
    if not probe['available']:
        raise RuntimeError('ffprobe.exe is not available.')
    for folder in (REPORTS, GENERATED, EXTRACTED):
        folder.mkdir(parents=True, exist_ok=True)
    control_report_path = REPORTS / 'experiment_002_control.json'
    try:
        control_report = json.loads(control_report_path.read_text(encoding='utf-8'))
        control_file = Path(control_report['local_file'])
        if control_report['hyperos_result'] is None:
            raise RuntimeError('NATIVE CONTROL has no recorded HyperOS result.')
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError('The NATIVE CONTROL report is unavailable.') from error
    if not control_file.is_file():
        raise RuntimeError(f'NATIVE CONTROL file is missing: {control_file}')

    native_bytes = sample.read_bytes()
    native_info = inspect_motion_photo(sample, probe['path'])
    native_xmp_values = _xmp_payloads(native_bytes)
    if not native_xmp_values:
        raise RuntimeError('Native Golden Sample has no standard XMP APP1 packet.')
    native_xmp = native_xmp_values[0]
    video_length = native_info['video_length']
    native_timestamp = native_info['xmp']['legacy'].get('MicroVideoPresentationTimestampUs', 0)
    imgtor_xmp = _xiaomi_xmp_payload(video_length, int(native_timestamp))

    image_copy = EXTRACTED / 'MVIMG_20260715_055104_primary.jpg'
    video_copy = EXTRACTED / 'MVIMG_20260715_055104_motion.mp4'
    if not image_copy.is_file() or not video_copy.is_file():
        extract_motion_photo(sample, image_copy, video_copy)
    primary = image_copy.read_bytes()
    video = video_copy.read_bytes()
    outputs = {
        'H': GENERATED / 'MVIMG_JPEG_XMP_H_20260815.jpg',
        'I': GENERATED / 'MVIMG_JPEG_XMP_I_20260815.jpg',
    }
    outputs['H'].write_bytes(_replace_standard_xmp(native_bytes, imgtor_xmp))
    regenerated = _regenerate_jpeg(primary)
    outputs['I'].write_bytes(_insert_xmp_and_video(regenerated, native_xmp, video))
    analyses = {
        'G': inspect_motion_photo(control_file, probe['path']),
        'H': inspect_motion_photo(outputs['H'], probe['path']),
        'I': inspect_motion_photo(outputs['I'], probe['path']),
    }
    for variant, analysis in analyses.items():
        if not analysis['valid']:
            raise RuntimeError(f'Generated {variant} failed structural validation.')

    native_markers = analyze_jpeg_markers(sample)
    imgtor_comparison = GENERATED / 'MVIMG_EXIF_D_20260815.jpg'
    if not imgtor_comparison.is_file():
        raise RuntimeError('The second-round ImgTor comparison file is missing.')
    imgtor_markers = analyze_jpeg_markers(imgtor_comparison)
    native_xmp_path = REPORTS / 'native_xmp.xml'
    imgtor_xmp_path = REPORTS / 'imgtor_xmp.xml'
    native_xmp_path.write_bytes(native_xmp)
    imgtor_xmp_path.write_bytes(imgtor_xmp)
    _write_diff(
        REPORTS / 'xmp_raw_diff.txt',
        native_xmp.decode('utf-8', 'replace'), imgtor_xmp.decode('utf-8', 'replace'),
        'native_xmp.xml', 'imgtor_xmp.xml')
    _write_diff(
        REPORTS / 'xmp_semantic_diff.txt',
        _normalized_xmp(native_xmp), _normalized_xmp(imgtor_xmp),
        'native_xmp.normalized.xml', 'imgtor_xmp.normalized.xml')
    _write_diff(
        REPORTS / 'jpeg_marker_diff.txt',
        json.dumps(native_markers['markers'], ensure_ascii=False, indent=2),
        json.dumps(imgtor_markers['markers'], ensure_ascii=False, indent=2),
        'native_markers.json', 'imgtor_markers.json')
    (REPORTS / 'jpeg_structure_native.json').write_text(
        json.dumps(native_markers, ensure_ascii=False, indent=2), encoding='utf-8')
    (REPORTS / 'jpeg_structure_imgtor.json').write_text(
        json.dumps(imgtor_markers, ensure_ascii=False, indent=2), encoding='utf-8')

    experiment = {
        'experiment': 'jpeg_xmp_structure',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_sample': str(sample),
        'ffprobe': probe,
        'control_report': str(control_report_path),
        'G': {'description': 'reuses the unchanged NATIVE CONTROL file',
              'local_file': str(control_file), 'analysis': analyses['G']},
        'xmp': {
            'native': _xmp_stats(native_xmp),
            'imgtor': _xmp_stats(imgtor_xmp),
            'native_file': str(native_xmp_path), 'imgtor_file': str(imgtor_xmp_path),
            'raw_diff': str(REPORTS / 'xmp_raw_diff.txt'),
            'semantic_diff': str(REPORTS / 'xmp_semantic_diff.txt'),
        },
        'jpeg_structure': {
            'native_file': str(REPORTS / 'jpeg_structure_native.json'),
            'imgtor_file': str(REPORTS / 'jpeg_structure_imgtor.json'),
            'marker_diff': str(REPORTS / 'jpeg_marker_diff.txt'),
        },
        'comparison_imgtor_file': str(imgtor_comparison),
        'variants': {},
        'device': None,
        'remote_files': None,
        'hyperos_result': None,
    }
    for variant, output in outputs.items():
        experiment['variants'][variant] = {
            'changes': {
                'H': 'native JPEG/MP4 retained; standard XMP replaced with current ImgTor Xiaomi XMP',
                'I': 'native XMP/MP4 retained; JPEG pixels re-encoded with Pillow',
            }[variant],
            'local_file': str(output), 'sha256': _sha256(output),
            'analysis': analyses[variant],
        }
    report_path = REPORTS / 'experiment_003_jpeg_xmp.json'
    report_path.write_text(json.dumps(experiment, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'report': str(report_path), 'experiment': experiment}


def prepare(sample_path: Path) -> dict:
    sample = sample_path.expanduser().resolve()
    if not sample.is_file():
        raise RuntimeError(f'Golden Sample does not exist: {sample}')
    probe = ffprobe_status()
    if not probe['available']:
        raise RuntimeError('ffprobe.exe is not available; copy it into the Motion Photo plugin directory first.')

    for folder in (REPORTS, GENERATED, EXTRACTED, ADB_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    stem = _sample_name(sample)
    image_copy = EXTRACTED / f'{stem}_primary.jpg'
    video_copy = EXTRACTED / f'{stem}_motion.mp4'
    extract_motion_photo(sample, image_copy, video_copy)
    duration = _probe_duration(video_copy, probe['path'])
    timestamp_us = round(duration * 0.5 * 1_000_000)
    if not 0 < timestamp_us < round(duration * 1_000_000):
        raise RuntimeError(f'Calculated timestamp is outside video duration: {timestamp_us}')

    outputs = {
        'A': GENERATED / f'{stem}_A.jpg',
        'B': GENERATED / f'{stem}_B.jpg',
    }
    timestamps = {'A': 0, 'B': timestamp_us}
    analyses = {}
    for variant, output in outputs.items():
        create_motion_photo(image_copy, video_copy, output,
                            presentation_timestamp_us=timestamps[variant],
                            profile='xiaomi')
        analyses[variant] = inspect_motion_photo(output, probe['path'])
        if not analyses[variant]['valid']:
            raise RuntimeError(f'Generated {variant} failed structural validation.')

    experiment = {
        'experiment': 'presentation_timestamp',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_sample': str(sample),
        'ffprobe': probe,
        'extracted': {
            'image': {'path': str(image_copy), 'sha256': _sha256(image_copy)},
            'video': {'path': str(video_copy), 'sha256': _sha256(video_copy),
                      'length': video_copy.stat().st_size, 'duration_seconds': duration},
        },
        'variants': {},
        'device': None,
        'remote_files': None,
        'hyperos_result': None,
    }
    for variant, output in outputs.items():
        experiment['variants'][variant] = {
            'changes': {'GCamera:MicroVideoPresentationTimestampUs': timestamps[variant]},
            'local_file': str(output),
            'sha256': _sha256(output),
            'analysis': analyses[variant],
        }
    report_path = REPORTS / 'experiment_001.json'
    report_path.write_text(json.dumps(experiment, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'report': str(report_path), 'experiment': experiment}


def push(report_path: Path, serial: str | None) -> dict:
    adb = find_adb()
    if not adb:
        raise RuntimeError('adb.exe was not found.')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    device, properties = _choose_device(adb, serial)
    _require_xiaomi(properties)
    remote_dir = '/sdcard/DCIM/Camera'
    pushed = {}
    for variant, data in report['variants'].items():
        local = Path(data['local_file'])
        base_name = local.name
        remote = f'{remote_dir}/{base_name}'
        exists = _run([adb, '-s', device['serial'], 'shell', 'test', '-e', remote])
        if exists.returncode == 0:
            raise RuntimeError(f'Refusing to overwrite existing remote file: {remote}')
        completed = _run([adb, '-s', device['serial'], 'push', str(local), remote], timeout=120)
        if completed.returncode:
            raise RuntimeError((completed.stderr or completed.stdout).strip() or f'adb push failed: {base_name}')
        check = _run([adb, '-s', device['serial'], 'shell', 'stat', '-c', '%s', remote])
        size = int((check.stdout or '0').strip()) if check.returncode == 0 else None
        if size != local.stat().st_size:
            raise RuntimeError(f'Remote size mismatch for {remote}: {size} != {local.stat().st_size}')
        _run([adb, '-s', device['serial'], 'shell', 'am', 'broadcast',
              '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE', '-d', f'file://{remote}'])
        pushed[variant] = {'remote_file': remote, 'size': size}
    report['device'] = properties
    report['remote_files'] = pushed
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'report': str(report_path), 'device': properties, 'remote_files': pushed}


def _remote_sha256(adb: str, serial: str, remote: str) -> str | None:
    completed = _run([adb, '-s', serial, 'shell', 'sha256sum', remote])
    if completed.returncode:
        return None
    value = (completed.stdout or '').strip().split()
    return value[0] if value else None


def push_native_control(sample_path: Path, serial: str) -> dict:
    """Push an unchanged native sample as the second-round control group."""
    adb = find_adb()
    if not adb:
        raise RuntimeError('adb.exe was not found.')
    sample = sample_path.expanduser().resolve()
    if not sample.is_file():
        raise RuntimeError(f'Golden Sample does not exist: {sample}')
    device, properties = _choose_device(adb, serial)
    _require_xiaomi(properties)
    ADB_DIR.mkdir(parents=True, exist_ok=True)
    local_copy = ADB_DIR / 'MVIMG_NATIVE_CONTROL_20260815.jpg'
    shutil.copyfile(sample, local_copy)
    local_hash = _sha256(local_copy)
    remote_dir = '/sdcard/DCIM/Camera'
    remote_name = local_copy.name
    remote = f'{remote_dir}/{remote_name}'
    for suffix in range(2, 100):
        exists = _run([adb, '-s', device['serial'], 'shell', 'test', '-e', remote])
        if exists.returncode != 0:
            break
        remote_name = f'MVIMG_NATIVE_CONTROL_20260815_{suffix}.jpg'
        remote = f'{remote_dir}/{remote_name}'
    else:
        raise RuntimeError('Could not allocate a unique native control filename.')
    completed = _run([adb, '-s', device['serial'], 'push', str(local_copy), remote], timeout=120)
    if completed.returncode:
        raise RuntimeError((completed.stderr or completed.stdout).strip() or 'adb push failed')
    size_check = _run([adb, '-s', device['serial'], 'shell', 'stat', '-c', '%s', remote])
    remote_size = int((size_check.stdout or '0').strip()) if size_check.returncode == 0 else None
    if remote_size != local_copy.stat().st_size:
        raise RuntimeError(f'Remote size mismatch: {remote_size} != {local_copy.stat().st_size}')
    remote_hash = _remote_sha256(adb, device['serial'], remote)
    _run([adb, '-s', device['serial'], 'shell', 'am', 'broadcast',
          '-a', 'android.intent.action.MEDIA_SCANNER_SCAN_FILE', '-d', f'file://{remote}'])
    report = {
        'experiment': 'native_control',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_sample': str(sample),
        'local_file': str(local_copy),
        'sha256': local_hash,
        'remote_file': remote,
        'remote_sha256': remote_hash,
        'size': local_copy.stat().st_size,
        'device': properties,
        'hyperos_result': None,
    }
    report_path = REPORTS / 'experiment_002_control.json'
    REPORTS.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'report': str(report_path), 'control': report}


def status() -> dict:
    probe = ffprobe_status()
    adb = find_adb()
    devices = list_devices(adb) if adb else []
    return {'ffprobe': probe, 'adb': adb, 'devices': devices}


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description='XAOCEN ImgTor Motion Photo compatibility lab')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    prepare_parser = sub.add_parser('prepare', help='extract a sample and create Timestamp A/B')
    prepare_parser.add_argument('--sample', type=Path, default=DEFAULT_SAMPLE)
    control_parser = sub.add_parser('control', help='push an unchanged Xiaomi sample as NATIVE CONTROL')
    control_parser.add_argument('--sample', type=Path, default=DEFAULT_SAMPLE)
    control_parser.add_argument('--serial', required=True)
    exif_parser = sub.add_parser('prepare-exif', help='create C/D/F after NATIVE CONTROL passes')
    exif_parser.add_argument('--sample', type=Path, default=DEFAULT_SAMPLE)
    jpeg_parser = sub.add_parser('prepare-jpeg-xmp', help='create G/H/I JPEG and XMP experiments')
    jpeg_parser.add_argument('--sample', type=Path, default=DEFAULT_SAMPLE)
    push_parser = sub.add_parser('push', help='push one prepared experiment to a Xiaomi device')
    push_parser.add_argument('--report', type=Path, default=REPORTS / 'experiment_001.json')
    push_parser.add_argument('--serial')
    args = parser.parse_args()
    try:
        if args.command == 'status':
            result = status()
        elif args.command == 'prepare':
            result = prepare(args.sample)
        elif args.command == 'control':
            result = push_native_control(args.sample, args.serial)
        elif args.command == 'prepare-exif':
            result = prepare_exif(args.sample)
        elif args.command == 'prepare-jpeg-xmp':
            result = prepare_jpeg_xmp(args.sample)
        else:
            result = push(args.report, args.serial)
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({'ok': True, 'data': result}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
