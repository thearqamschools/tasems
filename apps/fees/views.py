"""Fee screens for accountants, principals and head office."""

import datetime as dt
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import Section
from apps.core.branch import current_branch
from apps.core.models import AuditEvent
from apps.core.templatetags.tasems_tags import rupees
from apps.diary.models import DiaryLayout
from apps.organisation.models import AcademicSession, Branch
from apps.people.models import Enrolment, Student

from . import exchange, reports
from . import services as S
from .barcode import voucher_barcode
from .forms import ConcessionForm, GenerateForm, IssueForm, MonthField, PaymentForm, ReasonForm
from .models import (
    BranchFeeSettings,
    Charge,
    Concession,
    FeeHead,
    FeeRate,
    Method,
    Payment,
    PaymentChannel,
    Voucher,
    month_start,
)


def _branch(request, perm=S.VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _need(request, branch, perm):
    if not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied


def _session():
    return AcademicSession.objects.filter(is_current=True).first()


def _month(request, key="month"):
    try:
        return MonthField().clean(request.GET.get(key)) if request.GET.get(key) else month_start(timezone.localdate())
    except Exception:  # noqa: BLE001 - a bad value in the address bar just falls back to this month
        return month_start(timezone.localdate())


def _student(branch, student_id):
    student = Student.objects.filter(pk=student_id, branch=branch).first()
    if student is None:
        raise Http404
    return student


def _setup_warnings(branch):
    fee_settings = BranchFeeSettings.for_branch(branch)
    warnings = []
    if not (fee_settings.bank_name and fee_settings.account_number and fee_settings.account_title):
        warnings.append(_("Bank name, account title and account number are not set (Setup → Fee rates and vouchers)."))
    if not FeeRate.objects.filter(branch=branch, head__code="tuition").exists():
        warnings.append(_("No monthly fee is set for this branch (Setup → Fee rates and vouchers)."))
    return warnings


@login_required
def index(request):
    branch = _branch(request)
    q = request.GET.get("q", "").strip()
    if q:
        return find(request, branch, q)
    month = _month(request)
    user = request.user
    return render(
        request,
        "fees/index.html",
        {
            "branch": branch,
            "summary": reports.month_summary(branch, month),
            "month": month,
            "warnings": _setup_warnings(branch),
            "pending": Concession.objects.filter(branch=branch, status=Concession.Status.PENDING).count(),
            "can": {
                "generate": user.has_branch_perm(S.VOUCHER_PERM, branch.id),
                "pay": user.has_branch_perm(S.PAY_PERM, branch.id),
                "approve": user.has_branch_perm(S.APPROVE_PERM, branch.id),
                "royalty": bool(user.accessible_branch_ids(S.ROYALTY_PERM)),
            },
        },
    )


def find(request, branch, q):
    """Voucher number (typed or scanned) → payment screen; admission number or name → student."""
    digits = q.replace(" ", "")
    if digits.isdigit():
        voucher = Voucher.objects.filter(branch=branch, number=int(digits)).first()
        if voucher:
            return redirect("fees:receive", voucher_id=voucher.id)
    student = Student.objects.filter(branch=branch, admission_no__iexact=q).first()
    if student:
        return redirect("fees:student", student_id=student.id)
    matches = list(
        Student.objects.filter(branch=branch)
        .filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(father_name__icontains=q))
        .order_by("first_name")[:30]
    )
    if len(matches) == 1:
        return redirect("fees:student", student_id=matches[0].id)
    if not matches:
        messages.error(request, _("No voucher or student found for “%(q)s”.") % {"q": q})
        return redirect("fees:index")
    return render(request, "fees/find.html", {"q": q, "matches": matches})


# --- Vouchers --------------------------------------------------------------------------------


