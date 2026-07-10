"""Small standalone helpers: safe filenames, path-traversal guards, ids and
timestamps.

``secure_filename``/``generate_safe_filename``/``is_safe_path`` are a
Django-native port of the equivalent helpers from the original Flask MVP
(``app/utils/files.py``), which relied on ``werkzeug.utils.secure_filename``.
"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

_UNSAFE_CHARS_RE = re.compile(r"[^A-Za-z0-9._-]+")
_DOT_RUN_RE = re.compile(r"\.{2,}")


def secure_filename(filename: str) -> str:
    """Strip directory components and unsafe characters from a filename."""
    filename = (filename or "").strip().replace("\\", "/")
    filename = filename.rsplit("/", 1)[-1]
    filename = _UNSAFE_CHARS_RE.sub("_", filename)
    filename = _DOT_RUN_RE.sub(".", filename).strip("._")
    return filename or "file"


def generate_safe_filename(original_name: str) -> str:
    """Return a collision-free, path-traversal-safe filename derived from
    ``original_name``: ``<uuid-hex>_<sanitized-original-name>``.
    """
    return f"{uuid.uuid4().hex}_{secure_filename(original_name)}"


def is_safe_path(base_dir: Path, target: Path) -> bool:
    """Return True if ``target`` resolves to a path inside ``base_dir``."""
    base_dir = Path(base_dir).resolve()
    try:
        target_resolved = Path(target).resolve()
    except (OSError, RuntimeError):
        return False
    return target_resolved == base_dir or base_dir in target_resolved.parents


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().isoformat()


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
