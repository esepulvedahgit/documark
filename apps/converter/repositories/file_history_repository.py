"""File-based implementation of BaseHistoryRepository.

History entries live as one Fernet-encrypted JSON blob at
``storage/secure/history.enc`` — a dict keyed by entry id. Reads/writes go
through ``apps.core.storage.file_lock`` for safe concurrent access.
"""

from typing import List, Optional

from apps.converter.repositories.base import BaseHistoryRepository, HistoryEntry
from apps.core import crypto, storage

_LOCK_NAME = "history"
_FILENAME = "history.enc"


class FileHistoryRepository(BaseHistoryRepository):
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

    def add(self, entry: HistoryEntry) -> HistoryEntry:
        with storage.file_lock(_LOCK_NAME):
            data = self._load()
            data[entry.id] = entry.to_dict()
            self._save(data)
            return entry

    def get(self, entry_id: str) -> Optional[HistoryEntry]:
        data = self._load()
        record = data.get(entry_id)
        return HistoryEntry.from_dict(record) if record else None

    def list_for_user(self, user_id: str) -> List[HistoryEntry]:
        data = self._load()
        entries = [HistoryEntry.from_dict(r) for r in data.values() if r["user_id"] == user_id]
        return sorted(entries, key=lambda e: e.created_at, reverse=True)

    def list_all(self) -> List[HistoryEntry]:
        data = self._load()
        entries = [HistoryEntry.from_dict(r) for r in data.values()]
        return sorted(entries, key=lambda e: e.created_at, reverse=True)

    def update(self, entry: HistoryEntry) -> HistoryEntry:
        with storage.file_lock(_LOCK_NAME):
            data = self._load()
            if entry.id not in data:
                raise KeyError(f"Historial '{entry.id}' no encontrado.")
            data[entry.id] = entry.to_dict()
            self._save(data)
            return entry

    def delete(self, entry_id: str) -> None:
        with storage.file_lock(_LOCK_NAME):
            data = self._load()
            if data.pop(entry_id, None) is not None:
                self._save(data)