@login_required
def generate(request):
    branch = _branch(request, S.VOUCHER_PERM)
    session = _session()
    if session is None:
        messages.error(request, _("No current academic session is set."))
        return redirect("fees:index")
    this_month = month_start(timezone.localdate())
    initial = {
        "first_month": this_month,
        "last_month": this_month,
        "due_on": S.default_due_date(branch, this_month),
    }
    form = GenerateForm(request.POST or None, branch=branch, session=session, initial=initial)
    preview = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        section_ids = [s.id for s in d["sections"]] or None
        if "confirm" in request.POST:
            result = S.generate_vouchers(
                branch, session, d["first_month"], d["last_month"], d["due_on"], request.user, section_ids
            )
            created = result["created"]
            if created:
                messages.success(
                    request,
                    _("%(n)s vouchers made (numbers %(a)s to %(b)s). %(s)s students already had one.")
                    % {"n": len(created), "a": created[0].number, "b": created[-1].number, "s": result["skipped"]},
                )
            else:
                messages.warning(request, _("No new vouchers: every student already has one for these months."))
            return redirect(
                f"{_url('fees:vouchers')}?month={d['first_month']:%Y-%m}"
                + "".join(f"&section={i}" for i in section_ids or [])
            )
        enrolments = list(S.enrolled_students(branch, session, section_ids))
        months = S.months_between(d["first_month"], d["last_month"])
        done = S.covered([e.student_id for e in enrolments], months)
        unplaced = (
            Student.objects.filter(branch=branch, status=Student.Status.ACTIVE)
            .exclude(enrolments__session=session)
            .count()
        )
        preview = {
            "total": len(enrolments),
            "new": len(enrolments) - len(done),
            "done": len(done),
            "unplaced": unplaced,
        }
    return render(
        request,
        "fees/generate.html",
        {"form": form, "preview": preview, "warnings": _setup_warnings(branch)},
    )


def _url(name, *args):
    from django.urls import reverse

    return reverse(name, args=args)


def _filtered_vouchers(request, branch):
    month = _month(request)
    qs = (
        Voucher.objects.filter(branch=branch, first_month__lte=month, last_month__gte=month)
        .select_related("student", "section", "section__class_level")
        .order_by("section__class_level__sort_order", "section__name", "student__first_name", "number")
    )
    section_ids = [int(s) for s in request.GET.getlist("section") if s.isdigit()]
    if section_ids:
        qs = qs.filter(section_id__in=section_ids)
    status = request.GET.get("status")
    if status in Voucher.Status.values:
        qs = qs.filter(status=status)
    else:
        qs = qs.exclude(status=Voucher.Status.CANCELLED)
    return qs, month, section_ids, status


@login_required
def vouchers(request):
    branch = _branch(request)
    qs, month, section_ids, status = _filtered_vouchers(request, branch)
    page = Paginator(qs, 100).get_page(request.GET.get("page"))
    session = _session()
    sections = (
        Section.objects.filter(branch=branch, session=session)
        .select_related("class_level")
        .order_by("class_level__sort_order", "name")
        if session
        else []
    )
    return render(
        request,
        "fees/vouchers.html",
        {
            "page": page,
            "month": month,
            "sections": sections,
            "section_ids": section_ids,
            "status": status,
            "statuses": Voucher.Status.choices,
            "query": request.GET.urlencode(),
            "can_pay": request.user.has_branch_perm(S.PAY_PERM, branch.id),
        },
    )


COPIES = ("SCHOOL COPY", "BANK COPY", "STUDENT COPY")  # the printed voucher is always in English
PLACEHOLDERS = {
    "{bank_name}": "bank_name",
    "{account_title}": "account_title",
    "{account_number}": "account_number",
    "{whatsapp}": "receipt_whatsapp",
}


def _instruction(text, fee_settings, rtl):
    """One printed instruction line as safe HTML: **bold** words, and the branch's details filled in.
    In Urdu lines, numbers are kept left-to-right so 0339-2406479 does not print reversed."""
    import re

    from django.utils.html import escape
    from django.utils.safestring import mark_safe

    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escape(text))
    for token, attr in PLACEHOLDERS.items():
        value = escape(getattr(fee_settings, attr))
        html = html.replace(token, f'<span class="ltr">{value}</span>' if rtl else value)
    return mark_safe(html)


