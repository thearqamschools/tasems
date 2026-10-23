"""M4 student lifecycle: photo, brothers and sisters, leaving with certificates, promotion."""

import datetime as dt
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.academics.models import ClassLevel, Section
from apps.accounts.models import Scope
from apps.organisation.models import AcademicSession
from apps.people.models import Certificate, Enrolment, Student

pytestmark = pytest.mark.django_db


def kid(branch, adm, cnic="3310011111111", gender="male", section=None, session=None):
    s = Student.objects.create(
        branch=branch,
        admission_no=adm,
        first_name=f"Kid {adm}",
        father_name="Father",
        father_cnic=cnic,
        gender=gender,
        admission_date=dt.date(2025, 4, 1),
    )
    if section:
        Enrolment.objects.create(branch=branch, student=s, session=session, section=section)
    return s


def jpeg():
    out = io.BytesIO()
    Image.new("RGB", (1200, 1600), (200, 50, 50)).save(out, "JPEG")
    return SimpleUploadedFile("me.jpg", out.getvalue(), content_type="image/jpeg")


def test_photo_is_resized_and_private(org, make_user, login_as, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    s = kid(org["samanabad"], "101")
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    data = {
        "admission_no": "101",
        "first_name": "Kid",
        "gender": "male",
        "admission_date": "2025-04-01",
        "father_cnic": "33100-1111111-1",
        "father_name": "Father",
        "father_phone": "0300-1112223",
        "status": "active",
        "photo": jpeg(),
    }
    assert client.post(f"/students/{s.pk}/edit/", data).status_code == 302
    s.refresh_from_db()
    assert s.photo and "private/student-photos/" in s.photo.name
    with Image.open(s.photo.path) as image:
        assert max(image.size) <= 600  # small enough for the profile and ID card
    assert client.get(f"/students/{s.pk}/photo/").status_code == 200
    bad = client.post(f"/students/{s.pk}/edit/", {**data, "photo": SimpleUploadedFile("x.jpg", b"not an image")})
    assert "not an image" in bad.content.decode()  # Django's own image check
    outsider = login_as(make_user("principal", Scope.BRANCH, org["fsd_franchise"]))
    assert outsider.get(f"/students/{s.pk}/photo/").status_code == 404


def test_brothers_and_sisters_by_father_cnic(org, make_user, login_as):
    a, b = kid(org["samanabad"], "201"), kid(org["samanabad"], "202", gender="female")
    kid(org["samanabad"], "203", cnic="3310099999999")
    assert list(a.siblings()) == [b]
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    page = client.get(f"/students/{a.pk}/").content.decode()
    assert "Brothers and sisters" in page and "Kid 202" in page and "Kid 203" not in page


def test_leaving_with_certificate_and_numbering(org, make_user, login_as):
    s = kid(org["samanabad"], "301")
    client = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    response = client.post(
        f"/students/{s.pk}/leave/",
        {
            "status": "transferred",
            "left_on": "2026-10-10",
            "reason": "Moved city",
            "certificate": "on",
            "conduct": "very_good",
            "dues_cleared": "on",
        },
    )
    s.refresh_from_db()
    cert = Certificate.objects.get(student=s)
    assert s.status == "transferred" and s.status_changed_on == dt.date(2026, 10, 10)
    assert (cert.kind, cert.reference, cert.reason) == ("leaving", "TAS-HO-FSD-0001", "Moved city")
    assert response.url == f"/students/{s.pk}/certificates/{cert.pk}.pdf"
    pdf = client.get(response.url)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    other = kid(org["samanabad"], "302")
    client.post(f"/students/{other.pk}/certificates/new/", {"conduct": "good"})
    client.post(f"/students/{other.pk}/certificates/new/", {"conduct": "excellent"})
    refs = sorted(Certificate.objects.filter(kind="character").values_list("reference", flat=True))
    assert refs == ["TAS-HO-FSD-0002", "TAS-HO-FSD-0003"]  # one series per branch, never repeated
    franchise = org["fsd_franchise"]  # "Test FSD Franchise" in Faisalabad: branch initials, then the city code
    elsewhere = kid(franchise, "303")
    owner = login_as(make_user("principal", Scope.BRANCH, franchise))
    owner.post(f"/students/{elsewhere.pk}/certificates/new/", {"conduct": "good"})
    assert Certificate.objects.get(student=elsewhere).reference == "TAS-TFF-FSD-0001"  # each branch its own
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, org["samanabad"]))
    assert teacher.get(f"/students/{other.pk}/leave/").status_code == 403


