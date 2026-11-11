"""Hiring screens (R8): CV bank, add a CV, a candidate, vacancies with their board, interview mark sheet, this
week's interviews, hiring report, the Bin, and Setup → Hiring posts."""

import datetime as dt
import secrets
from collections import Counter
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core import exports
from apps.core.branch import current_branch

from . import services as S
from .forms import (
    CandidateForm,
    InterviewSheetForm,
    PostForm,
    ReceivedForm,
    StepForm,
    VacancyForm,
    candidate_formsets,
)
from .models import (
    LEVELS,
    MARKS,
    SUBJECTS,
    Application,
    Candidate,
    CandidateCV,
    CVFile,
    InterviewSheet,
    Post,
    Vacancy,
)

PAGE_SIZE = 50


def _branch(request, perm=S.VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _can(request, branch):
    def has(perm):
        return request.user.has_branch_perm(perm, branch.id)

    return {
        "add": has(S.ADD_PERM),
        "edit": has(S.EDIT_PERM),
        "bin": has(S.BIN_PERM),
        "vacancy": has(S.VACANCY_PERM),
        "move": has(S.MOVE_PERM),
        "sheet": has(S.SHEET_PERM),
        "sheet_view": has(S.SHEET_VIEW_PERM),
        "staff": has("hr.add_employee"),
    }


def _candidate(branch, pk):
    return get_object_or_404(Candidate, branch=branch, pk=pk)


def _natural_sort(request, items, keys, default="-received"):
    wanted = request.GET.get("sort") or default
    key = wanted.lstrip("-")
    if key not in keys:
        return items
    return sorted(items, key=keys[key], reverse=wanted.startswith("-"))


SORTS = {
    "received": lambda c: (c.last_received_on, c.id),
    "name": lambda c: c.full_name.lower(),
    "post": lambda c: str(c.post).lower(),
    "qualification": lambda c: (c.qualification or "").lower(),
    "experience": lambda c: c.experience_years or 0,
    "relevance": lambda c: c.relevance,
}


@login_required
def index(request):
    """CV bank: every candidate of the branch, latest CV first; search and filters (R8-7)."""
    branch = _branch(request)
    qs = Candidate.objects.filter(branch=branch, binned_at__isnull=True).select_related("post", "campus")
    f = {k: request.GET.get(k, "") for k in ("post", "subject", "level", "campus", "relevance", "status")}
    qs = S.filter_bank(S.search(qs, request.GET.get("q", "")), **f)
    received_from = request.GET.get("from", "")
    if received_from:
        try:
            qs = qs.filter(last_received_on__gte=dt.date.fromisoformat(received_from))
        except ValueError:
            pass
    rows = _natural_sort(request, list(qs[:2000]), SORTS)
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("CV bank"),
            [_("Latest CV"), _("Name"), _("Father / husband name"), _("Mobile"), _("Applied for"), _("Can teach"),
             _("Level"), _("Qualification"), _("Experience (years)"), _("Address"), _("Relevant?"), _("Status")],
            (
                [c.last_received_on, c.full_name, c.father_name, c.mobile, str(c.post), ", ".join(c.subject_labels()),
                 ", ".join(c.level_labels()), c.qualification, c.experience_years, c.address,
                 c.get_relevance_display(), c.get_status_display()]
                for c in rows
            ),
            branch=branch,
        )  # fmt: skip
    page = exports.paginate(request, rows, PAGE_SIZE)
    params = request.GET.copy()
    params.pop("page", None)
    from apps.organisation.models import Campus

    return render(
        request,
        "hiring/index.html",
        {
            "page": page,
            "total": len(rows),
            "f": f,
            "q": request.GET.get("q", ""),
            "received_from": received_from,
            "posts": Post.objects.filter(is_active=True),
            "subjects": SUBJECTS,
            "levels": LEVELS,
            "campuses": Campus.objects.filter(branch=branch, is_active=True),
            "relevances": Candidate.Relevance.choices,
            "statuses": Candidate.Status.choices,
            "binned": Candidate.objects.filter(branch=branch, binned_at__isnull=False).count(),
            "querystring": params.urlencode(),
            "can": _can(request, branch),
        },
    )


