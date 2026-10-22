"""Family vouchers (M6): every child of one father (same CNIC, as for the sibling fee) on one voucher.

A family voucher lists each child's own open voucher. Paying it records one payment per child, each for that
child's whole amount due on the day (the same amount the Barcode page would take), so every child's account,
receipt history and defaulter status stay exactly as if each voucher had been paid on its own."""

from collections import defaultdict

from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditEvent
from apps.people.models import Student, StudentGuardian

from . import services as S
from .models import FamilyVoucher, FamilyVoucherItem, Voucher


def families(branch, month):
    """Families with two or more children whose newest voucher covering `month` is still open."""
    open_vouchers = (
        Voucher.objects.filter(
            branch=branch,
            status=Voucher.Status.OPEN,
            first_month__lte=month,
            last_month__gte=month,
            student__status=Student.Status.ACTIVE,
        )
        .exclude(student__father_cnic="")
        .select_related("student", "section__class_level")
        .order_by("student__admission_date", "student_id", "-pk")
    )
    grouped = defaultdict(list)
    seen = set()
    for v in open_vouchers:
        if v.student_id in seen:
            continue
        seen.add(v.student_id)
        grouped[v.student.father_cnic].append(v)
    phones = {
        link.student_id: link.guardian.phone
        for link in StudentGuardian.objects.filter(student_id__in=seen, is_primary_contact=True).select_related(
            "guardian"
        )
    }
    out = []
    for cnic, vouchers in grouped.items():
        if len(vouchers) < 2:
            continue
        first = vouchers[0].student
        out.append(
            {
                "cnic": cnic,
                "father": first.father_name,
                "phone": next((phones[v.student_id] for v in vouchers if phones.get(v.student_id)), ""),
                "vouchers": vouchers,
                "payable": sum((v.payable for v in vouchers), S.ZERO),
            }
        )
    out.sort(key=lambda f: (f["father"] or "", f["cnic"]))
    return out


@transaction.atomic
def make(branch, month, user):
    """One family voucher per family for `month`. A family whose children's vouchers have not changed keeps
    its family voucher (and number); otherwise the old one is replaced. Returns (made, kept)."""
    today = timezone.localdate()
    made, kept = [], []
    current = {
        fv.father_cnic: fv
        for fv in FamilyVoucher.objects.filter(
            branch=branch, month=month, status=FamilyVoucher.Status.OPEN
        ).prefetch_related("items")
    }
    new = []
    for family in families(branch, month):
        existing = current.get(family["cnic"])
        if existing and {i.voucher_id for i in existing.items.all()} == {v.id for v in family["vouchers"]}:
            kept.append(existing)
        else:
            new.append((family, existing))
    numbers = S.reserve_numbers(len(new))
    for family, existing in new:
        if existing:
            existing.status = FamilyVoucher.Status.REPLACED
            existing.save(update_fields=["status", "updated_at"])
        fv = FamilyVoucher.objects.create(
            branch=branch,
            number=next(numbers),
            father_cnic=family["cnic"],
            father_name=family["father"],
            phone=family["phone"],
            month=month,
            issued_on=today,
            due_on=min(v.due_on for v in family["vouchers"]),
            payable=family["payable"],
            late_fine=sum((v.late_fine for v in family["vouchers"]), S.ZERO),
            created_by=user,
        )
        FamilyVoucherItem.objects.bulk_create(
            FamilyVoucherItem(branch=branch, family_voucher=fv, voucher=v, amount=v.payable) for v in family["vouchers"]
        )
        made.append(fv)
    if made:
        AuditEvent.objects.create(
            actor=user,
            action=AuditEvent.Action.CREATE,
            model_label="fees.FamilyVoucher",
            object_id=f"batch:{month:%Y-%m}",
            object_repr=f"{len(made)} family vouchers {month:%b %Y}",
            branch_id=branch.id,
            changes={"numbers": [fv.number for fv in made], "kept": len(kept)},
        )
    return made, kept


def due_now(family_voucher, on_date=None):
    """Each child's amount due today (whole balance plus a pending late fine) and the family total. A child
    whose voucher was carried to a newer one is paid against the newer voucher."""
    rows = []
    for item in family_voucher.items.select_related("voucher__student", "voucher__section__class_level"):
        child = item.voucher.student
        voucher = S.latest_voucher(child) or item.voucher
        due, fine = S.amount_due_now(voucher, on_date)
        rows.append({"student": child, "voucher": voucher, "printed": item, "due": due, "fine": fine})
    return rows, sum((r["due"] for r in rows), S.ZERO)


@transaction.atomic
def receive(family_voucher, paid_on, method, user, bank=None, reference="", note="", attachment=None):
    """Pays every child's amount due in full. Returns the payments (none if nothing was owed)."""
    if family_voucher.status != FamilyVoucher.Status.OPEN:
        raise ValueError("This family voucher is not open.")
    rows, _total = due_now(family_voucher, paid_on)
    payments = []
    for r in rows:
        if r["due"] <= 0:
            continue
        payment = S.record_payment(
            r["student"],
            r["due"],
            paid_on,
            method,
            user,
            voucher=r["voucher"],
            reference=reference,
            note=(note or f"Family voucher {family_voucher.number}")[:200],
            bank=bank,
            attachment=attachment if not payments else None,  # the slip photo is kept once
            family_voucher=family_voucher,
        )
        payments.append(payment)
    family_voucher.status = FamilyVoucher.Status.PAID
    family_voucher.save(update_fields=["status", "updated_at"])
    return payments
