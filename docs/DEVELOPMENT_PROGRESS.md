# Development progress

Status words: **Done** = built and passing automated tests. **Not deployed** until a deployment entry says so.

## Phase 1 — MVP, broken into milestones

| Milestone | Contents | Status |
| --- | --- | --- |
| 1a — Foundation | Project setup, settings from environment, PostgreSQL, organisation structure, users, roles × scopes, branch isolation, audit log, students/guardians/enrolments, classes/sections, seed data, 23 automated tests, CI | **Done (16 Oct 2026), not deployed** |
| 1b — Staff access and student register | Staff login screens (English/Urdu, RTL), two-factor login for privileged roles, role home screens, student register screens, Excel import of students with validation | Next |
| 1c — Student attendance | Daily attendance by section (3 taps), offline draft, absence list for principal, same-morning HO view | Planned |
| 1d — Daily Diary | Needs the current diary template from the project lead | Planned |
| 1e — AI Teacher Assistant | Needs textbook files for grounding; AI provider agreement | Planned |
| 1f — Basic HO dashboard + pilot hardening | Dashboard, PostgreSQL row-level security (D-006), backups, penetration test | Planned |

## Known gaps and pending inputs

- PostgreSQL row-level security not yet enabled (required before a second branch holds live data — D-006).
- Two-factor login not yet enforced (`Role.requires_mfa` is recorded; enforcement in 1b).
- Not yet provided: Daily Diary template; current software data export; biometric machine brand/model; academic session dates; subject list per class; whether separate boys and girls campuses are run as separate branches (own principal, admissions, fees) or one branch with two buildings.
- Hosting provider not chosen (no preference stated; shortlist in master plan Part 5).
