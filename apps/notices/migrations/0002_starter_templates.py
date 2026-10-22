"""Starter message templates for parents (head office can change or replace them). Placeholders are filled from
TASEMS records only: {student} {father} {class} {amount_due} {months_due} {date} {branch} {branch_phone} {text}."""

from django.db import migrations

TEMPLATES = [
    (
        "Fee reminder (Urdu)",
        "السلام علیکم معزز والدین،\n{student} ({class}) کی {months_due} ماہ کی فیس {amount_due} روپے ابھی واجب الادا ہے۔"
        " براہِ کرم جلد ادائیگی فرمائیں۔ اگر فیس ادا ہو چکی ہے تو اس پیغام کو نظر انداز کر دیں۔\n"
        "رابطہ: {branch_phone}\nدی ارقم سکولز، {branch}",
    ),
    (
        "Fee reminder (English)",
        "Assalamualaikum Respected Parents,\nThe fee of {student} ({class}) for {months_due} month(s), Rs {amount_due},"
        " is still pending. Kindly pay at your earliest convenience. If it is already paid, please ignore this"
        " message.\nContact: {branch_phone}\nThe Arqam Schools, {branch}",
    ),
    (
        "Absence (Urdu)",
        "السلام علیکم معزز والدین،\n{student} ({class}) آج {date} کو سکول میں غیر حاضر ہیں۔"
        " براہِ کرم سکول کو وجہ سے آگاہ فرمائیں۔\nرابطہ: {branch_phone}\nدی ارقم سکولز، {branch}",
    ),
    (
        "General message",
        "Assalamualaikum Respected Parents,\n{text}\nThe Arqam Schools, {branch}\nContact: {branch_phone}",
    ),
]


def add(apps, schema_editor):
    MessageTemplate = apps.get_model("notices", "MessageTemplate")
    for name, body in TEMPLATES:
        MessageTemplate.objects.get_or_create(name=name, defaults={"body": body})


class Migration(migrations.Migration):
    dependencies = [("notices", "0001_initial")]

    operations = [migrations.RunPython(add, migrations.RunPython.noop)]
