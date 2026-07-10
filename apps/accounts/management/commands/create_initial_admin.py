from django.core.management.base import BaseCommand

from apps.accounts.services.auth_service import ensure_initial_admin


class Command(BaseCommand):
    help = "Creates the initial admin user from DOCUMARK_INITIAL_ADMIN_* env vars if it doesn't exist yet."

    def handle(self, *args, **options):
        ensure_initial_admin()
        self.stdout.write(self.style.SUCCESS("create_initial_admin: done (see logs for details)."))
