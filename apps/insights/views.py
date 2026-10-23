"""Overview → Students needing attention (M13, free part)."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.academics.models import Section
from apps.attendance import services as attendance
from apps.core import exports
from apps.core.branch import current_branch
from apps.organisation.models import AcademicSession

from . import services as S


@login_required
def attention(request):
    branch = current_branch(request)
    user = request.user
    if branch is None or not user.has_branch_perm(attendance.VIEW_PERM, branch.id):
        raise PermissionDenied
    session = AcademicSession.objects.filter(is_current=True).first()
    everyone = user.has_branch_perm(attendance.CHANGE_PERM, branch.id)  # principals and coordinators
    sections = Section.objects.filter(branch=branch, session=session, is_active=True).select_related("class_level")
    if not everyone:
        sections = sections.filter(class_teacher=user)  # teachers: their own classes
    sections = list(sections.order_by("class_level__sort_order", "name"))
    chosen = [s for s in sections if str(s.id) == request.GET.get("section")]
    limits = S.read_limits(request.GET)
    can_fees = user.has_branch_perm("fees.view_voucher", branch.id)
    can_hifz = user.has_branch_perm("hifz.view_hifzlesson", branch.id)
    rows = S.students_needing_attention(
        branch, session, timezone.localdate(), limits, sections=chosen or sections, can_fees=can_fees,
        can_hifz=can_hifz,
    )  # fmt: skip
    signals = S.signals(can_fees, can_hifz)
    counts = {code: sum(1 for r in rows if any(f[0] == code for f in r.flags)) for code, _label in signals}
    signal = request.GET.get("signal", "")
    if signal:
        rows = [r for r in rows if any(f[0] == signal for f in r.flags)]
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Students needing attention"),
            [_("Admission no."), _("Name"), _("Father"), _("Class"), _("Parent's mobile"), _("Signals"), _("Details")],
            ([r.student.admission_no, r.student.full_name, r.student.father_name, str(r.section), r.phone,
              len(r.flags), "; ".join(t for _c, t in r.flags)] for r in rows),
            branch=branch,
        )  # fmt: skip
    return render(
        request,
        "insights/attention.html",
        {
            "branch": branch,
            "rows": rows,
            "signals": [(code, label, counts[code]) for code, label in signals],
            "signal": signal,
            "sections": sections,
            "chosen": chosen[0] if chosen else None,
            "limits": limits,
            "defaults": S.DEFAULTS,
            "can_fees": can_fees,
            "can_hifz": can_hifz,
            "everyone": everyone,
        },
    )
