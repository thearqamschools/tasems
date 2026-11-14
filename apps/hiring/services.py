"""Hiring rules: one record per person (same mobile or CNIC), CVs found by post / subject / level, the steps of a
vacancy, the Bin (two years from the latest CV, then 30 days), and making the staff record from a hired candidate."""

import datetime as dt

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import BIN_DAYS, KEEP_DAYS, Application, ApplicationStep, Candidate, CandidateCall, Vacancy

VIEW_PERM = "hiring.view_candidate"
ADD_PERM = "hiring.add_candidate"
EDIT_PERM = "hiring.change_candidate"
BIN_PERM = "hiring.delete_candidate"
VACANCY_PERM = "hiring.add_vacancy"
MOVE_PERM = "hiring.change_application"
SHEET_VIEW_PERM = "hiring.view_interviewsheet"
SHEET_PERM = "hiring.add_interviewsheet"
POST_PERM = "hiring.change_post"


def digits(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def mobile_key(value):
    """0300-1234567, +92 300 1234567 and 03001234567 are the same number: compare the last 10 digits."""
    d = digits(value)
    return d[-10:] if len(d) >= 10 else d


def find_same_person(branch, mobile="", cnic="", exclude=None):
    """The person already in the CV bank with this mobile number or CNIC (Bin included), or None."""
    key, cnic_digits = mobile_key(mobile), digits(cnic)
    if len(key) < 7 and len(cnic_digits) < 13:
        return None
    qs = Candidate.objects.filter(branch=branch)
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    for c in qs.only("id", "mobile", "cnic", "full_name", "last_received_on", "binned_at"):
        if (len(key) >= 7 and mobile_key(c.mobile) == key) or (
            len(cnic_digits) == 13 and digits(c.cnic) == cnic_digits
        ):
            return c
    return None


def search(qs, q):
    q = (q or "").strip()
    if not q:
        return qs
    match = Q(full_name__icontains=q) | Q(father_name__icontains=q) | Q(qualification__icontains=q)
    match |= Q(address__icontains=q) | Q(education__institute__icontains=q) | Q(education__degree__icontains=q)
    d = digits(q)
    if d and d == q.replace(" ", "").lstrip("#").removeprefix("CV").removeprefix("cv") and len(d) <= 6:
        match |= Q(cvs__number=int(d))  # CV No. (R10-1): typing 41 finds CV No. 41
    if len(d) >= 4:
        match |= Q(mobile__contains=d[-7:]) | Q(cnic__contains=d)
    return qs.filter(match).distinct()


def with_cv_numbers(candidates):
    """Sets each candidate's latest CV No. in one query (for lists)."""
    from .models import CandidateCV

    ids = [c.id for c in candidates]
    latest = {}
    for cid, number in (
        CandidateCV.objects.filter(candidate_id__in=ids).exclude(number=None).order_by("received_on", "number")
        .values_list("candidate_id", "number")
    ):  # fmt: skip
        latest[cid] = number
    for c in candidates:
        c._cv_no = latest.get(c.id)
    return candidates


def filter_bank(qs, post="", subject="", level="", campus="", relevance="", status=""):
    if str(post).isdigit():
        qs = qs.filter(post_id=post)
    if subject:
        qs = qs.filter(subjects__contains=[subject])
    if level:
        qs = qs.filter(levels__contains=[level])
    if str(campus).isdigit():
        qs = qs.filter(Q(campus_id=campus) | Q(campus__isnull=True))
    if relevance:
        qs = qs.filter(relevance=relevance)
    if status:
        qs = qs.filter(status=status)
    return qs


def matching(vacancy):
    """CVs that fit a vacancy: same post, the subject and level when the vacancy names them, not marked not
    relevant, not hired, not in the Bin and not already in this vacancy; latest CV first."""
    qs = Candidate.objects.filter(branch=vacancy.branch, post=vacancy.post, binned_at__isnull=True).exclude(
        relevance=Candidate.Relevance.NOT_RELEVANT
    )
    qs = qs.exclude(status=Candidate.Status.HIRED).exclude(applications__vacancy=vacancy)
    if vacancy.subject:
        qs = qs.filter(subjects__contains=[vacancy.subject])
    if vacancy.level:
        qs = qs.filter(levels__contains=[vacancy.level])
    if vacancy.campus_id:
        qs = qs.filter(Q(campus_id=vacancy.campus_id) | Q(campus__isnull=True))
    return qs.order_by("-last_received_on", "-id")


def refresh_status(candidate):
    if candidate.status == Candidate.Status.HIRED:
        return
    busy = candidate.applications.filter(stage__in=Application.OPEN_STAGES).exists()
    candidate.status = Candidate.Status.IN_PROCESS if busy else Candidate.Status.AVAILABLE
    candidate.save(update_fields=["status", "updated_at"])


@transaction.atomic
def shortlist(vacancy, candidates, user):
    added = 0
    for c in candidates:
        app, created = Application.objects.get_or_create(
            branch_id=vacancy.branch_id, vacancy=vacancy, candidate=c, defaults={"updated_by": user}
        )
        if created:
            ApplicationStep.objects.create(branch_id=vacancy.branch_id, application=app, stage=app.stage, by=user)
            added += 1
        refresh_status(c)
    return added


@transaction.atomic
def move(application, stage, user, note="", **details):
    """Moves an application to a step and records it. "Joined" is set only by making the staff record."""
    if stage not in Application.Stage.values or stage == Application.Stage.JOINED:
        raise ValueError(stage)
    application.stage = stage
    for field, value in details.items():
        setattr(application, field, value)
    if note:
        application.note = note[:250]
    application.updated_by = user
    application.save()
    ApplicationStep.objects.create(
        branch_id=application.branch_id, application=application, stage=stage, note=note[:250], by=user
    )
    refresh_status(application.candidate)
    return application


@transaction.atomic
def log_call(candidate, result, user, note="", application=None):
    """Records a call. Picked up moves a shortlisted person to Called; Not interested takes them off the vacancy
    (as "Not available"). Calls not picked up stay on record and show as "did not pick up ×N"."""
    call = CandidateCall.objects.create(
        branch_id=candidate.branch_id, candidate=candidate, application=application, result=result, note=note[:200],
        by=user,
    )  # fmt: skip
    if application is not None and application.is_open:
        if result == CandidateCall.Result.PICKED and application.stage == Application.Stage.SHORTLISTED:
            move(application, Application.Stage.CALLED, user, note)
        elif result == CandidateCall.Result.NOT_INTERESTED:
            move(application, Application.Stage.WITHDREW, user, note or str(CandidateCall.Result.NOT_INTERESTED.label))
    return call


@transaction.atomic
def mark_hired(candidate, employee, user):
    """The staff record made from this candidate: candidate hired, their open step "Joined", the vacancy filled
    once it has its people. The CV file is kept on the staff record when it has none."""
    candidate.hired_employee = employee
    candidate.status = Candidate.Status.HIRED
    candidate.save(update_fields=["hired_employee", "status", "updated_at"])
    app = (
        candidate.applications.filter(stage__in=Application.OPEN_STAGES)
        .order_by("-stage", "-updated_at")
        .select_related("vacancy")
        .first()
    )
    if app:
        app.stage, app.updated_by = Application.Stage.JOINED, user
        app.joining_on = app.joining_on or employee.joined_on
        app.save()
        ApplicationStep.objects.create(branch_id=app.branch_id, application=app, stage=app.stage, by=user)
        vacancy = app.vacancy
        if vacancy.applications.filter(stage=Application.Stage.JOINED).count() >= vacancy.openings:
            vacancy.status, vacancy.filled_on = Vacancy.Status.FILLED, timezone.localdate()
            vacancy.save(update_fields=["status", "filled_on", "updated_at"])
    if not employee.cv:
        first = next((f for cv in candidate.cvs.all() for f in cv.files.all()), None)
        if first and first.file.name.lower().endswith((".pdf", ".jpg", ".jpeg", ".png")):
            with first.file.open("rb") as handle:
                employee.cv.save(first.original_name or first.file.name.rsplit("/", 1)[-1], handle, save=True)
    from apps.hr.models import Qualification

    for e in candidate.education.all():
        Qualification.objects.get_or_create(
            branch_id=employee.branch_id, employee=employee, degree=e.degree[:120],
            defaults={"level": Qualification.Level.OTHER, "institute": e.institute[:150], "year": e.year},
        )  # fmt: skip


def staff_initial(candidate):
    """Add staff, filled in from the candidate."""
    from apps.hr.models import Employee

    teaching = candidate.post.is_teaching
    hifz = "hifz" in (candidate.levels or []) or "hifz" in (candidate.subjects or [])
    return {
        "full_name": candidate.full_name,
        "father_name": candidate.father_name,
        "gender": candidate.gender,
        "phone": candidate.mobile,
        "cnic": digits(candidate.cnic),
        "address": candidate.address,
        "qualification": candidate.qualification,
        "designation": candidate.post.name if not teaching else "Junior Teacher",
        "staff_type": Employee.StaffType.HIFZ
        if hifz
        else (Employee.StaffType.TEACHING if teaching else Employee.StaffType.ADMIN),
        "campus": candidate.campus_id,
        "joined_on": timezone.localdate(),
    }


def cleanup(now=None):
    """Bin CVs of people not hired and not in a vacancy two years after their latest CV; delete those 30 days in
    the Bin (with their files). Runs when TASEMS starts and every few hours (R8-13)."""
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    old = Candidate.objects.filter(
        binned_at__isnull=True, last_received_on__lte=today - dt.timedelta(days=KEEP_DAYS)
    ).exclude(status__in=[Candidate.Status.HIRED, Candidate.Status.IN_PROCESS])
    binned = old.update(binned_at=now)
    gone = 0
    for c in Candidate.objects.filter(binned_at__lte=now - dt.timedelta(days=BIN_DAYS)):
        delete_candidate(c)
        gone += 1
    return binned, gone


def delete_candidate(candidate):
    """Deletes a candidate with their CV files. A hired person's record stays (their staff record links to it)."""
    if candidate.status == Candidate.Status.HIRED:
        return False
    for cv in candidate.cvs.all():
        for f in cv.files.all():
            f.file.delete(save=False)
    candidate.delete()
    return True
