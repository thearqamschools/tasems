# Trying TASEMS (demo server)

A demo server runs the real software with **fictional data**, so the team can try every screen.
It is not the pilot server: no real student data goes on it, and two-step sign-in is switched off
so testers do not need an authenticator app. Every page shows a red "DEMO" bar.

## Option A — Render.com (a public link, free plan)

1. Sign in at <https://dashboard.render.com> with the school's GitHub account (thearqamschools).
2. Give Render access to the `tasems` repository when asked.
3. Click **New → Blueprint** and choose the `tasems` repository. To see the upgrade work in progress,
   set **Branch** to the newest `upgrade/…` branch (e.g. `upgrade/m3-setup`) instead of `main`.
   Then **Apply**. Every new push to that branch redeploys the demo automatically.
4. Render asks for `DEMO_PASSWORD`: type a password of at least 10 characters. All demo logins use it.
5. Wait for the first build (about 10 minutes). The link looks like `https://tasems-demo.onrender.com`.

Checked on 19 Oct 2026 by running the blueprint's start command locally on an empty database with
`DEBUG=False`: tables created, demo data loaded (about 16 s; a restart does not duplicate it), all five
staff logins and the parent sign-in page work, fee voucher PDFs download, unknown web addresses are refused.

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
| Head office | `demo-headoffice` | Faisalabad head office: its branches (Samanabad + Demo Branch FSD-1 to FSD-3), royalty statement, Setup |
| Network (both head offices) | `demo-network` | All 7 branches in Faisalabad and Lahore: network dashboard with filters by head office and region, royalty statement, Setup → Branches and regions, Users and roles, Academic sessions |
| Principal of a demo branch | `demo-principal-fsd-1` … `demo-principal-lhr-3` | One fictional branch each |
| Parent | at `/parents/login/`, mobile **0300-7000001** | The child's diary, attendance, fee voucher, Mid-Term report |

## What the demo contains

Four classes (Play Group, Class 4-A, Class 6 Boys, Pre-9 Boys) with 32 made-up students and parents;
last week's attendance for Class 4-A; today's diary; a published Mid-Term exam with marks; this
month's fee vouchers with some payments; five staff members with a week of machine punches; four
admission inquiries due today.

For head office there is also a fictional network: six "Demo Branch" campuses (FSD-1 to FSD-3 under
Faisalabad, LHR-1 to LHR-3 under Lahore) in four demo regions, franchise and company-owned, each with
three classes of 10 made-up students, two weeks of registers (some branches not yet taken today),
this month's vouchers with different collection rates, and a royalty statement. It is added the next
time the demo starts, also to a demo that is already running.
