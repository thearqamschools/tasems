"""Row-level security for salary changes, manual days and salary payments (see core/migrations/0002)."""

from django.db import migrations

TABLES = ["payroll_salarychange", "payroll_manualdays", "payroll_salarypayment"]


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
    dependencies = [("payroll", "0004_salaries_round5")]

    operations = [migrations.RunSQL(enable(t), disable(t)) for t in TABLES]
