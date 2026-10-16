# Decisions log

Every architectural or scope decision is recorded here with its date, the options considered and the reason.
Approved decisions are not changed silently: a change gets a new entry that supersedes the old one.

Decision authority: the project lead at The Arqam Schools (Samanabad head office), per the master plan.

| ID | Date | Decision | Reason | Status |
| --- | --- | --- | --- | --- |
| D-001 | 2026-10-16 | Modular monolith: one application, strict internal modules (apps), one PostgreSQL database | Lowest cost and complexity for the scale (250,000+ students); modules can be split out later if one proves to need it | Approved (master plan) |
| D-002 | 2026-10-16 | Stack: Python 3.12 + Django 5.2 LTS + PostgreSQL 16. Staff screens server-rendered (Django templates + HTMX); parent app as an installable web app (PWA) later | **Supersedes the master plan's Next.js + NestJS recommendation.** The in-house team is one senior developer; Django gives login, permissions, migrations, admin, translations (Urdu) and security defaults built in, so one person can maintain it. Python is also the strongest ecosystem for the AI work (RAG, OCR). Django 5.2 is a long-term-support release | Approved — stack choice delegated to Claude by the project lead |
| D-003 | 2026-10-16 | Code lives in a private GitHub repository owned by The Arqam Schools | Ownership, history, automated testing (GitHub Actions) | Approved |
| D-004 | 2026-10-16 | MVP scope: platform core, organisation and student records, student attendance, Daily Diary, AI Teacher Assistant, basic head-office dashboard | Daily value for teachers and parents, low financial risk | Approved |
| D-005 | 2026-10-16 | Pilot at the Faisalabad head office campus (Samanabad) first, then volunteer Faisalabad-region franchises; Lahore after Gate 2 | Company-owned campus, close supervision | Approved |
| D-006 | 2026-10-16 | Branch isolation: every branch-owned table has `branch_id`; all reads go through `Model.objects.for_user(user)`. PostgreSQL row-level security is added as a second lock before rollout beyond the Samanabad campus | Application lock now keeps development simple; the database lock is required before more than one branch holds live data | Approved; RLS pending (Milestone before Gate 2) |
| D-007 | 2026-10-16 | Access = roles × scopes. A role is a bundle of permissions; it is assigned at network, head office, region or branch scope. Head office responsibilities are data, not code | Matches the Faisalabad/Lahore split and franchise structure; no hard-coded head office rules | Approved |
| D-008 | 2026-10-16 | Append-only audit log of every create, update, delete, login and failed login, with before/after values; passwords never logged | Accountability for student and financial records | Approved |
| D-009 | 2026-10-16 | Students have no logins; parents will | Project lead decision | Approved |
| D-010 | 2026-10-16 | Royalty is a per-branch percentage, default 8% for franchises, 0% for company-owned campuses | Head office takes 8% of monthly fee collections from franchises; per-branch field allows exceptions without code changes | Approved |
| D-011 | 2026-10-16 | Staff attendance is imported from the existing face-recognition biometric machines, not replaced | Machines already in use; brand/model and export method to confirm | Approved |
| D-012 | 2026-10-16 | The built-in Django admin is used only as a temporary back-office for head office and IT during early milestones. Teachers, principals and parents get purpose-built screens | Fast, secure setup screens now; proper user experience where it matters | Proposed |
| D-013 | 2026-10-16 | Seed data contains only confirmed facts (head offices, Samanabad campus, roles, class levels). Lahore address, regions, subjects and session dates are entered by head office | Accuracy rule: nothing invented | Approved |
| D-014 | 2026-10-16 | Early Years = Play Group, Nursery, Prep; Primary starts at Class 1 | Confirmed by the project lead | Approved |
