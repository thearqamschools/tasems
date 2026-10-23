"""Fee screens for accountants, principals and head office."""

import datetime as dt
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import Section
from apps.core import exports
from apps.core.branch import current_branch
from apps.core.models import AuditEvent
from apps.core.templatetags.tasems_tags import rupees
from apps.diary.models import DiaryLayout
from apps.organisation.models import AcademicSession, Branch
from apps.people.models import Enrolment, Student

from . import exchange, family, reports
from . import services as S
from .barcode import voucher_barcode
from .forms import (
    ConcessionForm,
    FamilyReceiveForm,
    GenerateForm,
    IssueForm,
    MonthField,
    PaymentForm,
    QuickReceiveForm,
    ReasonForm,
    RoyaltyPaymentForm,
    VoucherEditForm,
)
from .models import (
    BranchFeeSettings,
    Charge,
    Concession,
    FamilyVoucher,
    FeeHead,
    FeeRate,
    Method,
    Payment,
    PaymentChannel,
    RoyaltyPayment,
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
    day = _date(request.GET.get("day"), timezone.localdate())
    return render(
        request,
        "fees/index.html",
        {
            "branch": branch,
            "day": day,
            "today": timezone.localdate(),
            "day_summary": reports.collections(branch, day, day),
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
        fv = FamilyVoucher.objects.filter(branch=branch, number=int(digits)).first()
        if fv:
            if request.user.has_branch_perm(S.PAY_PERM, branch.id):
                return redirect("fees:family_receive", family_id=fv.id)
            return redirect("fees:family_voucher_pdf", family_id=fv.id)
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
        "due_on": S.default_due_date(branch, this_month),
        # Annual charges are ticked in April and summer vacation in July, as usual; others when needed.
        "heads": [h for h in FeeHead.objects.filter(is_active=True) if this_month.month in (h.charge_months or [])],
    }
    form = GenerateForm(request.POST or None, branch=branch, session=session, initial=initial)
    preview = None
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        section_ids = d["section_ids"]
        chosen = {h.id for h in d["heads"]}
        if "confirm" in request.POST:
            result = S.generate_vouchers(
                branch,
                session,
                d["first_month"],
                d["last_month"],
                d["due_on"],
                request.user,
                section_ids,
                chosen,
                d["gender"],
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
        enrolments = list(S.enrolled_students(branch, session, section_ids, d["gender"]))
        months = S.months_between(d["first_month"], d["last_month"])
        done = S.covered([e.student_id for e in enrolments], months)
        unplaced = (
            Student.objects.filter(branch=branch, status=Student.Status.ACTIVE)
            .exclude(enrolments__session=session)
            .count()
        )
        book = S.RateBook(branch)
        preview = {
            "total": len(enrolments),
            "new": len(enrolments) - len(done),
            "done": len(done),
            "unplaced": unplaced,
            # Ticked fees this branch has no amount for: nothing would be added.
            "no_rate": [h for h in d["heads"] if not book.has_any(h)],
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
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Vouchers") + f" {month:%b %Y}",
            [_("Voucher ID"), _("Admission no."), _("Student"), _("Father name"), _("Class"), _("From month"),
             _("Until month"), _("Due date"), _("Payable (Rs)"), _("Status")],
            (
                [v.number, v.student.admission_no, v.student.full_name, v.student.father_name,
                 str(v.section or ""), v.first_month, v.last_month, v.due_on, v.payable, v.get_status_display()]
                for v in qs
            ),
            branch=branch,
        )  # fmt: skip
    page = exports.paginate(request, qs, 100)
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
            "can_generate": request.user.has_branch_perm(S.VOUCHER_PERM, branch.id),
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


MAX_PRINT = 100  # more than this is made in the background (Reports → print jobs), so the page never times out


def _queue_print(request, branch, kind, title, params):
    from apps.jobs.models import Job

    job = Job.objects.create(branch=branch, kind=kind, title=title, params=params, requested_by=request.user)
    return redirect("jobs:detail", job_id=job.id)


@login_required
def vouchers_pdf(request):
    branch = _branch(request)
    qs, month, _sections, _status = _filtered_vouchers(request, branch)
    voucher_list = list(qs.select_related("student")[: MAX_PRINT + 1])
    if not voucher_list:
        raise Http404
    if len(voucher_list) > MAX_PRINT:
        count = qs.count()
        return _queue_print(
            request,
            branch,
            "vouchers",
            _("%(n)s vouchers, %(m)s") % {"n": count, "m": f"{month:%B %Y}"},
            {"query": request.GET.urlencode()},
        )
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
        request.FILES or None,
        initial={"amount": due if due > 0 else None, "paid_on": today, "how": PaymentForm.CASH},
        branch=branch,
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
            bank=d["bank"],
            attachment=d["attachment"],
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
            "edit_form": None if newer or voucher.status == Voucher.Status.CANCELLED else _edit_form(voucher),
            "locked": voucher.charges.filter(is_cancelled=False, head__kind__in=S.LOCKED_KINDS).select_related("head"),
            "voucher": voucher,
            "student": st,
            "due": due,
            "fine": fine,
            "balance": S.balance(st),
            "unpaid": S.unpaid_charges(st),
            "newer": newer,
        },
    )


def _edit_form(voucher, data=None):
    charges = list(
        voucher.charges.filter(is_cancelled=False)
        .exclude(head__kind__in=S.LOCKED_KINDS)
        .exclude(source=Charge.Source.FINE)
        .select_related("head")
    )
    return VoucherEditForm(data, charges=charges, heads=S.editable_heads())


@login_required
@require_POST
def edit_voucher(request, voucher_id):
    """Receive page: the receiver changes the other fees on the voucher; the Voucher ID stays the same."""
    branch = _branch(request, S.PAY_PERM)
    voucher = _voucher(branch, voucher_id)
    form = _edit_form(voucher, request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            changed = S.edit_voucher(voucher, d["amounts"], d["additions"], request.user, note=d["note"])
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            if changed:
                messages.success(
                    request, _("Voucher %(n)s changed. Its Voucher ID stays the same.") % {"n": voucher.number}
                )
            else:
                messages.info(request, _("Nothing was changed."))
    else:
        messages.error(request, _("The voucher was not changed: check the amounts."))
    return redirect("fees:receive", voucher_id=voucher.id)


@login_required
def receipt(request, payment_id):
    branch = _branch(request)
    payment = (
        Payment.objects.filter(pk=payment_id, branch=branch)
        .select_related("student", "voucher", "bank", "received_by__employee")
        .first()
    )
    if payment is None:
        raise Http404
    return render(
        request,
        "fees/receipt.html",
        {
            "payment": payment,
            "receiver": reports.receiver_label(payment.received_by),
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
    branch = _branch(request, S.DEFAULTERS_PERM)
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
    by_family = request.GET.get("by") == "family"
    families = []
    if by_family:
        # One row per family: brothers and sisters share the father's CNIC (students without one stand alone).
        grouped = {}
        for r in out:
            key = r["student"].father_cnic or f"student-{r['student'].id}"
            family = grouped.setdefault(
                key, {"father": r["student"].father_name, "phone": r["phone"], "children": [], "due": S.ZERO}
            )
            family["children"].append(r)
            family["due"] += r["due"]
            family["phone"] = family["phone"] or r["phone"]
        families = sorted(grouped.values(), key=lambda f: -f["due"])
    if exports.wants_xlsx(request):
        if by_family:
            return exports.xlsx_response(
                _("Defaulters by family"),
                [_("Father"), _("Parent mobile"), _("Children"), _("Owed (Rs)")],
                (
                    [f["father"], f["phone"],
                     ", ".join(f"{r['student'].full_name} ({r['section'] or ''})" for r in f["children"]), f["due"]]
                    for f in families
                ),
                branch=branch,
            )  # fmt: skip
        return exports.xlsx_response(
            _("Defaulters"),
            [_("Admission no."), _("Student"), _("Father name"), _("Class"), _("Parent mobile"), _("Months unpaid"),
             _("Since"), _("Owed (Rs)")],
            (
                [r["student"].admission_no, r["student"].full_name, r["student"].father_name, str(r["section"] or ""),
                 r["phone"], r["months"], r["oldest"], r["due"]]
                for r in out
            ),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "fees/defaulters.html",
        {
            "by_family": by_family,
            "families": families,
            "rows": out,
            "total": sum((r["due"] for r in out), S.ZERO),
            "min_months": min_months,
            "sections": sorted(section_names.values(), key=lambda s: (s.class_level.sort_order, s.name)),
            "section_filter": section_filter,
            "can_fees": request.user.has_branch_perm(S.VIEW_PERM, branch.id),
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
    summary = reports.collections(branch, date_from, date_to)
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Fee collection")
            + f" {date_from:%d-%m-%Y}"
            + (f" to {date_to:%d-%m-%Y}" if date_to != date_from else ""),
            [_("Date"), _("Receipt"), _("Voucher ID"), _("Admission no."), _("Student"), _("Father name"),
             _("Received in"), _("Bank"), _("Transaction ID / slip number"), _("Received by"), _("Amount (Rs)"),
             _("Reversed")],
            (
                [p.paid_on, p.receipt_no, p.voucher.number if p.voucher else "", p.student.admission_no,
                 p.student.full_name, p.student.father_name, _("Cash") if p.method == "counter" else p.method_label,
                 p.bank.name if p.bank else "", p.reference, p.receiver, p.amount,
                 _("Yes") if p.is_reversed else ""]
                for p in summary["payments"]
            ),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "fees/collections.html",
        {"date_from": date_from, "date_to": date_to, "summary": summary, "payments": summary["payments"]},
    )


@login_required
def quick_receive(request):
    """Finance → Barcode: type or scan the Voucher ID, choose the date and Cash/Bank, press Pay.
    The whole amount due on that date is recorded, and the page is ready for the next voucher."""
    branch = _branch(request, S.PAY_PERM)
    today = timezone.localdate()
    form = QuickReceiveForm(
        request.POST or None,
        request.FILES or None,
        initial={"paid_on": today, "how": PaymentForm.CASH},
        branch=branch,
    )
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        digits = d["voucher_number"].replace(" ", "")
        voucher = (
            Voucher.objects.filter(branch=branch, number=int(digits)).select_related("student").first()
            if digits.isdigit()
            else None
        )
        due = S.amount_due_now(voucher, d["paid_on"])[0] if voucher else S.ZERO
        if voucher is None and digits.isdigit():
            fv = FamilyVoucher.objects.filter(branch=branch, number=int(digits)).first()
            if fv is not None:  # a family voucher: show the children and take the whole family's fees there
                return redirect("fees:family_receive", family_id=fv.id)
        if voucher is None:
            form.add_error("voucher_number", _("There is no voucher with this ID in this branch."))
        elif voucher.status == Voucher.Status.CANCELLED:
            form.add_error("voucher_number", _("This voucher was cancelled."))
        elif due <= 0:
            form.add_error("voucher_number", _("Nothing is owed on this voucher: it is already paid."))
        else:
            payment = S.record_payment(
                voucher.student,
                due,
                d["paid_on"],
                d["method"],
                request.user,
                voucher=voucher,
                reference=d["reference"],
                note=d["note"],
                bank=d["bank"],
                attachment=d["attachment"],
            )
            messages.success(
                request,
                _("Voucher %(v)s paid: Rs %(a)s from %(s)s. Receipt %(r)s.")
                % {"v": voucher.number, "a": rupees(due), "s": voucher.student.full_name, "r": payment.receipt_no},
            )
            return redirect("fees:quick")
    mine = [
        p
        for p in reports.collections(branch, today, today)["payments"]
        if p.received_by_id == request.user.id and not p.is_reversed
    ]
    return render(request, "fees/quick.html", {"form": form, "mine": mine[-10:][::-1]})


@login_required
def payment_attachment(request, payment_id):
    """Receipt photos are private: only people who may see this branch's fees can open them."""
    branch = _branch(request)
    payment = Payment.objects.filter(pk=payment_id, branch=branch).first()
    if payment is None or not payment.attachment:
        raise Http404
    return FileResponse(
        payment.attachment.open("rb"), filename=f"Payment {payment.receipt_no}{Path(payment.attachment.name).suffix}"
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
    balances = reports.royalty_balances(branches, month)
    for r in rows:
        r.paid, r.total_due = balances[r.branch.id]["paid"], balances[r.branch.id]["total_due"]
    franchise = [r for r in rows if r.branch.ownership == Branch.Ownership.FRANCHISE]
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Royalty statement") + f" {month:%b %Y}",
            [_("Branch"), _("Ownership"), _("Billed for the month"), _("Received in the month"), "%",
             _("Royalty (Rs)"), _("Paid (Rs)"), _("Pending (Rs)"), _("Total due (Rs)")],
            (
                [r.branch.name, r.branch.get_ownership_display(), r.billed, r.collected, r.percent, r.royalty,
                 r.paid, r.royalty - r.paid, r.total_due]
                for r in rows
            ),
        )  # fmt: skip
    return render(
        request,
        "fees/royalty.html",
        {
            "month": month,
            "rows": rows,
            "total_royalty": sum((r.royalty for r in franchise), S.ZERO),
            "total_base": sum((r.collected for r in franchise), S.ZERO),
            "total_paid": sum((r.paid for r in franchise), S.ZERO),
            "total_due": sum((r.total_due for r in franchise), S.ZERO),
        },
    )


def _royalty_branch(request, branch_id):
    if branch_id not in request.user.accessible_branch_ids(S.ROYALTY_PERM):
        raise Http404
    return Branch.objects.get(pk=branch_id)


@login_required
def royalty_branch(request, branch_id):
    """One branch's royalty month by month (due, paid, left, total due) and the payments head office
    recorded, with the form to record a new one for people allowed to."""
    branch = _royalty_branch(request, branch_id)
    month = _month(request)
    can_record = request.user.has_branch_perm(S.ROYALTY_RECORD_PERM, branch.id)
    form = None
    if can_record:
        form = RoyaltyPaymentForm(
            request.POST or None,
            request.FILES or None,
            initial={"month": month, "paid_on": timezone.localdate()},
            branch=branch,
        )
        if request.method == "POST" and form.is_valid():
            payment = form.save(commit=False)
            payment.received_by = request.user
            payment.save()
            messages.success(
                request,
                _("Royalty of Rs %(a)s recorded for %(m)s.")
                % {"a": rupees(payment.amount), "m": f"{payment.month:%B %Y}"},
            )
            return redirect(f"{reverse('fees:royalty_branch', args=[branch.id])}?month={month:%Y-%m}")
    elif request.method == "POST":
        raise PermissionDenied
    ledger = reports.royalty_ledger(branch, month)
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Royalty"),
            [_("Month"), _("Fees received (Rs)"), _("Royalty (Rs)"), _("Paid (Rs)"), _("Pending (Rs)"),
             _("Total due (Rs)")],
            (
                ([[_("Brought forward from earlier months"), "", "", "", "", ledger["carried"]]]
                 if ledger["carried"] else [])
                + [[f"{r['month']:%b %Y}", r["collected"], r["due"], r["paid"], r["left"], r["total_due"]]
                   for r in ledger["rows"]]
            ),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "fees/royalty_branch.html",
        {
            "branch": branch,
            "month": month,
            "ledger": ledger,
            "payments": RoyaltyPayment.objects.filter(branch=branch).select_related("received_by")[:50],
            "form": form,
        },
    )


@login_required
def royalty_attachment(request, payment_id):
    payment = RoyaltyPayment.objects.filter(pk=payment_id).first()
    if payment is None or not payment.attachment:
        raise Http404
    _royalty_branch(request, payment.branch_id)
    return FileResponse(
        payment.attachment.open("rb"), filename=f"Royalty {payment.month:%Y-%m}{Path(payment.attachment.name).suffix}"
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


# --- Family vouchers (M6) --------------------------------------------------------------------


def family_pdf_html(branch, family_vouchers):
    context = _voucher_context(branch, [])
    context["items"] = [
        {
            "fv": fv,
            "rows": [{"v": i.voucher, "amount": i.amount} for i in fv.items.all()],
            "barcode": voucher_barcode(fv.number),
        }
        for fv in family_vouchers
    ]
    return render_to_string("fees/family_voucher_document.html", context)


def render_family_pdf(branch, family_vouchers):
    from weasyprint import HTML

    return HTML(string=family_pdf_html(branch, family_vouchers), base_url=str(settings.BASE_DIR)).write_pdf()


def _family_qs(branch):
    return FamilyVoucher.objects.filter(branch=branch).prefetch_related(
        "items__voucher__student", "items__voucher__section__class_level"
    )


@login_required
def family_vouchers(request):
    branch = _branch(request)
    month = _month(request)
    can_make = request.user.has_branch_perm(S.VOUCHER_PERM, branch.id)
    if request.method == "POST":
        if not can_make:
            raise PermissionDenied
        made, kept = family.make(branch, month, request.user)
        if made or kept:
            messages.success(
                request,
                _("%(m)s family vouchers made; %(k)s already made and unchanged.") % {"m": len(made), "k": len(kept)},
            )
        else:
            messages.warning(request, _("No families with two or more children have open vouchers for this month."))
        return redirect(f"{_url('fees:family_vouchers')}?month={month:%Y-%m}")
    made = list(_family_qs(branch).filter(month=month).exclude(status=FamilyVoucher.Status.REPLACED))
    pending = [f for f in family.families(branch, month) if f["cnic"] not in {fv.father_cnic for fv in made}]
    return render(
        request,
        "fees/family_vouchers.html",
        {
            "month": month,
            "made": made,
            "pending": pending,
            "open_count": sum(1 for fv in made if fv.status == FamilyVoucher.Status.OPEN),
            "can_make": can_make,
            "can_pay": request.user.has_branch_perm(S.PAY_PERM, branch.id),
        },
    )


@login_required
def family_vouchers_pdf(request):
    branch = _branch(request)
    month = _month(request)
    items = list(_family_qs(branch).filter(month=month, status=FamilyVoucher.Status.OPEN).order_by("father_name"))
    if not items:
        raise Http404
    if len(items) > MAX_PRINT:
        return _queue_print(
            request,
            branch,
            "family_vouchers",
            _("%(n)s family vouchers, %(m)s") % {"n": len(items), "m": f"{month:%B %Y}"},
            {"month": month.isoformat()},
        )
    return _pdf_response(render_family_pdf(branch, items), f"Family-vouchers-{month:%Y-%m}")


@login_required
def family_voucher_pdf(request, family_id):
    branch = _branch(request)
    fv = _family_qs(branch).filter(pk=family_id).first()
    if fv is None:
        raise Http404
    return _pdf_response(render_family_pdf(branch, [fv]), f"Family-voucher-{fv.number}")


@login_required
def family_receive(request, family_id):
    """Family fee collection: every child's whole amount due today, in one go."""
    branch = _branch(request, S.PAY_PERM)
    fv = _family_qs(branch).filter(pk=family_id).first()
    if fv is None:
        raise Http404
    today = timezone.localdate()
    form = FamilyReceiveForm(
        request.POST or None,
        request.FILES or None,
        initial={"paid_on": today, "how": PaymentForm.CASH},
        branch=branch,
    )
    paid_on = today
    if request.method == "POST" and form.is_valid():
        paid_on = form.cleaned_data["paid_on"]
    rows, total = family.due_now(fv, paid_on)
    if request.method == "POST" and form.is_valid():
        if fv.status != FamilyVoucher.Status.OPEN:
            form.add_error(None, _("This family voucher is already paid or was replaced."))
        elif total <= 0:
            form.add_error(None, _("Nothing is owed by this family."))
        else:
            d = form.cleaned_data
            payments = family.receive(
                fv,
                d["paid_on"],
                d["method"],
                request.user,
                bank=d["bank"],
                reference=d["reference"],
                note=d["note"],
                attachment=d["attachment"],
            )
            messages.success(
                request,
                _("Family voucher %(n)s paid: Rs %(a)s for %(c)s children.")
                % {"n": fv.number, "a": rupees(sum(p.amount for p in payments)), "c": len(payments)},
            )
            return redirect("fees:family_receive", family_id=fv.id)
    return render(
        request,
        "fees/family_receive.html",
        {
            "fv": fv,
            "rows": rows,
            "total": total,
            "form": form,
            "payments": fv.payments.select_related("student").order_by("pk"),
        },
    )
