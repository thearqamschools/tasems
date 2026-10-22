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

## Phase 2 — Examinations and fees

| Milestone | Contents | Status |
| --- | --- | --- |
| 2a — Examinations and results | Approved result pattern (D-030/031) as editable data; exams and papers set up by head office; marks entry per paper with checks and audit; teacher ratings (discipline, neatness, summer work, class work); automatic attendance marks; section results with what is still missing; Mid-Term progress report and annual result card (one A4 page, PDF for one student or the whole section); remarks; row-level security on marks and ratings; 92 automated tests | **Done (16 Oct 2026), not deployed** |
| 2b — Fees | Per-branch fee rates by class (Samanabad fees seeded); monthly vouchers for the whole branch or chosen classes, or one student (admission, several months together); sibling fee by father's CNIC; special discounts with approval; unpaid balance and Rs 200 fine carried to the next voucher; A4 voucher with School, Bank and Student copies, barcode and the payment-options back page (bank details editable in Setup); receive payment by scanning or typing the Voucher ID (cash, bank, transfer, JazzCash, Alfa) with receipt; JazzCash: monthly Excel list of unpaid vouchers and import of JazzCash's paid list (checked row by row); reversal and cancellation with reasons; student fee account; defaulters; daily collection; royalty statement (8% of all fees received); row-level security on fee tables; 121 automated tests | **Done (16 Oct 2026), not deployed** |

## Phase 3 — Staff, Hifz, Admissions

| Milestone | Contents | Status |
| --- | --- | --- |
| 3a — Staff (HR) and staff attendance | Staff register (add, edit, Excel import with row-by-row checks); biometric machine file import (Excel, CSV, .dat/.txt) matched by machine ID; daily status worked out (present, late, half day, absent, leave, holiday, off) from per-branch duty time and grace; principal corrections with reason; daily and monthly views, monthly Excel for payroll; leave requests with approval by someone else and balances per session; "My attendance" self-service for staff with a login; holidays; row-level security on staff tables; 133 automated tests | **Done (16 Oct 2026), not deployed** |
| 3a+ — Parent portal | Parent sign-in by mobile number; first-time set-up and password reset with a printed one-time code from the school (per student or a whole class); each child's diary (image and PDF), monthly attendance, fee balance, vouchers (PDF) and payments, published result cards (PDF); English/Urdu, phone-sized; parents see only their own children; 140 automated tests | **Done (16 Oct 2026), not deployed** |
| 3b — Hifz | Sabaq, Sabqi, Manzil, mistakes, milestones, parent reports | **Deferred** by the project lead (D-050) |
| 3c — Admissions | Inquiries from every source; pipeline with next follow-up date and person responsible; follow-ups due today and campus visits today; call and WhatsApp buttons (ready message, no API); brothers/sisters already at school and earlier inquiries shown by mobile number; "not joining" with reason; admit → student record → admission fee voucher; report by source, class, status and reasons; Excel; 146 automated tests | **Done (16 Oct 2026), not deployed** |

## Phase 4 — ERP upgrade (planning)

Brief received 17 Oct 2026: upgrade TASEMS into a full multi-branch ERP with a modern interface, using a reference
demo video for workflows. Plan: `EXISTING_SYSTEM_AUDIT.md`, `REFERENCE_FEATURE_ANALYSIS.md`, `FEATURE_GAP_MATRIX.md`,
`UI_UX_REDESIGN_PLAN.md`, `INTEGRATION_ROADMAP.md`. Rollback point: commit `4b1ac5b` on `main`.

