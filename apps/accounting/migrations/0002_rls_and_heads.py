"""Row-level security for expenses, and a starter list of expense heads (head office can change it)."""

from django.db import migrations

TABLE = "accounting_expense"

HEADS = [
    ("utilities", "Electricity, gas and water"),
    ("rent", "Rent"),
    ("salaries", "Salaries and wages"),
    ("stationery", "Stationery and printing"),
    ("repairs", "Repairs and maintenance"),
    ("cleaning", "Cleaning and sanitation"),
    ("transport", "Transport and fuel"),
    ("internet-phone", "Internet and phone"),
    ("events", "Events and functions"),
    ("generator", "Generator and UPS"),
    ("royalty", "Royalty to head office"),
    ("other", "Other"),
]


def add_heads(apps, schema_editor):
    ExpenseHead = apps.get_model("accounting", "ExpenseHead")
    for order, (code, name) in enumerate(HEADS, start=1):
        ExpenseHead.objects.get_or_create(code=code, defaults={"name": name, "sort_order": order})


class Migration(migrations.Migration):
    dependencies = [("accounting", "0001_initial"), ("core", "0002_row_level_security")]

    operations = [
        migrations.RunSQL(
            f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY; "
            f"CREATE POLICY branch_isolation ON {TABLE} "
            f"USING (tasems_branch_allowed(branch_id)) WITH CHECK (tasems_branch_allowed(branch_id));",
            f"DROP POLICY IF EXISTS branch_isolation ON {TABLE}; ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY; "
            f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;",
        ),
        migrations.RunPython(add_heads, migrations.RunPython.noop),
    ]
