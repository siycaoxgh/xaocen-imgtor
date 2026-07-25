#!/usr/bin/env python3
"""Windows gdigrab MP4 recording plugin that keeps FFmpeg external to core."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path


MAX_RECORD_SECONDS = 120
MAX_CLIP_SECONDS = 15
MAX_THUMBNAILS = 4
MAX_THUMBNAIL_BYTES = 48 * 1024


def find_ffmpeg() -> Path | None:
    """Use only a binary shipped inside this plugin folder."""
    base = Path(__file__).resolve().parent
    names = ('ffmpeg.exe', 'ffmpeg') if os.name == 'nt' else ('ffmpeg',)
    for relative in ('ffmpeg/bin', 'bin', '.'):
        for name in names:
            candidate = base / relative / name
            if candidate.is_file():
                return candidate
    return None


def find_ffprobe() -> Path | None:
    """Locate the optional probe binary packaged beside FFmpeg."""
    binary = find_ffmpeg()
    if not binary:
        return None
    names = ('ffprobe.exe', 'ffprobe') if os.name == 'nt' else ('ffprobe',)
    for name in names:
        candidate = binary.with_name(name)
        if candidate.is_file():
            return candidate
    return None


def _input_mp4(payload: dict) -> Path:
    path = Path(str(payload['input_path'])).expanduser().resolve()
    if path.suffix.lower() != '.mp4' or not path.is_file():
        raise ValueError('motion_video_invalid')
    return path


def probe(payload: dict) -> dict:
    """Read MP4 duration without loading video frames into the application."""
    try:
        source = _input_mp4(payload)
    except (KeyError, TypeError, ValueError) as error:
        return {'ok': False, 'error': 'probe_payload_invalid', 'detail': str(error)}
    binary = find_ffmpeg()
    if not binary:
        return {'ok': False, 'error': 'ffmpeg_missing'}
    probe_binary = find_ffprobe()
    try:
        if probe_binary:
            completed = subprocess.run(
                [str(probe_binary), '-v', 'error', '-show_entries', 'format=duration',
                 '-of', 'json', str(source)], capture_output=True, timeout=20, check=False)
            data = json.loads(completed.stdout.decode('utf-8', 'replace')) if not completed.returncode else {}
            duration = float(data.get('format', {}).get('duration', 0))
        else:
            completed = subprocess.run([str(binary), '-hide_banner', '-i', str(source)],
                                       capture_output=True, timeout=20, check=False)
            match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)',
                              completed.stderr.decode('utf-8', 'replace'))
            duration = (int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))) if match else 0
    except (OSError, subprocess.TimeoutExpired, ValueError, json.JSONDecodeError) as error:
        return {'ok': False, 'error': 'probe_failed', 'detail': str(error)}
    if duration <= 0:
        return {'ok': False, 'error': 'probe_failed', 'detail': 'MP4 duration is unavailable.'}
    return {'ok': True, 'data': {'duration_seconds': round(duration, 3)}}


def thumbnails(payload: dict) -> dict:
    """Return at most four small JPEG timeline thumbnails as data URLs."""
    try:
        source = _input_mp4(payload)
        timestamps = [max(0.0, float(value)) for value in payload.get('timestamps', [])][:MAX_THUMBNAILS]
    except (KeyError, TypeError, ValueError) as error:
        return {'ok': False, 'error': 'thumbnail_payload_invalid', 'detail': str(error)}
    binary = find_ffmpeg()
    if not binary:
        return {'ok': False, 'error': 'ffmpeg_missing'}
    items = []
    for timestamp in timestamps:
        try:
            completed = subprocess.run(
                [str(binary), '-v', 'error', '-ss', f'{timestamp:.3f}', '-i', str(source),
                 '-frames:v', '1', '-vf', 'scale=200:-2', '-q:v', '8', '-f', 'image2pipe',
                 '-vcodec', 'mjpeg', 'pipe:1'], capture_output=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired):
            continue
        image = completed.stdout
        if completed.returncode or not image or len(image) > MAX_THUMBNAIL_BYTES:
            continue
        items.append({'timestamp': round(timestamp, 2),
                      'data_url': 'data:image/jpeg;base64,' + base64.b64encode(image).decode('ascii')})
    return {'ok': True, 'data': {'thumbnails': items}}


def clip(payload: dict) -> dict:
    """Precisely re-encode a short MP4 segment for sharing compatibility."""
    try:
        source = _input_mp4(payload)
        output = Path(str(payload['output_path'])).expanduser().resolve()
        start = max(0.0, float(payload.get('start_seconds', 0)))
        duration = float(payload['duration_seconds'])
        ensure_audio = bool(payload.get('ensure_audio', False))
    except (KeyError, TypeError, ValueError) as error:
        return {'ok': False, 'error': 'clip_payload_invalid', 'detail': str(error)}
    if not 0 < duration <= MAX_CLIP_SECONDS:
        return {'ok': False, 'error': 'clip_duration_invalid'}
    binary = find_ffmpeg()
    if not binary:
        return {'ok': False, 'error': 'ffmpeg_missing'}
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        command = [str(binary), '-y', '-ss', f'{start:.3f}', '-i', str(source)]
        if ensure_audio:
            # Xiaomi/WeChat/Douyin reference Motion Photos all contain mp4a.
            # Generate silence locally; no microphone capture or data access.
            command += ['-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100',
                        '-t', f'{duration:.3f}', '-map', '0:v:0', '-map', '1:a:0', '-shortest']
        else:
            command += ['-t', f'{duration:.3f}', '-map', '0:v:0', '-map', '0:a?']
        command += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                    '-movflags', '+faststart', str(output)]
        completed = subprocess.run(command, capture_output=True, timeout=duration + 60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'ok': False, 'error': 'clip_failed', 'detail': str(error)}
    if completed.returncode or not output.is_file() or not output.stat().st_size:
        return {'ok': False, 'error': 'clip_failed',
                'detail': completed.stderr.decode('utf-8', 'replace')[-500:]}
    return {'ok': True, 'data': {'output_path': str(output), 'start_seconds': start,
                                 'duration_seconds': duration}}


def check() -> dict:
    binary = find_ffmpeg()
    if os.name != 'nt':
        return {'ok': True, 'data': {'ready': False, 'reason': 'windows_only'}}
    if not binary:
        return {'ok': True, 'data': {'ready': False, 'reason': 'ffmpeg_missing'}}
    try:
        completed = subprocess.run([str(binary), '-version'], capture_output=True,
                                   timeout=10, check=False)
        ready = completed.returncode == 0
        return {'ok': True, 'data': {
            'ready': ready, 'reason': '' if ready else 'ffmpeg_unusable',
            'ffmpeg_path': str(binary),
            'version': completed.stdout.decode('utf-8', 'replace').splitlines()[0][:180],
        }}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'ok': True, 'data': {'ready': False, 'reason': 'ffmpeg_unusable', 'detail': str(error)}}


def record(payload: dict) -> dict:
    status = check()
    if not status['data']['ready']:
        return {'ok': False, 'error': status['data']['reason']}
    try:
        x, y = int(payload['x']), int(payload['y'])
        width, height = int(payload['width']), int(payload['height'])
        fps = max(1, min(60, int(payload.get('fps', 30))))
        seconds = max(1, min(MAX_RECORD_SECONDS, int(payload.get('duration_seconds', 15))))
        output = Path(payload['output_path']).expanduser().resolve()
    except (KeyError, TypeError, ValueError):
        return {'ok': False, 'error': 'record_payload_invalid'}
    if width < 2 or height < 2:
        return {'ok': False, 'error': 'record_region_invalid'}
    output.parent.mkdir(parents=True, exist_ok=True)
    binary = find_ffmpeg()
    command = [
        str(binary), '-y', '-f', 'gdigrab', '-framerate', str(fps),
        '-offset_x', str(x), '-offset_y', str(y), '-video_size', f'{width}x{height}',
        '-i', 'desktop', '-t', str(seconds), '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', str(output),
    ]
    try:
        completed = subprocess.run(command, capture_output=True,
                                   timeout=seconds + 30, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'ok': False, 'error': 'record_failed', 'detail': str(error)}
    if completed.returncode or not output.is_file() or not output.stat().st_size:
        return {'ok': False, 'error': 'record_failed',
                'detail': completed.stderr.decode('utf-8', 'replace')[-500:]}
    return {'ok': True, 'data': {'output_path': str(output), 'duration_seconds': seconds}}


def process_request(request: dict) -> dict:
    if not isinstance(request, dict) or request.get('protocol') != 1:
        return {'ok': False, 'error': 'protocol_unsupported'}
    payload = request.get('payload')
    if not isinstance(payload, dict):
        return {'ok': False, 'error': 'payload_invalid'}
    if request.get('command') == 'check':
        return check()
    if request.get('command') == 'record':
        return record(payload)
    if request.get('command') == 'probe':
        return probe(payload)
    if request.get('command') == 'thumbnails':
        return thumbnails(payload)
    if request.get('command') == 'clip':
        return clip(payload)
    return {'ok': False, 'error': 'command_unsupported'}


if __name__ == '__main__':
    try:
        request = json.loads(sys.stdin.buffer.read().decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError):
        print(json.dumps({'ok': False, 'error': 'request_invalid'}))
        raise SystemExit(2)
    response = process_request(request)
    print(json.dumps(response, ensure_ascii=False))
    raise SystemExit(0 if response.get('ok') else 2)
