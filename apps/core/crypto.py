"""Encryption-at-rest utilities built on cryptography.Fernet.

Every piece of persistent metadata (users, conversion history) and every
converted output kept on disk while awaiting download is encrypted with a
single Fernet key coming from the ``DOCUMARK_FERNET_KEY`` environment
variable.

Never log the key, plaintext passwords, or document contents from this
module.
"""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger("documark.security")


class CryptoError(Exception):
    """Raised when encryption/decryption fails."""


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = getattr(settings, "DOCUMARK_FERNET_KEY", None) or os.environ.get("DOCUMARK_FERNET_KEY")
    env = getattr(settings, "DOCUMARK_ENV", "development")

    if not key:
        if env == "production":
            raise ImproperlyConfigured(
                "DOCUMARK_FERNET_KEY is not set. Refusing to start in production "
                "without an encryption key. Generate one with "
                "scripts/generate_fernet_key.py and set it in the environment."
            )
        key = Fernet.generate_key().decode()
        logger.warning(
            "DOCUMARK_FERNET_KEY not set — generated a TEMPORARY in-memory key for "
            "this process only. Encrypted data will become unreadable on restart. "
            "Set DOCUMARK_FERNET_KEY in your environment before using this beyond "
            "local development."
        )

    if isinstance(key, str):
        key = key.encode()

    try:
        return Fernet(key)
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("DOCUMARK_FERNET_KEY is not a valid Fernet key") from exc


def encrypt_bytes(data: bytes) -> bytes:
    return _get_fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    try:
        return _get_fernet().decrypt(token)
    except InvalidToken as exc:
        raise CryptoError("Unable to decrypt data: invalid token or wrong key") from exc


def encrypt_json(obj) -> bytes:
    payload = json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
    return encrypt_bytes(payload)


def decrypt_json(token: bytes):
    payload = decrypt_bytes(token)
    return json.loads(payload.decode("utf-8"))


def encrypt_file(input_path: Path, output_path: Path) -> None:
    """Encrypt the contents of ``input_path`` and write the token to ``output_path``."""
    data = Path(input_path).read_bytes()
    token = encrypt_bytes(data)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_bytes(token)
    os.replace(tmp_path, output_path)


def decrypt_file_to_bytes(encrypted_path: Path) -> bytes:
    """Decrypt an on-disk Fernet token and return the plaintext bytes (in memory only)."""
    token = Path(encrypted_path).read_bytes()
    return decrypt_bytes(token)
