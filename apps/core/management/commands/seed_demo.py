"""Fills an EMPTY database with fictional demo data so the system can be tried out.

    DEMO_PASSWORD=... python manage.py seed_demo

Creates one session, a few classes with made-up students and parents, staff and their logins,
attendance, a published diary, a Mid-Term exam with marks, fee vouchers and payments, staff
attendance and admission inquiries. Every name, number and CNIC is invented.
Refuses to run if the database already has students that are not demo students.
"""

import datetime as dt
import os
import random
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.academics.models import ClassLevel, Section, Subject
from apps.accounts.models import Role, RoleAssignment, Scope, User
from apps.organisation.models import AcademicSession, Branch, HeadOffice
from apps.people.models import Enrolment, Guardian, Student, StudentGuardian

PREFIX = "DEMO-"
BOYS = ["Ahmad", "Ali", "Hamza", "Usman", "Bilal", "Hassan", "Zain", "Saad", "Talha", "Fahad", "Umar", "Hadi"]
GIRLS = ["Ayesha", "Fatima", "Hira", "Maryam", "Zainab", "Aiman", "Sana", "Iqra", "Noor", "Areeba", "Laiba", "Mahnoor"]
FATHERS = [
    "Imran",
    "Tariq",
    "Naveed",
    "Shahid",
    "Kashif",
    "Asif",
    "Rizwan",
    "Sajid",
    "Waqas",
    "Javed",
    "Farooq",
    "Nadeem",
]
SURNAMES = ["Khan", "Ahmad", "Malik", "Butt", "Sheikh", "Chaudhry", "Raza", "Iqbal"]
CLASSES = [
    ("play-group", "Tulip", "mixed"),
    ("class-4", "A", "mixed"),
    ("class-6", "Rose", "boys"),
    ("pre-9", "Daisy", "boys"),
]
BIRTH_YEAR = {"play-group": 2022, "class-4": 2017, "class-6": 2015, "pre-9": 2012}
USERS = [
    ("demo-principal", "Demo Principal", "principal"),
    ("demo-teacher", "Demo Class Teacher", "class_teacher"),
    ("demo-accountant", "Demo Accountant", "accountant"),
    ("demo-admissions", "Demo Admissions Officer", "admissions_officer"),
]


