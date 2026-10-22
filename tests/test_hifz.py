"""M12: Hifz-e-Quran — the day's Sabaq, Sabqi and Manzil, para tests, progress and the parents' view."""

import datetime as dt

import pytest
from django.utils import timezone

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.attendance.models import AttendanceRecord
from apps.core.models import AuditEvent
from apps.hifz import services as S
from apps.hifz.models import HifzLesson, ParaTest
from apps.people.models import Enrolment, Guardian, Student, StudentGuardian
from tests.test_parents import PASSWORD, PHONE, set_up

pytestmark = pytest.mark.django_db
TODAY = dt.date(2026, 10, 5)  # a Monday


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: TODAY)


@pytest.fixture
def hifz(org, make_user):
    branch = org["samanabad"]
    qari = make_user("hifz_teacher", Scope.BRANCH, branch)
    section = Section.objects.create(
        branch=branch, session=org["session"], class_level=ClassLevel.objects.get(code="hifz"), name="Boys",
        gender_group="boys", class_teacher=qari,
    )  # fmt: skip
    kids = []
    for n, name in enumerate(["Abdullah", "Usman"], 1):
        s = Student.objects.create(
            branch=branch, admission_no=str(400 + n), first_name=name, gender="male", admission_date=dt.date(2026, 4, 1)
        )
        Enrolment.objects.create(branch=branch, student=s, session=org["session"], section=section, roll_no=n)
        kids.append(s)
    regular = Section.objects.create(
        branch=branch, session=org["session"], class_level=ClassLevel.objects.get(code="class-5"), name="A"
    )
    day_hifz = Student.objects.create(
        branch=branch, admission_no="501", first_name="Hamza", gender="male", admission_date=dt.date(2026, 4, 1),
        is_hifz=True,
    )  # fmt: skip
    Enrolment.objects.create(branch=branch, student=day_hifz, session=org["session"], section=regular)
    other = Student.objects.create(
        branch=branch, admission_no="502", first_name="Bilal", gender="male", admission_date=dt.date(2026, 4, 1)
    )
    Enrolment.objects.create(branch=branch, student=other, session=org["session"], section=regular)
    principal = make_user("principal", Scope.BRANCH, branch)
    return {"branch": branch, "qari": qari, "section": section, "kids": kids, "regular": regular,
            "day_hifz": day_hifz, "principal": principal, "session": org["session"]}  # fmt: skip


def row(**kw):
    data = {"status": "heard", "sabaq_para": "3", "sabaq": "Al-Baqarah 142-157", "sabaq_lines": "15",
            "sabaq_mistakes": "2", "sabqi": "2", "sabqi_mistakes": "1", "manzil": "1", "manzil_mistakes": "0",
            "grade": "good", "remarks": ""}  # fmt: skip
    data.update(kw)
    return data


def post_data(students, **kw):
    out = {}
    for s in students:
        for k, v in row(**kw).items():
            out[f"{s.id}-{k}"] = v
    return out


def test_hifz_sections_and_students(hifz):
    sections = S.sections(hifz["branch"], hifz["session"])
    assert hifz["section"] in sections and hifz["regular"] in sections  # a section with a student marked Hifz
    assert [e.student for e in S.roster(hifz["regular"])] == [hifz["day_hifz"]]  # Bilal is not doing Hifz
    assert set(S.hifz_students(hifz["branch"], hifz["session"])) == {*hifz["kids"], hifz["day_hifz"]}


def test_qari_records_the_day_and_corrections_are_logged(hifz, login_as):
    client = login_as(hifz["qari"])
    AttendanceRecord.objects.create(
        branch=hifz["branch"],
        student=hifz["kids"][1],
        section=hifz["section"],
        date=TODAY,
        status="absent",
        marked_by=hifz["qari"],
    )
    url = f"/hifz/section/{hifz['section'].id}/{TODAY}/"
    page = client.get(url)
    assert page.status_code == 200
    statuses = {r["enrolment"].student_id: r["lesson"].status for r in S.sheet(hifz["section"], TODAY)}
    assert statuses[hifz["kids"][1].id] == "absent"  # follows the register
    done = client.post(url, post_data(hifz["kids"]))
    assert done.status_code == 302
    assert HifzLesson.objects.count() == 2 and HifzLesson.objects.get(student=hifz["kids"][0]).mistakes == 3
    assert not AuditEvent.objects.filter(model_label="hifz.HifzLesson").exists()  # new lines are not logged
    client.post(url, post_data(hifz["kids"], sabaq_mistakes="5"))
    assert HifzLesson.objects.get(student=hifz["kids"][0]).sabaq_mistakes == 5
    assert AuditEvent.objects.filter(model_label="hifz.HifzLesson").count() == 2
    nxt = S.sheet(hifz["section"], TODAY + dt.timedelta(days=1))
    assert nxt[0]["lesson"].sabaq_para == 3  # tomorrow continues the same para


