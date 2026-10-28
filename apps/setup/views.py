"""Setup screens (Phase 4, M3): the daily setup work that used to need the Django admin.

Every view checks the same permission the old admin needed, limited to the branches the person covers.
Changes are written to the audit log by the models (@audited); password resets are logged explicitly
(the password itself never is).
"""

import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.academics.models import Section
from apps.accounts.models import Role, RoleAssignment, Scope
from apps.core.branch import current_branch
from apps.core.models import AuditEvent
from apps.fees.models import BankAccount, BranchFeeSettings, DiscountType, FeeRate
from apps.organisation.models import AcademicSession, Branch, Campus, HeadOffice, Region
from apps.people.models import Student

from . import access
from .forms import (
    AssignmentForm,
    BankAccountForm,
    BranchForm,
    CampusForm,
    DiscountTypeForm,
    FeeRateForm,
    FeeSettingsForm,
    NewUserForm,
    RegionForm,
    SectionForm,
    SessionForm,
    UserDetailsForm,
)

SESSION_PERM = "organisation.change_academicsession"


def _branch(request, perm):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _current_session():
    return AcademicSession.objects.filter(is_current=True).first()


def _offices(user, perm):
    """Head offices whose every branch the user covers with `perm` (where new branches/regions may go)."""
    return [
        h for h in HeadOffice.objects.all() if access.covers(user, perm, access.scope_branch_ids(Scope.HEAD_OFFICE, h))
    ]


def _network_wide(user, perm):
    return access.covers(user, perm, access.scope_branch_ids(Scope.NETWORK))


def _form_page(request, form, title, back, lede="", submit=None, extra=None):
    from apps.core.deletion import kind_of

    instance = getattr(form, "instance", None)
    return render(
        request,
        "setup/form.html",
        {"form": form, "title": title, "lede": lede, "back": back, "submit": submit or _("Save"),
         "delete_kind": kind_of(instance), "object": instance, **(extra or {})},
    )  # fmt: skip


# ---------- Hub ----------
@login_required
def hub(request):
    user = request.user
    branch = current_branch(request)

    def here(perm):
        return branch is not None and user.has_branch_perm(perm, branch.id)

    def anywhere(perm):
        return bool(user.accessible_branch_ids(perm))

    areas = [
        (
            "sections",
            "setup:sections",
            _("Classes and sections"),
            _("Sections of this session, class teachers, capacity and campuses."),
            "users",
            here("academics.change_section") or here("organisation.change_campus"),
        ),
        (
            "fees",
            "setup:fees",
            _("Fee rates and vouchers"),
            _("Fee amounts per class, due day, late fine, bank details printed on vouchers."),
            "wallet",
            here("fees.change_feerate") or here("fees.change_branchfeesettings"),
        ),
        (
            "users",
            "setup:users",
            _("Users and roles"),
            _("Staff logins, what each person may do and where, password resets."),
            "user-check",
            anywhere(access.VIEW_USERS_PERM),
        ),
        (
            "branches",
            "setup:branches",
            _("Branches and regions"),
            _("Branch details, franchise or company-owned, royalty %, regions of each head office."),
            "building-2",
            anywhere("organisation.view_branch")
            and (anywhere("organisation.change_branch") or anywhere("organisation.add_region")),
        ),
        (
            "sessions",
            "setup:sessions",
            _("Academic sessions"),
            _("School years and which one is current across the network."),
            "calendar-check",
            _network_wide(user, SESSION_PERM),
        ),
    ]
    cards = [(reverse(name), title, text, icon) for _k, name, title, text, icon, ok in areas if ok]
    if not cards and not user.is_staff:
        raise PermissionDenied
    return render(request, "setup/hub.html", {"cards": cards, "branch": branch})


# ---------- Sections and campuses (branch) ----------
@login_required
def sections(request):
    branch = _branch(request, "academics.view_section")
    session = _current_session()
    rows = []
    if session:
        rows = (
            Section.objects.filter(branch=branch, session=session)
            .select_related("class_level", "class_teacher", "campus")
            .annotate(students=Count("enrolments", filter=Q(enrolments__student__status=Student.Status.ACTIVE)))
            .order_by("class_level__sort_order", "name")
        )
    can = {
        "add": request.user.has_branch_perm("academics.add_section", branch.id),
        "change": request.user.has_branch_perm("academics.change_section", branch.id),
        "campus": request.user.has_branch_perm("organisation.change_campus", branch.id),
        "add_campus": request.user.has_branch_perm("organisation.add_campus", branch.id),
    }
    return render(
        request,
        "setup/sections.html",
        {
            "branch": branch,
            "session": session,
            "rows": rows,
            "campuses": Campus.objects.filter(branch=branch),
            "no_teacher": sum(1 for r in rows if r.is_active and not r.class_teacher_id),
            "can": can,
        },
    )


