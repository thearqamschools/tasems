"""Staff screens: register, attendance from the machines, corrections, leave, self-service."""

import datetime as dt
import io
import ipaddress
import re
import secrets
from collections import defaultdict
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.core import exports
from apps.core.branch import current_branch
from apps.organisation.models import AcademicSession

from . import importer
from . import services as S
from .forms import CorrectionForm, EmployeeForm, LeaveForm, staff_formsets
from .models import DutyTime, Employee, HRSettings, LeaveRequest, StaffDay


def _branch(request, perm=S.VIEW_PERM):
    branch = current_branch(request)
    if branch is None or not request.user.has_branch_perm(perm, branch.id):
        raise PermissionDenied
    return branch


def _employee(branch, employee_id):
    e = Employee.objects.filter(pk=employee_id, branch=branch).select_related("campus", "user").first()
    if e is None:
        raise Http404
    return e


def _date(value, default):
    try:
        return dt.date.fromisoformat(value) if value else default
    except ValueError:
        return default


def _month(request):
    today = timezone.localdate()
    try:
        y, m = (int(x) for x in request.GET.get("month", "").split("-"))
        return dt.date(y, m, 1)
    except (ValueError, TypeError):
        return today.replace(day=1)


def _session():
    return AcademicSession.objects.filter(is_current=True).first()


def _month_end(first):
    return (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)


def _natural(text):
    """'E2' before 'E10'; empty last."""
    text = str(text or "")
    return (not text, [(0, int(t), "") if t.isdigit() else (1, 0, t.lower()) for t in re.split(r"(\d+)", text) if t])


STAFF_SORTS = {
    "code": lambda e: _natural(e.code),
    "machine": lambda e: _natural(e.machine_id),
    "name": lambda e: e.full_name.lower(),
    "designation": lambda e: (e.designation or "").lower(),
    "type": lambda e: str(e.get_staff_type_display()),
    "mobile": lambda e: _natural(e.phone),
    "joined": lambda e: e.joined_on,
}


def sort_by_heading(request, items, sorts, person=lambda x: x, default=None):
    """Sorts a list by the heading clicked (?sort=name, ?sort=-name for the other way; project lead, 6 Nov 2026)."""
    wanted = request.GET.get("sort", "") or (default or "")
    key = wanted.lstrip("-")
    if key not in sorts:
        return items
    return sorted(items, key=lambda x: sorts[key](person(x)), reverse=wanted.startswith("-"))


@login_required
def index(request):
    branch = _branch(request)
    today = timezone.localdate()
    qs = Employee.objects.filter(branch=branch).select_related("campus")
    status = request.GET.get("status", "active")
    if status in Employee.Status.values:
        qs = qs.filter(status=status)
    staff_type = request.GET.get("type")
    if staff_type in Employee.StaffType.values:
        qs = qs.filter(staff_type=staff_type)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(full_name__icontains=q) | Q(code__iexact=q) | Q(phone__icontains=q) | Q(designation__icontains=q)
        )
    if exports.wants_xlsx(request):
        return exports.xlsx_response(
            _("Staff"),
            [_("EMP.code"), _("Machine ID"), _("Name"), _("Father / husband name"), _("Designation"), _("Type"),
             _("Mobile"), _("CNIC"), _("Campus"), _("Qualification"), _("Joining date"), _("Status")],
            (
                [e.code, e.machine_id, e.full_name, e.father_name or e.husband_name, e.designation,
                 e.get_staff_type_display(), e.phone, e.cnic, str(e.campus or ""), e.qualification, e.joined_on,
                 e.get_status_display()]
                for e in sort_by_heading(request, list(qs.order_by("staff_type", "full_name")), STAFF_SORTS)
            ),
            branch=branch,
        )  # fmt: skip
    _rows, counts = S.day_summary(branch, today)
    hr = HRSettings.for_branch(branch)
    return render(
        request,
        "hr/index.html",
        {
            "employees": sort_by_heading(request, list(qs.order_by("staff_type", "full_name")[:500]), STAFF_SORTS),
            "counts": counts,
            "status": status,
            "staff_type": staff_type,
            "q": q,
            "statuses": Employee.Status.choices,
            "types": Employee.StaffType.choices,
            "settings_missing": (hr.pk is None or hr.duty_starts is None)
            and not DutyTime.objects.filter(branch=branch).exists(),
            "can_edit": request.user.has_branch_perm(S.ADD_PERM, branch.id),
            "can_import": request.user.has_branch_perm(S.IMPORT_PERM, branch.id),
            "today": today,
        },
    )


