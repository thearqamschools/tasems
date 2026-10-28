"""Loads the starting data TASEMS needs. Safe to run more than once.

Only facts confirmed by The Arqam Schools are seeded. Anything not yet
confirmed (Lahore address, regions, subjects, session dates) is left for head
office to enter, so nothing is invented.
"""

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import models, transaction

from apps.academics.models import ClassLevel, CurriculumSubject, Subject
from apps.accounts.models import Role, Scope
from apps.exams.models import GradingComponent, GradingScheme
from apps.fees.models import BranchFeeSettings, FeeHead, FeeRate, PaymentChannel, VoucherCounter
from apps.hr.models import HRSettings, LeaveType
from apps.organisation.models import Branch, HeadOffice

VIEW_PEOPLE = ["people.view_student", "people.view_guardian", "people.view_enrolment", "people.view_studentguardian"]
EDIT_PEOPLE = [
    "people.add_student",
    "people.change_student",
    "people.add_guardian",
    "people.change_guardian",
    "people.add_enrolment",
    "people.change_enrolment",
    "people.add_studentguardian",
    "people.change_studentguardian",
    "people.delete_studentguardian",
]
VIEW_ACADEMICS = [
    "academics.view_section",
    "academics.view_classlevel",
    "academics.view_subject",
    "academics.view_curriculumsubject",
    "organisation.view_branch",
    "organisation.view_campus",
    "organisation.view_academicsession",
]
EDIT_SECTIONS = [
    "academics.add_section",
    "academics.change_section",
    "organisation.add_campus",
    "organisation.change_campus",
]
VIEW_STUDENTS_ONLY = ["people.view_student", "people.view_enrolment"]
NETWORK_SETUP = [
    "organisation.add_branch",
    "organisation.change_branch",
    "organisation.view_headoffice",
    "organisation.view_region",
    "organisation.add_region",
    "organisation.change_region",
    "organisation.add_academicsession",
    "organisation.change_academicsession",
    "academics.add_classlevel",
    "academics.change_classlevel",
    "academics.add_subject",
    "academics.change_subject",
    "academics.add_curriculumsubject",
    "academics.change_curriculumsubject",
    "accounts.view_user",
    "accounts.add_user",
    "accounts.change_user",
    "accounts.view_roleassignment",
    "accounts.add_roleassignment",
    "accounts.change_roleassignment",
    "core.view_auditevent",
]

N, H, R, B = Scope.NETWORK, Scope.HEAD_OFFICE, Scope.REGION, Scope.BRANCH

# code, name, name_ur, scopes, permissions, requires_mfa
ROLES = [
    (
        "network_admin",
        "Network Administrator",
        "نیٹ ورک ایڈمنسٹریٹر",
        [N],
        VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS + NETWORK_SETUP,
        True,
    ),
    (
        "head_office_admin",
        "Head Office Administrator",
        "ہیڈ آفس ایڈمنسٹریٹر",
        [H],
        VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS + NETWORK_SETUP,
        True,
    ),
    ("regional_director", "Regional Director", "ریجنل ڈائریکٹر", [R], VIEW_PEOPLE + VIEW_ACADEMICS, True),
    (
        "branch_owner",
        "Branch Owner / Franchisee",
        "برانچ مالک",
        [B],
        VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS + ["accounts.view_user"],
        True,
    ),
    (
        "principal",
        "Principal",
        "پرنسپل",
        [B],
        VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS + ["accounts.view_user"],
        True,
    ),
    (
        "academic_coordinator",
        "Academic Coordinator",
        "اکیڈمک کوآرڈینیٹر",
        [B, R],
        VIEW_PEOPLE + VIEW_ACADEMICS + EDIT_SECTIONS,
        False,
    ),
    # Two-step sign-in since the Admin also receives fees (project lead, 23 Oct 2026).
    ("admissions_officer", "Admissions Officer", "داخلہ آفیسر", [B], VIEW_PEOPLE + EDIT_PEOPLE + VIEW_ACADEMICS, True),
    ("accountant", "Accountant", "اکاؤنٹنٹ", [B], VIEW_PEOPLE + VIEW_ACADEMICS, True),
    ("class_teacher", "Class Teacher", "کلاس ٹیچر", [B], VIEW_PEOPLE + VIEW_ACADEMICS, False),
    ("subject_teacher", "Subject Teacher", "سبجیکٹ ٹیچر", [B], VIEW_STUDENTS_ONLY + VIEW_ACADEMICS, False),
    ("hifz_teacher", "Hifz Teacher", "حفظ ٹیچر", [B], VIEW_STUDENTS_ONLY + VIEW_ACADEMICS, False),
]