@login_required
def section_form(request, pk=None):
    branch = _branch(request, "academics.change_section" if pk else "academics.add_section")
    session = _current_session()
    if session is None:
        messages.error(request, _("No current academic session is set. Set it under Setup → Academic sessions."))
        return redirect("setup:sections")
    instance = get_object_or_404(Section, pk=pk, branch=branch) if pk else None
    form = SectionForm(
        request.POST or None, instance=instance, branch=branch, session=instance.session if instance else session
    )
    if request.method == "POST" and form.is_valid():
        section = form.save()
        messages.success(request, _("Section %(s)s saved.") % {"s": section})
        return redirect("setup:sections")
    title = _("Edit %(s)s") % {"s": instance} if instance else _("Add a section")
    return _form_page(
        request,
        form,
        title,
        reverse("setup:sections"),
        lede=_("Session %(s)s · %(b)s. The class teacher must have a role in this branch.")
        % {"s": session, "b": branch},
    )


@login_required
def campus_form(request, pk=None):
    branch = _branch(request, "organisation.change_campus" if pk else "organisation.add_campus")
    instance = get_object_or_404(Campus, pk=pk, branch=branch) if pk else None
    form = CampusForm(request.POST or None, instance=instance, branch=branch)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Campus saved."))
        return redirect("setup:sections")
    return _form_page(
        request,
        form,
        _("Edit campus") if instance else _("Add a campus"),
        reverse("setup:sections"),
        lede=_(
            "A building of %(b)s, e.g. a separate boys or girls campus. Fees and administration stay with the branch."
        )
        % {"b": branch},
    )


# ---------- Fee rates and voucher settings (branch) ----------
@login_required
def fees(request):
    branch = _branch(request, "fees.view_feerate")
    today = timezone.localdate()
    rates = list(FeeRate.objects.filter(branch=branch).select_related("head", "class_level"))
    current = {}
    for r in sorted(rates, key=lambda r: r.effective_from):
        if r.effective_from <= today:
            current[(r.head_id, r.class_level_id)] = r.pk
    return render(
        request,
        "setup/fees.html",
        {
            "branch": branch,
            "rates": rates,
            "current_ids": set(current.values()),
            "today": today,
            "settings": BranchFeeSettings.for_branch(branch),
            "banks": BankAccount.objects.filter(branch=branch),
            "discounts": DiscountType.objects.all(),
            "can": {
                "add": request.user.has_branch_perm("fees.add_feerate", branch.id),
                "change": request.user.has_branch_perm("fees.change_feerate", branch.id),
                "settings": request.user.has_branch_perm("fees.change_branchfeesettings", branch.id),
                "discounts": _network_wide(request.user, "fees.change_feehead"),
            },
        },
    )


@login_required
def rate_form(request, pk=None):
    branch = _branch(request, "fees.change_feerate" if pk else "fees.add_feerate")
    instance = get_object_or_404(FeeRate, pk=pk, branch=branch) if pk else None
    form = FeeRateForm(request.POST or None, instance=instance, branch=branch)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            _("Fee rate saved. It is used for vouchers made from now on; vouchers already made keep their amounts."),
        )
        return redirect("setup:fees")
    return _form_page(
        request,
        form,
        _("Edit fee rate") if instance else _("Add a fee rate"),
        reverse("setup:fees"),
        lede=_(
            "To change a fee from a new month, add a new rate starting that month — the old one stays for the record."
        ),
    )


@login_required
def fee_settings(request):
    branch = _branch(request, "fees.change_branchfeesettings")
    form = FeeSettingsForm(request.POST or None, instance=BranchFeeSettings.for_branch(branch))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Voucher settings saved."))
        return redirect("setup:fees")
    return _form_page(
        request,
        form,
        _("Voucher and payment settings"),
        reverse("setup:fees"),
        lede=_("Printed on every fee voucher of %(b)s.") % {"b": branch},
    )


