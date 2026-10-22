"""Staff attendance and leave rules (DECISIONS D-042 to D-045).

A working day (branch working weekday, not a holiday) becomes:
* On leave — an approved leave covers it and the person did not punch in;
* Present / Late / Half day — from the first punch of the day, compared with duty time + grace
  minutes and the half-day time (late and half day are only worked out once duty time is set);
* Absent — no punch, for days already over (today stays empty until the person punches in).
Off days and holidays are recorded as such; anyone who punches in on one is Present.
A day a principal corrected by hand keeps the correction.
"""

import csv
import datetime as dt
import io
import re
from collections import defaultdict
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from openpyxl import load_workbook

from apps.core.models import AuditEvent

from .models import Employee, Holiday, HRSettings, LeaveRequest, LeaveType, Punch, StaffDay

VIEW_PERM = "hr.view_employee"
EDIT_PERM = "hr.change_employee"
ADD_PERM = "hr.add_employee"
IMPORT_PERM = "hr.add_punch"
CORRECT_PERM = "hr.change_staffday"
LEAVE_PERM = "hr.add_leaverequest"
APPROVE_PERM = "hr.approve_leaverequest"


def dates_between(start, end):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def holidays(branch, start, end):
    """date → holiday name; a branch's own holiday wins over a network-wide one."""
    out = {}
    for h in Holiday.objects.filter(
        Q(branch__isnull=True) | Q(branch=branch), date__gte=start, date__lte=end, staff_off=True
    ).order_by("branch_id"):
        if h.date not in out or h.branch_id:
            out[h.date] = h.name
    return out


def kind_of_day(hr, holiday_map, date):
    if date in holiday_map:
        return "holiday"
    if date.weekday() not in (hr.working_days or []):
        return "off"
    return "work"


def working_days_between(hr, holiday_map, start, end):
    return sum(1 for d in dates_between(start, end) if kind_of_day(hr, holiday_map, d) == "work")


def _late_status(hr, first_in):
    if hr.half_day_after and first_in > hr.half_day_after:
        return StaffDay.Status.HALF_DAY
    if hr.duty_starts:
        limit = (dt.datetime.combine(dt.date.today(), hr.duty_starts) + dt.timedelta(minutes=hr.grace_minutes)).time()
        if first_in > limit:
            return StaffDay.Status.LATE
    return StaffDay.Status.PRESENT