# Early Years confirmed by the project lead on 16 Oct 2026: Play Group, Nursery, Prep.
CLASS_LEVELS = [
    ("play-group", "Play Group", "پلے گروپ", "early_years"),
    ("nursery", "Nursery", "نرسری", "early_years"),
    ("prep", "Prep", "پریپ", "early_years"),
]
# Confirmed by the project lead on 16 Oct 2026. Boys and girls are separated from Middle School (Class 6) onwards.
# Names in words without "Class" (project lead, 28 Oct 2026): One, Two … Pre-Nine, Nine, Ten. Codes stay class-1 …
WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten"}
CLASS_LEVELS += [(f"class-{n}", WORDS[n], f"جماعت {n}", "primary") for n in range(1, 6)]
CLASS_LEVELS += [(f"class-{n}", WORDS[n], f"جماعت {n}", "middle") for n in (6, 7)]
CLASS_LEVELS += [
    ("class-8", "Eight", "جماعت 8", "high"),
    ("pre-9", "Pre-Nine", "پری نہم", "high"),
    ("class-9", "Nine", "جماعت 9", "high"),
    ("class-10", "Ten", "جماعت 10", "high"),
]
CLASS_LEVELS += [("hifz", "Hifz-e-Quran", "حفظ القرآن", "hifz")]


# Confirmed 16 Oct 2026: on Saturdays only Hifz, Pre-9, Class 9 and Class 10 attend. Sunday is off for all.
SATURDAY_CLASSES = {"hifz", "pre-9", "class-9", "class-10"}

# Daily attendance (Milestone 1c)
ATT_VIEW = ["attendance.view_attendancerecord", "attendance.view_sectionattendance"]
ATT_MARK = ATT_VIEW + ["attendance.add_attendancerecord"]
ATT_MANAGE = ATT_MARK + ["attendance.change_attendancerecord"]
# Daily Diary (Milestone 1d)
DIARY_VIEW = ["diary.view_diary", "diary.view_diaryweek"]
DIARY_WRITE = DIARY_VIEW + ["diary.add_diary"]
DIARY_MANAGE = DIARY_WRITE + ["diary.change_diary", "diary.add_diaryweek", "diary.change_diaryweek"]
DIARY_DESIGN = DIARY_VIEW + [
    "diary.add_diaryweek",
    "diary.change_diaryweek",
    "diary.view_diarylayout",
    "diary.add_diarylayout",
    "diary.change_diarylayout",
]

# Examinations and results (Phase 2)
EXAM_VIEW = [
    "exams.view_exam",
    "exams.view_paper",
    "exams.view_mark",
    "exams.view_rating",
    "exams.view_resultremark",
    "exams.view_gradingscheme",
    "exams.view_gradingcomponent",
]
EXAM_ENTER = EXAM_VIEW + ["exams.add_mark", "exams.add_rating", "exams.add_resultremark", "exams.change_resultremark"]
EXAM_MANAGE = EXAM_ENTER + ["exams.change_mark", "exams.change_rating"]
EXAM_SETUP = EXAM_VIEW + [
    "exams.add_exam",
    "exams.change_exam",
    "exams.add_paper",
    "exams.change_paper",
    "exams.delete_paper",
    "exams.add_gradingscheme",
    "exams.change_gradingscheme",
    "exams.add_gradingcomponent",
    "exams.change_gradingcomponent",
]

