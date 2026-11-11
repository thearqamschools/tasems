"""Hiring (project lead, 11 Nov 2026; change request R8): every CV the school receives — by hand, WhatsApp, email,
an advertisement or online — is saved once with the date it came, marked relevant or not, found again when a post
falls vacant, taken through interview and demo lesson, and the person hired becomes a staff record.

Entered by hand with a short form (no reading by AI and no paid service, R8-10). CVs of people not hired stay two
years from the latest CV entered, then go to the Bin, and are deleted 30 days later (R8-13, R8-16)."""

import secrets
from pathlib import Path

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel, TimeStampedModel

# Levels the school teaches (R8-11) and subjects a candidate can teach (R8-5, lead 11 Nov 2026).
LEVELS = [
    ("early_years", _("Early Years")),
    ("primary", _("Primary")),
    ("middle", _("Middle")),
    ("matric", _("Matric")),
    ("hifz", _("Hifz-e-Quran")),
]
SUBJECTS = [
    ("english", _("English")),
    ("urdu", _("Urdu")),
    ("maths", _("Maths")),
    ("science", _("Science")),
    ("physics", _("Physics")),
    ("chemistry", _("Chemistry")),
    ("biology", _("Biology")),
    ("computer", _("Computer")),
    ("islamiyat", _("Islamiyat")),
    ("nazra", _("Nazra")),
    ("hifz", _("Hifz")),
    ("social_studies", _("Social Studies")),
    ("pak_studies", _("Pak Studies")),
    ("general_knowledge", _("General Knowledge")),
    ("arabic", _("Arabic")),
    ("art", _("Drawing / Art")),
]
KEEP_DAYS = 730  # two years from the latest CV entered
BIN_DAYS = 30


def cv_file_path(instance, filename):
    """Private folder and a random name, so a CV cannot be guessed; it is opened only through TASEMS."""
    return f"private/hiring-cv/{instance.branch_id}/{secrets.token_hex(16)}{Path(filename).suffix.lower()}"


class Post(TimeStampedModel):
    """A post people apply for: the staff designations plus Teacher, Designer, Content Creator, Graphic Designer,
    Typist (R8-17). One list for the whole network, kept in Setup → Hiring posts."""

    name = models.CharField(_("post"), max_length=80, unique=True)
    is_teaching = models.BooleanField(_("teaching post"), default=False, help_text=_("Subjects and level apply"))
    order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(_("in use"), default=True)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


@audited
class Candidate(BranchOwnedModel):
    class Relevance(models.TextChoices):
        UNCHECKED = "unchecked", _("Not checked yet")
        RELEVANT = "relevant", _("Relevant")
        LATER = "later", _("Keep for later")
        NOT_RELEVANT = "not_relevant", _("Not relevant")

    class Status(models.TextChoices):
        AVAILABLE = "available", _("Available")
        IN_PROCESS = "in_process", _("In process")
        HIRED = "hired", _("Hired")

    full_name = models.CharField(_("name"), max_length=150)
    father_name = models.CharField(_("father / husband name"), max_length=150, blank=True)
    gender = models.CharField(
        _("gender"), max_length=10, choices=[("female", _("Female")), ("male", _("Male"))], default="female"
    )
    mobile = models.CharField(_("mobile"), max_length=30, blank=True)
    cnic = models.CharField(_("CNIC"), max_length=15, blank=True)
    email = models.EmailField(_("email"), blank=True)
    address = models.CharField(_("address"), max_length=250, blank=True)
    post = models.ForeignKey(Post, verbose_name=_("applied for"), on_delete=models.PROTECT, related_name="+")
    campus = models.ForeignKey(
        "organisation.Campus", verbose_name=_("campus"), on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )  # fmt: skip
    subjects = models.JSONField(_("can teach"), default=list, blank=True)
    levels = models.JSONField(_("level"), default=list, blank=True)
    qualification = models.CharField(_("highest qualification"), max_length=120, blank=True)
    experience_years = models.DecimalField(
        _("experience (years)"), max_digits=4, decimal_places=1, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(60)],
    )  # fmt: skip
    salary_asked = models.PositiveIntegerField(_("salary asked (Rs)"), null=True, blank=True)
    relevance = models.CharField(_("relevant?"), max_length=12, choices=Relevance.choices, default=Relevance.UNCHECKED)
    relevance_note = models.CharField(_("reason"), max_length=200, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.AVAILABLE)
    last_received_on = models.DateField(_("latest CV received"))
    binned_at = models.DateTimeField(null=True, blank=True)
    hired_employee = models.OneToOneField(
        "hr.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="hired_from"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-last_received_on", "-id"]
        indexes = [models.Index(fields=["branch", "last_received_on"]), models.Index(fields=["branch", "mobile"])]

    def __str__(self):
        return self.full_name

    def subject_labels(self):
        names = dict(SUBJECTS)
        return [str(names.get(s, s)) for s in self.subjects or []]

    def level_labels(self):
        names = dict(LEVELS)
        return [str(names.get(s, s)) for s in self.levels or []]