@login_required
def bank_form(request, pk=None):
    """The banks and wallets this branch collects fees in (chosen when a fee is received by bank)."""
    branch = _branch(request, "fees.change_branchfeesettings")
    instance = get_object_or_404(BankAccount, pk=pk, branch=branch) if pk else None
    form = BankAccountForm(request.POST or None, instance=instance, branch=branch)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Bank saved."))
        return redirect("setup:fees")
    return _form_page(
        request,
        form,
        _("Edit bank") if instance else _("Add a bank"),
        reverse("setup:fees"),
        lede=_("Fees received by bank are recorded against one of %(b)s's banks.") % {"b": branch},
    )


@login_required
def discount_form(request, pk=None):
    """Discount types offered at admission; the same list for every branch, so only network-wide setup."""
    if not _network_wide(request.user, "fees.change_feehead"):
        raise PermissionDenied
    instance = get_object_or_404(DiscountType, pk=pk) if pk else None
    form = DiscountTypeForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Discount saved."))
        return redirect("setup:fees")
    return _form_page(
        request,
        form,
        _("Edit discount") if instance else _("Add a discount"),
        reverse("setup:fees"),
        lede=_("Offered on the admission form. Brothers and sisters get the sibling fee by themselves."),
    )


# ---------- Branches and regions (head office / network) ----------
@login_required
def branches(request):
    ids = request.user.accessible_branch_ids("organisation.view_branch")
    if not ids and not request.user.is_superuser:
        raise PermissionDenied
    qs = Branch.objects.filter(id__in=ids).select_related("head_office", "region")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(city__icontains=q))
    office = request.GET.get("ho", "")
    if office.isdigit():
        qs = qs.filter(head_office_id=int(office))
    status = request.GET.get("status", "active")
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)
    page = Paginator(qs.order_by("head_office__name", "name"), 50).get_page(request.GET.get("page"))
    changeable = request.user.accessible_branch_ids("organisation.change_branch")
    region_offices = _offices(request.user, "organisation.change_region")
    return render(
        request,
        "setup/branches.html",
        {
            "page": page,
            "q": q,
            "ho": office,
            "status": status,
            "offices": HeadOffice.objects.filter(branches__id__in=ids).distinct(),
            "changeable": changeable,
            "can_add": bool(_offices(request.user, "organisation.add_branch")),
            "regions": Region.objects.filter(head_office__in=region_offices)
            .select_related("head_office")
            .annotate(n=Count("branches")),
            "can_add_region": bool(_offices(request.user, "organisation.add_region")),
        },
    )


@login_required
def branch_form(request, pk=None):
    user = request.user
    if pk:
        instance = get_object_or_404(Branch, pk=pk)
        if not user.has_branch_perm("organisation.change_branch", instance.id):
            raise PermissionDenied
        offices = _offices(user, "organisation.add_branch")
        if instance.head_office not in offices:
            offices.append(instance.head_office)  # may keep its head office; moving it needs rights over the new one
    else:
        instance = None
        offices = _offices(user, "organisation.add_branch")
        if not offices:
            raise PermissionDenied
    form = BranchForm(request.POST or None, instance=instance, head_offices=offices)
    if request.method == "POST" and form.is_valid():
        branch = form.save()
        messages.success(request, _("Branch %(b)s saved.") % {"b": branch})
        return redirect("setup:branches")
    return _form_page(
        request,
        form,
        _("Edit %(b)s") % {"b": instance} if instance else _("Add a branch"),
        reverse("setup:branches"),
        lede=_(
            "Royalty %: the head office's share of the fees received each month — "
            "usually 8 for franchises and 0 for company-owned campuses."
        ),
    )


@login_required
def region_form(request, pk=None):
    perm = "organisation.change_region" if pk else "organisation.add_region"
    offices = _offices(request.user, perm)
    instance = get_object_or_404(Region, pk=pk) if pk else None
    if not offices or (instance and instance.head_office not in offices):
        raise PermissionDenied
    form = RegionForm(request.POST or None, instance=instance, head_offices=offices)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Region saved."))
        return redirect("setup:branches")
    return _form_page(request, form, _("Edit region") if instance else _("Add a region"), reverse("setup:branches"))


# ---------- Academic sessions (network-wide) ----------
def _sessions_allowed(user):
    if not _network_wide(user, SESSION_PERM):
        raise PermissionDenied


@login_required
def sessions(request):
    _sessions_allowed(request.user)
    return render(request, "setup/sessions.html", {"sessions": AcademicSession.objects.all()})


@login_required
def session_form(request, pk=None):
    _sessions_allowed(request.user)
    instance = get_object_or_404(AcademicSession, pk=pk) if pk else None
    form = SessionForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Session saved."))
        return redirect("setup:sessions")
    return _form_page(request, form, _("Edit session") if instance else _("Add a session"), reverse("setup:sessions"))


