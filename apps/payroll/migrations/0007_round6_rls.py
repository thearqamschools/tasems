"""Row-level security for payroll rules, adjustments, advances and securities (see core/migrations/0002)."""

from django.db import migrations

TABLES = [
    "payroll_payrollrules",
    "payroll_payadjustment",
    "payroll_advance",
    "payroll_advancemonth",
    "payroll_advancerecovery",
    "payroll_securityrelease",
]


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
    dependencies = [("payroll", "0006_round6")]

    operations = [migrations.RunSQL(enable(t), disable(t)) for t in TABLES]