| Milestone | Contents | Status |
| --- | --- | --- |
| 4.0 — Audit and plan | Code and docs audit, 149 tests passing, live check with all demo roles, gap matrix, redesign plan, roadmap | **Done (17 Oct 2026)** |
| 4.0a — Reference video analysis | 194 screens of the supplied demo video reviewed; gap matrix rows added; approvals and logo colours recorded (D-056 to D-062) | **Done (17 Oct 2026)** |
| M1 — Design system + app shell | Logo colours as design tokens; grouped collapsible sidebar (permission-filtered, RTL, phone slide-in); top bar with searchable branch picker; local icon sprite; buttons that led to "Forbidden" removed; 161 automated tests; live check of every demo role in English and Urdu, desktop and phone | **Done (17 Oct 2026), not deployed** |
| M1b — Design system completed (Phase 1: UI/UX foundation) | Stylesheet reorganised into 15 numbered sections with tokens (colour, space, type, shape); components: page header, buttons (primary/secondary/quiet/danger/small/busy/disabled), cards, KPI figures with tones, tables with totals, filter bars, form fields with required mark and error state, badges, messages and callouts, empty states, tabs, pagination, disclosure; **confirmation dialog** on risky actions (cancel voucher, cancel charge, reverse payment, cancel or withdraw leave); **double-submit guard** on every form that saves; top-bar student search; running session in the sidebar; living style guide at `/design-system/` (staff) and `docs/DESIGN_SYSTEM.md`; Urdu labels for all new text; fixed an existing bug that stopped the register's script in Urdu; 165 automated tests | **Done (17 Oct 2026), not deployed** |
| M2 — Role dashboards | Home page rebuilt as a dashboard from each person's permissions: quick actions; **class teacher** — today's register and diary per class with one-press links, students absent 3+ days in a row; **principal** — registers, attendance %, absentees, staff in, class-wise attendance today, 14-day attendance chart, month fees (billed, received, % collected, owed, today) with daily chart and payment methods, admissions (follow-ups due, visits, new, admitted, open inquiries by stage), student records; **head office / several branches** — network figures, 14-day attendance chart, branch table with attendance and fee-collection meters, filter by head office and region, five orderings, royalty due this month; **staff** — own attendance this month; "Hide amounts" switch remembered per browser; charts drawn on the server (D-064) with tooltips and table views; all text in Urdu; 12 dashboard tests (figures match module pages, queries do not grow with branches); 177 automated tests | **Done (19 Oct 2026), not deployed** |
| M3 — Settings and branch management | New **Setup** area (`/setup/`) replacing the admin site for daily setup: classes and sections (boys/girls group, campus, class teacher, capacity) with a warning for sections without a class teacher; campuses; fee rates per class with "In use / Upcoming / Replaced" and new rates from a chosen month; voucher and bank settings; branches (franchise or company-owned, royalty %) and regions; academic sessions with "Make current" behind a confirmation; **users and roles** — search, add a login with its first role, give or end roles, reset password (temporary password shown once), switch a login off or on; **My password** for every staff member from the top bar. Access rule D-066 (no one gives more than they hold, only inside their own area). Translated labels on every setup form; all text in Urdu; 17 setup tests (194 in total) | **Done (19 Oct 2026), not deployed** |
| Lead's changes (19 Oct 2026) | 46 items collected one by one (`CHANGE_REQUESTS.md`), built in four batches: students (class/section, family details, plain admission numbers, no Urdu entry), inquiries, attendance, staff (designations, CV), fees (Cash/Bank with branch banks, who received, today's totals, Barcode quick receive, receipt photos, discount types at admission), royalty paid/pending ledger, expenses | **Done (19 Oct 2026), not deployed** — demo updated |
| M4 — Student lifecycle | Student photo, profile sections, brothers and sisters; leave school with leaving/character certificates (numbered PDFs); promotion to next session (copy sections, promote/keep/graduate); ID cards; defaulters by family | **Done (22 Oct 2026), not deployed** |
| M5 | Module restyle: Excel/Print on every list, print layout, consistent filters and empty states, parent portal on phones | Done 22 Oct 2026 (printed documents keep their approved layouts) |
| M6 | Reports centre, family vouchers and family fee collection, background printing of large PDFs | Done 22 Oct 2026 |
| M7 | Subject teachers, timetable, holiday calendar, date sheets, exam slips with photo, award lists | Done 22 Oct 2026 |
| M8 | Notices and circulars, messages to parents (WhatsApp links / Excel for SMS, no paid service), installable parent portal | Done 22 Oct 2026 (SMS/WhatsApp provider: needs approval and cost) |
| M9 | Accounting: other income, cash & bank book with opening balances, profit & loss, branch-wise statement | Done 22 Oct 2026 |
| M10 | Payroll: fixed salaries, per-day cut for absence and unpaid leave, finalise and lock, payslips, bank sheet | Done 22 Oct 2026 (per-day rate = salary ÷ days in the month, to confirm) |
| M11 | Shop & stock: items with barcode, stock ledger, sale counter (cash / bank / fee account), receipts, cancel, stock and sales reports | Done 22 Oct 2026 |
| M12 | Hifz-e-Quran: daily Sabaq / Sabqi / Manzil with mistakes, para tests, 30-para progress, section report, parent tab | Done 23 Oct 2026 |
| M13 | See `INTEGRATION_ROADMAP.md` | Not started (AI: cost estimate in AI_COST_ESTIMATE.md, needs approval) |

## Known gaps and pending inputs

