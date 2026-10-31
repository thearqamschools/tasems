"""Round 5 (project lead, 31 Oct 2026): student search and campus filter, Events & Tickets (list, report, banks),
side menu groups, staff qualifications, payroll (manual days, paying, increments, acknowledgement sheet)."""

import datetime as dt
from decimal import Decimal

import pytest

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.events.models import Event, EventClass, TicketSale
from apps.fees.models import BankAccount
from apps.hr.models import Employee, StaffDay
from apps.organisation.models import Campus
from apps.payroll import services as P
from apps.payroll.models import EmployeePay, PayrollRun, SalaryChange
from apps.people.models import Enrolment, Guardian, Student, StudentGuardian

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def school(org, make_user):
    branch = org["samanabad"]
    girls = Campus.objects.create(branch=branch, name="Girls Campus", gender_group="girls")
    boys = Campus.objects.create(branch=branch, name="Boys Campus", gender_group="boys")
    four = ClassLevel.objects.get(code="class-4")
    six = ClassLevel.objects.get(code="class-6")
    s4 = Section.objects.create(branch=branch, session=org["session"], class_level=four, name="Rose", campus=girls)
    s6 = Section.objects.create(
        branch=branch, session=org["session"], class_level=six, name="Rose", gender_group="boys", campus=boys
    )

    def kid(adm, name, section, cnic="3310011111111", gender="female"):
        s = Student.objects.create(
            branch=branch, admission_no=adm, first_name=name, gender=gender, father_name="Naveed",
            father_cnic=cnic, admission_date=dt.date(2026, 4, 1),
        )  # fmt: skip
        Enrolment.objects.create(branch=branch, student=s, session=org["session"], section=section)
        return s

    fiza = kid("4453", "Fiza", s4)
    fakhar = kid("1465", "Fakhar", s6, cnic="3310022222222", gender="male")
    mother = Guardian.objects.create(branch=branch, full_name="Mother", phone="03214445556")
    StudentGuardian.objects.create(student=fiza, guardian=mother, relationship="mother")
    return {
        "branch": branch, "girls": girls, "boys": boys, "four": four, "six": six, "fiza": fiza, "fakhar": fakhar,
        "director": make_user("branch_owner", Scope.BRANCH, branch, first_name="Demo", last_name="Director"),
        "accountant": make_user("accountant", Scope.BRANCH, branch, first_name="Demo", last_name="Accountant"),
    }  # fmt: skip


def test_student_search_by_any_mobile_cnic_and_campus(school, login_as):
    client = login_as(school["director"])

    def names(query):
        return {s.first_name for s in client.get(f"/students/?{query}").context["page"].object_list}

    assert names("q=0321-4445556") == {"Fiza"}  # the mother's mobile, typed with a dash
    assert names("q=33100-2222222-2") == {"Fakhar"}  # father CNIC
    assert names(f"campus={school['boys'].id}") == {"Fakhar"}
    page = client.get("/students/").content.decode()
    assert 'name="campus"' in page and "Girls Campus" in page


