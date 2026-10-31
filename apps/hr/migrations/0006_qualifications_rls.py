"""Row-level security for staff qualifications, certificates and experience (see core/migrations/0002)."""

from django.db import migrations

TABLES = ["hr_qualification", "hr_certificate", "hr_experience"]


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
    dependencies = [("hr", "0005_qualifications_experience")]

    operations = [migrations.RunSQL(enable(t), disable(t)) for t in TABLES]