class CandidateCV(BranchOwnedModel):
    """One time a person sent a CV: when, how, for which post; the photos or PDF of it."""

    class Channel(models.TextChoices):
        IN_HAND = "in_hand", _("In hand at school")
        WHATSAPP = "whatsapp", _("WhatsApp")
        EMAIL = "email", _("Email")
        ADVERT = "advert", _("After an advertisement")
        ONLINE = "online", _("Online")
        REFERRED = "referred", _("Referred by someone")
        OTHER = "other", _("Other")

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="cvs")
    received_on = models.DateField(_("CV received on"))
    channel = models.CharField(_("came by"), max_length=10, choices=Channel.choices, default=Channel.IN_HAND)
    post = models.ForeignKey(Post, verbose_name=_("applied for"), on_delete=models.PROTECT, related_name="+")
    note = models.CharField(_("note"), max_length=200, blank=True)
    entered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-received_on", "-id"]


class CVFile(BranchOwnedModel):
    cv = models.ForeignKey(CandidateCV, on_delete=models.CASCADE, related_name="files")
    file = models.FileField(upload_to=cv_file_path)
    original_name = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["id"]

    @property
    def is_image(self):
        return Path(self.file.name).suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}


class Education(BranchOwnedModel):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="education")
    degree = models.CharField(_("degree"), max_length=120, help_text=_("e.g. M.Sc Chemistry, B.Ed"))
    institute = models.CharField(_("institute"), max_length=150, blank=True)
    year = models.PositiveSmallIntegerField(
        _("year"), null=True, blank=True, validators=[MinValueValidator(1950), MaxValueValidator(2100)]
    )

    class Meta:
        ordering = ["-year", "id"]


class Experience(BranchOwnedModel):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="experience")
    organisation = models.CharField(_("school / organisation"), max_length=150)
    post = models.CharField(_("post"), max_length=100, blank=True)
    level = models.CharField(_("level"), max_length=12, choices=LEVELS, blank=True)
    years = models.DecimalField(
        _("years"), max_digits=4, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(0)]
    )

    class Meta:
        ordering = ["id"]


@audited
class Vacancy(BranchOwnedModel):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        FILLED = "filled", _("Filled")
        CLOSED = "closed", _("Closed")

    post = models.ForeignKey(Post, verbose_name=_("post"), on_delete=models.PROTECT, related_name="+")
    subject = models.CharField(_("subject"), max_length=20, choices=SUBJECTS, blank=True)
    level = models.CharField(_("level"), max_length=12, choices=LEVELS, blank=True)
    campus = models.ForeignKey(
        "organisation.Campus", verbose_name=_("campus"), on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+",
    )  # fmt: skip
    openings = models.PositiveSmallIntegerField(_("people needed"), default=1, validators=[MinValueValidator(1)])
    needed_by = models.DateField(_("needed by"), null=True, blank=True)
    notes = models.CharField(_("notes"), max_length=250, blank=True, help_text=_("e.g. replaces Ms. Sana, Class 6"))
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN)
    filled_on = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["status", "-created_at"]
        verbose_name_plural = "vacancies"

    def __str__(self):
        parts = [str(self.post)]
        if self.subject:
            parts.append(str(self.get_subject_display()))
        if self.level:
            parts.append(str(self.get_level_display()))
        return " · ".join(parts)