@login_required
@require_POST
def make_current(request, pk):
    _sessions_allowed(request.user)
    session = get_object_or_404(AcademicSession, pk=pk)
    with transaction.atomic():
        for old in AcademicSession.objects.filter(is_current=True).exclude(pk=pk):
            old.is_current = False
            old.save()  # one by one so each change is audited
        session.is_current = True
        session.save()
    messages.success(request, _("%(s)s is now the current session across the network.") % {"s": session})
    return redirect("setup:sessions")


# ---------- Users and roles ----------
def _temporary_password():
    while True:
        candidate = "-".join(secrets.token_urlsafe(6)[:5] for _i in range(3))
        try:
            validate_password(candidate)
            return candidate
        except ValidationError:
            continue


def _log_password_reset(request, target):
    AuditEvent.objects.create(
        actor=request.user,
        action=AuditEvent.Action.UPDATE,
        model_label="accounts.User",
        object_id=str(target.pk),
        object_repr=str(target)[:255],
        changes={"password": "reset (new temporary password issued)"},
        ip_address=request.META.get("REMOTE_ADDR"),
    )


def _assignment_form(request, data=None, prefix=None):
    targets = access.scope_targets(request.user)
    roles = _grantable_roles(request.user, targets)
    return AssignmentForm(data, roles=roles, targets=targets, prefix=prefix), targets


def _grantable_roles(user, targets):
    """Roles the user can give somewhere (exact check repeats on save)."""
    out = []
    for role in Role.objects.prefetch_related("permissions__content_type"):
        scopes = role.allowed_scopes or [s.value for s in Scope]
        options = []
        if Scope.NETWORK in scopes and targets["network"]:
            options.append((Scope.NETWORK, access.scope_branch_ids(Scope.NETWORK)))
        if Scope.HEAD_OFFICE in scopes:
            options += [
                (Scope.HEAD_OFFICE, access.scope_branch_ids(Scope.HEAD_OFFICE, h)) for h in targets["head_offices"]
            ]
        if Scope.REGION in scopes:
            options += [(Scope.REGION, access.scope_branch_ids(Scope.REGION, region=r)) for r in targets["regions"]]
        if Scope.BRANCH in scopes:
            options += [(Scope.BRANCH, {b.id}) for b in targets["branches"]]
        if any(access.can_assign(user, role, scope, ids)[0] for scope, ids in options):
            out.append(role)
    return out


def _check_assignment(request, form):
    """Apply the no-escalation rule to a valid AssignmentForm; adds a form error and returns False if refused."""
    d = form.cleaned_data
    ids = access.scope_branch_ids(d["scope"], d["head_office"], d["region"], d["branch"])
    ok, reason = access.can_assign(request.user, d["role"], d["scope"], ids)
    if not ok:
        form.add_error(
            None,
            {
                "scope": _("This role cannot be given at this level."),
                "outside": _("You can only give roles inside your own area."),
                "more_than_you_hold": _(
                    "This role can manage logins or setup there that you cannot manage yourself, so you cannot give it."
                ),
            }[reason],
        )
    return ok


def _new_assignment(user, d):
    a = RoleAssignment(
        user=user,
        role=d["role"],
        scope=d["scope"],
        head_office=d["head_office"],
        region=d["region"],
        branch=d["branch"],
        starts_on=d["starts_on"],
        ends_on=d["ends_on"],
    )
    a.full_clean()
    a.save()
    return a


@login_required
def users(request):
    if not request.user.accessible_branch_ids(access.VIEW_USERS_PERM) and not request.user.is_superuser:
        raise PermissionDenied
    qs = access.visible_users(request.user)
    q = request.GET.get("q", "").strip()
    if q:
        cond = Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        digits = "".join(c for c in q if c.isdigit())
        if len(digits) >= 4:
            cond |= Q(phone__contains=digits[-10:])
        qs = qs.filter(cond)
    role = request.GET.get("role", "")
    if role.isdigit():
        qs = qs.filter(role_assignments__role_id=int(role), role_assignments__is_active=True)
    status = request.GET.get("status", "active")
    if status in ("active", "inactive"):
        qs = qs.filter(is_active=status == "active")
    qs = (
        qs.order_by("first_name", "last_name", "username")
        .distinct()
        .prefetch_related(
            "role_assignments__role",
            "role_assignments__branch",
            "role_assignments__region",
            "role_assignments__head_office",
        )
    )
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    for u in page:
        u.current_roles = [a for a in u.role_assignments.all() if a.is_active]
    return render(
        request,
        "setup/users.html",
        {
            "page": page,
            "q": q,
            "role": role,
            "status": status,
            "roles": Role.objects.all(),
            "can_add": bool(request.user.accessible_branch_ids(access.ADD_USER_PERM)) or request.user.is_superuser,
        },
    )


