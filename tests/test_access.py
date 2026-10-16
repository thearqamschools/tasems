"""Branch isolation and role-based access — the most important rules in TASEMS."""

import datetime as dt

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import Role, RoleAssignment, Scope
from apps.people.models import Student

pytestmark = pytest.mark.django_db


def visible(user):
    return set(Student.objects.for_user(user).values_list("admission_no", flat=True))


def test_principal_sees_only_own_branch(org, students, make_user):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    assert visible(principal) == {"S-1"}


def test_head_office_admin_sees_only_its_head_office(org, students, make_user):
    fsd_admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    assert visible(fsd_admin) == {"S-1", "F-1"}
    lhr_admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["lhr"])
    assert visible(lhr_admin) == {"L-1"}


def test_regional_director_sees_only_region(org, students, make_user):
    director = make_user("regional_director", Scope.REGION, org["fsd_region"])
    assert visible(director) == {"F-1"}  # Samanabad campus is not in that region


def test_network_admin_sees_everything(org, students, make_user):
    admin = make_user("network_admin", Scope.NETWORK)
    assert visible(admin) == {"S-1", "F-1", "L-1"}


def test_user_without_roles_sees_nothing(org, students, make_user):
    assert visible(make_user()) == set()


def test_inactive_user_sees_nothing(org, students, make_user):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"], is_active=False)
    assert visible(principal) == set()


def test_expired_assignment_gives_no_access(org, students, make_user):
    user = make_user()
    RoleAssignment.objects.create(
        user=user,
        role=Role.objects.get(code="principal"),
        scope=Scope.BRANCH,
        branch=org["samanabad"],
        ends_on=dt.date(2020, 1, 1),
    )
    assert visible(user) == set()


def test_permissions_come_from_roles(org, make_user):
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    assert teacher.has_perm("people.view_student")
    assert not teacher.has_perm("people.change_student")
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    assert principal.has_perm("people.change_student")


def test_branch_permission_is_checked_per_branch(org, make_user):
    """Teacher at one branch and principal at another: edit rights only where principal."""
    user = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    RoleAssignment.objects.create(
        user=user, role=Role.objects.get(code="principal"), scope=Scope.BRANCH, branch=org["fsd_franchise"]
    )
    assert user.has_branch_perm("people.change_student", org["fsd_franchise"].id)
    assert not user.has_branch_perm("people.change_student", org["samanabad"].id)
    assert user.has_branch_perm("people.view_student", org["samanabad"].id)
    assert not user.has_branch_perm("people.view_student", org["lhr_franchise"].id)


def test_assignment_must_name_the_right_target(org, make_user):
    user = make_user()
    with pytest.raises(IntegrityError), transaction.atomic():
        RoleAssignment.objects.create(
            user=user,
            role=Role.objects.get(code="principal"),
            scope=Scope.BRANCH,  # no branch given
        )


def test_role_cannot_be_given_at_wrong_scope(org, make_user):
    assignment = RoleAssignment(user=make_user(), role=Role.objects.get(code="principal"), scope=Scope.NETWORK)
    with pytest.raises(ValidationError):
        assignment.full_clean()
