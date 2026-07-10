"""Shared, app-agnostic views — currently just the friendly rate-limit
error page referenced by settings.RATELIMIT_VIEW.
"""

from django.http import HttpResponse


_MESSAGE = "Demasiados intentos. Por favor espera un momento antes de volver a intentarlo."


def ratelimited_view(request, exception=None):
    if request.headers.get("HX-Request") == "true":
        html = f'<div class="rounded-md bg-red-50 border border-red-200 text-red-700 px-4 py-3 text-sm">{_MESSAGE}</div>'
    else:
        html = (
            "<!doctype html><html lang='es'><head><meta charset='utf-8'>"
            "<title>Límite alcanzado — documark</title></head>"
            "<body style='font-family:sans-serif;max-width:32rem;margin:4rem auto;text-align:center;'>"
            f"<h1>429</h1><p>{_MESSAGE}</p>"
            "</body></html>"
        )
    return HttpResponse(html, status=429)
