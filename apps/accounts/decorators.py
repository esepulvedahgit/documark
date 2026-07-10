"""Access-control decorators built on request.current_user, which
apps.core.middleware.AuthContextMiddleware attaches on every request.

Deliberately not django.contrib.auth.decorators.login_required — there is
no contrib.auth user model here.
"""

from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

from apps.accounts.repositories.base import ROLE_ADMIN


def login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.current_user is None:
            login_url = reverse("accounts:login")
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{login_url}?{query}")
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.current_user.role != ROLE_ADMIN:
            messages.error(request, "No tienes permisos de administrador para acceder a esta página.")
            return redirect("converter:dashboard")
        return view_func(request, *args, **kwargs)

    return wrapper