class Application(BranchOwnedModel):
    """A candidate in a vacancy, moving through the steps (shortlisted → … → joined)."""

    class Stage(models.TextChoices):
        SHORTLISTED = "shortlisted", _("Shortlisted")
        CALLED = "called", _("Called")
        INTERVIEW = "interview", _("Interview")
        DEMO = "demo", _("Demo lesson")
        SELECTED = "selected", _("Selected")
        JOINED = "joined", _("Joined")
        REJECTED = "rejected", _("Not selected")
        WITHDREW = "withdrew", _("Not available")

    OPEN_STAGES = ["shortlisted", "called", "interview", "demo", "selected"]
    BOARD = ["shortlisted", "called", "interview", "demo", "selected", "joined"]

    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name="applications")
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="applications")
    stage = models.CharField(max_length=12, choices=Stage.choices, default=Stage.SHORTLISTED)
    interview_at = models.DateTimeField(_("interview / demo on"), null=True, blank=True)
    demo_class = models.CharField(_("demo lesson: class and topic"), max_length=150, blank=True)
    salary_offered = models.PositiveIntegerField(_("salary offered (Rs)"), null=True, blank=True)
    joining_on = models.DateField(_("joining date"), null=True, blank=True)
    note = models.CharField(_("note"), max_length=250, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(fields=["vacancy", "candidate"], name="one_application_per_vacancy")]

    @property
    def is_open(self):
        return self.stage in self.OPEN_STAGES


class ApplicationStep(BranchOwnedModel):
    """Every move of an application: which step, when, by whom."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="steps")
    stage = models.CharField(max_length=12, choices=Application.Stage.choices)
    note = models.CharField(max_length=250, blank=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["created_at", "id"]


MARKS = [
    # (field, heading, out of) — proposed by Claude 11 Nov 2026, accepted by the lead.
    ("subject_knowledge", _("Subject knowledge"), 10),
    ("teaching", _("Teaching method / demo lesson"), 10),
    ("communication", _("Communication (Urdu / English)"), 10),
    ("character", _("Personality, manners, Islamic values"), 10),
    ("experience", _("Experience and qualification"), 5),
    ("impression", _("Overall impression"), 5),
]


class InterviewSheet(BranchOwnedModel):
    """The interview mark sheet (R8-14): 50 marks, who interviewed, remarks and the decision."""

    class Decision(models.TextChoices):
        SELECT = "select", _("Select")
        WAITING = "waiting", _("Waiting list")
        REJECT = "reject", _("Not selected")

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="sheet")
    held_on = models.DateField(_("date"))
    interviewers = models.CharField(_("interviewed by"), max_length=200)
    subject_knowledge = models.PositiveSmallIntegerField(_("Subject knowledge"), validators=[MaxValueValidator(10)])
    teaching = models.PositiveSmallIntegerField(_("Teaching method / demo lesson"), validators=[MaxValueValidator(10)])
    communication = models.PositiveSmallIntegerField(
        _("Communication (Urdu / English)"), validators=[MaxValueValidator(10)]
    )
    character = models.PositiveSmallIntegerField(
        _("Personality, manners, Islamic values"), validators=[MaxValueValidator(10)]
    )
    experience = models.PositiveSmallIntegerField(_("Experience and qualification"), validators=[MaxValueValidator(5)])
    impression = models.PositiveSmallIntegerField(_("Overall impression"), validators=[MaxValueValidator(5)])
    remarks = models.TextField(_("remarks"), blank=True)
    decision = models.CharField(_("decision"), max_length=8, choices=Decision.choices)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    OUT_OF = sum(m for _f, _h, m in MARKS)

    @property
    def total(self):
        return sum(getattr(self, f) or 0 for f, _h, _m in MARKS)
