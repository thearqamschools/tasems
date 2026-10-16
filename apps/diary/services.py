"""Daily Diary rules and rendering (PDF for printing, one tall image for WhatsApp)."""

import datetime as dt
import io
import re

from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.academics.models import CurriculumSubject, Subject
from apps.attendance.services import is_school_day

from .models import Diary, DiaryEntry, DiaryLayout, DiaryWeek

ADD_PERM = "diary.add_diary"
CHANGE_PERM = "diary.change_diary"
VIEW_PERM = "diary.view_diary"
PLAN_AHEAD_DAYS = 7
URDU = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


def is_urdu(text):
    """True when the text is mostly in Urdu/Arabic script, so it must be set right-to-left."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    return sum(1 for ch in letters if URDU.match(ch)) / len(letters) > 0.5


def subjects_for(section):
    """Subjects of this class from the curriculum; all active subjects if none are mapped yet."""
    mapped = list(
        CurriculumSubject.objects.filter(class_level=section.class_level, subject__is_active=True)
        .select_related("subject")
        .order_by("sort_order")
    )
    if mapped:
        return [(m.subject, m.sort_order) for m in mapped]
    return [(s, i) for i, s in enumerate(Subject.objects.filter(is_active=True).order_by("name"))]


def next_school_day(class_level, date):
    day = date + dt.timedelta(days=1)
    for _ in range(14):
        if is_school_day(class_level, day):
            return day
        day += dt.timedelta(days=1)
    return date + dt.timedelta(days=1)


def can_edit(user, section, date):
    """Class teachers write their own sections' diaries for today or up to a week ahead;
    principals and coordinators can write or correct any section, any school day of the session."""
    session = section.session
    if date < session.starts_on or date > session.ends_on or not is_school_day(section.class_level, date):
        return False
    if user.has_branch_perm(CHANGE_PERM, section.branch_id):
        return True
    today = timezone.localdate()
    return (
        section.class_teacher_id == user.id
        and user.has_branch_perm(ADD_PERM, section.branch_id)
        and today <= date <= today + dt.timedelta(days=PLAN_AHEAD_DAYS)
    )


def week_info(branch, date):
    monday = date - dt.timedelta(days=date.weekday())
    return (
        DiaryWeek.objects.filter(starts_on=monday, branch=branch).first()
        or DiaryWeek.objects.filter(starts_on=monday, branch__isnull=True).first()
    )


@transaction.atomic
def save_diary(section, date, user, entries, publish=False):
    """`entries` maps subject id → dict(in_class, home_task, deadline). Blank subjects are not stored."""
    diary, _created = Diary.objects.get_or_create(
        section=section, date=date, defaults={"branch_id": section.branch_id, "written_by": user}
    )
    diary.written_by = user
    if publish:
        diary.status = Diary.Status.PUBLISHED
        diary.published_at = timezone.now()
    diary.save()
    order = {s.id: o for s, o in subjects_for(section)}
    keep = []
    for subject_id, data in entries.items():
        in_class = (data.get("in_class") or "").strip()
        home_task = (data.get("home_task") or "").strip()
        if not in_class and not home_task:
            continue
        DiaryEntry.objects.update_or_create(
            diary=diary,
            subject_id=subject_id,
            defaults={
                "in_class": in_class,
                "home_task": home_task,
                "deadline": data.get("deadline") if home_task else None,
                "sort_order": order.get(subject_id, 99),
            },
        )
        keep.append(subject_id)
    diary.entries.exclude(subject_id__in=keep).delete()
    return diary


def document_context(diary, for_file=False):
    entries = list(diary.entries.select_related("subject"))
    for e in entries:
        e.in_class_rtl = e.subject.is_rtl or is_urdu(e.in_class)
        e.home_task_rtl = e.subject.is_rtl or is_urdu(e.home_task)
    return {
        "diary": diary,
        "layout": DiaryLayout.current(),
        "week": week_info(diary.branch, diary.date),
        "in_class": [e for e in entries if e.in_class],
        "home": [e for e in entries if e.home_task],
        "font_base": f"file://{settings.BASE_DIR}/static/fonts/" if for_file else f"{settings.STATIC_URL}fonts/",
        "media_base": f"file://{settings.MEDIA_ROOT}/" if for_file else settings.MEDIA_URL,
        "for_file": for_file,
    }


def render_pdf(diary):
    from weasyprint import HTML

    html = render_to_string("diary/document.html", document_context(diary, for_file=True))
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


def render_image(diary, width_px=1080):
    """All pages stacked into one PNG, sized for WhatsApp."""
    import pypdfium2 as pdfium
    from PIL import Image

    pdf = pdfium.PdfDocument(render_pdf(diary))
    pages = []
    for page in pdf:
        scale = width_px / page.get_width()
        pages.append(page.render(scale=scale).to_pil().convert("RGB"))
    height = sum(p.height for p in pages)
    sheet = Image.new("RGB", (width_px, height), "white")
    y = 0
    for p in pages:
        sheet.paste(p, (0, y))
        y += p.height
    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
