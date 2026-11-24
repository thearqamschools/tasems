"""Teachers for class teacher and subject teacher (R17-8, project lead 24 Nov 2026): chosen from the staff records
(Staff), with or without a TASEMS login. When a staff member gets a login later, their classes and subjects follow
them by themselves — the login is what lets a class teacher mark attendance, write the diary and enter marks."""

from django.db.models.signals import post_save

TEACHING_TYPES = ("teaching", "hifz")


def teacher_choices(branch):
    """Teachers and Qaris of the branch still working there, by name."""
    from apps.hr.models import Employee

    return Employee.objects.filter(
        branch=branch, staff_type__in=TEACHING_TYPES, status=Employee.Status.ACTIVE
    ).order_by("full_name")


def set_class_teacher(section, employee):
    section.class_teacher_staff = employee
    section.class_teacher = employee.user if employee and employee.user_id else None


def teacher_of(subject_link):
    """The person who teaches a section's subject: the staff record, else (older data) the login."""
    if subject_link is None:
        return None
    return subject_link.teacher_staff or subject_link.teacher


def teacher_key(teacher):
    """One key per person whether a staff record or a login (for clashes on the timetable)."""
    if teacher is None:
        return None
    from apps.hr.models import Employee

    if isinstance(teacher, Employee):
        return ("u", teacher.user_id) if teacher.user_id else ("s", teacher.id)
    return ("u", teacher.id)


def follow_login(sender, instance, **kwargs):
    """A staff member who now has a login: their class sections and subjects use it (R17-8)."""
    from .models import Section, SectionSubject

    if instance.user_id:
        Section.objects.filter(class_teacher_staff=instance).exclude(class_teacher_id=instance.user_id).update(
            class_teacher_id=instance.user_id
        )
        SectionSubject.objects.filter(teacher_staff=instance).exclude(teacher_id=instance.user_id).update(
            teacher_id=instance.user_id
        )


def connect():
    from apps.hr.models import Employee

    post_save.connect(follow_login, sender=Employee, dispatch_uid="academics_teachers_follow_login")


def teacher_name(teacher):
    if teacher is None:
        return ""
    if hasattr(teacher, "full_name"):
        return teacher.full_name
    return teacher.get_full_name() or teacher.username