# --- Add a CV -------------------------------------------------------------------------------------------

PENDING_KEY = "hiring_pending_files"


def _keep_files(request, files):
    """Files of a CV held while the office decides whether it is the same person (a page reload loses uploads)."""
    token = secrets.token_hex(8)
    saved = []
    for f in files:
        path = default_storage.save(f"private/hiring-pending/{token}/{secrets.token_hex(8)}{Path(f.name).suffix}", f)
        saved.append((path, f.name[:150]))
    pending = request.session.get(PENDING_KEY, {})
    pending[token] = saved
    request.session[PENDING_KEY] = pending
    return token


def _take_files(request, token):
    pending = request.session.get(PENDING_KEY, {})
    saved = pending.pop(token, []) if token else []
    request.session[PENDING_KEY] = pending
    return saved


def _attach_files(cv, uploads, kept):
    for f in uploads:
        CVFile.objects.create(branch_id=cv.branch_id, cv=cv, file=f, original_name=f.name[:150])
    for path, name in kept:
        if default_storage.exists(path):
            with default_storage.open(path, "rb") as handle:
                CVFile.objects.create(branch_id=cv.branch_id, cv=cv, file=File(handle, name=name), original_name=name)
            default_storage.delete(path)


def _add_cv(candidate, received, user, uploads, kept, post=None):
    cv = received.save(commit=False)
    cv.branch_id, cv.candidate, cv.entered_by = candidate.branch_id, candidate, user
    cv.post = post or candidate.post
    cv.save()
    _attach_files(cv, uploads, kept)
    if cv.received_on >= candidate.last_received_on or candidate.binned_at:
        candidate.last_received_on = max(candidate.last_received_on, cv.received_on)
        candidate.binned_at = None  # a new CV brings the person back from the Bin; the two years start again
        candidate.save(update_fields=["last_received_on", "binned_at", "updated_at"])
    return cv


@login_required
def add(request):
    """Add a CV (steps 1–3): when and how it came, its photos, the person's details, relevant or not."""
    branch = _branch(request, S.ADD_PERM)
    form = CandidateForm(request.POST or None, branch=branch)
    received = ReceivedForm(request.POST or None, request.FILES or None)
    sets = candidate_formsets(request.POST if request.method == "POST" else None)
    same, token = None, request.POST.get("pending", "")
    if (
        request.method == "POST"
        and form.is_valid()
        and received.is_valid()
        and all(s.is_valid() for s in sets.values())
    ):
        choice = request.POST.get("same_person", "")
        same = S.find_same_person(branch, form.cleaned_data["mobile"], form.cleaned_data["cnic"])
        uploads = received.cleaned_data["files"]
        if same and choice not in ("attach", "new"):
            # Same mobile or CNIC already in the CV bank: ask before saving (R8, one record per person).
            kept_token = _keep_files(request, uploads) if uploads else token
            return render(
                request, "hiring/add.html", _add_context(request, branch, form, received, sets, same, kept_token)
            )
        kept = _take_files(request, token)
        with transaction.atomic():
            if same and choice == "attach":
                candidate = same
                _add_cv(candidate, received, request.user, uploads, kept, post=form.cleaned_data["post"])
                messages.success(request, _("CV added to %(n)s's record.") % {"n": candidate.full_name})
            else:
                candidate = form.save(commit=False)
                candidate.branch, candidate.created_by = branch, request.user
                candidate.last_received_on = received.cleaned_data["received_on"]
                candidate.save()
                for s in sets.values():
                    s.instance = candidate
                    for item in s.save(commit=False):
                        item.branch_id = branch.id
                        item.save()
                    for item in s.deleted_objects:
                        item.delete()
                _add_cv(candidate, received, request.user, uploads, kept)
                messages.success(request, _("CV of %(n)s saved.") % {"n": candidate.full_name})
        if request.POST.get("next") == "add":
            return redirect("hiring:add")
        return redirect("hiring:candidate", candidate.pk)
    return render(request, "hiring/add.html", _add_context(request, branch, form, received, sets, same, token))


def _add_context(request, branch, form, received, sets, same, token):
    return {"form": form, "received": received, "sets": sets, "same": same, "pending": token, "branch": branch}


