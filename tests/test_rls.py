"""Database-level branch isolation (row-level security)."""

import pytest
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction

from apps.accounts.models import Scope
from apps.core.rls import branch_scope
from apps.people.models import Student

pytestmark = pytest.mark.django_db


@pytest.fixture
def app_role(db):
    """Runs queries as an ordinary role, like production (superusers ignore row-level security)."""
    with connection.cursor() as cursor:
        cursor.execute("CREATE ROLE tasems_rls_test NOSUPERUSER NOBYPASSRLS")
        cursor.execute("GRANT USAGE ON SCHEMA public TO tasems_rls_test")
        cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO tasems_rls_test")
        cursor.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO tasems_rls_test")
        cursor.execute("SET ROLE tasems_rls_test")
    yield
    with connection.cursor() as cursor:
        cursor.execute("RESET ROLE")


def test_database_hides_other_branches_even_without_filters(org, students, app_role):
    assert Student.objects.count() == 3  # no web request: no restriction (jobs, commands)
    with branch_scope([org["samanabad"].id]):
        assert list(Student.objects.values_list("admission_no", flat=True)) == ["S-1"]
    with branch_scope([]):
        assert Student.objects.count() == 0


def test_database_refuses_writes_into_other_branches(org, students, app_role):
    with branch_scope([org["samanabad"].id]):
        with pytest.raises(DatabaseError), transaction.atomic():
            Student.objects.create(
                branch=org["lhr_franchise"],
                admission_no="X-1",
                first_name="X",
                gender="male",
                admission_date="2026-04-01",
            )
        # and cannot move a visible record into another branch
        with pytest.raises(DatabaseError), transaction.atomic():
            Student.objects.filter(admission_no="S-1").update(branch=org["lhr_franchise"])


def test_web_requests_are_scoped(org, students, make_user, login_as, app_role):
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    body = client.get("/students/?status=all").content.decode()
    assert "S-1" in body and "L-1" not in body
    # scope is cleared after the request
    assert Student.objects.count() == 3


def test_security_check_reports_superuser_connection(db, capsys):
    call_command("check_security")
    out = capsys.readouterr().out
    assert "superuser" in out or "Security check passed" in out


def test_every_branch_table_has_the_policy(db):
    from apps.core.rls import RLS_TABLES

    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_policies WHERE policyname = 'branch_isolation'")
        protected = {row[0] for row in cursor.fetchall()}
    assert set(RLS_TABLES) <= protected
    assert {"fees_voucher", "fees_charge", "fees_payment"} <= protected
