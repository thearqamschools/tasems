"""Messages to parents without a paid SMS service (M8): a template is filled in for each student from TASEMS
records, then sent one by one with WhatsApp (a link opens the chat with the text ready) or downloaded as Excel for
the branch's own bulk SMS tool. Nothing is sent automatically."""

from decimal import Decimal
from urllib.parse import quote

from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

PLACEHOLDERS = [
    ("{student}", gettext_lazy("Student's name")),
    ("{father}", gettext_lazy("Father's name")),
    ("{class}", gettext_lazy("Class and section")),
    ("{amount_due}", gettext_lazy("Fees owed (Rs)")),
    ("{months_due}", gettext_lazy("Months of fee unpaid")),
    ("{date}", gettext_lazy("Today's date")),
    ("{branch}", gettext_lazy("Branch name")),
    ("{branch_phone}", gettext_lazy("Branch phone")),
    ("{text}", gettext_lazy("Your own words, typed below")),
]


def audiences(user, branch):
    """[(value, label)] the person may prepare messages for (each needs the page's own permission)."""
    out = []
    if user.has_branch_perm("fees.view_defaulters", branch.id):
        out.append(("defaulters", _("Parents of fee defaulters")))
    if user.has_branch_perm("attendance.view_attendancerecord", branch.id):
        out.append(("absent", _("Parents of students absent today")))
    if user.has_branch_perm("people.view_guardian", branch.id):
        out += [("section", _("Parents of one class")), ("all", _("All parents"))]
    return out


def _sections(student_ids):
    from apps.people.models import Enrolment

    return {
        e.student_id: e.section
        for e in Enrolment.objects.filter(student_id__in=student_ids, session__is_current=True).select_related(
            "section__class_level"
        )
    }


def recipients(branch, audience, *, min_months=1, section_id=None, today=None):
    """[{student, phone, section, amount_due, months_due}] — one row per student with a mobile number."""
    from apps.attendance.models import AttendanceRecord
    from apps.fees import reports
    from apps.fees.models import month_start
    from apps.people.models import Enrolment, Student

    today = today or timezone.localdate()
    owed = {}
    if audience == "defaulters":
        rows = [r for r in reports.outstanding(branch, as_of=month_start(today)) if r["months"] >= min_months]
        owed = {r["student_id"]: r for r in rows}
        ids = list(owed)
    elif audience == "absent":
        ids = list(
            AttendanceRecord.objects.filter(branch=branch, date=today, status="absent").values_list(
                "student_id", flat=True
            )
        )
    elif audience == "section" and section_id:
        ids = list(
            Enrolment.objects.filter(
                section_id=section_id, section__branch=branch, student__status="active"
            ).values_list("student_id", flat=True)
        )
    elif audience == "all":
        ids = list(Student.objects.filter(branch=branch, status="active").values_list("id", flat=True))
    else:
        ids = []
    students = Student.objects.filter(branch=branch, id__in=ids).order_by("first_name")
    phones = reports.guardian_phones(ids)
    sections = _sections(ids)
    out = []
    for s in students:
        if not phones.get(s.id):
            continue
        r = owed.get(s.id, {})
        out.append(
            {
                "student": s,
                "phone": phones[s.id],
                "section": sections.get(s.id),
                "amount_due": r.get("due", Decimal(0)),
                "months_due": r.get("months", 0),
            }
        )
    return out, len(ids) - len(out)


def ltr(value):
    """Numbers and phone numbers stay left-to-right inside an Urdu message (041-2660265 must not show as
    2660265-041): wrapped in invisible Unicode isolate marks, which phones and WhatsApp understand."""
    return f"\u2066{value}\u2069" if value else value


def fill(body, row, branch, text="", today=None):
    today = today or timezone.localdate()
    values = {
        "{student}": row["student"].full_name,
        "{father}": row["student"].father_name or "",
        "{class}": str(row["section"] or ""),
        "{amount_due}": ltr(f"{row['amount_due']:,.0f}"),
        "{months_due}": str(row["months_due"]),
        "{date}": ltr(f"{today:%d-%m-%Y}"),
        "{branch}": branch.name,
        "{branch_phone}": ltr(branch.phone),
        "{text}": text,
    }
    for key, value in values.items():
        body = body.replace(key, value)
    return body


def international(phone):
    """03001234567 → 923001234567 for WhatsApp links."""
    digits = "".join(ch for ch in phone if ch.isdigit())
    return "92" + digits[1:] if digits.startswith("0") else digits


def whatsapp_link(phone, text):
    return f"https://wa.me/{international(phone)}?text={quote(text)}"
