"""Filesystem layout, atomic writes and cross-process locking for the
file-based storage backend.

No business data lives in a database yet; this module is the single place
that knows where things live on disk and how to mutate them safely when
several Gunicorn workers touch the same encrypted file concurrently.
"""

import contextlib
import fcntl
import os
from pathlib import Path

from django.conf import settings


def storage_root() -> Path:
    return Path(settings.STORAGE_ROOT)


def secure_dir() -> Path:
    return storage_root() / "secure"


def uploads_dir() -> Path:
    return storage_root() / "uploads"


def outputs_dir() -> Path:
    return storage_root() / "outputs"


def runtime_dir() -> Path:
    return storage_root() / "runtime"


def logs_dir() -> Path:
    return storage_root() / "logs"


def cache_dir() -> Path:
    return runtime_dir() / "cache"


def locks_dir() -> Path:
    d = runtime_dir() / "locks"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_storage_dirs() -> None:
    for path in (secure_dir(), uploads_dir(), outputs_dir(), runtime_dir(), logs_dir(), cache_dir(), locks_dir()):
        path.mkdir(parents=True, exist_ok=True)


@contextlib.contextmanager
def file_lock(name: str):
    """Cross-process exclusive lock keyed by ``name`` (e.g. "users", "history").

    Guards the read-modify-write cycle on encrypted metadata files so that
    concurrent Gunicorn workers don't clobber each other's writes.
    """
    lock_path = locks_dir() / f"{name}.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically (write to temp file + rename)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)


def read_bytes_or_none(path: Path):
    path = Path(path)
    if not path.exists():
        return None
    return path.read_bytes()
