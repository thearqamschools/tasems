# ruff: noqa: E501  (a catalogue of report titles and one-line descriptions reads best one report per line)
"""The reports centre (M6): for each module, four figures and the printable reports a person may open.

Every figure reuses the module's own calculation (dashboards.metrics or the module's reports), and every
report is listed with the permission its page checks, so the centre never leads to a refusal."""

import datetime as dt
from dataclasses import dataclass, field

from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.dashboards import metrics
from apps.dashboards.charts import percent
from apps.fees.models import month_start
from apps.people.models import Student


@dataclass
class Report:
    title: str
    text: str
    url: str


@dataclass
class Module:
    key: str
    title: str
    icon: str
    figures: list = field(default_factory=list)  # (value, label, tone, money)
    reports: list = field(default_factory=list)


def _students(branch, session, today):
    active = Student.objects.filter(branch=branch, status=Student.Status.ACTIVE)
    counts = active.aggregate(
        total=Count("id"),
        boys=Count("id", filter=Q(gender="male")),
        girls=Count("id", filter=Q(gender="female")),
        hifz=Count("id", filter=Q(is_hifz=True)),
    )
    new = Student.objects.filter(branch=branch, admission_date__gte=today.replace(day=1)).count()
    return [
        (counts["total"], _("Active students"), "", False),
        (counts["boys"], _("Boys"), "", False),
        (counts["girls"], _("Girls"), "", False),
        (new, _("New admissions this month"), "", False),
    ]


