from django.core.management.base import BaseCommand

from apps.converter.services.cleanup_service import cleanup_all


class Command(BaseCommand):
    help = "Deletes stale uploads and expires conversion outputs past their TTL. Safe to run from cron."

    def handle(self, *args, **options):
        result = cleanup_all()
        self.stdout.write(self.style.SUCCESS(f"cleanup_expired: {result}"))