@login_required
def employee_form(request, employee_id=None):
    branch = _branch(request, S.EDIT_PERM if employee_id else S.ADD_PERM)
    instance = _employee(branch, employee_id) if employee_id else None
    money = request.user.has_branch_perm("payroll.change_employeepay", branch.id)
    form = EmployeeForm(request.POST or None, request.FILES or None, instance=instance, branch=branch, money=money)
    sets = staff_formsets(request.POST or None, instance)
    if request.method == "POST" and form.is_valid() and all(f.is_valid() for f in sets.values() if f.is_bound):
        with transaction.atomic():
            e = form.save()
            for formset in (f for f in sets.values() if f.is_bound):
                formset.instance = e
                for row in formset.save(commit=False):
                    row.branch = branch
                    row.save()
                for row in formset.deleted_objects:
                    row.delete()
        if instance and instance.status != Employee.Status.ACTIVE and e.left_on:
            S.rebuild_days(branch, e.left_on, timezone.localdate(), [e.id])
        messages.success(request, _("Saved."))
        return redirect("hr:employee", employee_id=e.id)
    return render(request, "hr/employee_form.html", {"form": form, "employee": instance, "sets": sets})


@login_required
def employee_cv(request, employee_id):
    """The CV is private: only people who may see this branch's staff can open it."""
    branch = _branch(request)
    e = _employee(branch, employee_id)
    if not e.cv:
        raise Http404
    return FileResponse(e.cv.open("rb"), filename=f"CV - {e.full_name}{Path(e.cv.name).suffix}")


@login_required
def employee(request, employee_id):
    branch = _branch(request)
    e = _employee(branch, employee_id)
    month = _month(request)
    days = StaffDay.objects.filter(employee=e, date__gte=month, date__lte=_month_end(month))
    session = _session()
    return render(
        request,
        "hr/employee.html",
        {
            "employee": e,
            "month": month,
            "days": days,
            "balance": S.leave_balance(e, session),
            "leaves": e.leave_requests.select_related("leave_type").order_by("-starts_on")[:20],
            "can_edit": request.user.has_branch_perm(S.EDIT_PERM, branch.id),
            "can_leave": request.user.has_branch_perm(S.LEAVE_PERM, branch.id),
        },
    )


# --- Staff list from Excel -------------------------------------------------------------------


