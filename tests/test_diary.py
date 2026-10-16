"""Daily Diary: writing, empty-subject rule, permissions, PDF and WhatsApp image."""

import datetime as dt
import io

import pytest
from django.core.management import call_command
from django.utils import timezone
from PIL import Image

from apps.academics.models import ClassLevel, Section, Subject
from apps.accounts.models import Scope
from apps.diary import services
from apps.diary.models import Diary, DiaryWeek

pytestmark = pytest.mark.django_db

WEDNESDAY = dt.date(2026, 10, 14)


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda *args, **kwargs: WEDNESDAY)


@pytest.fixture
def class4(org, make_user):
    teacher = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    section = Section.objects.create(
        branch=org["samanabad"],
        session=org["session"],
        class_level=ClassLevel.objects.get(code="class-4"),
        name="A",
        class_teacher=teacher,
    )
    return {"section": section, "teacher": teacher}


def sid(code):
    return Subject.objects.get(code=code).id


def write_url(section, day=WEDNESDAY):
    return f"/diary/section/{section.pk}/{day.isoformat()}/"


def test_class4_subjects_follow_the_shared_diary(class4):
    names = [s.name for s, _o in services.subjects_for(class4["section"])]
    assert names == ["English", "Science", "Mathematics", "Computer", "Islamiyat", "Urdu", "Al-Quran"]


def test_teacher_writes_and_publishes(class4, login_as):
    client = login_as(class4["teacher"])
    assert client.get(write_url(class4["section"])).status_code == 200
    response = client.post(
        write_url(class4["section"]),
        {
            f"c{sid('english')}": "Unit 8 explained.",
            f"h{sid('english')}": "Learn the words of Unit 8.",
            f"d{sid('english')}": "2026-10-15",
            f"c{sid('urdu')}": "سبق نمبر 10 پڑھایا گیا۔",
            "publish": "1",
        },
    )
    diary = Diary.objects.get(section=class4["section"], date=WEDNESDAY)
    assert response.status_code == 302 and diary.status == Diary.Status.PUBLISHED
    assert diary.entries.count() == 2  # empty subjects are not stored


def test_empty_parts_are_left_out_of_the_diary(class4):
    diary = services.save_diary(
        class4["section"],
        WEDNESDAY,
        class4["teacher"],
        {
            sid("english"): {"in_class": "Unit 8.", "home_task": "", "deadline": None},
            sid("science"): {"in_class": "", "home_task": "Read pages 69-70.", "deadline": dt.date(2026, 10, 15)},
            sid("urdu"): {"in_class": "سبق نمبر 10", "home_task": "", "deadline": None},
        },
    )
    context = services.document_context(diary)
    assert [e.subject.code for e in context["in_class"]] == ["english", "urdu"]
    assert [e.subject.code for e in context["home"]] == ["science"]
    assert context["in_class"][1].in_class_rtl and not context["in_class"][0].in_class_rtl


def test_urdu_written_in_an_english_subject_is_right_to_left():
    assert services.is_urdu("طلبہ کو ہدایت دی گئی ہے")
    assert not services.is_urdu("Read pages 69-70")


def test_teacher_cannot_write_another_section_or_a_past_day(org, class4, make_user, login_as):
    other = make_user("class_teacher", Scope.BRANCH, org["samanabad"])
    assert login_as(other).get(write_url(class4["section"])).status_code == 403
    client = login_as(class4["teacher"])
    assert client.get(write_url(class4["section"], WEDNESDAY - dt.timedelta(days=1))).status_code == 403
    assert client.get(write_url(class4["section"], WEDNESDAY + dt.timedelta(days=1))).status_code == 200  # plan ahead


def test_no_diary_on_sunday_or_saturday_for_class4(org, class4, make_user, login_as):
    principal = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    assert principal.get(write_url(class4["section"], dt.date(2026, 10, 11))).status_code == 403
    assert principal.get(write_url(class4["section"], dt.date(2026, 10, 10))).status_code == 403


def test_deadline_defaults_to_next_school_day(class4):
    friday = dt.date(2026, 10, 16)
    assert services.next_school_day(class4["section"].class_level, friday) == dt.date(2026, 10, 19)  # Monday
    class9 = ClassLevel.objects.get(code="class-9")
    assert services.next_school_day(class9, friday) == dt.date(2026, 10, 17)  # Saturday class


def test_pdf_and_whatsapp_image(org, class4, make_user, login_as):
    DiaryWeek.objects.create(starts_on=dt.date(2026, 10, 12), week_number=5, theme="Cleanliness", quote="Q")
    diary = services.save_diary(
        class4["section"],
        WEDNESDAY,
        class4["teacher"],
        {sid("urdu"): {"in_class": "سبق نمبر 10", "home_task": "یاد کریں", "deadline": dt.date(2026, 10, 15)}},
    )
    client = login_as(class4["teacher"])
    pdf = client.get(f"/diary/{diary.pk}/diary.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    png = client.get(f"/diary/{diary.pk}/diary.png")
    image = Image.open(io.BytesIO(png.content))
    assert image.width == 1080
    page = client.get(f"/diary/{diary.pk}/").content.decode()
    assert "Week: 05" in page and "Cleanliness" in page and "Image for WhatsApp" in page


def test_other_branch_cannot_open_a_diary(org, class4, make_user, login_as):
    diary = services.save_diary(
        class4["section"], WEDNESDAY, class4["teacher"], {sid("english"): {"in_class": "x", "home_task": ""}}
    )
    lahore = login_as(make_user("principal", Scope.BRANCH, org["lhr_franchise"]))
    assert lahore.get(f"/diary/{diary.pk}/").status_code == 404
    assert lahore.get(f"/diary/{diary.pk}/diary.pdf").status_code == 404


def test_branch_theme_overrides_network_theme(org, class4, make_user, login_as):
    DiaryWeek.objects.create(starts_on=dt.date(2026, 10, 12), theme="Network theme")
    principal = login_as(make_user("principal", Scope.BRANCH, org["samanabad"]))
    principal.post(
        "/diary/?date=2026-10-14", {"week_number": "5", "theme": "Branch theme", "theme_ur": "", "quote": ""}
    )
    assert services.week_info(org["samanabad"], WEDNESDAY).theme == "Branch theme"
    assert services.week_info(org["fsd_franchise"], WEDNESDAY).theme == "Network theme"


def test_seed_keeps_subjects_stable(seeded):
    call_command("seed_tasems", verbosity=0)
    assert Subject.objects.filter(is_rtl=True).count() == 3
