"""
Django settings for the documark project.

Business data (users, conversion history) is persisted in PostgreSQL via
apps/*/models.py and the Django*Repository implementations in
apps/*/repositories/. Document content (converted .md output) stays as
Fernet-encrypted files under storage/ — see apps/core/crypto.py.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default):
    value = os.environ.get(name)
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core / environment
# ---------------------------------------------------------------------------

DOCUMARK_ENV = os.environ.get("DOCUMARK_ENV", "development")
DEBUG = env_bool("DJANGO_DEBUG", DOCUMARK_ENV != "production")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

if DOCUMARK_ENV == "production" and SECRET_KEY == "dev-secret-key-change-me":
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be set to a real secret in production "
        "(DOCUMARK_ENV=production)."
    )

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
# Deliberately excludes django.contrib.auth/admin/contenttypes: documark
# manages its own users through the repository layer, not the ORM.

INSTALLED_APPS = [
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_ratelimit",
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.converter.apps.ConverterConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "apps.core.middleware.SessionIdleMiddleware",
    "apps.core.middleware.AuthContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database — PostgreSQL. Only User/HistoryEntry metadata lives here; document
# content stays as encrypted files under STORAGE_ROOT (see apps/core/crypto.py).
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "documark"),
        "USER": os.environ.get("POSTGRES_USER", "documark"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "documark"),
        "HOST": os.environ.get("POSTGRES_HOST", "postgres"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "es"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Sessions — signed cookies, no database/cache backend required.
# ---------------------------------------------------------------------------

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
DOCUMARK_SESSION_IDLE_SECONDS = int(os.environ.get("DOCUMARK_SESSION_IDLE_SECONDS", "1800"))
SESSION_COOKIE_AGE = DOCUMARK_SESSION_IDLE_SECONDS
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", DOCUMARK_ENV == "production")

# ---------------------------------------------------------------------------
# CSRF — kept on everywhere; HTMX sends it via the X-CSRFToken header
# (see static/js/app.js), which requires the cookie to be readable by JS.
# ---------------------------------------------------------------------------

CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", DOCUMARK_ENV == "production")
CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

# HTTPS-only settings — off by default in dev, toggle via env once behind TLS.
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_HSTS_PRELOAD = env_bool("DJANGO_SECURE_HSTS_PRELOAD", False)

# ---------------------------------------------------------------------------
# Password validation (no contrib.auth models required — these validators
# only need attribute access on a lightweight "user-like" object).
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "apps.core.security.StrongPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Uploads
# ---------------------------------------------------------------------------

DOCUMARK_MAX_UPLOAD_MB = int(os.environ.get("DOCUMARK_MAX_UPLOAD_MB", "50"))
DATA_UPLOAD_MAX_MEMORY_SIZE = DOCUMARK_MAX_UPLOAD_MB * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = DOCUMARK_MAX_UPLOAD_MB * 1024 * 1024

DOCUMARK_ALLOWED_EXTENSIONS = env_list(
    "DOCUMARK_ALLOWED_EXTENSIONS",
    [".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".json", ".xml", ".html", ".txt", ".epub", ".zip"],
)

# Hard ceiling on a single conversion, enforced in a subprocess by
# MarkItDownService (see apps/converter/services/markitdown_service.py) so a
# slow/adversarial document becomes a controlled "failed" history entry
# instead of running past Gunicorn's own worker timeout (GUNICORN_TIMEOUT in
# config/gunicorn.conf.py, which should stay comfortably larger than this).
DOCUMARK_CONVERSION_TIMEOUT_SECONDS = int(os.environ.get("DOCUMARK_CONVERSION_TIMEOUT_SECONDS", "240"))

# ---------------------------------------------------------------------------
# Storage (file-based, encrypted at rest) — see apps/core/storage.py
# ---------------------------------------------------------------------------

STORAGE_ROOT = Path(os.environ.get("DOCUMARK_STORAGE_ROOT", BASE_DIR / "storage"))
# How long a converted .md stays downloadable before the file is deleted
# and the entry is marked "expired" (see cleanup_service.cleanup_expired_outputs).
DOCUMARK_OUTPUT_TTL_SECONDS = int(os.environ.get("DOCUMARK_OUTPUT_TTL_SECONDS", "7200"))
# How long a history *record* (metadata only) is kept at all, regardless of
# status, before being purged entirely (see
# cleanup_service.cleanup_old_history_entries) — must be >= DOCUMARK_OUTPUT_TTL_SECONDS.
DOCUMARK_HISTORY_RETENTION_SECONDS = int(os.environ.get("DOCUMARK_HISTORY_RETENTION_SECONDS", "86400"))
DOCUMARK_FERNET_KEY = os.environ.get("DOCUMARK_FERNET_KEY", "")

# ---------------------------------------------------------------------------
# Initial admin (created by create_initial_admin management command)
# ---------------------------------------------------------------------------

DOCUMARK_INITIAL_ADMIN_USERNAME = os.environ.get("DOCUMARK_INITIAL_ADMIN_USERNAME", "admin")
DOCUMARK_INITIAL_ADMIN_PASSWORD = os.environ.get("DOCUMARK_INITIAL_ADMIN_PASSWORD", "")
DOCUMARK_INITIAL_ADMIN_EMAIL = os.environ.get("DOCUMARK_INITIAL_ADMIN_EMAIL", "admin@example.local")

# ---------------------------------------------------------------------------
# Rate limiting cache (django-ratelimit) — Redis-backed, atomic incr().
# ---------------------------------------------------------------------------

DOCUMARK_REDIS_CACHE_URL = os.environ.get("DOCUMARK_REDIS_CACHE_URL", "redis://redis:6379/1")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": DOCUMARK_REDIS_CACHE_URL,
    }
}
RATELIMIT_USE_CACHE = "default"
RATELIMIT_VIEW = "apps.core.views.ratelimited_view"

# ---------------------------------------------------------------------------
# Celery — background conversion jobs. Redis here is purely a broker; it
# holds no business data (users/history stay in the encrypted file
# repositories). CELERY_RESULT_BACKEND is intentionally unset: HistoryEntry
# (apps/converter/repositories) is already the source of truth for a
# conversion's status, so we don't need Celery's own result store.
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Redelivers a task to another worker if the one running it dies mid-task
# (crash, OOM, container restart) instead of silently losing the work — a
# real reliability gain over the previous thread-based background design.
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Celery's own timeout is a generous outer backstop: MarkItDownService
# already enforces DOCUMARK_CONVERSION_TIMEOUT_SECONDS itself via a
# subprocess (see apps/converter/services/markitdown_service.py), so this
# should rarely if ever be the one that fires.
CELERY_TASK_SOFT_TIME_LIMIT = DOCUMARK_CONVERSION_TIMEOUT_SECONDS + 30
CELERY_TASK_TIME_LIMIT = DOCUMARK_CONVERSION_TIMEOUT_SECONDS + 60

# The Redis transport doesn't redeliver an unacked message (CELERY_TASK_ACKS_LATE)
# until this many seconds pass — its default is 3600s (1 hour), which would
# leave a conversion whose worker died sitting un-retried for an hour. Tie it
# to how long a task could legitimately still be running, plus a buffer, so
# a live task's message isn't redelivered to a second worker prematurely.
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "visibility_timeout": CELERY_TASK_TIME_LIMIT + 120,
}

CELERY_BEAT_SCHEDULE = {
    "cleanup-expired": {
        "task": "apps.converter.tasks.cleanup_expired_task",
        "schedule": float(os.environ.get("DOCUMARK_CLEANUP_INTERVAL_SECONDS", "300")),
    },
}

# ---------------------------------------------------------------------------
# Logging — never log document contents, passwords or encryption keys.
# ---------------------------------------------------------------------------

(STORAGE_ROOT / "logs").mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(STORAGE_ROOT / "logs" / "documark.log"),
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "documark.security": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
