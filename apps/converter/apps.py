import logging

from django.apps import AppConfig

logger = logging.getLogger("documark.security")


class ConverterConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.converter"
    label = "converter"

    def ready(self):
        # Idempotent by design (deleting already-gone files / re-marking
        # already-expired entries are no-ops), so it's safe to run this on
        # every process start without worrying about the dev autoreloader
        # spawning it twice.
        try:
            from apps.converter.services.cleanup_service import cleanup_all

            cleanup_all()
        except Exception:  # never block app startup because of cleanup
            logger.exception("startup_cleanup_failed")