@transaction.atomic
def rebuild_days(branch, start, end, employee_ids=None):
    """Works out StaffDay rows for every employee (or the ones given) between two dates.
    Corrected days are left alone. Returns the number of days written."""
    today = timezone.localdate()
    end = min(end, today)
    if end < start:
        return 0
    hr = HRSettings.for_branch(branch)
    holiday_map = holidays(branch, start, end)
    employees = Employee.objects.filter(branch=branch, joined_on__lte=end).filter(
        Q(left_on__isnull=True) | Q(left_on__gte=start)
    )
    if employee_ids is not None:
        employees = employees.filter(id__in=employee_ids)
    employees = list(employees)
    ids = [e.id for e in employees]

    tz = timezone.get_current_timezone()
    punches = defaultdict(list)
    first_moment = dt.datetime.combine(start, dt.time.min, tzinfo=tz)
    last_moment = dt.datetime.combine(end + dt.timedelta(days=1), dt.time.min, tzinfo=tz)
    found = Punch.objects.filter(employee_id__in=ids, at__gte=first_moment, at__lt=last_moment)
    for employee_id, at in found.values_list("employee_id", "at"):
        local = timezone.localtime(at, tz)
        punches[(employee_id, local.date())].append(local.time().replace(microsecond=0))

    leaves = defaultdict(list)
    for lr in LeaveRequest.objects.filter(
        employee_id__in=ids, status=LeaveRequest.Status.APPROVED, starts_on__lte=end, ends_on__gte=start
    ):
        leaves[lr.employee_id].append(lr)

    existing = {
        (d.employee_id, d.date): d for d in StaffDay.objects.filter(employee_id__in=ids, date__gte=start, date__lte=end)
    }
    to_create, to_update = [], []
    for e in employees:
        for date in dates_between(start, end):
            if not e.employed_on(date):
                continue
            current = existing.get((e.id, date))
            if current and current.is_corrected:
                continue
            times = sorted(punches.get((e.id, date), []))
            kind = kind_of_day(hr, holiday_map, date)
            leave = next((lr for lr in leaves[e.id] if lr.starts_on <= date <= lr.ends_on), None)
            first_in = times[0] if times else None
            last_out = times[-1] if len(times) > 1 else None
            note = ""
            if times:
                status = _late_status(hr, first_in) if kind == "work" else StaffDay.Status.PRESENT
                if kind != "work":
                    note = holiday_map.get(date, "") or _("Worked on an off day")
                leave = None if kind != "work" else leave
                if leave:
                    note = _("Came in during approved leave")
                    leave = None
            elif kind == "holiday":
                status, note = StaffDay.Status.HOLIDAY, holiday_map[date]
            elif kind == "off":
                status = StaffDay.Status.OFF
            elif leave:
                status = StaffDay.Status.LEAVE
            elif date < today:
                status = StaffDay.Status.ABSENT
            else:
                continue  # today, not in yet
            values = {
                "first_in": first_in,
                "last_out": last_out,
                "status": status,
                "leave": leave,
                "note": note[:200],
            }
            if current:
                if any(getattr(current, k) != v for k, v in values.items()):
                    for k, v in values.items():
                        setattr(current, k, v)
                    to_update.append(current)
            else:
                to_create.append(StaffDay(branch_id=branch.id, employee=e, date=date, **values))
        if not e.employed_on(end):
            StaffDay.objects.filter(employee=e, date__gt=e.left_on or end, is_corrected=False).delete()
    StaffDay.objects.bulk_create(to_create)
    StaffDay.objects.bulk_update(to_update, ["first_in", "last_out", "status", "leave", "note", "updated_at"])
    return len(to_create) + len(to_update)


@transaction.atomic
def correct_day(employee, date, status, note, user, first_in=None, last_out=None):
    """A principal's correction (e.g. machine was down). Kept until removed; audited."""
    day = StaffDay.objects.filter(employee=employee, date=date).first()
    before = {"status": day.status, "first_in": str(day.first_in or "")} if day else {}
    if day is None:
        day = StaffDay(branch_id=employee.branch_id, employee=employee, date=date)
    day.status, day.note, day.is_corrected, day.corrected_by = status, note[:200], True, user
    day.first_in, day.last_out = first_in, last_out
    day.save()
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.UPDATE,
        model_label="hr.StaffDay",
        object_id=f"{employee.pk}:{date}",
        object_repr=f"{employee} {date:%d %b %Y}"[:255],
        branch_id=employee.branch_id,
        changes={"from": before, "to": {"status": status, "first_in": str(first_in or "")}, "reason": note},
    )
    return day


@transaction.atomic
def remove_correction(employee, date, user):
    StaffDay.objects.filter(employee=employee, date=date).update(is_corrected=False, corrected_by=None, note="")
    rebuild_days(employee.branch, date, date, [employee.id])
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.UPDATE,
        model_label="hr.StaffDay",
        object_id=f"{employee.pk}:{date}",
        object_repr=f"{employee} {date:%d %b %Y}"[:255],
        branch_id=employee.branch_id,
        changes={"correction": "removed"},
    )


# --- Leave -----------------------------------------------------------------------------------


def count_leave_days(employee, start, end):
    hr = HRSettings.for_branch(employee.branch)
    return working_days_between(hr, holidays(employee.branch, start, end), start, end)


def overlapping_leave(employee, start, end, exclude=None):
    qs = LeaveRequest.objects.filter(
        employee=employee,
        status__in=[LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED],
        starts_on__lte=end,
        ends_on__gte=start,
    )
    if exclude:
        qs = qs.exclude(pk=exclude.pk)
    return qs.first()