class Command(BaseCommand):
    help = "Fill an empty database with fictional demo data (never on a server with real data)."

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD", "")
        if len(password) < 10:
            raise CommandError("Set DEMO_PASSWORD (at least 10 characters) before running seed_demo.")
        call_command("seed_tasems", verbosity=0)
        if Student.objects.exclude(admission_no__startswith=PREFIX).exists():
            raise CommandError("This database has real students. Demo data is only for an empty database.")
        if User.objects.filter(username="demo-principal").exists():
            self.stdout.write("Demo data already present; nothing to do.")
            return
        random.seed(2026)
        with transaction.atomic():
            self.build(password)
        self.stdout.write(self.style.SUCCESS("Demo data created. Sign in as demo-principal (password: DEMO_PASSWORD)."))

    # ------------------------------------------------------------------------------------------
    def build(self, password):
        today = timezone.localdate()
        branch = Branch.objects.get(code="fsd-samanabad")
        start = dt.date(today.year if today.month >= 4 else today.year - 1, 4, 1)
        session, _ = AcademicSession.objects.get_or_create(
            name=f"{start.year}-{str(start.year + 1)[2:]}",
            defaults={"starts_on": start, "ends_on": dt.date(start.year + 1, 3, 31), "is_current": True},
        )
        AcademicSession.objects.exclude(pk=session.pk).update(is_current=False)
        session.is_current = True
        session.save()

        users = {}
        for username, name, role in USERS:
            first, last = name.split(" ", 1)
            u = User.objects.create_user(username=username, password=password, first_name=first, last_name=last)
            RoleAssignment.objects.create(user=u, role=Role.objects.get(code=role), scope=Scope.BRANCH, branch=branch)
            users[role] = u
        ho = User.objects.create_user(
            username="demo-headoffice", password=password, first_name="Demo", last_name="Head Office", is_staff=True
        )
        RoleAssignment.objects.create(
            user=ho,
            role=Role.objects.get(code="head_office_admin"),
            scope=Scope.HEAD_OFFICE,
            head_office=HeadOffice.objects.get(code="faisalabad"),
        )

        # Classes and students (some brothers/sisters share a father's CNIC)
        sections, students, n = {}, [], 0
        for code, name, group in CLASSES:
            level = ClassLevel.objects.get(code=code)
            sec = Section.objects.create(
                branch=branch,
                session=session,
                class_level=level,
                name=name,
                gender_group=group,
                class_teacher=users["class_teacher"] if code == "class-4" else None,
            )
            sections[code] = sec
            for i in range(8):
                n += 1
                gender = "male" if group == "boys" or i % 2 == 0 else "female"
                first = random.choice(BOYS if gender == "male" else GIRLS)
                father = f"{random.choice(FATHERS)} {random.choice(SURNAMES)}"
                phone = f"0300{7000000 + n:07d}"
                cnic = f"33100{1000000 + n:07d}1"
                if code == "class-4" and i == 1:  # a sister of the Play Group child of the same family
                    sibling = students[0]
                    father, phone, cnic = (
                        sibling.father_name,
                        sibling.guardian_links.get().guardian.phone,
                        sibling.father_cnic,
                    )
                s = Student.objects.create(
                    branch=branch,
                    admission_no=f"{PREFIX}{n:03d}",
                    first_name=first,
                    last_name=father.split()[-1],
                    gender=gender,
                    date_of_birth=dt.date(BIRTH_YEAR[code], 1 + i, 10),
                    admission_date=dt.date(start.year - (i % 3), 4, 1),
                    father_name=father,
                    father_cnic=cnic,
                )
                g = Guardian.objects.filter(branch=branch, phone=phone).first() or Guardian.objects.create(
                    branch=branch, full_name=father, phone=phone
                )
                StudentGuardian.objects.create(student=s, guardian=g, relationship="father", is_primary_contact=True)
                Enrolment.objects.create(branch=branch, student=s, session=session, section=sec, roll_no=i + 1)
                students.append(s)

        self.attendance(sections["class-4"], users["class_teacher"], today)
        self.diary(sections["class-4"], users["class_teacher"], today)
        self.exam(session, sections["class-4"], users["class_teacher"])
        self.fees(branch, session, users["accountant"], today)
        self.staff(branch, users, today)
        self.admissions(branch, users["admissions_officer"])
        self.parent(students[0], branch, users["principal"], password)

    def attendance(self, section, teacher, today):
        from apps.attendance.services import is_school_day, roster, save_register

        day, done = today, 0
        while done < 5:
            day -= dt.timedelta(days=1)
            if not is_school_day(section.class_level, day):
                continue
            marks = {e.student_id: ("absent" if random.random() < 0.1 else "present", "") for e in roster(section)}
            save_register(section, day, marks, teacher)
            done += 1

    def diary(self, section, teacher, today):
        from apps.diary.services import save_diary, subjects_for

        work = {
            "English": ("Read Unit 5 and learned new words.", "Write 5 sentences with the new words."),
            "Mathematics": ("Exercise 6.4: changing units of length.", "Solve questions 1–5 of Exercise 6.4."),
            "Science": ("Parts of a plant and what each part does.", "Draw and label a plant."),
            "Urdu": ("سبق نمبر 7 پڑھا اور مشکل الفاظ کے معنی یاد کیے۔", "سبق نمبر 7 کے سوالات کے جوابات لکھیں۔"),
            "Islamiyat": ("نماز کی اہمیت پر گفتگو کی گئی۔", ""),
        }
        entries = {}
        for subject, _order in subjects_for(section):
            if subject.name in work:
                in_class, home = work[subject.name]
                entries[subject.id] = {
                    "in_class": in_class,
                    "home_task": home,
                    "deadline": today + dt.timedelta(days=1),
                }
        save_diary(section, today, teacher, entries, publish=True)

    def exam(self, session, section, teacher):
        from apps.exams import services as exams
        from apps.exams.models import Exam, Paper

        mid = Exam.objects.create(
            session=session, kind="mid", name=f"Mid-Term Examination {session.name}", is_published=True
        )
        for code in ["english", "mathematics", "science", "urdu", "islamiyat"]:
            paper = Paper.objects.create(
                exam=mid, class_level=section.class_level, subject=Subject.objects.get(code=code), total_marks=50
            )
            marks = {e.student_id: ("present", Decimal(random.randint(22, 49))) for e in exams.roster(section)}
            exams.save_marks(paper, section, marks, teacher)

    def fees(self, branch, session, accountant, today):
        from apps.fees import services as fees
        from apps.fees.models import BranchFeeSettings

        fs = BranchFeeSettings.for_branch(branch)
        fs.bank_name, fs.bank_branch, fs.account_title, fs.account_number = (
            "Demo Bank",
            "Samanabad, Faisalabad",
            "The Arqam Schools (DEMO)",
            "0000-0000000000",
        )
        fs.save()
        month = today.replace(day=1)
        result = fees.generate_vouchers(branch, session, month, month, fees.default_due_date(branch, month), accountant)
        for v in result["created"][::3]:
            fees.record_payment(v.student, v.payable, today, "counter", accountant, voucher=v)

    def staff(self, branch, users, today):
        from apps.hr import services as hr
        from apps.hr.models import Employee, Punch

        people = [
            ("Demo Senior Teacher", "Senior Teacher", "teaching", users["class_teacher"]),
            ("Demo Qari Sahib", "Hifz Teacher", "hifz", None),
            ("Demo Accountant", "Accountant", "admin", users["accountant"]),
            ("Demo Guard", "Guard", "support", None),
            ("Demo Teacher Two", "Teacher", "teaching", None),
        ]
        for i, (name, designation, kind, user) in enumerate(people, start=1):
            e = Employee.objects.create(
                branch=branch,
                code=f"{PREFIX}E{i}",
                machine_id=str(100 + i),
                full_name=name,
                gender="male" if i % 2 else "female",
                designation=designation,
                staff_type=kind,
                joined_on=dt.date(2024, 4, 1),
                user=user,
            )
            for back in range(1, 8):
                day = today - dt.timedelta(days=back)
                if day.weekday() == 6 or (i == 4 and back == 2):
                    continue
                minute = random.choice([35, 40, 44, 50, 58, 5])
                hour = 7 if minute >= 30 else 8
                for h, m in ((hour, minute), (13, 50)):
                    Punch.objects.create(
                        branch=branch,
                        employee=e,
                        at=timezone.make_aware(dt.datetime.combine(day, dt.time(h, m))),
                        created_by=users["principal"],
                    )
        hr.rebuild_days(branch, today - dt.timedelta(days=7), today)

    def admissions(self, branch, officer):
        from apps.admissions import services as adm
        from apps.admissions.models import Inquiry

        rows = [
            ("Demo Child One", "Demo Parent One", "03117000001", "play-group", "facebook"),
            ("Demo Child Two", "Demo Parent Two", "03117000002", "nursery", "walk_in"),
            ("Demo Child Three", "Demo Parent Three", "03117000003", "class-6", "referral"),
            ("Demo Child Four", "Demo Parent Four", "03117000004", "class-1", "phone"),
        ]
        for child, parent, phone, level, source in rows:
            inquiry = Inquiry(
                branch=branch,
                child_name=child,
                gender="male",
                class_level=ClassLevel.objects.get(code=level),
                parent_name=parent,
                phone=phone,
                source=source,
                next_follow_up=timezone.localdate(),
            )
            adm.create(inquiry, officer)

    def parent(self, student, branch, issuer, password):
        from apps.parents import services as parents

        phone = student.guardian_links.get().guardian.phone
        code = parents.issue_code(phone, branch, issuer)
        parents.redeem(parents.check_code(phone, code), password)
        self.stdout.write(f"Parent demo login: mobile {phone}")