@login_required
def edit(request, pk):
    branch = _branch(request, S.EDIT_PERM)
    candidate = _candidate(branch, pk)
    form = CandidateForm(request.POST or None, instance=candidate, branch=branch)
    sets = candidate_formsets(request.POST if request.method == "POST" else None, instance=candidate)
    if request.method == "POST" and form.is_valid() and all(s.is_valid() for s in sets.values()):
        with transaction.atomic():
            form.save()
            for s in sets.values():
                for item in s.save(commit=False):
                    item.branch_id = branch.id
                    item.save()
                for item in s.deleted_objects:
                    item.delete()
        messages.success(request, _("Saved."))
        return redirect("hiring:candidate", candidate.pk)
    return render(request, "hiring/edit.html", {"form": form, "sets": sets, "candidate": candidate})


@login_required
def candidate(request, pk):
    branch = _branch(request)
    c = _candidate(branch, pk)
    can = _can(request, branch)
    received = ReceivedForm(request.POST or None, request.FILES or None, prefix="cv")
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "relevance" and can["edit"]:
            value = request.POST.get("relevance")
            if value in Candidate.Relevance.values:
                c.relevance, c.relevance_note = value, request.POST.get("relevance_note", "")[:200]
                c.save(update_fields=["relevance", "relevance_note", "updated_at"])
                messages.success(request, _("Marked %(r)s.") % {"r": c.get_relevance_display()})
        elif action == "add_cv" and can["add"]:
            if received.is_valid():
                _add_cv(c, received, request.user, received.cleaned_data["files"], [])
                messages.success(request, _("CV added."))
            else:
                messages.error(request, _("Check the date and the files."))
        elif action == "bin" and can["bin"] and c.status != Candidate.Status.HIRED:
            c.binned_at = timezone.now()
            c.save(update_fields=["binned_at", "updated_at"])
            messages.success(request, _("%(n)s moved to the Bin. It is deleted after 30 days.") % {"n": c.full_name})
            return redirect("hiring:index")
        elif action == "restore" and can["bin"]:
            c.binned_at = None
            c.save(update_fields=["binned_at", "updated_at"])
            messages.success(request, _("Taken out of the Bin."))
        elif action == "shortlist" and can["move"]:
            vacancy = Vacancy.objects.filter(branch=branch, pk=request.POST.get("vacancy") or 0).first()
            if vacancy:
                S.shortlist(vacancy, [c], request.user)
                messages.success(request, _("Shortlisted for %(v)s.") % {"v": vacancy})
        else:
            raise PermissionDenied
        return redirect("hiring:candidate", c.pk)
    apps = c.applications.select_related("vacancy__post").prefetch_related("steps")
    return render(
        request,
        "hiring/candidate.html",
        {
            "c": c,
            "cvs": c.cvs.select_related("post", "entered_by").prefetch_related("files"),
            "applications": apps,
            "received": received,
            "open_vacancies": Vacancy.objects.filter(branch=branch, status=Vacancy.Status.OPEN).exclude(
                applications__candidate=c
            ),
            "relevances": Candidate.Relevance.choices,
            "can": can,
            "keep_until": c.last_received_on + dt.timedelta(days=730),
        },
    )


@login_required
def cv_file(request, file_id):
    """CV files are private: only people who may see this branch's CV bank open them."""
    branch = _branch(request)
    f = get_object_or_404(CVFile, branch=branch, pk=file_id)
    return FileResponse(f.file.open("rb"), filename=f.original_name or Path(f.file.name).name)


# --- Vacancies ------------------------------------------------------------------------------------------


@login_required
def vacancies(request):
    branch = _branch(request, "hiring.view_vacancy")
    can = _can(request, branch)
    form = VacancyForm(request.POST or None, branch=branch)
    if request.method == "POST":
        if not can["vacancy"]:
            raise PermissionDenied
        if form.is_valid():
            v = form.save(commit=False)
            v.branch, v.created_by = branch, request.user
            v.save()
            messages.success(request, _("Vacancy opened. Matching CVs are listed below."))
            return redirect("hiring:vacancy", v.pk)
    rows = (
        Vacancy.objects.filter(branch=branch)
        .select_related("post", "campus")
        .annotate(people=Count("applications"))
        .order_by("status", "-created_at")
    )
    return render(request, "hiring/vacancies.html", {"rows": rows, "form": form, "can": can})


