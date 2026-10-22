"""Academics → Hifz (M12): the day's Hifz sheet per section, each student's progress and para tests, and the
section progress report."""

import datetime as dt

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import Section
from apps.core import exports
from apps.core.branch import current_branch
from apps.organisation.models import AcademicSession
from apps.people.models import Student

from . import services as S
from .forms import LessonRow, ParaTestForm
from .models import PARAS, HifzLesson, ParaTest


def _branch(request, perm=S.VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _session():
    return AcademicSession.objects.filter(is_current=True).first()


def _day(value):
    today = timezone.localdate()
    try:
        return min(dt.date.fromisoformat(value), today) if value else today
    except ValueError:
        return today


@login_required
def index(request):
    branch = _branch(request)
    session = _session()
    date = _day(request.GET.get("date"))
    sections = S.sections(branch, session)
    done = {}
    for lesson in HifzLesson.objects.filter(branch=branch, date=date).values("section_id", "status"):
        d = done.setdefault(lesson["section_id"], {"saved": 0, "heard": 0})
        d["saved"] += 1
        d["heard"] += lesson["status"] == HifzLesson.Status.HEARD
    rows = [
        {
            "section": s,
            "students": len(S.roster(s)),
            "done": done.get(s.id, {"saved": 0, "heard": 0}),
            "can_record": S.can_record(request.user, s, date),
        }
        for s in sections
    ]
    students = S.hifz_students(branch, session)
    month = date.replace(day=1)
    passed = ParaTest.objects.filter(branch=branch, result=ParaTest.Result.PASSED, is_cancelled=False)
    complete = sum(1 for paras in S.passed_paras(students).values() if len(paras) == PARAS)
    return render(
        request,
        "hifz/index.html",
        {
            "branch": branch,
            "date": date,
            "is_today": date == timezone.localdate(),
            "previous_day": date - dt.timedelta(days=1),
            "next_day": date + dt.timedelta(days=1),
            "rows": rows,
            "kpi": {
                "students": students.count(),
                "heard": sum(r["done"]["heard"] for r in rows),
                "paras": passed.filter(before_joining=False, tested_on__gte=month, tested_on__lte=date).count(),
                "complete": complete,
            },
        },
    )


@login_required
def record(request, section_id, date):
    branch = _branch(request)
    day = _day(date)
    if day.isoformat() != date:
        raise Http404
    section = get_object_or_404(Section.objects.select_related("session", "class_level"), pk=section_id, branch=branch)
    if not S.can_record(request.user, section, day):
        raise PermissionDenied
    rows = S.sheet(section, day)
    forms = [LessonRow(request.POST or None, instance=r["lesson"], prefix=str(r["enrolment"].student_id)) for r in rows]
    if request.method == "POST":
        if all(f.is_valid() for f in forms):
            values = {
                r["enrolment"].student_id: {k: f.cleaned_data[k] for k in S.FIELDS}
                for r, f in zip(rows, forms, strict=True)
            }
            S.save_sheet(section, day, values, request.user)
            messages.success(request, _("Hifz sheet saved for %(section)s.") % {"section": section})
            return redirect(f"/hifz/?date={day.isoformat()}")
        messages.error(request, _("Please check the lines marked in red."))
    return render(
        request,
        "hifz/record.html",
        {
            "section": section,
            "date": day,
            "lines": list(zip(rows, forms, strict=True)),
            "already_saved": any(r["saved"] for r in rows),
        },
    )


@login_required
def student(request, student_id):
    branch = _branch(request)
    st = get_object_or_404(Student, pk=student_id, branch=branch)
    can_test = request.user.has_branch_perm(S.TEST_PERM, branch.id)
    passed = S.passed_paras([st]).get(st.id, {})
    form = ParaTestForm(
        request.POST or None,
        passed=passed,
        initial={"tested_on": timezone.localdate(), "result": ParaTest.Result.PASSED},
    )
    if request.method == "POST":
        if not can_test:
            raise PermissionDenied
        if form.is_valid():
            d = form.cleaned_data
            try:
                S.record_test(st, d["para"], d["tested_on"], d["result"], d["mistakes"], request.user,
                              d["before_joining"], d["remarks"])  # fmt: skip
            except ValueError:
                form.add_error("para", _("This para is already marked as passed."))
            else:
                messages.success(request, _("Para %(n)s test recorded.") % {"n": d["para"]})
                return redirect("hifz:student", student_id=st.id)
    today = timezone.localdate()
    start, end = _month_range(request, today)
    lessons = st.hifz_lessons.filter(date__gte=start, date__lte=end).select_related("recorded_by")
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Hifz record") + f" — {st.full_name} {start:%b %Y}",
            [_("Date"), _("Status"), _("Para"), _("Sabaq"), _("Lines"), _("Sabaq mistakes"), _("Sabqi"),
             _("Sabqi mistakes"), _("Manzil"), _("Manzil mistakes"), _("Grade"), _("Remarks")],
            ([x.date, x.get_status_display(), x.sabaq_para, x.sabaq, x.sabaq_lines, x.sabaq_mistakes, x.sabqi,
              x.sabqi_mistakes, x.manzil, x.manzil_mistakes, x.get_grade_display(), x.remarks] for x in lessons),
            branch=branch,
        )  # fmt: skip
    summary = S.progress([st], start, end)[0]
    return render(
        request,
        "hifz/student.html",
        {
            "student": st,
            "enrolment": S.enrolment(st, _session()),
            "grid": [(n, passed.get(n)) for n in range(1, PARAS + 1)],
            "summary": summary,
            "lessons": lessons,
            "tests": st.para_tests.select_related("tested_by").order_by("-tested_on", "-pk"),
            "form": form,
            "can_test": can_test,
            "month": start,
            "previous": (start - dt.timedelta(days=1)).replace(day=1),
            "next": (end + dt.timedelta(days=1)) if end < today else None,
        },
    )


