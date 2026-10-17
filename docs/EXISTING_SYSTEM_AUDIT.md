# Existing system audit

Audit of TASEMS before the ERP upgrade (Phase 4). Done 17 Oct 2026 against `main` at commit `4b1ac5b`
(Git tag `checkpoint/before-erp-upgrade`). Facts below were checked in the code, by running the test
suite and by signing in to a running copy with every demo account.

## 1. Health check

| Check | Result |
| --- | --- |
| Automated tests (`pytest`) | **149 passed**, 0 failed (5 min 10 s, PostgreSQL 16) |
| Lint (`ruff check`) | Clean |
| Missing migrations (`makemigrations --check`) | None |
| Live run with demo data (`seed_demo`, `DEMO_MODE=True`) | All 6 demo logins work; ~1,000 pages and files opened without a server error; a register saved end to end |
| Test-environment note | Tests need `DEMO_MODE` off and a database user allowed to create roles (as in CI); otherwise 4 tests fail for environment reasons, not code reasons |

## 2. Technology stack (as built)

| Layer | Technology | Source |
| --- | --- | --- |
| Language / framework | Python 3.12, Django 5.2 LTS | D-002 |
| Database | PostgreSQL 16, one shared schema, row-level security on every branch table | D-001, D-006, D-028 |
| Screens | Server-rendered Django templates, one stylesheet (`static/css/tasems.css`, 126 rules), **no JavaScript framework**; small inline scripts on 2 pages only | D-019 |
| HTMX | Approved in D-002 but **not used yet** | — |
| PDFs / images | WeasyPrint (Pango/HarfBuzz) for diaries, vouchers, result cards; pypdfium2 for WhatsApp images | D-024 |
| Excel | openpyxl (imports with row-by-row checking, exports) | — |
| Fonts | Noto Sans, Noto Nastaliq Urdu, bundled locally (no Google Fonts) | 1f |
| Languages | English + Urdu (right-to-left), `locale/ur` (≈4,250 lines) | 1b |
| Auth | Custom user, roles × scopes, TOTP two-step sign-in, lockout from audit log | D-007, D-017, D-018 |
| Static files | WhiteNoise | — |
| Deployment | Dockerfile, Docker Compose, Caddy (HTTPS), Render blueprint for the demo only | D-029, D-054 |
| CI | GitHub Actions: ruff, `check --deploy`, migration check, pytest | — |
| API | **None** (no REST/JSON API apart from `/healthz`) | — |

## 3. Modules (Django apps)

| App | Python lines* | What works today |
| --- | ---: | --- |
| core | 1,017 | Branch-scoped base models, branch switcher, audit log, home screens, `/healthz`, `check_security`, `seed_demo` |
| organisation | 175 | Head offices (Faisalabad, Lahore), regions, branches (company/franchise, royalty %), campuses (boys/girls buildings), academic sessions |
| accounts | 1,188 | Users, roles, scoped role assignments, sign-in by username or mobile, two-step sign-in, backup codes, navigation, `seed_tasems` |
| academics | 162 | Class levels (Play Group → Matric + Hifz), subjects, curriculum per class, sections with class teacher and capacity |
| people | 1,117 | Students, guardians, enrolments, search/filter, add/edit/history, Excel import, old-system PDF import, agreed fee |
| attendance | 476 | Daily student register per section, corrections audited, absentees with 3+ day streaks, branch summary for head office |
| diary | 465 | Daily Diary (In-class learning, Home learning tasks), A4 PDF + WhatsApp image, draft/publish, theme of the week |
| exams | 1,112 | Exams, papers, marks entry, teacher ratings, remarks, result pattern as data, positions, Mid-Term and annual result cards (PDF) |
| fees | 2,542 | Fee rates per branch, monthly vouchers (3 copies + barcode), sibling rule, discounts with approval, arrears + fine, receive payments, receipts, reversals, student fee account, defaulters, daily collection, royalty, JazzCash Excel export/import |
| hr | 1,655 | Staff register, Excel import, biometric punch import, daily status, monthly sheet (Excel for payroll), leave with approval, holidays, "My attendance" |
| parents | 572 | Parent portal: sign-in by mobile, one-time codes, diary, attendance, fees, vouchers, result cards; English/Urdu |
| admissions | 682 | Inquiry pipeline, follow-ups, campus visits, WhatsApp/call buttons, admit → student → admission voucher, reports |

\* Excluding migrations. 72 templates (2,218 lines), 149 tests in 14 files.

Database: 42 tables across the apps, documented in `docs/DATABASE_DESIGN.md` (accurate as of this audit).

## 4. Roles tested with demo data

Principal, class teacher, accountant, admissions officer, head office, parent. Each sees only the menu items its
permissions allow (navigation is built in `apps/accounts/context_processors.py`).

## 5. Strengths to preserve

1. **Data safety:** two locks on branch data (application filter + PostgreSQL row-level security), append-only audit log, money as a ledger that is never overwritten.
2. **Business rules as data:** result pattern, fee rates, school week, royalty, HR duty times are editable without code.
3. **Pakistani context done properly:** Urdu Nastaliq in PDFs, CNIC sibling rule, JazzCash/bank vouchers, boys/girls campuses from Class 6.
4. **Low running cost:** no JavaScript build, no paid services, works on slow connections, one server.
5. **Test coverage:** every milestone shipped with tests; CI enforces them.

## 6. Weaknesses found (input to the upgrade)

### Interface
- **Top navigation only:** 10+ horizontal items for a principal; no grouping, no icons, wraps on small screens; not scalable as modules are added.
- **Branch switcher is a plain dropdown of up to 400 branches** (`MAX_SWITCHER_BRANCHES`); unusable for head office at 350+ branches. Needs a searchable selector grouped by head office/region.
- **Home screen is basic:** a few count tiles and one table; no charts, no trends, no role-specific dashboards beyond simple variations.
- **Setup goes to the Django admin** (D-012, temporary) for branches, sessions, sections, users, roles, fee rates, exams. Not suitable for head office staff.
- **Buttons shown to people who cannot use them** (found in the live test): "Remarks"/"Ratings" for teachers of other classes and for head office; "Receive" on vouchers for admissions and head office; "Take today's register" on non-school days. All end in a 403 page.
- **Brand colours are placeholders** (comment in `tasems.css`): green `#0f5c4d` until official colours are supplied. The official logo is in use (D-051).
- No icons, no loading states, inconsistent filter bars between modules, no breadcrumb/page header pattern.

### Function
- No REST API (only needed later for a mobile app or integrations).
- Bulk voucher PDF for a whole branch takes ~23 s for 32 vouchers (measured); a branch of 800 students would exceed the web timeout. Needs background generation.
- Session rollover / promotion, student photos, certificates, ID cards: not built.
- No accounting beyond fees, no payroll, no inventory, no Hifz, no AI, no notices/SMS (see FEATURE_GAP_MATRIX.md).

## 7. Facts that need confirmation

| Item | In project docs (16 Oct 2026) | In the upgrade brief (17 Oct 2026) |
| --- | --- | --- |
| Students | 250,000+ | 200,000+ |
| Hifz-e-Quran students | 20,000+ | 15,000+ |
| Branches | 350+ | 350+ |

Not changed in any document until the project lead confirms which figures are current.