# Fees (Phase 2b)
FEE_VIEW = [
    "fees.view_feehead",
    "fees.view_feerate",
    "fees.view_voucher",
    "fees.view_charge",
    "fees.view_payment",
    "fees.view_concession",
    "fees.view_branchfeesettings",
    "fees.view_defaulters",
]
DEFAULTERS = ["fees.view_defaulters"]  # principals and coordinators: who owes, nothing else about fees
FEE_COLLECT = FEE_VIEW + ["fees.add_payment", "fees.add_voucher", "fees.add_charge", "fees.add_concession"]
FEE_APPROVE = ["fees.approve_concession"]
FEE_MANAGE = (
    FEE_COLLECT
    + FEE_APPROVE
    + [
        "fees.change_payment",
        "fees.change_charge",
        "fees.change_voucher",
        "fees.add_feerate",
        "fees.change_feerate",
        "fees.add_branchfeesettings",
        "fees.change_branchfeesettings",
    ]
)
FEE_SETUP = (
    FEE_VIEW
    + FEE_APPROVE
    + [
        "fees.view_royalty",
        "fees.add_feehead",
        "fees.change_feehead",
        "fees.add_feerate",
        "fees.change_feerate",
        "fees.add_branchfeesettings",
        "fees.change_branchfeesettings",
        "fees.view_paymentchannel",
        "fees.add_paymentchannel",
        "fees.change_paymentchannel",
        "fees.view_vouchercounter",
        "fees.change_vouchercounter",
    ]
)

# Royalty paid to head office (19 Oct 2026): head office records it, branches see their own.
ROYALTY_VIEW = ["fees.view_royalty", "fees.view_royaltypayment"]
ROYALTY_RECORD = ROYALTY_VIEW + ["fees.add_royaltypayment"]

# Expenses (19 Oct 2026): the branch records them, head office sees them.
# Other income, opening balances, cash/bank book and profit & loss (M9) go with the same roles as expenses.
EXPENSE_VIEW = [
    "accounting.view_expense",
    "accounting.view_expensehead",
    "accounting.view_income",
    "accounting.view_incomehead",
    "accounting.view_openingbalance",
]
EXPENSE_WORK = EXPENSE_VIEW + ["accounting.add_expense", "accounting.add_income"]
EXPENSE_MANAGE = EXPENSE_WORK + [
    "accounting.change_expense",
    "accounting.change_income",
    "accounting.add_openingbalance",
    "accounting.change_openingbalance",
]

# Staff (HR) — Phase 3a
HR_VIEW = [
    "hr.view_employee",
    "hr.view_staffday",
    "hr.view_punch",
    "hr.view_leaverequest",
    "hr.view_leavetype",
    "hr.view_holiday",
    "hr.view_hrsettings",
]
HR_MANAGE = HR_VIEW + [
    "hr.add_employee",
    "hr.change_employee",
    "hr.add_punch",
    "hr.change_staffday",
    "hr.add_leaverequest",
    "hr.change_leaverequest",
    "hr.approve_leaverequest",
    "hr.add_holiday",
    "hr.change_holiday",
    "hr.change_hrsettings",
    "hr.add_hrsettings",
]
HR_SETUP = HR_MANAGE + ["hr.add_leavetype", "hr.change_leavetype"]

# Admissions (Phase 3c)
ADM_VIEW = ["admissions.view_inquiry", "admissions.view_followup"]
ADM_WORK = ADM_VIEW + ["admissions.add_inquiry", "admissions.change_inquiry", "admissions.add_followup"]

# Notices and messages to parents (M8): principals post for their branch; head office and network admins also
# post for every branch they look after and keep the message templates.
NOTICE_POST = ["notices.view_notice", "notices.add_notice", "notices.change_notice", "notices.send_messages"]
TEMPLATE_EDIT = ["notices.view_messagetemplate", "notices.add_messagetemplate", "notices.change_messagetemplate"]