def _voucher_context(branch, voucher_list, for_file=True):
    heads = reports.columns()
    fee_settings = BranchFeeSettings.for_branch(branch)
    channels = PaymentChannel.for_branch(branch)
    for c in channels:
        c.title_filled = fee_settings.fill(c.title)
        c.steps_en_list = [_instruction(x, fee_settings, rtl=False) for x in c.steps_en.splitlines() if x.strip()]
        c.steps_ur_list = [_instruction(x, fee_settings, rtl=True) for x in c.steps_ur.splitlines() if x.strip()]
        c.shows_bank = c.method in ("bank_branch", "bank_transfer")
    from apps.people.models import StudentGuardian

    links = {
        link.student_id: link.guardian
        for link in StudentGuardian.objects.filter(
            student_id__in=[v.student_id for v in voucher_list], is_primary_contact=True
        ).select_related("guardian")
    }
    items = []
    for v in voucher_list:
        guardian = links.get(v.student_id)
        items.append(
            {
                "v": v,
                "table": reports.voucher_table(v, heads),
                "barcode": voucher_barcode(v.number),
                "father": v.student.father_name or (guardian.full_name if guardian else ""),
            }
        )
    return {
        "items": items,
        "heads": heads,
        "branch": branch,
        "fs": fee_settings,
        "channels": channels,
        "back_notes_ur": [x for x in fee_settings.back_notes_ur.splitlines() if x.strip()],
        "back_notes_en": [x for x in fee_settings.back_notes_en.splitlines() if x.strip()],
        "copies": COPIES,
        "layout": DiaryLayout.current(),
        "font_base": f"file://{settings.BASE_DIR}/static/fonts/" if for_file else f"{settings.STATIC_URL}fonts/",
        "media_base": f"file://{settings.MEDIA_ROOT}/" if for_file else settings.MEDIA_URL,
    }


def render_vouchers_pdf(branch, voucher_list):
    from weasyprint import HTML

    html = render_to_string("fees/voucher_document.html", _voucher_context(branch, voucher_list))
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


def _pdf_response(pdf, name):
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{name}.pdf"'
    return response


MAX_PRINT = 600


@login_required
def vouchers_pdf(request):
    branch = _branch(request)
    qs, month, _sections, _status = _filtered_vouchers(request, branch)
    voucher_list = list(qs.select_related("student")[: MAX_PRINT + 1])
    if not voucher_list:
        raise Http404
    if len(voucher_list) > MAX_PRINT:
        messages.error(
            request, _("Too many vouchers to print at once (%(n)s at most). Choose a class.") % {"n": MAX_PRINT}
        )
        return redirect(f"{_url('fees:vouchers')}?{request.GET.urlencode()}")
    return _pdf_response(render_vouchers_pdf(branch, voucher_list), f"Vouchers-{month:%Y-%m}")


def _voucher(branch, voucher_id):
    voucher = Voucher.objects.filter(pk=voucher_id, branch=branch).select_related("student", "section").first()
    if voucher is None:
        raise Http404
    return voucher


@login_required
def voucher_pdf(request, voucher_id):
    branch = _branch(request)
    voucher = _voucher(branch, voucher_id)
    return _pdf_response(render_vouchers_pdf(branch, [voucher]), f"Voucher-{voucher.number}")


@login_required
@require_POST
def cancel_voucher(request, voucher_id):
    branch = _branch(request, S.CANCEL_PERM)
    voucher = _voucher(branch, voucher_id)
    form = ReasonForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Write why the voucher is being cancelled."))
    else:
        try:
            S.cancel_voucher(voucher, request.user, form.cleaned_data["reason"])
            messages.success(request, _("Voucher %(n)s cancelled.") % {"n": voucher.number})
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("fees:student", student_id=voucher.student_id)


# --- Student account -------------------------------------------------------------------------


