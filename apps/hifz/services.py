"""Hifz (M12): which students and sections are Hifz, who may record, saving a day's sheet, and progress."""

from django.db import transaction
from django.db.models import Avg, Count, F, Max, Q, Sum
from django.utils import timezone

from apps.academics.models import Section
from apps.attendance import services as attendance
from apps.attendance.models import AttendanceRecord
from apps.core.models import AuditEvent
from apps.people.models import Enrolment, Student

from .models import PARAS, HifzLesson, ParaTest

VIEW_PERM = "hifz.view_hifzlesson"
WRITE_PERM = "hifz.add_hifzlesson"
CHANGE_PERM = "hifz.change_hifzlesson"
TEST_PERM = "hifz.add_paratest"

FIELDS = [
    "status", "sabaq_para", "sabaq", "sabaq_lines", "sabaq_mistakes", "sabqi", "sabqi_mistakes", "manzil",
    "manzil_mistakes", "grade", "remarks",
]  # fmt: skip


def is_hifz_section(section):
    return section.class_level.code == "hifz"


def sections(branch, session):
    """Hifz sections, and other sections that have Hifz students (marked Hifz on their record)."""
    if session is None:
        return []
    qs = Section.objects.filter(branch=branch, session=session, is_active=True).filter(
        Q(class_level__code="hifz")
        | Q(
            enrolments__session=session,
            enrolments__student__is_hifz=True,
            enrolments__student__status=Student.Status.ACTIVE,
        )
    )
    return list(
        qs.distinct().select_related("class_level", "class_teacher").order_by("class_level__sort_order", "name")
    )


def roster(section):
    entries = attendance.roster(section)
    return entries if is_hifz_section(section) else [e for e in entries if e.student.is_hifz]


def hifz_students(branch, session):
    """Active students of the branch in a Hifz section this session, or marked Hifz."""
    if session is None:
        return Student.objects.none()
    return (
        Student.objects.filter(branch=branch, status=Student.Status.ACTIVE)
        .filter(Q(is_hifz=True) | Q(enrolments__session=session, enrolments__section__class_level__code="hifz"))
        .distinct()
    )


def can_record(user, section, date):
    """Hifz teachers record their own sections for today; principals and coordinators any school day."""
    today = timezone.localdate()
    if date > today or date < section.session.starts_on or date > section.session.ends_on:
        return False
    if not attendance.is_school_day(section.class_level, date, section.branch_id):
        return False
    if user.has_branch_perm(CHANGE_PERM, section.branch_id):
        return True
    return date == today and section.class_teacher_id == user.id and user.has_branch_perm(WRITE_PERM, section.branch_id)


def sheet(section, date):
    """Rows for the day's sheet: saved lesson, or a new one that continues the last para and follows the register."""
    entries = roster(section)
    ids = [e.student_id for e in entries]
    saved = {x.student_id: x for x in HifzLesson.objects.filter(student_id__in=ids, date=date)}
    last_para = dict(
        HifzLesson.objects.filter(student_id__in=ids, date__lt=date, sabaq_para__isnull=False)
        .order_by("student_id", "-date")
        .distinct("student_id")
        .values_list("student_id", "sabaq_para")
    )
    absent = set(
        AttendanceRecord.objects.filter(student_id__in=ids, date=date, status__in=["absent", "leave"]).values_list(
            "student_id", flat=True
        )
    )
    rows = []
    for e in entries:
        lesson = saved.get(e.student_id) or HifzLesson(
            student=e.student,
            sabaq_para=last_para.get(e.student_id),
            status=HifzLesson.Status.ABSENT if e.student_id in absent else HifzLesson.Status.HEARD,
        )
        rows.append({"enrolment": e, "lesson": lesson, "saved": e.student_id in saved})
    return rows


