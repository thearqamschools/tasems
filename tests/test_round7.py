"""Round 7 (project lead, 6 Nov 2026): Biometric ID rules, machine names matched only with confirmation, staff
attendance in two parts (machine / by hand), In and Out times per staff type from a date, late / early left / missing
In or Out, staff list columns and sorting, staff page layout."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.accounts.models import Scope
from apps.hr import services as S
from apps.hr.models import AttendanceMachine, DutyTime, Employee, Punch, StaffDay

from .test_round6 import fake_machine

pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 11, 6)  # Friday
MON, TUE, WED, THU = (dt.date(2026, 11, d) for d in (2, 3, 4, 5))


@pytest.fixture
def staff(org, make_user, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *a, **k: TODAY)
    branch = org["samanabad"]

    def person(code, name, machine_id="", staff_type="teaching", designation="Teacher"):
        e = Employee.objects.create(
            branch=branch, code=code, machine_id=machine_id, full_name=name, gender="female",
            designation=designation, staff_type=staff_type, joined_on=dt.date(2026, 4, 1),
        )  # fmt: skip
        if machine_id:
            Employee.objects.filter(pk=e.pk).update(machine_id_since=dt.date(2026, 10, 1))
            e.refresh_from_db()
        return e

    director = make_user("branch_owner", Scope.BRANCH, branch, first_name="Demo", last_name="Director")
    return {"branch": branch, "person": person, "director": director}


def punch(e, date, hh, mm, user):
    at = timezone.make_aware(dt.datetime.combine(date, dt.time(hh, mm)))
    return Punch.objects.create(branch=e.branch, employee=e, at=at, created_by=user, source=Punch.Source.MACHINE)


def day(e, date):
    return StaffDay.objects.filter(employee=e, date=date).first()


def test_no_biometric_id_is_never_marked_by_the_machine(staff):
    on_machine = staff["person"]("E1", "Sana", machine_id="11")
    by_hand = staff["person"]("E2", "Hina")
    punch(on_machine, TUE, 7, 40, staff["director"])
    S.rebuild_days(staff["branch"], MON, THU)
    assert day(on_machine, WED).status == "absent"  # on the machine: no punch on a working day is absent
    assert day(by_hand, WED) is None and day(by_hand, TUE) is None  # never marked; entered by hand


def test_machine_marks_from_the_day_the_id_is_known(staff):
    late_enrolled = staff["person"]("E3", "Asma")
    late_enrolled.machine_id = "15"
    late_enrolled.save()
    assert late_enrolled.machine_id_since == TODAY
    S.rebuild_days(staff["branch"], MON, THU)
    assert not StaffDay.objects.filter(employee=late_enrolled, status="absent").exists()


def test_reading_only_works_out_the_staff_whose_punches_came(staff, login_as):
    on_machine = staff["person"]("E1", "Sana", machine_id="17")
    other = staff["person"]("E4", "Rabia", machine_id="18")
    by_hand = staff["person"]("E2", "Hina")
    yesterday = dt.datetime.combine(THU, dt.time(7, 40))
    port, thread = fake_machine(
        [("17", yesterday), ("17", yesterday.replace(hour=13, minute=50)), ("40", yesterday)],
        users={"17": "Sana", "18": "Rabia", "40": "Ahmad", "41": "Ahmad", "42": "Maryam Bibi"},
    )
    client = login_as(staff["director"])
    client.post("/staff/attendance/machines/", {"action": "save", "name": "Gate", "host": "127.0.0.1", "port": port,
                                                "comm_key": "0", "auto_read": "on"})  # fmt: skip
    machine = AttendanceMachine.objects.get()
    client.post("/staff/attendance/machines/", {"action": "read", "machine": machine.id})
    thread.join(5)
    machine.refresh_from_db()
    assert machine.users["40"] == "Ahmad" and machine.users["42"] == "Maryam Bibi"
    assert day(on_machine, THU).status == "present"
    assert day(other, THU) is None and day(by_hand, THU) is None  # nobody else worked out from this reading


def test_match_by_name_only_after_confirmation(staff, login_as):
    maryam = staff["person"]("E5", "Maryam Bibi")
    ahmad_1 = staff["person"]("E6", "Ahmad")
    staff["person"]("E7", "Ahmad")
    machine = AttendanceMachine.objects.create(
        branch=staff["branch"], host="127.0.0.1", added_by=staff["director"],
        users={"40": "Ahmad", "41": "Ahmad", "42": "Maryam Bibi"}, unknown_ids={"42": 12},
    )  # fmt: skip
    rows, _free = S.match_rows(machine)
    by_number = {r["number"]: r for r in rows}
    assert by_number["42"]["suggested"] == maryam and by_number["42"]["punches"] == 12
    assert by_number["40"]["suggested"] is None and by_number["40"]["same_name"]  # two Ahmads: choose by hand
    maryam.refresh_from_db()
    assert maryam.machine_id == ""  # nothing saved by itself
    client = login_as(staff["director"])
    page = client.get("/staff/attendance/machines/").content.decode()
    assert "same name, choose by hand" in page and "name matches" in page
    client.post(
        "/staff/attendance/machines/",
        {"action": "match", "machine": machine.id, "use": ["42", "40"], "staff_42": maryam.id,
         "staff_40": ahmad_1.id, "staff_41": ahmad_1.id},
    )  # fmt: skip
    maryam.refresh_from_db()
    ahmad_1.refresh_from_db()
    assert maryam.machine_id == "42" and ahmad_1.machine_id == "40"  # only the ticked rows


def test_times_per_staff_type_from_a_date_late_early_and_missing(staff, login_as):
    teacher = staff["person"]("E1", "Sana", machine_id="11")
    guard = staff["person"]("E8", "Akram", machine_id="12", staff_type="support", designation="Guard")
    client = login_as(staff["director"])
    page = client.get("/staff/attendance/times/").content.decode()
    assert "Support staff" in page and "07:45" in page
    # Winter times from Wednesday: teachers 08:00–14:00; support staff 07:00–17:00.
    data = {"starts_from": "2026-11-04", "label": "Winter times", "in_teaching": "08:00", "out_teaching": "14:00",
            "grace_teaching": "5", "in_support": "07:00", "out_support": "17:00", "grace_support": "0"}  # fmt: skip
    client.post("/staff/attendance/times/", data)
    assert DutyTime.objects.filter(starts_from=WED, staff_type="support").exists()
    p = staff["director"]
    punch(teacher, TUE, 7, 55, p)  # Tuesday keeps 07:45 (+0): late
    punch(teacher, TUE, 13, 50, p)
    punch(teacher, WED, 8, 4, p)  # winter 08:00 + 5 minutes: on time
    punch(teacher, WED, 12, 30, p)  # before 14:00: early left
    punch(teacher, THU, 7, 58, p)  # In, no Out
    punch(guard, WED, 17, 5, p)  # Out, no In
    S.rebuild_days(staff["branch"], TUE, THU)
    assert day(teacher, TUE).status == "late" and not day(teacher, TUE).early_left
    assert day(teacher, WED).status == "present" and day(teacher, WED).early_left
    assert day(teacher, THU).status == "present" and day(teacher, THU).missing == "out"
    g = day(guard, WED)
    assert g.status == "present" and g.missing == "in" and g.first_in is None and g.last_out == dt.time(17, 5)
    sheet = client.get("/staff/attendance/month/?month=2026-11").content.decode()
    assert "Pe" in sheet and "P!" in sheet and "Guard" in sheet and "EMP.code" in sheet
    today_page = client.get("/staff/attendance/?date=2026-11-04").content.decode()
    assert "Early left" in today_page and "Out, no In" in today_page


def test_attendance_in_two_parts_and_entered_by_hand(staff, login_as):
    staff["person"]("E1", "Sana", machine_id="11")
    hina = staff["person"]("E2", "Hina")
    client = login_as(staff["director"])
    page = client.get("/staff/attendance/?date=2026-11-05").content.decode()
    assert "From the attendance machine" in page and "Entered by hand" in page
    assert page.index("Sana") < page.index("Entered by hand") < page.index("Hina")
    entry = {"action": "hand", f"status_{hina.id}": "late", f"in_{hina.id}": "08:10", f"out_{hina.id}": "13:00"}
    client.post("/staff/attendance/?date=2026-11-05", entry)
    d = day(hina, THU)
    assert d.status == "late" and d.first_in == dt.time(8, 10) and d.is_corrected and d.early_left
    S.rebuild_days(staff["branch"], THU, THU)
    assert day(hina, THU).status == "late"  # kept


def test_staff_list_columns_sorting_and_staff_page(staff, login_as):
    staff["person"]("E10", "Zainab", machine_id="5")
    staff["person"]("E2", "Bushra")
    a = staff["person"]("E9", "Amna", designation="Aapa")
    client = login_as(staff["director"])
    page = client.get("/staff/").content.decode()
    heads = [
        page.index(h) for h in ("EMP.code", "Machine ID", ">Name<", "Designation", "Type", "Mobile", "Joining date")
    ]
    assert heads == sorted(heads)
    by_code = client.get("/staff/?sort=code").content.decode()
    assert by_code.index("Bushra") < by_code.index("Amna") < by_code.index("Zainab")  # E2, E9, E10
    by_name_desc = client.get("/staff/?sort=-name").content.decode()
    assert by_name_desc.index("Zainab") < by_name_desc.index("Bushra") < by_name_desc.index("Amna")
    assert 'aria-sort="descending"' in by_name_desc
    person = client.get(f"/staff/{a.id}/").content.decode()
    assert person.index("Record leave") < person.index("actions-end")  # Delete on the far right
    assert "Biometric ID not set" in person
