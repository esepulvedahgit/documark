"""Deletes stale temporary files, expires old conversion outputs, rescues
orphaned "processing" entries, and purges history records past their
retention window.

Runs before every conversion (conversion_service.start_conversion) and
periodically via Celery Beat (apps/converter/tasks.cleanup_expired_task,
see CELERY_BEAT_SCHEDULE) — also exposed as the `cleanup_expired`
management command for manual/cron use.

Two independent, deliberately different lifetimes:
- DOCUMARK_OUTPUT_TTL_SECONDS: how long the converted .md file stays
  downloadable (cleanup_expired_outputs) — after this, only the file is
  deleted; the history entry stays, marked "expired".
- DOCUMARK_HISTORY_RETENTION_SECONDS: how long the history *record itself*
  (metadata only — filename, status, timestamps) is kept at all
  (cleanup_old_history_entries) — after this, the entry is removed
  entirely, regardless of status.
"""

import logging
import time

from django.conf import settings

from apps.converter.repositories import get_history_repository
from apps.converter.repositories.base import STATUS_EXPIRED, STATUS_FAILED, STATUS_PROCESSING, STATUS_SUCCESS
from apps.core import storage
from apps.core.utils import parse_iso, utcnow, utcnow_iso

logger = logging.getLogger("documark.security")

# Uploads are deleted right after conversion; anything older than this that
# still lingers (e.g. after a crash mid-conversion) is considered garbage.
_STALE_UPLOAD_SECONDS = 3600

# Grace period on top of the conversion timeout before a stuck "processing"
# entry is considered orphaned (e.g. a Celery worker died without acking
# and without redelivery ever completing) rather than just still running.
_STALE_PROCESSING_GRACE_SECONDS = 60


def cleanup_stale_uploads() -> int:
    removed = 0
    cutoff = time.time() - _STALE_UPLOAD_SECONDS
    for path in storage.uploads_dir().glob("*"):
        if path.is_file() and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
            removed += 1
    if removed:
        logger.info("cleanup_stale_uploads removed=%d", removed)
    return removed


def cleanup_expired_outputs() -> int:
    repo = get_history_repository()
    now = utcnow()
    expired_count = 0

    for entry in repo.list_all():
        if entry.status != STATUS_SUCCESS or not entry.expires_at:
            continue
        try:
            expires_at = parse_iso(entry.expires_at)
        except (ValueError, TypeError):
            continue
        if expires_at > now:
            continue

        if entry.output_filename:
            output_path = storage.outputs_dir() / entry.output_filename
            output_path.unlink(missing_ok=True)

        entry.status = STATUS_EXPIRED
        entry.output_filename = None
        repo.update(entry)
        expired_count += 1

    if expired_count:
        logger.info("cleanup_expired_outputs expired=%d", expired_count)
    return expired_count


def cleanup_stale_processing() -> int:
    """Marks "processing" entries that have been stuck far longer than the
    conversion timeout as failed. Guards against a Celery worker dying
    without the task ever being redelivered/finalized, so the user never
    sees an infinite "processing" state."""
    repo = get_history_repository()
    now = utcnow()
    cutoff_seconds = settings.DOCUMARK_CONVERSION_TIMEOUT_SECONDS + _STALE_PROCESSING_GRACE_SECONDS
    stuck_count = 0

    for entry in repo.list_all():
        if entry.status != STATUS_PROCESSING:
            continue
        try:
            created_at = parse_iso(entry.created_at)
        except (ValueError, TypeError):
            continue
        if (now - created_at).total_seconds() <= cutoff_seconds:
            continue

        entry.status = STATUS_FAILED
        entry.error_message = "La conversión no terminó (proceso interrumpido). Vuelve a intentarlo."
        repo.update(entry)
        stuck_count += 1

    if stuck_count:
        logger.info("cleanup_stale_processing marked_failed=%d", stuck_count)
    return stuck_count


def cleanup_old_history_entries() -> int:
    """Purges history records (any status) older than
    DOCUMARK_HISTORY_RETENTION_SECONDS. Also deletes the underlying output
    file if one still somehow exists (belt-and-suspenders — by this point
    cleanup_expired_outputs should already have removed it)."""
    repo = get_history_repository()
    now = utcnow()
    cutoff_seconds = settings.DOCUMARK_HISTORY_RETENTION_SECONDS
    removed_count = 0

    for entry in repo.list_all():
        try:
            created_at = parse_iso(entry.created_at)
        except (ValueError, TypeError):
            continue
        if (now - created_at).total_seconds() <= cutoff_seconds:
            continue

        if entry.output_filename:
            (storage.outputs_dir() / entry.output_filename).unlink(missing_ok=True)

        repo.delete(entry.id)
        removed_count += 1

    if removed_count:
        logger.info("cleanup_old_history_entries removed=%d", removed_count)
    return removed_count


def cleanup_all() -> dict:
    storage.ensure_storage_dirs()
    removed_uploads = cleanup_stale_uploads()
    expired_outputs = cleanup_expired_outputs()
    stale_processing = cleanup_stale_processing()
    removed_history = cleanup_old_history_entries()
    return {
        "removed_uploads": removed_uploads,
        "expired_outputs": expired_outputs,
        "stale_processing": stale_processing,
        "removed_history": removed_history,
        "ran_at": utcnow_iso(),
    }
