# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Documark is a self-hosted Django web app that converts documents (`.pdf`, `.docx`, `.pptx`, `.xlsx`,
`.csv`, `.json`, `.xml`, `.html`, `.txt`, `.epub`, `.zip`) to Markdown using
[MarkItDown](https://github.com/microsoft/markitdown). It's a Django rewrite/evolution of a Flask MVP
(`/opt/ConvMk-pdf`), adding users, roles, conversion history and a Tailwind + HTMX UI. UI strings,
templates, and log messages are in Spanish (`LANGUAGE_CODE = "es"`).

## Commands

```bash
# Run the full test suite (Celery runs eager/synchronous — no Redis needed)
pytest

# Run a single test file / test
pytest tests/test_conversion_service.py
pytest tests/test_conversion_service.py::test_name -v

# Local dev server (needs .env configured — see below)
python manage.py runserver

# Full stack (web + celery_worker + celery_beat + redis) via Docker
docker compose up --build
# -> http://localhost:8000

# Generate the Fernet encryption key (put the output in .env as DOCUMARK_FERNET_KEY)
python scripts/generate_fernet_key.py

# Create the initial admin user (also run automatically by the entrypoint on container start)
python manage.py create_initial_admin

# Purge expired outputs/history entries (also run periodically by celery_beat)
python manage.py cleanup_expired

# Bump the pinned MarkItDown version
bash scripts/update_markitdown.sh   # rewrites requirements-markitdown.txt
docker compose up --build
pytest                               # re-validate key formats still convert
```

First-time setup: `cp .env.example .env`, then set at least `DJANGO_SECRET_KEY`,
`DOCUMARK_FERNET_KEY`, and `DOCUMARK_INITIAL_ADMIN_PASSWORD`.

## Architecture

**No SQL database.** `DATABASES["default"]["ENGINE"]` is `django.db.backends.dummy` on purpose —
`django.contrib.auth`/`admin`/`contenttypes` are deliberately excluded from `INSTALLED_APPS`. Users
and conversion history are plain dataclasses (`apps/accounts/repositories/base.py:User`,
`apps/converter/repositories/base.py:HistoryEntry`) persisted as Fernet-encrypted JSON files under
`storage/secure/` (`users.enc`, `history.enc`), guarded by `fcntl` file locks so multiple Gunicorn
workers can write concurrently. Redis is used *only* as the Celery broker and rate-limit cache — never
for business data (no persistent volume, by design: a Redis restart should only cost in-flight
conversions, which `cleanup_stale_processing` detects and marks failed).

**Repository abstraction is the seam for a future Postgres migration.** Services never import a
concrete repository — they call `get_user_repository()` / `get_history_repository()` factories
(`apps/accounts/repositories/__init__.py`, `apps/converter/repositories/__init__.py`), which today
return `FileUserRepository` / `FileHistoryRepository`. Adding `DjangoUserRepository` /
`DjangoHistoryRepository` behind `BaseUserRepository` / `BaseHistoryRepository` and switching the
factory return value is the entire migration — views and services don't change (see README "Migrando
a PostgreSQL" for the full checklist).

**Auth is homegrown, not `django.contrib.auth`.** `SESSION_ENGINE = signed_cookies` (no DB-backed
session store). The session holds `{user_id, username, role}`; `apps.core.middleware.AuthContextMiddleware`
re-validates the user against `FileUserRepository` on *every* request (not just at login), so
deactivating a user takes effect immediately rather than waiting for cookie expiry.
`apps.core.middleware.SessionIdleMiddleware` expires sessions after `DOCUMARK_SESSION_IDLE_SECONDS`
of inactivity. Route protection uses `apps/accounts/decorators.py` (`login_required`,
`admin_required`), not `django.contrib.auth.decorators`.

**Conversions run in Celery, never inline in the request.** `POST /convert/` validates and saves the
upload, writes a `HistoryEntry(status="processing")`, enqueues a Celery task
(`apps/converter/tasks.py`), and returns immediately with an HTMX "processing" fragment. The browser
polls `GET /convert/status/<id>/` (`hx-trigger="load delay:2s"`) until the status changes. Inside the
task, `MarkItDownService` (`apps/converter/services/markitdown_service.py`) runs the actual conversion
in a **subprocess** (`subprocess.Popen`, deliberately not `multiprocessing` — Celery's `prefork` pool
runs tasks in daemon processes, which can't spawn `multiprocessing.Process` children) bounded by
`DOCUMARK_CONVERSION_TIMEOUT_SECONDS`. `CELERY_TASK_ACKS_LATE` + a tuned `visibility_timeout` mean a
worker dying mid-conversion gets its task redelivered rather than losing it; `cleanup_stale_processing`
is the backstop that marks any conversion stuck "processing" too long as failed.

**All MarkItDown usage is isolated in one file**: `apps/converter/services/markitdown_service.py`
(plus its subprocess entrypoint `_markitdown_worker.py`). The library is pinned separately in
`requirements-markitdown.txt` because it releases very frequently, and upgrading it should only ever
require touching that one service file.

**Encryption**: `apps/core/crypto.py` wraps `cryptography.Fernet` for all persisted metadata
(`storage/secure/*.enc`) and queued output files (`storage/outputs/*.md.enc`). The original uploaded
document exists in plaintext only for the duration of conversion and is deleted immediately after.
Without `DOCUMARK_FERNET_KEY` set, a temporary in-memory key is generated in dev (logged as a warning,
data becomes unreadable on restart); in production (`DOCUMARK_ENV=production`) missing the key is a
hard startup failure.

**App layout** (`apps/core`, `apps/accounts`, `apps/converter`) follows a `views -> services ->
repositories` layering per app: views handle HTTP/HTMX concerns only, services hold business logic,
repositories are the only code that touches the encrypted storage files. `apps/core` holds
cross-cutting concerns: crypto, storage path management, security headers/middleware, password
strength validation (`apps/core/security.py`), and upload sanitization (`apps/core/utils.py`).

## Security-relevant conventions

- Passwords: hashed via `django.contrib.auth.hashers` (contrib.auth's *hasher*, not its user model).
  `StrongPasswordValidator` (`apps/core/security.py`) requires 12+ chars, upper/lower/digit/symbol, on
  top of Django's standard common-password/similarity validators.
- CSRF stays on everywhere; HTMX sends the token via the `X-CSRFToken` header (`static/js/app.js`),
  which is why `CSRF_COOKIE_HTTPONLY = False`.
- Rate limiting (`django-ratelimit` + `django-redis`, real atomic counters): login 5/min per IP+user,
  conversion 10/hour per user, download 60/hour per user. The status-polling endpoint is deliberately
  *not* rate-limited — a single long conversion's own polling can legitimately exceed 60 req/hour.
- Uploads: extension/size/MIME checks plus filename sanitization + UUID renaming
  (`apps/core/utils.py`) — never trust the original filename; guards against path traversal.
- Never log document contents, passwords, or encryption keys (see `documark.security` logger in
  `config/settings.py`).

## Tests

`pytest` (config in `pytest.ini`, `DJANGO_SETTINGS_MODULE=config.settings`). `conftest.py` provides:
- `celery_eager` (autouse): forces `CELERY_TASK_ALWAYS_EAGER` so tasks run synchronously in-process —
  no real Redis broker needed for any test.
- `isolated_storage`: redirects `settings.STORAGE_ROOT` to a temp dir so repository/service tests never
  touch real `storage/secure/*.enc` files.

Coverage includes encryption round-trips, password hashing/strength, file repositories, MarkItDown
subprocess isolation/timeout (against the real library, not mocked), and the full background
conversion flow (validation, state transitions, idempotency under Celery redelivery).
