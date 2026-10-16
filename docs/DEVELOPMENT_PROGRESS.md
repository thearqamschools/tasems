# Development progress

Status words: **Done** = built and passing automated tests. **Not deployed** until a deployment entry says so.

## Phase 1 — MVP, broken into milestones

| Milestone | Contents | Status |
| --- | --- | --- |
| 1a — Foundation | Project setup, settings from environment, PostgreSQL, organisation structure, users, roles × scopes, branch isolation, audit log, students/guardians/enrolments, classes/sections, seed data, 23 automated tests, CI | **Done (16 Oct 2026), not deployed** |
| 1b — Staff access and student register | Sign-in by username or mobile; lockout after 5 failures; two-step sign-in (authenticator app + 8 backup codes) for privileged roles; English/Urdu interface with right-to-left layout; branch switcher; home screen per role; student list, search, add, edit, history; Excel import with row-by-row checking; 49 automated tests | **Done (16 Oct 2026), not deployed** |
| 1c — Student attendance | Register once a day per section: everyone starts present, tap only absent/leave/late; class teacher marks own sections today, principal/coordinator can correct past days (changes audited); draft kept on the phone when offline; absent list with parent mobile and 3+ day streaks; section progress for the branch; branch summary for head office; home screen progress; 60 automated tests | **Done (16 Oct 2026), not deployed** |
| 1d — Daily Diary | Built from the school's own Class 4 diary: header, week number, quote, theme of the week, In Class Learning and Home Learning Tasks with deadlines; empty subjects left out; Urdu set right-to-left in Nastaliq; one-page A4 PDF and a WhatsApp image; draft/publish; class teacher writes today and up to a week ahead, principal corrects any day; branch or network theme of the week; 73 automated tests | **Done (16 Oct 2026), not deployed** |
| 1e — AI Teacher Assistant | Provider decided: Claude API (D-026). Deferred until textbook PDFs are collected and API billing is set up | **Deferred** |
| 1f — Pilot hardening + head office view | PostgreSQL row-level security on all branch tables (tested with an ordinary role); `check_security` command; fonts served locally (~370 KB, no Google Fonts); head office home shows today's registers and diaries per branch; `/healthz`; production setup with automatic HTTPS (Caddy), ordinary database role, static files (WhiteNoise); encrypted nightly backup and restore-drill scripts; deployment guide; 79 automated tests | **Done (16 Oct 2026), not deployed** |

## Known gaps and pending inputs

- Production setup not yet run on a real server (no Docker available in the build environment); first install should be on a test server.
- Independent penetration test still needed before the pilot.
- Backups are nightly (lose up to a day); point-in-time recovery needed before rollout beyond the pilot.
- Screens tested by automated tests and a live server check; not yet reviewed on a real phone or by Samanabad staff.
- Urdu translations written by Claude; a native-speaker review is needed before the pilot.
- No public-holiday calendar yet: registers can be taken on any school day of the session (Sunday off; Saturday only Hifz, Pre-9, 9, 10).
- Diary: official logo files not yet uploaded (Setup → Diary layout); subject lists for classes other than Class 4; whether the principal must approve a diary before it is shared.
- Not yet provided: current software data export; biometric machine brand/model; academic session dates; subject list per class.
- Hosting provider not chosen (no preference stated; shortlist in master plan Part 5).
