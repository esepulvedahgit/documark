"""Orchestrates the document -> Markdown conversion flow.

``start_conversion`` does the fast, synchronous part (validate, save the
upload, record a "processing" HistoryEntry) and enqueues a Celery task for
the slow part; it never blocks on the actual conversion. ``finalize_conversion``
is the task body: convert -> delete original -> encrypt result at rest ->
update history metadata (never the document content). Views call only this
module; it is the only place besides markitdown_service that touches the
filesystem for a conversion.
"""

import logging
from datetime import timedelta
from pathlib import Path

from django.conf import settings

from apps.converter.repositories import get_history_repository
from apps.converter.repositories.base import HistoryEntry, STATUS_EXPIRED, STATUS_FAILED, STATUS_PROCESSING, STATUS_SUCCESS
from apps.converter.services import cleanup_service
from apps.converter.services.markitdown_service import ConversionError, MarkItDownService
from apps.core import crypto, storage
from apps.core.security import UploadValidationError, validate_upload
from apps.core.utils import generate_safe_filename, is_safe_path, new_uuid, parse_iso, secure_filename, utcnow, utcnow_iso

logger = logging.getLogger("documark.security")


class HistoryNotFoundError(Exception):
    pass


class HistoryForbiddenError(Exception):
    pass


class HistoryExpiredError(Exception):
    pass


class SuspiciousOperationGuard(Exception):
    pass


def _extension_of(filename: str) -> str:
    return ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""


def start_conversion(uploaded_file, user) -> HistoryEntry:
    """Validates and saves the upload, records a "processing" HistoryEntry,
    and enqueues the actual conversion as a Celery task. Returns immediately
    — never blocks on the conversion itself.

    Invalid uploads (bad extension/size) still fail fast and synchronously,
    exactly like before: no entry ever reaches "processing" for those.
    """
    cleanup_service.cleanup_all()

    repo = get_history_repository()
    original_filename = uploaded_file.name or "documento"
    file_extension = _extension_of(original_filename)
    file_size = getattr(uploaded_file, "size", 0) or 0
    now = utcnow()

    try:
        validate_upload(uploaded_file)
    except UploadValidationError as exc:
        entry = HistoryEntry(
            id=new_uuid(),
            user_id=user.id,
            username=user.username,
            original_filename=secure_filename(original_filename),
            safe_filename=None,
            output_filename=None,
            file_extension=file_extension,
            file_size=file_size,
            status=STATUS_FAILED,
            error_message=str(exc.message if hasattr(exc, "message") else exc),
            created_at=now.isoformat(),
            expires_at=None,
            downloaded_at=None,
        )
        repo.add(entry)
        logger.info("conversion_failed username=%s reason=validation", user.username)
        return entry

    safe_filename = generate_safe_filename(original_filename)
    upload_path = storage.uploads_dir() / safe_filename
    if not is_safe_path(storage.uploads_dir(), upload_path):
        raise SuspiciousOperationGuard("Ruta de carga fuera del directorio permitido.")

    storage.uploads_dir().mkdir(parents=True, exist_ok=True)
    with open(upload_path, "wb") as fh:
        for chunk in uploaded_file.chunks():
            fh.write(chunk)

    entry = HistoryEntry(
        id=new_uuid(),
        user_id=user.id,
        username=user.username,
        original_filename=secure_filename(original_filename),
        safe_filename=safe_filename,
        output_filename=None,
        file_extension=file_extension,
        file_size=file_size,
        status=STATUS_PROCESSING,
        error_message=None,
        created_at=now.isoformat(),
        expires_at=None,
        downloaded_at=None,
    )
    repo.add(entry)

    from apps.converter.tasks import convert_document_task

    convert_document_task.delay(entry.id, str(upload_path), user.username)
    logger.info("conversion_queued username=%s conversion_id=%s", user.username, entry.id)
    return entry


