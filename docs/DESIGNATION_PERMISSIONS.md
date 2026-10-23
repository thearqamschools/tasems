# Designation → login permissions (approved by the project lead, 23 Oct 2026)

This table shows **what TASEMS does today**, as set by the project lead on 23 Oct 2026 (D-083).

**How it works today:**
- A staff member's **designation** (Staff → Add staff) and their **login** are separate.
- A login gets its permissions from the **role** chosen in Setup → Users. The designation does not give any permission by itself.
- Column 2 is the role that fits each designation best today. It is a suggestion; nothing links them automatically yet.
- Once the table is approved, TASEMS can suggest (or set) the role from the designation when a login is made.

**Flow:** Staff → Add staff (designation) → Setup → Users → make a login → choose the role (column 2) → the login can do what column 3 says, in its own branch only.

## 1. Branch staff (designations from Staff → Add staff)

**Fees are received only by the Director, the Accountant and the Admin.**

| # | Designation | Login role | What that login can do |
|---|---|---|---|
| 1 | Director | Branch Owner / Franchisee | **Everything in the branch**, seeing and doing: students, inquiries, attendance, diary, marks, fees (vouchers, receiving, discounts and approvals, fee rates and settings, cancelling), royalty, expenses and other income, cash & bank book, profit & loss, staff, payroll, shop & stock, Hifz, notices, needs attention, sections and campuses. |
| 2 | Principal | Principal | Students (add, change, leave school, certificates, promotion), inquiries, attendance (mark and correct), diary, marks (enter and correct), staff (add, attendance, approve leave, holidays), Hifz (any day, para tests, cancel a test), notices and parent messages, needs attention (whole branch, with unpaid fees), sections and campuses. **Sees payroll** (cannot change it) and **only the fee defaulters list**. **No** fee receiving, other fee figures, expenses, accounting or shop. |
| 3 | Vice Principal | Academic Coordinator | Attendance (mark and correct), diary (write and approve), marks (enter and correct), sections (add and change), Hifz (any day, para tests), needs attention, **fee defaulters list only**. **No** staff, payroll, shop or other fees. |
| 4 | Coordinator | Academic Coordinator | Same as Vice Principal. Can also be given a whole region. |
| 5 | Accountant | Accountant | Vouchers, **receiving fees** (Cash/Bank, Barcode page), adding charges, asking for discounts, defaulters and fee reports; expenses and other income (record and cancel), opening balances, cash & bank book, profit & loss; **shop & stock** (items, stock in / out, selling, cancelling a sale); **payroll in full** (salaries, finalise the month, payslips, bank sheet); sees staff list, staff attendance and leave. |
| 6 | Admin | Admissions Officer | Students (add and change, including leave school, certificates and promotion), inquiries and follow-ups, admission vouchers, **receiving fees**. |
| 7 | Senior Teacher | Class Teacher | For the class assigned: daily attendance, diary, marks and remarks, needs attention. |
| 8 | Junior Teacher | Class Teacher | Same as Senior Teacher when a class is assigned. |
| 9 | Qari | Hifz Teacher | Hifz only: attendance, diary, the Hifz sheet of own section (today), para tests. |
| 10 | Guard | No login | — |
| 11 | Aapa | No login | — |
| 12 | Janitorial staff | No login | — |
| 13 | Office boy | No login | — |
| 14 | Helping staff / Other | No login | — |
| 15 | Lawyer | No login | — |

## 2. Head office and regional logins (not branch designations)

| Login role | Covers | What it can do today |
|---|---|---|
| Network Administrator | All head offices and branches | Setup of the whole network: branches, regions, sessions, class levels, subjects, exam setup, fee heads and rates, voucher counter, staff setup, users and roles, diary design, audit history, message templates. Posts notices for any branch. Records royalty received. Sees attendance, expenses, payroll, shop & stock, Hifz and inquiries everywhere. **Does not** receive fees or mark attendance. |
| Head Office Administrator | One head office (Faisalabad or Lahore) and its branches | Same as Network Administrator, for its own head office only (message templates stay with the Network Administrator). |
| Regional Director | One region's branches | Sees everything in those branches (like Branch Owner). Approves 100% discounts. |

## 3. Things that apply to every login
- Everyone sees only their own branch (or head office or region). The database also enforces this.
- Nobody can give someone more access than they have themselves. Nobody can change their own roles.
- Principal, Accountant, Branch Owner, Regional Director and the administrators must use two-step sign-in (a code from an authenticator app) on the real server. It is off only on the demo server.
- One person can hold more than one role, for example Principal in one branch and Coordinator in a region.
- Every change is recorded in the history: who, what, when.

## 4. Changes
Any change to a row is made in `apps/accounts/management/commands/seed_tasems.py` (role permissions) and takes
effect for every login with that role when `seed_tasems` runs on deploy.
