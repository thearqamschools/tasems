"""Notices for staff and parents, and preparing messages to parents (M8)."""

from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.academics.models import Section
from apps.core import exports
from apps.core.branch import current_branch

from . import messaging as M
from . import services as S
from .forms import NoticeForm, TemplateForm
from .models import MessageBatch, MessageTemplate, Notice


def _branch(request):
    branch = current_branch(request)
    if branch is None:
        raise PermissionDenied
    return branch


@login_required
def index(request):
    branch = _branch(request)
    can_post = bool(S.where_choices(request.user, branch))
    qs = Notice.objects.for_branch(branch).select_related("branch", "head_office", "created_by")
    if not can_post:  # staff see what is meant for staff
        qs = S.staff_notices(branch, timezone.localdate())
    notices = list(qs.annotate(read_count=Count("reads"))[:100])
    return render(
        request,
        "notices/index.html",
        {
            "notices": notices,
            "can_post": can_post,
            "unread": S.unread_ids(notices, request.user),
            "today": timezone.localdate(),
            "can_message": request.user.has_branch_perm(S.SEND_PERM, branch.id),
        },
    )


@login_required
def new(request):
    branch = _branch(request)
    choices = S.where_choices(request.user, branch)
    if not choices:
        raise PermissionDenied
    form = NoticeForm(request.POST or None, request.FILES or None, where_choices=choices)
    if request.method == "POST" and form.is_valid():
        notice = form.save(commit=False)
        where = form.cleaned_data["where"]
        notice.branch = branch if where == "branch" else None
        notice.head_office = branch.head_office if where == "head_office" else None
        notice.created_by = request.user
        notice.save()
        form.save_m2m()
        messages.success(request, _("Notice posted: %(t)s") % {"t": notice.title})
        return redirect("notices:detail", notice_id=notice.id)
    return render(request, "notices/form.html", {"form": form})


def _visible(request, branch, notice_id):
    notice = Notice.objects.for_branch(branch).filter(pk=notice_id).first()
    if notice is None:
        raise Http404
    if not (notice.for_staff or S.where_choices(request.user, branch)):
        raise Http404  # a parents-only notice is shown to staff who post notices
    return notice


@login_required
def detail(request, notice_id):
    branch = _branch(request)
    notice = _visible(request, branch, notice_id)
    S.mark_read(notice, request.user)
    return render(
        request,
        "notices/detail.html",
        {
            "notice": notice,
            "can_manage": S.may_manage(request.user, notice, branch),
            "read_count": notice.reads.count(),
        },
    )


@login_required
@require_POST
def withdraw(request, notice_id):
    branch = _branch(request)
    notice = _visible(request, branch, notice_id)
    if not S.may_manage(request.user, notice, branch):
        raise PermissionDenied
    notice.is_withdrawn = True
    notice.save(update_fields=["is_withdrawn", "updated_at"])
    messages.success(request, _("Notice withdrawn: it is no longer shown."))
    return redirect("notices:index")


@login_required
def attachment(request, notice_id):
    branch = _branch(request)
    notice = _visible(request, branch, notice_id)
    if not notice.attachment:
        raise Http404
    return FileResponse(notice.attachment.open("rb"), filename=f"{notice.title}{Path(notice.attachment.name).suffix}")


# --- Messages to parents ---------------------------------------------------------------------


@login_required
def compose(request):
    branch = _branch(request)
    if not request.user.has_branch_perm(S.SEND_PERM, branch.id):
        raise PermissionDenied
    templates = MessageTemplate.objects.filter(is_active=True)
    choices = M.audiences(request.user, branch)
    g = request.GET
    template = templates.filter(pk=g.get("template")).first() if g.get("template", "").isdigit() else None
    audience = g.get("audience") if g.get("audience") in dict(choices) else ""
    try:
        min_months = max(1, int(g.get("months", "1")))
    except ValueError:
        min_months = 1
    section_id = int(g["section"]) if g.get("section", "").isdigit() else None
    text = g.get("text", "").strip()[:500]
    rows, without_phone = [], 0
    if template and audience:
        rows, without_phone = M.recipients(branch, audience, min_months=min_months, section_id=section_id)
        for r in rows:
            r["message"] = M.fill(template.body, r, branch, text)
            r["whatsapp"] = M.whatsapp_link(r["phone"], r["message"])
        if exports.wants_xlsx(request):
            MessageBatch.objects.create(
                branch=branch, template=template, audience=audience, count=len(rows), created_by=request.user
            )
            return exports.xlsx_response(
                _("Messages to parents"),
                [_("Mobile"), _("Student"), _("Class"), _("Message")],
                ([r["phone"], r["student"].full_name, str(r["section"] or ""), r["message"]] for r in rows),
                branch=branch,
            )
    return render(
        request,
        "notices/compose.html",
        {
            "templates": templates,
            "template": template,
            "audiences": choices,
            "audience": audience,
            "months": min_months,
            "sections": Section.objects.filter(branch=branch, session__is_current=True, is_active=True).select_related(
                "class_level"
            ),
            "section_id": section_id,
            "text": text,
            "rows": rows,
            "without_phone": without_phone,
            "placeholders": M.PLACEHOLDERS,
            "batches": MessageBatch.objects.filter(branch=branch).select_related("template", "created_by")[:10],
            "can_edit_templates": request.user.has_perm(S.TEMPLATE_PERM)
            or bool(request.user.accessible_branch_ids(S.TEMPLATE_PERM)),
        },
    )


def _template_editor(request):
    branch = _branch(request)
    if not (request.user.is_superuser or len(request.user.accessible_branch_ids(S.TEMPLATE_PERM)) > 0):
        raise PermissionDenied
    from apps.accounts.models import RoleAssignment, Scope

    network = (
        request.user.is_superuser
        or RoleAssignment.objects.filter(
            user=request.user, is_active=True, scope=Scope.NETWORK, role__permissions__codename="change_messagetemplate"
        ).exists()
    )
    if not network:
        raise PermissionDenied  # templates are the same for every branch, so only network setup changes them
    return branch


@login_required
def templates(request):
    _template_editor(request)
    return render(
        request, "notices/templates.html", {"templates": MessageTemplate.objects.all(), "placeholders": M.PLACEHOLDERS}
    )


@login_required
def template_form(request, template_id=None):
    _template_editor(request)
    instance = MessageTemplate.objects.filter(pk=template_id).first() if template_id else None
    if template_id and instance is None:
        raise Http404
    form = TemplateForm(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Message template saved."))
        return redirect("notices:templates")
    return render(request, "notices/template_form.html", {"form": form, "placeholders": M.PLACEHOLDERS})
