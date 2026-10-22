"""Parent portal: sign-in, first-time set-up with a school code, and each child's diary,
attendance, fees and published results. Also the staff screens that print access codes."""

import calendar
import datetime as dt
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.academics.models import Section
from apps.accounts.throttle import is_locked
from apps.attendance.models import AttendanceRecord
from apps.core.branch import current_branch
from apps.core.models import AuditEvent
from apps.diary.models import Diary
from apps.exams.models import Exam
from apps.organisation.models import AcademicSession
from apps.people.models import Enrolment, Student

from . import services as S
from .forms import ChangePasswordForm, ParentLoginForm, StartForm
from .models import ParentAccount

BACKEND = "apps.accounts.backends.RoleBackend"


def parent_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        account = S.account_for(request.user)
        if account is None:
            return redirect(f"/parents/login/?next={request.path}")
        request.parent = account
        return view(request, *args, **kwargs)

    return wrapper


def _failed(request, label):
    AuditEvent.objects.create(
        action=AuditEvent.Action.LOGIN_FAILED,
        model_label="parents.ParentAccount",
        object_repr=label[:255],
        ip_address=request.META.get("REMOTE_ADDR"),
    )


@never_cache
def login_view(request):
    if S.account_for(request.user):
        return redirect("parents:home")
    form = ParentLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        username = f"parent-{phone}"
        if is_locked(username, request.META.get("REMOTE_ADDR")):
            form.add_error(None, _("Too many failed attempts. Please wait 15 minutes and try again."))
        else:
            user = authenticate(request, username=username, password=form.cleaned_data["password"])
            if user is None or not ParentAccount.objects.filter(user=user).exists():
                form.add_error(None, _("Mobile number or password is not correct."))
            else:
                login(request, user, backend=BACKEND)
                response = redirect("parents:home")
                response.set_cookie(settings.LANGUAGE_COOKIE_NAME, translation.get_language(), samesite="Lax")
                return response
    return render(request, "parents/login.html", {"form": form})