# Payroll (M10): accountants and directors set salaries and finalise the month; principals and supervisors see it.
PAYROLL_VIEW = ["payroll.view_employeepay", "payroll.view_payrollrun", "payroll.view_payslip"]
PAYROLL_MANAGE = PAYROLL_VIEW + [
    "payroll.add_employeepay",
    "payroll.change_employeepay",
    "payroll.add_payrollrun",
    "payroll.change_payrollrun",
    "payroll.finalise_payroll",
]

# Shop & stock (M11): accountants and directors keep the item list, sell, record stock and cancel sales;
# supervisors see stock and sales.
INVENTORY_VIEW = ["inventory.view_item", "inventory.view_stockmove", "inventory.view_sale", "inventory.view_saleline"]
INVENTORY_WORK = INVENTORY_VIEW + ["inventory.add_sale", "inventory.add_saleline", "inventory.add_stockmove"]
INVENTORY_MANAGE = INVENTORY_WORK + ["inventory.add_item", "inventory.change_item", "inventory.change_sale"]

# Hifz (M12): Hifz teachers (Qari, senior Qari) record their own sections' daily lessons and take para tests;
# directors, principals and coordinators also correct any section and cancel a test; supervisors see progress.
HIFZ_VIEW = ["hifz.view_hifzlesson", "hifz.view_paratest"]
HIFZ_WRITE = HIFZ_VIEW + ["hifz.add_hifzlesson", "hifz.add_paratest"]
HIFZ_MANAGE = HIFZ_WRITE + ["hifz.change_hifzlesson", "hifz.change_paratest"]

# Who does what in a branch (project lead, 23 Oct 2026):
# - Director (branch owner): everything in the branch, including receiving fees.
# - Principal: students, attendance, diary, marks, staff, Hifz, notices, needs attention; sees payroll and the
#   fee defaulters list only. No fee receiving, fee figures, expenses or shop.
# - Vice Principal / Coordinator: attendance, diary, marks, sections, Hifz, defaulters list. No staff, payroll, shop.
# - Accountant: vouchers, receiving fees, expenses and other income, shop & stock, payroll (full).
# - Admin (admissions officer): students, inquiries, admission vouchers, and receiving fees.
# Only the Director, the Accountant and the Admin receive fees.
# Deleting records made by mistake (23 Oct 2026): the master login (superuser), head office / network
# administrators everywhere they look after, and the Director in the branch.
DELETE_RECORDS = ["core.delete_records"]
BRANCH_EVERYTHING = (
    DELETE_RECORDS
    + PAYROLL_MANAGE
    + INVENTORY_MANAGE
    + HIFZ_MANAGE
    + NOTICE_POST
    + ATT_MANAGE
    + DIARY_MANAGE
    + EXAM_MANAGE
    + FEE_MANAGE
    + ROYALTY_VIEW
    + EXPENSE_MANAGE
    + HR_MANAGE
    + ADM_WORK
)

EXTRA_PERMISSIONS = {
    "network_admin": DELETE_RECORDS
    + HIFZ_VIEW
    + INVENTORY_VIEW
    + PAYROLL_VIEW
    + NOTICE_POST
    + TEMPLATE_EDIT
    + ATT_VIEW
    + DIARY_DESIGN
    + EXAM_SETUP
    + FEE_SETUP
    + ROYALTY_RECORD
    + EXPENSE_VIEW
    + HR_SETUP
    + ADM_VIEW,
    "head_office_admin": DELETE_RECORDS
    + HIFZ_VIEW
    + INVENTORY_VIEW
    + PAYROLL_VIEW
    + NOTICE_POST
    + ATT_VIEW
    + DIARY_DESIGN
    + EXAM_SETUP
    + FEE_SETUP
    + ROYALTY_RECORD
    + EXPENSE_VIEW
    + HR_SETUP
    + ADM_VIEW,
    "regional_director": HIFZ_VIEW
    + INVENTORY_VIEW
    + PAYROLL_VIEW
    + ATT_VIEW
    + DIARY_VIEW
    + EXAM_VIEW
    + FEE_VIEW
    + FEE_APPROVE
    + ROYALTY_VIEW
    + HR_VIEW
    + ADM_VIEW,
    "branch_owner": BRANCH_EVERYTHING,
    "principal": PAYROLL_VIEW
    + DEFAULTERS
    + HIFZ_MANAGE
    + NOTICE_POST
    + ATT_MANAGE
    + DIARY_MANAGE
    + EXAM_MANAGE
    + HR_MANAGE
    + ADM_WORK,
    "academic_coordinator": DEFAULTERS + HIFZ_MANAGE + ATT_MANAGE + DIARY_MANAGE + EXAM_MANAGE,
    "accountant": FEE_COLLECT
    + EXPENSE_MANAGE
    + INVENTORY_MANAGE
    + PAYROLL_MANAGE
    + ["hr.view_employee", "hr.view_staffday", "hr.view_leaverequest"],
    "admissions_officer": FEE_COLLECT + ADM_WORK,
    "class_teacher": ATT_MARK + DIARY_WRITE + EXAM_ENTER,
    "hifz_teacher": HIFZ_WRITE + ATT_MARK + DIARY_WRITE,
    "subject_teacher": ATT_VIEW + DIARY_VIEW + EXAM_VIEW,
}