def _month_range(request, today):
    try:
        y, m = (int(x) for x in request.GET.get("month", "").split("-"))
        start = dt.date(y, m, 1)
    except ValueError:
        start = today.replace(day=1)
    end = (start + dt.timedelta(days=32)).replace(day=1) - dt.timedelta(days=1)
    return start, end


@login_required
@require_POST
def cancel_test(request, student_id, test_id):
    branch = _branch(request, "hifz.change_paratest")
    test = get_object_or_404(ParaTest, pk=test_id, student_id=student_id, branch=branch, is_cancelled=False)
    S.cancel_test(test)
    messages.success(request, _("The para test is cancelled. It stays in the history."))
    return redirect("hifz:student", student_id=student_id)


@login_required
def report(request):
    branch = _branch(request)
    session = _session()
    sections = S.sections(branch, session)
    chosen = next((s for s in sections if str(s.id) == request.GET.get("section")), None)
    today = timezone.localdate()
    start, end = _month_range(request, today)
    if chosen:
        students = [e.student for e in S.roster(chosen)]
    else:
        students = list(S.hifz_students(branch, session).order_by("first_name", "last_name"))
    rows = S.progress(students, start, end)
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Hifz progress") + f" {start:%b %Y}" + (f" — {chosen}" if chosen else ""),
            [_("Admission no."), _("Name"), _("Paras memorised"), _("Current para"), _("Days heard"),
             _("Not ready"), _("Absent"), _("Lines of sabaq"), _("Average mistakes"), _("Last lesson")],
            ([r["student"].admission_no, r["student"].full_name, r["paras"], r["current"], r["heard"], r["not_ready"],
              r["absent"], r["lines"], r["mistakes"], r["last"]] for r in rows),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "hifz/report.html",
        {
            "branch": branch,
            "rows": rows,
            "sections": sections,
            "chosen": chosen,
            "month": start,
            "paras": PARAS,
        },
    )
