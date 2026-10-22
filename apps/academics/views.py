"""Timetable, subject teachers and bell times (M7)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.forms import modelformset_factory
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from apps.core.branch import current_branch
from apps.organisation.models import AcademicSession

from . import timetable as T
from .forms import PeriodForm
from .models import Period, Section, Subject

VIEW_PERM, EDIT_PERM = "academics.view_section", "academics.change_section"


def _branch(request, perm=VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _session():
    return AcademicSession.objects.filter(is_current=True).first()


def _section(branch, section_id):
    section = Section.objects.filter(pk=section_id, branch=branch).select_related("class_level", "session").first()
    if section is None:
        raise Http404
    return section


@login_required
def index(request):
    branch = _branch(request)
    session = _session()
    sections = (
        Section.objects.filter(branch=branch, session=session, is_active=True)
        .select_related("class_level", "class_teacher")
        .annotate(cells=Count("timetable", distinct=True), subjects=Count("subject_teachers__teacher", distinct=True))
        .order_by("class_level__sort_order", "name")
        if session
        else []
    )
    teachers = T.teachers_of(branch).filter(subject_sections__section__session=session).distinct() if session else []
    return render(
        request,
        "academics/index.html",
        {
            "branch": branch,
            "session": session,
            "sections": sections,
            "teachers": teachers,
            "periods": Period.objects.filter(branch=branch),
            "clashes": T.clashes(branch, session) if session else [],
            "can_edit": request.user.has_branch_perm(EDIT_PERM, branch.id),
        },
    )


@login_required
def periods(request):
    branch = _branch(request, EDIT_PERM)
    PeriodFormSet = modelformset_factory(Period, form=PeriodForm, extra=3, can_delete=True)
    formset = PeriodFormSet(request.POST or None, queryset=Period.objects.filter(branch=branch))
    if request.method == "POST" and formset.is_valid():
        for form in formset.forms:
            form.instance.branch = branch
        formset.save()
        messages.success(request, _("Bell times saved."))
        return redirect("academics:index")
    return render(request, "academics/periods.html", {"formset": formset, "branch": branch})


@login_required
def section_subjects(request, section_id):
    branch = _branch(request)
    section = _section(branch, section_id)
    can_edit = request.user.has_branch_perm(EDIT_PERM, branch.id)
    rows = T.subjects_of(section)
    teachers = list(T.teachers_of(branch))
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        by_id = {t.id: t for t in teachers}
        chosen = {}
        for subject, _teacher in rows:
            value = request.POST.get(f"s_{subject.id}", "")
            if value and int(value) not in by_id:
                raise PermissionDenied  # only people of this branch can be chosen
            chosen[subject] = by_id.get(int(value)) if value else None
        extra = request.POST.get("add_subject")
        if extra:
            subject = Subject.objects.filter(pk=extra, is_active=True).first()
            if subject and subject not in chosen:
                chosen[subject] = by_id.get(int(request.POST.get("add_teacher") or 0))
        T.save_subject_teachers(section, chosen, request.user)
        messages.success(request, _("Subject teachers saved for %(s)s.") % {"s": section})
        return redirect("academics:section_subjects", section_id=section.id)
    taken = {s.id for s, _t in rows}
    return render(
        request,
        "academics/section_subjects.html",
        {
            "section": section,
            "rows": rows,
            "teachers": teachers,
            "can_edit": can_edit,
            "other_subjects": Subject.objects.filter(is_active=True).exclude(pk__in=taken),
        },
    )


@login_required
def section_timetable(request, section_id):
    branch = _branch(request)
    section = _section(branch, section_id)
    can_edit = request.user.has_branch_perm(EDIT_PERM, branch.id)
    subjects = [s for s, _t in T.subjects_of(section)]
    editing = can_edit and (request.GET.get("edit") == "1" or request.method == "POST")
    errors = []
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        by_id = {s.id: s for s in subjects}
        cells = {}
        for p in Period.objects.filter(branch=branch, is_break=False):
            for day, _label in T.days_of(section):
                value = request.POST.get(f"c_{day}_{p.id}", "")
                cells[(day, p.id)] = by_id.get(int(value)) if value.isdigit() else None
        try:
            T.save_grid(section, cells, request.user)
        except ValueError as exc:
            errors = exc.args[0]
        else:
            messages.success(request, _("Timetable saved for %(s)s.") % {"s": section})
            return redirect("academics:section_timetable", section_id=section.id)
    return render(
        request,
        "academics/section_timetable.html",
        {
            "section": section,
            "grid": T.grid(section),
            "subjects": subjects,
            "editing": editing,
            "errors": errors,
            "can_edit": can_edit,
            "missing_teachers": [s for s, t in T.subjects_of(section) if t is None],
        },
    )


def _teacher_page(request, branch, teacher, mine=False):
    session = _session()
    return render(
        request,
        "academics/teacher_timetable.html",
        {"teacher": teacher, "grid": T.teacher_grid(branch, session, teacher) if session else None, "mine": mine},
    )


@login_required
def teacher_timetable(request, user_id):
    branch = _branch(request)
    teacher = T.teachers_of(branch).filter(pk=user_id).first()
    if teacher is None:
        raise Http404
    return _teacher_page(request, branch, teacher)


@login_required
def my_timetable(request):
    branch = _branch(request)
    return _teacher_page(request, branch, request.user, mine=True)


# --- Holiday calendar (M7) -------------------------------------------------------------------

HOLIDAY_ADD, HOLIDAY_CHANGE = "hr.add_holiday", "hr.change_holiday"


def _network_holidays_allowed(user):
    from apps.accounts.models import RoleAssignment, Scope

    return (
        user.is_superuser
        or RoleAssignment.objects.filter(
            user=user, is_active=True, scope=Scope.NETWORK, role__permissions__codename="add_holiday"
        ).exists()
    )


@login_required
def holidays(request):
    import datetime as dt

    from django.db.models import Q

    from apps.core.models import AuditEvent
    from apps.hr.models import Holiday

    from .forms import HolidayForm

    branch = _branch(request)
    session = _session()
    can_add = request.user.has_branch_perm(HOLIDAY_ADD, branch.id)
    network = _network_holidays_allowed(request.user)
    form = HolidayForm(request.POST or None, network=network)
    if request.method == "POST" and "remove" in request.POST:
        holiday = (
            Holiday.objects.filter(pk=request.POST["remove"]).filter(Q(branch=branch) | Q(branch__isnull=True)).first()
        )
        if holiday is None or not (
            request.user.has_branch_perm(HOLIDAY_CHANGE, branch.id) if holiday.branch_id else network
        ):
            raise PermissionDenied
        holiday.delete()
        messages.success(
            request, _("Holiday removed: %(d)s %(n)s.") % {"d": f"{holiday.date:%d %b %Y}", "n": holiday.name}
        )
        return redirect("academics:holidays")
    if request.method == "POST":
        if not can_add:
            raise PermissionDenied
        if form.is_valid():
            d = form.cleaned_data
            target = None if d.get("everywhere") else branch
            day, added, skipped = d["starts_on"], 0, 0
            while day <= d["ends_on"]:
                _h, created = Holiday.objects.get_or_create(
                    branch=target,
                    date=day,
                    defaults={"name": d["name"], "students_off": d["students_off"], "staff_off": d["staff_off"]},
                )
                added, skipped = added + created, skipped + (not created)
                day += dt.timedelta(days=1)
            AuditEvent.objects.create(
                actor=request.user,
                action=AuditEvent.Action.CREATE,
                model_label="hr.Holiday",
                object_id=f"{d['starts_on']}..{d['ends_on']}",
                object_repr=d["name"][:255],
                branch_id=target.id if target else None,
                changes={"days": added, "students_off": d["students_off"], "staff_off": d["staff_off"]},
            )
            messages.success(
                request,
                _("%(n)s holiday days added; %(s)s days already had a holiday.") % {"n": added, "s": skipped},
            )
            return redirect("academics:holidays")
    start = session.starts_on if session else dt.date.today().replace(month=1, day=1)
    end = session.ends_on if session else start.replace(year=start.year + 1)
    rows = list(
        Holiday.objects.filter(Q(branch=branch) | Q(branch__isnull=True), date__gte=start, date__lte=end).order_by(
            "date", "branch_id"
        )
    )
    for h in rows:
        h.can_remove = request.user.has_branch_perm(HOLIDAY_CHANGE, branch.id) if h.branch_id else network
    return render(
        request,
        "academics/holidays.html",
        {
            "branch": branch,
            "session": session,
            "rows": rows,
            "form": form,
            "can_add": can_add,
            "today": dt.date.today(),
        },
    )
