# Designation → login permissions (current, 22 Oct 2026)

This table shows **what TASEMS does today**, for the project lead to mark changes.

**How it works today:**
- A staff member's **designation** (Staff → Add staff) and their **login** are separate.
- A login gets its permissions from the **role** chosen in Setup → Users. The designation does not give any permission by itself.
- Column 2 is the role that fits each designation best today. It is a suggestion; nothing links them automatically yet.
- Once the table is approved, TASEMS can suggest (or set) the role from the designation when a login is made.

## 1. Branch staff (designations from Staff → Add staff)

| # | Designation | Login role today (suggested) | What that login can do today |
|---|---|---|---|
| 1 | Director | Branch Owner / Franchisee | Sees everything in the branch (students, attendance, diary, results, fees, royalty, staff, inquiries). Approves 100% discounts. Cannot enter or change anything else. |
| 2 | Principal | Principal | Everything in the branch: students (add, change, leave school, certificates, promotion), inquiries, attendance (mark and correct), diary, exam marks (enter and correct), fees (vouchers, receive, change charges, approve discounts, branch fee rates and settings), expenses (record and cancel), staff (add, attendance, approve leave, holidays), sections and campuses. Sees royalty and the users list. |
| 3 | Vice Principal | Academic Coordinator (or Principal, if the Vice Principal also handles fees and staff) | Students (view), sections (add and change), attendance (mark and correct), diary (write and approve), exam marks (enter and correct). **No fees, staff or expenses.** |
| 4 | Coordinator | Academic Coordinator | Same as Vice Principal above. Can also be given a whole region. |
| 5 | Accountant | Accountant | Students (view), fees: make vouchers, receive fees (Cash/Bank, Barcode page), add charges, ask for discounts (cannot approve), change other fees on a voucher while receiving. Records expenses (cannot cancel them). Sees staff list, staff attendance and leave. Cannot change fee rates. |
| 6 | Admin | Admissions Officer | Students (add and change, **including leave school, certificates and promotion**), inquiries and follow-ups, admission vouchers (admission and registration fee). Sees fees. Cannot receive fees. |
| 7 | Senior Teacher | Class Teacher | Students (view), marks attendance for the class, writes the diary, enters exam marks and remarks. |
| 8 | Junior Teacher | Class Teacher (if in charge of a class) or Subject Teacher | Subject Teacher: students (view only), sees attendance, diary and results. Cannot enter anything. |
| 9 | Qari | Hifz Teacher | Students (view only), marks attendance, writes the diary. |
| 10 | Guard | No login | — |
| 11 | Aapa | No login | — |
| 12 | Janitorial staff | No login | — |
| 13 | Office boy | No login | — |
| 14 | Helping staff / Other | No login | — |
| 15 | Lawyer | No login | — |

## 2. Head office and regional logins (not branch designations)

| Login role | Covers | What it can do today |
|---|---|---|
| Network Administrator | All head offices and branches | Setup of the whole network: branches, regions, sessions, class levels, subjects, exam setup, fee heads and rates, voucher counter, staff setup, users and roles, diary design, audit history. Records royalty received. Sees attendance, expenses and inquiries everywhere. **Does not** receive fees or mark attendance. |
| Head Office Administrator | One head office (Faisalabad or Lahore) and its branches | Same as Network Administrator, for its own head office only. |
| Regional Director | One region's branches | Sees everything in those branches (like Branch Owner). Approves 100% discounts. |

## 3. Things that apply to every login
- Everyone sees only their own branch (or head office or region). The database also enforces this.
- Nobody can give someone more access than they have themselves. Nobody can change their own roles.
- Principal, Accountant, Branch Owner, Regional Director and the administrators must use two-step sign-in (a code from an authenticator app) on the real server. It is off only on the demo server.
- One person can hold more than one role, for example Principal in one branch and Coordinator in a region.
- Every change is recorded in the history: who, what, when.

## 4. For the project lead
Please mark the changes against each row:
- a different role, or
- "can also do …" / "should not do …".

TASEMS will then be changed to match the approved table.
