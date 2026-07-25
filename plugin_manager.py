#!/usr/bin/env python3
"""Discovery-only plugin registry for optional drawru-imgter capabilities.

Plugins deliberately live outside the core application bundle.  This keeps a
PyInstaller one-file core small and lets optional media tooling (for example
FFmpeg) be installed, upgraded, or removed independently.
"""

import hashlib
import hmac
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


PLUGIN_API_VERSION = 1
MAX_MANIFEST_BYTES = 128 * 1024
MAX_PLUGIN_PACKAGE_BYTES = 256 * 1024 * 1024
MAX_PLUGIN_PACKAGE_FILES = 512
PLUGIN_PACKAGE_SUFFIX = '.xaocen-plugin'
_ID_PATTERN = re.compile(r'^[a-z0-9][a-z0-9._-]{1,63}$')


def _default_plugin_root():
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    elif os.name == 'posix' and os.environ.get('XDG_DATA_HOME'):
        base = Path(os.environ['XDG_DATA_HOME'])
    else:
        base = Path.home() / '.local' / 'share'
    return base / 'drawru-imgter' / 'plugins'


DEFAULT_PLUGIN_ROOT = _default_plugin_root()
# Kept as an override seam for tests and for embedders.  Normal production
# selection is resolved in plugin_root() from config.json.
PLUGIN_ROOT = DEFAULT_PLUGIN_ROOT


def plugin_root():
    """Return the configured plugin directory without importing plugin code.

    The default is per-user and therefore survives one-file PyInstaller
    extraction.  A user may explicitly choose a writable portable directory.
    """
    override = Path(PLUGIN_ROOT)
    if override != DEFAULT_PLUGIN_ROOT:
        return override
    try:
        # Lazy import prevents config_manager -> plugin_manager import cycles.
        from config_manager import load_config
        selected = str(load_config().get('plugin_directory', '') or '').strip()
        if selected:
            candidate = Path(selected).expanduser()
            if candidate.is_absolute():
                return candidate.resolve()
    except Exception:
        pass
    return DEFAULT_PLUGIN_ROOT


def ensure_plugin_root():
    root = plugin_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_package_member(name):
    """Reject absolute paths and zip-slip paths before extraction."""
    path = Path(name)
    return bool(name) and not path.is_absolute() and '..' not in path.parts and not path.drive


def _sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_plugin_package(package_path):
    """Verify a portable plugin bundle before any plugin file is extracted.

    The package is a standard ZIP with a readable ``integrity.json`` map. This
    detects corruption and accidental tampering, but is deliberately not
    presented as a publisher signature or a security sandbox.
    """
    package = Path(package_path)
    try:
        if package.suffix.lower() != PLUGIN_PACKAGE_SUFFIX or not package.is_file():
            return {'ok': False, 'error': 'plugin_package_invalid'}
        if package.stat().st_size > MAX_PLUGIN_PACKAGE_BYTES:
            return {'ok': False, 'error': 'plugin_package_too_large'}
        with zipfile.ZipFile(package) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if not members or len(members) > MAX_PLUGIN_PACKAGE_FILES:
                return {'ok': False, 'error': 'plugin_package_invalid'}
            if any(not _safe_package_member(item.filename) for item in members):
                return {'ok': False, 'error': 'plugin_package_path_invalid'}
            if sum(item.file_size for item in members) > MAX_PLUGIN_PACKAGE_BYTES:
                return {'ok': False, 'error': 'plugin_package_too_large'}
            names = {item.filename for item in members}
            if len(names) != len(members):
                return {'ok': False, 'error': 'plugin_package_integrity_invalid'}
            if {'plugin.json', 'integrity.json'} - names:
                return {'ok': False, 'error': 'plugin_package_integrity_missing'}
            integrity = json.loads(archive.read('integrity.json').decode('utf-8'))
            files = integrity.get('files') if isinstance(integrity, dict) else None
            if not isinstance(files, dict) or not files:
                return {'ok': False, 'error': 'plugin_package_integrity_invalid'}
            declared = set(files)
            payload_names = names - {'integrity.json'}
            if declared != payload_names:
                return {'ok': False, 'error': 'plugin_package_integrity_invalid'}
            for name, expected in files.items():
                if not _safe_package_member(name) or not isinstance(expected, str):
                    return {'ok': False, 'error': 'plugin_package_integrity_invalid'}
                actual = hashlib.sha256(archive.read(name)).hexdigest()
                if not hmac.compare_digest(actual, expected.lower()):
                    return {'ok': False, 'error': 'plugin_package_hash_mismatch'}
            manifest = json.loads(archive.read('plugin.json').decode('utf-8'))
            if not isinstance(manifest, dict) or not _ID_PATTERN.fullmatch(str(manifest.get('id', ''))):
                return {'ok': False, 'error': 'plugin_package_manifest_invalid'}
            return {'ok': True, 'id': manifest['id'], 'name': str(manifest.get('name', manifest['id'])),
                    'version': str(manifest.get('version', '')), 'manifest': manifest}
    except (OSError, UnicodeError, ValueError, zipfile.BadZipFile, json.JSONDecodeError):
        return {'ok': False, 'error': 'plugin_package_invalid'}


