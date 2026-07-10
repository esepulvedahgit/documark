"""Security helpers: strong-password validation, upload validation and
rate-limit key functions.

Kept independent of django.contrib.auth models — documark manages its own
user records via the repository layer, but reuses Django's password
hashing (`django.contrib.auth.hashers`) and the stock
`CommonPasswordValidator` / `UserAttributeSimilarityValidator`, which only
need attribute access on a "user-like" object.
"""

import mimetypes
import re

from django.conf import settings
from django.core.exceptions import ValidationError

_SYMBOL_RE = re.compile(r"[^A-Za-z0-9]")
_UPPER_RE = re.compile(r"[A-Z]")
_LOWER_RE = re.compile(r"[a-z]")
_DIGIT_RE = re.compile(r"[0-9]")


class StrongPasswordValidator:
    """Enforces: >=12 chars, upper, lower, digit and symbol.

    Registered in AUTH_PASSWORD_VALIDATORS alongside Django's stock
    CommonPasswordValidator (blocks common passwords) and
    UserAttributeSimilarityValidator (blocks passwords similar to the
    username).
    """

    MIN_LENGTH = 12

    def validate(self, password, user=None):
        errors = []
        if len(password) < self.MIN_LENGTH:
            errors.append(f"Debe tener al menos {self.MIN_LENGTH} caracteres.")
        if not _UPPER_RE.search(password):
            errors.append("Debe incluir al menos una letra mayúscula.")
        if not _LOWER_RE.search(password):
            errors.append("Debe incluir al menos una letra minúscula.")
        if not _DIGIT_RE.search(password):
            errors.append("Debe incluir al menos un número.")
        if not _SYMBOL_RE.search(password):
            errors.append("Debe incluir al menos un símbolo (por ejemplo: ! @ # $ %).")
        if errors:
            raise ValidationError(errors, code="password_too_weak")

    def get_help_text(self):
        return (
            f"La contraseña debe tener al menos {self.MIN_LENGTH} caracteres e incluir "
            "mayúscula, minúscula, número y símbolo."
        )


class UploadValidationError(ValidationError):
    """Raised when an uploaded file fails extension/MIME/size checks."""


def allowed_extensions() -> set:
    return {ext.lower() for ext in settings.DOCUMARK_ALLOWED_EXTENSIONS}


def max_upload_bytes() -> int:
    return settings.DOCUMARK_MAX_UPLOAD_MB * 1024 * 1024


def validate_upload(uploaded_file) -> None:
    """Validate extension, approximate MIME type and size of an uploaded file.

    Raises UploadValidationError with a user-friendly message on failure.
    Does not trust the original filename beyond checking its extension —
    callers must generate a fresh safe name (see apps.core.utils) before
    writing anything to disk.
    """
    name = uploaded_file.name or ""
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""

    if ext not in allowed_extensions():
        allowed = ", ".join(sorted(allowed_extensions()))
        raise UploadValidationError(
            f"Extensión no permitida ({ext or 'sin extensión'}). Formatos aceptados: {allowed}."
        )

    size = getattr(uploaded_file, "size", None)
    max_bytes = max_upload_bytes()
    if size is not None and size > max_bytes:
        raise UploadValidationError(
            f"El archivo supera el tamaño máximo permitido ({settings.DOCUMARK_MAX_UPLOAD_MB} MB)."
        )
    if size == 0:
        raise UploadValidationError("El archivo está vacío.")

    guessed_type, _ = mimetypes.guess_type(name)
    content_type = getattr(uploaded_file, "content_type", None)
    if guessed_type and content_type and content_type not in ("application/octet-stream",):
        # Best-effort sanity check only — browsers/clients are free to lie
        # about content_type, so this never replaces the extension check.
        guessed_family = guessed_type.split("/")[0]
        content_family = content_type.split("/")[0]
        if guessed_family in ("text", "application", "image") and content_family not in (
            guessed_family,
            "application",
        ):
            raise UploadValidationError(
                "El tipo de contenido del archivo no coincide con su extensión."
            )


def login_rate_key(group, request):
    """Rate-limit key combining client IP and the submitted username."""
    ip = request.META.get("REMOTE_ADDR", "unknown")
    username = (request.POST.get("username") or "unknown").strip().lower()
    return f"{ip}:{username}"


def session_user_key(group, request):
    """Rate-limit key based on the logged-in user's id (falls back to IP)."""
    user_id = request.session.get("user_id")
    if user_id:
        return str(user_id)
    return request.META.get("REMOTE_ADDR", "unknown")
