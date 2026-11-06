"""Row-level security for staff duty times, and the first duty times from the branch's HR settings.

Each branch's one duty time (e.g. Samanabad 07:45–13:45) becomes the starting In / Out time of all four staff types,
from 1 Jan 2020, so the days already worked out keep the same late rule (project lead, 6 Nov 2026)."""

import datetime as dt

from django.db import migrations

TABLE = "hr_dutytime"
ENABLE = (
    f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY; "
    f"CREATE POLICY branch_isolation ON {TABLE} "
    f"USING (tasems_branch_allowed(branch_id)) WITH CHECK (tasems_branch_allowed(branch_id));"
)
DISABLE = (
    f"DROP POLICY IF EXISTS branch_isolation ON {TABLE}; ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY; "
    f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;"
)
TYPES = ["teaching", "hifz", "admin", "support"]


def first_times(apps, schema_editor):
    HRSettings = apps.get_model("hr", "HRSettings")
    DutyTime = apps.get_model("hr", "DutyTime")
    for hr in HRSettings.objects.exclude(duty_starts=None).exclude(duty_ends=None):
        for staff_type in TYPES:
            DutyTime.objects.get_or_create(
                branch_id=hr.branch_id,
                staff_type=staff_type,
                starts_from=dt.date(2020, 1, 1),
                defaults={
                    "duty_starts": hr.duty_starts,
                    "duty_ends": hr.duty_ends,
                    "grace_minutes": hr.grace_minutes,
                    "half_day_after": hr.half_day_after,
                },
            )


class Migration(migrations.Migration):
    dependencies = [("hr", "0010_round7")]

    operations = [migrations.RunSQL(ENABLE, DISABLE), migrations.RunPython(first_times, migrations.RunPython.noop)]
