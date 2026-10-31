"""Row-level security for attendance machines (see core/migrations/0002)."""

from django.db import migrations

TABLE = "hr_attendancemachine"
ENABLE = (
    f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY; "
    f"CREATE POLICY branch_isolation ON {TABLE} "
    f"USING (tasems_branch_allowed(branch_id)) WITH CHECK (tasems_branch_allowed(branch_id));"
)
DISABLE = (
    f"DROP POLICY IF EXISTS branch_isolation ON {TABLE}; ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY; "
    f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;"
)


class Migration(migrations.Migration):
    dependencies = [("hr", "0008_attendance_machine")]

    operations = [migrations.RunSQL(ENABLE, DISABLE)]