def test_events_sell_by_class_bank_report(school, login_as):
    branch = school["branch"]
    bank = BankAccount.objects.create(branch=branch, name="Meezan Bank", account_number="0101")
    event = Event.objects.create(branch=branch, name="Gala", date=dt.date(2026, 12, 1), created_by=school["director"])
    EventClass.objects.create(branch=branch, event=event, class_level=school["four"], price=1000)
    EventClass.objects.create(branch=branch, event=event, class_level=school["six"], price=1500)
    client = login_as(school["accountant"])
    page = client.get(f"/events/{event.id}/sell/?class={school['six'].id}").content.decode()
    assert "Fakhar" in page and "Fiza" not in page and "Boys Campus" in page
    here = f"/events/{event.id}/sell/?class={school['six'].id}"
    answer = client.post(f"/events/{event.id}/sell/", {"student": school["fakhar"].id, "paid_by": "bank", "next": here})
    assert answer.url == here and not TicketSale.objects.exists()  # a bank sale needs the bank
    client.post(f"/events/{event.id}/sell/", {"student": school["fakhar"].id, "paid_by": "bank", "bank": bank.id})
    client.post(f"/events/{event.id}/sell/", {"student": school["fiza"].id, "paid_by": "cash"})
    assert TicketSale.objects.get(student=school["fakhar"]).bank == bank
    recent = client.get(f"/events/{event.id}/sell/").content.decode()
    assert "1465" in recent and "Six" in recent  # last receipts show admission no. and class
    index = client.get("/events/").content.decode()
    assert f'data-href="/events/{event.id}/"' in index  # the whole row opens the event
    report = client.get(f"/events/{event.id}/report/").content.decode()
    assert "EVENT REPORT — DETAIL" in report and "EVENT REPORT — SUMMARY" in report
    assert "Meezan Bank" in report and "Demo Accountant" in report and "2,500" in report and "Profit" in report


def test_side_menu_groups_open_and_close(school, login_as):
    page = login_as(school["director"]).get("/events/").content.decode()
    assert 'class="nav-group-label" aria-expanded="true"' in page  # the group of this page is open
    assert 'aria-expanded="false"' in page and " hidden>" in page  # the others start closed


def test_staff_qualifications_certificates_experience(school, login_as):
    client = login_as(school["director"])
    form = client.get("/staff/new/").content.decode()
    assert form.index('name="cv"') < form.index('name="code"')  # CV first
    assert "Last qualification" in form and "qualifications-TOTAL_FORMS" in form
    data = {
        "code": "T-9", "full_name": "Sana Khan", "father_name": "Khan", "gender": "female",
        "designation": "Senior Teacher",
        "staff_type": "teaching", "joined_on": "2026-04-01", "status": "active", "qualification": "MA English",
        "qualifications-TOTAL_FORMS": "2", "qualifications-INITIAL_FORMS": "0",
        "qualifications-0-level": "matric", "qualifications-0-institute": "BISE Faisalabad",
        "qualifications-0-year": "2010",
        "qualifications-1-level": "master", "qualifications-1-degree": "MA English", "qualifications-1-year": "2016",
        "certificates-TOTAL_FORMS": "1", "certificates-INITIAL_FORMS": "0", "certificates-0-name": "",
        "experiences-TOTAL_FORMS": "1", "experiences-INITIAL_FORMS": "0", "experiences-0-organisation": "City School",
        "experiences-0-started_on": "2017-04-01", "experiences-0-ended_on": "2026-03-31",
        "experiences-0-reason_left": "Moved",
    }  # fmt: skip
    answer = client.post("/staff/new/", data)
    assert answer.status_code == 302, answer.content.decode()[:3000]
    e = Employee.objects.get(code="T-9")
    assert [q.level for q in e.qualifications.all()] == ["matric", "master"] and e.experiences.count() == 1
    assert not e.certificates.exists()  # the empty row is left out
    page = client.get(f"/staff/{e.id}/").content.decode()
    assert "BISE Faisalabad" in page and "City School" in page and 'href="/staff/"' in page


@pytest.fixture
def payroll(school, monkeypatch):
    from django.utils import timezone

    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: dt.date(2026, 11, 5))
    branch = school["branch"]

    def person(code, designation, salary):
        e = Employee.objects.create(
            branch=branch, code=code, full_name=f"Staff {code}", gender="female", designation=designation,
            staff_type="teaching", joined_on=dt.date(2025, 1, 1),
        )  # fmt: skip
        EmployeePay.objects.create(branch=branch, employee=e, monthly_salary=salary)
        return e

    teacher = person("E1", "Senior Teacher", D(31000))
    guard = person("E2", "Guard", D(20000))
    StaffDay.objects.create(branch=branch, employee=teacher, date=dt.date(2026, 10, 5), status="absent")
    return {**school, "teacher": teacher, "guard": guard}


OCT = "2026-10"