@login_required
def staff_import(request):
    from apps.people.views import _import_dir

    branch = _branch(request, S.ADD_PERM)
    if request.GET.get("template"):
        response = HttpResponse(
            importer.template_workbook(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="TASEMS-staff-template.xlsx"'
        return response
    context = {}
    if request.method == "POST" and request.POST.get("step") == "check":
        upload = request.FILES.get("file")
        if upload is None or not upload.name.lower().endswith(".xlsx") or upload.size > 5 * 1024 * 1024:
            messages.error(request, _("Choose an Excel file (.xlsx) smaller than 5 MB."))
        else:
            content = upload.read()
            result = importer.check(content, branch=branch)
            token = ""
            if result.ok or result.can_skip:
                token = secrets.token_hex(16)
                (_import_dir() / f"{token}.xlsx").write_bytes(content)
                request.session["staff_import"] = {"token": token, "branch": branch.id}
            context.update(result=result, token=token, shown_errors=result.errors[:300])
            if result.can_skip:
                context.update(skip_count=len(result.problem_rows), keep_count=len(result.without_problem_rows().rows))
    elif request.method == "POST" and request.POST.get("step") == "import":
        pending = request.session.pop("staff_import", None)
        token = request.POST.get("token", "")
        if not pending or pending["token"] != token or pending["branch"] != branch.id or not token.isalnum():
            messages.error(request, _("This import has expired. Please check the file again."))
            return redirect("hr:staff_import")
        path = _import_dir() / f"{token}.xlsx"
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            messages.error(request, _("This import has expired. Please check the file again."))
            return redirect("hr:staff_import")
        finally:
            path.unlink(missing_ok=True)
        result = importer.check(content, branch=branch)
        skipped = []
        if request.POST.get("skip") == "1" and result.can_skip:
            skipped = result.problem_rows
            result = result.without_problem_rows()
        if not result.ok:
            messages.error(request, _("The data changed since the check. Please check the file again."))
            return redirect("hr:staff_import")
        n = importer.run_import(result, branch=branch)
        messages.success(request, _("%(n)s staff members added.") % {"n": n})
        if skipped:
            from apps.people.views import skipped_message

            messages.warning(request, skipped_message(skipped))
        return redirect("hr:index")
    return render(request, "hr/staff_import.html", context)


# --- Attendance machine file -----------------------------------------------------------------


@login_required
def punches_import(request):
    from apps.people.views import _import_dir

    branch = _branch(request, S.IMPORT_PERM)
    context = {}
    if request.method == "POST" and request.POST.get("step") == "check":
        upload = request.FILES.get("file")
        name = upload.name if upload else ""
        if upload is None or not name.lower().endswith((".xlsx", ".csv", ".dat", ".txt")):
            messages.error(request, _("Choose the machine's export file (.xlsx, .csv, .dat or .txt)."))
        elif upload.size > S.MAX_BYTES:
            messages.error(request, _("The file is larger than 10 MB. Export one month at a time."))
        else:
            content = upload.read()
            machine_file = S.read_machine_file(content, name)
            check = S.check_punches(branch, machine_file)
            token = ""
            if check.matched and not machine_file.errors:
                token = secrets.token_hex(16)
                ext = name.lower().rsplit(".", 1)[-1]
                (_import_dir() / f"{token}.xlsx").write_bytes(content)  # removed after a day like other uploads
                request.session["punch_import"] = {"token": token, "branch": branch.id, "name": name, "ext": ext}
            context.update(file=machine_file, check=check, token=token, filename=name)
    elif request.method == "POST" and request.POST.get("step") == "import":
        pending = request.session.pop("punch_import", None)
        token = request.POST.get("token", "")
        if not pending or pending["token"] != token or pending["branch"] != branch.id or not token.isalnum():
            messages.error(request, _("This import has expired. Please check the file again."))
            return redirect("hr:punches_import")
        path = _import_dir() / f"{token}.xlsx"
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            messages.error(request, _("This import has expired. Please check the file again."))
            return redirect("hr:punches_import")
        finally:
            path.unlink(missing_ok=True)
        check = S.check_punches(branch, S.read_machine_file(content, pending["name"]))
        added = S.save_punches(branch, check, request.user, pending["name"])
        messages.success(
            request,
            _("%(n)s new punches saved for %(e)s staff; attendance worked out from %(a)s to %(b)s.")
            % {"n": added, "e": check.employees, "a": check.first, "b": check.last},
        )
        return redirect(f"{reverse('hr:day')}?date={check.last:%Y-%m-%d}")
    return render(request, "hr/punches_import.html", context)


# --- Daily and monthly attendance ------------------------------------------------------------


DAY_SORTS = {
    **{k: (lambda f: lambda r: f(r[0]))(f) for k, f in STAFF_SORTS.items()},
    "status": lambda r: str(r[1].get_status_display()) if r[1] else "~",
    "in": lambda r: (r[1] is None or r[1].first_in is None, r[1].first_in if r[1] and r[1].first_in else dt.time()),
    "out": lambda r: (r[1] is None or r[1].last_out is None, r[1].last_out if r[1] and r[1].last_out else dt.time()),
}


@login_required
def day(request):
    """One day's staff attendance in two parts (R7-8, project lead 6 Nov 2026): staff on the attendance machine
    (worked out from their punches) and staff with no Biometric ID (entered by hand here). Both can be corrected."""
    branch = _branch(request)
    today = timezone.localdate()
    date = min(_date(request.GET.get("date"), today), today)
    can_correct = request.user.has_branch_perm(S.CORRECT_PERM, branch.id)
    if request.method == "POST":
        if not can_correct:
            raise PermissionDenied
        if request.POST.get("action") == "hand":
            saved = _save_hand_entries(request, branch, date)
            if saved:
                messages.success(request, _("Attendance entered for %(n)s staff.") % {"n": saved})
            else:
                messages.error(request, _("Choose a status for at least one person."))
            return redirect(f"{reverse('hr:day')}?date={date:%Y-%m-%d}")
        e = _employee(branch, request.POST.get("employee"))
        if request.POST.get("remove"):
            S.remove_correction(e, date, request.user)
            messages.success(request, _("Correction removed for %(n)s.") % {"n": e.full_name})
        else:
            form = CorrectionForm(request.POST)
            if form.is_valid():
                d = form.cleaned_data
                S.correct_day(e, date, d["status"], d["note"], request.user, d["first_in"], d["last_out"])
                messages.success(request, _("Attendance corrected for %(n)s.") % {"n": e.full_name})
            else:
                messages.error(request, _("Choose a status and write the reason."))
        return redirect(f"{reverse('hr:day')}?date={date:%Y-%m-%d}")
    if request.GET.get("refresh") and can_correct:
        S.rebuild_days(branch, date, date)
    rows, counts = S.day_summary(branch, date)
    rows = sort_by_heading(request, rows, DAY_SORTS, default="code")
    return render(
        request,
        "hr/day.html",
        {
            "date": date,
            "machine_rows": [r for r in rows if r[0].machine_id],
            "hand_rows": [r for r in rows if not r[0].machine_id],
            "counts": counts,
            "previous": date - dt.timedelta(days=1),
            "next": date + dt.timedelta(days=1) if date < today else None,
            "can_correct": can_correct,
            "statuses": [c for c in CorrectionForm.base_fields["status"].choices],
        },
    )


def _clock(value):
    try:
        return dt.time.fromisoformat(value) if value else None
    except ValueError:
        return None


def _save_hand_entries(request, branch, date):
    """Rows of the "entered by hand" part: a status (and times, if known) for each person who has one."""
    allowed = {v for v, _l in CorrectionForm.base_fields["status"].choices}
    saved = 0
    for e in Employee.objects.filter(branch=branch, machine_id=""):
        status = request.POST.get(f"status_{e.id}", "")
        if status not in allowed:
            continue
        first_in, last_out = _clock(request.POST.get(f"in_{e.id}")), _clock(request.POST.get(f"out_{e.id}"))
        current = StaffDay.objects.filter(employee=e, date=date).first()
        if current and (current.status, current.first_in, current.last_out) == (status, first_in, last_out):
            continue
        S.correct_day(e, date, status, _("Entered by hand"), request.user, first_in, last_out)
        saved += 1
    return saved


@login_required
def month(request):
    branch = _branch(request)
    first = _month(request)
    dates, rows = S.month_sheet(branch, first)
    rows = sort_by_heading(request, rows, STAFF_SORTS, person=lambda r: r["employee"])
    if request.GET.get("format") == "xlsx":
        return _month_xlsx(branch, first, dates, rows)
    return render(request, "hr/month.html", {"month": first, "dates": dates, "rows": rows})


TOTAL_COLUMNS = [
    ("present", "P"),
    ("late", "L"),
    ("half_day", "H"),
    ("absent", "A"),
    ("leave", "LV"),
    ("early_left", "EL"),
    ("missing", "No In/Out"),
    ("unpaid", "Unpaid days"),
]


def _month_xlsx(branch, first, dates, rows):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = f"{first:%b %Y}"
    ws.append([f"{branch.name} — staff attendance {first:%B %Y}"])
    ws.append(["EMP.code", "MAC.ID", "Name", "Designation"] + [d.day for d in dates] + [c for _s, c in TOTAL_COLUMNS])
    for cell in ws[2]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="E3EFEB")
    for r in rows:
        e = r["employee"]
        ws.append(
            [e.code, e.machine_id, e.full_name, e.designation]
            + [c.mark if c else "" for c in r["cells"]]
            + [r["totals"].get(s, 0) for s, _c in TOTAL_COLUMNS]
        )
    ws.append([])
    ws.append(["P = present, L = late, H = half day, A = absent, LV = leave, HD = holiday, – = off day"])
    ws.append(["e = early left; ! = In with no Out, or Out with no In (the day still counts)."])
    ws.append(["Unpaid days = absent days + days of unpaid leave (salary is deducted for these)."])
    ws.column_dimensions["C"].width = 24
    ws.column_dimensions["D"].width = 18
    ws.freeze_panes = "E3"
    buffer = io.BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="Staff-attendance-{first:%Y-%m}.xlsx"'
    return response


# --- Leave -----------------------------------------------------------------------------------


@login_required
def leaves(request):
    branch = _branch(request)
    can_decide = request.user.has_branch_perm(S.APPROVE_PERM, branch.id)
    if request.method == "POST":
        if not can_decide:
            raise PermissionDenied
        req = LeaveRequest.objects.filter(pk=request.POST.get("id"), branch=branch).select_related("employee").first()
        if req is None:
            raise Http404
        try:
            if request.POST.get("decision") == "cancel":
                S.cancel_leave(req, request.user)
            else:
                S.decide_leave(
                    req, request.user, request.POST.get("decision") == "approve", request.POST.get("note", "")
                )
            messages.success(request, _("Decision saved."))
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("hr:leaves")
    qs = LeaveRequest.objects.filter(branch=branch).select_related(
        "employee", "leave_type", "requested_by", "decided_by"
    )
    return render(
        request,
        "hr/leaves.html",
        {
            "pending": qs.filter(status=LeaveRequest.Status.PENDING).order_by("starts_on"),
            "recent": qs.exclude(status=LeaveRequest.Status.PENDING).order_by("-starts_on")[:100],
            "can_decide": can_decide,
        },
    )


def _leave_form(request, employee, back):
    form = LeaveForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            S.request_leave(employee, d["leave_type"], d["starts_on"], d["ends_on"], d["reason"], request.user)
            messages.success(request, _("Leave request saved. It counts once the principal approves it."))
            return redirect(back)
        except ValueError as exc:
            form.add_error(None, str(exc))
    return render(request, "hr/leave_form.html", {"form": form, "employee": employee, "back": back})


@login_required
def leave_new(request, employee_id):
    branch = _branch(request, S.LEAVE_PERM)
    e = _employee(branch, employee_id)
    return _leave_form(request, e, reverse("hr:employee", args=[e.id]))


# --- Self-service ----------------------------------------------------------------------------


def _me(request):
    e = Employee.objects.filter(user=request.user).select_related("branch").first()
    if e is None:
        raise Http404
    return e


@login_required
def mine(request):
    e = _me(request)
    first = _month(request)
    return render(
        request,
        "hr/mine.html",
        {
            "employee": e,
            "month": first,
            "days": StaffDay.objects.filter(employee=e, date__gte=first, date__lte=_month_end(first)),
            "balance": S.leave_balance(e, _session()),
            "leaves": e.leave_requests.select_related("leave_type").order_by("-starts_on")[:20],
        },
    )


@login_required
def my_leave(request):
    e = _me(request)
    return _leave_form(request, e, reverse("hr:mine"))


@login_required
@require_POST
def my_leave_cancel(request, leave_id):
    e = _me(request)
    req = LeaveRequest.objects.filter(pk=leave_id, employee=e, status=LeaveRequest.Status.PENDING).first()
    if req is None:
        raise Http404
    S.cancel_leave(req, request.user)
    messages.success(request, _("Leave request withdrawn."))
    return redirect("hr:mine")


# ---------- Attendance machine (Setup → Attendance machine; project lead, 31 Oct 2026) ----------
@login_required
def machines(request):
    """ZKTeco machines on the office network: add, test the connection, read punches now."""
    from . import zk
    from .models import AttendanceMachine

    branch = _branch(request, "hr.view_attendancemachine")
    can_edit = request.user.has_branch_perm("hr.change_attendancemachine", branch.id)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        action = request.POST.get("action")
        machine = AttendanceMachine.objects.filter(pk=request.POST.get("machine") or 0, branch=branch).first()
        if action == "save":
            host = request.POST.get("host", "").strip()
            try:
                port = int(request.POST.get("port") or zk.DEFAULT_PORT)
                key = int(request.POST.get("comm_key") or 0)
            except ValueError:
                port, key = -1, -1
            if not host or port <= 0 or key < 0:
                messages.error(request, _("Give the machine's IP address, port and comm key (numbers)."))
                return redirect("hr:machines")
            machine = machine or AttendanceMachine(branch=branch, added_by=request.user)
            machine.name = request.POST.get("name", "").strip()[:80] or _("Attendance machine")
            machine.host, machine.port, machine.comm_key = host[:60], port, key
            machine.auto_read = request.POST.get("auto_read") == "on"
            machine.is_active = request.POST.get("is_active", "on") == "on"
            machine.save()
            messages.success(request, _("Machine saved."))
        elif machine and action == "test":
            try:
                reading = zk.read(machine.host, machine.port, machine.comm_key, with_punches=False)
                clock = reading.clock.strftime("%d %b %Y %H:%M") if reading.clock else "?"
                messages.success(
                    request,
                    _("Connected (%(t)s). Machine clock %(c)s · %(u)s users · %(r)s records.")
                    % {"t": reading.transport.upper(), "c": clock, "u": reading.users, "r": reading.records},
                )
            except (zk.MachineError, OSError) as error:
                messages.error(request, _("The machine did not answer: %(e)s") % {"e": error})
        elif machine and action == "read":
            result = S.read_machine(machine, request.user)
            (messages.success if machine.last_ok else messages.error)(request, result)
        elif machine and action == "match":
            # Only the rows a person ticked; each with the staff member chosen in its row (R7-7).
            if not request.user.has_branch_perm(S.EDIT_PERM, branch.id):
                raise PermissionDenied
            pairs = [
                (number, request.POST.get(f"staff_{number}"))
                for number in request.POST.getlist("use")
                if str(request.POST.get(f"staff_{number}") or "").isdigit()
            ]
            saved, problems = S.give_machine_ids(branch, pairs)
            if saved:
                messages.success(
                    request,
                    _("Biometric ID given to %(n)s staff: %(names)s. Their punches come in at the next reading.")
                    % {"n": len(saved), "names": ", ".join(f"{e.full_name} ({e.machine_id})" for e in saved)},
                )
            for p in problems:
                messages.error(request, p)
            if not pairs:
                messages.error(request, _("Tick the rows to save and choose the staff member in each."))
        return redirect("hr:machines")
    from apps.core.escpos import local_networks

    rows = list(AttendanceMachine.objects.filter(branch=branch))
    networks = local_networks()
    for m in rows:  # a machine on another network can never answer: say so before anyone presses a button
        try:
            ip = ipaddress.ip_address(m.host)
        except ValueError:
            ip = None
        m.other_network = bool(ip and networks) and not any(ip in n for n in networks)
    here = [str(n.network_address).rsplit(".", 1)[0] + ".x" for n in networks]
    for m in rows:
        m.match, m.free_staff = S.match_rows(m)
    can_match = can_edit and request.user.has_branch_perm(S.EDIT_PERM, branch.id)
    return render(
        request,
        "hr/machines.html",
        {"branch": branch, "machines": rows, "can_edit": can_edit, "can_match": can_match, "here": here},
    )


# ---------- Staff duty times (Setup → Staff duty times; project lead, 6 Nov 2026) ----------
@login_required
def duty_times(request):
    """In and Out time of each staff type, from a date: summer and winter times keep their own dates, so earlier
    days keep the times that applied then."""
    branch = _branch(request, "hr.view_hrsettings")
    can_edit = request.user.has_branch_perm("hr.change_hrsettings", branch.id)
    types = Employee.StaffType.choices
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        if request.POST.get("action") == "remove":
            date = _date(request.POST.get("starts_from"), None)
            removed, _detail = DutyTime.objects.filter(branch=branch, starts_from=date).delete()
            if removed:
                S.rebuild_days(branch, max(date, timezone.localdate() - dt.timedelta(days=62)), timezone.localdate())
                messages.success(request, _("Times from %(d)s removed.") % {"d": date})
            return redirect("hr:duty_times")
        date = _date(request.POST.get("starts_from"), None)
        label = request.POST.get("label", "").strip()[:60]
        rows, problems = [], []
        for value, name in types:
            starts, ends = _clock(request.POST.get(f"in_{value}")), _clock(request.POST.get(f"out_{value}"))
            if not starts and not ends:
                continue
            if not starts or not ends or ends <= starts:
                problems.append(str(name))
                continue
            try:
                grace = max(min(int(request.POST.get(f"grace_{value}") or 0), 120), 0)
            except ValueError:
                grace = 0
            rows.append((value, starts, ends, grace, _clock(request.POST.get(f"half_{value}"))))
        if date is None or problems or not rows:
            messages.error(
                request,
                _("Give the date the times start from, and an In time before the Out time for: %(t)s.")
                % {"t": ", ".join(problems) or _("at least one staff type")},
            )
            return redirect("hr:duty_times")
        for value, starts, ends, grace, half in rows:
            DutyTime.objects.update_or_create(
                branch=branch, staff_type=value, starts_from=date,
                defaults={"duty_starts": starts, "duty_ends": ends, "grace_minutes": grace,
                          "half_day_after": half, "label": label},
            )  # fmt: skip
        today = timezone.localdate()
        if date <= today:  # days already worked out from this date are worked out again with the new times
            S.rebuild_days(branch, max(date, today - dt.timedelta(days=62)), today)
        messages.success(request, _("Staff duty times saved, from %(d)s.") % {"d": date.strftime("%d %b %Y")})
        return redirect("hr:duty_times")
    today = timezone.localdate()
    lookup = S.duty_lookup(branch)
    current = [(value, name, lookup(value, today)) for value, name in types]
    history = defaultdict(list)
    for d in DutyTime.objects.filter(branch=branch).order_by("-starts_from", "staff_type"):
        history[d.starts_from].append(d)
    return render(
        request,
        "hr/duty_times.html",
        {
            "branch": branch,
            "can_edit": can_edit,
            "current": current,
            "history": sorted(history.items(), reverse=True),
            "today": today,
        },
    )
