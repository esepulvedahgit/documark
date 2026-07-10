"""Password hashing and strength validation.

Hashing delegates entirely to django.contrib.auth.hashers (PBKDF2 by
default) — passwords are never stored or logged in plain text. Strength
validation runs the validators configured in settings.AUTH_PASSWORD_VALIDATORS
against a lightweight user-like object so the username-similarity check
works without a real Django auth User model.
"""

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import FieldDoesNotExist, ValidationError


class _FakeMeta:
    """Stands in for a Django model's `_meta` so that
    UserAttributeSimilarityValidator's error-message branch (which calls
    `user._meta.get_field(...)` and expects a FieldDoesNotExist on
    failure) doesn't blow up on a plain user-like object.
    """

    def get_field(self, name):
        raise FieldDoesNotExist(name)


class _UserLike:
    """Minimal stand-in for a Django auth User, exposing just the
    attributes UserAttributeSimilarityValidator inspects."""

    def __init__(self, username):
        self.username = username
        self.first_name = ""
        self.last_name = ""
        self.email = ""
        self._meta = _FakeMeta()


def hash_password(raw_password: str) -> str:
    return make_password(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    return check_password(raw_password, password_hash)


def validate_strength(raw_password: str, username: str = "") -> None:
    """Raises django.core.exceptions.ValidationError if the password is too weak."""
    validate_password(raw_password, user=_UserLike(username))