- Production setup not yet run on a real server (no Docker available in the build environment); first install should be on a test server.
- Independent penetration test still needed before the pilot.
- Backups are nightly (lose up to a day); point-in-time recovery needed before rollout beyond the pilot.
- Screens tested by automated tests and a live server check; not yet reviewed on a real phone or by Samanabad staff.
- Urdu translations written by Claude; a native-speaker review is needed before the pilot.
- No public-holiday calendar yet: registers can be taken on any school day of the session (Sunday off; Saturday only Hifz, Pre-9, 9, 10).
- Diary: subject lists for classes other than Class 4; whether the principal must approve a diary before it is shared.
- Fees: Bank Alfalah's API connection (Voucher ID lookup in the Alfa app) still runs through the old software; moving it to TASEMS needs Bank Alfalah's interface document and test account from IT. Until then Alfa payments are entered by staff.
- Fees: the JazzCash export and import use TASEMS's own column layout; a sample of the form JazzCash receives and sends back is needed to match it exactly.
- Fees: opening balances (arrears) from the old software are not imported yet; needed before the first TASEMS vouchers so arrears are not lost.
- Fees: bank name, account title and number to enter in Setup; the voucher counter to set above the old system's last Voucher ID.
- Staff: grace minutes and half-day time if the school wants them (Setup → HR settings); whether a half day or late arrival also cuts salary; the attendance machine brand/model and a sample export; the Samanabad staff list (Excel template in TASEMS).
- Admissions: no public online inquiry form on the website yet; no automatic WhatsApp messages (needs the WhatsApp Business API).
- Fees: moving the JazzCash/Bank Alfalah connection to TASEMS deferred (D-050).
- Parents: no SMS or WhatsApp alerts yet (needs a messaging provider / WhatsApp Business approval); online fee payment from the portal waits for the bank/JazzCash connection.
- Staff: no recruitment, appraisals or payroll yet (payroll gets the monthly Excel).
- Exams: exam set-up and grading scheme edits are in Setup (admin) for now; a purpose-built head-office screen can follow.
- Not yet provided: current software data export; biometric machine brand/model; academic session dates; subject list per class.
- Phase 4: SMS/WhatsApp provider and AI monthly spending cap to agree before switching on (D-060). HTMX and Chart.js (D-055) are added with the first screen that needs them (M2 dashboards), not before.
- Bulk voucher PDF for a whole month still takes ~23 s for 32 vouchers; background printing is planned in M6.
- Phase 1 checks done on 17 Oct 2026 (local demo server): every page and file reachable by the six demo roles opened (≈1,000; none refused), 24 main screens on desktop and phone in English and Urdu with no horizontal scrolling and no script errors, and these workflows end to end in the browser: register saved, fee received (second press blocked, one payment recorded), payment reversed through the confirmation dialog, inquiry added, student found from the top-bar search, branch switched. Not yet reviewed on a real phone or by Samanabad staff.
- Urdu: some labels on the admissions inquiry form (date of birth, gender, source, notes, referred by, current school, next follow-up) and the student form are still English; the design-system page is English only (IT reference).
- M2 checks (19 Oct 2026, local demo server): dashboards for the five staff roles in English and Urdu at desktop and phone width (no horizontal scrolling, no script errors); tooltip, "Hide amounts" (remembered after reload), network filter and ordering used in the browser with two temporary demo branches (removed afterwards); all pages of every demo role re-opened. Demo data has one branch only, so the network view is covered mainly by automated tests.
- Dashboards: no year-to-date or month-on-month comparisons yet; expenses and profit (seen in the reference ERP) arrive with Accounting (M9).
- Printed documents (vouchers, receipts, diaries, result cards) and the parent portal keep their earlier layout apart from the new colours; restyling them is part of M5.
- M3 checks (19 Oct 2026, local demo server): every setup screen opened as principal, head office and a temporary system administrator in English and Urdu at desktop and phone width (no horizontal scrolling, no script errors); in the browser: a login added (temporary password shown once), its password reset and the login switched off through the confirmation dialog, the "Make current" dialog opened; a teacher gets no Setup link and is refused the setup pages. Temporary logins and the test session were deleted afterwards.
- Setup: principals cannot yet add logins or give roles (the principal role does not include user management); to decide whether they should, for their own branch's teachers and staff.
- Setup: class levels, subjects, exams and grading are still edited under Advanced setup (admin); exam setup moves in M7.
- Setup: no bulk import of staff logins yet; logins are added one at a time.
- Lead's changes: designation → login permissions table still to agree (staff designations are a fixed list; logins still use roles). Answers still open: father occupation required?, roll number position, second father mobile, Coordinator/Lawyer in the designation list — defaults used are listed in `CHANGE_REQUESTS.md`.
- Files (staff CVs, receipt and bill photos) are kept on the server's disk under a private folder; the free Render demo loses them when it restarts. The pilot server needs a backed-up file store.
- M4: certificate wording is a standard text for head office to review; staff ID cards, printable admission form and experience certificate are not built yet.
- Real student data was entered on the public demo by the lead (22 Oct 2026); the demo is for fictional data only — to be removed or moved to a private test server.
- Hosting provider not chosen (no preference stated; shortlist in master plan Part 5).
