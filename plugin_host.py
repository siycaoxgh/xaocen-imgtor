"""Restricted subprocess host for user-initiated optional plugins.

The main application never imports plugin modules.  A validated plugin can
only be started through this host, using a small JSON request/response protocol
over standard input/output.
"""

import json
import subprocess
import sys
from pathlib import Path

from plugin_manager import resolve_plugin


PLUGIN_PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024


def _failure(code, detail=''):
    result = {'ok': False, 'error': code}
    if detail:
        result['detail'] = str(detail)[:500]
    return result


def _entrypoint(plugin_dir, manifest):
    entry = manifest.get('entrypoint')
    if not isinstance(entry, str) or not entry or Path(entry).is_absolute():
        return None
    candidate = (plugin_dir / entry).resolve()
    try:
        candidate.relative_to(plugin_dir)
    except ValueError:
        return None
    return candidate if candidate.is_file() and candidate.suffix.lower() == '.py' else None


def run_plugin(plugin_id, command, payload=None, timeout=30):
    """Run a declared plugin command in an isolated Python subprocess.

    The caller must supply an exact plugin id and a command named in the
    manifest.  Plugin stdout must be one small JSON object.  This is a trust
    boundary, not a sandbox: users should install plugins only from sources
    they trust.
    """
    resolved = resolve_plugin(plugin_id)
    if not resolved:
        return _failure('plugin_unavailable')
    plugin_dir, manifest = resolved
    commands = manifest.get('commands', [])
    if not isinstance(command, str) or not isinstance(commands, list) or command not in commands:
        return _failure('plugin_command_unsupported')
    entry = _entrypoint(plugin_dir, manifest)
    if entry is None:
        return _failure('plugin_entrypoint_invalid')
    request = {'protocol': PLUGIN_PROTOCOL_VERSION, 'command': command,
               'payload': payload if isinstance(payload, dict) else {}}
    encoded = json.dumps(request, ensure_ascii=False).encode('utf-8')
    if len(encoded) > MAX_REQUEST_BYTES:
        return _failure('plugin_request_too_large')
    try:
        completed = subprocess.run(
            [sys.executable, '-I', str(entry), '--request'], input=encoded,
            capture_output=True, cwd=str(plugin_dir), timeout=max(1, min(int(timeout), 120)),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _failure('plugin_timeout')
    except OSError as error:
        return _failure('plugin_start_failed', error)
    if len(completed.stdout) > MAX_RESPONSE_BYTES:
        return _failure('plugin_response_too_large')
    try:
        response = json.loads(completed.stdout.decode('utf-8'))
    except (UnicodeError, json.JSONDecodeError):
        return _failure('plugin_invalid_response', completed.stderr.decode('utf-8', 'replace'))
    if not isinstance(response, dict) or not isinstance(response.get('ok'), bool):
        return _failure('plugin_invalid_response')
    if completed.returncode and response.get('ok'):
        return _failure('plugin_failed', completed.stderr.decode('utf-8', 'replace'))
    return response
