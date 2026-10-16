import datetime as dt

import pytest
from django.core.management import call_command

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Role, RoleAssignment, Scope, User
from apps.organisation.models import AcademicSession, Branch, HeadOffice, Region
from apps.people.models import Student


@pytest.fixture
def seeded(db):
    call_command("seed_tasems", verbosity=0)


@pytest.fixture
def org(seeded):
    """Two head offices, one region each, test branches under them."""
    fsd = HeadOffice.objects.get(code="faisalabad")
    lhr = HeadOffice.objects.get(code="lahore")
    fsd_region = Region.objects.create(head_office=fsd, code="test-fsd-region", name="Test FSD Region")
    lhr_region = Region.objects.create(head_office=lhr, code="test-lhr-region", name="Test LHR Region")
    samanabad = Branch.objects.get(code="fsd-samanabad")
    fsd_franchise = Branch.objects.create(
        code="test-fsd-1", name="Test FSD Franchise", head_office=fsd, region=fsd_region, city="Faisalabad"
    )
    lhr_franchise = Branch.objects.create(
        code="test-lhr-1", name="Test LHR Franchise", head_office=lhr, region=lhr_region, city="Lahore"
    )
    session = AcademicSession.objects.create(
        name="2026-27", starts_on=dt.date(2026, 4, 1), ends_on=dt.date(2027, 3, 31), is_current=True
    )
    return {
        "fsd": fsd,
        "lhr": lhr,
        "fsd_region": fsd_region,
        "lhr_region": lhr_region,
        "samanabad": samanabad,
        "fsd_franchise": fsd_franchise,
        "lhr_franchise": lhr_franchise,
        "session": session,
    }


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(role_code=None, scope=None, target=None, **extra):
        counter["n"] += 1
        user = User.objects.create_user(username=f"user{counter['n']}", password="Str0ng-pass-123", **extra)
        if role_code:
            kwargs = {"user": user, "role": Role.objects.get(code=role_code), "scope": scope}
            if scope == Scope.HEAD_OFFICE:
                kwargs["head_office"] = target
            elif scope == Scope.REGION:
                kwargs["region"] = target
            elif scope == Scope.BRANCH:
                kwargs["branch"] = target
            RoleAssignment.objects.create(**kwargs)
        return user

    return _make


@pytest.fixture
def students(org):
    def make(branch, adm):
        return Student.objects.create(
            branch=branch,
            admission_no=adm,
            first_name=f"Student {adm}",
            gender="male",
            admission_date=dt.date(2026, 4, 1),
        )

    return {
        "samanabad": make(org["samanabad"], "S-1"),
        "fsd_franchise": make(org["fsd_franchise"], "F-1"),
        "lhr_franchise": make(org["lhr_franchise"], "L-1"),
    }


@pytest.fixture
def section(org):
    return Section.objects.create(
        branch=org["samanabad"], session=org["session"], class_level=ClassLevel.objects.get(code="class-5"), name="A"
    )


@pytest.fixture
def login_as(client):
    """Signs a user in as if they had passed the two-step check."""

    def _login(user):
        client.force_login(user)
        session = client.session
        session["mfa_verified"] = True
        session.save()
        return client

    return _login
