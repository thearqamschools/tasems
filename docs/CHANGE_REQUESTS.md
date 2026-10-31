# Change requests from the project lead (19 Oct 2026)

Collected one by one; the lead said "implement" on 19 Oct 2026. Worked in four batches (see the end).

Defaults used where a question was still open (the lead can change any of them):
Father CNIC required · father occupation optional · roll number optional, first in the class block ·
heading "Family details" · no second father mobile · item 5 order used for both list and filters ·
"Received by" as its own column · JazzCash is an entry in the Bank list · special discounts apply at once,
100% discounts need approval · Coordinator kept after Vice Principal · "Lawyer" added as heard.

## Students list (branch portal, e.g. Demo Branch FSD-1)
1. Class and Section are separate fields/columns: Class first, then Section (section = sub-group of a class). Never written together like "Class 4-A".
2. Standard section names per class: Rose, Jasmine, Daisy, Pansy, Tulip (e.g. Play Group has these 5).
3. Status filter: rename "Withdrawn" to "Withdrawn / Left". Active, Transferred out, Graduated are fine.
4. Admission number: plain number only (no letters, no dashes), generated automatically in sequence. Old system uses 4-digit numbers, e.g. 4256, 3661.
5. Order of columns/filters: Admission no → Name → Father name → Class → Section → Parent mobile → Status.
   (Message ended at "Parent mobile" — may continue.)

## Students → Add student
6. "Add student" button at the top of the Students page, above the search, prominent. ("Show students" button below is fine.)
7. Remove ALL Urdu data entry everywhere: no Urdu name fields at all (e.g. "Full name (Urdu)", "Parent/guardian name (Urdu)"). No data typed in Urdu.
8. Fields OK as they are: Admission no, First name, Last name, Gender, Date of birth, Admission date, B-Form number.
9. Father CNIC is required.
10. Class and Section as two separate fields (sections Rose, Jasmine, Daisy, Pansy, Tulip).
11. Roll number: keep for now; decide later.
12. Contacts section with three groups:
    - Father name, Father mobile / WhatsApp
    - Mother name, Mother mobile / WhatsApp
    - Guardian name, Guardian mobile / WhatsApp, Relationship (free text, e.g. uncle, aunt — not a fixed list)
    Required: only father name and father mobile.
    (Unclear: "इसके आगे ऑप्शन दें 2 … फादर मोबाइल" — maybe a second number for father? To confirm.)

## Add student — more (message 3)
13. Student information: add Current address and Permanent address.
14. Class section of the form: Class → Section → Subject group (only for Pre-9th, 9th, 10th: Biology or Computer).
15. Roll number: optional; "bring it first" (position to confirm: top of class part or top of form).
16. Rename "Primary contact" heading to "Contact details" or "Family details".
17. Family details layout (each person on its own row):
    - Father: Name, Mobile/WhatsApp, Occupation, Organisation (occupation "zaroori" — required? to confirm)
    - Mother: Name, Mobile/WhatsApp, Occupation, Organisation
    - Guardian: Name, Mobile/WhatsApp, Relationship (free text), Occupation (organisation can be left out for guardian)

## Add student — more (message 4)
18. Email: father's email, and also an email in student information.
19. At the end of the form (above Save): two free-text fields "Reference" and "Notes".
20. Fee information inside Add student: what this child's fee will be — full fee, sibling discount, or a special discount, and the resulting fee amount. Set here, at admission.

## Admissions (inquiries)
21. Menu item "Admissions" is really inquiries → rename to "Admission Inquiries" (wording to confirm).
22. Must have an "Add inquiry" option there. Inquiry fields: Class, Person name, Contact number, Description, Source (where they came from: social media, where they got the number, etc.).
    (Note for processing: an "Add inquiry" form with source already exists for principal/admissions officer; the demo-network login cannot add, so the button is hidden there.)
23. Admissions report (inquiries from a date, how many admitted, how many not converted): review later.

## Attendance
24. Attendance page table order: Class → Section → Present → Absent → Leave → Register (class and section as separate columns; class teacher column currently also there).
25. Absent students: filter/group by class and by section.
26. Absent students list: instead of one "Parent mobile", show Father mobile and Mother mobile (both), then Note.
(Lead asked how attendance works — explained: teacher marks on mobile, shows here at once, absent list built from it. They said that is fine.)

