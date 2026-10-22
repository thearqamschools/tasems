"""Row-level security for Hifz lessons and para tests (see core/migrations/0002_row_level_security.py)."""

from django.db import migrations

TABLES = ["hifz_hifzlesson", "hifz_paratest"]


def enable(table):
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY; "
        f"CREATE POLICY branch_isolation ON {table} "
        f"USING (tasems_branch_allowed(branch_id)) WITH CHECK (tasems_branch_allowed(branch_id));"
    )


def disable(table):
    return (
        f"DROP POLICY IF EXISTS branch_isolation ON {table}; ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY; "
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;"
    )


class Migration(migrations.Migration):
    dependencies = [("hifz", "0001_initial"), ("core", "0002_row_level_security")]

    operations = [migrations.RunSQL(enable(t), disable(t)) for t in TABLES]
