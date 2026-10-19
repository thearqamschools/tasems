"""Row-level security for bank accounts, and the discount types the project lead listed on 19 Oct 2026."""

from decimal import Decimal

from django.db import migrations

TABLE = "fees_bankaccount"

# name, percent, needs approval
DISCOUNTS = [
    ("10% off", "10", False),
    ("20% off", "20", False),
    ("30% off", "30", False),
    ("50% off", "50", False),
    ("60% off", "60", False),
    ("Scholarship (100%)", "100", True),
    ("Staff child (50%)", "50", False),
    ("Staff child (100%)", "100", True),
]


def add_discounts(apps, schema_editor):
    DiscountType = apps.get_model("fees", "DiscountType")
    for order, (name, percent, approval) in enumerate(DISCOUNTS, start=1):
        DiscountType.objects.get_or_create(
            name=name, defaults={"percent": Decimal(percent), "needs_approval": approval, "sort_order": order}
        )


class Migration(migrations.Migration):
    dependencies = [("fees", "0006_bank_accounts_discount_types"), ("core", "0002_row_level_security")]

    operations = [
        migrations.RunSQL(
            f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY; ALTER TABLE {TABLE} FORCE ROW LEVEL SECURITY; "
            f"CREATE POLICY branch_isolation ON {TABLE} "
            f"USING (tasems_branch_allowed(branch_id)) WITH CHECK (tasems_branch_allowed(branch_id));",
            f"DROP POLICY IF EXISTS branch_isolation ON {TABLE}; ALTER TABLE {TABLE} NO FORCE ROW LEVEL SECURITY; "
            f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY;",
        ),
        migrations.RunPython(add_discounts, migrations.RunPython.noop),
    ]
