from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.converter.repositories import get_history_repository
from apps.converter.repositories.base import HistoryEntry, STATUS_EXPIRED, STATUS_FAILED, STATUS_PROCESSING, STATUS_SUCCESS
from apps.converter.services import conversion_service
from apps.converter.services.markitdown_service import ConversionError, MarkItDownService
from apps.core import crypto, storage
from apps.core.security import UploadValidationError, validate_upload
from apps.core.utils import is_safe_path, parse_iso, utcnow

pytestmark = pytest.mark.django_db


def _fake_user(user_id="u-1", username="alice"):
    return SimpleNamespace(id=user_id, username=username, role="user")


def _final_entry(entry_id):
    """Re-fetches from the repository — with CELERY_TASK_ALWAYS_EAGER, the
    task already ran by the time start_conversion() returns, but the
    HistoryEntry object start_conversion() returned is a stale
    "processing" snapshot from before the task updated it."""
    return get_history_repository().get(entry_id)


def test_validate_upload_rejects_disallowed_extension():
    upload = SimpleUploadedFile("malware.exe", b"binary-content", content_type="application/octet-stream")
    with pytest.raises(UploadValidationError):
        validate_upload(upload)


def test_validate_upload_accepts_allowed_extension():
    upload = SimpleUploadedFile("notes.txt", b"hello world", content_type="text/plain")
    validate_upload(upload)  # should not raise


def test_is_safe_path_rejects_traversal(tmp_path):
    base = tmp_path / "uploads"
    base.mkdir()
    assert is_safe_path(base, base / "file.txt") is True
    assert is_safe_path(base, base / ".." / ".." / "etc" / "passwd") is False


def test_start_conversion_bad_extension_fails_fast_without_queueing(isolated_storage):
    upload = SimpleUploadedFile("malware.exe", b"binary-content", content_type="application/octet-stream")
    entry = conversion_service.start_conversion(upload, _fake_user())

    # Invalid uploads never reach "processing" — no task is ever queued.
    assert entry.status == STATUS_FAILED
    assert entry.output_filename is None


def test_start_conversion_success_flow(isolated_storage, monkeypatch, settings):
    monkeypatch.setattr(
        MarkItDownService, "convert_to_markdown", lambda self, path: "# Título\n\nContenido convertido."
    )

    upload = SimpleUploadedFile("informe.txt", b"contenido original", content_type="text/plain")
    user = _fake_user()

    queued_entry = conversion_service.start_conversion(upload, user)
    assert queued_entry.status == STATUS_PROCESSING

    entry = _final_entry(queued_entry.id)
    assert entry.status == STATUS_SUCCESS
    assert entry.output_filename is not None
    assert entry.error_message is None
    assert parse_iso(entry.expires_at) == parse_iso(entry.created_at) + timedelta(
        seconds=settings.DOCUMARK_OUTPUT_TTL_SECONDS
    )

    # The original upload must be gone after conversion.
    uploads_left = list((isolated_storage / "uploads").glob("*"))
    assert uploads_left == []

    # The output is encrypted at rest — plaintext must not appear on disk.
    output_path = isolated_storage / "outputs" / entry.output_filename
    assert output_path.exists()
    assert b"Contenido convertido" not in output_path.read_bytes()

    _, text = conversion_service.get_preview(entry.id, user)
    assert "Contenido convertido" in text


def test_start_conversion_failure_flow(isolated_storage, monkeypatch):
    def _raise(self, path):
        raise ConversionError("formato corrupto")

    monkeypatch.setattr(MarkItDownService, "convert_to_markdown", _raise)

    upload = SimpleUploadedFile("informe.txt", b"contenido", content_type="text/plain")
    user = _fake_user()

    queued_entry = conversion_service.start_conversion(upload, user)
    entry = _final_entry(queued_entry.id)

    assert entry.status == STATUS_FAILED
    assert entry.output_filename is None
    assert "formato corrupto" in entry.error_message
    assert list((isolated_storage / "uploads").glob("*")) == []


def test_finalize_conversion_is_idempotent(isolated_storage, monkeypatch):
    """A Celery redelivery (CELERY_TASK_ACKS_LATE) could call
    finalize_conversion twice for the same entry. The second call must be a
    no-op — it must not reprocess or overwrite an already-finalized entry."""
    calls = []

    def _convert(self, path):
        calls.append(path)
        return "contenido"

    monkeypatch.setattr(MarkItDownService, "convert_to_markdown", _convert)

    upload = SimpleUploadedFile("informe.txt", b"contenido", content_type="text/plain")
    user = _fake_user()

    queued_entry = conversion_service.start_conversion(upload, user)
    finalized = _final_entry(queued_entry.id)
    assert finalized.status == STATUS_SUCCESS
    assert len(calls) == 1

    # Simulate a redelivered task for the same (already finalized) entry.
    conversion_service.finalize_conversion(queued_entry.id, "/nonexistent/path.txt", user.username)

    assert len(calls) == 1  # convert_to_markdown was NOT called again
    still_finalized = _final_entry(queued_entry.id)
    assert still_finalized.output_filename == finalized.output_filename


def test_get_preview_forbidden_for_other_user(isolated_storage, monkeypatch):
    monkeypatch.setattr(MarkItDownService, "convert_to_markdown", lambda self, path: "contenido")

    owner = _fake_user("u-1", "alice")
    stranger = _fake_user("u-2", "mallory")

    upload = SimpleUploadedFile("informe.txt", b"contenido", content_type="text/plain")
    queued_entry = conversion_service.start_conversion(upload, owner)

    with pytest.raises(conversion_service.HistoryForbiddenError):
        conversion_service.get_preview(queued_entry.id, stranger)


def test_get_preview_allowed_for_admin(isolated_storage, monkeypatch):
    monkeypatch.setattr(MarkItDownService, "convert_to_markdown", lambda self, path: "contenido")

    owner = _fake_user("u-1", "alice")
    admin = SimpleNamespace(id="u-admin", username="root", role="admin")

    upload = SimpleUploadedFile("informe.txt", b"contenido", content_type="text/plain")
    queued_entry = conversion_service.start_conversion(upload, owner)

    _, text = conversion_service.get_preview(queued_entry.id, admin)
    assert "contenido" in text


def test_get_preview_blocks_and_marks_expired_after_expiration(isolated_storage):
    repo = get_history_repository()
    output_filename = "expired.md.enc"
    storage.atomic_write_bytes(storage.outputs_dir() / output_filename, crypto.encrypt_bytes(b"contenido"))
    entry = HistoryEntry(
        id="expired-entry",
        user_id="u-1",
        username="alice",
        original_filename="informe.txt",
        safe_filename="informe.txt",
        output_filename=output_filename,
        file_extension=".txt",
        file_size=9,
        status=STATUS_SUCCESS,
        error_message=None,
        created_at=(utcnow() - timedelta(hours=3)).isoformat(),
        expires_at=(utcnow() - timedelta(hours=1)).isoformat(),
        downloaded_at=None,
    )
    repo.add(entry)

    with pytest.raises(conversion_service.HistoryExpiredError):
        conversion_service.get_preview(entry.id, _fake_user())

    fetched = repo.get(entry.id)
    assert fetched.status == STATUS_EXPIRED
    assert fetched.output_filename is None
    assert not (storage.outputs_dir() / output_filename).exists()
