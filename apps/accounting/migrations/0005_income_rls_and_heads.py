"""Row-level security for other income and opening balances, and a starter list of income heads (the same for every
branch; head office can change it). Fees are not an income head: they come from the Fees pages."""

from django.db import migrations

TABLES = ["accounting_income", "accounting_openingbalance"]

HEADS = [
    ("forms", "Admission and prospectus forms"),
    ("books", "Books and stationery sale"),
    ("uniform", "Uniform sale"),
    ("canteen", "Canteen / tuck shop"),
    ("events", "Events and functions"),
    ("rent", "Rent received"),
    ("donations", "Donations"),
    ("bank-profit", "Bank profit"),
    ("scrap", "Sale of old items"),
    ("other", "Other"),
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


def add_heads(apps, schema_editor):
    IncomeHead = apps.get_model("accounting", "IncomeHead")
    for order, (code, name) in enumerate(HEADS, start=1):
        IncomeHead.objects.get_or_create(code=code, defaults={"name": name, "sort_order": order})


class Migration(migrations.Migration):
    dependencies = [("accounting", "0004_income_and_openings"), ("core", "0002_row_level_security")]

    operations = [migrations.RunSQL(enable(t), disable(t)) for t in TABLES] + [
        migrations.RunPython(add_heads, migrations.RunPython.noop)
    ]
