"""No re-admission fee at The Arqam Schools (confirmed 16 Oct 2026): remove the head.
If it was ever used it is only switched off, so past records stay intact."""

from django.db import migrations


def remove_head(apps, schema_editor):
    FeeHead = apps.get_model("fees", "FeeHead")
    Charge = apps.get_model("fees", "Charge")
    FeeRate = apps.get_model("fees", "FeeRate")
    Concession = apps.get_model("fees", "Concession")
    head = FeeHead.objects.filter(code="re_admission").first()
    if head is None:
        return
    used = (
        Charge.objects.filter(head=head).exists()
        or FeeRate.objects.filter(head=head).exists()
        or Concession.objects.filter(head=head).exists()
    )
    if used:
        head.is_active = False
        head.save(update_fields=["is_active"])
    else:
        head.delete()


class Migration(migrations.Migration):
    dependencies = [("fees", "0003_remove_royalty_flag")]

    operations = [migrations.RunPython(remove_head, migrations.RunPython.noop)]
