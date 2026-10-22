"""Project lead, 22 Oct 2026: keep AC charges, remove Generator charges — the generator is already billed
as "Gen. Exp." (generator expenses), whose full name is corrected here. A Generator head already used on a
voucher or given a rate is switched off instead of deleted, so old vouchers still print."""

from django.db import migrations

ORDER = ["admission", "registration", "tuition", "annual", "summer_work", "ac", "general", "others", "fine"]


def forwards(apps, schema_editor):
    FeeHead = apps.get_model("fees", "FeeHead")
    Charge, FeeRate = apps.get_model("fees", "Charge"), apps.get_model("fees", "FeeRate")
    FeeHead.objects.filter(code="general").update(name="Generator expenses", name_ur="جنریٹر اخراجات")
    generator = FeeHead.objects.filter(code="generator").first()
    if generator:
        if Charge.objects.filter(head=generator).exists() or FeeRate.objects.filter(head=generator).exists():
            generator.is_active = False
            generator.save(update_fields=["is_active"])
        else:
            generator.delete()
    for order, code in enumerate(ORDER, start=1):
        FeeHead.objects.filter(code=code).update(sort_order=order)
    for extra, head in enumerate(FeeHead.objects.exclude(code__in=ORDER).order_by("sort_order"), start=len(ORDER) + 1):
        head.sort_order = extra
        head.save(update_fields=["sort_order"])


class Migration(migrations.Migration):
    dependencies = [("fees", "0010_generator_and_ac_heads")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
