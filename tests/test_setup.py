"""Setup screens (Phase 4, M3): who may change what, and the rule that nobody can give more than they hold."""

import datetime as dt

import pytest

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Role, RoleAssignment, Scope, User
from apps.core.models import AuditEvent
from apps.fees.models import FeeHead, FeeRate
from apps.organisation.models import AcademicSession, Branch, Campus
from apps.setup import access

pytestmark = pytest.mark.django_db


def _role(code):
    return Role.objects.get(code=code)


def _assign(client, user_id, role, scope, **target):
    data = {"action": "assign", "a-role": _role(role).pk, "a-scope": scope}
    for key, value in target.items():
        data[f"a-{key}"] = value.pk
    return client.post(f"/setup/users/{user_id}/", data)


# ---------- The no-escalation rule ----------
def test_head_office_admin_can_give_branch_roles_inside_own_head_office(org, make_user, login_as):
    admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    teacher = make_user("class_teacher", Scope.BRANCH, org["fsd_franchise"])
    client = login_as(admin)
    _assign(client, teacher.pk, "accountant", Scope.BRANCH, branch=org["fsd_franchise"])
    assert teacher.role_assignments.filter(role__code="accountant", branch=org["fsd_franchise"]).exists()


def test_cannot_give_roles_outside_own_area(org, make_user, login_as):
    admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    person = make_user("class_teacher", Scope.BRANCH, org["fsd_franchise"])
    can, reason = access.can_assign(admin, _role("accountant"), Scope.BRANCH, {org["lhr_franchise"].pk})
    assert not can and reason == "outside"
    # Lahore's branches are not even offered on the form, and a forged post changes nothing.
    response = _assign(login_as(admin), person.pk, "accountant", Scope.BRANCH, branch=org["lhr_franchise"])
    assert response.status_code == 200
    assert not person.role_assignments.filter(branch=org["lhr_franchise"]).exists()


def test_cannot_give_a_role_with_more_power_than_you_hold(org, make_user):
    admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    # A role with a permission the head office admin does not hold anywhere.
    from django.contrib.auth.models import Permission

    powerful = Role.objects.create(code="test-powerful", name="Powerful", allowed_scopes=["branch"])
    powerful.permissions.add(Permission.objects.get(codename="delete_auditevent"))
    can, reason = access.can_assign(admin, powerful, Scope.BRANCH, {org["fsd_franchise"].pk})
    assert not can and reason == "more_than_you_hold"
    # A head office admin cannot make someone a network administrator.
    can, reason = access.can_assign(
        admin, _role("network_admin"), Scope.NETWORK, access.scope_branch_ids(Scope.NETWORK)
    )
    assert not can


def test_principal_cannot_hand_out_roles(org, make_user, login_as):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    client = login_as(principal)
    response = _assign(client, teacher.pk, "principal", Scope.BRANCH, branch=org["samanabad"])
    assert response.status_code == 403
    assert not teacher.role_assignments.filter(role__code="principal").exists()


def test_nobody_changes_their_own_access(org, make_user, login_as):
    admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    client = login_as(admin)
    assert _assign(client, admin.pk, "accountant", Scope.BRANCH, branch=org["samanabad"]).status_code == 403
    own = admin.role_assignments.get()
    assert client.post(f"/setup/users/{admin.pk}/roles/{own.pk}/end/").status_code == 403
    assert client.post(f"/setup/users/{admin.pk}/password/").status_code == 403


def test_superusers_are_protected(org, make_user, login_as):
    admin = make_user("network_admin", Scope.NETWORK)
    root = User.objects.create_superuser("root", password="Str0ng-pass-123")
    RoleAssignment.objects.create(user=root, role=_role("network_admin"), scope=Scope.NETWORK)
    client = login_as(admin)
    assert client.post(f"/setup/users/{root.pk}/password/").status_code == 403
    assert client.post(f"/setup/users/{root.pk}/active/", {"active": "0"}).status_code == 403
    root.refresh_from_db()
    assert root.is_active


