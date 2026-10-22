"""Project lead, 22 Oct 2026: add the usual expense heads of a school (one list for every branch; branch-own
heads are not offered for now). Existing heads keep their codes; "Other" moves to the end."""

from django.db import migrations

HEADS = [
    ("salaries", "Salaries and wages"),
    ("rent", "Rent"),
    ("utilities", "Electricity, gas and water"),
    ("generator", "Generator and UPS"),
    ("internet-phone", "Internet and phone"),
    ("stationery", "Stationery and printing"),
    ("books", "Books and teaching material"),
    ("exams", "Examination expenses"),
    ("lab", "Science and computer lab"),
    ("computers", "Computers and IT"),
    ("furniture", "Furniture and equipment"),
    ("repairs", "Repairs and maintenance"),
    ("building", "Building and construction"),
    ("cleaning", "Cleaning and sanitation"),
    ("security", "Security"),
    ("transport", "Transport and fuel"),
    ("advertising", "Advertising and admissions campaign"),
    ("events", "Events and functions"),
    ("sports", "Sports and co-curricular"),
    ("refreshments", "Refreshments and hospitality"),
    ("medical", "First aid and medical"),
    ("staff-welfare", "Staff welfare"),
    ("training", "Staff training"),
    ("postage", "Postage and courier"),
    ("bank-charges", "Bank charges"),
    ("taxes", "Taxes and government fees"),
    ("royalty", "Royalty to head office"),
    ("other", "Other"),
]


def forwards(apps, schema_editor):
    ExpenseHead = apps.get_model("accounting", "ExpenseHead")
    for order, (code, name) in enumerate(HEADS, start=1):
        head, created = ExpenseHead.objects.get_or_create(code=code, defaults={"name": name, "sort_order": order})
        if not created:
            head.sort_order = order
            head.save(update_fields=["sort_order"])
    known = [code for code, _ in HEADS]
    for extra, head in enumerate(ExpenseHead.objects.exclude(code__in=known).order_by("sort_order"), start=len(HEADS)):
        head.sort_order = extra  # heads head office added itself stay just before "Other"
        head.save(update_fields=["sort_order"])
    ExpenseHead.objects.filter(code="other").update(sort_order=len(HEADS) + 100)


class Migration(migrations.Migration):
    dependencies = [("accounting", "0002_rls_and_heads")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
