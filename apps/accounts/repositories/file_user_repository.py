"""File-based implementation of BaseUserRepository.

Users are stored as one Fernet-encrypted JSON blob at
``storage/secure/users.enc`` — a dict keyed by user id. All reads/writes go
through ``apps.core.storage.file_lock`` so concurrent Gunicorn workers
never interleave a read-modify-write cycle.
"""

from typing import List, Optional

from apps.accounts.repositories.base import BaseUserRepository, User
from apps.core import crypto, storage

_LOCK_NAME = "users"
_FILENAME = "users.enc"


class FileUserRepository(BaseUserRepository):
    def _path(self):
        return storage.secure_dir() / _FILENAME

    def _load(self) -> dict:
        raw = storage.read_bytes_or_none(self._path())
        if raw is None:
            return {}
        return crypto.decrypt_json(raw)

    def _save(self, data: dict) -> None:
        token = crypto.encrypt_json(data)
        storage.atomic_write_bytes(self._path(), token)

    def get_by_id(self, user_id: str) -> Optional[User]:
        data = self._load()
        record = data.get(user_id)
        return User.from_dict(record) if record else None

    def get_by_username(self, username: str) -> Optional[User]:
        username = (username or "").strip().lower()
        data = self._load()
        for record in data.values():
            if record["username"].strip().lower() == username:
                return User.from_dict(record)
        return None

    def list_all(self) -> List[User]:
        data = self._load()
        users = [User.from_dict(record) for record in data.values()]
        return sorted(users, key=lambda u: u.created_at)

    def create(self, user: User) -> User:
        with storage.file_lock(_LOCK_NAME):
            data = self._load()
            if any(r["username"].strip().lower() == user.username.strip().lower() for r in data.values()):
                raise ValueError(f"El usuario '{user.username}' ya existe.")
            data[user.id] = user.to_dict()
            self._save(data)
            return user

    def update(self, user: User) -> User:
        with storage.file_lock(_LOCK_NAME):
            data = self._load()
            if user.id not in data:
                raise KeyError(f"Usuario '{user.id}' no encontrado.")
            data[user.id] = user.to_dict()
            self._save(data)
            return user
