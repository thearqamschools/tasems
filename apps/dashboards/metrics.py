"""Figures for the role dashboards (Phase 4, M2).

Rules: branch figures reuse the module calculations so the dashboard and the module page always agree;
network figures read summary rows (`SectionAttendance`, D-022) and SQL totals grouped by branch, so the
number of queries does not grow with the number of branches.
"""

import datetime as dt
from collections import Counter
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils.formats import date_format

from apps.academics.models import Section
from apps.attendance.models import SectionAttendance
from apps.attendance.services import absence_streaks, in_school
from apps.diary.models import Diary
from apps.fees.models import Charge, Payment, add_months, month_start
from apps.people.models import Enrolment, Student

from .charts import column_chart, percent

ZERO = Decimal("0")
TREND_DAYS = 14


# ---------- Attendance ----------
def _register_totals(qs):
    t = qs.aggregate(p=Sum("present"), late=Sum("late"), a=Sum("absent"), lv=Sum("leave"), n=Count("id"))
    attended = (t["p"] or 0) + (t["late"] or 0)
    total = attended + (t["a"] or 0) + (t["lv"] or 0)
    return {"registers": t["n"], "attended": attended, "absent": t["a"] or 0, "leave": t["lv"] or 0, "total": total}


def attendance_trend(branch_ids, end):
    """Attendance % for the last 14 days on which any register was taken, ending on `end`."""
    rows = (
        SectionAttendance.objects.filter(
            branch_id__in=branch_ids, date__lte=end, date__gte=end - dt.timedelta(days=TREND_DAYS * 3)
        )
        .values("date")
        .annotate(p=Sum("present"), late=Sum("late"), a=Sum("absent"), lv=Sum("leave"))
        .order_by("-date")[:TREND_DAYS]
    )
    points = []
    for r in reversed(list(rows)):
        attended = r["p"] + r["late"]
        total = attended + r["a"] + r["lv"]
        rate = percent(attended, total)
        points.append(
            {
                "label": date_format(r["date"], "j M"),
                "title": date_format(r["date"], "l j M"),
                "value": rate,
                "text": f"{rate}%" if rate is not None else "—",
                "detail": f"{attended}/{total}",
            }
        )
    return column_chart(points, percent=True) if points else None


def classes_today(branch, session, today):
    """Class-wise attendance for today (strength, present, absent, leave, %) — every section in school today."""
    sections = list(
        in_school(Section.objects.filter(branch=branch, session=session, is_active=True), today)
        .select_related("class_level")
        .annotate(strength=Count("enrolments", filter=Q(enrolments__student__status=Student.Status.ACTIVE)))
        .order_by("class_level__sort_order", "name")
    )
    registers = {r.section_id: r for r in SectionAttendance.objects.filter(branch=branch, date=today)}
    rows = []
    for s in sections:
        r = registers.get(s.id)
        rows.append(
            {
                "section": s,
                "strength": s.strength,
                "register": r,
                "rate": percent(r.attended, r.total) if r else None,
            }
        )
    return rows


def branch_today(branch, session, today):
    totals = _register_totals(SectionAttendance.objects.filter(branch=branch, date=today))
    due = in_school(Section.objects.filter(branch=branch, session=session, is_active=True), today).count()
    return {**totals, "due": due, "rate": percent(totals["attended"], totals["total"])}


# ---------- Fees ----------
def fee_month(branch, today):
    """This month's fee position for one branch (same figures as the Fees page) and daily receipts."""
    from apps.fees import reports

    month = month_start(today)
    summary = reports.month_summary(branch, month)
    payments = Payment.objects.filter(branch=branch, is_reversed=False, paid_on__gte=month, paid_on__lte=today)
    by_day = dict(payments.values_list("paid_on").annotate(t=Sum("amount")))
    points = []
    day = month
    while day <= today:
        amount = by_day.get(day, ZERO)
        points.append(
            {
                "label": str(day.day),
                "title": date_format(day, "l j M"),
                "value": amount,
                "text": f"Rs {amount:,.0f}",
            }
        )
        day += dt.timedelta(days=1)
    today_rows = payments.filter(paid_on=today)
    return {
        **summary,
        "rate": percent(summary["collected"], summary["billed"]),
        "today_total": today_rows.aggregate(t=Sum("amount"))["t"] or ZERO,
        "today_count": today_rows.count(),
        "chart": column_chart(points, money=True),
    }


