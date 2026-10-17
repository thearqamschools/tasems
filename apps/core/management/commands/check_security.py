"""Pre-deployment security check. Run on the server before going live:

python manage.py check_security --strict
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from apps.core.rls import RLS_TABLES


class Command(BaseCommand):
    help = "Checks database role, row-level security and key production settings."

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="Exit with an error if any problem is found.")

    def handle(self, *args, **options):
        problems = []
        with connection.cursor() as cursor:
            cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            superuser, bypass = cursor.fetchone()
            if superuser or bypass:
                problems.append(
                    "The app connects to PostgreSQL as a superuser or a BYPASSRLS role, so row-level security "
                    "is ignored. Use the tasems_app role (docs/DEPLOYMENT.md)."
                )
            cursor.execute(
                "SELECT relname FROM pg_class WHERE relname = ANY(%s) AND relrowsecurity AND relforcerowsecurity",
                [RLS_TABLES],
            )
            protected = {row[0] for row in cursor.fetchall()}
            missing = sorted(set(RLS_TABLES) - protected)
            if missing:
                problems.append(f"Row-level security is not enabled on: {', '.join(missing)}. Run migrations.")

        if settings.DEBUG:
            problems.append("DEBUG is on. Set DEBUG=False in production.")
        if getattr(settings, "DEMO_MODE", False):
            problems.append("DEMO_MODE is on (no two-step sign-in). Only for demo servers with fictional data.")
        if len(settings.SECRET_KEY) < 50:
            problems.append("SECRET_KEY is shorter than 50 characters.")
        if not settings.ALLOWED_HOSTS:
            problems.append("ALLOWED_HOSTS is empty.")
        if not settings.SECURE_SSL_REDIRECT:
            problems.append("SECURE_SSL_REDIRECT is off; all traffic must use HTTPS.")
        if not settings.SECURE_HSTS_SECONDS:
            problems.append("SECURE_HSTS_SECONDS is 0; enable HSTS once HTTPS works.")

        if not problems:
            self.stdout.write(self.style.SUCCESS("Security check passed."))
            return
        for p in problems:
            self.stdout.write(self.style.WARNING(f"- {p}"))
        if options["strict"]:
            raise CommandError(f"{len(problems)} security problem(s) found.")
