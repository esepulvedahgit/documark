from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.accounts.services import auth_service
from apps.accounts.decorators import admin_required, login_required
from apps.accounts.forms import LoginForm, UserCreateForm, UserEditForm
from apps.core.security import login_rate_key
from apps.core.utils import utcnow_iso


def _login_user(request, user):
    request.session.flush()
    request.session["user_id"] = user.id
    request.session["username"] = user.username
    request.session["role"] = user.role
    request.session["last_activity"] = utcnow_iso()


@ratelimit(key=login_rate_key, rate="5/m", method="POST", block=True)
def login_view(request):
    if request.current_user is not None:
        return redirect("converter:dashboard")

    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = auth_service.authenticate(
                form.cleaned_data["username"], form.cleaned_data["password"]
            )
        except auth_service.AuthenticationError as exc:
            messages.error(request, str(exc))
        else:
            _login_user(request, user)
            next_url = request.GET.get("next") or "converter:dashboard"
            return redirect(next_url if next_url.startswith("/") else "converter:dashboard")

    return render(request, "accounts/login.html", {"form": form})


@require_POST
@login_required
def logout_view(request):
    request.session.flush()
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect("accounts:login")


@admin_required
def user_list(request):
    users = auth_service.list_users()
    return render(request, "accounts/user_list.html", {"users": users})


@admin_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            auth_service.create_user(
                form.cleaned_data["username"],
                form.cleaned_data["password"],
                role=form.cleaned_data["role"],
            )
        except ValidationError as exc:
            for message in exc.messages:
                form.add_error(None, message)
        else:
            messages.success(request, f"Usuario '{form.cleaned_data['username']}' creado.")
            return redirect("accounts:user_list")

    return render(request, "accounts/user_form.html", {"form": form, "mode": "create"})


@admin_required
def user_edit(request, user_id):
    user = auth_service.get_user(user_id)
    if user is None:
        messages.error(request, "Usuario no encontrado.")
        return redirect("accounts:user_list")

    form = UserEditForm(
        request.POST or None,
        initial={"role": user.role, "is_active": user.is_active},
    )
    if request.method == "POST" and form.is_valid():
        auth_service.set_role(user.id, form.cleaned_data["role"])
        auth_service.set_active(user.id, form.cleaned_data["is_active"])
        messages.success(request, f"Usuario '{user.username}' actualizado.")
        return redirect("accounts:user_list")

    return render(request, "accounts/user_form.html", {"form": form, "mode": "edit", "target_user": user})
