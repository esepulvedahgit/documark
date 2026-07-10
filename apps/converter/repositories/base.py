"""Logical conversion-history model and repository interface.

``HistoryEntry`` stores only metadata about a conversion — never the
document's content. It is a plain dataclass so the same shape works
whether the concrete repository is file-based (today) or backed by a
future ``ConversionHistory`` Django model / PostgreSQL table.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import List, Optional

STATUS_PROCESSING = "processing"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"
STATUSES = (STATUS_PROCESSING, STATUS_SUCCESS, STATUS_FAILED, STATUS_EXPIRED)


@dataclass
class HistoryEntry:
    id: str
    user_id: str
    username: str
    original_filename: str
    safe_filename: Optional[str]
    output_filename: Optional[str]
    file_extension: str
    file_size: int
    status: str
    error_message: Optional[str]
    created_at: str
    expires_at: Optional[str]
    downloaded_at: Optional[str]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HistoryEntry":
        return cls(**{field: data.get(field) for field in cls.__dataclass_fields__})


class BaseHistoryRepository(ABC):
    """Contract every history repository implementation must satisfy.

    A future ``DjangoHistoryRepository``/``PostgresHistoryRepository``
    implements this same interface — services and views don't change.
    """

    @abstractmethod
    def add(self, entry: HistoryEntry) -> HistoryEntry: ...

    @abstractmethod
    def get(self, entry_id: str) -> Optional[HistoryEntry]: ...

    @abstractmethod
    def list_for_user(self, user_id: str) -> List[HistoryEntry]: ...

    @abstractmethod
    def list_all(self) -> List[HistoryEntry]: ...

    @abstractmethod
    def update(self, entry: HistoryEntry) -> HistoryEntry: ...

    @abstractmethod
    def delete(self, entry_id: str) -> None: ...
