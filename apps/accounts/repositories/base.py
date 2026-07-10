"""Logical user model and repository interface.

``User`` is a plain dataclass — not a Django model — so it works identically
whether the concrete repository behind it reads from an encrypted file
(today) or a PostgreSQL table (future). Services and views only ever depend
on ``BaseUserRepository``.
"""

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import List, Optional

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLES = (ROLE_ADMIN, ROLE_USER)


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "User":
        return cls(
            id=data["id"],
            username=data["username"],
            password_hash=data["password_hash"],
            role=data["role"],
            is_active=data["is_active"],
            created_at=data["created_at"],
            updated_at=data["updated_at"],
        )


class BaseUserRepository(ABC):
    """Contract every user repository implementation must satisfy.

    A future ``DjangoUserRepository``/``PostgresUserRepository`` backed by
    the ORM implements this same interface — no other code needs to change.
    """

    @abstractmethod
    def get_by_id(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    def get_by_username(self, username: str) -> Optional[User]: ...

    @abstractmethod
    def list_all(self) -> List[User]: ...

    @abstractmethod
    def create(self, user: User) -> User: ...

    @abstractmethod
    def update(self, user: User) -> User: ...
