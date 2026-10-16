# Changelog

## 0.6.0 — 2026-10-16 — Milestone 2a: Examinations and results

Added
- Approved result pattern stored as data: Final 50, Mid-Term 25, Attendance 5 (automatic), Discipline 5, Neatness 5, Summer vacation work 5, Class work & homework 5.
- Exams (network-wide or per branch) with papers per class and subject, each with its own total.
- Marks entry per paper and section: half marks, absent / absent with leave, checks against the paper total, nothing saved until all values are valid; corrections audited.
- Teacher ratings screen for discipline (once per student) and neatness, summer work, class work (per subject).
- Results per section: percentage, grade, pass, positions (1st–3rd), and exactly what is still missing per student.
- Mid-Term progress report and annual result card: one A4 page per student, PDF for a student or the whole section; class teacher and principal remarks.
- Row-level security on marks, ratings and remarks.
- 92 automated tests.

Not deployed.

## 0.5.0 — 2026-10-16 — Milestone 1f: Pilot hardening and head office view

Added
- PostgreSQL row-level security on every branch-owned table; each signed-in request is limited to the user's branches inside the database too.
- `manage.py check_security` for go-live (database role, row-level security, DEBUG, keys, HTTPS settings).
- Fonts served from TASEMS itself as small WOFF2 files; no outside font service.
- Head office home: today's registers taken and diaries published, per branch, with unfinished branches first.
- `/healthz` for uptime monitoring.
- Production setup: Docker Compose with Caddy (automatic HTTPS), ordinary `tasems_app` database role, WhiteNoise static files, only logo files publicly served.
- Encrypted nightly backup script and restore-drill script; deployment guide.
- Uploaded Excel files older than a day are removed automatically.
- 79 automated tests.

Not deployed.

## 0.4.0 — 2026-10-16 — Milestone 1d: Daily Diary

Added
- Daily Learning Overview per section and school day, matching the school's current diary layout.
- In Class Learning and Home Learning Tasks per subject, with deadline defaulting to the next school day of that class.
- Subjects with nothing in a part of the diary are left out of that part; Urdu text detected and set right-to-left in Nastaliq.
- Draft and publish; class teacher writes own sections (today and up to 7 days ahead); principal and coordinator any day.
- Theme of the week, week number and quote: network-wide from head office, or per branch.
- One-page A4 PDF and a 1080-px-wide image for WhatsApp; fonts bundled with the system.
- Subjects of the Class 4 diary seeded; other classes' subjects entered by head office.
- 73 automated tests.

Not deployed.

## 0.3.0 — 2026-10-16 — Milestone 1c: Student attendance

Added
- Daily register per section (once a day): present by default; absent, leave and late with an optional note.
- Who can mark: class teacher for own sections, today only; principal and academic coordinator for any section and any past day of the session. Corrections are written to the audit log student by student.
- Draft kept on the phone if the connection drops; restored when the page is opened again.
- Absent students page with parent mobile (tap to call) and students absent 3 or more days in a row; printable.
- Today page: registers taken, attendance %, absent and leave counts, my classes; head office branch summary.
- 60 automated tests.

Not deployed.

## 0.2.0 — 2026-10-16 — Milestone 1b: Staff access and student register

Added
- Sign-in page (username or mobile number), lockout after 5 failed attempts in 15 minutes.
- Two-step sign-in for privileged roles: authenticator app (QR set-up), encrypted keys, codes cannot be reused, 8 one-time backup codes. Admin site uses the same sign-in.
- English and Urdu interface (Urdu right-to-left, Nastaliq font); language follows each user's preference.
- Branch switcher for head office and regional staff.
- Home screen: active students, Hifz students, missing parent contacts, unplaced students, students by stage, my classes, branch table for head office.
- Student register: search by name, admission number or parent mobile; filters by class, section, status; add and edit with class and primary contact; siblings share a parent contact; record history.
- Excel import: template download, row-by-row problem report, all-or-nothing save, sections created automatically (boys/girls from Class 6).
- 49 automated tests.

Not deployed.

## 0.1.0 — 2026-10-16 — Milestone 1a: Foundation

Added
- Django 5.2 project with PostgreSQL, environment-based settings, English/Urdu language setup, Pakistan time zone.
- Organisation: head offices, regions, branches (ownership and royalty %), academic sessions.
- Accounts: custom user, roles, scoped role assignments, role-based permission backend.
- Branch isolation helpers (`for_user`, `has_branch_perm`, scoped admin).
- Academics: class levels, subjects, curriculum mapping, sections.
- People: students, guardians, student–guardian links, enrolments.
- Append-only audit log.
- `seed_tasems` command (confirmed facts only): 15 class levels incl. Prep and Pre-9.
- Boys/girls separation from Class 6: section gender group and enrolment check.
- Campus (building) under Branch for separate boys/girls buildings; sections can be placed in a campus.
- 27 automated tests; GitHub Actions CI (lint, checks, migrations, tests); Dockerfile and docker-compose.

Not deployed.