@transaction.atomic
def save_sheet(section, date, values, user):
    """`values` maps student id → dict of FIELDS (already cleaned). Students not in the section are refused.
    An absent student's lesson keeps only the status and remarks. Returns the number of lessons saved."""
    ids = {e.student_id for e in roster(section)}
    if not set(values) <= ids:
        raise ValueError("Student is not in this section.")
    saved = {x.student_id: x for x in HifzLesson.objects.select_for_update().filter(student_id__in=values, date=date)}
    for student_id, data in values.items():
        if data["status"] == HifzLesson.Status.ABSENT:
            data = {**{f: HifzLesson._meta.get_field(f).get_default() for f in FIELDS}, "status": data["status"],
                    "remarks": data.get("remarks", ""), "sabaq_para": data.get("sabaq_para")}  # fmt: skip
        lesson = saved.get(student_id)
        if lesson is None:
            HifzLesson.objects.create(
                branch_id=section.branch_id, student_id=student_id, section=section, date=date, recorded_by=user,
                **data,
            )  # fmt: skip
            continue
        changes = {
            f: {"from": str(getattr(lesson, f)), "to": str(data[f])} for f in FIELDS if getattr(lesson, f) != data[f]
        }
        if changes:
            for f in FIELDS:
                setattr(lesson, f, data[f])
            lesson.recorded_by = user
            lesson.save()
            AuditEvent.objects.create(
                actor=user, action=AuditEvent.Action.UPDATE, model_label="hifz.HifzLesson", object_id=str(lesson.pk),
                object_repr=str(lesson)[:255], branch_id=section.branch_id, changes=changes,
            )  # fmt: skip
    return len(values)


def passed_paras(students):
    """{student_id: {para: ParaTest}} of passed, not cancelled tests."""
    out = {}
    for t in ParaTest.objects.filter(student__in=students, result=ParaTest.Result.PASSED, is_cancelled=False):
        out.setdefault(t.student_id, {})[t.para] = t
    return out


def record_test(student, para, tested_on, result, mistakes, user, before_joining=False, remarks=""):
    """Records a para test. A second pass of the same para is refused (ValueError)."""
    if (
        result == ParaTest.Result.PASSED
        and ParaTest.objects.filter(
            student=student, para=para, result=ParaTest.Result.PASSED, is_cancelled=False
        ).exists()
    ):
        raise ValueError("Para already passed.")
    return ParaTest.objects.create(
        branch_id=student.branch_id, student=student, para=para, tested_on=tested_on, result=result,
        mistakes=mistakes, before_joining=before_joining, remarks=remarks[:200], tested_by=user,
    )  # fmt: skip


def cancel_test(test):
    test.is_cancelled = True
    test.save()


def progress(students, start, end):
    """Per student: paras passed, current para, and the period's lessons (heard, not ready, absent, lines,
    average mistakes per heard lesson)."""
    students = list(students)
    passed = passed_paras(students)
    current = dict(
        HifzLesson.objects.filter(student__in=students, sabaq_para__isnull=False)
        .order_by("student_id", "-date")
        .distinct("student_id")
        .values_list("student_id", "sabaq_para")
    )
    stats = {
        r["student_id"]: r
        for r in HifzLesson.objects.filter(student__in=students, date__gte=start, date__lte=end)
        .values("student_id")
        .annotate(
            heard=Count("id", filter=Q(status="heard")),
            not_ready=Count("id", filter=Q(status="not_ready")),
            absent=Count("id", filter=Q(status="absent")),
            mistakes=Avg(F("sabaq_mistakes") + F("sabqi_mistakes") + F("manzil_mistakes"), filter=Q(status="heard")),
            last=Max("date"),
        )
    }
    line_totals = dict(
        HifzLesson.objects.filter(student__in=students, date__gte=start, date__lte=end, status="heard")
        .values("student_id")
        .annotate(t=Sum("sabaq_lines"))
        .values_list("student_id", "t")
    )
    rows = []
    for s in students:
        st = stats.get(s.id, {})
        done = passed.get(s.id, {})
        rows.append(
            {
                "student": s,
                "paras": len(done),
                "complete": len(done) == PARAS,
                "current": current.get(s.id),
                "heard": st.get("heard", 0),
                "not_ready": st.get("not_ready", 0),
                "absent": st.get("absent", 0),
                "lines": line_totals.get(s.id) or 0,
                "mistakes": round(st["mistakes"], 1) if st.get("mistakes") is not None else None,
                "last": st.get("last"),
            }
        )
    return rows


def enrolment(student, session):
    return Enrolment.objects.filter(student=student, session=session).select_related("section").first()