def test_absent_keeps_only_status_and_bad_values_are_refused(hifz, login_as):
    client = login_as(hifz["qari"])
    url = f"/hifz/section/{hifz['section'].id}/{TODAY}/"
    bad = client.post(url, post_data(hifz["kids"], sabaq_para="31"))
    assert bad.status_code == 200 and not HifzLesson.objects.exists()
    client.post(url, post_data(hifz["kids"], status="absent"))
    lesson = HifzLesson.objects.get(student=hifz["kids"][0])
    assert lesson.status == "absent" and lesson.sabaq == "" and lesson.sabaq_mistakes == 0


def test_who_may_record(hifz, login_as, make_user):
    qari = login_as(hifz["qari"])
    yesterday = TODAY - dt.timedelta(days=1)  # a Sunday: no school
    assert qari.get(f"/hifz/section/{hifz['section'].id}/{yesterday}/").status_code == 403
    friday = TODAY - dt.timedelta(days=3)
    assert qari.get(f"/hifz/section/{hifz['section'].id}/{friday}/").status_code == 403  # teachers: today only
    assert qari.get(f"/hifz/section/{hifz['regular'].id}/{TODAY}/").status_code == 403  # not their section
    principal = login_as(hifz["principal"])
    assert principal.get(f"/hifz/section/{hifz['section'].id}/{friday}/").status_code == 200
    saturday = TODAY - dt.timedelta(days=2)
    assert principal.get(f"/hifz/section/{hifz['section'].id}/{saturday}/").status_code == 200  # Hifz on Saturday
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, hifz["branch"]))
    assert teacher.get("/hifz/").status_code == 403


def test_para_tests_and_progress(hifz, login_as):
    kid = hifz["kids"][0]
    qari = login_as(hifz["qari"])
    assert qari.post(f"/hifz/student/{kid.id}/", {"para": 1}).status_code == 403  # tests by senior staff
    principal = login_as(hifz["principal"])
    for para in (1, 2):
        principal.post(f"/hifz/student/{kid.id}/", {"para": para, "tested_on": "2026-09-01", "result": "passed",
                                                    "mistakes": 0, "before_joining": "on"})  # fmt: skip
    principal.post(f"/hifz/student/{kid.id}/", {"para": 3, "tested_on": "2026-10-03", "result": "passed",
                                                "mistakes": 2})  # fmt: skip
    assert ParaTest.objects.filter(student=kid, result="passed").count() == 3
    with pytest.raises(ValueError):
        S.record_test(kid, 3, TODAY, "passed", 0, hifz["principal"])
    S.save_sheet(hifz["section"], TODAY, {kid.id: {k: v for k, v in _clean(row(sabaq_para=4)).items()}},
                 hifz["principal"])  # fmt: skip
    page = principal.get(f"/hifz/student/{kid.id}/").content.decode()
    assert "3 / 30" in page and 'class="done"' in page
    report = principal.get(f"/hifz/report/?section={hifz['section'].id}&month=2026-10")
    r = next(x for x in report.context["rows"] if x["student"] == kid)
    assert r["paras"] == 3 and r["current"] == 4 and r["heard"] == 1 and r["mistakes"] == 3.0
    xlsx = principal.get(f"/hifz/report/?section={hifz['section'].id}&format=xlsx")
    assert xlsx["Content-Type"].startswith("application/vnd.openxml")
    home = principal.get("/hifz/").content.decode()
    assert "Hifz students" in home and 'href="/hifz/"' in home
    test = ParaTest.objects.get(student=kid, para=3)
    principal.post(f"/hifz/student/{kid.id}/tests/{test.id}/cancel/")
    assert S.passed_paras([kid])[kid.id].keys() == {1, 2}
    assert "Hifz-e-Quran" in principal.get("/reports/").content.decode()


def _clean(data):
    ints = {"sabaq_para", "sabaq_lines", "sabaq_mistakes", "sabqi_mistakes", "manzil_mistakes"}
    return {k: (int(v) if k in ints else v) for k, v in data.items()}


def test_parents_see_their_childs_hifz(client, login_as, hifz):
    kid = hifz["kids"][0]
    guardian = Guardian.objects.create(branch=hifz["branch"], full_name="Abdul Rauf", phone=PHONE)
    StudentGuardian.objects.create(student=kid, guardian=guardian, relationship="father", is_primary_contact=True)
    S.record_test(kid, 1, TODAY, "passed", 0, hifz["principal"])
    S.save_sheet(hifz["section"], TODAY, {kid.id: _clean(row(remarks="Well done"))}, hifz["principal"])
    set_up(client, login_as, {"principal": hifz["principal"], "kids": [kid]})
    assert client.post("/parents/login/", {"phone": PHONE, "password": PASSWORD}).status_code in (200, 302)
    page = client.get(f"/parents/child/{kid.id}/?tab=hifz").content.decode()
    assert "1 / 30" in page and "Well done" in page and "?tab=hifz" in page
