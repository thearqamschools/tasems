"""Saving a student with their class and primary contact, shared by the form and the Excel import."""

from django.db import transaction

from .models import Enrolment, Guardian, StudentGuardian


@transaction.atomic
def save_student(
    student,
    *,
    session,
    section,
    roll_no,
    guardian_name,
    guardian_phone,
    relationship,
    guardian_name_ur="",
):
    """`student` is an unsaved or changed Student. Returns the saved student."""
    student.full_clean()
    student.save()

    guardian = Guardian.objects.filter(branch=student.branch, phone=guardian_phone).first()
    if guardian is None:
        guardian = Guardian.objects.create(
            branch=student.branch, full_name=guardian_name, full_name_ur=guardian_name_ur, phone=guardian_phone
        )
    elif guardian_name_ur and not guardian.full_name_ur:
        guardian.full_name_ur = guardian_name_ur
        guardian.save()

    StudentGuardian.objects.filter(student=student, is_primary_contact=True).exclude(guardian=guardian).update(
        is_primary_contact=False
    )
    StudentGuardian.objects.update_or_create(
        student=student,
        guardian=guardian,
        defaults={"relationship": relationship, "is_primary_contact": True},
    )

    if session and section:
        enrolment = Enrolment.objects.filter(student=student, session=session).first() or Enrolment(
            student=student, session=session, branch=student.branch
        )
        enrolment.section = section
        enrolment.roll_no = roll_no
        enrolment.full_clean()
        enrolment.save()
    return student


def primary_contact(student):
    link = student.guardian_links.filter(is_primary_contact=True).select_related("guardian").first()
    return link


def current_enrolment(student, session):
    if not session:
        return None
    return Enrolment.objects.filter(student=student, session=session).select_related("section").first()