def install_plugin_package(package_path):
    """Install a verified bundle using a temporary directory and rollback copy."""
    checked = verify_plugin_package(package_path)
    if not checked.get('ok'):
        return checked
    root = ensure_plugin_root()
    identifier = checked['id']
    target = root / identifier
    temporary = Path(tempfile.mkdtemp(prefix=f'.{identifier}.install-', dir=root))
    backup = root / f'.{identifier}.previous'
    try:
        with zipfile.ZipFile(package_path) as archive:
            archive.extractall(temporary)
        # Re-check after extraction, including the manifest convention used by discovery.
        item = _read_manifest(temporary)
        if item.get('id') != identifier or item.get('status') == 'invalid':
            return {'ok': False, 'error': 'plugin_package_manifest_invalid'}
        if backup.exists():
            shutil.rmtree(backup)
        if target.exists():
            target.replace(backup)
        temporary.replace(target)
        temporary = None
        # Retain only a short-lived recoverable previous version during this install.
        if backup.exists():
            shutil.rmtree(backup)
        return {'ok': True, 'id': identifier, 'name': item.get('name', identifier),
                'version': item.get('version', '')}
    except (OSError, zipfile.BadZipFile):
        if not target.exists() and backup.exists():
            try:
                backup.replace(target)
            except OSError:
                pass
        return {'ok': False, 'error': 'plugin_package_install_failed'}
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def create_plugin_package(source_directory, output_path):
    """Create a readable integrity-checked bundle for trusted distribution."""
    source = Path(source_directory).resolve()
    output = Path(output_path).resolve()
    item = _read_manifest(source)
    if item.get('status') == 'invalid':
        raise ValueError(f"Invalid plugin source: {item.get('reason', 'manifest_invalid')}")
    payload = []
    for path in source.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and path.name != 'integrity.json':
            payload.append(path)
    if len(payload) > MAX_PLUGIN_PACKAGE_FILES:
        raise ValueError('Too many plugin files.')
    hashes = {str(path.relative_to(source)).replace('\\', '/'): _sha256_file(path) for path in payload}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in payload:
            archive.write(path, str(path.relative_to(source)).replace('\\', '/'))
        archive.writestr('integrity.json', json.dumps({'format': 1, 'files': hashes}, indent=2, sort_keys=True))
    return output


def validate_plugin_root(path):
    """Return a resolved writable plugin directory or a stable error code."""
    try:
        root = Path(path).expanduser().resolve()
        if not root.is_absolute():
            return None, 'plugin_directory_invalid'
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix='.drawru-plugin-', dir=root, delete=True):
            pass
        return root, ''
    except (OSError, RuntimeError, ValueError):
        return None, 'plugin_directory_not_writable'


