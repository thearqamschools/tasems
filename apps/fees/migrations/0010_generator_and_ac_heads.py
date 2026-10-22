"""Generator charges and AC charges (project lead, 22 Oct 2026): added only when ticked while making
vouchers; each branch sets the amount in its fee rates. Placed after Summer vacation on the voucher."""

from django.db import migrations

ORDER = ["admission", "registration", "tuition", "annual", "summer_work", "generator", "ac", "general", "others", "fine"]
NEW = [
    ("generator", "Generator charges", "Generator", "جنریٹر چارجز"),
    ("ac", "AC charges", "AC", "اے سی چارجز"),
]


def add(apps, schema_editor):
    FeeHead = apps.get_model("fees", "FeeHead")
    for code, name, short, name_ur in NEW:
        FeeHead.objects.get_or_create(
            code=code,
            defaults={"name": name, "short_name": short, "name_ur": name_ur, "kind": "seasonal", "charge_months": []},
        )
    for order, code in enumerate(ORDER, start=1):
        FeeHead.objects.filter(code=code).update(sort_order=order)
    # Heads added by head office later keep their place after these.
    for extra, head in enumerate(FeeHead.objects.exclude(code__in=ORDER).order_by("sort_order"), start=len(ORDER) + 1):
        head.sort_order = extra
        head.save(update_fields=["sort_order"])


class Migration(migrations.Migration):
    dependencies = [("fees", "0009_royalty_payments_rls")]

    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