def build(user, branch, session, today):
    """The modules this person can see in `branch`, in menu order."""

    def perm(name):
        return user.has_branch_perm(name, branch.id)

    month = month_start(today)
    modules = []

    if perm("people.view_student"):
        modules.append(
            Module(
                "students",
                _("Students"),
                "users",
                _students(branch, session, today),
                [
                    Report(_("Students list"), _("Every student with class, section, father and mobile; filter by class."), reverse("people:student_list")),
                    Report(_("Class strength"), _("Boys, girls and Hifz students in every class and section."), reverse("reports:class_strength")),
                    *([Report(_("Students needing attention"), _("Absences in a row, low attendance, falling marks, unpaid fees, Hifz not ready."), reverse("insights:attention"))]
                      if perm("attendance.view_attendancerecord") else []),
                    Report(_("New admissions"), _("Students admitted between two dates."), reverse("reports:new_admissions")),
                    Report(_("Students who left"), _("Withdrawn, transferred and graduated students."), reverse("people:student_list") + "?status=withdrawn"),
                ],
            )
        )  # fmt: skip

    if perm("attendance.view_attendancerecord"):
        t = metrics.branch_today(branch, session, today) if session else None
        figures = []
        if t:
            figures = [
                (f"{t['registers']}/{t['due']}", _("Registers taken today"), "attention" if t["registers"] < t["due"] else "ok", False),
                (f"{t['rate']}%" if t["rate"] is not None else "—", _("Attendance today"), "", False),
                (t["absent"], _("Absent today"), "attention" if t["absent"] else "", False),
                (t["leave"], _("On leave today"), "", False),
            ]  # fmt: skip
        items = [
            Report(_("Today's attendance"), _("Every class with present, absent and leave, and who has not taken the register."), reverse("attendance:today")),
            Report(_("Absent students"), _("Absent, on leave and late students with parents' mobiles; 3+ days in a row first."), reverse("attendance:absentees")),
            Report(_("Monthly attendance by class"), _("Days the register was taken, attendance percentage and absences for each class."), reverse("reports:attendance_month")),
        ]  # fmt: skip
        if len(user.accessible_branch_ids("attendance.view_attendancerecord")) > 1:
            items.append(
                Report(
                    _("All my branches"),
                    _("Registers taken and attendance percentage for each branch."),
                    reverse("attendance:branches"),
                )
            )
        modules.append(Module("attendance", _("Attendance"), "calendar-check", figures, items))

    if perm("fees.view_voucher"):
        f = metrics.fee_month(branch, today)
        items = [
            Report(_("Month summary"), _("Billed, received and still owed this month; received today by Cash and Bank."), reverse("fees:index")),
            Report(_("Vouchers"), _("Vouchers of a month by class and status; print them all as PDF."), reverse("fees:vouchers")),
            Report(_("Family vouchers"), _("All children of one father on one voucher with one Voucher ID; print and receive."), reverse("fees:family_vouchers")),
            Report(_("Defaulters"), _("Students with unpaid months, oldest first."), reverse("fees:defaulters")),
            Report(_("Defaulters by family"), _("One row per father with every child and the family total."), reverse("fees:defaulters") + "?by=family"),
            Report(_("Daily collection"), _("Every payment between two dates, who received it, Cash or which Bank."), reverse("fees:collections")),
            Report(_("Special discounts"), _("Discounts waiting for approval and decided."), reverse("fees:concessions")),
        ]  # fmt: skip
        if user.accessible_branch_ids("fees.view_royalty"):
            items.append(
                Report(
                    _("Royalty statement"),
                    _("Each branch's royalty, paid, pending and total due."),
                    reverse("fees:royalty"),
                )
            )
        modules.append(
            Module(
                "fees",
                _("Fees"),
                "wallet",
                [
                    (f["billed"], _("Billed this month (Rs)"), "", True),
                    (f["collected"], _("Received this month (Rs)"), "", True),
                    (f"{f['rate']}%" if f["rate"] is not None else "—", _("Collected"), "", False),
                    (f["today_total"], _("Received today (Rs)"), "", True),
                ],
                items,
            )
        )

    if perm("admissions.view_inquiry"):
        a = metrics.admissions(branch, today)
        modules.append(
            Module(
                "admissions",
                _("Admissions"),
                "user-plus",
                [
                    (a["due"], _("Follow-ups due today"), "attention" if a["due"] else "", False),
                    (a["open"], _("Open inquiries"), "", False),
                    (a["new"], _("New this month"), "", False),
                    (a["admitted"], _("Admitted this month"), "ok" if a["admitted"] else "", False),
                ],
                [
                    Report(_("Admission inquiries"), _("Every inquiry with its next follow-up."), reverse("admissions:index")),
                    Report(_("Admissions report"), _("Inquiries and admissions by source, class and status between two dates."), reverse("admissions:report")),
                ],
            )
        )  # fmt: skip

    if perm("exams.view_mark"):
        modules.append(
            Module(
                "exams",
                _("Exams & Results"),
                "graduation-cap",
                [],
                [
                    Report(_("Results by class"), _("Marks entered, result sheets and printed result cards for each class."), reverse("exams:index")),
                    Report(_("Date sheets, exam slips and award lists"), _("Open an exam for its date sheet; open a class for exam slips with photo and award lists."), reverse("exams:index")),
                ],
            )
        )  # fmt: skip

    if perm("hifz.view_hifzlesson"):
        from apps.hifz import services as hifz
        from apps.hifz.models import PARAS, HifzLesson

        students = hifz.hifz_students(branch, session)
        heard = HifzLesson.objects.filter(branch=branch, date=today, status=HifzLesson.Status.HEARD).count()
        complete = sum(1 for p in hifz.passed_paras(students).values() if len(p) == PARAS)
        modules.append(
            Module(
                "hifz",
                _("Hifz-e-Quran"),
                "book-open",
                [
                    (students.count(), _("Hifz students"), "", False),
                    (heard, _("Sabaq heard today"), "", False),
                    (complete, _("Hifz completed (30 paras)"), "ok" if complete else "", False),
                ],
                [
                    Report(_("Hifz sheet of the day"), _("Each Hifz section: recorded or not, sabaq heard."), reverse("hifz:index")),
                    Report(_("Hifz progress"), _("Paras memorised, current para, days heard, not ready and mistakes for any month."), reverse("hifz:report")),
                ],
            )
        )  # fmt: skip

    if perm("academics.view_section"):
        modules.append(
            Module(
                "academics",
                _("Timetable and calendar"),
                "clock",
                [],
                [
                    Report(
                        _("Timetable"),
                        _("Each class's week and each teacher's week; clashes are shown."),
                        reverse("academics:index"),
                    ),
                    Report(
                        _("Holiday calendar"),
                        _("Holidays of this session for students and staff."),
                        reverse("academics:holidays"),
                    ),
                ],
            )
        )

    if perm("hr.view_employee"):
        s = metrics.staff_today(branch, today)
        modules.append(
            Module(
                "staff",
                _("Staff"),
                "briefcase",
                [
                    (s["in"], _("In today"), "", False),
                    (s["late"], _("Late today"), "attention" if s["late"] else "", False),
                    (s["leave"], _("On leave today"), "", False),
                    (s["none"], _("Not in yet"), "", False),
                ],
                [
                    Report(_("Staff list"), _("Staff with designation, mobile and machine ID."), reverse("hr:index")),
                    Report(_("Staff attendance today"), _("Time in and out, late and absent staff."), reverse("hr:day")),
                    Report(_("Monthly sheet"), _("Every staff member's month, day by day, with unpaid days for payroll."), reverse("hr:month")),
                    Report(_("Leave"), _("Leave waiting for approval and decided."), reverse("hr:leaves")),
                    *([Report(_("Payroll"), _("Each staff member's salary, days cut and net pay; payslips and bank sheet."), reverse("payroll:index"))]
                      if perm("payroll.view_payrollrun") else []),
                ],
            )
        )  # fmt: skip

    if perm("accounting.view_expense"):
        from apps.accounting.models import Expense
        from apps.fees.models import add_months

        live = Expense.objects.filter(branch=branch, is_cancelled=False, date__gte=month, date__lt=add_months(month, 1))
        totals = live.aggregate(
            t=Sum("amount"),
            cash=Sum("amount", filter=Q(paid_from="cash")),
            bank=Sum("amount", filter=Q(paid_from="bank")),
        )
        modules.append(
            Module(
                "expenses",
                _("Expenses"),
                "receipt",
                [
                    (totals["t"] or 0, _("Spent this month (Rs)"), "", True),
                    (totals["cash"] or 0, _("From cash (Rs)"), "", True),
                    (totals["bank"] or 0, _("From bank (Rs)"), "", True),
                ],
                [
                    Report(_("Expenses of the month"), _("Every expense with head, paid to, cash or bank; totals by head."), reverse("accounting:index")),
                    Report(_("Other income"), _("Money received other than fees, by head."), reverse("accounting:incomes")),
                    Report(_("Cash & bank book"), _("Cash in hand and each bank: opening balance, money in and out, running balance."), reverse("accounting:book")),
                    Report(_("Profit & loss"), _("Fees received and other income, less expenses, for any dates."), reverse("accounting:profit_loss")),
                ],
            )
        )  # fmt: skip

    if perm("inventory.view_item"):
        from apps.inventory import services as stock
        from apps.inventory.models import Sale

        rows = stock.stock_rows(branch)
        sold = Sale.objects.filter(branch=branch, is_cancelled=False, date__gte=month, date__lte=today)
        modules.append(
            Module(
                "stock",
                _("Shop & stock"),
                "package",
                [
                    (sum(r["value"] for r in rows), _("Stock value at sale price (Rs)"), "", True),
                    (sum(1 for r in rows if r["low"]), _("Low stock"), "attention" if any(r["low"] for r in rows) else "", False),
                    (sum(1 for r in rows if r["out"]), _("Out of stock"), "danger" if any(r["out"] for r in rows) else "", False),
                    (sold.aggregate(t=Sum("total"))["t"] or 0, _("Sold this month (Rs)"), "", True),
                ],
                [
                    Report(_("Stock in hand"), _("Every item with stock, sale price and value; low and out of stock."), reverse("inventory:index")),
                    Report(_("Sales"), _("Each sale with how it was paid, and totals by item, for any dates."), reverse("inventory:sales")),
                ],
            )
        )  # fmt: skip
    return modules


