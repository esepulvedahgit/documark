"""PostgreSQL-backed implementation of BaseHistoryRepository, via the ORM.

Converts between the ``HistoryEntry`` dataclass (dates as ISO strings, per
apps/converter/repositories/base.py) and the ``ConversionHistory`` model
(real DateTimeField columns) at the boundary, so callers of
BaseHistoryRepository keep working with plain ISO strings regardless of the
storage backend.
"""

from typing import List, Optional

from apps.converter.models import ConversionHistory
from apps.converter.repositories.base import BaseHistoryRepository, HistoryEntry
from apps.core.utils import parse_iso


def _optional_iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _optional_parse(value: Optional[str]):
    return parse_iso(value) if value is not None else None


def _to_dataclass(entry: ConversionHistory) -> HistoryEntry:
    return HistoryEntry(
        id=entry.id,
        user_id=entry.user_id,
        username=entry.username,
        original_filename=entry.original_filename,
        safe_filename=entry.safe_filename,
        output_filename=entry.output_filename,
        file_extension=entry.file_extension,
        file_size=entry.file_size,
        status=entry.status,
        error_message=entry.error_message,
        created_at=entry.created_at.isoformat(),
        expires_at=_optional_iso(entry.expires_at),
        downloaded_at=_optional_iso(entry.downloaded_at),
    )


class DjangoHistoryRepository(BaseHistoryRepository):
    def add(self, entry: HistoryEntry) -> HistoryEntry:
        ConversionHistory.objects.create(
            id=entry.id,
            user_id=entry.user_id,
            username=entry.username,
            original_filename=entry.original_filename,
            safe_filename=entry.safe_filename,
            output_filename=entry.output_filename,
            file_extension=entry.file_extension,
            file_size=entry.file_size,
            status=entry.status,
            error_message=entry.error_message,
            created_at=parse_iso(entry.created_at),
            expires_at=_optional_parse(entry.expires_at),
            downloaded_at=_optional_parse(entry.downloaded_at),
        )
        return entry

    def get(self, entry_id: str) -> Optional[HistoryEntry]:
        entry = ConversionHistory.objects.filter(id=entry_id).first()
        return _to_dataclass(entry) if entry else None

    def list_for_user(self, user_id: str) -> List[HistoryEntry]:
        qs = ConversionHistory.objects.filter(user_id=user_id).order_by("-created_at")
        return [_to_dataclass(e) for e in qs]

    def list_all(self) -> List[HistoryEntry]:
        qs = ConversionHistory.objects.order_by("-created_at")
        return [_to_dataclass(e) for e in qs]

    def update(self, entry: HistoryEntry) -> HistoryEntry:
        try:
            record = ConversionHistory.objects.get(id=entry.id)
        except ConversionHistory.DoesNotExist:
            raise KeyError(f"Historial '{entry.id}' no encontrado.")
        record.user_id = entry.user_id
        record.username = entry.username
        record.original_filename = entry.original_filename
        record.safe_filename = entry.safe_filename
        record.output_filename = entry.output_filename
        record.file_extension = entry.file_extension
        record.file_size = entry.file_size
        record.status = entry.status
        record.error_message = entry.error_message
        record.expires_at = _optional_parse(entry.expires_at)
        record.downloaded_at = _optional_parse(entry.downloaded_at)
        record.save()
        return entry

    def delete(self, entry_id: str) -> None:
        ConversionHistory.objects.filter(id=entry_id).delete()
