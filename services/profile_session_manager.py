"""Cross-process ownership for GPM profile sessions.

Invariant: one Facebook automation process may own a GPM profile at a time.
The OS-level lock is released automatically if the worker process crashes.
"""
from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from threading import RLock
from urllib.parse import urlparse

from paths import DATA_DIR

LOCK_DIR = DATA_DIR / "profile_locks"
LOCK_DIR.mkdir(parents=True, exist_ok=True)

class ProfileLeaseError(RuntimeError):
    pass

_registry_lock = RLock()
_active_leases: dict[str, "ProfileLease"] = {}
_runtime: dict[str, dict] = {}
def _safe_id(profile_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(profile_id))


def _endpoint_open(endpoint: str) -> bool:
    if not endpoint:
        return False
    parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if not port:
        return False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(0.4)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()

def _try_lock(handle) -> bool:
    if os.name == "nt":
        import msvcrt
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False
    import fcntl
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
class ProfileLease:
    def __init__(self, profile_id: str, timeout: float = 20.0):
        self.profile_id = str(profile_id)
        self.timeout = timeout
        self.path = LOCK_DIR / f"{_safe_id(profile_id)}.lock"
        self.handle = None

    def acquire(self) -> "ProfileLease":
        deadline = time.monotonic() + self.timeout
        self.path.parent.mkdir(parents=True, exist_ok=True)
        while time.monotonic() < deadline:
            handle = open(self.path, "a+b")
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            if _try_lock(handle):
                handle.seek(0)
                previous = handle.read().decode("utf-8", errors="ignore")
                previous_endpoint = ""
                for line in previous.splitlines():
                    if line.startswith("endpoint="):
                        previous_endpoint = line.split("=", 1)[1].strip()
                        break
                if previous_endpoint and _endpoint_open(previous_endpoint):
                    _unlock(handle)
                    handle.close()
                    raise ProfileLeaseError(
                        f"Profile {self.profile_id} still has a live browser endpoint: {previous_endpoint}"
                    )
                self.handle = handle
                handle.seek(0)
                handle.truncate()
                meta = f"pid={os.getpid()} profile={self.profile_id} acquired={time.time()}\nendpoint=\n"
                handle.write(meta.encode("utf-8"))
                handle.flush()
                return self
            handle.close()
            time.sleep(0.25)
        raise ProfileLeaseError(f"Profile {self.profile_id} is already owned by another automation process.")
    def release(self) -> None:
        if not self.handle:
            return
        try:
            _unlock(self.handle)
        finally:
            try:
                self.handle.close()
            finally:
                self.handle = None


def acquire_profile(profile_id: str, timeout: float = 20.0) -> ProfileLease:
    key = str(profile_id)
    with _registry_lock:
        existing = _active_leases.get(key)
        if existing and existing.handle:
            raise ProfileLeaseError(f"Profile {key} is already leased in this process.")
        lease = ProfileLease(key, timeout=timeout).acquire()
        _active_leases[key] = lease
        _runtime[key] = {"profile_id": key, "pid": os.getpid(), "acquired_at": time.time()}
        return lease


def attach_runtime(profile_id: str, **metadata) -> None:
    key = str(profile_id)
    with _registry_lock:
        _runtime.setdefault(key, {}).update(metadata)
        lease = _active_leases.get(key)
        endpoint = str(metadata.get("cdp_endpoint") or "")
        if lease and lease.handle and endpoint:
            current = _runtime.get(key, {})
            lease.handle.seek(0)
            lease.handle.truncate()
            meta = (
                f"pid={os.getpid()} profile={key} acquired={current.get('acquired_at', time.time())}\n"
                f"endpoint={endpoint}\n"
            )
            lease.handle.write(meta.encode("utf-8"))
            lease.handle.flush()


def runtime_snapshot(profile_id: str | None = None):
    with _registry_lock:
        if profile_id is not None:
            return dict(_runtime.get(str(profile_id), {}))
        return {k: dict(v) for k, v in _runtime.items()}
def release_profile(profile_id: str) -> None:
    key = str(profile_id)
    with _registry_lock:
        lease = _active_leases.pop(key, None)
        _runtime.pop(key, None)
    if lease:
        lease.release()


def wait_endpoint_closed(endpoint: str, timeout: float = 15.0) -> bool:
    """Return True once a CDP host:port is no longer accepting TCP connections."""
    if not endpoint:
        return True
    parsed = urlparse(endpoint if "://" in endpoint else f"http://{endpoint}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port
    if not port:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            if sock.connect_ex((host, port)) != 0:
                return True
        finally:
            sock.close()
        time.sleep(0.4)
    return False