def test_promotion_to_next_session(org, make_user, login_as):
    branch, now = org["samanabad"], org["session"]
    nxt = AcademicSession.objects.create(name="2027-28", starts_on=dt.date(2027, 4, 1), ends_on=dt.date(2028, 3, 31))
    four = Section.objects.create(
        branch=branch, session=now, class_level=ClassLevel.objects.get(code="class-4"), name="Rose"
    )
    ten = Section.objects.create(
        branch=branch, session=now, class_level=ClassLevel.objects.get(code="class-10"), name="Daisy"
    )
    Section.objects.create(branch=branch, session=now, class_level=ClassLevel.objects.get(code="class-5"), name="Rose")
    pass_, stay = kid(branch, "401", section=four, session=now), kid(branch, "402", section=four, session=now)
    senior = kid(branch, "403", section=ten, session=now)
    client = login_as(make_user("principal", Scope.BRANCH, branch))
    page = client.get("/students/promotion/").content.decode()
    assert "2027-28" in page
    client.post("/students/promotion/", {"action": "copy"})
    assert (
        Section.objects.filter(session=nxt).count() == 3
        and not Section.objects.filter(session=nxt, class_teacher__isnull=False).exists()
    )
    client.post(f"/students/promotion/{four.id}/", {f"action-{pass_.id}": "promote", f"action-{stay.id}": "keep"})
    assert Enrolment.objects.get(student=pass_, session=nxt).section.class_level.code == "class-5"
    assert Enrolment.objects.get(student=stay, session=nxt).section.class_level.code == "class-4"
    assert Enrolment.objects.filter(student=pass_, session=now).exists()  # this year unchanged
    client.post(f"/students/promotion/{ten.id}/", {})  # Class 10 graduates by default
    senior.refresh_from_db()
    assert senior.status == "graduated" and not Enrolment.objects.filter(student=senior, session=nxt).exists()
    teacher = login_as(make_user("class_teacher", Scope.BRANCH, branch))
    assert teacher.get("/students/promotion/").status_code == 403


def test_id_cards_for_a_student_and_a_section(org, make_user, login_as):
    branch, now = org["samanabad"], org["session"]
    rose = Section.objects.create(
        branch=branch, session=now, class_level=ClassLevel.objects.get(code="class-4"), name="Rose"
    )
    a = kid(branch, "501", section=rose, session=now)
    kid(branch, "502", section=rose, session=now)
    client = login_as(make_user("principal", Scope.BRANCH, branch))
    one = client.get(f"/students/id-cards.pdf?student={a.pk}")
    assert one.status_code == 200 and one.content.startswith(b"%PDF")
    many = client.get(f"/students/id-cards.pdf?class={rose.class_level_id}&section=Rose")
    assert many.status_code == 200 and many.content.startswith(b"%PDF")
    outsider = login_as(make_user("principal", Scope.BRANCH, org["fsd_franchise"]))
    assert outsider.get(f"/students/id-cards.pdf?student={a.pk}").status_code == 404


def test_defaulters_by_family(org, make_user, login_as):
    from decimal import Decimal

    from apps.fees import services as S
    from apps.fees.models import FeeHead

    branch = org["samanabad"]
    principal = make_user("principal", Scope.BRANCH, branch)
    a, b = kid(branch, "601"), kid(branch, "602")  # same father's CNIC
    c = kid(branch, "603", cnic="3310077777777")
    for s, amount in ((a, 3000), (b, 2000), (c, 1500)):
        S.add_charge(
            s, FeeHead.objects.get(code="tuition"), dt.date(2026, 9, 1), Decimal(amount), principal, note="Test"
        )
    client = login_as(principal)
    page = client.get("/fees/defaulters/?by=family").content.decode()
    assert "5,000" in page and "1,500" in page  # one family owes 5,000 for two children
    assert page.index("5,000") < page.index("1,500")  # largest family first


def test_reference_starts_are_made_from_the_branch(org):
    """Project lead, 23 Oct 2026: TAS-<HO or branch initials>-<city code>, unique in the network."""
    from apps.organisation.models import Branch

    assert org["samanabad"].reference_prefix == "TAS-HO-FSD"
    assert org["lhr_franchise"].reference_prefix == "TAS-TLF-LHR" and org["lhr_franchise"].city_code == "LHR"
    gulberg = Branch.objects.create(
        code="t-gc", name="Gulberg Colony Campus", head_office=org["fsd"], city="Faisalabad"
    )
    twin = Branch.objects.create(code="t-gc2", name="Ghulam Colony", head_office=org["fsd"], city="Faisalabad")
    assert (gulberg.reference_prefix, twin.reference_prefix) == ("TAS-GC-FSD", "TAS-GC2-FSD")
    sialkot = Branch.objects.create(
        code="t-skt", name="Model Town", head_office=org["lhr"], city="Sialkot", city_code="skt"
    )
    assert sialkot.reference_prefix == "TAS-MT-SKT"  # other cities: the code head office enters