@transaction.atomic
def request_leave(employee, leave_type, start, end, reason, user):
    clash = overlapping_leave(employee, start, end)
    if clash:
        raise ValueError(_("There is already a leave request for some of these days."))
    return LeaveRequest.objects.create(
        branch_id=employee.branch_id,
        employee=employee,
        leave_type=leave_type,
        starts_on=start,
        ends_on=end,
        days=count_leave_days(employee, start, end),
        reason=reason,
        requested_by=user,
    )


@transaction.atomic
def decide_leave(request, user, approve, note=""):
    if request.status != LeaveRequest.Status.PENDING:
        raise ValueError(_("This request has already been decided."))
    if request.requested_by_id == user.id and not user.is_superuser:
        raise ValueError(_("Someone else must approve a leave you asked for."))
    if getattr(request.employee, "user_id", None) == user.id and not user.is_superuser:
        raise ValueError(_("You cannot approve your own leave."))
    request.status = LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    request.decided_by, request.decided_at, request.decision_note = user, timezone.now(), note[:200]
    request.save()
    rebuild_days(request.employee.branch, request.starts_on, request.ends_on, [request.employee_id])


@transaction.atomic
def cancel_leave(request, user):
    was_approved = request.status == LeaveRequest.Status.APPROVED
    request.status = LeaveRequest.Status.CANCELLED
    request.decided_by, request.decided_at = user, timezone.now()
    request.save()
    if was_approved:
        rebuild_days(request.employee.branch, request.starts_on, request.ends_on, [request.employee_id])


def leave_balance(employee, session):
    """[(leave type, allowed or None, approved days used, pending days, days left or None)]
    for the academic session."""
    rows = []
    if session is None:
        return rows
    taken = LeaveRequest.objects.filter(
        employee=employee, starts_on__lte=session.ends_on, ends_on__gte=session.starts_on
    )
    used = dict(
        taken.filter(status=LeaveRequest.Status.APPROVED)
        .values("leave_type")
        .annotate(n=Sum("days"))
        .values_list("leave_type", "n")
    )
    pending = dict(
        taken.filter(status=LeaveRequest.Status.PENDING)
        .values("leave_type")
        .annotate(n=Sum("days"))
        .values_list("leave_type", "n")
    )
    for t in LeaveType.objects.filter(is_active=True):
        taken_days = used.get(t.id, 0)
        left = None if t.days_per_year is None else t.days_per_year - taken_days
        rows.append((t, t.days_per_year, taken_days, pending.get(t.id, 0), left))
    return rows


# --- Attendance machine files ----------------------------------------------------------------

ID_HEADERS = {
    "acno", "userid", "empno", "enrollno", "enrollnumber", "employeeid", "empid", "id", "no", "badgenumber",
    "personid", "staffid", "machineid", "pin", "userno", "employeeno", "emplcode",
}  # fmt: skip
DATETIME_HEADERS = {"datetime", "checktime", "punchtime", "time", "logtime", "attendancetime", "timestamp"}
DATE_HEADERS = {"date", "punchdate", "attendancedate", "logdate"}
TIME_ONLY_HEADERS = {"time", "punchtime", "intime", "logtime"}
MAX_BYTES = 10 * 1024 * 1024
MAX_PUNCHES = 100_000

DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d-%b-%Y", "%d/%m/%y")
TIME_FORMATS = ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p", "%I:%M%p")


def _key(text):
    return re.sub(r"[^a-z]", "", str(text or "").lower())


