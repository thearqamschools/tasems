"""Leaving a school and the certificates that go with it (M4)."""

from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.template.loader import render_to_string
from django.utils import timezone

from apps.diary.models import DiaryLayout

from .models import Certificate


def last_class(student):
    enrolment = (
        student.enrolments.select_related("section__class_level", "session").order_by("-session__starts_on").first()
    )
    return f"{enrolment.section.class_level} · {enrolment.section.name} ({enrolment.session})" if enrolment else ""


@transaction.atomic
def mark_left(student, status, left_on, user):
    """Withdrawn / left, transferred out or graduated. The record stays; fees and registers stop."""
    student.status = status
    student.status_changed_on = left_on
    student.full_clean()
    student.save()
    return student


@transaction.atomic
def issue(student, kind, user, **details):
    highest = Certificate.objects.filter(branch_id=student.branch_id, kind=kind).aggregate(n=Max("number"))["n"]
    return Certificate.objects.create(
        branch_id=student.branch_id,
        student=student,
        kind=kind,
        number=(highest or 0) + 1,
        issued_on=timezone.localdate(),
        last_class=details.pop("last_class", None) or last_class(student),
        issued_by=user,
        **details,
    )


def render_pdf(certificate):
    from weasyprint import HTML

    html = render_to_string(
        "people/certificate.html",
        {
            "c": certificate,
            "s": certificate.student,
            "branch": certificate.student.branch,
            "layout": DiaryLayout.current(),
            "font_base": f"file://{settings.BASE_DIR}/static/fonts/",
            "media_base": f"file://{settings.MEDIA_ROOT}/",
            "female": certificate.student.gender == "female",
        },
    )
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()
