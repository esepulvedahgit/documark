"""Session-idle enforcement and per-request auth context.

Sessions are stored client-side (``signed_cookies`` engine, no database), so
there is no server-side session table we could invalidate directly. These
two middlewares add two things Django's cookie-signature max-age check
doesn't give us on its own:

1. An explicit, testable idle-timeout check based on a ``last_activity``
   timestamp we control (defense in depth, independent of the session
   engine's internal signing behaviour).
2. Re-validation, on every request, that the user referenced by the session
   still exists and is active — so an admin disabling a user takes effect
   immediately instead of waiting for the cookie to expire.
"""

import logging
from types import SimpleNamespace

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from apps.core.utils import utcnow, utcnow_iso, parse_iso

logger = logging.getLogger("documark.security")


class SessionIdleMiddleware(MiddlewareMixin):
    """Flushes the session if it has been inactive for too long."""

    def process_request(self, request):
        if "user_id" not in request.session:
            return None

        last_activity = request.session.get("last_activity")
        idle_seconds = getattr(settings, "DOCUMARK_SESSION_IDLE_SECONDS", 1800)
        if last_activity:
            try:
                elapsed = (utcnow() - parse_iso(last_activity)).total_seconds()
            except (ValueError, TypeError):
                elapsed = None
            if elapsed is not None and elapsed > idle_seconds:
                request.session.flush()
                return None

        request.session["last_activity"] = utcnow_iso()
        return None


class AuthContextMiddleware(MiddlewareMixin):
    """Attaches ``request.current_user`` and revalidates the session user.

    ``request.current_user`` is ``None`` for anonymous requests, otherwise a
    lightweight namespace with ``id``, ``username``, ``role`` and
    ``is_active`` — mirroring the dataclass fields without coupling this
    module to the accounts app's repository at import time.
    """

    def process_request(self, request):
        request.current_user = None
        user_id = request.session.get("user_id")
        if not user_id:
            return None

        # Local import: accounts depends on core, not the other way around.
        from apps.accounts.repositories import get_user_repository

        user = get_user_repository().get_by_id(user_id)
        if user is None or not user.is_active:
            request.session.flush()
            return None

        # Keep session role in sync in case an admin changed it mid-session.
        if request.session.get("role") != user.role:
            request.session["role"] = user.role

        request.current_user = SimpleNamespace(
            id=user.id,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
        )
        return None
