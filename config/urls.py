from django.urls import include, path

urlpatterns = [
    path("", include("apps.converter.urls")),
    path("", include("apps.accounts.urls")),
]

# django_ratelimit raises Ratelimited (a PermissionDenied subclass) when a
# rate-limited view is blocked; route it to a friendly, HTMX-aware page
# instead of Django's generic 403.
handler403 = "apps.core.views.ratelimited_view"