@login_required
def vacancy(request, pk):
    branch = _branch(request, "hiring.view_vacancy")
    v = get_object_or_404(Vacancy.objects.select_related("post", "campus"), branch=branch, pk=pk)
    can = _can(request, branch)
    if request.method == "POST":
        action = request.POST.get("action")
        if not can["move"]:
            raise PermissionDenied
        if action == "shortlist":
            ids = [i for i in request.POST.getlist("candidate") if i.isdigit()]
            added = S.shortlist(v, Candidate.objects.filter(branch=branch, pk__in=ids), request.user)
            messages.success(request, _("%(n)s shortlisted.") % {"n": added}) if added else messages.error(
                request, _("Tick the CVs to shortlist.")
            )
        elif action == "move":
            app = get_object_or_404(Application, vacancy=v, pk=request.POST.get("application") or 0)
            step = StepForm(request.POST, instance=app)
            stage = request.POST.get("stage", "")
            if step.is_valid() and stage in Application.Stage.values and stage != Application.Stage.JOINED:
                d = step.cleaned_data
                S.move(app, stage, request.user, d.get("note") or "", interview_at=d.get("interview_at"),
                       demo_class=d.get("demo_class") or "", salary_offered=d.get("salary_offered"),
                       joining_on=d.get("joining_on"))  # fmt: skip
                messages.success(request, _("%(n)s: %(s)s.") % {"n": app.candidate, "s": app.get_stage_display()})
            else:
                messages.error(request, _("Check the date and time."))
        elif action in ("close", "reopen") and can["vacancy"]:
            v.status = Vacancy.Status.CLOSED if action == "close" else Vacancy.Status.OPEN
            v.save(update_fields=["status", "updated_at"])
        return redirect("hiring:vacancy", v.pk)
    apps = list(v.applications.select_related("candidate").prefetch_related("steps"))
    for a in apps:
        a.sheet_or_none = InterviewSheet.objects.filter(application=a).first() if can["sheet_view"] else None
    board = [(value, label, [a for a in apps if a.stage == value]) for value, label in Application.Stage.choices
             if value in Application.BOARD]  # fmt: skip
    out = [a for a in apps if a.stage not in Application.BOARD]
    return render(
        request,
        "hiring/vacancy.html",
        {
            "v": v,
            "board": board,
            "out": out,
            "matching": list(S.matching(v)[:100]) if v.status == Vacancy.Status.OPEN else [],
            "stages": [(s, label) for s, label in Application.Stage.choices if s != Application.Stage.JOINED],
            "can": can,
        },
    )


@login_required
def sheet(request, application_id):
    """Interview mark sheet (R8-14): 50 marks, who interviewed, remarks, decision."""
    branch = _branch(request, S.SHEET_VIEW_PERM)
    app = get_object_or_404(Application.objects.select_related("candidate", "vacancy__post"), branch=branch,
                            pk=application_id)  # fmt: skip
    current = InterviewSheet.objects.filter(application=app).first()
    can_edit = request.user.has_branch_perm(S.SHEET_PERM, branch.id)
    form = InterviewSheetForm(request.POST or None, instance=current)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        if form.is_valid():
            s = form.save(commit=False)
            s.branch_id, s.application, s.by = branch.id, app, request.user
            s.save()
            decision = {"select": "selected", "reject": "rejected"}.get(s.decision)
            if decision and app.stage != decision and app.is_open:
                S.move(app, decision, request.user, _("Interview: %(t)s / %(o)s") % {"t": s.total, "o": s.OUT_OF})
            messages.success(request, _("Mark sheet saved: %(t)s / %(o)s.") % {"t": s.total, "o": s.OUT_OF})
            return redirect("hiring:vacancy", app.vacancy_id)
    return render(
        request,
        "hiring/sheet.html",
        {"app": app, "form": form, "current": current, "can_edit": can_edit, "marks": MARKS,
         "out_of": InterviewSheet.OUT_OF},
    )  # fmt: skip