def finalize_conversion(entry_id: str, upload_path_str: str, username: str) -> None:
    """Runs the actual conversion and updates the HistoryEntry. This is the
    Celery task body (apps/converter/tasks.py) — kept as a plain function
    here so it stays testable without Celery machinery.

    Idempotency guard: with CELERY_TASK_ACKS_LATE, a worker crash mid-task
    can cause Celery to redeliver it. If the entry is no longer "processing"
    (already finalized by a previous delivery), this is a no-op.
    """
    repo = get_history_repository()
    entry = repo.get(entry_id)
    if entry is None or entry.status != STATUS_PROCESSING:
        return

    upload_path = Path(upload_path_str)

    try:
        text = MarkItDownService().convert_to_markdown(upload_path)
    except ConversionError as exc:
        entry.status = STATUS_FAILED
        entry.error_message = str(exc)
        repo.update(entry)
        logger.info("conversion_failed username=%s reason=markitdown", username)
        return
    finally:
        upload_path.unlink(missing_ok=True)

    output_filename = f"{new_uuid()}.md.enc"
    output_path = storage.outputs_dir() / output_filename
    token = crypto.encrypt_bytes(text.encode("utf-8"))
    storage.atomic_write_bytes(output_path, token)

    try:
        created_at = parse_iso(entry.created_at)
    except (ValueError, TypeError):
        created_at = utcnow()
    expires_at = created_at + timedelta(seconds=settings.DOCUMARK_OUTPUT_TTL_SECONDS)
    entry.status = STATUS_SUCCESS
    entry.output_filename = output_filename
    entry.expires_at = expires_at.isoformat()
    repo.update(entry)
    logger.info("conversion_success username=%s", username)


def _authorize(entry: HistoryEntry, user) -> None:
    is_owner = entry.user_id == user.id
    is_admin = getattr(user, "role", None) == "admin"
    if not (is_owner or is_admin):
        raise HistoryForbiddenError("No tienes permiso para acceder a esta conversión.")


def _get_entry_or_404(entry_id: str) -> HistoryEntry:
    entry = get_history_repository().get(entry_id)
    if entry is None:
        raise HistoryNotFoundError("Conversión no encontrada.")
    return entry


def get_entry(entry_id: str, user) -> HistoryEntry:
    """Fetches a HistoryEntry, enforcing ownership (or admin). Raises
    HistoryNotFoundError / HistoryForbiddenError as appropriate. Used both
    for the status-polling endpoint and by get_preview/get_download."""
    entry = _get_entry_or_404(entry_id)
    _authorize(entry, user)
    return entry


def get_preview(entry_id: str, user) -> tuple:
    """Returns (entry, markdown_text). Raises HistoryNotFoundError /
    HistoryForbiddenError / HistoryExpiredError as appropriate."""
    entry = get_entry(entry_id, user)

    if entry.status != STATUS_SUCCESS or not entry.output_filename:
        raise HistoryExpiredError("Este resultado ya no está disponible (expiró o falló).")

    try:
        is_expired = bool(entry.expires_at and parse_iso(entry.expires_at) <= utcnow())
    except (ValueError, TypeError):
        is_expired = False

    if is_expired:
        (storage.outputs_dir() / entry.output_filename).unlink(missing_ok=True)
        entry.status = STATUS_EXPIRED
        entry.output_filename = None
        get_history_repository().update(entry)
        raise HistoryExpiredError("Este resultado ya no está disponible (expiró o falló).")

    output_path = storage.outputs_dir() / entry.output_filename
    if not output_path.exists():
        raise HistoryExpiredError("Este resultado ya no está disponible.")

    text = crypto.decrypt_file_to_bytes(output_path).decode("utf-8")
    return entry, text


def get_download(entry_id: str, user) -> tuple:
    """Returns (download_filename, content_bytes). Marks downloaded_at.
    Raises the same exceptions as get_preview."""
    entry, text = get_preview(entry_id, user)

    entry.downloaded_at = utcnow_iso()
    get_history_repository().update(entry)
    logger.info("download username=%s conversion_id=%s", user.username, entry.id)

    base_name = secure_filename(Path(entry.original_filename).stem) or "documento"
    download_filename = f"{base_name}.md"
    return download_filename, text.encode("utf-8")
