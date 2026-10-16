"""Loads the starting data TASEMS needs. Safe to run more than once.

Only facts confirmed by The Arqam Schools are seeded. Anything not yet
confirmed (Lahore address, regions, subjects, session dates) is left for head
office to enter, so nothing is invented.
"""

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academics.models import ClassLevel
from apps.accounts.models import Role, Scope
from apps.organisation.models import Branch, HeadOffice

VIEW_PEOPLE = ["people.view_student", "people.view_guardian", "people.view_enrolment", "people.view_studentguardian"]
EDIT_PEOPLE = [
    "people.add_student",
    "people.change_student",
    "people.add_guardian",
    "people.change_guardian",
    "people.add_enrolment",
    "people.change_enrolment",
    "people.add_studentguardian",
    "people.change_studentguardian",
    "people.delete_studentguardian",
]
VIEW_ACADEMICS = [
    "academics.view_section",
    "academics.view_classlevel",
    "academics.view_subject",
    "academics.view_curriculumsubject",
    "organisation.view_branch",
    "organisation.view_academicsession",
]
EDIT_SECTIONS = ["academics.add_section", "academics.change_section"]
VIEW_STUDENTS_ONLY = ["people.view_student", "people.view_enrolment"]
NETWORK_SETUP = [
    "organisation.add_branch",
    "organisation.change_branch",
    "organisation.view_headoffice",
    "organisation.view_region",
    "organisation.add_region",
    "organisation.change_region",
    "organisation.add_academicsession",
    "organisation.change_academicsession",
    "academics.add_classlevel",
    "academics.change_classlevel",
    "academics.add_subject",
    "academics.change_subject",
    "academics.add_curriculumsubject",
    "academics.change_curriculumsubject",
    "accounts.view_user",
    "accounts.add_user",
    "accounts.change_user",
    "accounts.view_roleassignment",
    "accounts.add_roleassignment",
    "accounts.change_roleassignment",
    "core.view_auditevent",
]

N, H, R, B = Scope.NETWORK, Scope.HEAD_OFFICE, Scope.REGION, Scope.BRANCH

# code, name, name_ur, scopes, permissions, requires_mfa
ROLES = [
    (
        "network_admin",
        "Network Administrator",
        "نیٹ ورک ایڈمنسٹریٹر",
        [N],
        VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS + NETWORK_SETUP,
        True,
    ),
    (
        "head_office_admin",
        "Head Office Administrator",
        "ہیڈ آفس ایڈمنسٹریٹر",
        [H],
        VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS + NETWORK_SETUP,
        True,
    ),
    ("regional_director", "Regional Director", "ریجنل ڈائریکٹر", [R], VIEW_PEOPLE + VIEW_ACADEMICS, True),
    ("branch_owner", "Branch Owner / Franchisee", "برانچ مالک", [B], VIEW_PEOPLE + VIEW_ACADEMICS, True),
    (
        "principal",
        "Principal",
        "پرنسپل",
        [B],
        VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS + ["accounts.view_user"],
        True,
    ),
    (
        "academic_coordinator",
        "Academic Coordinator",
        "اکیڈمک کوآرڈینیٹر",
        [B, R],
        VIEW_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS,
        False,
    ),
    ("admissions_officer", "Admissions Officer", "داخلہ آفیسر", [B], VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS, False),
    ("accountant", "Accountant", "اکاؤنٹنٹ", [B], VIEW_PEOPLE + VIEW_ACADEMICS, True),
    ("class_teacher", "Class Teacher", "کلاس ٹیچر", [B], VIEW_PEOPLE + VIEW_ACADEMICS, False),
    ("subject_teacher", "Subject Teacher", "سبجیکٹ ٹیچر", [B], VIEW_STUDENTS_ONLY + VIEW_ACADEMICS, False),
    ("hifz_teacher", "Hifz Teacher", "حفظ ٹیچر", [B], VIEW_STUDENTS_ONLY + VIEW_ACADEMICS, False),
]

# Levels named in the project brief. Whether "Prep / KG" is a separate class is to be confirmed.
CLASS_LEVELS = [("play-group", "Play Group", "پلے گروپ", "early_years"), ("nursery", "Nursery", "نرسری", "early_years")]
CLASS_LEVELS += [
    (f"class-{n}", f"Class {n}", f"جماعت {n}", "primary" if n <= 5 else "middle" if n <= 8 else "secondary")
    for n in range(1, 11)
]
CLASS_LEVELS += [("hifz", "Hifz-e-Quran", "حفظ القرآن", "hifz")]


def perms(names):
    result = []
    for name in names:
        app_label, codename = name.split(".")
        result.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return result


class Command(BaseCommand):
    help = "Seed head offices, the Samanabad campus, system roles and class levels."

    @transaction.atomic
    def handle(self, *args, **options):
        fsd, _ = HeadOffice.objects.update_or_create(
            code="faisalabad",
            defaults={
                "name": "The Arqam Schools — Faisalabad Head Office",
                "city": "Faisalabad",
                "address": "Sanora Colony, Samanabad, Faisalabad, Pakistan",
                "phone": "041-2660265, 041-2406479",
            },
        )
        HeadOffice.objects.update_or_create(
            code="lahore", defaults={"name": "The Arqam Schools — Lahore Head Office", "city": "Lahore"}
        )
        Branch.objects.update_or_create(
            code="fsd-samanabad",
            defaults={
                "name": "The Arqam Schools — Samanabad Campus (Head Office)",
                "head_office": fsd,
                "ownership": Branch.Ownership.COMPANY,
                "royalty_percent": 0,
                "city": "Faisalabad",
                "address": "Sanora Colony, Samanabad, Faisalabad, Pakistan",
                "phone": "041-2660265, 041-2406479",
            },
        )

        for code, name, name_ur, scopes, perm_names, mfa in ROLES:
            role, _ = Role.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "name_ur": name_ur,
                    "allowed_scopes": list(scopes),
                    "requires_mfa": mfa,
                    "is_system": True,
                },
            )
            role.permissions.set(perms(perm_names))

        for i, (code, name, name_ur, stage) in enumerate(CLASS_LEVELS, start=1):
            ClassLevel.objects.update_or_create(
                code=code, defaults={"name": name, "name_ur": name_ur, "stage": stage, "sort_order": i * 10}
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded: 2 head offices, Samanabad campus, {len(ROLES)} roles, {len(CLASS_LEVELS)} class levels."
            )
        )
