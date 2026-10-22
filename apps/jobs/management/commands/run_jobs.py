import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections, connection

from apps.jobs import runner


class Command(BaseCommand):
    help = "Makes waiting PDFs in the background (started next to the web server)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run the waiting jobs, then stop.")
        parser.add_argument("--sleep", type=float, default=3.0, help="Seconds to wait when nothing is waiting.")

    def handle(self, *args, once=False, sleep=3.0, **options):
        runner.requeue_stuck()
        runner.clean_old()
        while True:
            if not connection.in_atomic_block:  # a long-running worker must not keep a dropped connection
                close_old_connections()
            job = runner.run_one()
            if job is not None:
                self.stdout.write(f"{job.pk} {job.kind}: {job.status}")
                continue
            if once:
                return
            time.sleep(sleep)