def test_cannot_manage_someone_who_also_works_elsewhere(org, make_user, login_as):
    fsd_admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    both = make_user("class_teacher", Scope.BRANCH, org["fsd_franchise"])
    RoleAssignment.objects.create(
        user=both, role=_role("class_teacher"), scope=Scope.BRANCH, branch=org["lhr_franchise"]
    )
    client = login_as(fsd_admin)
    assert client.post(f"/setup/users/{both.pk}/active/", {"active": "0"}).status_code == 403
    lahore_role = both.role_assignments.get(branch=org["lhr_franchise"])
    assert client.post(f"/setup/users/{both.pk}/roles/{lahore_role.pk}/end/").status_code == 403
    fsd_role = both.role_assignments.get(branch=org["fsd_franchise"])
    client.post(f"/setup/users/{both.pk}/roles/{fsd_role.pk}/end/")
    fsd_role.refresh_from_db()
    assert not fsd_role.is_active and fsd_role.ends_on == dt.date.today()


def test_users_list_shows_only_people_in_your_area(org, make_user, login_as):
    fsd_admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    mine = make_user("class_teacher", Scope.BRANCH, org["fsd_franchise"])
    theirs = make_user("class_teacher", Scope.BRANCH, org["lhr_franchise"])
    client = login_as(fsd_admin)
    names = {u.pk for u in client.get("/setup/users/?status=all").context["page"]}
    assert mine.pk in names and theirs.pk not in names
    assert client.get(f"/setup/users/{theirs.pk}/").status_code == 404


# ---------- Logins and passwords ----------
def test_new_login_gets_a_temporary_password_once(org, make_user, login_as):
    admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    client = login_as(admin)
    response = client.post(
        "/setup/users/new/",
        {
            "username": "new.teacher",
            "first_name": "New",
            "last_name": "Teacher",
            "phone": "0300 7654321",
            "preferred_language": "ur",
            "a-role": _role("class_teacher").pk,
            "a-scope": Scope.BRANCH,
            "a-branch": org["fsd_franchise"].pk,
        },
    )
    assert response.status_code == 200 and response["Cache-Control"].startswith("max-age=0")
    password = response.context["password"]
    user = User.objects.get(username="new.teacher")
    assert user.phone == "03007654321" and user.check_password(password)
    assert user.role_assignments.get().branch == org["fsd_franchise"]
    assert password not in str(list(AuditEvent.objects.values_list("changes", flat=True)))


def test_password_reset_is_audited_without_the_password(org, make_user, login_as):
    admin = make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"])
    teacher = make_user("class_teacher", Scope.BRANCH, org["fsd_franchise"])
    response = login_as(admin).post(f"/setup/users/{teacher.pk}/password/")
    password = response.context["password"]
    teacher.refresh_from_db()
    assert teacher.check_password(password)
    event = AuditEvent.objects.filter(model_label="accounts.User", object_id=str(teacher.pk)).latest("occurred_at")
    assert event.actor == admin and password not in str(event.changes)


def test_staff_change_their_own_password(org, make_user, login_as):
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    client = login_as(teacher)
    response = client.post(
        "/accounts/password/",
        {"old_password": "Str0ng-pass-123", "new_password1": "Another-pass-456", "new_password2": "Another-pass-456"},
    )
    assert response.status_code == 302
    teacher.refresh_from_db()
    assert teacher.check_password("Another-pass-456")


