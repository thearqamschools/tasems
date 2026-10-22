"""Fills an EMPTY database with fictional demo data so the system can be tried out.

    DEMO_PASSWORD=... python manage.py seed_demo

Creates one session, a few classes with made-up students and parents, staff and their logins,
attendance, a published diary, a Mid-Term exam with marks, fee vouchers and payments, staff
attendance and admission inquiries. Every name, number and CNIC is invented.
Also adds a fictional network for head office to look at: demo regions and "Demo Branch"
campuses under both head offices, each with classes, registers, fees and inquiries
(added once, also to a database that already has the first demo data).
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
from apps.organisation.models import AcademicSession, Branch, HeadOffice, Region
from apps.people.models import Enrolment, Guardian, Student, StudentGuardian

PREFIX = "DEMO-"  # admission numbers of demos made before plain-number admission numbers
DEMO_MARK = "Demo data (fictional)"  # kept in Student.reference so demo students are always recognised
MOTHERS = ["Saima", "Nadia", "Rabia", "Amna", "Sadia", "Farah", "Huma", "Asma", "Bushra", "Shazia", "Uzma", "Sobia"]
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
    ("class-4", "Rose", "mixed"),
    ("class-6", "Rose", "boys"),
    ("pre-9", "Daisy", "boys"),
]
BIRTH_YEAR = {"play-group": 2022, "class-4": 2017, "class-6": 2015, "pre-9": 2012}
# Fictional branches for the head-office view: code, name, head office, region, ownership, royalty %,
# chance a child is absent, share of vouchers paid, register taken today
NETWORK_REGIONS = [
    ("demo-fsd-east", "Demo Region — Faisalabad East", "faisalabad"),
    ("demo-fsd-west", "Demo Region — Faisalabad West", "faisalabad"),
    ("demo-lhr-north", "Demo Region — Lahore North", "lahore"),
    ("demo-lhr-south", "Demo Region — Lahore South", "lahore"),
]
NETWORK_BRANCHES = [
    ("demo-fsd-1", "Demo Branch FSD-1", "faisalabad", "demo-fsd-east", "franchise", 8, 0.05, 0.85, True),
    ("demo-fsd-2", "Demo Branch FSD-2", "faisalabad", "demo-fsd-east", "franchise", 8, 0.12, 0.45, True),
    ("demo-fsd-3", "Demo Branch FSD-3", "faisalabad", "demo-fsd-west", "company", 0, 0.08, 0.70, False),
    ("demo-lhr-1", "Demo Branch LHR-1", "lahore", "demo-lhr-north", "franchise", 8, 0.06, 0.60, True),
    ("demo-lhr-2", "Demo Branch LHR-2", "lahore", "demo-lhr-north", "franchise", 8, 0.18, 0.30, True),
    ("demo-lhr-3", "Demo Branch LHR-3", "lahore", "demo-lhr-south", "franchise", 8, 0.09, 0.75, False),
]
NETWORK_CLASSES = [
    ("class-1", "Jasmine", "mixed", 2020),
    ("class-5", "Rose", "mixed", 2016),
    ("class-8", "Daisy", "boys", 2013),
]
USERS = [
    ("demo-principal", "Demo Principal", "principal"),
    ("demo-teacher", "Demo Class Teacher", "class_teacher"),
    ("demo-accountant", "Demo Accountant", "accountant"),
    ("demo-admissions", "Demo Admissions Officer", "admissions_officer"),
]


class Command(BaseCommand):
    help = "Fill an empty database with fictional demo data (never on a server with real data)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--without-network", action="store_true", help="Only the Samanabad demo (faster, for automated tests)."
        )

    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD", "")
        if len(password) < 10:
            raise CommandError("Set DEMO_PASSWORD (at least 10 characters) before running seed_demo.")
        call_command("seed_tasems", verbosity=0)
        if Student.objects.exclude(admission_no__startswith=PREFIX).exclude(reference=DEMO_MARK).exists():
            raise CommandError("This database has real students. Demo data is only for an empty database.")
        self.upgrade_old_demo()
        if User.objects.filter(username="demo-principal").exists():
            self.stdout.write("Demo data already present.")
        else:
            random.seed(2026)
            with transaction.atomic():
                self.build(password)
            self.stdout.write(
                self.style.SUCCESS("Demo data created. Sign in as demo-principal (password: DEMO_PASSWORD).")
            )
        self.demo_banks()
        if options["without_network"]:
            return
        if Branch.objects.filter(code__startswith="demo-").exists():
            self.stdout.write("Demo network already present.")
        else:
            random.seed(2027)
            with transaction.atomic():
                self.network(password)
            self.stdout.write(
                self.style.SUCCESS("Demo network created. Sign in as demo-network to see both head offices.")
            )
        self.royalty_and_expenses()
        self.demo_salaries()
        self.demo_stock()

    def demo_salaries(self):
        """Fictional salaries for the demo staff (added once), so the Payroll page has something to show."""
        from apps.hr.models import Employee
        from apps.payroll.models import EmployeePay

        for e in Employee.objects.filter(code__startswith=PREFIX, pay__isnull=True):
            EmployeePay.objects.create(branch=e.branch, employee=e, monthly_salary=Decimal(25000 + 5000 * (e.pk % 3)))

    def demo_stock(self):
        """A few fictional shop items with stock for the demo campus (added once), so Shop & stock has something
        to show. Names and prices are made up for the demo."""
        from apps.inventory import services as stock
        from apps.inventory.models import Item

        branch = Branch.objects.get(code="fsd-samanabad")
        user = User.objects.filter(username="demo-principal").first()
        if user is None or Item.objects.filter(branch=branch).exists():
            return
        today = timezone.localdate()
        level = ClassLevel.objects.filter(code="class-4").first()
        for name, category, cls, code, price, reorder, qty in [
            ("Demo English reader", "books", level, "DEMO-1001", 650, 10, 40),
            ("Demo Mathematics book", "books", level, "DEMO-1002", 720, 10, 8),
            ("Demo Urdu book", "books", level, "DEMO-1003", 540, 10, 0),
            ("Exercise copy (single line)", "stationery", None, "DEMO-2001", 80, 50, 300),
            ("School tie", "uniform", None, "DEMO-3001", 250, 20, 35),
        ]:
            item = Item.objects.create(
                branch=branch, name=name, category=category, class_level=cls, barcode=code,
                sale_price=Decimal(price), reorder_level=reorder,
            )  # fmt: skip
            if qty:
                stock.move(item, "received", qty, today, user, note="Demo opening stock")

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
                        sibling.guardian_links.get(relationship="father").guardian.phone,
                        sibling.father_cnic,
                    )
                s = Student.objects.create(
                    branch=branch,
                    admission_no=str(4000 + n),
                    reference=DEMO_MARK,
                    first_name=first,
                    last_name=father.split()[-1],
                    gender=gender,
                    date_of_birth=dt.date(BIRTH_YEAR[code], 1 + i, 10),
                    admission_date=dt.date(start.year - (i % 3), 4, 1),
                    father_name=father,
                    father_cnic=cnic,
                )
                g = Guardian.objects.filter(branch=branch, phone=phone).first() or Guardian.objects.create(
                    branch=branch, full_name=father, phone=phone, occupation="Business"
                )
                StudentGuardian.objects.create(student=s, guardian=g, relationship="father", is_primary_contact=True)
                self.mother(s, branch, n, father)
                Enrolment.objects.create(branch=branch, student=s, session=session, section=sec, roll_no=i + 1)
                students.append(s)

        self.attendance(sections["class-4"], users["class_teacher"], today)
        self.diary(sections["class-4"], users["class_teacher"], today)
        self.exam(session, sections["class-4"], users["class_teacher"])
        self.fees(branch, session, users["accountant"], today)
        self.staff(branch, users, today)
        self.admissions(branch, users["admissions_officer"])
        self.parent(students[0], branch, users["principal"], password)

    def network(self, password):
        """Fictional regions and branches so the head-office screens have a network to show."""
        from apps.attendance.services import is_school_day, roster, save_register
        from apps.fees import services as fees
        from apps.fees.models import BankAccount, BranchFeeSettings, FeeRate

        today = timezone.localdate()
        session = AcademicSession.objects.get(is_current=True)
        month = today.replace(day=1)
        samanabad = Branch.objects.get(code="fsd-samanabad")
        offices = {h.code: h for h in HeadOffice.objects.all()}
        regions = {
            code: Region.objects.create(code=code, name=name, head_office=offices[office])
            for code, name, office in NETWORK_REGIONS
        }
        network = User.objects.create_user(
            username="demo-network", password=password, first_name="Demo", last_name="Network Admin", is_staff=True
        )
        RoleAssignment.objects.create(user=network, role=Role.objects.get(code="network_admin"), scope=Scope.NETWORK)
        principal_role = Role.objects.get(code="principal")
        n = 0
        for code, name, office, region, ownership, royalty, absent, paid, today_done in NETWORK_BRANCHES:
            branch = Branch.objects.create(
                code=code,
                name=f"{name} (DEMO)",
                head_office=offices[office],
                region=regions[region],
                ownership=ownership,
                royalty_percent=royalty,
                city=offices[office].city,
            )
            principal = User.objects.create_user(
                username=f"demo-principal-{code[5:]}",
                password=password,
                first_name="Demo",
                last_name=f"Principal {name[-5:]}",
            )
            RoleAssignment.objects.create(user=principal, role=principal_role, scope=Scope.BRANCH, branch=branch)
            for rate in FeeRate.objects.filter(branch=samanabad):
                rate.pk, rate.branch = None, branch
                rate.save()
            fs = BranchFeeSettings.for_branch(branch)
            fs.bank_name, fs.account_title, fs.account_number = "Demo Bank", f"{name} (DEMO)", "0000-0000000000"
            fs.save()
            for order, bank_name in enumerate(["Askari Bank", "Bank Alfalah", "JazzCash"], start=1):
                BankAccount.objects.create(
                    branch=branch, name=bank_name, account_title=f"{name} (DEMO)", sort_order=order
                )

            for c, (level_code, section_name, group, born) in enumerate(NETWORK_CLASSES):
                section = Section.objects.create(
                    branch=branch,
                    session=session,
                    class_level=ClassLevel.objects.get(code=level_code),
                    name=section_name,
                    gender_group=group,
                )
                for i in range(10):
                    n += 1
                    gender = "male" if group == "boys" or i % 2 == 0 else "female"
                    father = f"{random.choice(FATHERS)} {random.choice(SURNAMES)}"
                    s = Student.objects.create(
                        branch=branch,
                        admission_no=str(1001 + 10 * c + i),
                        reference=DEMO_MARK,
                        first_name=random.choice(BOYS if gender == "male" else GIRLS),
                        last_name=father.split()[-1],
                        gender=gender,
                        date_of_birth=dt.date(born, 1 + i, 12),
                        admission_date=dt.date(session.starts_on.year - (i % 3), 4, 1),
                        father_name=father,
                        father_cnic=f"35200{2000000 + n:07d}1",
                    )
                    g = Guardian.objects.create(branch=branch, full_name=father, phone=f"0301{7000000 + n:07d}")
                    StudentGuardian.objects.create(
                        student=s, guardian=g, relationship="father", is_primary_contact=True
                    )
                    self.mother(s, branch, 500 + n, father)
                    Enrolment.objects.create(branch=branch, student=s, session=session, section=section, roll_no=i + 1)

                day, done = today + dt.timedelta(days=1 if today_done else 0), 0
                while done < 14:
                    day -= dt.timedelta(days=1)
                    if not is_school_day(section.class_level, day):
                        continue
                    marks = {
                        e.student_id: ("absent" if random.random() < absent else "present", "") for e in roster(section)
                    }
                    save_register(section, day, marks, principal)
                    done += 1

            result = fees.generate_vouchers(
                branch, session, month, month, fees.default_due_date(branch, month), principal
            )
            banks = list(BankAccount.objects.filter(branch=branch)) or [None]
            for v in result["created"]:
                if random.random() < paid:
                    paid_on = month + dt.timedelta(days=random.randint(0, max(0, (today - month).days)))
                    bank = random.choice(banks) if random.random() < 0.4 else None
                    fees.record_payment(
                        v.student, v.payable, paid_on, "bank" if bank else "counter", principal, voucher=v, bank=bank
                    )

    def royalty_and_expenses(self):
        """Some royalty paid to head office and some branch expenses (added once), so those pages have data."""
        from apps.accounting.models import Expense, ExpenseHead
        from apps.fees.models import RoyaltyPayment
        from apps.fees.reports import royalty_ledger

        if RoyaltyPayment.objects.exists() or Expense.objects.exists():
            return
        recorder = User.objects.filter(username="demo-network").first()
        principal = User.objects.filter(username="demo-principal").first()
        if recorder is None or principal is None:
            return
        today = timezone.localdate()
        with transaction.atomic():
            # Some franchises paid their royalty in full, some in part, one not at all.
            for code, share in [("demo-fsd-1", 1), ("demo-fsd-2", 0.5), ("demo-lhr-1", 1), ("demo-lhr-3", 0.25)]:
                branch = Branch.objects.get(code=code)
                row = royalty_ledger(branch, today, months=1)["rows"][-1]
                amount = (row["due"] * Decimal(str(share))).quantize(Decimal("1"))
                if amount > 0:
                    RoyaltyPayment.objects.create(
                        branch=branch,
                        month=row["month"],
                        amount=amount,
                        paid_on=today,
                        reference=f"DEMO-SLIP-{branch.id}",
                        received_by=recorder,
                    )
            samanabad = Branch.objects.get(code="fsd-samanabad")
            for code, amount, text, paid_to in [
                ("utilities", 18500, "Electricity bill", "Demo Electricity Company"),
                ("stationery", 3200, "Registers and chalk", "Demo Stationers"),
                ("repairs", 6000, "Fan repair, Class 4", "Demo Electrician"),
                ("cleaning", 2500, "Cleaning material", "Demo Store"),
            ]:
                Expense.objects.create(
                    branch=samanabad,
                    date=today,
                    head=ExpenseHead.objects.get(code=code),
                    amount=amount,
                    description=text,
                    paid_to=paid_to,
                    recorded_by=principal,
                )

    def demo_banks(self):
        """Every branch with demo students gets three fictional banks to choose when a fee comes by bank."""
        from apps.fees.models import BankAccount

        branch_ids = Student.objects.filter(reference=DEMO_MARK).values_list("branch_id", flat=True).distinct()
        for branch in Branch.objects.filter(id__in=branch_ids):
            for order, name in enumerate(["Askari Bank", "Bank Alfalah", "JazzCash"], start=1):
                BankAccount.objects.get_or_create(
                    branch=branch,
                    name=name,
                    defaults={
                        "account_title": f"{branch.name} (DEMO)",
                        "account_number": "0000-0000000000",
                        "sort_order": order,
                    },
                )

    def mother(self, student, branch, n, father):
        mother = Guardian.objects.filter(branch=branch, phone=f"0302{7000000 + n:07d}").first()
        if mother is None:
            mother = Guardian.objects.create(
                branch=branch,
                full_name=f"{random.choice(MOTHERS)} {father.split()[-1]}",
                phone=f"0302{7000000 + n:07d}",
                occupation=random.choice(["Housewife", "Teacher", "Doctor"]),
            )
        StudentGuardian.objects.create(student=student, guardian=mother, relationship="mother")

    def upgrade_old_demo(self):
        """Demos made before October 2026 used admission numbers like DEMO-001 and sections like "A":
        give their students plain numbers and the sections the usual names. Only demo students are touched."""
        old = Student.objects.filter(admission_no__startswith=PREFIX)
        if not old.exists():
            return
        with transaction.atomic():
            for branch_id in old.values_list("branch_id", flat=True).distinct():
                number = 4001 if Branch.objects.get(pk=branch_id).code == "fsd-samanabad" else 1001
                for student in old.filter(branch_id=branch_id).order_by("pk"):
                    student.admission_no, student.reference = str(number), DEMO_MARK
                    student.save(update_fields=["admission_no", "reference"])
                    number += 1
            renames = {"A": "Rose", "Boys": "Daisy"}
            demo_sections = Section.objects.filter(name__in=renames, enrolments__student__reference=DEMO_MARK)
            for section in demo_sections.distinct():
                if section.class_level.code == "class-1":
                    section.name = "Jasmine"
                else:
                    section.name = renames[section.name]
                section.save(update_fields=["name"])
        self.stdout.write("Older demo updated: plain admission numbers and usual section names.")

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
            ("Demo Qari Sahib", "Qari", "hifz", None),
            ("Demo Accountant", "Accountant", "admin", users["accountant"]),
            ("Demo Guard", "Guard", "support", None),
            ("Demo Teacher Two", "Junior Teacher", "teaching", None),
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

        phone = student.guardian_links.get(relationship="father").guardian.phone
        code = parents.issue_code(phone, branch, issuer)
        parents.redeem(parents.check_code(phone, code), password)
        self.stdout.write(f"Parent demo login: mobile {phone}")