# Subjects and their order as they appear on the Class 4 diary shared on 16 Oct 2026.
# Other classes' subject lists are to be entered by head office (Setup → Class levels).
SUBJECTS = [
    ("english", "English", "انگریزی", False),
    ("science", "Science", "سائنس", False),
    ("mathematics", "Mathematics", "ریاضی", False),
    ("computer", "Computer", "کمپیوٹر", False),
    ("islamiyat", "Islamiyat", "اسلامیات", True),
    ("urdu", "Urdu", "اردو", True),
    ("al-quran", "Al-Quran", "القرآن", True),
]
# Approved by the project lead on 16 Oct 2026. Seeded once; head office edits it in Setup afterwards.
RESULT_PATTERN = [
    ("final", "Final exam", "فائنل امتحان", "final", "subject", 50),
    ("mid", "Mid-Term exam", "مڈ ٹرم امتحان", "mid", "subject", 25),
    ("attendance", "Attendance", "حاضری", "attendance", "student", 5),
    ("discipline", "Discipline", "نظم و ضبط", "rating", "student", 5),
    ("neatness", "Neatness", "صفائی", "rating", "subject", 5),
    ("summer_work", "Summer vacation work", "موسم گرما کا کام", "rating", "subject", 5),
    ("class_work", "Class work & homework", "کلاس ورک اور ہوم ورک", "rating", "subject", 5),
]

# Leave types: names only. How many days each allows is set by head office (Setup → Leave types).
LEAVE_TYPES = [
    ("casual", "Casual leave", "اتفاقی رخصت"),
    ("sick", "Sick leave", "بیماری کی رخصت"),
    ("other", "Other leave", "دیگر رخصت"),
]