## Finance — Barcode / quick receive
27. Finance menu: first item "Barcode" (quick receive). One bar at the top: type or scan Voucher ID (e.g. 800001) → choose date (today by default; calendar for yesterday/any past date) → choose where the money came: Cash, Askari Bank, Bank Alfalah, JazzCash, other banks/options → "Pay" → voucher marked paid. All on one screen, fast.
    (Note for processing: the Fees page already has a "scan or type voucher number" box that opens a receive screen with date and method; methods today are generic — Cash at school, Deposited at bank, Bank transfer, JazzCash, Alfa app, Other — no named banks like Askari. Request = own menu item + one-screen flow + named bank accounts list.)

## Finance — who received the fee
28. VERY IMPORTANT: every payment shows who received it (name of the login: admin or accountant). Shown wherever payments are listed/received.
29. Fees page summary figures (Billed for month, Received in month, Vouchers paid, Owed by students) are fine. Add a DAILY block above/with them: defaults to today (date selectable): total received today, and a breakdown per person who received (e.g. A: Rs X, B: Rs Y). Per-person breakdown needed for daily only, not monthly.
    (Note: TASEMS stores received_by on every payment; the separate "Daily collection" page already has a "By person receiving" table, but the payments list there has no "Received by" column and the Fees page has no daily block.)

## Finance — Daily collection page
30. Payments table columns, in this order: Date → Voucher ID → Student name → Father name → Method → Received by (in brackets after the method, a separate column, or in Reference — wording to confirm). Remove "Receipt number" column (Voucher ID is the key).
31. Payment methods grouped:
    - Cash at school (+ who received it)
    - Online: Askari Bank, Bank Alfalah, JazzCash (three options)

## Finance — Discounts
32. Sibling discount automatic: first child full fee (e.g. 4,300); a brother/sister with the same father CNIC automatically gets the sibling fee (e.g. 4,000).
    (Note: sibling rate by father CNIC already exists in fee rates — check it is applied automatically and visible at admission.)
33. Discount types that head office defines itself (a list in Setup), chosen on the admission form:
    - 10%, 20%, 30%, 50%, 60% off
    - Scholarship: 100% waived
    - Staff child: 50% off
    - Staff child: 100% off
    - (more can be added later)
    At admission: if sibling → applied automatically; otherwise choose a discount type from the list.

## Staff
34. Staff page: "Add staff member" and "Import staff from Excel" buttons at the top (e.g. top right, wherever the design fits best).
35. Add staff form:
    - Attach CV (JPG or PDF)
    - Employee code, Full name; REMOVE "Full name (Urdu)"
    - Father name (required, always) — not "Father/Husband name"; separate optional "Husband name"
    - CNIC, Date of birth, Mobile, Other phone, Email
    - Two addresses: Permanent address and Present address
    - Designation: very important — fixed list, and logins/permissions follow the designation.
36. Designations (in this order; each gets its own access level):
    Director (full access to the branch) → Principal → Vice Principal → Coordinator (more access than teachers) → Accountant → Admin →
    Senior Teacher → Junior Teacher → Qari → Guard → Aapa → Janitorial staff → Office boy → Helping staff / Other (open-ended) → Lawyer(?)
    (Coordinator was in the first listing but not the second; "Lawyer" heard as लॉयर — to confirm.)
37. Staff form rest is fine: Staff type (Teacher, Qari, Administration, Office, Board/support staff), Campus, Qualification, Joining date, Notes.
38. Staff attendance: review later, once machine attendance is running. Monthly sheet → payroll is built from the monthly sheet.

## Finance — Expenses (new)
39. Branch expenses with a full accounting cycle: record each expense, who made/approved it, where the money came from (cash in hand, bank account, etc.).
    (Note: this is roadmap M9 Accounting — expenses, other income, cash/bank book, branch P&L, head-office consolidation — already approved; may be moved earlier.)

## Finance — Royalty (payments and balance)
40. Royalty ledger per branch, per month: royalty due (calculated as now) → royalty paid to head office → pending. Pending carries forward and adds up month to month, with a running "Total due".
    Example: month 1 due 100,000, paid 50,000 → pending 50,000; month 2 due 20,000, paid 10,000 → pending 10,000; total due 60,000.
