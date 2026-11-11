"""Row-level security for hiring tables (see core/migrations/0002), and the starting list of posts (R8-17)."""

from django.db import migrations

TABLES = [
    "hiring_candidate", "hiring_candidatecv", "hiring_cvfile", "hiring_education", "hiring_experience",
    "hiring_vacancy", "hiring_application", "hiring_applicationstep", "hiring_interviewsheet",
]  # fmt: skip

# The staff designations, plus Teacher and the posts the lead added on 11 Nov 2026.
POSTS = [
    ("Teacher", True), ("Senior Teacher", True), ("Junior Teacher", True), ("Qari", True), ("Principal", False),
    ("Vice Principal", False), ("Coordinator", False), ("Director", False), ("Accountant", False), ("Admin", False),
    ("Designer", False), ("Content Creator", False), ("Graphic Designer", False), ("Typist", False),
    ("Aapa", False), ("Guard", False), ("Office boy", False), ("Janitorial staff", False),
    ("Helping staff / Other", False), ("Lawyer", False),
]  # fmt: skip


def enable(table):
    return (
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY; ALTER TABLE {table} FORCE ROW LEVEL SECURITY; "
        f"CREATE POLICY branch_isolation ON {table} "
        f"USING (tasems_branch_allowed(branch_id)) WITH CHECK (tasems_branch_allowed(branch_id));"
    )


def disable(table):
    return (
        f"DROP POLICY IF EXISTS branch_isolation ON {table}; ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY; "
        f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;"
    )


def add_posts(apps, schema_editor):
    Post = apps.get_model("hiring", "Post")
    for order, (name, teaching) in enumerate(POSTS, start=1):
        Post.objects.get_or_create(name=name, defaults={"is_teaching": teaching, "order": order * 10})


class Migration(migrations.Migration):
    dependencies = [("hiring", "0001_initial"), ("core", "0002_row_level_security")]

    operations = [migrations.RunSQL(enable(t), disable(t)) for t in TABLES] + [
        migrations.RunPython(add_posts, migrations.RunPython.noop)
    ]