# Voucher columns, in the order of the school's current fee voucher (shared 16 Oct 2026).
# code, name, short name, Urdu, kind, charge months. No re-admission fee (confirmed 16 Oct 2026).
FEE_HEADS = [
    ("admission", "Admission fee", "Admission", "داخلہ فیس", "one_time", []),
    ("registration", "Registration fee", "Reg.", "رجسٹریشن فیس", "one_time", []),
    ("tuition", "Monthly (tuition) fee", "Tuition", "ماہانہ فیس", "monthly", []),
    ("annual", "Annual charges", "Annual", "سالانہ چارجز", "yearly", [4]),
    ("summer_work", "Summer vacation work", "S.V.W.", "سمر ویکیشن ورک", "seasonal", [7]),
    # Added only when ticked while making vouchers (22 Oct 2026); each branch sets the amount.
    ("ac", "AC charges", "AC", "اے سی چارجز", "seasonal", []),
    # "Gen. Exp." on the school's voucher is the generator expense (project lead, 22 Oct 2026).
    ("general", "Generator expenses", "Gen. Exp.", "جنریٹر اخراجات", "other", []),
    ("others", "Other charges", "Others", "دیگر", "other", []),
    ("fine", "Late fee fine", "Fine", "جرمانہ", "fine", []),
]
# Samanabad campus fees confirmed by the project lead on 16 Oct 2026. Each franchise sets its own.
# head, class level code (None = all classes), amount, sibling amount
SAMANABAD_RATES = [
    ("tuition", None, 4300, 4000),
    ("annual", None, 4500, None),
    ("annual", "pre-9", 5500, None),
    ("annual", "class-9", 5500, None),
    ("annual", "class-10", 5500, None),
    ("annual", "hifz", 2000, None),
    ("admission", None, 6500, None),
    ("registration", None, 1500, None),
]
OFFICIAL_WHATSAPP = "0339-2406479"
VOUCHER_NOTE = "Dear parents, you can pay this voucher online via the JazzCash app, anytime, anywhere. Thank you."
# Back of the voucher, as shared by the project lead on 16 Oct 2026.
BACK_NOTES_UR = """والدین آن لائن فیس جمع کرواتے وقت ادائیگی سے پہلے واؤچر ضرور چیک کریں تاکہ کسی پریشانی سے بچا جا سکے۔
والدین آن لائن فیس جمع کروانے کے بعد رسید کاپی + فیس واؤچر سکول کے دیئے گئے واٹس ایپ نمبر پر لازمی بھیجیں تاکہ آپ کی فیس کا اندراج بروقت کیا جا سکے۔
اگر کسی وجہ سے واؤچر حاصل نہ ہو سکے تو سکول آفس یا واٹس ایپ پر رابطہ کریں۔"""
BACK_FOOTER_UR = "آپ کے بچوں کے بہترین مستقبل کے لئے کوشاں۔ انتظامیہ"
PAYMENT_CHANNELS = [
    (
        "jazzcash",
        "JazzCash - Education Payment",
        """Open the JazzCash app.
Navigate to the "More" section.
Under **Education**, select **Schools**.
Choose **The Arqam Schools** from the list.
Enter the Voucher ID (as mentioned on the fee voucher).
Verify your child's name and the fee details.
Click **Confirm** to complete the transaction.
After payment, please share the receipt on the school's WhatsApp number: **{whatsapp}**.""",
        """جاز کیش ایپ کھولیں۔
"More" سیکشن میں جائیں اور Education کے آپشن میں Schools منتخب کریں۔
فہرست میں سے The Arqam Schools کا انتخاب کریں۔
Voucher ID درج کریں (جیسا کہ فیس واؤچر پر درج ہے)۔
اپنے بچے کا نام اور فیس کی تفصیلات کی تصدیق کریں۔
Confirm پر کلک کر کے ٹرانزیکشن مکمل کریں۔
ادائیگی کے بعد، براہ کرم رسید اسکول کے واٹس ایپ نمبر {whatsapp} پر شیئر کریں۔""",
        "Please note: A service fee of Rs. 15 per transaction is charged by JazzCash for this facility.",
        "براہ کرم نوٹ فرمائیں: اس سہولت کے استعمال پر جاز کیش کی جانب سے فی ٹرانزیکشن 15 روپے سروس چارج لیا جاتا ہے۔",
    ),
    (
        "bank_branch",
        "{bank_name} – Branch & Online Payment",
        """Fees may be deposited at any {bank_name} branch by presenting the fee voucher.
For online bank transfers, please use the bank details below.
After completing the payment, it is mandatory to share the payment receipt along with the fee voucher on the school's WhatsApp number: **{whatsapp}**.""",
        """فیس کسی بھی بینک برانچ میں فیس واؤچر جمع کروا کر ادا کی جا سکتی ہے۔
آن لائن بینک ٹرانسفر کے لیے، براہ کرم نیچے دی گئی بینک تفصیلات استعمال کریں۔
ادائیگی مکمل ہونے کے بعد، ادائیگی کی رسید اور فیس واؤچر اسکول کے واٹس ایپ نمبر {whatsapp} پر شیئر کرنا لازمی ہے۔""",
        "",
        "",
    ),
    (
        "alfa",
        "Bank Al-Falah App - Education Payment",
        """Open the Bank Alfalah Mobile Banking App.
Navigate to **Bills & Payments**.
Select **Fees**, then choose **New Payment**.
Under the **Education** category, search for **The Arqam Schools**.
Enter the Voucher ID (as mentioned on the fee voucher).
Verify your child's name and fee details.
Click **Continue**, then select **Pay Now** to complete the transaction.
After payment, please share the receipt on the school's WhatsApp number: **{whatsapp}**.""",
        """بینک الفلاح موبائل بینکنگ ایپ کھولیں۔
Bills & Payments کے آپشن پر جائیں۔
Fees منتخب کریں، پھر New Payment پر کلک کریں۔
Education کے سیکشن میں جا کر The Arqam Schools تلاش کریں۔
Voucher ID درج کریں (جیسا کہ فیس واؤچر پر درج ہے)۔
اپنے بچے کا نام اور فیس کی تفصیلات کی تصدیق کریں۔
Continue پر کلک کریں، پھر Pay Now دبا کر ادائیگی مکمل کریں۔
ادائیگی کے بعد، براہ کرم رسید اسکول کے واٹس ایپ نمبر {whatsapp} پر شیئر کریں۔""",
        "Please note: Bank Alfalah charges a service fee of Rs. 40 per transaction for this facility.",
        "براہ کرم نوٹ فرمائیں: اس سہولت کے استعمال پر بینک الفلاح کی جانب سے فی ٹرانزیکشن 40 روپے چارج کیے جاتے ہیں۔",
    ),
]

