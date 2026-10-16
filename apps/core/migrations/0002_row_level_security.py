"""Second lock on branch data: PostgreSQL row-level security (DECISIONS D-006).

Table list is frozen here on purpose; new branch-owned tables get their own migration.
"""

from django.db import migrations

TABLES = [
    "organisation_campus",
    "academics_section",
    "people_guardian",
    "people_student",
    "people_enrolment",
    "attendance_attendancerecord",
    "attendance_sectionattendance",
    "diary_diary",
]

FUNCTION = """
CREATE OR REPLACE FUNCTION tasems_branch_allowed(b bigint) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT coalesce(current_setting('tasems.enforce', true), '') <> 'on'
        OR b = ANY (string_to_array(nullif(current_setting('tasems.branches', true), ''), ',')::bigint[])
$$;
"""


def enable(table):
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; "
        f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY; "
        f"CREATE POLICY branch_isolation ON {table} "
        f"USING (tasems_branch_allowed(branch_id)) WITH CHECK (tasems_branch_allowed(branch_id));"
    )


def disable(table):
    return (
        f"DROP POLICY IF EXISTS branch_isolation ON {table}; "
        f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY; "
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("organisation", "0002_campus"),
        ("academics", "0005_saturday_classes"),
        ("people", "0001_initial"),
        ("attendance", "0001_initial"),
        ("diary", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(FUNCTION, "DROP FUNCTION IF EXISTS tasems_branch_allowed(bigint);"),
        *[migrations.RunSQL(enable(t), disable(t)) for t in TABLES],
    ]