def _invalid(folder, reason):
    return {
        'id': folder.name,
        'name': folder.name,
        'version': '',
        'capabilities': [],
        'status': 'invalid',
        'reason': reason,
    }


def _read_manifest(folder):
    manifest = folder / 'plugin.json'
    try:
        if not manifest.is_file() or manifest.stat().st_size > MAX_MANIFEST_BYTES:
            return _invalid(folder, 'manifest_missing_or_too_large')
        data = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _invalid(folder, 'manifest_invalid')
    if not isinstance(data, dict):
        return _invalid(folder, 'manifest_invalid')

    identifier = str(data.get('id', ''))
    if not _ID_PATTERN.fullmatch(identifier):
        return _invalid(folder, 'plugin_id_invalid')
    try:
        api_version = int(data.get('api_version', 0) or 0)
    except (TypeError, ValueError):
        return _invalid(folder, 'api_version_invalid')
    if api_version != PLUGIN_API_VERSION:
        return _invalid(folder, 'api_version_unsupported')
    name = str(data.get('name', identifier)).strip()[:80] or identifier
    version = str(data.get('version', '')).strip()[:40]
    capabilities = data.get('capabilities', [])
    if not isinstance(capabilities, list) or not all(isinstance(item, str) for item in capabilities):
        return _invalid(folder, 'capabilities_invalid')
    platforms = data.get('platforms', [])
    if not isinstance(platforms, list) or not all(isinstance(item, str) for item in platforms):
        return _invalid(folder, 'platforms_invalid')
    current_platform = 'windows' if os.name == 'nt' else ('macos' if os.uname().sysname == 'Darwin' else 'linux')
    compatible = not platforms or current_platform in platforms
    return {
        'id': identifier,
        'name': name,
        'version': version,
        'capabilities': [item[:80] for item in capabilities[:12]],
        'status': 'installed' if compatible else 'incompatible',
        'reason': '' if compatible else 'platform_unsupported',
    }


def discover_plugins():
    """Return validated manifests only; code is never imported or executed."""
    root = plugin_root()
    if not root.is_dir():
        return []
    # A user may also copy a verified package directly into the plugin folder.
    # Only packages whose target folder does not exist are auto-installed; an
    # existing installation is never silently replaced during a state refresh.
    try:
        for package in root.glob(f'*{PLUGIN_PACKAGE_SUFFIX}'):
            checked = verify_plugin_package(package)
            target = root / str(checked.get('id', '')) if checked.get('ok') else None
            if checked.get('ok') and target and not target.exists():
                install_plugin_package(package)
    except OSError:
        pass
    results = []
    try:
        folders = sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.lower())
    except OSError:
        return []
    for folder in folders[:64]:
        results.append(_read_manifest(folder))
    return results


def resolve_plugin(identifier):
    """Resolve one compatible plugin folder for explicit user-initiated work.

    This function only returns manifest data and a path.  Importing or running
    plugin code belongs to the isolated plugin host.
    """
    if not isinstance(identifier, str) or not _ID_PATTERN.fullmatch(identifier):
        return None
    root = plugin_root()
    # Prefer the conventional <plugin-id> folder, but resolve by manifest ID
    # when a user copied a bundled example whose folder uses underscores.
    # Discovery already validates each manifest; no plugin code is imported.
    candidates = [root / identifier]
    try:
        candidates.extend(
            item for item in root.iterdir()
            if item.is_dir() and item.name != identifier
        )
    except OSError:
        return None
    for folder in candidates[:65]:
        if not folder.is_dir():
            continue
        item = _read_manifest(folder)
        if item.get('id') != identifier or item.get('status') != 'installed':
            continue
        try:
            data = json.loads((folder / 'plugin.json').read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return folder.resolve(), data
    return None
