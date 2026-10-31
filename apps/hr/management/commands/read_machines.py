"""Reads every attendance machine set to read automatically (the Windows copy runs this every few minutes)."""

from django.core.management.base import BaseCommand

from apps.hr.models import AttendanceMachine
from apps.hr.services import read_machine


class Command(BaseCommand):
    help = "Read punches from the attendance machines on the office network."

    def handle(self, *args, **options):
        # Outside a web request the branch filter is not applied, so every branch's machines are read.
        machines = AttendanceMachine.objects.filter(is_active=True, auto_read=True).select_related("branch", "added_by")
        for machine in machines:
            self.stdout.write(f"{machine}: {read_machine(machine)}")
