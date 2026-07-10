from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Cross-cutting infrastructure: crypto, storage paths, security helpers, middleware."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "documark_core"