CONFIRMED_CURRICULUM = {"class-4": [code for code, *_rest in SUBJECTS]}


def perms(names):
    result = []
    for name in names:
        app_label, codename = name.split(".")
        result.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return result


class Command(BaseCommand):
    help = "Seed head offices, the Samanabad campus, system roles and class levels."

    @transaction.atomic
    def handle(self, *args, **options):
        fsd, _ = HeadOffice.objects.update_or_create(
            code="faisalabad",
            defaults={
                "name": "The Arqam Schools — Faisalabad Head Office",
                "city": "Faisalabad",
                "address": "Sanora Colony, Samanabad, Faisalabad, Pakistan",
                "phone": "041-2660265, 041-2406479",
            },
        )
        HeadOffice.objects.update_or_create(
            code="lahore", defaults={"name": "The Arqam Schools — Lahore Head Office", "city": "Lahore"}
        )
        Branch.objects.update_or_create(
            code="fsd-samanabad",
            defaults={
                "name": "The Arqam Schools — Samanabad Campus (Head Office)",
                "head_office": fsd,
                "ownership": Branch.Ownership.COMPANY,
                "royalty_percent": 0,
                "city": "Faisalabad",
                # Head office campus: certificate references read TAS-HO-FSD-0001 (project lead, 23 Oct 2026).
                "is_head_office": True,
            },
        )
        # Official contacts; filled only where empty, so changes made in Setup → Branches are kept.
        samanabad = Branch.objects.get(code="fsd-samanabad")
        contacts = {
            "address": "Sanora Colony, Samanabad, Faisalabad, Pakistan",
            "phone": "041-2660265",
            "phone_2": "041-2406479",
            "mobile_1": "0339-2406479",
        }
        empty = {k: v for k, v in contacts.items() if not getattr(samanabad, k)}
        if empty:
            Branch.objects.filter(pk=samanabad.pk).update(**empty)

        for code, name, name_ur, scopes, perm_names, mfa in ROLES:
            role, _ = Role.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "name_ur": name_ur,
                    "allowed_scopes": list(scopes),
                    "requires_mfa": mfa,
                    "is_system": True,
                },
            )
            role.permissions.set(perms(perm_names + EXTRA_PERMISSIONS.get(code, [])))

        # Move existing levels out of the way first so re-ordering never hits the unique sort_order rule.
        ClassLevel.objects.update(sort_order=models.F("sort_order") + 10000)
        for i, (code, name, name_ur, stage) in enumerate(CLASS_LEVELS, start=1):
            ClassLevel.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "name_ur": name_ur,
                    "stage": stage,
                    "sort_order": i * 10,
                    "separate_by_gender": stage in ("middle", "high"),
                    "attends_on_saturday": code in SATURDAY_CLASSES,
                },
            )

        for code, name, name_ur, rtl in SUBJECTS:
            Subject.objects.update_or_create(code=code, defaults={"name": name, "name_ur": name_ur, "is_rtl": rtl})
        for level_code, subject_codes in CONFIRMED_CURRICULUM.items():
            level = ClassLevel.objects.get(code=level_code)
            for order, subject_code in enumerate(subject_codes, start=1):
                CurriculumSubject.objects.update_or_create(
                    class_level=level, subject=Subject.objects.get(code=subject_code), defaults={"sort_order": order}
                )

        # Approved result pattern (D-030): every subject out of 100.
        scheme, created = GradingScheme.objects.get_or_create(
            is_default=True, defaults={"name": "Arqam result pattern (Final 50 + Mid 25 + 25 continuous)"}
        )
        if created:
            for order, (code, name, name_ur, source, scope, maximum) in enumerate(RESULT_PATTERN, start=1):
                GradingComponent.objects.create(
                    scheme=scheme,
                    code=code,
                    name=name,
                    name_ur=name_ur,
                    source=source,
                    scope=scope,
                    max_marks=maximum,
                    sort_order=order,
                )

        self.seed_fees()
        self.seed_hr()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded: 2 head offices, Samanabad campus, {len(ROLES)} roles, {len(CLASS_LEVELS)} class levels."
            )
        )

    def seed_fees(self):
        for order, (code, name, short, name_ur, kind, months) in enumerate(FEE_HEADS, start=1):
            FeeHead.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "short_name": short,
                    "name_ur": name_ur,
                    "kind": kind,
                    "charge_months": months,
                    "sort_order": order,
                },
            )
        if not VoucherCounter.objects.exists():
            VoucherCounter.objects.create()

        samanabad = Branch.objects.get(code="fsd-samanabad")
        # Rates and settings are created once; after that head office edits them in Setup.
        if not FeeRate.objects.filter(branch=samanabad).exists():
            for head, level, amount, sibling in SAMANABAD_RATES:
                FeeRate.objects.create(
                    branch=samanabad,
                    head=FeeHead.objects.get(code=head),
                    class_level=ClassLevel.objects.get(code=level) if level else None,
                    amount=amount,
                    sibling_amount=sibling,
                    effective_from="2026-04-01",
                )
        # Bank name, account title and number are entered by head office in Setup, not kept in code.
        BranchFeeSettings.objects.get_or_create(
            branch=samanabad,
            defaults={
                "receipt_whatsapp": OFFICIAL_WHATSAPP,
                "voucher_note": VOUCHER_NOTE,
                "back_notes_ur": BACK_NOTES_UR,
                "back_footer_ur": BACK_FOOTER_UR,
            },
        )
        if not PaymentChannel.objects.exists():
            for order, (method, title, steps_en, steps_ur, note_en, note_ur) in enumerate(PAYMENT_CHANNELS, 1):
                PaymentChannel.objects.create(
                    method=method,
                    title=title,
                    steps_en=steps_en,
                    steps_ur=steps_ur,
                    note_en=note_en,
                    note_ur=note_ur,
                    sort_order=order,
                )

    def seed_hr(self):
        # No fixed leave allowance: any leave is unpaid (confirmed 16 Oct 2026).
        for code, name, name_ur in LEAVE_TYPES:
            LeaveType.objects.update_or_create(
                code=code, defaults={"name": name, "name_ur": name_ur, "is_paid": False, "days_per_year": None}
            )
        # Samanabad staff duty 07:45–13:45, Monday to Saturday (confirmed 16 Oct 2026). Created once;
        # head office changes it in Setup afterwards.
        HRSettings.objects.get_or_create(
            branch=Branch.objects.get(code="fsd-samanabad"),
            defaults={"duty_starts": "07:45", "duty_ends": "13:45", "working_days": [0, 1, 2, 3, 4, 5]},
        )