def test_manual_days_replace_the_machine(payroll, login_as):
    client = login_as(payroll["accountant"])
    t = payroll["teacher"]
    page = client.get(f"/payroll/manual/?month={OCT}").content.decode()
    assert f'name="absent_days_{t.id}"' in page
    figures = {"days_in_month": "31", "working_days": "26", "days_employed": "31", "absent_days": "3",
               "leave_days": "0", "half_days": "2"}  # fmt: skip
    client.post(f"/payroll/manual/?month={OCT}", {f"use_{t.id}": "1", **{f"{k}_{t.id}": v for k, v in figures.items()}})
    rows, _totals = P.compute(payroll["branch"], dt.date(2026, 10, 1))
    row = next(r for r in rows if r["employee"] == t)
    assert row["manual"] and row["absent"] == 3 and row["deduction"] == D(4000)  # 1000 a day × (3 + 2 halves)
    bad = {f"use_{t.id}": "1", **{f"{k}_{t.id}": v for k, v in figures.items()}, f"absent_days_{t.id}": "40"}
    assert "Check the days of" in client.post(f"/payroll/manual/?month={OCT}", bad, follow=True).content.decode()


def test_pay_each_person_totals_and_lock(payroll, login_as):
    client = login_as(payroll["accountant"])
    client.post(f"/payroll/finalise/?month={OCT}")
    run = PayrollRun.objects.get()
    page = client.get(f"/payroll/?month={OCT}").content.decode()
    assert "Still to pay" in page and "Not paid" in page
    t = payroll["teacher"]
    client.post(f"/payroll/staff/{t.id}/?month={OCT}", {"action": "pay", "paid_on": "2026-11-05", "method": "cash"})
    slip = run.payslips.get(employee=t)
    assert slip.payment.method == "cash" and slip.payment.amount == slip.net_pay == D(30000)
    again = client.post(
        f"/payroll/staff/{t.id}/?month={OCT}", {"action": "pay", "paid_on": "2026-11-05", "method": "bank"}, follow=True
    )
    assert "already paid" in again.content.decode() and slip.payment.method == "cash"
    rows, totals = P.run_rows(run)
    assert totals["paid"] == D(30000) and totals["to_pay"] == D(20000) and totals["paid_staff"] == 1
    page = client.get(f"/payroll/?month={OCT}&designation=Guard").content.decode()
    assert "Staff E2" in page and "Staff E1" not in page  # filter by designation
    person = client.get(f"/payroll/staff/{t.id}/?month={OCT}").content.decode()
    assert "Salary history" in person and "October 2026" in person
    director = login_as(payroll["director"])
    director.post(f"/payroll/{run.id}/cancel/", {"reason": "x"})
    run.refresh_from_db()
    assert run.status == "final"  # a month with paid salaries cannot be reopened
    pdf = director.get(f"/payroll/acknowledgement.pdf?month={OCT}")
    assert pdf["Content-Type"] == "application/pdf" and pdf.content[:4] == b"%PDF"


def test_increment_from_a_month_keeps_earlier_months(payroll, login_as):
    client = login_as(payroll["director"])
    g = payroll["guard"]
    client.post(
        f"/payroll/staff/{g.id}/",
        {"action": "increment", "from_month": "2026-11", "new_salary": "22000", "reason": "Annual",
         "approved_by": "Director"},
    )  # fmt: skip
    change = SalaryChange.objects.get()
    assert (change.old_salary, change.new_salary) == (D(20000), D(22000))
    oct_rows, _ = P.compute(payroll["branch"], dt.date(2026, 10, 1))
    nov_rows, _ = P.compute(payroll["branch"], dt.date(2026, 11, 1))
    assert next(r for r in oct_rows if r["employee"] == g)["salary"] == D(20000)
    assert next(r for r in nov_rows if r["employee"] == g)["salary"] == D(22000)
    assert EmployeePay.objects.get(employee=g).monthly_salary == D(22000)  # salary now