def attendance_rows(branch, session, month, next_month):
    """Each section's month: register days, attendance %, absences and leave (from the register summaries)."""
    from apps.academics.models import Section
    from apps.attendance.models import SectionAttendance

    sections = list(
        Section.objects.filter(branch=branch, session=session, is_active=True)
        .select_related("class_level")
        .order_by("class_level__sort_order", "name")
    )
    totals = {
        r["section_id"]: r
        for r in SectionAttendance.objects.filter(branch=branch, date__gte=month, date__lt=next_month)
        .values("section_id")
        .annotate(days=Count("id"), p=Sum("present"), late=Sum("late"), a=Sum("absent"), lv=Sum("leave"))
    }
    rows = []
    for s in sections:
        t = totals.get(s.id)
        attended = (t["p"] + t["late"]) if t else 0
        total = attended + (t["a"] + t["lv"] if t else 0)
        rows.append(
            {
                "section": s,
                "days": t["days"] if t else 0,
                "rate": percent(attended, total),
                "absent": t["a"] if t else 0,
                "leave": t["lv"] if t else 0,
                "late": t["late"] if t else 0,
            }
        )
    return rows


def month_bounds(value, today):
    try:
        month = dt.date.fromisoformat(f"{value}-01") if value else today.replace(day=1)
    except ValueError:
        month = today.replace(day=1)
    from apps.fees.models import add_months

    return month, add_months(month, 1)
