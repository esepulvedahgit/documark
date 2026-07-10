"""Repository factory — the one place that decides which concrete
BaseHistoryRepository implementation is in use. See
apps/accounts/repositories/__init__.py for the same pattern applied to users.
"""

from apps.converter.repositories.base import BaseHistoryRepository
from apps.converter.repositories.file_history_repository import FileHistoryRepository


def get_history_repository() -> BaseHistoryRepository:
    return FileHistoryRepository()