# ---------- Sessions, sections, fee rates, branches ----------
def test_only_network_wide_people_switch_the_session(org, make_user, login_as):
    new = AcademicSession.objects.create(name="2027-28", starts_on=dt.date(2027, 4, 1), ends_on=dt.date(2028, 3, 31))
    fsd_admin = login_as(make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"]))
    assert fsd_admin.post(f"/setup/sessions/{new.pk}/current/").status_code == 403


def test_making_a_session_current_keeps_exactly_one(org, make_user, login_as):
    new = AcademicSession.objects.create(name="2027-28", starts_on=dt.date(2027, 4, 1), ends_on=dt.date(2028, 3, 31))
    login_as(make_user("network_admin", Scope.NETWORK)).post(f"/setup/sessions/{new.pk}/current/")
    assert list(AcademicSession.objects.filter(is_current=True)) == [new]


def test_section_rules_are_checked(org, make_user, login_as):
    principal = make_user("principal", Scope.BRANCH, org["samanabad"])
    outsider = make_user("class_teacher", Scope.BRANCH, org["lhr_franchise"])
    client = login_as(principal)
    six = ClassLevel.objects.get(code="class-6")
    # From Class 6 a section is for boys or girls (D-015).
    r = client.post(
        "/setup/sections/new/", {"class_level": six.pk, "name": "A", "gender_group": "mixed", "is_active": "on"}
    )
    assert "gender_group" in r.context["form"].errors
    # A teacher from another branch is not offered.
    r = client.post(
        "/setup/sections/new/",
        {"class_level": six.pk, "name": "A", "gender_group": "boys", "class_teacher": outsider.pk, "is_active": "on"},
    )
    assert "class_teacher" in r.context["form"].errors
    r = client.post(
        "/setup/sections/new/", {"class_level": six.pk, "name": "Rose", "gender_group": "boys", "is_active": "on"}
    )
    assert "campus" in r.context["form"].errors  # campus is required (project lead, 28 Oct 2026)
    boys = Campus.objects.create(branch=org["samanabad"], name="Boys Campus", gender_group="boys")
    r = client.post(
        "/setup/sections/new/",
        {"class_level": six.pk, "name": "Rose", "gender_group": "boys", "campus": boys.pk, "is_active": "on"},
    )
    assert r.status_code == 302
    assert Section.objects.filter(branch=org["samanabad"], session=org["session"], name="Rose").exists()
    r = client.post(
        "/setup/sections/new/", {"class_level": six.pk, "name": "rose", "gender_group": "boys", "is_active": "on"}
    )
    assert "name" in r.context["form"].errors  # same name again in the same class and session


def test_director_sets_own_fee_rates_only(org, make_user, login_as):
    principal = make_user("branch_owner", Scope.BRANCH, org["samanabad"])
    client = login_as(principal)
    head = FeeHead.objects.get(code="tuition")
    r = client.post("/setup/fees/rates/new/", {"head": head.pk, "amount": "4500", "effective_from": "2027-04-15"})
    assert r.status_code == 302
    rate = FeeRate.objects.get(branch=org["samanabad"], head=head, effective_from=dt.date(2027, 4, 1))
    assert rate.amount == 4500  # month rounded to its first day
    other = FeeRate.objects.create(
        branch=org["lhr_franchise"], head=head, amount=3000, effective_from=dt.date(2026, 4, 1)
    )
    assert client.get(f"/setup/fees/rates/{other.pk}/").status_code == 404


def test_branch_editing_is_scoped_and_checked(org, make_user, login_as):
    client = login_as(make_user("head_office_admin", Scope.HEAD_OFFICE, org["fsd"]))
    assert client.get(f"/setup/branches/{org['lhr_franchise'].pk}/").status_code == 403
    r = client.post(
        "/setup/branches/new/",
        {
            "code": "fsd-new",
            "name": "New FSD Branch",
            "head_office": org["fsd"].pk,
            "region": org["lhr_region"].pk,
            "ownership": "franchise",
            "royalty_percent": "8.00",
            "city": "Faisalabad",
            "is_active": "on",
        },
    )
    assert "region" in r.context["form"].errors  # region from another head office is not offered
    r = client.post(
        "/setup/branches/new/",
        {
            "code": "fsd-new",
            "name": "New FSD Branch",
            "head_office": org["fsd"].pk,
            "region": org["fsd_region"].pk,
            "ownership": "franchise",
            "royalty_percent": "8.00",
            "city": "Faisalabad",
            "is_active": "on",
        },
    )
    assert r.status_code == 302 and Branch.objects.filter(code="fsd-new", head_office=org["fsd"]).exists()


def test_menu_shows_setup_only_to_people_who_can_change_something(org, make_user, login_as, client):
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, org["samanabad"]))
    urls = {i["url"] for g in teacher.get("/").context["nav_groups"] for i in g["items"]}
    assert "/setup/" not in urls
    assert teacher.get("/setup/sections/new/").status_code == 403
    client.logout()
    principal = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    urls = {i["url"] for g in principal.get("/").context["nav_groups"] for i in g["items"]}
    assert "/setup/" in urls and principal.get("/setup/").status_code == 200
