"""Hifz-e-Quran (M12): each Hifz student's daily lesson — Sabaq (new lesson), Sabqi (recent revision) and Manzil
(older revision) with mistakes — and the para tests that mark a para as memorised."""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.audit import audited
from apps.core.models import BranchOwnedModel

PARAS = 30
PARA = [MinValueValidator(1), MaxValueValidator(PARAS)]


class HifzLesson(BranchOwnedModel):
    """One student's lesson on one day. Not audited on creation (thousands a day); changes are logged by the
    service that saves the day's sheet."""

    class Status(models.TextChoices):
        HEARD = "heard", _("Heard")
        NOT_READY = "not_ready", _("Not ready")
        ABSENT = "absent", _("Absent")

    class Grade(models.TextChoices):  # shown in English in both languages (project lead, 23 Oct 2026)
        EXCELLENT = "excellent", "Excellent"
        GOOD = "good", "Good"
        AVERAGE = "average", "Average"
        WEAK = "weak", "Weak"

    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="hifz_lessons")
    section = models.ForeignKey("academics.Section", on_delete=models.PROTECT, null=True, related_name="+")
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.HEARD)
    sabaq_para = models.PositiveSmallIntegerField(_("para"), null=True, blank=True, validators=PARA)
    sabaq = models.CharField(
        _("sabaq"), max_length=80, blank=True, help_text=_("Surah and ayaat, e.g. Al-Baqarah 142–157")
    )
    sabaq_lines = models.PositiveSmallIntegerField(_("lines"), null=True, blank=True)
    sabaq_mistakes = models.PositiveSmallIntegerField(_("sabaq mistakes"), default=0)
    sabqi = models.CharField(_("sabqi"), max_length=40, blank=True, help_text=_("Para(s) revised, e.g. 3"))
    sabqi_mistakes = models.PositiveSmallIntegerField(_("sabqi mistakes"), default=0)
    manzil = models.CharField(_("manzil"), max_length=40, blank=True, help_text=_("Para(s) revised, e.g. 1–2"))
    manzil_mistakes = models.PositiveSmallIntegerField(_("manzil mistakes"), default=0)
    grade = models.CharField(_("grade"), max_length=10, choices=Grade.choices, blank=True)
    remarks = models.CharField(_("remarks"), max_length=200, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["student", "date"], name="one_hifz_lesson_per_day")]
        indexes = [models.Index(fields=["branch", "date"]), models.Index(fields=["section", "date"])]

    def __str__(self):
        return f"{self.student} {self.date:%d %b %Y}"

    @property
    def mistakes(self):
        return self.sabaq_mistakes + self.sabqi_mistakes + self.manzil_mistakes


@audited
class ParaTest(BranchOwnedModel):
    """A para heard in full by a senior teacher. A passed test marks the para as memorised."""

    class Result(models.TextChoices):
        PASSED = "passed", _("Passed")
        REPEAT = "repeat", _("To repeat")

    student = models.ForeignKey("people.Student", on_delete=models.PROTECT, related_name="para_tests")
    para = models.PositiveSmallIntegerField(_("para"), validators=PARA)
    tested_on = models.DateField(_("date"))
    result = models.CharField(_("result"), max_length=10, choices=Result.choices, default=Result.PASSED)
    mistakes = models.PositiveSmallIntegerField(_("mistakes"), default=0)
    before_joining = models.BooleanField(
        _("memorised before joining"), default=False, help_text=_("For paras memorised before the student joined")
    )
    remarks = models.CharField(_("remarks"), max_length=200, blank=True)
    tested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["para", "-tested_on"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "para"],
                condition=models.Q(result="passed", is_cancelled=False),
                name="one_passed_test_per_para",
            )
        ]

    def __str__(self):
        return f"{self.student} — para {self.para}: {self.get_result_display()}"
