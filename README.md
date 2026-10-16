# TASEMS — The Arqam Smart Education & Management System

School management platform for **The Arqam Schools**, Pakistan. Private repository; owned by The Arqam Schools.

Current status: **Phase 1 done except AI assistant (deferred); Phase 2 (examinations, fees) and Phase 3a (staff) done; not deployed.** Deployment: `docs/DEPLOYMENT.md`. See `docs/DEVELOPMENT_PROGRESS.md`.

## Stack

Python 3.12 · Django 5.2 LTS · PostgreSQL 16 · WeasyPrint (diary PDFs) · Docker · GitHub Actions. Diary PDFs need the Pango library (`libpango-1.0-0`), already in the Dockerfile. Reasons: `docs/DECISIONS.md` (D-002).

## Run it locally (about 5 minutes)

```bash
# 1. Database
docker compose up -d db

# 2. Python environment
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. Settings: copy, then set SECRET_KEY and FIELD_ENCRYPTION_KEY (command is in the file)
cp .env.example .env

# 4. Tables and starting data
python manage.py migrate
python manage.py seed_tasems
python manage.py createsuperuser
python manage.py compilemessages -l ur   # Urdu screens (needs gettext installed)

# 5. Start
python manage.py runserver
```

Open http://localhost:8000/ and sign in. Superusers must set up two-step sign-in with an authenticator app on first sign-in.

## Tests and checks

```bash
pytest                      # automated tests (needs the database running)
ruff check . && ruff format --check .
python manage.py makemigrations --check --dry-run
```

The same checks run automatically on GitHub for every push.

## Layout

| Folder | Holds |
| --- | --- |
| `config/` | Settings and URLs |
| `apps/core/` | Shared models, branch isolation, audit log |
| `apps/organisation/` | Head offices, regions, branches, sessions |
| `apps/accounts/` | Users, roles, scoped role assignments, seed command |
| `apps/academics/` | Class levels, subjects, curriculum, sections |
| `apps/people/` | Students, guardians, enrolments, Excel import |
| `apps/attendance/` | Daily student attendance |
| `apps/diary/` | Daily Diary, PDF and WhatsApp image |
| `apps/exams/` | Exams, marks, result pattern, result cards |
| `apps/hr/` | Staff records, biometric attendance import, leave, monthly sheet |
| `apps/parents/` | Parent portal: diary, attendance, fees, results; access codes |
| `apps/admissions/` | Inquiries, follow-ups, campus visits, admit to student, reports |
| `apps/fees/` | Fee rates, vouchers (3 copies + payment options), payments, defaulters, discounts, royalty |
| `static/fonts/` | Bundled Urdu and Latin fonts (Open Font License) |
| `deploy/` | Production setup: HTTPS proxy, database role, backups |
| `tests/` | Automated tests |
| `docs/` | Project source of truth: decisions, progress, design, security |

## Rules

- Never commit `.env`, passwords or API keys.
- Read branch data only through `Model.objects.for_user(user)`.
- Every change of direction goes in `docs/DECISIONS.md`.
