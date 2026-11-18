"""Reads the attendance machines that are due (Setup → Attendance machine → "Read by itself": never, every 15, 30
or 60 minutes). The Windows copy runs this every few minutes; a machine set to "Never" is never read here."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.hr.models import AttendanceMachine
from apps.hr.services import read_machine


class Command(BaseCommand):
    help = "Read punches from the attendance machines that are due."

    def handle(self, *args, **options):
        # Outside a web request the branch filter is not applied, so every branch's machines are read.
        now = timezone.now()
        machines = AttendanceMachine.objects.filter(is_active=True, read_every__gt=0).select_related(
            "branch", "added_by"
        )
        for machine in machines:
            if machine.is_due(now):
                self.stdout.write(f"{machine}: {read_machine(machine)}")
