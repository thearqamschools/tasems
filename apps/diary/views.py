"""Daily Diary screens: sections for a day, writing a diary, preview, PDF and WhatsApp image."""

import datetime as dt

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from apps.academics.models import Section
from apps.attendance.services import in_school
from apps.core.branch import current_branch
from apps.organisation.models import AcademicSession

from . import services
from .models import Diary, DiaryWeek


def _branch(request):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(services.VIEW_PERM, branch.id):
        raise PermissionDenied
    return branch


def _parse_date(raw, default=None):
    try:
        return dt.date.fromisoformat(raw)
    except (TypeError, ValueError):
        return default


class WeekForm(forms.ModelForm):
    class Meta:
        model = DiaryWeek
        fields = ["week_number", "theme", "theme_ur", "quote"]
        widgets = {"theme_ur": forms.TextInput(attrs={"dir": "rtl", "lang": "ur", "class": "ur"})}
        labels = {"week_number": gettext_lazy("Week number")}


@login_required
def day(request):
    branch = _branch(request)
    today = timezone.localdate()
    date = _parse_date(request.GET.get("date"), today)
    session = AcademicSession.objects.filter(is_current=True).first()
    sections = []
    if session:
        sections = list(
            in_school(Section.objects.filter(branch=branch, session=session, is_active=True), date)
            .select_related("class_level", "class_teacher", "session")
            .order_by("class_level__sort_order", "name")
        )
    diaries = {d.section_id: d for d in Diary.objects.filter(branch=branch, date=date)}
    rows = [
        {"section": s, "diary": diaries.get(s.id), "can_edit": services.can_edit(request.user, s, date)}
        for s in sections
    ]

    monday = date - dt.timedelta(days=date.weekday())
    can_set_week = request.user.has_branch_perm("diary.change_diaryweek", branch.id)
    week = DiaryWeek.objects.filter(branch=branch, starts_on=monday).first()
    week_form = None
    if can_set_week:
        week_form = WeekForm(request.POST or None, instance=week or DiaryWeek(branch=branch, starts_on=monday))
        if request.method == "POST" and week_form.is_valid():
            week_form.save()
            messages.success(request, _("Theme of the week saved."))
            return redirect(f"/diary/?date={date.isoformat()}")
    return render(
        request,
        "diary/day.html",
        {
            "date": date,
            "rows": rows,
            "mine": [r for r in rows if r["section"].class_teacher_id == request.user.id],
            "week": services.week_info(branch, date),
            "week_form": week_form,
            "previous_day": date - dt.timedelta(days=1),
            "next_day": date + dt.timedelta(days=1),
            "is_today": date == today,
            "weekday": date.weekday(),
            "session": session,
        },
    )


@login_required
def write(request, section_id, date):
    branch = _branch(request)
    day_ = _parse_date(date)
    if day_ is None:
        raise Http404
    section = Section.objects.filter(pk=section_id, branch=branch).select_related("session", "class_level").first()
    if section is None:
        raise Http404
    if not services.can_edit(request.user, section, day_):
        raise PermissionDenied
    diary = Diary.objects.filter(section=section, date=day_).first()
    existing = {e.subject_id: e for e in diary.entries.all()} if diary else {}
    default_deadline = services.next_school_day(section.class_level, day_, section.branch_id)

    subjects = services.subjects_for(section)
    if request.method == "POST":
        entries = {}
        for subject, _order in subjects:
            entries[subject.id] = {
                "in_class": request.POST.get(f"c{subject.id}", ""),
                "home_task": request.POST.get(f"h{subject.id}", ""),
                "deadline": _parse_date(request.POST.get(f"d{subject.id}"), default_deadline),
            }
        publish = "publish" in request.POST
        diary = services.save_diary(section, day_, request.user, entries, publish=publish)
        if not diary.entries.exists():
            messages.warning(request, _("The diary is empty. Write at least one subject."))
            return redirect(request.path)
        messages.success(request, _("Diary published.") if publish else _("Diary saved as a draft."))
        return redirect("diary:view", pk=diary.pk)

    rows = []
    for subject, _order in subjects:
        e = existing.get(subject.id)
        rows.append(
            {
                "subject": subject,
                "in_class": e.in_class if e else "",
                "home_task": e.home_task if e else "",
                "deadline": (e.deadline if e and e.deadline else default_deadline).isoformat(),
            }
        )
    return render(request, "diary/write.html", {"section": section, "date": day_, "rows": rows, "diary": diary})


def _visible_diary(request, pk):
    branch = _branch(request)
    diary = Diary.objects.filter(pk=pk, branch=branch).select_related("section__class_level", "branch").first()
    if diary is None:
        raise Http404
    return diary


@login_required
def view(request, pk):
    diary = _visible_diary(request, pk)
    context = services.document_context(diary)
    context["can_edit"] = services.can_edit(request.user, diary.section, diary.date)
    return render(request, "diary/view.html", context)


def _filename(diary, ext):
    return f"Diary-{str(diary.section).replace(' ', '')}-{diary.date.isoformat()}.{ext}"


@login_required
def pdf(request, pk):
    diary = _visible_diary(request, pk)
    response = HttpResponse(services.render_pdf(diary), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{_filename(diary, "pdf")}"'
    return response


@login_required
def image(request, pk):
    diary = _visible_diary(request, pk)
    response = HttpResponse(services.render_image(diary), content_type="image/png")
    response["Content-Disposition"] = f'attachment; filename="{_filename(diary, "png")}"'
    return response
