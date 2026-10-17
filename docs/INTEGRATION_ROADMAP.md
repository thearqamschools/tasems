# Integration roadmap — Phase 4 (ERP upgrade)

How the upgrade is added to the existing TASEMS without breaking it. Read with FEATURE_GAP_MATRIX.md and
UI_UX_REDESIGN_PLAN.md.

## 1. Integration architecture

TASEMS stays a **modular monolith** (D-001): one Django project, one PostgreSQL database, one sign-in, one
navigation, one design system. New areas become new Django apps beside the existing ones and use the same base
pieces:

| Existing piece | Every new module must use it |
| --- | --- |
| `BranchOwnedModel` + `for_user(user)` (core) | All branch data; never unscoped queries in views |
| Row-level security migration (pattern: `apps/hr/migrations/0002_row_level_security.py`) | One per new branch table, plus a test in `tests/test_rls.py` style |
| Roles × scopes (accounts) | New permissions added to roles in `seed_tasems`; menu items appear only with the permission |
| Audit log (core) | Every create/update/cancel of official or money records |
| `current_branch(request)` + branch switcher | All branch screens |
| Ledger rules (D-033) | Accounting and inventory sales post into ledgers; nothing overwritten, only reversed |
| WeasyPrint + bundled fonts | All new printed documents (certificates, ID cards, payslips) |
| `locale/ur` | Every new label translated; RTL checked |

### New apps (proposed)

| App | Holds | Reuses |
| --- | --- | --- |
| `ui` (no models) | Design system: templates/components, icons sprite, template tags (`{% kpi %}`, `{% table %}`) | — |
| `dashboards` (no models at first) | Role dashboards, network view | Attendance summaries, fee ledger, admissions, HR |
| `reports` | Reports centre registry and exports | Each module's existing report queries |
| `settings_ui` (or inside `organisation`/`accounts`) | Purpose-built setup screens replacing Django admin for daily use | Existing models; admin stays for IT |
| `academics` (extend) | Subject-teacher assignment, timetable | Section, Subject |
| `people` (extend) | Photo, promotion, certificates, ID cards | Student, Enrolment, AcademicSession |
| `notices` | Circulars to parents/staff, shown in portal | parents, accounts |
| `accounts_finance` ✱ | Expenses, other income, cash/bank book, P&L | fees ledger |
| `payroll` ✱ | Salary structure, monthly payroll, payslips | hr StaffDay, monthly sheet |
| `inventory` ✱ | Items, stock moves, sales → fee charges | fees Charge/Voucher |
| `hifz` ✱ | Sabaq/Sabqi/Manzil, milestones | Student `is_hifz`, attendance |
| `ai` ✱ | Teacher assistant, question papers, analytics summaries | Claude API (D-026), diary, exams |

✱ = needs approval (see Section 4).

### Background jobs

Needed for large PDFs (vouchers for a whole branch), bulk exports and later SMS/AI. Proposal: a
**PostgreSQL-backed job queue** (no Redis, no extra paid service), run as a second process from the same Docker
image. Choice of library to be recorded as a decision before Milestone 6.

## 2. Development sequence

| # | Milestone | Contents | Depends on | Effort* |
| --- | --- | --- | --- | --- |
| **M1** | **Design system + app shell** | Tokens and components, collapsible grouped sidebar, top bar, searchable branch selector, icons, toasts, empty/loading states, HTMX vendored; hide actions users cannot perform; all existing pages moved into the new shell unchanged in function | Brand colours (can start with placeholder) | 6–8 days |
| M2 | Role dashboards | Head office network dashboard, principal, teacher, accountant, admissions dashboards with charts | M1 | 6–8 days |
| M3 | Settings & multi-branch screens | Branches/regions/campuses, sessions, class levels & sections, class teachers, fee rates & bank details, users & role assignments, exam setup | M1 | 8–10 days |
| M4 | Student lifecycle | Profile with tabs, photos, session rollover & promotion, withdrawal/transfer workflow, leaving & character certificates, ID cards, parent directory | M1, M3 | 8–10 days |
| M5 | Module restyle | Apply components to students, attendance, diary, exams, fees, admissions, staff, parent portal; consistent filters and exports | M1 | 8–12 days |
| M6 | Reports centre + background printing | One reports hub, Excel/PDF everywhere, job queue for large PDFs | M5 | 5–7 days |
| M7 | Academic management | Subject-teacher assignment, timetable, holiday calendar, date sheets, roll-number slips, award lists | M3 | 6–8 days |
| M8 | Notices & parent communication | Circulars in portal and staff home; PWA for parents; SMS/WhatsApp provider ✱ later | M1 | 4–6 days (+ provider) |
| M9 ✱ | Accounting | Expenses, other income, cash/bank book, branch P&L, head-office consolidation | M3 | 10–15 days |
| M10 ✱ | Payroll | Salary structures, monthly run from staff attendance, payslips, bank sheet | M3 | 8–12 days |
| M11 ✱ | Inventory | Items, stock, issue, sales linked to vouchers | M9 | 6–8 days |
| M12 ✱ | Hifz | Per D-050 when un-deferred | M4 | 8–10 days |
| M13 ✱ | AI | Rules-based at-risk analytics first (free), then Teacher Assistant, Question Paper Generator, AI summaries (Claude API) | Textbook PDFs, API billing | 12–18 days |

