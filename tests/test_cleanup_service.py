from datetime import timedelta

from apps.converter.repositories import get_history_repository
from apps.converter.repositories.base import HistoryEntry, STATUS_EXPIRED, STATUS_FAILED, STATUS_PROCESSING, STATUS_SUCCESS
from apps.converter.services import cleanup_service
from apps.core import crypto, storage
from apps.core.utils import new_uuid, utcnow


def _make_entry(status, created_at, expires_at=None, output_filename=None):
    return HistoryEntry(
        id=new_uuid(),
        user_id="u-1",
        username="alice",
        original_filename="doc.pdf",
        safe_filename="abc_doc.pdf",
        output_filename=output_filename,
        file_extension=".pdf",
        file_size=1234,
        status=status,
        error_message=None,
        created_at=created_at.isoformat(),
        expires_at=expires_at.isoformat() if expires_at else None,
        downloaded_at=None,
    )


def test_cleanup_expired_outputs_deletes_file_and_marks_expired(isolated_storage):
    repo = get_history_repository()
    now = utcnow()

    output_filename = f"{new_uuid()}.md.enc"
    storage.atomic_write_bytes(storage.outputs_dir() / output_filename, crypto.encrypt_bytes(b"contenido"))

    entry = _make_entry(
        STATUS_SUCCESS,
        created_at=now - timedelta(hours=3),
        expires_at=now - timedelta(hours=1),  # already past its TTL
        output_filename=output_filename,
    )
    repo.add(entry)

    expired_count = cleanup_service.cleanup_expired_outputs()

    assert expired_count == 1
    fetched = repo.get(entry.id)
    assert fetched.status == STATUS_EXPIRED
    assert fetched.output_filename is None
    assert not (storage.outputs_dir() / output_filename).exists()


def test_cleanup_expired_outputs_leaves_fresh_entries_alone(isolated_storage):
    repo = get_history_repository()
    now = utcnow()

    entry = _make_entry(STATUS_SUCCESS, created_at=now, expires_at=now + timedelta(hours=1))
    repo.add(entry)

    assert cleanup_service.cleanup_expired_outputs() == 0
    assert repo.get(entry.id).status == STATUS_SUCCESS


def test_cleanup_stale_processing_marks_stuck_entries_failed(isolated_storage, settings):
    settings.DOCUMARK_CONVERSION_TIMEOUT_SECONDS = 10
    repo = get_history_repository()
    now = utcnow()

    stuck = _make_entry(STATUS_PROCESSING, created_at=now - timedelta(minutes=10))
    fresh = _make_entry(STATUS_PROCESSING, created_at=now)
    repo.add(stuck)
    repo.add(fresh)

    marked = cleanup_service.cleanup_stale_processing()

    assert marked == 1
    assert repo.get(stuck.id).status == STATUS_FAILED
    assert repo.get(fresh.id).status == STATUS_PROCESSING


def test_cleanup_old_history_entries_purges_regardless_of_status(isolated_storage, settings):
    settings.DOCUMARK_HISTORY_RETENTION_SECONDS = 3600  # 1 hour
    repo = get_history_repository()
    now = utcnow()

    old_entry = _make_entry(STATUS_EXPIRED, created_at=now - timedelta(hours=25))
    recent_entry = _make_entry(STATUS_SUCCESS, created_at=now - timedelta(minutes=5))
    repo.add(old_entry)
    repo.add(recent_entry)

    removed = cleanup_service.cleanup_old_history_entries()

    assert removed == 1
    assert repo.get(old_entry.id) is None
    assert repo.get(recent_entry.id) is not None


def test_cleanup_old_history_entries_deletes_lingering_output_file(isolated_storage, settings):
    settings.DOCUMARK_HISTORY_RETENTION_SECONDS = 3600
    repo = get_history_repository()
    now = utcnow()

    output_filename = f"{new_uuid()}.md.enc"
    storage.atomic_write_bytes(storage.outputs_dir() / output_filename, crypto.encrypt_bytes(b"contenido"))

    entry = _make_entry(STATUS_SUCCESS, created_at=now - timedelta(hours=25), output_filename=output_filename)
    repo.add(entry)

    removed = cleanup_service.cleanup_old_history_entries()

    assert removed == 1
    assert repo.get(entry.id) is None
    assert not (storage.outputs_dir() / output_filename).exists()