def network_fees(branch_ids, today):
    """Billed and received this month per branch, in two grouped queries."""
    month = month_start(today)
    nxt = add_months(month, 1)
    billed = dict(
        Charge.objects.filter(branch_id__in=branch_ids, month=month, is_cancelled=False)
        .values_list("branch_id")
        .annotate(t=Sum("amount"))
    )
    received = dict(
        Payment.objects.filter(branch_id__in=branch_ids, is_reversed=False, paid_on__gte=month, paid_on__lt=nxt)
        .values_list("branch_id")
        .annotate(t=Sum("amount"))
    )
    return billed, received


# ---------- Network (head office, regional director, branch owner with several branches) ----------
def network(branches, session, today, fee_branch_ids):
    ids = [b.id for b in branches]
    students = dict(
        Student.objects.filter(branch_id__in=ids, status=Student.Status.ACTIVE)
        .values_list("branch_id")
        .annotate(n=Count("id"))
    )
    att = {
        r["branch_id"]: r
        for r in SectionAttendance.objects.filter(branch_id__in=ids, date=today)
        .values("branch_id")
        .annotate(n=Count("id"), p=Sum("present"), late=Sum("late"), a=Sum("absent"), lv=Sum("leave"))
    }
    due, diaries = {}, {}
    if session:
        due = dict(
            in_school(Section.objects.filter(branch_id__in=ids, session=session, is_active=True), today)
            .values_list("branch_id")
            .annotate(n=Count("id"))
        )
        diaries = dict(
            Diary.objects.filter(branch_id__in=ids, date=today, status=Diary.Status.PUBLISHED)
            .values_list("branch_id")
            .annotate(n=Count("id"))
        )
    fee_ids = [i for i in ids if i in fee_branch_ids]
    billed, received = network_fees(fee_ids, today) if fee_ids else ({}, {})
    rows = []
    for b in branches:
        a = att.get(b.id)
        attended = (a["p"] + a["late"]) if a else 0
        total = attended + a["a"] + a["lv"] if a else 0
        has_fees = b.id in fee_branch_ids
        rows.append(
            {
                "branch": b,
                "students": students.get(b.id, 0),
                "registers": a["n"] if a else 0,
                "sections": due.get(b.id, 0),
                "attended": attended,
                "total": total,
                "rate": percent(attended, total),
                "diaries": diaries.get(b.id, 0),
                "has_fees": has_fees,
                "billed": billed.get(b.id, ZERO) if has_fees else None,
                "received": received.get(b.id, ZERO) if has_fees else None,
                "collection": percent(received.get(b.id, ZERO), billed.get(b.id, ZERO)) if has_fees else None,
            }
        )
    totals = {
        "branches": len(rows),
        "students": sum(r["students"] for r in rows),
        "registers": sum(r["registers"] for r in rows),
        "sections": sum(r["sections"] for r in rows),
        "attended": sum(r["attended"] for r in rows),
        "total": sum(r["total"] for r in rows),
        "diaries": sum(r["diaries"] for r in rows),
        "has_fees": bool(fee_ids),
        "billed": sum((r["billed"] or ZERO for r in rows), ZERO),
        "received": sum((r["received"] or ZERO for r in rows), ZERO),
    }
    totals["rate"] = percent(totals["attended"], totals["total"])
    totals["collection"] = percent(totals["received"], totals["billed"])
    return rows, totals