def parse_moment(value, time_value=None):
    """A date-and-time from a machine file cell (or a date cell plus a time cell)."""
    if isinstance(value, dt.datetime) and time_value is None:
        return value.replace(microsecond=0)
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        date = value
    elif isinstance(value, dt.datetime):
        date = value.date()
    else:
        text = str(value or "").strip()
        if time_value is None:
            for df in DATE_FORMATS:
                for tf in TIME_FORMATS:
                    try:
                        return dt.datetime.strptime(text, f"{df} {tf}")
                    except ValueError:
                        continue
            raise ValueError(text)
        for df in DATE_FORMATS:
            try:
                date = dt.datetime.strptime(text.split(" ")[0], df).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError(text)
    if isinstance(time_value, dt.time):
        return dt.datetime.combine(date, time_value.replace(microsecond=0))
    if isinstance(time_value, dt.datetime):
        return dt.datetime.combine(date, time_value.time().replace(microsecond=0))
    text = str(time_value or "").strip()
    for tf in TIME_FORMATS:
        try:
            return dt.datetime.combine(date, dt.datetime.strptime(text.upper(), tf).time())
        except ValueError:
            continue
    raise ValueError(text)


@dataclass
class MachineFile:
    punches: list = field(default_factory=list)  # (machine_id, naive local datetime)
    errors: list = field(default_factory=list)
    bad_lines: int = 0


def _rows_from_table(rows, result):
    rows = iter(rows)
    header = None
    for _i in range(10):
        candidate = next(rows, None)
        if candidate is None:
            break
        keys = [_key(c) for c in candidate]
        if any(k in ID_HEADERS for k in keys) and any(k in DATETIME_HEADERS | DATE_HEADERS for k in keys):
            header = keys
            break
    if header is None:
        result.errors.append(_("Could not find the machine ID and date/time columns in the file."))
        return
    id_col = next(i for i, k in enumerate(header) if k in ID_HEADERS)
    date_col = next((i for i, k in enumerate(header) if k in DATE_HEADERS), None)
    time_col = None
    if date_col is not None:
        time_col = next((i for i, k in enumerate(header) if k in TIME_ONLY_HEADERS and i != date_col), None)
    dt_col = (
        None if time_col is not None else next((i for i, k in enumerate(header) if k in DATETIME_HEADERS), date_col)
    )
    for row in rows:
        if not row or all(c in (None, "") for c in row):
            continue
        try:
            raw_id = row[id_col]
            if isinstance(raw_id, float) and raw_id.is_integer():
                raw_id = int(raw_id)
            machine_id = str(raw_id).strip()
            moment = parse_moment(row[date_col], row[time_col]) if time_col is not None else parse_moment(row[dt_col])
            if not machine_id:
                raise ValueError
            result.punches.append((machine_id, moment))
        except (ValueError, IndexError, TypeError):
            result.bad_lines += 1
        if len(result.punches) > MAX_PUNCHES:
            result.errors.append(_("The file has too many punches. Export one month at a time."))
            return


def read_machine_file(content, filename):
    """Reads an attendance machine export: Excel (.xlsx), CSV, or the machine's own text log
    (.dat/.txt: ID then date and time on each line). Nothing is saved."""
    result = MachineFile()
    name = filename.lower()
    if name.endswith(".xlsx"):
        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:  # noqa: BLE001 - any unreadable file gets the same message
            result.errors.append(_("This file could not be opened. Save it as an Excel .xlsx file and try again."))
            return result
        _rows_from_table(wb.worksheets[0].iter_rows(values_only=True), result)
        return result
    text = content.decode("utf-8-sig", errors="replace")
    if name.endswith(".csv"):
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t") if text.strip() else csv.excel
        _rows_from_table(csv.reader(io.StringIO(text), dialect), result)
        return result
    # .dat / .txt log: "  12\t2026-10-14 07:52:10\t1\t0\t1\t0"
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            if line.strip():
                result.bad_lines += 1
            continue
        try:
            result.punches.append((parts[0], parse_moment(f"{parts[1]} {parts[2]}")))
        except ValueError:
            result.bad_lines += 1
    if not result.punches and not result.errors:
        result.errors.append(_("No punches found. Export the attendance log from the machine and try again."))
    return result


@dataclass
class PunchCheck:
    matched: list = field(default_factory=list)  # (employee, aware datetime)
    unknown_ids: dict = field(default_factory=dict)  # machine id → count
    already: int = 0
    first: dt.date | None = None
    last: dt.date | None = None
    future: int = 0

    @property
    def employees(self):
        return len({e.id for e, _a in self.matched})


