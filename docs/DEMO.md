# Trying TASEMS (demo server)

A demo server runs the real software with **fictional data**, so the team can try every screen.
It is not the pilot server: no real student data goes on it, and two-step sign-in is switched off
so testers do not need an authenticator app. Every page shows a red "DEMO" bar.

## Option A — Render.com (a public link, free plan)

1. Sign in at <https://dashboard.render.com> with the school's GitHub account (thearqamschools).
2. Give Render access to the `tasems` repository when asked.
3. Click **New → Blueprint**, choose the `tasems` repository, then **Apply**.
4. Render asks for `DEMO_PASSWORD`: type a password of at least 10 characters. All demo logins use it.
5. Wait for the first build (about 10 minutes). The link looks like `https://tasems-demo.onrender.com`.

Free plan notes: the site sleeps after 15 minutes without visitors and takes about a minute to wake
up; the free database is deleted by Render after its free period, so the demo is for testing only.

## Option B — on the developer's computer

```bash
docker compose up -d db                       # PostgreSQL for development
cp .env.example .env                          # then set DEMO_MODE=True in .env
python manage.py migrate
DEMO_PASSWORD='choose-a-password' python manage.py seed_demo
python manage.py runserver                    # open http://127.0.0.1:8000
```

## Demo logins (password: the DEMO_PASSWORD chosen above)

| Sign in as | Username | What to try |
| --- | --- | --- |
| Principal | `demo-principal` | Everything for the branch: students, attendance, diary, exams, fees, admissions, staff |
| Class teacher (Class 4-A) | `demo-teacher` | Take today's register, write the diary, enter marks, "My attendance" |
| Accountant | `demo-accountant` | Make vouchers, receive fees, defaulters, daily collection |
| Admissions officer | `demo-admissions` | Inquiries due today, follow-ups, WhatsApp button, admit a child |
| Head office | `demo-headoffice` | All branches, royalty statement, Setup |
| Parent | at `/parents/login/`, mobile **0300-7000001** | The child's diary, attendance, fee voucher, Mid-Term report |

## What the demo contains

Four classes (Play Group, Class 4-A, Class 6 Boys, Pre-9 Boys) with 32 made-up students and parents;
last week's attendance for Class 4-A; today's diary; a published Mid-Term exam with marks; this
month's fee vouchers with some payments; five staff members with a week of machine punches; four
admission inquiries due today.