SORTS = {
    # Default: branches that still have registers to take first, then the largest.
    "attention": lambda r: (not (r["sections"] and r["registers"] < r["sections"]), -r["students"]),
    "students": lambda r: -r["students"],
    "attendance": lambda r: (r["rate"] is None, r["rate"] if r["rate"] is not None else 0),
    "collection": lambda r: (r["collection"] is None, r["collection"] if r["collection"] is not None else 0),
    "name": lambda r: r["branch"].name.lower(),
}


# ---------- Admissions ----------
def admissions(branch, today):
    from apps.admissions.models import Inquiry

    open_qs = Inquiry.objects.filter(branch=branch, status__in=Inquiry.OPEN)
    start = today.replace(day=1)
    by_status = Counter(dict(open_qs.values_list("status").annotate(n=Count("id"))))
    labels = dict(Inquiry.Status.choices)
    pipeline = [(labels[s], by_status.get(s, 0)) for s in Inquiry.OPEN]
    most = max((n for _l, n in pipeline), default=0)
    return {
        "due": open_qs.filter(next_follow_up__lte=today).count(),
        "visits": open_qs.filter(visit_at__date=today).count(),
        "new": Inquiry.objects.filter(branch=branch, created_at__date__gte=start).count(),
        "admitted": Inquiry.objects.filter(branch=branch, status=Inquiry.Status.ADMITTED, closed_on__gte=start).count(),
        "pipeline": [(label, n, round(100 * n / most) if most else 0) for label, n in pipeline],
        "open": sum(by_status.values()),
    }


# ---------- Staff ----------
def staff_today(branch, today):
    from apps.hr import services as hr

    _rows, counts = hr.day_summary(branch, today)
    total = sum(v for k, v in counts.items() if k != "in")
    return {
        "in": counts.get("in", 0),
        "late": counts.get("late", 0),
        "absent": counts.get("absent", 0),
        "leave": counts.get("leave", 0),
        "none": counts.get("none", 0),
        "total": total,
    }


def my_month(employee, today):
    from apps.hr.models import StaffDay

    counts = Counter(
        dict(
            StaffDay.objects.filter(employee=employee, date__gte=today.replace(day=1), date__lte=today)
            .values_list("status")
            .annotate(n=Count("id"))
        )
    )
    return {
        "present": counts.get("present", 0) + counts.get("half_day", 0),
        "late": counts.get("late", 0),
        "absent": counts.get("absent", 0),
        "leave": counts.get("leave", 0),
    }


# ---------- Class teacher ----------
def my_classes(user, branch, sections, today):
    """For each of the teacher's sections: today's register and diary, and students absent 3+ days in a row."""
    from apps.attendance.services import can_mark
    from apps.diary.services import can_edit

    ids = [s.id for s in sections]
    registers = {r.section_id: r for r in SectionAttendance.objects.filter(section_id__in=ids, date=today)}
    diaries = {d.section_id: d for d in Diary.objects.filter(section_id__in=ids, date=today)}
    enrolments = list(
        Enrolment.objects.filter(section_id__in=ids, student__status=Student.Status.ACTIVE).select_related("student")
    )
    streaks = absence_streaks([e.student_id for e in enrolments], today)
    worrying = {}
    for e in enrolments:
        if streaks.get(e.student_id, 0) >= 3:
            worrying.setdefault(e.section_id, []).append((e.student, streaks[e.student_id]))
    out = []
    for s in sections:
        out.append(
            {
                "section": s,
                "register": registers.get(s.id),
                # Links are offered only when the page will accept them (same rules as the pages).
                "can_take": s.branch_id == branch.id and can_mark(user, s, today),
                "can_write_diary": s.branch_id == branch.id and can_edit(user, s, today),
                "diary": diaries.get(s.id),
                "streaks": sorted(worrying.get(s.id, []), key=lambda x: -x[1]),
            }
        )
    return out
