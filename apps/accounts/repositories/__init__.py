"""Repository factory — the one place that decides which concrete
BaseUserRepository implementation is in use.

Today it always returns FileUserRepository. Migrating to PostgreSQL later
means adding a DjangoUserRepository and switching the return value here;
apps/accounts/services/* never import a concrete repository directly.
"""

from apps.accounts.repositories.base import BaseUserRepository
from apps.accounts.repositories.file_user_repository import FileUserRepository


def get_user_repository() -> BaseUserRepository:
    return FileUserRepository()