@login_required
def student(request, student_id):
    branch = _branch(request)
    st = _student(branch, student_id)
    user = request.user
    session = _session()
    enrolment = Enrolment.objects.filter(student=st, session=session).select_related("section").first()
    siblings = (
        Student.objects.filter(branch=branch, father_cnic=st.father_cnic, status=Student.Status.ACTIVE)
        .exclude(pk=st.pk)
        .order_by("admission_date", "pk")
        if st.father_cnic
        else []
    )
    return render(
        request,
        "fees/student.html",
        {
            "student": st,
            "enrolment": enrolment,
            "balance": S.balance(st),
            "unpaid": S.unpaid_charges(st),
            "vouchers": st.vouchers.order_by("-pk")[:24],
            "payments": st.fee_payments.select_related("received_by", "voucher").order_by("-paid_on", "-pk")[:24],
            "charges": Charge.objects.filter(student=st)
            .select_related("head")
            .order_by("-month", "head__sort_order")[:60],
            "concessions": st.concessions.select_related("head").order_by("-created_at"),
            "siblings": siblings,
            "pays_full": not S.is_sibling(st, S.first_children(branch)) if st.father_cnic else True,
            "can": {
                "issue": user.has_branch_perm(S.VOUCHER_PERM, branch.id),
                "pay": user.has_branch_perm(S.PAY_PERM, branch.id),
                "reverse": user.has_branch_perm(S.REVERSE_PERM, branch.id),
                "cancel": user.has_branch_perm(S.CANCEL_PERM, branch.id),
                "cancel_charge": user.has_branch_perm(S.CANCEL_CHARGE_PERM, branch.id),
                "concession": user.has_branch_perm(S.CONCESSION_PERM, branch.id),
            },
        },
    )