def check_punches(branch, machine_file):
    by_machine = {e.machine_id: e for e in Employee.objects.filter(branch=branch).exclude(machine_id="")}
    tz = timezone.get_current_timezone()
    now = timezone.now()
    result = PunchCheck()
    seen = set()
    for machine_id, moment in machine_file.punches:
        e = by_machine.get(machine_id) or by_machine.get(machine_id.lstrip("0"))
        if e is None:
            result.unknown_ids[machine_id] = result.unknown_ids.get(machine_id, 0) + 1
            continue
        aware = timezone.make_aware(moment, tz) if timezone.is_naive(moment) else moment
        if aware > now + dt.timedelta(minutes=5):
            result.future += 1
            continue
        if (e.id, aware) in seen:
            continue
        seen.add((e.id, aware))
        result.matched.append((e, aware))
    if result.matched:
        moments = [a for _e, a in result.matched]
        result.first = timezone.localtime(min(moments)).date()
        result.last = timezone.localtime(max(moments)).date()
        existing = set(
            Punch.objects.filter(
                employee_id__in={e.id for e, _a in result.matched}, at__gte=min(moments), at__lte=max(moments)
            ).values_list("employee_id", "at")
        )
        result.already = sum(1 for e, a in result.matched if (e.id, a) in existing)
    return result


@transaction.atomic
def save_punches(branch, check, user, batch):
    rows = [
        Punch(branch_id=branch.id, employee=e, at=a, source=Punch.Source.MACHINE, batch=batch[:40], created_by=user)
        for e, a in check.matched
    ]
    created = Punch.objects.bulk_create(rows, ignore_conflicts=True, batch_size=2000)
    if check.first:
        rebuild_days(branch, check.first, check.last)
    AuditEvent.objects.create(
        actor=user,
        action=AuditEvent.Action.CREATE,
        model_label="hr.Punch",
        object_id=f"import:{batch}"[:64],
        object_repr=f"Attendance machine file {batch}"[:255],
        branch_id=branch.id,
        changes={"punches": len(rows) - check.already, "from": str(check.first), "to": str(check.last)},
    )
    return len(created) - check.already


# --- Reports ---------------------------------------------------------------------------------


def day_summary(branch, date):
    days = {d.employee_id: d for d in StaffDay.objects.filter(branch=branch, date=date)}
    employees = [
        e for e in Employee.objects.filter(branch=branch).order_by("staff_type", "full_name") if e.employed_on(date)
    ]
    rows = [(e, days.get(e.id)) for e in employees]
    counts = defaultdict(int)
    for _e, d in rows:
        counts[d.status if d else "none"] += 1
    counts["in"] = counts["present"] + counts["late"] + counts["half_day"]
    return rows, dict(counts)


def month_sheet(branch, month_start_date):
    first = month_start_date
    last = (first.replace(day=28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
    dates = list(dates_between(first, last))
    days = defaultdict(dict)
    for d in StaffDay.objects.filter(branch=branch, date__gte=first, date__lte=last).select_related(
        "leave__leave_type"
    ):
        days[d.employee_id][d.date] = d
    employees = [
        e
        for e in Employee.objects.filter(branch=branch, joined_on__lte=last)
        .filter(Q(left_on__isnull=True) | Q(left_on__gte=first))
        .order_by("staff_type", "full_name")
    ]
    rows = []
    for e in employees:
        cells = [days[e.id].get(d) for d in dates]
        totals = defaultdict(int)
        for c in cells:
            if c:
                totals[c.status] += 1
                # Salary is deducted for absence and for unpaid leave (confirmed 16 Oct 2026).
                if c.status == StaffDay.Status.ABSENT or (
                    c.status == StaffDay.Status.LEAVE and not (c.leave and c.leave.leave_type.is_paid)
                ):
                    totals["unpaid"] += 1
        rows.append({"employee": e, "cells": cells, "totals": dict(totals)})
    return dates, rows
