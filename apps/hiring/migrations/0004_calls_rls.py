"""Row-level security for candidate calls (see core/migrations/0002)."""

from django.db import migrations

TABLE = "hiring_candidatecall"
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
    dependencies = [("hiring", "0003_calls")]

    operations = [migrations.RunSQL(ENABLE, DISABLE)]
