"""Row-level security for royalty payments (see core/migrations/0002_row_level_security.py)."""

from django.db import migrations

TABLE = "fees_royaltypayment"


class Migration(migrations.Migration):
    dependencies = [("fees", "0008_royalty_payments"), ("core", "0002_row_level_security")]

    operations = [
        migrations.RunSQL(
            f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY; "
            f"CREATE POLICY branch_isolation ON {TABLE} "
            f"USING (tasems_branch_allowed(branch_id)) WITH CHECK (tasems_branch_allowed(branch_id));",
            f"DROP POLICY IF EXISTS branch_isolation ON {TABLE}; ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY; "
            f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;",
        )
    ]
