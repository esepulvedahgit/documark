from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django_ratelimit.decorators import ratelimit

from apps.accounts.decorators import admin_required, login_required
from apps.accounts.repositories.base import ROLE_ADMIN
from apps.converter.services import conversion_service
from apps.converter.forms import UploadForm
from apps.converter.repositories import get_history_repository
from apps.converter.repositories.base import STATUS_EXPIRED, STATUS_FAILED, STATUS_PROCESSING, STATUS_SUCCESS
from apps.core.security import session_user_key
from apps.core.utils import parse_iso, utcnow


def index(request):
    if request.current_user is not None:
        return redirect("converter:dashboard")
    return redirect("accounts:login")


def _stats_for(entries):
    now = utcnow()
    total = len(entries)
    processing = sum(1 for e in entries if e.status == STATUS_PROCESSING)
    success = sum(1 for e in entries if e.status == STATUS_SUCCESS)
    failed = sum(1 for e in entries if e.status == STATUS_FAILED)

    def _still_active(e):
        if e.status != STATUS_SUCCESS or not e.expires_at:
            return False
        try:
            return parse_iso(e.expires_at) > now
        except (ValueError, TypeError):
            return False

    active_temp_files = sum(1 for e in entries if _still_active(e))
    return {
        "total": total,
        "processing": processing,
        "success": success,
        "failed": failed,
        "active_temp_files": active_temp_files,
    }


@login_required
def dashboard(request):
    repo = get_history_repository()
    is_admin = request.current_user.role == ROLE_ADMIN
    entries = repo.list_all() if is_admin else repo.list_for_user(request.current_user.id)
    stats = _stats_for(entries)
    return render(request, "converter/dashboard.html", {"stats": stats, "is_admin": is_admin})


@login_required
@ratelimit(key=session_user_key, rate="10/h", method="POST", block=True)
def convert_view(request):
    form = UploadForm()
    context = {"form": form}

    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        context["form"] = form
        if form.is_valid():
            entry = conversion_service.start_conversion(
                form.cleaned_data["document"], request.current_user
            )
            context["entry"] = entry
            if entry.status == STATUS_SUCCESS:
                _, text = conversion_service.get_preview(entry.id, request.current_user)
                context["preview_text"] = text

        if request.headers.get("HX-Request") == "true":
            return render(request, "converter/partials/result.html", context)

    return render(request, "converter/upload.html", context)


@login_required
def convert_status_view(request, conversion_id):
    """Polled by the browser (HTMX) while a conversion has status
    "processing". Deliberately not rate-limited: legitimate polling of one
    long conversion can easily exceed 60 req/h on its own.
    """
    try:
        entry = conversion_service.get_entry(conversion_id, request.current_user)
    except conversion_service.HistoryNotFoundError:
        return render(
            request,
            "converter/partials/error.html",
            {"title": "Conversión no encontrada", "message": "Esta conversión ya no existe."},
            status=404,
        )
    except conversion_service.HistoryForbiddenError:
        return render(
            request,
            "converter/partials/error.html",
            {"title": "Acceso denegado", "message": "No tienes permiso para ver esta conversión."},
            status=403,
        )

    context = {"entry": entry}
    if entry.status == STATUS_SUCCESS:
        _, text = conversion_service.get_preview(entry.id, request.current_user)
        context["preview_text"] = text
    return render(request, "converter/partials/result.html", context)


@login_required
def preview_view(request, conversion_id):
    try:
        entry, text = conversion_service.get_preview(conversion_id, request.current_user)
    except conversion_service.HistoryNotFoundError:
        messages.error(request, "Conversión no encontrada.")
        return redirect("converter:history")
    except conversion_service.HistoryForbiddenError:
        messages.error(request, "No tienes permiso para ver esta conversión.")
        return redirect("converter:history")
    except conversion_service.HistoryExpiredError as exc:
        messages.error(request, str(exc))
        return redirect("converter:history")

    return render(request, "converter/preview.html", {"entry": entry, "preview_text": text})


@login_required
@ratelimit(key=session_user_key, rate="60/h", method="GET", block=True)
def download_view(request, conversion_id):
    try:
        filename, content = conversion_service.get_download(conversion_id, request.current_user)
    except conversion_service.HistoryNotFoundError:
        messages.error(request, "Conversión no encontrada.")
        return redirect("converter:history")
    except conversion_service.HistoryForbiddenError:
        messages.error(request, "No tienes permiso para descargar esta conversión.")
        return redirect("converter:history")
    except conversion_service.HistoryExpiredError as exc:
        messages.error(request, str(exc))
        return redirect("converter:history")

    response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _is_past_expiration(entry):
    if not entry.expires_at:
        return False
    try:
        return parse_iso(entry.expires_at) <= utcnow()
    except (ValueError, TypeError):
        return False


def _downloadable(entry):
    return entry.status == STATUS_SUCCESS and bool(entry.expires_at) and not _is_past_expiration(entry)


def _rows_for(entries):
    return [
        {
            "entry": e,
            "downloadable": _downloadable(e),
            "effective_status": STATUS_EXPIRED if e.status == STATUS_SUCCESS and _is_past_expiration(e) else e.status,
        }
        for e in entries
    ]


@login_required
def history_view(request):
    entries = get_history_repository().list_for_user(request.current_user.id)
    return render(request, "converter/history.html", {"rows": _rows_for(entries), "is_admin_view": False})


@admin_required
def admin_history_view(request):
    entries = get_history_repository().list_all()
    return render(request, "converter/history.html", {"rows": _rows_for(entries), "is_admin_view": True})
