"""Moves CVs of people not hired to the Bin two years after their latest CV, and deletes those 30 days in the Bin."""

from django.core.management.base import BaseCommand

from apps.hiring.services import cleanup


class Command(BaseCommand):
    help = "Bin old CVs (2 years) and empty the Bin (30 days)."

    def handle(self, *args, **options):
        binned, gone = cleanup()
        self.stdout.write(f"{binned} CVs moved to the Bin, {gone} deleted from the Bin.")
