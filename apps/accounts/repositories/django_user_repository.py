"""PostgreSQL-backed implementation of BaseUserRepository, via the ORM.

Converts between the ``User`` dataclass (created_at/updated_at as ISO
strings, per apps/accounts/repositories/base.py) and the ``UserProfile``
model (real DateTimeField columns) at the boundary, so callers of
BaseUserRepository keep working with plain ISO strings regardless of the
storage backend.
"""

from typing import List, Optional

from django.db import IntegrityError

from apps.accounts.models import UserProfile
from apps.accounts.repositories.base import BaseUserRepository, User
from apps.core.utils import parse_iso


def _to_dataclass(profile: UserProfile) -> User:
    return User(
        id=profile.id,
        username=profile.username,
        password_hash=profile.password_hash,
        role=profile.role,
        is_active=profile.is_active,
        created_at=profile.created_at.isoformat(),
        updated_at=profile.updated_at.isoformat(),
    )


class DjangoUserRepository(BaseUserRepository):
    def get_by_id(self, user_id: str) -> Optional[User]:
        profile = UserProfile.objects.filter(id=user_id).first()
        return _to_dataclass(profile) if profile else None

    def get_by_username(self, username: str) -> Optional[User]:
        username = (username or "").strip()
        profile = UserProfile.objects.filter(username__iexact=username).first()
        return _to_dataclass(profile) if profile else None

    def list_all(self) -> List[User]:
        return [_to_dataclass(p) for p in UserProfile.objects.order_by("created_at")]

    def create(self, user: User) -> User:
        try:
            UserProfile.objects.create(
                id=user.id,
                username=user.username,
                password_hash=user.password_hash,
                role=user.role,
                is_active=user.is_active,
                created_at=parse_iso(user.created_at),
                updated_at=parse_iso(user.updated_at),
            )
        except IntegrityError:
            raise ValueError(f"El usuario '{user.username}' ya existe.")
        return user

    def update(self, user: User) -> User:
        try:
            profile = UserProfile.objects.get(id=user.id)
        except UserProfile.DoesNotExist:
            raise KeyError(f"Usuario '{user.id}' no encontrado.")
        profile.username = user.username
        profile.password_hash = user.password_hash
        profile.role = user.role
        profile.is_active = user.is_active
        profile.updated_at = parse_iso(user.updated_at)
        profile.save()
        return user
