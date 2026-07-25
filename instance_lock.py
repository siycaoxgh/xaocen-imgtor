#!/usr/bin/env python3
"""Small cross-platform process lock used by the global screenshot listener."""

import os
import signal
import subprocess
import time
from pathlib import Path

LOCK_PATH = Path(__file__).resolve().parent / 'archive' / 'runtime' / '.xaocen-main.lock'


class InstanceLock:
    def __init__(self, path=LOCK_PATH):
        self.path = Path(path)
        self.handle = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        self.handle = self.path.open('r+')
        self.handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            try:
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                self.handle.close()
                self.handle = None
                return False
        else:
            import fcntl
            try:
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                self.handle.close()
                self.handle = None
                return False
        self.handle.seek(0)
        self.handle.truncate()
        self.handle.write(str(os.getpid()))
        self.handle.flush()
        return True

    def takeover_existing(self):
        """Terminate only a verified drawru-imgter main process, then retry the lock."""
        candidates = []
        try:
            self.handle = self.handle or self.path.open('r')
            self.handle.seek(0)
            content = self.handle.read().strip()
            if content.isdigit() and int(content) != os.getpid():
                candidates.append(int(content))
        except OSError:
            pass
        finally:
            if self.handle is not None and not self.handle.writable():
                self.handle.close()
                self.handle = None

        if os.name == 'nt':
            project = str(self.path.parent).replace("'", "''")
            command = (
                "Get-CimInstance Win32_Process | "
                f"Where-Object {{$_.ProcessId -ne {os.getpid()} -and $_.CommandLine -and "
                f"$_.CommandLine -like '*{project}*main.py*'}} | "
                "Select-Object -ExpandProperty ProcessId"
            )
            try:
                result = subprocess.run(
                    ['powershell', '-NoProfile', '-Command', command],
                    capture_output=True, text=True, timeout=5, check=False)
                candidates.extend(int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit())
            except (OSError, subprocess.SubprocessError, ValueError):
                pass
        else:
            proc_root = Path('/proc')
            if proc_root.exists():
                for entry in proc_root.iterdir():
                    if not entry.name.isdigit() or int(entry.name) == os.getpid():
                        continue
                    try:
                        commandline = (entry / 'cmdline').read_bytes().decode(errors='ignore').replace('\x00', ' ')
                        if str(self.path.parent) in commandline and 'main.py' in commandline:
                            candidates.append(int(entry.name))
                    except OSError:
                        pass

        for pid in dict.fromkeys(candidates):
            try:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(pid), '/T', '/F'], capture_output=True, timeout=5, check=False)
                else:
                    os.kill(pid, signal.SIGTERM)
            except (OSError, subprocess.SubprocessError):
                continue
        if candidates:
            time.sleep(0.4)
        return bool(candidates)

    def release(self):
        if self.handle is None:
            return
        try:
            if os.name == 'nt':
                import msvcrt
                self.handle.seek(0)
                msvcrt.locking(self.handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
        finally:
            self.handle.close()
            self.handle = None

    def __enter__(self):
        if not self.acquire():
            raise RuntimeError('drawru-imgter screenshot listener is already running')
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()
