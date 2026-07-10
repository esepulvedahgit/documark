import pytest

from apps.accounts.repositories.base import ROLE_ADMIN, ROLE_USER, User
from apps.accounts.repositories.django_user_repository import DjangoUserRepository
from apps.converter.repositories.base import HistoryEntry, STATUS_EXPIRED, STATUS_SUCCESS
from apps.converter.repositories.django_history_repository import DjangoHistoryRepository
from apps.core.utils import new_uuid, utcnow_iso

pytestmark = pytest.mark.django_db


def _make_user(username="alice", role=ROLE_USER):
    now = utcnow_iso()
    return User(
        id=new_uuid(),
        username=username,
        password_hash="not-a-real-hash",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _make_history_entry(user, status=STATUS_SUCCESS, expires_at=None):
    now = utcnow_iso()
    return HistoryEntry(
        id=new_uuid(),
        user_id=user.id,
        username=user.username,
        original_filename="doc.pdf",
        safe_filename="abc_doc.pdf",
        output_filename="abc.md.enc" if status == STATUS_SUCCESS else None,
        file_extension=".pdf",
        file_size=1234,
        status=status,
        error_message=None,
        created_at=now,
        expires_at=expires_at,
        downloaded_at=None,
    )


def test_create_and_get_user():
    repo = DjangoUserRepository()
    user = _make_user()
    repo.create(user)

    fetched = repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.username == "alice"
    assert repo.get_by_username("ALICE") is not None  # case-insensitive lookup


def test_duplicate_username_raises():
    repo = DjangoUserRepository()
    repo.create(_make_user("bob"))
    with pytest.raises(ValueError):
        repo.create(_make_user("bob"))


def test_update_user_role_and_active():
    repo = DjangoUserRepository()
    user = _make_user("carol", role=ROLE_USER)
    repo.create(user)

    user.role = ROLE_ADMIN
    user.is_active = False
    repo.update(user)

    fetched = repo.get_by_id(user.id)
    assert fetched.role == ROLE_ADMIN
    assert fetched.is_active is False


def test_update_missing_user_raises():
    repo = DjangoUserRepository()
    with pytest.raises(KeyError):
        repo.update(_make_user("ghost"))


def test_history_add_and_list_for_user():
    repo = DjangoHistoryRepository()
    user = _make_user("dave")
    entry_a = _make_history_entry(user)
    entry_b = _make_history_entry(user)
    repo.add(entry_a)
    repo.add(entry_b)

    other_user = _make_user("erin")
    repo.add(_make_history_entry(other_user))

    own = repo.list_for_user(user.id)
    assert {e.id for e in own} == {entry_a.id, entry_b.id}
    assert len(repo.list_all()) == 3


def test_history_entry_can_be_marked_expired():
    repo = DjangoHistoryRepository()
    user = _make_user("frank")
    entry = _make_history_entry(user, status=STATUS_SUCCESS, expires_at=utcnow_iso())
    repo.add(entry)

    entry.status = STATUS_EXPIRED
    entry.output_filename = None
    repo.update(entry)

    fetched = repo.get(entry.id)
    assert fetched.status == STATUS_EXPIRED
    assert fetched.output_filename is None


def test_history_entry_delete_removes_record():
    repo = DjangoHistoryRepository()
    user = _make_user("grace")
    entry = _make_history_entry(user)
    repo.add(entry)
    assert repo.get(entry.id) is not None

    repo.delete(entry.id)

    assert repo.get(entry.id) is None
    assert entry.id not in {e.id for e in repo.list_all()}


def test_history_entry_delete_is_idempotent():
    repo = DjangoHistoryRepository()
    repo.delete("does-not-exist")  # must not raise


def test_history_update_missing_entry_raises():
    repo = DjangoHistoryRepository()
    user = _make_user("henry")
    with pytest.raises(KeyError):
        repo.update(_make_history_entry(user))