@never_cache
def start_view(request):
    """First time (or forgotten password): mobile number + the school's code + a new password."""
    form = StartForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        label = f"parent-code:{phone}"
        if is_locked(label, request.META.get("REMOTE_ADDR")):
            form.add_error(None, _("Too many failed attempts. Please wait 15 minutes and try again."))
        else:
            code = S.check_code(phone, form.cleaned_data["code"])
            if code is None:
                _failed(request, label)
                form.add_error(
                    "code", _("This code is not correct or has expired. Ask the school office for a new one.")
                )
            else:
                account = S.redeem(code, form.cleaned_data["password1"])
                logout(request)
                login(request, account.user, backend=BACKEND)
                messages.success(request, _("Your password is set. Welcome!"))
                return redirect("parents:home")
    return render(request, "parents/start.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("parents:login")


def _child(request, student_id):
    child = S.children(request.parent.phone).filter(pk=student_id).first()
    if child is None:
        raise Http404
    return child


def _current(child):
    session = AcademicSession.objects.filter(is_current=True).first()
    enrolment = (
        Enrolment.objects.filter(student=child, session=session)
        .select_related("section", "section__class_level")
        .first()
        if session
        else None
    )
    return session, enrolment


@parent_required
def home(request):
    today = timezone.localdate()
    cards = []
    for child in S.children(request.parent.phone):
        session, enrolment = _current(child)
        today_mark = AttendanceRecord.objects.filter(student=child, date=today).first()
        diary = (
            Diary.objects.filter(
                section=enrolment.section, status=Diary.Status.PUBLISHED, date__lte=today + dt.timedelta(days=1)
            )
            .order_by("-date")
            .first()
            if enrolment
            else None
        )
        from apps.fees.services import balance

        cards.append(
            {
                "child": child,
                "enrolment": enrolment,
                "today": today_mark,
                "diary": diary,
                "balance": balance(child),
            }
        )
    from apps.notices import services as N

    notices = list(N.parent_notices(S.children(request.parent.phone), today)[:5])
    return render(
        request,
        "parents/home.html",
        {"cards": cards, "today": today, "notices": notices, "unread": N.unread_ids(notices, request.user)},
    )


def _parent_notice(request, notice_id):
    from apps.notices import services as N

    notice = N.parent_notices(S.children(request.parent.phone), timezone.localdate()).filter(pk=notice_id).first()
    if notice is None:
        raise Http404
    return notice


@parent_required
def notices(request):
    from apps.notices import services as N

    items = list(N.parent_notices(S.children(request.parent.phone), timezone.localdate())[:50])
    return render(request, "parents/notices.html", {"notices": items, "unread": N.unread_ids(items, request.user)})


@parent_required
def notice(request, notice_id):
    from apps.notices import services as N

    item = _parent_notice(request, notice_id)
    N.mark_read(item, request.user)
    return render(request, "parents/notice.html", {"notice": item})


@parent_required
def notice_file(request, notice_id):
    from pathlib import Path

    from django.http import FileResponse

    item = _parent_notice(request, notice_id)
    if not item.attachment:
        raise Http404
    return FileResponse(item.attachment.open("rb"), filename=f"{item.title}{Path(item.attachment.name).suffix}")


@parent_required
def child(request, student_id):
    st = _child(request, student_id)
    session, enrolment = _current(st)
    tab = request.GET.get("tab", "diary")
    is_hifz = st.is_hifz or bool(enrolment and enrolment.section.class_level.code == "hifz")
    context = {"child": st, "enrolment": enrolment, "tab": tab, "is_hifz": is_hifz}
    today = timezone.localdate()
    if tab == "attendance":
        try:
            y, m = (int(x) for x in request.GET.get("month", "").split("-"))
            first = dt.date(y, m, 1)
        except ValueError:
            first = today.replace(day=1)
        last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
        records = AttendanceRecord.objects.filter(student=st, date__gte=first, date__lte=last).order_by("date")
        counts = dict(records.values_list("status").annotate(n=Count("id")))
        total = sum(counts.values())
        attended = counts.get("present", 0) + counts.get("late", 0)
        context.update(
            month=first,
            records=records,
            counts=counts,
            percent=round(attended * 100 / total) if total else None,
            previous=(first - dt.timedelta(days=1)).replace(day=1),
            next=(last + dt.timedelta(days=1)) if last < today else None,
        )
    elif tab == "fees":
        from apps.fees.models import Voucher
        from apps.fees.services import balance

        context.update(
            balance=balance(st),
            vouchers=st.vouchers.exclude(status=Voucher.Status.CANCELLED).order_by("-pk")[:12],
            payments=st.fee_payments.filter(is_reversed=False).order_by("-paid_on", "-pk")[:12],
        )
    elif tab == "results":
        context["exams"] = _published_exams(st, session)
    elif tab == "hifz" and context["is_hifz"]:
        from apps.hifz import services as hifz
        from apps.hifz.models import PARAS

        passed = hifz.passed_paras([st]).get(st.id, {})
        context.update(
            grid=[(n, passed.get(n)) for n in range(1, PARAS + 1)],
            summary=hifz.progress([st], today.replace(day=1), today)[0],
            lessons=st.hifz_lessons.order_by("-date")[:14],
        )
    else:
        sections = Enrolment.objects.filter(student=st).values_list("section_id", flat=True)
        context["diaries"] = Diary.objects.filter(
            section_id__in=sections, status=Diary.Status.PUBLISHED, date__lte=today + dt.timedelta(days=7)
        ).order_by("-date")[:21]
    return render(request, "parents/child.html", context)


def _published_exams(st, session):
    if session is None:
        return []
    return list(
        Exam.objects.filter(session=session, is_published=True, kind__in=[Exam.Kind.MID, Exam.Kind.FINAL])
        .filter(Q(branch__isnull=True) | Q(branch=st.branch))
        .order_by("starts_on", "kind")
    )


@parent_required
def diary(request, student_id, diary_id, kind):
    st = _child(request, student_id)
    sections = Enrolment.objects.filter(student=st).values_list("section_id", flat=True)
    d = Diary.objects.filter(pk=diary_id, section_id__in=sections, status=Diary.Status.PUBLISHED).first()
    if d is None:
        raise Http404
    from apps.diary import services as diary_services

    if kind == "png":
        return HttpResponse(diary_services.render_image(d), content_type="image/png")
    response = HttpResponse(diary_services.render_pdf(d), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Diary-{d.date:%Y-%m-%d}.pdf"'
    return response


@parent_required
def voucher(request, student_id, voucher_id):
    st = _child(request, student_id)
    from apps.fees.models import Voucher
    from apps.fees.views import render_vouchers_pdf

    v = (
        st.vouchers.exclude(status=Voucher.Status.CANCELLED)
        .filter(pk=voucher_id)
        .select_related("student", "section")
        .first()
    )
    if v is None:
        raise Http404
    response = HttpResponse(render_vouchers_pdf(st.branch, [v]), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Voucher-{v.number}.pdf"'
    return response


@parent_required
def result(request, student_id, exam_id):
    st = _child(request, student_id)
    session, enrolment = _current(st)
    exam = next((e for e in _published_exams(st, session) if e.id == exam_id), None)
    if exam is None or enrolment is None:
        raise Http404
    from weasyprint import HTML

    from apps.exams import results as R
    from apps.exams.views import _card_context

    card = "mid" if exam.kind == Exam.Kind.MID else "annual"
    data = R.section_results(enrolment.section, card)
    data["results"] = [r for r in data["results"] if r.student.id == st.id]
    if not data["results"]:
        raise Http404
    html = render_to_string("exams/card_document.html", _card_context(enrolment.section, card, data, for_file=True))
    response = HttpResponse(HTML(string=html).write_pdf(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Result-{card}-{st.admission_no}.pdf"'
    return response


@parent_required
def account(request):
    form = ChangePasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not request.user.check_password(form.cleaned_data["current"]):
            form.add_error("current", _("The current password is not correct."))
        else:
            request.user.set_password(form.cleaned_data["password1"])
            request.user.save()
            update_session_auth_hash(request, request.user)
            messages.success(request, _("Password changed."))
            return redirect("parents:home")
    return render(request, "parents/account.html", {"form": form})


# --- Staff: access codes ---------------------------------------------------------------------


def _staff_branch(request):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(S.ISSUE_PERM, branch.id):
        raise PermissionDenied
    return branch


@login_required
def codes(request):
    """Print parent access slips for one student's family or a whole section."""
    branch = _staff_branch(request)
    session = AcademicSession.objects.filter(is_current=True).first()
    sections = (
        Section.objects.filter(branch=branch, session=session, is_active=True)
        .select_related("class_level")
        .order_by("class_level__sort_order", "name")
        if session
        else []
    )
    if request.method == "POST":
        students = Student.objects.filter(branch=branch, status=Student.Status.ACTIVE)
        if request.POST.get("student"):
            students = students.filter(pk=request.POST["student"])
        elif request.POST.get("section"):
            students = students.filter(
                enrolments__section_id=request.POST["section"], enrolments__section__branch=branch
            )
        else:
            raise Http404
        families = S.primary_phones(students)
        if request.POST.get("only_new"):
            have = set(ParentAccount.objects.filter(phone__in=families).values_list("phone", flat=True))
            families = {p: f for p, f in families.items() if p not in have}
        slips = []
        for phone, family in sorted(families.items(), key=lambda kv: kv[1]["students"][0].first_name):
            slips.append({"phone": phone, "code": S.issue_code(phone, branch, request.user), **family})
        if not slips:
            messages.warning(
                request, _("No families to print: no primary contact mobile, or all already have an account.")
            )
            return redirect("parents:codes")
        return render(
            request,
            "parents/slips.html",
            {"slips": slips, "branch": branch, "days": S.CODE_DAYS, "portal": request.build_absolute_uri("/parents/")},
        )
    accounts = ParentAccount.objects.count()
    return render(request, "parents/codes.html", {"sections": sections, "accounts": accounts})


# --- Installable app (M8): the parent portal works like an app on the phone's home screen -----


def manifest(request):
    from django.http import JsonResponse
    from django.templatetags.static import static

    return JsonResponse(
        {
            "name": "The Arqam Schools — Parents",
            "short_name": "Arqam Parents",
            "start_url": "/parents/",
            "scope": "/parents/",
            "display": "standalone",
            "background_color": "#f4f5fa",
            "theme_color": "#3e4095",
            "icons": [
                {"src": static("img/arqam-logo-192.png"), "sizes": "192x192", "type": "image/png"},
                {"src": static("img/arqam-logo-512.png"), "sizes": "512x512", "type": "image/png"},
            ],
        },
        content_type="application/manifest+json",
    )


def service_worker(request):
    from django.templatetags.static import static

    body = render_to_string(
        "parents/sw.js",
        {"assets": [static("css/tasems.css"), static("img/arqam-logo-192.png"), static("js/parents.js")]},
    )
    response = HttpResponse(body, content_type="application/javascript")
    response["Cache-Control"] = "no-cache"
    return response


def offline(request):
    return render(request, "parents/offline.html")