\* Rough working days for one developer working with Claude, including tests and docs; excludes school-side
input (data, approvals, staff review). Total ≈ 95–130 working days. Estimates will be revised after M1.

## 3. Rules for every milestone

1. Branch from `main`; Git tag before any migration.
2. Migrations are additive only (new tables/columns, nullable or with defaults). No column drops or renames of
   existing data without a separate approved plan.
3. New branch tables get row-level security in the same milestone.
4. Full test suite + ruff + migration check green; new tests for new features.
5. Live check with `seed_demo` and every demo role; before/after screenshots.
6. Update DEVELOPMENT_PROGRESS.md, DECISIONS.md, DATABASE_DESIGN.md, CHANGELOG.md.
7. No deployment, paid service or destructive change without explicit approval.

## 4. Decisions needed from the project lead

| # | Decision | Why it needs approval |
| --- | --- | --- |
| 1 | Screenshots or file of the reference video | The video could not be opened from the build environment |
| 2 | Current figures: 200,000+ / 15,000+ (brief) or 250,000+ / 20,000+ (docs, 16 Oct) | Conflicting confirmed facts |
| 3 | Official brand colours (hex) | `tasems.css` uses placeholders |
| 4 | Un-defer Hifz (D-050) | Earlier decision by the project lead |
| 5 | Build payroll (reverses D-045 "integrate, not build") | Earlier decision |
| 6 | Build accounting and inventory | New scope |
| 7 | Claude API billing for AI modules; SMS/WhatsApp provider | Paid, usage-based services |
| 8 | Push access for this session to the `tasems` repository | Work is committed locally; it cannot be pushed until access is granted |

## 5. Risks and dependencies

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Shell change touches every page | Layout regressions; 55 tests check page HTML | Keep content blocks and URLs unchanged; run full suite; screenshot every role |
| RTL (Urdu) breakage in new layout | Unusable Urdu screens | Logical CSS properties only; Urdu screenshots in every milestone |
| Network dashboards slow at 350 branches | Timeouts | Read summary tables (D-022); index checks; cached aggregates if needed |
| New tables without RLS | Cross-branch data leak | RLS migration + test required in the same milestone (review checklist) |
| Payroll/accounting correctness | Money errors | Ledger rules, exact decimals, four-eyes approvals, audit, reversal not deletion |
| Scope growth (22 areas) | Delays pilot | Pilot can start after M1–M5; finance/AI modules follow |
| Pending school inputs (subject lists, session dates, machine model, bank details, arrears) | Features built but not usable | Tracked in DEVELOPMENT_PROGRESS.md "Known gaps" |
| Paid services (AI, SMS) | Running cost | Usage-based only; monthly cap; feature works without them where possible |
| Single developer | Bus factor | Docs-first workflow (this folder), tests, small milestones |

## 6. Recommended first milestone: M1 — Design system + app shell

Why first: every later module uses the shell and components; it changes no data and needs no migrations; it fixes
the 350-branch selector and the 403 buttons; results are visible to every role immediately.

Deliverables: new `base.html` shell, component CSS, icon sprite, HTMX vendored, searchable branch selector,
permission-aware action buttons, restyled home screen as a preview of dashboards; all 149 existing tests passing;
screenshots in English and Urdu for all six demo roles.