41. Shown in both places: the branch sees its own royalty (due, paid, pending, total due); head office sees all branches.
42. Head office has a "Royalty received" section to enter payments from a branch (amount, date) with an attachment (image of the deposit slip / proof).
43. Fee payment attachment: when receiving a fee (especially bank / JazzCash / online), optional attachment (image of the receipt/screenshot) can be added to that payment.

## Campus dashboard (Overview)
44. Existing figures fine (Active students, Registers taken today, Attendance, Diary, Fee received this month, Fee collection %). ADD: total fee received TODAY.
    Clicking it opens today's breakdown: cash (and which person received how much), JazzCash, Bank Alfalah, Askari Bank, other banks.
45. Fee collection methods defined in Settings per branch: Cash, and the branch's own online channels/banks (JazzCash, Alfalah, Askari, UBL, HBL, ...). Branch can add its own bank. (Answers the earlier question: list is per branch, editable.)
46. Simplify fee collection methods to TWO: Cash or Bank.
    - Cash → shows the receiving login's designation and name.
    - Bank → which bank (from the branch's own list in Settings: Askari, Alfalah, UBL, HBL, ... ; JazzCash presumably an entry in this list — to confirm).
    (Supersedes the method lists in items 27, 31, 45.)

## Progress
| Batch | Items | Status |
| --- | --- | --- |
| 1 — Students | 1–19 (fee at admission → batch 3) | Done 19 Oct 2026 |
| 2 — Inquiries, attendance, staff | 21–26, 34–38 | Done 19 Oct 2026 (designation → login permissions: table to approve) |
| 3 — Fees | 20, 27–33, 43–46 | Done 19 Oct 2026 |
| 4 — Royalty, expenses | 39–42 | Done 19 Oct 2026 (expenses = first part of M9 Accounting; cash/bank book and P&L follow) |

# Round 2 (from 22 Oct 2026) — approved for processing ("ہاں فائنل ہے، اب سب بنا دیں") and built 22 Oct 2026

## Vouchers — Generate vouchers
R2-1. "Generate vouchers" option inside Vouchers. Screen: Month (e.g. October) → Class (All classes, each class, then Hifz Boys and Hifz Girls) → Section (All sections or one section).
R2-2. Below that, the voucher contents (fee heads) are listed with tick boxes, to choose what to add this time: e.g. summer vacation fee, AC charges, annual charges, and every other fee head.
R2-3. Generating gives each voucher a unique Voucher ID that never repeats. Admission numbers are also unique and cannot be created twice.
   (Note for processing: "Make vouchers" exists under Finance (needs voucher permission; not shown to demo-network) with month range, due date and a multi-select of sections; voucher numbers are already unique across the network and admission numbers unique per branch. Request = inside Vouchers, Class → Section dropdowns with Hifz Boys/Girls, and fee-head tick boxes.)

## Vouchers — heads, arrears month by month, editing at receipt (22 Oct 2026)
R2-4. New fee head "AC charges", placed next to "Generator charges".
   (Note: TASEMS has no "Generator charges" head yet — heads today: Admission, Registration, Monthly fee, Annual, Summer vacation work, General expenses, Other charges, Late fine. Add both.)
R2-5. Remove the "Arrears" column from vouchers. Unpaid amounts show under their own month: e.g. if October is unpaid, the October row shows October's amounts.
R2-6. When a new month's voucher is made, all earlier unpaid months come on it month by month (Oct + Nov, or 3–5 months), with their fines — one combined voucher.
R2-7. Edit a voucher when receiving payment (from Pay / Vouchers): the person receiving can change Other charges, AC charges, Summer vacation, Annual charges etc. (add or reduce), and the amount paid — but NOT the monthly (tuition) fee. The Voucher ID stays the same after editing.
   (Note for processing: today unpaid vouchers are "carried to a newer voucher" (superseded) and earlier dues appear as one Arrears figure; partial payments are allowed per branch setting. Editing must be recorded in the history with who changed what.)

## Round 2 — how it was built (22 Oct 2026)
| Item | Where | Notes |
|---|---|---|
| R2-1 | Vouchers → "Generate vouchers" (also in the Finance menu) | Month (and optional "until month"), due date, Class (All classes, each class, Hifz Boys, Hifz Girls), Section (All or one). Hifz Boys/Girls also filter by the student's gender, because Hifz sections are often mixed. |
| R2-2 | Same screen, "Add these fees as well" | Tick boxes for every fee head except the monthly fee (always added), the late fine (automatic) and admission/registration (one student's voucher). Annual is pre-ticked in April and Summer vacation in its months, but only ticked fees are added. A ticked fee with no amount set for the branch is warned about on the check step. |
| R2-3 | — | Voucher IDs come from one network-wide counter (never repeated, tested); admission numbers stay unique per branch. |
| R2-4 | Fee heads | "Generator charges" and "AC charges" added (after Summer vacation work). **Default:** their amounts are set per branch in Setup → Fee rates and vouchers, and they are added only when ticked. |
| R2-5 / R2-6 | Voucher print | No Arrears column. Each unpaid month has its own row (fines in that month's row); with more than 3 months the oldest share one row so all three copies fit on the page. An advance shows as "Advance paid". |
| R2-7 | Receive fee page → "Change other fees on this voucher" | Change, remove (0) or add other fees (Other, AC, Generator, Summer vacation, Annual…) on the student's newest voucher. The monthly fee and the late fine are shown as fixed and refused by the server. The Voucher ID stays the same; the amount on the voucher is recalculated; every change is in the history (who, which fee, from → to). The amount received was already editable when the branch allows part payments. |

## Round 2 follow-ups (22 Oct 2026) — built the same day
- R2-8. Remove "Generator charges"; keep "AC charges". The generator is already billed as "Gen. Exp." (now named "Generator expenses").
- R2-9. Current designation → login permissions table, for the lead to mark changes: `docs/DESIGNATION_PERMISSIONS.md`.
- R2-10. Add the usual school expense heads; no branch-own heads for now.
- R2-11. Certificates print on the letterhead: remove the logo and school heading, keep only the title.
- R2-12. Certificate reference number = branch start + unique number, e.g. HO-FAISALABAD-FSD-0001. Each branch's start is different and is set in Setup → Branches. Only the head office campus was given by the lead; other branches use their branch code until head office fills it in.
- Asked: the cost of a private test server (answered in chat; nothing bought).

## Round 3 (28 Oct 2026) — built on 28 Oct 2026 (Windows installer v6)
The lead listed the changes one by one and said "haan ji, ab kar do" the same day; all built together
(CHANGELOG 0.36.0, D-090). R3-11 was withdrawn.

### Setup → Classes and sections
- R3-1. The sections table shows the class and section together in one "Section" column. Split it into separate
  columns: **Class** | **Section** | **Boys / Girls** | **Campus** (then class teacher, students, capacity as now).
- R3-2. **Campus is required** for every section (marked with *).
  How campuses work in the branches (for information): Play Group to Class 5, boys and girls both study in the
  girls' campus; from then on boys move to the boys' campus and girls stay in the girls' campus.
- R3-3. In the Boys / Girls column, write **"Boys and Girls"** with a capital G (now "Boys and girls"), as the
  branches already use it.

### Students → Add / Edit student
- R3-4. Remove the **"Father email"** field from the Contacts part of the Add student and Edit student forms.
  The **"Email"** field higher up on the form stays and is the one email for the student.

### Campus lists everywhere
- R3-5. Wherever a campus is chosen from a list (Setup → Classes and sections → Edit, and every other place that
  asks for a campus), the list shows **only the campus name**, not the school and branch in front of it
  (now e.g. "The Arqam Schools — Samanabad Campus (Head Office) — Boys Campus").
  Order: **Girls Campus first, then Boys Campus**.

### Students list — parent mobiles
- R3-6. The **Parent mobile** column shows **both** the father's and the mother's mobile.

### Parent Tree slip (from the old software) — photos in `docs/reference/parent-tree/`
Used to call children out of class: when a father comes to take his children early, the office prints a slip
with the child and all brothers and sisters, and the children are called with it.
- R3-7. **Where:**
  - Students list: a new **Parent Tree** column after Status, with a small printer icon on every row.
  - Student page: a small Parent Tree icon next to the student's name, and a **Parent Tree** button after
    "Edit student" (with Delete, Fees, ID card…).
  - One click prints straight away (the old software asked "Are you really want to print Parent Child Tree?"
    with Confirm / Cancel; the lead asked for a simple click).
- R3-8. **The slip** (copy of the old one):
  - Logo, **THE ARQAM SCHOOLS**, Sanora Colony Samanabad Faisalabad, (041-2660265, 041-2406479).
  - Title **Parent Tree**; **Parent Name** (father) and the **date and time** of printing.
  - Table: **Campus** (Girls / Boys) | **Comp. Code** (admission no) | **Student Name** | **Class** | **Section**,
    one row for the child and each brother / sister.
  - Footer "Thank you" (the old slip says "Thanks you").
- R3-9. **Printer:** SPEEDX SPEED-X 400UL thermal receipt printer, **80 mm** paper, USB + LAN, ESC/POS.
  The slip is laid out for 80 mm roll paper.
- Decided by the lead (28 Oct 2026):
  - Brothers and sisters are **always** found by the **father's CNIC**; every current brother and sister is on
    the slip.
  - Only **current (present) students** are on the slip; those who left school are not.
  - A Parent Tree can be printed **only for a current student**; for a student who has left, the option is not
    shown.
  - The address and phones on the slip come from the branch's own details (R3-10).

### Setup → branch contact details and banks (used on slips, vouchers and wherever needed)
- R3-10. Each branch has its own **Address**, **Phone 1**, **Phone 2**, **Mobile 1**, **Mobile 2**, entered in
  Setup. These print wherever the school's contact is shown (Parent Tree slip, vouchers, …) instead of fixed text.
- R3-11. ~~Several banks on the voucher~~ — **withdrawn by the lead (28 Oct 2026):** the voucher keeps showing
  **one bank**, as now (Setup → Fee settings). Nothing to change.

### Class names (added while building, 28 Oct 2026)
- R3-12. Class names in words, without the word "Class": Play Group, Nursery, Prep (unchanged), then **One, Two,
  Three, Four, Five, Six, Seven, Eight, Pre-Nine, Nine, Ten** (capital first letter). Hifz-e-Quran unchanged.
  Everywhere a class is shown. Excel import still accepts the old names (Class 1 … Class 10, Pre-9) and numbers.
- R3-13 (28 Oct 2026). The printer is on **LAN** (not USB). Parent Tree must print **straight away — no new window,
  no print window**. Built: TASEMS sends the slip to the printer's network address (Setup → Branches).
- R3-14 (28 Oct 2026). The printer's IP could not be found (self-test did not work, no official SPEEDX driver
  online). Built: Setup → Receipt printer finds it on the network, prints a test slip and saves it (v8).

## Round 4 (30 Oct 2026) — built 30 Oct 2026 (Windows installer v10)
- R4-1. **Events & Tickets** (name to confirm): school events such as Eid Milan party, Summer Gala, trips, farewell.
  - Set up an event: name, type, date, which classes (from–to), ticket price per class.
  - Sell tickets at the office **without a voucher**; cash at first (other payment ways kept possible).
    "Received by" = the login that took the money, by name.
  - Receipt printed on the same receipt printer as Parent Tree, given to the parent.
  - Event expenses; tickets sold and money collected per class; profit or loss of the event.
  - Its **own account**, not linked to school fees or the school's accounts.
- R4-2. Parent Tree slip shows the **name of the person (login) who printed it**.
- Decided by the lead: name **Events & Tickets**; student ticket **plus extra tickets** for parents/guests; Director
  and Principal make events, Director/Accountant/Admin take the money; **refunds allowed** with a reason.

## Round 5 (31 Oct 2026) — built 31 Oct 2026 (Windows installer v11, CHANGELOG 0.40.0, D-093)

### Students → search and filters
- R5-1. Student search also finds by **mobile number** — the father's, mother's or guardian's, any of them — and
  by **CNIC** (father CNIC, and the student's B-Form). Every student with that mobile number is shown.
  (Today: admission no., name, father name; mobile only partly.)
- R5-2. Filters: Class, Section, then a new **Campus** filter (Boys Campus / Girls Campus — choose one), then
  Status.

### Events & Tickets
- R5-3. Events list: the **whole row** of an event opens it (click anywhere on the row), not only its name.
- R5-4. Sell tickets: the same search as Students (R5-1) — student name, father name, admission no., **any mobile
  number** (father, mother, guardian), **CNIC / B-Form** — plus filters **Class, Section, Campus**, so a whole class
  (or section, or campus) can be listed at once. From that list the office sells tickets one student after another
  (each sale prints its receipt and the list stays, showing who already has a ticket).
- R5-5. Sell tickets → "Your last receipts": show the student's **admission no., name, class and section** (today
  only the name).
- R5-6. Event page → Receipts → **Print**: today it prints the whole page. It must print **only the receipts list**
  (the tickets sold), as a report: first the paid receipts, then the **refunded ones in a separate part at the
  end**, so it is clear which tickets are sold. (The on-screen list follows the same order.)

### Side menu
- R5-7. Left side menu: each heading (Overview, Students, Academics, Finance, Events, Staff, Settings) becomes a
  **drop-down** — click the heading to open or close its items, so one can go straight to e.g. Events without
  scrolling past all of Finance. (To decide when building: the group of the page you are on stays open; the
  open/closed choice is remembered on that computer.)

### Events & Tickets — event report
- R5-8. A **Report** button on the event page opens one printable report (A4) of the event:
  - **Detail part**: first all receipts sold (paid), then the **refunded** receipts (if any) in their own part,
    then the **expenses**.
  - **Summary on a separate page**: tickets sold and amount (refunds not shown here, only what was sold and kept),
    expenses, totals, and **profit or loss**.
  (R5-6 — printing only the receipts list — is covered by this report.)
- R5-9. The event report (R5-8) also shows **who received how much**: cash received by each person (name, receipts,
  amount), and money that came **in each bank** (and JazzCash / Easypaisa) — so the cash and bank amounts can be
  checked. (Ticket sales by bank then choose the bank, like fee receiving.)

### Staff
- R5-10. Staff list: the **whole row** of a staff member opens them (not only the name).
- R5-11. Staff member's page: a **Back** link to the staff list (today there is no way back).
- R5-12. Add / Edit staff member:
  - The present "Qualification" box becomes **Last qualification**.
  - Below, in this order, three parts where any number of rows can be added:
    1. **Qualifications** — level (Matric, Intermediate, Bachelor's, Master's, PhD; usual extras to confirm:
       O/A-Level, Diploma, MPhil), degree / title, subjects or major, board / university, year passed, marks %
       or CGPA, grade / division.
    2. **Certificates** (courses, trainings) — name, institute, year, duration.
    3. **Experience** — organisation, designation / post, from, to (or "still working"), reason for leaving,
       (classes / subjects taught — to confirm).
  - Then Save.
- R5-13. ~~Monthly salary on the staff form~~ — **withdrawn by the lead (31 Oct 2026)**: salaries and bank /
  cash details stay in **Payroll → Salaries and bank details** only. (Original note: a **Monthly salary (Rs)** box after Date of joining and Biometric (machine) ID.
  Shown and saved only for logins with payroll rights (Director, Accountant; Principal sees, cannot change); others
  do not see the box. It is the same salary as Staff → Payroll → Salaries (one record, with history).
  Asked: where is the salary module today → **Staff → Payroll** (side menu), button **Salaries**.
- R5-14. Add / Edit staff member: **CV upload moves to the top** (first line of the form), not at the end. Notes and
  Biometric machine ID stay as they are.

### Payroll (found by the lead under Staff → Payroll, 31 Oct 2026) — make it complete and professional
- R5-15. Linked to staff attendance as today, plus:
  1. **Enter manually** (button on the Payroll page, for the month shown): all staff listed; for each person type
     days in the month, working days, days on staff, absent, unpaid leave, half days → TASEMS works out deduction
     and net pay. For when the machine was out of order or the sheet is wrong. Manual figures are marked as manual
     and replace the machine figures for that person and month.
  2. **Search** by staff name and **filter by designation** (teachers, vice principal, admin staff, sweeper…) on
     Payroll and on Salaries and bank details.
  3. **Totals at the top** of the month: total salaries, deductions, net pay to pay, **paid so far**, **still to pay**.
  4. **Pay salary** (tab / button): the month's staff list; open a person → that month's detail (salary, days on
     staff, absent, unpaid leave, half days, deduction, net pay) → **pay**: date, **cash or bank transfer**
     (bank from their bank details), then it is **locked**. People are paid on different days. The Payroll table
     shows for each person: Paid / Not paid, how, and the date.
  5. **History** of each person: every month from the start — salary, net pay, date paid, how — so increases or cuts
     can be seen (a table; a graph is not needed).
  6. Kept from before: **increments** (new salary from a month, amount, reason, approved by), **salary sheet** (A4)
     with a **signature column** for cash payments, **bank transfer sheet**.
  7. **Salary acknowledgement sheet** (print, A4), after the month's figures are ready (from the machine or entered
     manually): title "Payroll — <Month Year> — Acknowledgement", **one page (or set of pages) per designation group**
     — administration, teachers, helping staff… — each with a list: name, designation, monthly salary, days absent,
     unpaid leave, half days, deduction, net pay, **payment received by: Cash / Bank / Online** (tick; no bank
     details), **"Payment received"** and a **signature** column, with signature lines at the bottom (prepared by,
     checked by, principal / director). Kept on paper as the school's record; can be printed again at any time.
     (Replaces the plain salary sheet of item 6.) Groups to confirm when building, from the designations list.
  - To confirm when building: "working days" in manual entry — today a day's pay = salary ÷ days in the month
    (decided 23 Oct 2026). Working days would be shown but not change the rate, unless the lead says otherwise.

## Round 6 (31 Oct 2026) — NOTED ONLY, not built yet
Build nothing until the lead says to make the changes; then all together (next Windows installer: v12).

### Payroll
- R6-1. Column order: **Employee code first**, then Name, Designation, Monthly salary, then the rest (code is
  now written after the name).
- R6-2. **Absent only**: remove the separate "Unpaid leave" column — there is no paid/unpaid idea, every absence is
  unpaid. Days columns: Absent, Half days (unpaid leave days count as absent). Working days stay automatic.
- R6-3. After Half days, before Deduction: **GP Fund** and **EOBI** — deduction columns kept **empty for now**
  (not used yet; to be decided later), only the place is kept.
- R6-4. **Bonus** (attendance bonus): a staff member with **no absence** in the month gets **one extra day's
  salary**. Columns after Half days: **Bonus days** and **Bonus amount**; net pay includes it.
  - **Decided by the lead (31 Oct 2026)**: a **half day also stops the bonus**. The bonus applies **only** to these
    designations: **Aapa, Guard, Peon (Office boy), Qari, Sweeper (Janitorial staff)**. Not to anyone else
    (Director, Principal, Vice Principal, Coordinator, Admin, Accountant, teachers, Lawyer, Helping staff / Other).
  - The **rules are set in Setup** (to choose the best place): bonus on or off, how many days, and which
    designations get it (the list above to start with). Column order is ours to arrange.

### Payroll — salary security
- R6-5. **Security**: for some staff, the school keeps **one salary as security** (usually the **first** month's
  salary, e.g. Rs 15,000). It is given back when the person leaves **with proper notice**.
  - Payroll: a setting per person — security held: amount, which month's salary was kept (e.g. "first salary,
    October 2026"), date. That month's net pay is **held, not paid** (shown as "Held as security").
  - When a staff member **leaves** (Staff → leaving date / status), TASEMS asks: **return the security or not**.
    Left with proper notice → returned (date, how: cash / bank, by whom). Left **without notice** → **not
    returned** (forfeited), with the reason.
  - A list of securities held, returned and kept (forfeited), per branch.
  - To confirm when building: the security is always the full **first** month's net pay, or any amount / month
    chosen per person? Who decides return or not (Director, Accountant)?

### Payroll — advances
- R6-6. **Salary advance**, two kinds:
  1. **Advance from this month's salary**: e.g. salary Rs 15,000, paid on the 10th; the person takes Rs 5,000
     earlier (on an application). It is **cut from that month's salary** (net pay 10,000).
  2. **Large advance in instalments (loan)**: e.g. salary 15,000, advance Rs 50,000, cut **Rs 5,000 every month**
     until it is paid back — the person gets 10,000 for those months, automatically.
  - Recorded with: date given, amount, cash / bank, approved by, application / reason, and for instalments the
    monthly cut and the month the cuts start. Payroll shows an **Advance** column (deduction); each person's
    page shows the advance, what is cut so far and **what is still due**; a list of all advances with balances.
  - To confirm when building: can a month's instalment be skipped or changed (e.g. Eid month)? When a person
    leaves with an advance still due, is it cut from their last salary / security?
