"""Database-level branch isolation (PostgreSQL row-level security) — the second lock.

The first lock is in the application (`Model.objects.for_user`). This second lock is in
the database itself: during a signed-in web request, PostgreSQL only returns or accepts
rows whose `branch_id` belongs to the user's branches, even if application code forgets
to filter. Background jobs and management commands run without the restriction.

It only works when the application connects as an ordinary database role. A PostgreSQL
superuser, or a role with BYPASSRLS, ignores these rules — `manage.py check_security`
reports that. See docs/DEPLOYMENT.md.
"""

from contextlib import contextmanager

from django.db import connection

# Every table that has a branch_id column (branch-owned data).
RLS_TABLES = [
    "organisation_campus",
    "academics_section",
    "people_guardian",
    "people_student",
    "people_enrolment",
    "attendance_attendancerecord",
    "attendance_sectionattendance",
    "diary_diary",
    "exams_mark",
    "exams_resultremark",
    "exams_rating",
]

# Policies are created by migrations: core/0002_row_level_security.py and exams/0002_row_level_security.py.


@contextmanager
def branch_scope(branch_ids):
    """Within this block the database only shows rows of `branch_ids`."""
    ids = ",".join(str(int(i)) for i in sorted(branch_ids))
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('tasems.enforce', 'on', false), set_config('tasems.branches', %s, false)", [ids]
        )
    try:
        yield
    finally:
        # Every request sets its own scope first, so a failed reset cannot leak access;
        # resetting keeps reused connections clean for non-request work.
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('tasems.enforce', '', false), set_config('tasems.branches', '', false)"
                )
        except Exception:  # noqa: BLE001 - connection may be closed or in a failed transaction
            connection.close()


class RowLevelSecurityMiddleware:
    """Applies the user's branches to the database for the whole request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            branch_ids = set()
        else:
            branch_ids = user.accessible_branch_ids()
        with branch_scope(branch_ids):
            return self.get_response(request)
