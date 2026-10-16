# Changelog

## 0.8.1 — 2026-10-16 — Staff: confirmed timings and unpaid leave

Changed
- Samanabad staff duty time 07:45–13:45, Monday to Saturday (seeded; editable in Setup).
- Leave has no fixed allowance and is unpaid; the monthly sheet and its Excel show "unpaid days" (absent + unpaid leave) for salary deduction.

Not deployed.

## 0.8.0 — 2026-10-16 — Milestone 3a: Staff (HR) and staff attendance

Added
- Staff register: add, edit, search; staff list import from Excel with row-by-row checks.
- Attendance machine file import (Excel, CSV, or the machine's .dat/.txt log), matched by machine ID; the same file imported twice adds nothing.
- Daily status per person: present, late, half day, absent, on leave, holiday, off day — from per-branch duty time, grace minutes and half-day time.
- Principal corrections with a reason, kept and audited; daily and monthly views; monthly Excel for payroll.
- Leave requests (by the person or the principal), approval by someone else, balances per session; "My attendance" for staff with a login.
- Row-level security on staff tables; Urdu translations; 133 automated tests.

Fixed
- Father's CNIC typed with dashes (33100-1234567-1) was refused on the student form.

Not deployed.

## 0.7.1 — 2026-10-16 — Fees: confirmed rules and JazzCash files

Changed
- Royalty is 8% of all fees received in the month (confirmed).
- Re-admission column removed from the voucher (there is no re-admission fee).

Added
- Voucher list for JazzCash: unpaid vouchers of a month as an Excel file.
- Payments from a file: JazzCash's (or a bank's) paid list imported by Voucher ID; every row checked first (unknown or cancelled vouchers, repeats, already recorded), then recorded with the normal rules.
- 121 automated tests.

Not deployed.

## 0.7.0 — 2026-10-16 — Milestone 2b: Fees

Added
- Fee heads matching the school's voucher; per-branch fee rates by class with start dates; Samanabad fees seeded as confirmed.
- Father's name and CNIC on the student record and Excel import; brothers and sisters recognised by CNIC for the sibling fee.
- Monthly vouchers for the whole branch or chosen classes, with a check before anything is made; annual charges in April, summer vacation work in July; students already billed are skipped.
- Single-student vouchers: admission, registration, annual or other charges, several months together.
- Unpaid balance carried to the next voucher with the Rs 200 late fine once per late voucher; due date the 10th or the day made.
- Printed voucher: A4 with School, Bank and Student copies, barcode, bank details from Setup, and the Fee Payment Options back page (English and Urdu).
- Receive payment by scanning or typing the Voucher ID: cash, bank deposit, transfer, JazzCash, Alfa app; transaction ID required for non-cash; receipt; reversal with reason.
- Student fee account, special discounts with approval by someone else, defaulters list, daily collection, royalty statement for head office.
- Row-level security on fee tables; 119 automated tests.

Not deployed.

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
