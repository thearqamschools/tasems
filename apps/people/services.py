"""Saving a student with their class and family, shared by the form, admissions and the Excel import."""

from django.db import transaction
from django.db.models import Q
from django.db.models.functions import Length

from .models import Enrolment, Guardian, Student, StudentGuardian

FAMILY_ROLES = ("father", "mother", "guardian")


def next_admission_no(branch):
    """The branch's next admission number: one more than its highest plain-number admission number."""
    numbers = (
        Student.objects.filter(branch=branch, admission_no__regex=r"^[0-9]+$")
        .order_by(Length("admission_no").desc(), "-admission_no")
        .values_list("admission_no", flat=True)
    )
    highest = numbers.first()
    return str(int(highest) + 1) if highest else "1001"


def family_of(student):
    """{role: link} for the father, mother and guardian rows of the form (older records: the primary
    contact counts as the guardian row when it is not marked father or mother)."""
    rows = {}
    for link in student.guardian_links.select_related("guardian").order_by("-is_primary_contact", "pk"):
        role = link.relationship if link.relationship in ("father", "mother") else "guardian"
        rows.setdefault(role, link)
    return rows


def parent_mobiles(student):
    """The father's and the mother's mobile (project lead, 28 Oct 2026); without either, the main contact's.
    Uses `student.contact_links` when the list prefetched it."""
    links = getattr(student, "contact_links", None)
    if links is None:
        links = list(student.guardian_links.select_related("guardian"))
    links = sorted(links, key=lambda link: (not link.is_primary_contact, link.pk))
    found = {}
    for link in links:
        if link.relationship in ("father", "mother") and link.guardian.phone:
            found.setdefault(link.relationship, link.guardian.phone)
    phones = [found[r] for r in ("father", "mother") if r in found]
    if not phones:
        phones = [link.guardian.phone for link in links if link.is_primary_contact and link.guardian.phone][:1]
    return phones


def _guardian_for(branch, role, person):
    """Brothers and sisters share one parent record: same mobile and same role (or same name)."""
    same_phone = Guardian.objects.filter(branch=branch, phone=person["phone"])
    return (
        same_phone.filter(student_links__relationship=role).first()
        or same_phone.filter(full_name__iexact=person["name"]).first()
    )


@transaction.atomic
def save_family(student, family):
    """`family` = {"father": {...}, "mother": {...}, "guardian": {...}}, each with name, phone and optionally
    email, occupation, organisation, relation_detail. An empty row removes that person from this student."""
    current = family_of(student)
    for role in FAMILY_ROLES:
        person = family.get(role) or {}
        link = current.get(role)
        if not person.get("name"):
            if link is not None and role != "father":
                link.delete()
            continue
        guardian = link.guardian if link is not None and link.guardian.phone == person["phone"] else None
        guardian = guardian or _guardian_for(student.branch, role, person)
        taken = StudentGuardian.objects.filter(student=student, guardian=guardian).exclude(pk=getattr(link, "pk", None))
        if guardian is None or (guardian.pk and taken.exists()):  # e.g. mother typed exactly like the father
            guardian = Guardian(branch=student.branch, phone=person["phone"])
        guardian.full_name = person["name"]
        for field in ("email", "occupation", "organisation"):
            if field in person:
                setattr(guardian, field, person[field])
        guardian.save()
        if link is not None and link.guardian_id != guardian.id:
            link.delete()
            link = None
        StudentGuardian.objects.update_or_create(
            student=student,
            guardian=guardian,
            defaults={
                "relationship": role,
                "relation_detail": person.get("relation_detail", "") if role == "guardian" else "",
                "is_primary_contact": False,
            },
        )
    # The father is the main contact; without one, the mother, then the guardian.
    links = family_of(student)
    primary = links.get("father") or links.get("mother") or links.get("guardian")
    if primary is not None:
        StudentGuardian.objects.filter(student=student).exclude(pk=primary.pk).update(is_primary_contact=False)
        StudentGuardian.objects.filter(pk=primary.pk).update(is_primary_contact=True)


@transaction.atomic
def save_student(
    student,
    *,
    session,
    section,
    roll_no,
    family=None,
    guardian_name="",
    guardian_phone="",
    relationship="father",
    guardian_name_ur="",
):
    """`student` is an unsaved or changed Student. Returns the saved student.
    The form passes `family` (father, mother, guardian); the Excel import passes one primary contact."""
    student.full_clean()
    student.save()
    if family is not None:
        save_family(student, family)
    else:
        _save_primary_contact(student, guardian_name, guardian_phone, relationship, guardian_name_ur)
    _place(student, session, section, roll_no)
    return student


def _save_primary_contact(student, guardian_name, guardian_phone, relationship, guardian_name_ur):
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


def _place(student, session, section, roll_no):
    if session and section:
        enrolment = Enrolment.objects.filter(student=student, session=session).first() or Enrolment(
            student=student, session=session, branch=student.branch
        )
        enrolment.section = section
        enrolment.roll_no = roll_no
        enrolment.full_clean()
        enrolment.save()


def primary_contact(student):
    link = student.guardian_links.filter(is_primary_contact=True).select_related("guardian").first()
    return link


def current_enrolment(student, session):
    if not session:
        return None
    return Enrolment.objects.filter(student=student, session=session).select_related("section").first()


def search(students, q):
    """Admission no., name, father name, any mobile of the father, mother or guardian, father CNIC or B-Form
    (project lead, 31 Oct 2026). Numbers may be typed with or without dashes."""
    q = q.strip()
    if not q:
        return students
    digits = "".join(ch for ch in q if ch.isdigit())
    match = (
        Q(admission_no__icontains=q)
        | Q(first_name__icontains=q)
        | Q(last_name__icontains=q)
        | Q(father_name__icontains=q)
        | Q(full_name_ur__icontains=q)
    )
    words = q.split()
    if len(words) > 1:  # "Ali Ahmad": first and last name together
        match |= Q(first_name__icontains=words[0], last_name__icontains=" ".join(words[1:]))
    if len(digits) >= 4:
        match |= Q(guardian_links__guardian__phone__contains=digits)
        match |= Q(father_cnic__contains=digits) | Q(b_form_no__contains=digits)
        if digits.startswith("0") and len(digits) == 11:  # 0300… also stored as +92 300…
            match |= Q(guardian_links__guardian__phone__contains=digits[1:])
    return students.filter(match).distinct()


def place_filter(students, session, level_id="", section_name="", campus_id=""):
    """Class, section and campus filters on the current session's class places."""
    if not session:
        return students
    places = Enrolment.objects.filter(session=session)
    used = False
    if str(level_id).isdigit():
        places, used = places.filter(section__class_level_id=level_id), True
    if section_name:
        places, used = places.filter(section__name=section_name), True
    if str(campus_id).isdigit():
        places, used = places.filter(section__campus_id=campus_id), True
    return students.filter(pk__in=places.values("student_id")) if used else students
