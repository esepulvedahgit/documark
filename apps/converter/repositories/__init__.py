"""Repository factory — the one place that decides which concrete
BaseHistoryRepository implementation is in use. See
apps/accounts/repositories/__init__.py for the same pattern applied to users.
"""

from apps.converter.repositories.base import BaseHistoryRepository


def get_history_repository() -> BaseHistoryRepository:
    # Imported lazily: apps.converter.models imports apps.converter.repositories.base,
    # which would otherwise trigger this package's __init__ importing models.py
    # back before it finishes defining ConversionHistory (circular import).
    from apps.converter.repositories.django_history_repository import DjangoHistoryRepository

    return DjangoHistoryRepository()
