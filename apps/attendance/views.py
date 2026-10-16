"""Daily register screens: today's sections, taking the register, absentees, branch summary."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.academics.models import Section
from apps.core.branch import current_branch
from apps.organisation.models import AcademicSession, Branch
from apps.people.models import StudentGuardian

from . import services
from .models import AttendanceRecord, SectionAttendance, Status


def _date_from(request, value=None):
    today = timezone.localdate()
    raw = value or request.GET.get("date")
    if not raw:
        return today
    try:
        day = dt.date.fromisoformat(raw)
    except ValueError:
        return today
    return min(day, today)


def _branch(request):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(services.VIEW_PERM, branch.id):
        raise PermissionDenied
    return branch


def _session():
    return AcademicSession.objects.filter(is_current=True).first()


@login_required
def today(request):
    branch = _branch(request)
    session = _session()
    date = _date_from(request)
    sections = []
    if session:
        sections = list(
            services.in_school(Section.objects.filter(branch=branch, session=session, is_active=True), date)
            .select_related("class_level", "class_teacher", "campus", "session")
            .order_by("class_level__sort_order", "name")
        )
    registers = {r.section_id: r for r in SectionAttendance.objects.filter(branch=branch, date=date)}
    rows = []
    for s in sections:
        rows.append(
            {"section": s, "register": registers.get(s.id), "can_mark": services.can_mark(request.user, s, date)}
        )
    mine = [r for r in rows if r["section"].class_teacher_id == request.user.id]
    taken = [r["register"] for r in rows if r["register"]]
    totals = {
        "taken": len(taken),
        "sections": len(rows),
        "attended": sum(r.attended for r in taken),
        "absent": sum(r.absent for r in taken),
        "leave": sum(r.leave for r in taken),
        "students": sum(r.total for r in taken),
    }
    totals["rate"] = round(100 * totals["attended"] / totals["students"]) if totals["students"] else None
    return render(
        request,
        "attendance/today.html",
        {
            "date": date,
            "is_today": date == timezone.localdate(),
            "rows": rows,
            "mine": mine,
            "totals": totals,
            "session": session,
            "previous_day": date - dt.timedelta(days=1),
            "weekday": date.weekday(),
            "multi_branch": len(request.user.accessible_branch_ids(services.VIEW_PERM)) > 1,
            "next_day": date + dt.timedelta(days=1),
        },
    )


@login_required
def take_register(request, section_id, date):
    branch = _branch(request)
    day = _date_from(request, date)
    if day.isoformat() != date:
        raise Http404
    section = Section.objects.filter(pk=section_id, branch=branch).select_related("session", "class_level").first()
    if section is None:
        raise Http404
    if not services.can_mark(request.user, section, day):
        raise PermissionDenied
    entries = services.roster(section)
    existing = {
        r.student_id: r
        for r in AttendanceRecord.objects.filter(student_id__in=[e.student_id for e in entries], date=day)
    }

    if request.method == "POST":
        marks = {}
        for e in entries:
            status = request.POST.get(f"s{e.student_id}", Status.PRESENT)
            if status not in Status.values:
                status = Status.PRESENT
            marks[e.student_id] = (status, request.POST.get(f"n{e.student_id}", "").strip())
        register = services.save_register(section, day, marks, request.user)
        messages.success(
            request,
            _("Register saved for %(section)s: %(present)s present, %(absent)s absent.")
            % {"section": section, "present": register.attended, "absent": register.absent},
        )
        return redirect(f"/attendance/?date={day.isoformat()}")

    rows = [
        {
            "enrolment": e,
            "status": existing[e.student_id].status if e.student_id in existing else Status.PRESENT,
            "note": existing[e.student_id].note if e.student_id in existing else "",
        }
        for e in entries
    ]
    return render(
        request,
        "attendance/take.html",
        {
            "section": section,
            "date": day,
            "rows": rows,
            "statuses": Status.choices,
            "already_taken": bool(existing),
            "draft_key": f"tasems-att-{section.pk}-{day.isoformat()}",
        },
    )


@login_required
def absentees(request):
    branch = _branch(request)
    date = _date_from(request)
    records = list(
        AttendanceRecord.objects.filter(branch=branch, date=date)
        .exclude(status=Status.PRESENT)
        .select_related("student", "section__class_level")
        .order_by("section__class_level__sort_order", "section__name", "student__first_name")
    )
    ids = [r.student_id for r in records]
    contacts = {
        link.student_id: link.guardian
        for link in StudentGuardian.objects.filter(student_id__in=ids, is_primary_contact=True).select_related(
            "guardian"
        )
    }
    streaks = services.absence_streaks(ids, date)
    groups = {s: [] for s in (Status.ABSENT, Status.LEAVE, Status.LATE)}
    for r in records:
        groups[r.status].append(
            {"record": r, "contact": contacts.get(r.student_id), "streak": streaks.get(r.student_id, 0)}
        )
    return render(
        request,
        "attendance/absentees.html",
        {
            "date": date,
            "absent": groups[Status.ABSENT],
            "leave": groups[Status.LEAVE],
            "late": groups[Status.LATE],
            "long_absences": [g for g in groups[Status.ABSENT] if g["streak"] >= 3],
        },
    )


@login_required
def branches_summary(request):
    """Head office and regional view: which branches took registers, and attendance rates."""
    date = _date_from(request)
    branch_ids = request.user.accessible_branch_ids(services.VIEW_PERM)
    if len(branch_ids) < 2:
        return redirect("attendance:today")
    session = _session()
    section_counts = {}
    if session:
        for row in (
            services.in_school(Section.objects.filter(branch_id__in=branch_ids, session=session, is_active=True), date)
            .values("branch_id")
            .annotate(n=Count("id"))
        ):
            section_counts[row["branch_id"]] = row["n"]
    taken = {
        row["branch_id"]: row
        for row in SectionAttendance.objects.filter(branch_id__in=branch_ids, date=date)
        .values("branch_id")
        .annotate(
            registers=Count("id"),
            present=Sum("present"),
            late=Sum("late"),
            absent=Sum("absent"),
            leave=Sum("leave"),
        )
    }
    rows = []
    for b in Branch.objects.filter(id__in=branch_ids).select_related("head_office", "region").order_by("name"):
        t = taken.get(b.id)
        students = (t["present"] + t["late"] + t["absent"] + t["leave"]) if t else 0
        rows.append(
            {
                "branch": b,
                "sections": section_counts.get(b.id, 0),
                "registers": t["registers"] if t else 0,
                "absent": t["absent"] if t else 0,
                "rate": round(100 * (t["present"] + t["late"]) / students) if t and students else None,
            }
        )
    rows.sort(key=lambda r: (r["registers"] >= r["sections"] and r["sections"] > 0, r["branch"].name))
    return render(
        request,
        "attendance/branches.html",
        {"date": date, "rows": rows, "not_started": sum(1 for r in rows if r["sections"] and not r["registers"])},
    )