@login_required
def interviews(request):
    branch = _branch(request, "hiring.view_application")
    today = timezone.localdate()
    start = timezone.make_aware(dt.datetime.combine(today, dt.time.min))
    rows = (
        Application.objects.filter(branch=branch, interview_at__gte=start, stage__in=Application.OPEN_STAGES)
        .select_related("candidate", "vacancy__post")
        .order_by("interview_at")
    )
    return render(request, "hiring/interviews.html", {"rows": rows, "today": today})


@login_required
def report(request):
    branch = _branch(request)
    today = timezone.localdate()
    since = (today.replace(day=1) - dt.timedelta(days=150)).replace(day=1)
    cvs = CandidateCV.objects.filter(branch=branch, received_on__gte=since)
    months = Counter((cv.received_on.year, cv.received_on.month) for cv in cvs.only("received_on"))
    month_rows = []
    d = since
    while d <= today:
        month_rows.append((d, months.get((d.year, d.month), 0)))
        d = (d.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    by_channel = cvs.values("channel").annotate(n=Count("id")).order_by("-n")
    channel_names = dict(CandidateCV.Channel.choices)
    filled = Vacancy.objects.filter(branch=branch, status=Vacancy.Status.FILLED, filled_on__isnull=False)
    days = [(v.filled_on - v.created_at.date()).days for v in filled]
    return render(
        request,
        "hiring/report.html",
        {
            "month_rows": month_rows,
            "most": max([n for _d, n in month_rows] or [1]) or 1,
            "by_channel": [(channel_names.get(r["channel"], r["channel"]), r["n"]) for r in by_channel],
            "open": Vacancy.objects.filter(branch=branch, status=Vacancy.Status.OPEN).select_related("post"),
            "bank": Candidate.objects.filter(branch=branch, binned_at__isnull=True).count(),
            "relevant": Candidate.objects.filter(branch=branch, binned_at__isnull=True, relevance="relevant").count(),
            "hired": Candidate.objects.filter(branch=branch, status=Candidate.Status.HIRED).count(),
            "days_to_fill": round(sum(days) / len(days)) if days else None,
            "since": since,
        },
    )


@login_required
def bin_view(request):
    branch = _branch(request)
    can = _can(request, branch)
    if request.method == "POST":
        if not can["bin"]:
            raise PermissionDenied
        c = get_object_or_404(Candidate, branch=branch, pk=request.POST.get("candidate") or 0, binned_at__isnull=False)
        if request.POST.get("action") == "restore":
            c.binned_at = None
            c.save(update_fields=["binned_at", "updated_at"])
            messages.success(request, _("%(n)s taken out of the Bin.") % {"n": c.full_name})
        elif request.POST.get("action") == "delete":
            name = c.full_name
            S.delete_candidate(c)
            messages.success(request, _("%(n)s deleted.") % {"n": name})
        return redirect("hiring:bin")
    rows = Candidate.objects.filter(branch=branch, binned_at__isnull=False).select_related("post")
    for c in rows:
        c.goes_on = (c.binned_at + dt.timedelta(days=30)).date()
    return render(request, "hiring/bin.html", {"rows": rows, "can": can})


@login_required
def posts(request):
    """Setup → Hiring posts: the list of posts people apply for (one list for the network)."""
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm("hiring.view_post", branch.id):
        raise PermissionDenied
    can_edit = request.user.is_superuser or request.user.has_branch_perm(S.POST_PERM, branch.id)
    form = PostForm(request.POST or None)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        if request.POST.get("action") == "toggle":
            p = get_object_or_404(Post, pk=request.POST.get("post") or 0)
            p.is_active = not p.is_active
            p.save(update_fields=["is_active", "updated_at"])
        elif form.is_valid():
            form.save()
            messages.success(request, _("Post added."))
        else:
            messages.error(request, _("Give the post a name that is not in the list yet."))
        return redirect("hiring:posts")
    return render(request, "hiring/posts.html", {"rows": Post.objects.all(), "form": form, "can_edit": can_edit})


def staff_link(candidate):
    return f"{reverse('hr:employee_new')}?candidate={candidate.pk}"