@login_required
def issue(request, student_id):
    branch = _branch(request, S.VOUCHER_PERM)
    st = _student(branch, student_id)
    session = _session()
    enrolment = (
        Enrolment.objects.filter(student=st, session=session).select_related("section").first() if session else None
    )
    if session is None or enrolment is None:
        messages.error(request, _("Place the student in a class for this session first."))
        return redirect("fees:student", student_id=st.id)
    level_id = enrolment.section.class_level_id
    this_month = month_start(timezone.localdate())
    one_time = [
        (h, S.one_time_price(st, h, level_id, this_month))
        for h in FeeHead.objects.filter(is_active=True, kind__in=[FeeHead.Kind.ONE_TIME, FeeHead.Kind.YEARLY])
    ]
    first_voucher = not st.vouchers.exclude(status=Voucher.Status.CANCELLED).exists()
    initial = {"first_month": this_month, "last_month": this_month, "due_on": S.default_due_date(branch, this_month)}
    for head, _amount in one_time:
        # A new student's first voucher usually carries admission and registration.
        initial[f"h_{head.code}"] = first_voucher and head.code in ("admission", "registration")
    form = IssueForm(request.POST or None, branch=branch, session=session, one_time=one_time, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        if not request.user.has_branch_perm(S.CHARGE_PERM, branch.id):
            raise PermissionDenied
        extras = []
        for head, _amount in one_time:
            if d.get(f"h_{head.code}") and d.get(f"a_{head.code}"):
                extras.append((head, d[f"a_{head.code}"], 0, "", d["first_month"], ""))
        if d.get("other_head"):
            extras.append((d["other_head"], d["other_amount"], 0, "", d["first_month"], d.get("other_note", "")))
        months = S.months_between(d["first_month"], d["last_month"])
        if S.covered([st.id], months) and not extras:
            messages.error(request, _("This student already has a voucher for these months."))
        else:
            voucher = S.issue_voucher(st, session, d["first_month"], d["last_month"], d["due_on"], request.user, extras)
            messages.success(request, _("Voucher %(n)s made.") % {"n": voucher.number})
            return redirect("fees:student", student_id=st.id)
    pairs = [(form[f"h_{h.code}"], form[f"a_{h.code}"]) for h, _amount in one_time]
    return render(request, "fees/issue.html", {"form": form, "student": st, "pairs": pairs})


@login_required
@require_POST
def cancel_charge(request, charge_id):
    branch = _branch(request, S.CANCEL_CHARGE_PERM)
    charge = Charge.objects.filter(pk=charge_id, branch=branch, is_cancelled=False).first()
    if charge is None:
        raise Http404
    form = ReasonForm(request.POST)
    if form.is_valid():
        S.cancel_charge(charge, request.user, form.cleaned_data["reason"])
        messages.success(request, _("Charge cancelled."))
    else:
        messages.error(request, _("Write why the charge is being cancelled."))
    return redirect("fees:student", student_id=charge.student_id)


# --- Payments --------------------------------------------------------------------------------


@login_required
def receive(request, voucher_id):
    branch = _branch(request, S.PAY_PERM)
    voucher = _voucher(branch, voucher_id)
    st = voucher.student
    fee_settings = BranchFeeSettings.for_branch(branch)
    due, fine = S.amount_due_now(voucher)
    today = timezone.localdate()
    form = PaymentForm(
        request.POST or None,
        initial={"amount": due if due > 0 else None, "paid_on": today, "method": "counter"},
        full_amount=due,
        allow_partial=fee_settings.allow_partial_payment,
    )
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        payment = S.record_payment(
            st,
            d["amount"],
            d["paid_on"],
            d["method"],
            request.user,
            voucher=voucher,
            reference=d["reference"],
            note=d["note"],
        )
        messages.success(
            request, _("Rs %(a)s received. Receipt %(r)s.") % {"a": rupees(d["amount"]), "r": payment.receipt_no}
        )
        return redirect("fees:receipt", payment_id=payment.id)
    newer = (
        Voucher.objects.filter(student=st, pk__gt=voucher.pk)
        .exclude(status=Voucher.Status.CANCELLED)
        .order_by("-pk")
        .first()
    )
    return render(
        request,
        "fees/receive.html",
        {
            "form": form,
            "voucher": voucher,
            "student": st,
            "due": due,
            "fine": fine,
            "balance": S.balance(st),
            "unpaid": S.unpaid_charges(st),
            "newer": newer,
        },
    )


@login_required
def receipt(request, payment_id):
    branch = _branch(request)
    payment = (
        Payment.objects.filter(pk=payment_id, branch=branch).select_related("student", "voucher", "received_by").first()
    )
    if payment is None:
        raise Http404
    return render(
        request,
        "fees/receipt.html",
        {
            "payment": payment,
            "balance": S.balance(payment.student),
            "paid_for": payment.allocations.select_related("charge__head").order_by("charge__month"),
            "branch": branch,
            "can_reverse": request.user.has_branch_perm(S.REVERSE_PERM, branch.id),
        },
    )


@login_required
@require_POST
def reverse_payment(request, payment_id):
    branch = _branch(request, S.REVERSE_PERM)
    payment = Payment.objects.filter(pk=payment_id, branch=branch).first()
    if payment is None:
        raise Http404
    form = ReasonForm(request.POST)
    if form.is_valid():
        S.reverse_payment(payment, request.user, form.cleaned_data["reason"])
        messages.success(request, _("Receipt %(r)s reversed.") % {"r": payment.receipt_no})
    else:
        messages.error(request, _("Write why the payment is being reversed."))
    return redirect("fees:student", student_id=payment.student_id)


# --- Special discounts -----------------------------------------------------------------------


@login_required
def concession_new(request, student_id):
    branch = _branch(request, S.CONCESSION_PERM)
    st = _student(branch, student_id)
    instance = Concession(branch=branch, student=st, requested_by=request.user)
    form = ConcessionForm(
        request.POST or None, instance=instance, initial={"starts_on": month_start(timezone.localdate())}
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Discount request saved. It applies once the principal or a director approves it."))
        return redirect("fees:student", student_id=st.id)
    return render(request, "fees/concession_form.html", {"form": form, "student": st})


@login_required
def concessions(request):
    branch = _branch(request)
    can_decide = request.user.has_branch_perm(S.APPROVE_PERM, branch.id)
    if request.method == "POST":
        if not can_decide:
            raise PermissionDenied
        c = Concession.objects.filter(
            pk=request.POST.get("id"), branch=branch, status=Concession.Status.PENDING
        ).first()
        if c is None:
            raise Http404
        if c.requested_by_id == request.user.id and not request.user.is_superuser:
            messages.error(request, _("Someone else must approve a discount you asked for."))
        else:
            S.decide_concession(c, request.user, approve=request.POST.get("decision") == "approve")
            messages.success(request, _("Decision saved."))
        return redirect("fees:concessions")
    qs = Concession.objects.filter(branch=branch).select_related("student", "head", "requested_by", "decided_by")
    return render(
        request,
        "fees/concessions.html",
        {
            "pending": qs.filter(status=Concession.Status.PENDING),
            "decided": qs.exclude(status=Concession.Status.PENDING)[:100],
            "can_decide": can_decide,
        },
    )


# --- Reports ---------------------------------------------------------------------------------


@login_required
def defaulters(request):
    branch = _branch(request)
    session = _session()
    try:
        min_months = max(1, int(request.GET.get("months", "1")))
    except ValueError:
        min_months = 1
    rows = [
        r for r in reports.outstanding(branch, as_of=month_start(timezone.localdate())) if r["months"] >= min_months
    ]
    students = {s.id: s for s in Student.objects.filter(id__in=[r["student_id"] for r in rows])}
    sections = (
        dict(
            Enrolment.objects.filter(student_id__in=students, session=session)
            .select_related("section", "section__class_level")
            .values_list("student_id", "section_id")
        )
        if session
        else {}
    )
    section_names = {
        s.id: s for s in Section.objects.filter(id__in=set(sections.values())).select_related("class_level")
    }
    phones = reports.guardian_phones(list(students))
    section_filter = request.GET.get("section")
    out = []
    for r in rows:
        sec = section_names.get(sections.get(r["student_id"]))
        if section_filter and str(getattr(sec, "id", "")) != section_filter:
            continue
        out.append({**r, "student": students[r["student_id"]], "section": sec, "phone": phones.get(r["student_id"])})
    out.sort(key=lambda r: (-r["months"], -r["due"]))
    return render(
        request,
        "fees/defaulters.html",
        {
            "rows": out,
            "total": sum((r["due"] for r in out), S.ZERO),
            "min_months": min_months,
            "sections": sorted(section_names.values(), key=lambda s: (s.class_level.sort_order, s.name)),
            "section_filter": section_filter,
        },
    )


def _date(value, default):
    try:
        return dt.date.fromisoformat(value) if value else default
    except ValueError:
        return default


@login_required
def collections(request):
    branch = _branch(request)
    today = timezone.localdate()
    date_from = _date(request.GET.get("from"), today)
    date_to = _date(request.GET.get("to"), date_from)
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    if (date_to - date_from).days > 92:
        date_to = date_from + dt.timedelta(days=92)
    return render(
        request,
        "fees/collections.html",
        {"date_from": date_from, "date_to": date_to, **reports.collections(branch, date_from, date_to)},
    )


@login_required
def royalty(request):
    ids = request.user.accessible_branch_ids(S.ROYALTY_PERM)
    if not ids:
        raise PermissionDenied
    month = _month(request)
    branches = list(Branch.objects.filter(id__in=ids, is_active=True).select_related("head_office", "region"))
    branches.sort(key=lambda b: (b.ownership != Branch.Ownership.FRANCHISE, b.head_office.name, b.name))
    rows = reports.royalty(branches, month)
    franchise = [r for r in rows if r.branch.ownership == Branch.Ownership.FRANCHISE]
    return render(
        request,
        "fees/royalty.html",
        {
            "month": month,
            "rows": rows,
            "total_royalty": sum((r.royalty for r in franchise), S.ZERO),
            "total_base": sum((r.collected for r in franchise), S.ZERO),
        },
    )


# --- Files exchanged with JazzCash and banks -------------------------------------------------


@login_required
def jazzcash_export(request):
    """Unpaid vouchers of a month as an Excel file, to give to JazzCash."""
    branch = _branch(request)
    month = _month(request)
    content, count = exchange.export_open_vouchers(branch, month)
    AuditEvent.objects.create(
        actor=request.user,
        action=AuditEvent.Action.UPDATE,
        model_label="fees.Voucher",
        object_id=f"export:{month:%Y-%m}",
        object_repr=f"Voucher list for JazzCash {month:%b %Y} ({count} vouchers)",
        branch_id=branch.id,
        changes={"exported": count},
    )
    response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="Vouchers-{branch.code}-{month:%Y-%m}.xlsx"'
    return response


IMPORT_METHODS = [Method.JAZZCASH, Method.BANK_BRANCH, Method.BANK_TRANSFER, Method.ALFA]


@login_required
def payments_import(request):
    """Step 1: upload the paid list (e.g. from JazzCash) and see every row checked.
    Step 2: record the good rows. Nothing is saved before step 2."""
    from apps.people.views import _import_dir

    branch = _branch(request, S.PAY_PERM)
    today = timezone.localdate()
    methods = [(m.value, m.label) for m in IMPORT_METHODS]
    method = request.POST.get("method") if request.POST.get("method") in dict(methods) else "jazzcash"
    try:
        default_date = dt.date.fromisoformat(request.POST.get("paid_on", "")) if request.POST.get("paid_on") else today
    except ValueError:
        default_date = today
    context = {"methods": methods, "method": method, "paid_on": default_date, "max_rows": exchange.MAX_ROWS}

    def check(content):
        return exchange.read_paid_file(content, branch=branch, method=method, default_date=default_date, today=today)

    if request.method == "POST" and request.POST.get("step") == "check":
        upload = request.FILES.get("file")
        if upload is None or not upload.name.lower().endswith(".xlsx"):
            messages.error(request, _("Choose an Excel file (.xlsx)."))
        elif upload.size > exchange.MAX_BYTES:
            messages.error(request, _("The file is larger than 5 MB. Split it into smaller files."))
        else:
            content = upload.read()
            result = check(content)
            token = ""
            if result.good:
                token = secrets.token_hex(16)
                (_import_dir() / f"{token}.xlsx").write_bytes(content)
                request.session["payments_import"] = {"token": token, "branch": branch.id, "name": upload.name}
            context.update(result=result, token=token, filename=upload.name)

    elif request.method == "POST" and request.POST.get("step") == "import":
        pending = request.session.pop("payments_import", None)
        token = request.POST.get("token", "")
        if not pending or pending["token"] != token or pending["branch"] != branch.id or not token.isalnum():
            messages.error(request, _("This import has expired. Please check the file again."))
            return redirect("fees:payments_import")
        path = _import_dir() / f"{token}.xlsx"
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            messages.error(request, _("This import has expired. Please check the file again."))
            return redirect("fees:payments_import")
        finally:
            path.unlink(missing_ok=True)
        result = check(content)  # checked again: someone may have recorded a payment meanwhile
        payments = exchange.record_paid_rows(
            result.rows, method=method, user=request.user, note=f"Imported from {pending['name']}"
        )
        messages.success(
            request,
            _("%(n)s payments recorded, Rs %(t)s in total. %(s)s rows skipped.")
            % {"n": len(payments), "t": rupees(result.total), "s": len(result.rows) - len(payments)},
        )
        first = min((p.paid_on for p in payments), default=today)
        return redirect(f"{_url('fees:collections')}?from={first:%Y-%m-%d}&to={today:%Y-%m-%d}")

    return render(request, "fees/payments_import.html", context)
