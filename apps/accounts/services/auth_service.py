"""User authentication and management, on top of BaseUserRepository.

Views never talk to the repository directly — they go through this
service, which is the only place that knows about hashing, validation and
security logging for user accounts.
"""

import logging

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.accounts.repositories import get_user_repository
from apps.accounts.repositories.base import ROLES, ROLE_USER, User
from apps.accounts.services.password_service import hash_password, validate_strength, verify_password
from apps.core.utils import new_uuid, utcnow_iso

logger = logging.getLogger("documark.security")


class AuthenticationError(Exception):
    """Raised when login credentials are invalid or the account is disabled."""


def authenticate(username: str, password: str) -> User:
    repo = get_user_repository()
    user = repo.get_by_username(username)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        logger.info("login_failed username=%s", username)
        raise AuthenticationError("Usuario o contraseña incorrectos.")
    logger.info("login_success username=%s", username)
    return user


def create_user(username: str, password: str, role: str = ROLE_USER) -> User:
    username = (username or "").strip()
    if not username:
        raise ValidationError("El nombre de usuario es obligatorio.")
    if role not in ROLES:
        raise ValidationError(f"Rol inválido: {role}")

    validate_strength(password, username=username)

    now = utcnow_iso()
    user = User(
        id=new_uuid(),
        username=username,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    get_user_repository().create(user)
    logger.info("user_created username=%s role=%s", username, role)
    return user


def set_active(user_id: str, is_active: bool) -> User:
    repo = get_user_repository()
    user = repo.get_by_id(user_id)
    if user is None:
        raise KeyError(f"Usuario '{user_id}' no encontrado.")
    user.is_active = is_active
    user.updated_at = utcnow_iso()
    repo.update(user)
    logger.info("user_%s username=%s", "activated" if is_active else "deactivated", user.username)
    return user


def set_role(user_id: str, role: str) -> User:
    if role not in ROLES:
        raise ValidationError(f"Rol inválido: {role}")
    repo = get_user_repository()
    user = repo.get_by_id(user_id)
    if user is None:
        raise KeyError(f"Usuario '{user_id}' no encontrado.")
    user.role = role
    user.updated_at = utcnow_iso()
    repo.update(user)
    logger.info("user_role_changed username=%s role=%s", user.username, role)
    return user


def list_users():
    return get_user_repository().list_all()


def get_user(user_id: str):
    return get_user_repository().get_by_id(user_id)


def ensure_initial_admin() -> None:
    """Create the initial admin account from environment variables if it
    doesn't already exist. Safe to call on every startup.
    """
    from apps.accounts.repositories.base import ROLE_ADMIN

    username = settings.DOCUMARK_INITIAL_ADMIN_USERNAME
    password = settings.DOCUMARK_INITIAL_ADMIN_PASSWORD

    if get_user_repository().get_by_username(username) is not None:
        logger.info("initial_admin_already_exists username=%s", username)
        return

    if not password:
        logger.error(
            "initial_admin_not_created username=%s reason=missing_password "
            "(set DOCUMARK_INITIAL_ADMIN_PASSWORD)",
            username,
        )
        return

    try:
        create_user(username, password, role=ROLE_ADMIN)
        logger.info("initial_admin_created username=%s", username)
    except ValidationError as exc:
        logger.error("initial_admin_not_created username=%s reason=%s", username, exc)