@never_cache
@login_required
def user_new(request):
    if not request.user.accessible_branch_ids(access.ADD_USER_PERM) and not request.user.is_superuser:
        raise PermissionDenied
    form = NewUserForm(request.POST or None)
    assign, targets = _assignment_form(request, request.POST or None, prefix="a")
    if request.method == "POST" and form.is_valid() and assign.is_valid() and _check_assignment(request, assign):
        d = assign.cleaned_data
        ids = access.scope_branch_ids(d["scope"], d["head_office"], d["region"], d["branch"])
        if not access.covers(request.user, access.ADD_USER_PERM, ids):
            assign.add_error(None, _("You can only add logins for people inside your own area."))
        else:
            password = _temporary_password()
            with transaction.atomic():
                user = form.save(commit=False)
                user.set_password(password)
                user.save()
                _new_assignment(user, d)
            return render(request, "setup/password.html", {"target": user, "password": password, "new": True})
    return render(request, "setup/user_new.html", {"form": form, "assign": assign, "targets": targets})


@never_cache
@login_required
def user_detail(request, pk):
    target = get_object_or_404(access.visible_users(request.user), pk=pk)
    can_manage = access.can_manage_user(request.user, target)
    can_assign_any = bool(request.user.accessible_branch_ids(access.ASSIGN_PERM)) or request.user.is_superuser
    details = UserDetailsForm(
        request.POST if request.POST.get("action") == "details" else None, instance=target, prefix="u"
    )
    assign, targets = _assignment_form(
        request, request.POST if request.POST.get("action") == "assign" else None, prefix="a"
    )
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "details":
            if not can_manage:
                raise PermissionDenied
            if details.is_valid():
                details.save()
                messages.success(request, _("Details saved."))
                return redirect("setup:user", pk=pk)
        elif action == "assign":
            if (
                target.pk == request.user.pk
                or not can_assign_any
                or (target.is_superuser and not request.user.is_superuser)
            ):
                raise PermissionDenied
            if assign.is_valid() and _check_assignment(request, assign):
                _new_assignment(target, assign.cleaned_data)
                messages.success(request, _("Role given."))
                return redirect("setup:user", pk=pk)
    assignments = list(
        target.role_assignments.select_related("role", "head_office", "region", "branch").order_by(
            "-is_active", "role__name"
        )
    )
    for a in assignments:
        a.can_end = a.is_active and access.can_end(request.user, a)
    return render(
        request,
        "setup/user_detail.html",
        {
            "target": target,
            "assignments": assignments,
            "details": details,
            "assign": assign,
            "targets": targets,
            "can_manage": can_manage,
            "can_assign": can_assign_any
            and target.pk != request.user.pk
            and not (target.is_superuser and not request.user.is_superuser),
            "is_self": target.pk == request.user.pk,
        },
    )


@login_required
@require_POST
def end_assignment(request, pk, assignment_id):
    a = get_object_or_404(RoleAssignment.objects.select_related("user", "role"), pk=assignment_id, user_id=pk)
    if not access.can_end(request.user, a):
        raise PermissionDenied
    a.is_active = False
    a.ends_on = timezone.localdate()
    a.save()
    messages.success(
        request,
        _("%(role)s ended for %(name)s.")
        % {"role": a.role.display_name, "name": a.user.get_full_name() or a.user.username},
    )
    return redirect("setup:user", pk=pk)


@never_cache
@login_required
@require_POST
def reset_password(request, pk):
    target = get_object_or_404(access.visible_users(request.user), pk=pk)
    if not access.can_manage_user(request.user, target):
        raise PermissionDenied
    password = _temporary_password()
    target.set_password(password)
    target.save()
    _log_password_reset(request, target)
    return render(request, "setup/password.html", {"target": target, "password": password, "new": False})


@login_required
@require_POST
def set_active(request, pk):
    target = get_object_or_404(access.visible_users(request.user), pk=pk)
    if not access.can_manage_user(request.user, target):
        raise PermissionDenied
    target.is_active = request.POST.get("active") == "1"
    target.save()
    messages.success(
        request, _("Login switched on.") if target.is_active else _("Login switched off. They can no longer sign in.")
    )
    return redirect("setup:user", pk=pk)
