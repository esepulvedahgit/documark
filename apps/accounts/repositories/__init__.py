"""Repository factory — the one place that decides which concrete
BaseUserRepository implementation is in use.

apps/accounts/services/* never import a concrete repository directly, so
this is the only place a future storage backend change would touch.
"""

from apps.accounts.repositories.base import BaseUserRepository


def get_user_repository() -> BaseUserRepository:
    # Imported lazily: apps.accounts.models imports apps.accounts.repositories.base,
    # which would otherwise trigger this package's __init__ importing models.py
    # back before it finishes defining UserProfile (circular import).
    from apps.accounts.repositories.django_user_repository import DjangoUserRepository

    return DjangoUserRepository()
