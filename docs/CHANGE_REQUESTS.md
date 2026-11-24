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

## Round 6 (31 Oct 2026) — built 31 Oct 2026 (Windows installer v12, CHANGELOG 0.41.0, D-094)

### Payroll
- R6-1. Column order: **Employee code first**, then Name, Designation, Monthly salary, then the rest (code is
  now written after the name).
- R6-2. **Absent only**: remove the separate "Unpaid leave" column — there is no paid/unpaid idea, every absence is
  unpaid. Days columns: Absent, Half days (unpaid leave days count as absent). Working days stay automatic.
- R6-3. After Half days, before Deduction: **GP Fund** and **EOBI** — deduction columns, **shown always**, empty
  (0) unless an amount is **typed in by hand** for a person and month (e.g. on Enter manually); no automatic rule.
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
  - Payroll shows a **Security** column (the cut each month) and each person's page the security collected so
    far, still to collect, and held.
  - When a staff member **leaves** (Staff → leaving date / status), TASEMS asks: **return the security or not**.
    Left with proper notice → returned (date, how: cash / bank, by whom). Left **without notice** → **not
    returned** (forfeited), with the reason.
  - A list of securities held, returned and kept (forfeited), per branch.
  - **Decided by the lead (31 Oct 2026)**:
    - Security = **one month's salary** (the monthly salary, e.g. 15,000). It is chosen **when the staff member is
      added**: Add / Edit staff → tick **"Keep salary security"**; no tick, no security.
    - Also chosen there: collected in **1, 2 or 3 months** (e.g. 15,000 in 3 months = 5,000 a month), cut from
      the net pay of the first months and kept aside.
    - If a month's net pay is less than the cut (e.g. absent days in the first month: net 12,000 instead of
      15,000), the rest is **cut from the next month's pay**, until the full security is collected.
    - **Director and Accountant** (both) decide whether it is returned when the person leaves.

### Payroll — advances
- R6-6. **Salary advance**, two kinds:
  1. **Advance from this month's salary**: e.g. salary Rs 15,000, paid on the 10th; the person takes Rs 5,000
     earlier (on an application). It is **cut from that month's salary** (net pay 10,000).
  2. **Large advance in instalments (loan)**: e.g. salary 15,000, advance Rs 50,000, cut **Rs 5,000 every month**
     until it is paid back — the person gets 10,000 for those months, automatically.
  - Recorded with: date given, amount, cash / bank, approved by, application / reason, and for instalments the
    monthly cut and the month the cuts start. Payroll shows an **Advance** column (deduction); each person's
    page shows the advance, what is cut so far and **what is still due**; a list of all advances with balances.
  - **Decided by the lead (31 Oct 2026)**:
    - A month's instalment **can be skipped or made smaller** (the rest stays due and the cuts carry on after).
    - When a person **leaves with an advance still due**, it is cut from their **last salary and then their
      security**. If something is **still due after that**, it stays as an amount to recover from the person —
      **management decides** (shown as "still due after leaving"; recorded when paid back or written off, with
      who decided).

### Payroll — extras accepted by the lead (31 Oct 2026)
- R6-7. **Final settlement** page / print when a staff member leaves: last month's pay, bonus, advance still due
  cut, security returned or kept, and at the end **amount to pay or to recover**; signature lines for Director
  and Accountant.
- R6-8. **Other deduction** and **Other addition** for a person and month, amount and reason typed by hand (fine,
  damage, arrears…).
- R6-9. **Advance application** (photo / scan) can be uploaded with the advance.
- R6-10. **Payslip and acknowledgement sheet** show all the new columns: Bonus, Advance, Security, GP Fund, EOBI,
  Other deduction / addition.
- (Late-arrival rule — "3 lates = 1 half day" — **not wanted**.)

### Events & Tickets — Sell tickets
- R6-11. After a search shows the student (e.g. 1385, 1398), the **search box is empty again**, so the next
  admission no. can be typed at once — also after a sale (today the old number stays and must be deleted first).
- R6-12. **Remove "Sell again"**: once a student has a ticket, no second sale button (shows "Has a ticket" only).
- R6-13. **One line per student**: Paid by and the **Receive and print** button **beside** the other fields, small,
  not on a second line. **Reference** only when Bank or JazzCash / Easypaisa is chosen (hidden for Cash).
- R6-14. **Campus in short and on one line** wherever it is shown in lists: "Girls" / "Boys" instead of
  "Girls Campus" / "Boys Campus"; in general, avoid table cells breaking into two lines where possible.

### Staff attendance machine — photos in `docs/reference/attendance-machine/`
- R6-15. Settings to connect the staff **attendance machine** to TASEMS. The machine: **ZKTeco** face + fingerprint
  terminal with keypad (SN QWC5245000036), **LAN (Ethernet) connected**, 12 V; shows "Check-In".
  Today TASEMS only imports the machine's file (Excel / CSV / .dat). To add:
  - Setup → **Attendance machine**: machine name, **IP address**, port (ZKTeco default **4370**), comm key
    (password, often 0), which branch / campus; **Test connection** (shows the machine's time, number of users and
    records).
  - **Get attendance now** button, and **automatic every few minutes** while TASEMS is running: punches come in
    by themselves and the daily staff attendance (present, late, half day, absent) is worked out as today from the
    duty times.
  - Staff are matched by the **Biometric machine ID** already on each staff record; a list of machine users not
    matched to any staff member.
  - Optional later: **set the machine's clock** from TASEMS; more than one machine per branch.
  - When TASEMS goes online, the machine can instead **send** punches to the server itself (ZKTeco "Cloud server /
    ADMS" setting) — to choose then.
  - **Given by the lead (31 Oct 2026)**: IP **192.168.1.222**, mask 255.255.255.0, gateway 192.168.1.1, TCP port
    **4370**, DHCP off; platform **ZMM220_TFT**, ZKFinger VX10.0, ZKFace VX7.0, MAC 00:17:61:10:da:4c. **No other
    software** uses the machine.

## Round 7 (6 Nov 2026) — built 6 Nov 2026 (Windows installer v16, CHANGELOG 0.42.0, D-095); **confirmed working by the lead on 11 Nov 2026** (duty times per staff type; machine users matched by name with ticks)

Context: installer v14 connected to the head-office machine (192.168.1.222, TCP): 93 users, 39,979 records,
0 staff matched (no staff record has a Biometric machine ID yet). After **Get attendance now** the lead reported
that "all 93 enrolled staff disappeared". Checked: TASEMS sends the machine only read commands (connect, clock,
counts, read attendance log, free buffer, disconnect — codes checked against pyzk's list); none adds, changes or
deletes users. In TASEMS, a read with 0 matched staff saves nothing and changes no staff record. **Waiting for the
lead to say where the staff are missing** (on the machine's User Mgt, or in TASEMS → Staff) — see R7-6.

### Staff menu
- R7-1. ~~**Staff** page (first item of the Staff menu) is for staff information only: Add staff, Import staff,
  the staff list. Remove **Today's staff attendance** and **Import machine file** buttons from it.~~
  **Withdrawn by the lead (6 Nov 2026)**: the buttons at the top of the Staff page (Today's staff attendance,
  Import machine file, Monthly sheet, Leave) **stay as they are**; do not change them.
- R7-2. ~~The side menu **Staff** group keeps only staff items. **Monthly sheet** and **Leave** move to the
  **Staff attendance** side (with Today's attendance, Import machine file, Attendance machine): everything about
  attendance lives under Staff attendance.~~
  **Withdrawn by the lead (6 Nov 2026)**: the side menu stays as it is; do not change it.

### Computer code and Biometric ID
- R7-3. Every staff member has two separate numbers: **Computer code** (our own, for records and documents) and
  **Biometric ID** (the user number on the machine, used only to match punches). (Both fields exist today:
  "Code" and "Biometric machine ID"; to label them clearly.)
- R7-4. **No Biometric ID = never touched by the machine.** Punches are not taken for them and **no attendance is
  marked for them from the machine** (today a read that matches anyone works out the days of *every* staff member
  in that date range, so staff without an ID would get "absent" — to stop). They are never removed or hidden. The
  page shows "Biometric ID not set" for them.
- R7-5. New staff are often put on the machine weeks or a month after joining. Until the ID is typed into TASEMS
  nothing is taken for them; once it is typed, punches are taken **from then on** (the lead's wording: "phir wo
  uthana shuru kar de"). **Answered by the lead (6 Nov 2026)**: there are no earlier punches to bring — a person
  gets their machine ID only when enrolled on the machine, and punches start from then.
- R7-6. Investigation: where the 93 staff went missing (machine or TASEMS), and how to get them back.

- R7-10. **Staff list columns** (Staff page), in this order: **EMP.code** (heading renamed from "Code"),
  **Machine ID** (moved from the last column to right after the code), **Name**, **Designation**, **Type**,
  **Mobile**. EMP.code and Machine ID values **centred** under their headings (today they sit to one side).
  - Heading names: **EMP.code** (employee code) and **Machine ID**; where the full heading does not fit, short form
    **MAC.ID** (the lead, 6 Nov 2026).
  - The same two columns, **before the name**, also on **Staff attendance** (today's page) and the **Monthly
    sheet**.
  - **Joining date** added as the last column of the staff list (after Mobile): EMP.code, Machine ID, Name,
    Designation, Type, Mobile, **Joining date** (the lead, 6 Nov 2026).
  - **Monthly sheet** starts with: EMP.code, Machine ID, Name, **Designation** (designation added), then the days.
- R7-17. **Sort by clicking a column heading** (the lead, 6 Nov 2026): on the **Staff list** — EMP.code, Machine ID,
  Name (A–Z), Designation, Type, Mobile, Joining date — one click ascending, a second click descending, with an
  arrow showing the order. The same on **Staff attendance** (today's page) for its headings.
### Staff member page (6 Nov 2026)
- R7-15. Buttons at the top of a staff member's page: today **Edit, Delete, Record leave** — Delete sits in the
  middle and can be pressed by mistake. New order: **Edit**, **Record leave**, then empty space, and **Delete on
  the far right** of the box.
- R7-16. Details on the staff member's page: all values **left-aligned** alike (today Father name is on the left
  but CNIC and Biometric machine ID sit on the right).

### In / Out times and late / early left (6 Nov 2026)
Today (checked): the branch has one duty time for everyone, **07:45 to 13:45**, Monday to Saturday, with "grace
minutes" and "half day after" settings, and **late** is worked out from the In time. But these can only be changed
in the technical admin screen (no page in Setup), there is **no early-left**, and a day with one punch is not
flagged.
- R7-11. **Payroll rules** (Setup) get the **In time** and **Out time** (with grace minutes and half-day-after),
  editable by the office.
  - **Decided by the lead (6 Nov 2026)**: times are set **per staff type**, the four types on the staff form:
    **Teacher**, **Hifz teacher (Qari)**, **Administration / office**, **Support staff** — each with its own In
    and Out time, in Setup (Payroll rules / settings).
  - **Summer and winter** times differ: the office can change the times during the year. Each change has a
    **"from" date**, so earlier days keep the times that applied then (late / early left of last month does not
    change when the winter times are entered). E.g. "Winter times from 1 Nov", "Summer times from 1 Apr".
- R7-12. In after the In time (+ grace) = **Late**. Out before the Out time = **Early left** (new; shown on the day,
  the monthly sheet and the staff member's page).
- R7-13. **In but no Out**: the day closes at midnight; the attendance counts (present / late), and the day shows
  "**In, no Out**". The next day is worked out on its own.
- R7-14. **Out but no In** (only a punch near or after the Out time): the attendance counts, and the day shows
  "**Out, no In**" (today such a punch would be read as a late In).
- R7-8. Staff attendance has **two parts**: (1) staff **with a Biometric ID** — attendance comes from the
  machine; (2) staff **without** one — attendance is **entered by hand**. Attendance of **both** parts can be
  **edited** by hand.

### Accepted from Claude's suggestion (6 Nov 2026), with confirmation
- R7-7. Read machine user **names** with the numbers; show "13 – name (112)" in the not-matched list.
  **Match by name only with confirmation**: TASEMS shows the suggested pairs (machine number + machine name ↔
  staff member); nothing is filled until a person ticks / OKs each pair. Two people with the same name (e.g. two
  "Ahmad") are never matched by themselves — they are shown as "same name, choose by hand". The ID can always be
  typed by hand instead. Read-only on the machine.

### Problem reported 6 Nov 2026 (after installing v14) — to investigate first
- R7-9. Dashboard shows **1,215 active students**, but **Students** list and search show nothing; **Staff** list is
  empty too (it showed before). The dashboard counts straight from the database, so the records are there; the
  lists are not showing them. **Found and fixed 6 Nov 2026 (v15, CHANGELOG 0.41.3)**: a second, empty campus with
  the same name made by the seed after the campus code was changed; the top bar showed the empty one.

## Round 8 (11 Nov 2026) — Hiring (CV bank, vacancies) — built 11 Nov 2026 (Windows installer v17, CHANGELOG 0.43.0, D-096)

The lead's request (11 Nov 2026):
- R8-1. A **Hiring** tab in the side menu, after Staff, with its own sub-items.
- R8-2. CVs arrive from many places: in hand at school, online, after an advertisement, by email, by WhatsApp. Each CV
  is **uploaded** (photo or PDF) and its **date received** saved, so a record of all CVs builds up.
- R8-3. Data is **taken out of the CV automatically** where possible, and every field stays **editable**; what could
  not be read is typed in. Fields: name, father name, phone, address; education (degree, institute, year);
  experience; the CV file attached.
- R8-4. Each CV is marked **Relevant / Not relevant**, e.g. lives 8–10 km from the campus, or applies for a
  Faisalabad post from Islamabad.
- R8-5. Category (post: teacher or other), **subjects** the person can teach (Science, Biology, Physics, Chemistry,
  English, Urdu …) and **level** (Primary, Middle, High) of their experience.
- R8-6. Filling a CV must be **quick**: most things filled by themselves, the rest fast to choose.
- R8-7. **Search**: "an English teacher for this level" lists the matching CVs, **latest received first**.
- R8-8. A CV can be marked **Hired**.
- R8-9. The lead asked for a professional flow including steps not mentioned, shown before building.

Proposal (to confirm with the lead): see the Hiring flow page sent 11 Nov 2026 — CV bank, quick review screen,
relevance rules by city / area / distance, duplicate check by mobile / CNIC, vacancies with matching CVs, interview
→ demo lesson → selected → joined, and "Create staff record" from the hired candidate. Automatic reading of CV photos
needs an online service (Claude API: internet, a paid API key and the lead's approval; CVs are sent to Anthropic) —
not to be bought or switched on without approval.

### Round 8 — decided by the lead (11 Nov 2026)
- R8-10. **No paid service and no AI** now: CVs are entered with the quick form (option A). Option C (AI reading) only
  later, after a separate decision. Option B (free OCR) not chosen.
- R8-11. **Levels**: Early Years, Primary, Middle, Matric, Hifz-e-Quran.
- R8-12. **Distance**: each campus, a radius of at most **4 km**. TASEMS shows how far the candidate lives from the
  campus (e.g. "x km from Samanabad"); a person decides relevant / not relevant, because addresses on CVs are often
  incomplete or wrong.
- R8-13. **Keeping CVs**: CVs of people not hired stay **2 years**, then move to a **Bin** by themselves; after
  **30 days** in the Bin they are deleted by themselves. A person can also remove a CV before that.
- R8-14. **Interview mark sheet**: the school has none; TASEMS is to provide one (headings to agree).
- Open: other posts than teacher (staff designations list?), subjects list, how the distance is worked out without a
  paid map service, whether the 2 years count from the last CV received, mark sheet headings.
- R8-15 (11 Nov 2026). **No distance**: TASEMS does not work out or show any distance (no paid map service). The
  address is written as on the CV and the office judges relevant / not relevant itself. (Replaces R8-12.)
- R8-16. The **2 years** count from the date the latest CV of that person was entered in TASEMS. People in an open
  interview step or hired do not go to the Bin (Claude's proposal, not objected to).
- R8-17. **Posts**: the staff designations list, plus **Designer, Content creator, Graphic designer, Typist**. More
  posts will be given by the lead; the list is kept in Setup so the office can add posts.
- Subjects list and the 50-mark interview sheet as proposed by Claude on 11 Nov 2026, unless the lead changes them.

## Round 9 (13 Nov 2026) — Hiring: calls, move screen, CV import — built 13 Nov 2026 (installer v18, CHANGELOG 0.44.0, D-097)
- R9-1. Vacancy board: the panel under "Move" was cramped (columns spilling out); make it clean, and make Move a
  clear, full-width button.
- R9-2. Joining date belongs to Selected only.
- R9-3. Calls: record each call — picked up or not — with the date; several calls; so the office sees a candidate
  who does not pick up and does not shortlist them again.
- R9-4. No AI integration in TASEMS. Instead: CV bank import from Excel; a template the office gives to Claude
  together with the scanned CVs (100–200 at present), or an "agent" in Claude, which returns a file with the data
  filled in; that file (with the CVs) is uploaded to TASEMS, so CV + data come in without typing.

## Round 10 (13–14 Nov 2026) — built 14 Nov 2026 (installer v19, CHANGELOG 0.45.0, D-098)
- R10-1. **CV number**: like the EMP.code and the admission no., every CV in the CV bank gets a number of its own,
  running 1, 2, 3 … per branch, given by TASEMS when the CV is saved (typed in, or imported from Excel / ZIP).
  - The office writes it on the paper CV, and names the WhatsApp CV with it (e.g. "CV No. 41").
  - **CV bank list**: a "CV No." column first, before the latest CV date. Also shown on the candidate's page, in
    search (typing 41 finds CV No. 41), on the vacancy board, and in the Excel download.
  - Proposed by Claude, to confirm: a person who sends a second CV gets a new number for that CV (each paper has its
    own number); the list shows the person's latest CV number. Existing CVs are numbered in the order they were
    received.

### Payroll (14 Nov 2026)
- R10-2. **Payroll page look**: EMP.code and every number (salary, days, amounts) **centred** in their columns.
  The figures at the top (Staff, Salaries, Net pay, To pay …) spill out of their boxes: fit them inside, aligned.
- R10-3. **Days columns on the payroll page**, in this order: **Days in month**, **Absent**, **Half days**,
  **Working days**, then Bonus days … (today one "Days" column shows "31/31", which is not clear).
  - Working days = days in month − absent − half days × ½. E.g. 31 days, 2 absent, 1 half day → 31 − 2 − 0.5 =
    **28.5 working days**; no bonus (absence / half day), and the salary follows these days.
- R10-4. **Enter manually** page (Payroll → Enter manually):
  - Columns: Use, **EMP.code**, Name, **Working days**, **Half days**, **Bonus days** — no "Days in month" (taken by
    itself), no "Days on staff", no "Absent" (worked out: days in month − working days − half days × ½).
  - **Working days filled in by itself** from the attendance; changed only when it must differ.
  - **Bonus days filled in by itself**: 1 (or as set in Payroll rules) when the person has no absence and no half
    day and the rules give them the bonus; can be changed, e.g. to 0 when a person is not to get it.
  - A **search box** that filters the list while typing (no Enter): "a" shows names with "a", "aa" narrows further;
    clearing it shows everyone again. Ticked rows stay ticked while searching.
  - **Save and work out** updates the payroll page with these figures.
- To confirm with the lead: for a person who joined (or left) during the month, "days in month" for their pay means
  the days they were on staff, as today; working days count from those days.

## Round 11 (14 Nov 2026) — built 16 Nov 2026 (installer v20, CHANGELOG 0.46.0)
- R11-1. **Payroll → Enter manually** columns, in this order: Use, EMP.code, Name, **Monthly salary** (new, after the
  name), Working days, Half days, Bonus days, Net pay now.
- R11-2. **Net pay now changes while typing**: as working days, half days or bonus days are changed, the person's
  net pay is worked out again on the page at once, without saving. "Save and work out the pay" still saves.
  - Worked out the same way as payroll: day's pay = monthly salary ÷ days in the month; cut for absent days and
    half a day's pay per half day; plus bonus days; GP Fund, EOBI, advance, security and other amounts as already
    set for that month (Claude's note: the page shows the figure; the saved payroll stays the one that counts).
- R11-3. **Search while typing** (no Enter, no "Show" button), as on Payroll → Enter manually, also on:
  - the **Payroll** page (name or EMP.code);
  - the **Staff** list (name, EMP.code, mobile, designation);
  - the **Students** list (name, admission no., father name, mobile, CNIC).
  The list narrows as each letter is typed; clearing the box shows everyone again. (Claude's note: on long lists —
  e.g. 1,215 students over several pages — the page asks TASEMS for the matching rows a moment after typing stops,
  so the whole list is searched, not only the page on screen.)
- R11-4. **Back link** ("‹ Staff", as on other pages) at the top of the pages opened from the buttons on the Staff
  page — **Today's staff attendance**, **Import machine file**, **Monthly sheet**, **Leave** — taking the user back
  to the Staff page.
- R11-5. **Staff leaving** (lead, 14 Nov 2026: "there is no option for a staff member who leaves"). Today it exists
  only at the bottom of **Edit** (Status: Resigned / Services ended / Retired + Leaving date), which is hard to find.
  To add:
  - A clear **"Staff member is leaving"** button on the staff member's page (beside Record leave; not next to Delete):
    **last working day**, **reason** (Resigned, Services ended, Retired, Other), a note.
  - From the day after the last working day: no attendance is marked (machine or by hand), no "absent", no salary
    for the days after; the person stays in all records and reports up to that day (already how TASEMS works once a
    leaving date is set).
  - The page shows **"Left on <date> — <reason>"**; the Staff list has a **"Left"** filter (the record is never
    deleted); a link to the payroll **Final settlement** (last salary, advance, security).
  - Taking it back (left by mistake) by the Director.
- R11-6. **Payroll → Salaries and bank details**: an **EMP.code** column first, before Name (centred, like the other
  payroll pages), instead of the code written small after the name.
- R11-7. **Setup → Attendance machine**: the box "machine users not given to any staff member" (Name on the machine
  / staff member TASEMS suggests) leaves an empty strip on the left and squeezes the table to the right. Make the
  heading sit on top and the table use the **full width** of the page.

## Round 12 (18 Nov 2026) — built 18 Nov 2026 (installer v21, CHANGELOG 0.47.0)
- Context: on 18 Nov the machine (192.168.1.222) answered a ping but took no connection on port 4370 (TCP or UDP);
  **restarting the machine fixed it** (lead, 18 Nov 2026). Likely cause: TASEMS reads all ~40,000 records every
  5 minutes, and a "Get attendance now" at the same moment opens a second connection.
- R12-1. (Proposed by Claude) Only **one connection** to a machine at a time: "Get attendance now" waits for an
  automatic reading in progress instead of opening a second connection.
- R12-2. **Decided by the lead (18 Nov 2026)**: a setting on Setup → Attendance machine for **how often TASEMS reads
  by itself**: **Never (only when "Get attendance now" is pressed)**, every 15 minutes, every 30 minutes, every
  hour. No 5-minute option. Starting value: **Never** — the office presses "Get attendance now" when it wants the
  latest attendance.
- R12-3. (Proposed) After a machine does not answer, TASEMS waits **30 minutes** before trying again by itself (the
  page says so; "Test connection" still works at any time), and suggests restarting the machine.
- R12-4. **Monthly sheet print** (lead's print preview, 18 Nov 2026, A4 landscape): the sheet does not fit the paper
  width — days 28 to 30/31 and the totals (P, L, H, A, LV, EL, !, Unpaid) are cut off. To do: a print layout that
  fits every day of the month and the totals on the page width (smaller type and narrower day columns on paper,
  landscape), headings repeated on each page, and the "‹ Staff" link and buttons left off the paper.
  - Lead, 18 Nov 2026: **no empty space on the left** of the printed / PDF sheet (the page starts at the margin), and
    the **whole sheet from EMP.code to Unpaid** fits one page width **with the browser's normal (default) margins**;
    type may be smaller to fit.
- R12-5. **Setup → Attendance machine**, table of machine users not given to anyone (Save, MAC.ID, Name on the
  machine, Punches, Staff member): spacing is uneven — a wide gap between Save and MAC.ID, MAC.ID too close to the
  name, a very wide gap after Punches. Even column widths: Save and MAC.ID narrow and **centred**, Punches narrow
  and centred, the name and the staff member choice taking the rest; a cleaner layout overall.
- R12-6. **Setup → Attendance machine — spacing and the side line** (lead, 18 Nov 2026):
  - The box with the machine users has a dark line down its side. (Claude: that line is TASEMS's "needs attention"
    note style — a yellow box with a bar on one side, used for warnings. This box is a working list, not a warning,
    so it becomes a plain box like the others, without the side line. The real warning above it — machine not on
    this computer's network — keeps it.)
  - Even space between: the table and "Save the ticked rows"; the box and "Get attendance now / Test connection";
    those buttons and "Change"; and the note at the bottom of the page ("On the machine: M/OK → …").
  - The same even spacing between text, tables and buttons on this page first; the other pages to be checked for
    the same in a later round.
- R12-7. **Staff → Monthly sheet, first columns** (EMP.code, MAC.ID, Name, Designation): sensible widths — narrow
  for EMP.code and MAC.ID, wider for Name and Designation — so the gaps are even; and the **heading row centred**
  (every heading of the sheet centred over its column).

## Round 13 (19 Nov 2026) — built 19 Nov 2026 (installer v22, CHANGELOG 0.48.0; R13-9 moved to the website)
- R13-1. **Side menu — one group open at a time** (lead, 19 Nov 2026): the menu groups (Overview, Students,
  Academics, Finance, Events, Staff, Hiring, Settings) open when clicked, but an open group stays open when another
  is clicked, so several are open together. To do: opening a group closes the others by itself, so only **one
  drop-down is open at a time** (e.g. Settings → Setup open, then clicking Staff or Hiring closes Settings).
- R13-2. **Staff → Monthly sheet, the rows** (lead, 19 Nov 2026): the headings are centred (R12-7); now **everything
  in the rows below centred too** (EMP.code, MAC.ID, Name, Designation, the day marks and the totals), with cleaner
  alignment overall.
- R13-3. **Staff → Monthly sheet, the sheet fills the page width** (lead, 19 Nov 2026): the table now takes less than
  half of the page and leaves empty space on the right; it should **stretch across the full width**.
- R13-4. **Staff → Monthly sheet, the key to the marks** (lead, 19 Nov 2026):
  - The key text goes **at the top**, the buttons **below it** (now the buttons come first).
  - Written as **P = Present | L = Late | H = Half day | A = Absent | LV = Leave | HD = Holiday | – = Off day |
    E = Early left** (and the other marks the same way: ! = In with no Out, or Out with no In; Unpaid = absent days +
    days of unpaid leave), with the first letter of each word in capitals, separated by "|" (or commas), **well
    spaced** so it is easy to read.
  - (Claude: the sheet shows early left as a small "e" next to the mark; the key will match whatever the sheet shows
    — to be confirmed whether the mark itself also becomes a capital "E".)
- R13-5. **Staff → Monthly sheet, Print, Excel and PDF** (lead, 19 Nov 2026): options to **print**, download as
  **Excel** and download as **PDF** on this page. (Claude: Print and Excel buttons already appear on the page; to
  check that Excel downloads the monthly sheet itself, and add a **PDF** download.)
- R13-6. **Side menu — capital first letter of every word** (lead, 19 Nov 2026): every item in the menu groups with
  each word starting with a capital, e.g. "Needs attention" → **Needs Attention**, "Admission enquiries" →
  **Admission Enquiries**, "Admission report" → **Admission Report**, "Staff attendance" → **Staff Attendance** —
  the whole menu the same way (group names and the items under them). (Claude: small joining words such as "of",
  "and", "by" to stay small, as usual in titles — to be confirmed if the lead wants those capital too.)
- R13-7. **Staff → Staff attendance (today's page) — a report for the day** (lead, 19 Nov 2026):
  - **Print, Excel and PDF** buttons for the day's attendance, placed on the **right side, on the same line as the
    "From the attendance machine" heading**, just above the table.
  - The report is for the date shown on the page (today or the day chosen): the **summary** (present, late, half day,
    on leave, nothing recorded, …) and the list of staff with their In / Out times and marks, **including the staff
    who have not marked attendance yet** ("Nothing recorded").
  - **Absent is not marked during the day**: e.g. school starts at 8:30; a person who has not come by 9:30 is
    **not** marked absent on the day — they stay "Nothing recorded" (as now; "Nothing recorded 25" is fine as it
    is), and absent is counted from the next day. Nothing to change in that rule; only the report is added.
- R13-8. **Side menu — a new group "School Fee"** (lead, 19 Nov 2026): the fee items move out of Finance into a new
  group **School Fee**, placed above Finance: Barcode, Fees, Generate vouchers, Vouchers, Family vouchers,
  Defaulters, Daily collection, Discounts. **Finance keeps**: Expenses, Cash & bank book, Profit & loss, Shop & stock,
  Sell, Royalty. Order in the menu: … School Fee, Finance, …
- R13-9. **NOT IN TASEMS — moved to the school website (lead, 19 Nov 2026)**: the Books ordering feature will be
  built on the website and its admin panel, not in TASEMS. The prompt for the website's Claude is in
  `docs/BOOKS_WEBSITE_PROMPT.md`. The notes below are kept for the record only.
  **Books — a new section for selling books** (lead, 19 Nov 2026; the lead will send a reference of the
  present online system). Menu group **Books**, below Finance. Today books are sold through a separate online
  system; it is to come into TASEMS.
  - **Book inventory**: every book with its name, class (e.g. Play Group), stock in hand, **purchase price** and
    **sale price**.
  - **Customers** (branches, or anyone buying books) are known by their **mobile number** (main key), with name and
    address.
  - **Order link**: an open link is sent to the customer; they type their mobile number (no password) and see an
    order form with **every book in stock, class by class** (class, book, sale price, a quantity box, the line
    total), and the order total at the bottom. **View / preview** shows a summary of the books chosen (e.g. 8–10
    items) to check again; they choose **Pick up** (they collect it) or **Delivery**, then **Place order**.
  - The order reaches TASEMS: whose it is (mobile number, name, address), the books, pick up / delivery. The office
    checks it, packs it and delivers it (or it is collected).
  - **Invoice with an order ID and a barcode** (like a fee voucher ID): order status shows whether it is **paid or
    pending**.
  - **Recording the payment** (before or after delivery): scan or type the order ID → how it was paid (cash / bank),
    **received by** = the person signed in (filled by itself), **which account / bank account** it went into,
    **attach the receipt**, date, a note → Save; the payment is recorded against the order.
  - (Claude, points to settle before building:
    1. The open link has to be reachable from the customers' phones over the internet. TASEMS now runs on the
       office computer (Windows), which phones outside cannot reach. This needs TASEMS (or the order page) on an
       internet server — a hosting decision, and possibly a paid service, which need the lead's approval first.
    2. With no password, anyone who knows a mobile number can place an order in that name. Since every order is
       checked by the office before it is packed, this may be acceptable; or a one-time code by SMS / WhatsApp
       (paid) could be added later.
    3. Is the stock taken off when the order is placed, when it is packed / delivered, or when it is paid?
    4. Are branch orders a sale (with an invoice and payment) like any customer, or a transfer?
    5. Delivery charges, discounts, part payments, cancelled or changed orders, returns?
    6. Is this the same stock as Finance → Shop & stock, or a separate books stock?
    To be settled with the lead's reference.)
  - **Decided by the lead (19 Nov 2026)** on the points above:
    1. Hosting: the school has its own domain and hosting (the website already runs, with its admin panel).
       **Not live now** — the features are built and tested first; going live (on that website, e.g. a "Login"
       button leading to TASEMS) is a later step, with the lead's approval. (Domain name as heard:
       "theyearcomesschools.com" — exact spelling to be confirmed.)
    3. **Stock is taken off when the payment is recorded.**
    4. **Every buyer is simply a customer** — a branch, a book shop or anyone; no branch role. A customer = **name,
       mobile number, address** (mobile number the main key).
    5. **No delivery charges.** **Discount**: none on the customer's form; the office may type a discount by hand
       when recording the payment (not shown to the customer). **Part payments allowed**: recorded against the
       order with the discount, on the payment page.
       **Orders can be edited by the customer before payment**: on the link, after the mobile number, the customer
       sees their **order history** and can change an unpaid order; every change is kept on record ("edited").
       **Returns allowed**, also part of an order (e.g. 2 of 10 books) — how a part return works to be proposed by
       Claude.
    6. **Books is a separate system** — its own stock and its own accounts, apart from Finance → Shop & stock and
       the other Finance books; it works in a similar way but its process and accounting stay separate.
  - (Claude, still to confirm: with part payments, is the stock taken off at the **first** payment or when the
    order is **fully paid**? Proposal for part returns: a **return note** against the order — pick the order, type
    how many of each book come back (not more than were taken), the stock goes back up, and the amount is either
    paid back or kept as credit for the customer's next order; the order shows what was returned.)
- **Lead, 19 Nov 2026**: early left stays a small **"e"** on the sheet and in the key ("e = Early Left"); in the menu,
  small joining words (of, and, by, from, a …) stay small, every other word starts with a capital.

## Round 14 (20–24 Nov 2026) — built 24 Nov 2026 (installer v23, CHANGELOG 0.49.0)
- R14-1. **Setup → Staff duty times — a different time for a day of the week** (lead, 20 Nov 2026): Friday has
  different In / Out times (Sunday is off), so the duty times need a way to set the times of a day separately —
  either **Friday only**, or **every day of the week**. (Claude's proposal: on each set of duty times (per staff type,
  summer / winter), a row for each working day Monday–Saturday with In time, Out time and half day after; left blank
  = the normal times of the set. So Friday is filled in today, and any other day can be changed later without a new
  build. Late, half day and early left on that day are worked out from that day's times.)
  **Decided by the lead (20 Nov 2026): every day of the week** (as proposed; a blank day keeps the normal times).
- R14-2. **Payroll — "Pay employees" (pay many at once)** (lead, 20 Nov 2026): a button **Pay employees** on the
  Payroll page, before "Acknowledgement sheet (PDF)" (next to Payslips, Bank transfer sheet, Excel). It opens a list
  of the staff not yet paid for the month; tick the ones to pay and press one button — **all the ticked staff are
  marked as paid** at once, instead of opening each person and paying one by one. (Claude's proposal: the list shows
  EMP.code, name, designation, net pay and how they are paid (cash / bank, from their salary record); a "tick all"
  box; one payment date for all (today to start); each person is paid their full net pay for the month by their own
  method; only after the month's payroll is finalised; staff already paid are not listed; the total of the ticked
  rows shows before saving. Paying part of a salary stays on the person's own page.)
- R14-3. **Academics → Exams & Results — the year's assessments** (lead, 24 Nov 2026; more details to follow).
  The academic session starts in **March**. The main assessments of a year, in order:
  1. **Periodic Assessment – I** — before the summer vacation.
  2. **Summer Vacation Work** — given for the summer vacation.
  3. **Mid-Term** — after the summer vacation, in August / September.
  4. **Periodic Assessment – II** — in November (e.g. the date sheet of 10–17 Nov 2026 and the result card
     "Result of Periodic Assessment – II" the lead shared: subjects with their own total marks — for Class Seven
     English 40, Urdu 40, Mathematics 30, Science 30, Islamiyat 30, Computer 25, Tarjama tul Quran 25, Social Studies
     30, total 250 — percentage, Attentive / Punctual / Neatness / Participation as Excellent / Good / Fair, remarks,
     Teacher and Head / Principal signatures).
  5. **Finals** — in February / March.
  (Claude: TASEMS's exams now know only Class test, Mid-Term and Final.)
- R14-4. **Exam kinds — four exams only** (lead, 24 Nov 2026): **Periodic Assessment – I, Mid-Term, Periodic
  Assessment – II, Final**, in that order under each session (e.g. Session 2026-27). These are ready to choose when an
  exam is added. **Summer Vacation Work is not an exam** of its own; its marks are added **into the Mid-Term**.
  **No other exam's marks are added into the Final** (the Final stands on its own). The **total marks of every
  paper are typed by hand** for each exam in each session, and can be changed.
- R14-5. **Date sheet** (lead, 24 Nov 2026; the printed 10–17 Nov 2026 sheet is the sample, to be made better): in
  the exam (e.g. Periodic Assessment – I) a **Generate date sheet** button makes a printable date sheet:
  - At the top the **logo** and **The Arqam Schools**, below it **DATE SHEET**, below that the **exam's name** (e.g.
    Periodic Assessment – II), the **dates it runs** (e.g. 10 November – 17 November 2026) and the **session**
    (Session 2026-27).
  - Then the grid as in the sample: a row per date, a column per class (Playgroup, Nursery, Prep, One … Seven,
    Pre-Ninth …), the paper of each class on each date, "–" where a class has no paper.
  - **No times anywhere** on any date sheet — dates only.
- R14-6. **Question papers kept on record** (lead, 24 Nov 2026): for every exam, the **question paper of each
  subject of each class is uploaded** and kept in TASEMS (only the question paper — not the checked answer
  papers), so it is known later what, e.g., Class 7 English's paper was last year and what the students' results
  were.
- R14-7. **Entering the marks — two ways** (lead, 24 Nov 2026; as quick and simple as possible):
  1. **On the screen, a whole section at once**: open the exam → the section → one table with the **students down
     the left** and the **subjects across the top**; type every student's marks in every subject on that one table.
     The **Attentive / Punctual / Neatness / Participation** ratings (Excellent / Good / Fair) are marked by a **tick
     / one click** for each student — on the same table or right next to it, whichever is quicker (Claude to
     propose).
  2. **On paper / Excel**: TASEMS gives a **sheet** (Excel, and a printable sheet) with every student of the class /
     section and the subjects; the marks are filled in (typed in Excel, or written by hand) and brought back into
     TASEMS. The lead asked that a **photo or scan of the hand-written sheet is read by itself**.
     (Claude: reading hand-writing from a photo needs an AI reading service. The lead decided on 13 Nov 2026 (D-097)
     that TASEMS has no AI or paid integration and sends nothing out; CVs are read by the office in its own Claude
     with the TASEMS skill and brought in as TASEMS's Excel template. Proposal: the same for marks — the office gives
     the photo / scan to Claude with a TASEMS "marks reader" skill, which fills TASEMS's marks Excel; the Excel is
     imported, checked on screen and saved. To be confirmed by the lead.)
- R14-8. **Summer Vacation Work in the Mid-Term** (lead, 24 Nov 2026): in the Mid-Term, every class / section has
  **Summer Vacation Work as a subject** of its own, with its own total marks (typed first) and marks like any
  subject. **Periodic Assessment marks are not added into the Mid-Term** (or into any other exam).
- R14-9. **Result cards** (lead, 24 Nov 2026): **one card per student, for every one of the four exams**, exactly
  like the sample "Result of Periodic Assessment – II" — **black and white**:
  - Logo and THE ARQAM SCHOOLS, "RESULT OF <exam name>"; Name, Class, **Code = the admission code**, Section.
  - The subjects with total and obtained marks, total marks, percentage.
  - Attentive / Punctual / Neatness / Participation with Excellent / Good / Fair boxes (the chosen one ticked).
  - **Remarks** — written by hand on the printed card (left empty by TASEMS); Teacher and Head / Principal lines.
  - The address line at the bottom: The Arqam Schools, Sanora Colony, Samanabad, Faisalabad (as on the sample).
  - Cards can be **exported** (PDF) one student at a time or the whole section.
  - Every exam's marks stay on record, so each student's **progress across the exams and the years** is kept.
- R14-10. **Lead, 24 Nov 2026**: the exams process above is an overview — it need not be built exactly so; anything
  that makes it easier, quicker or better is to be done. **Claude's proposals** (for the lead to accept or change):
  1. **One click for the year**: "Add this session's exams" makes Periodic Assessment – I, Mid-Term, Periodic
     Assessment – II and Final for the session at once (dates added later).
  2. **Papers copied from last time**: when an exam is set up, the subjects and total marks of each class are copied
     from the same exam of last year (or the previous exam), then changed where needed — no typing from scratch.
  3. **Date sheet made on one grid**: dates down the side, classes across the top, the subject chosen in each box;
     "–" where empty; then Generate date sheet (PDF, logo, no times).
  4. **Marks table made for speed**: Enter goes to the next student, Tab to the next subject; "A" = absent; marks
     above the total turn red and are not saved; total and percentage fill in by themselves while typing.
  5. **Ratings in one move**: Attentive / Punctual / Neatness / Participation start as **Good for everyone** (a
     "set all" choice); only the students who are Excellent or Fair are clicked — most of the class needs no click.
  6. **The same sheet for paper and Excel**: one sheet per section (student code, name, subjects with their totals)
     to print and fill by hand, or fill in Excel and import; the import shows the marks on screen before saving.
  7. **Question papers private until the exam**: a paper uploaded before its date is seen only by the principal /
     exam staff; after the exam it is open to teachers of that subject for record.
  8. **Marks closed after the due date**: after "marks due on", only the principal can change marks (TASEMS already
     has this rule; kept).
  9. **Progress on the student's page**: every exam of every year in one table (percentage of each exam), so
     progress can be seen at a glance.
  10. Result cards as in R14-9 (black and white, A4, one student per page; the whole section in one PDF).
- **Lead, 24 Nov 2026 ("ok kr do")**: Claude's proposals in R14-10 accepted, and the marks reader skill for photos
  of hand-filled sheets (read in the office's own Claude, not inside TASEMS).

## Round 15 (24 Nov 2026) — built 24 Nov 2026 (installer v24, CHANGELOG 0.50.0)
- R15-1. **Colour logo on the result card and the date sheet** (lead, 24 Nov 2026): the official logo in its own
  colours (not grey) on both, with "The Arqam Schools" beside it as on the school's own designs. The lead will send
  the logo file to use.
- R15-2. **Exams & Results — the exams list**: beside each exam (Periodic Assessment – I, Mid-Term, Periodic
  Assessment – II, Final) **two clear buttons: Edit and Date sheet** (in place of the "Papers & question papers ·
  Date sheet" links); the table's alignment and look made proper, so it is easy to see which exams there are.
- R15-3. **Setup → Classes & Subjects** (new): for **each class** (class-wise, not section-wise — Claude: sections of
  a class share its subjects, e.g. 9th's Biology / Computer stay subjects of the class), choose its subjects; new
  subjects can be added here. Only a class's subjects then show for that class in the exams (and elsewhere subjects
  of a class are listed).
- R15-4. **Edit = one page for everything of an exam** (the present "Papers & question papers" page): the classes
  across the top (Play Group, Nursery, Prep, One … ); for the chosen class only **its subjects** (from R15-3), each
  with **total marks, the paper's date and the question paper** on the same row; at the top the exam's **first and
  last day**; "Save <class>" at the bottom. The separate "Set the dates" page is no longer needed. A **Date sheet**
  button (and "Generate date sheet (PDF)") at the top of this page too.
- R15-5. **The date sheet PDF — layout** (lead, 24 Nov 2026; the lead sends the logo to use):
  - At the top **the logo** (the file the lead sends). The school name is **not** written separately above (the logo
    carries it), and the campus line under it ("The Arqam Schools — Samanabad Campus (Head Office)") is removed.
  - The band: **DATE SHEET**; directly under it, **in the centre, the exam's name** (e.g. Periodic Assessment – I);
    on the same line, **the dates on the left** (e.g. 10 November – 17 November 2026) and **the session on the right
    corner** (Session 2026-27) — not all run together as now.
  - The table: every box and column evenly aligned, the text well placed and centred in each box.
  - At the very **bottom: the branch's address only** (where the date sheet is made; no "Head Office" wording, no
    phone or website).
  - Better alignment, a better-looking sheet and a better colour scheme overall.
- R15-6. **Setup → Branch details** (lead, 24 Nov 2026): one place in Settings for the details of the branch the
  software runs in: **branch name** (as shown at the top of TASEMS), **full address**, **phone numbers** (several),
  **mobile / WhatsApp numbers** (several; mobile and WhatsApp are the same number), and **website**. Printed papers
  take them from here (e.g. the date sheet's address, R15-5).
  (Claude: TASEMS already keeps a branch's address, phone 1–2 and mobile 1–2 under Setup → Branches, entered by head
  office. To do: a "Branch details" page the branch's own principal / owner can fill, the mobiles marked as WhatsApp,
  and a **website** field added.)
- R15-7. **Exams & Results — "All sections" list** (lead, 24 Nov 2026): fine as it is, but better with a **filter at
  the top** (Claude: choose a class, or type a section, to see only those rows).
- R15-8. **Marks & cards — the marks table** (lead, 24 Nov 2026):
  - **No roll number**: the student's **admission number (ADM.NO.)** shows instead; the Roll column is removed.
  - Better alignment, spacing and ease of use of the table (subjects, Total, %, Attentive, Punctual, Neatness,
    Participation, Card); the **Card** link made proper (a clear button).
- R15-9. **Result card — fonts and layout like the school's own card** (lead, 24 Nov 2026):
  - "THE ARQAM SCHOOLS" beside the logo in **Helvetica Inserat** (the font of the school's card); **everything
    else in Poppins** (e.g. "RESULT OF PERIODIC ASSESSMENT – II"). The **date sheet uses the same fonts** (R15-5).
  - **Name, ADM.NO., Class, Section**: the line runs **beside** each label (the value written on the line), not
    under it; "Code" becomes **ADM.NO.**
  - The whole card aligned properly, as on the sample.
  - (Claude: Poppins is free to use and can ship with TASEMS. Helvetica Inserat is a paid (licensed) font: TASEMS can
    use it only if the school has the font file with a licence for it — the lead to send it; otherwise a free font
    that looks very close is used, e.g. Anton. To be confirmed by the lead.)
- R15-10. **Result reports** (lead, 24 Nov 2026): after the marks are saved, reports to see **how a class / section
  did overall** in an exam, and **each student's progress**. (Claude's proposal, for the lead to confirm:
  1. **Section / class result** (per exam; print, PDF, Excel): number of students, how many sat, class average %,
     highest and lowest %, **subject-wise average** and highest in each subject, the students ranked by percentage
     (top three marked), and students below a chosen percentage listed for attention; a class report adds the
     sections side by side.
  2. **Student progress report** (print / PDF): one student's percentage in every exam of the session (and earlier
     sessions), subject by subject, with the change from the exam before — the "Exam results by year" table made
     printable with subjects.
  To confirm: is a pass / fail line wanted (e.g. 33%), and should positions (1st, 2nd, 3rd) show?)
- R15-11. **"All sections" table — columns** (lead, 24 Nov 2026): **Class**, then **Section**, then the exams
  (Periodic Assessment – I, Mid-Term, Periodic Assessment – II, Final) — not the class and section run together in
  one column. (Lead also suggested arranging this part exam-wise; with R15-7's filter.)
- **Lead, 24 Nov 2026 — fonts received**: Helvetica Inserat LT Std (Roman) and Poppins (OFL) sent by the lead; kept in
  `static/fonts/` for R15-9 / R15-5. (Helvetica Inserat is a licensed Linotype font; the zip had no licence file —
  the school is responsible for its licence.) Logo file still to come.
- **Lead, 24 Nov 2026 — logo received**: the colour banner (round logo + "THE ARQAM SCHOOLS" + "دی ارقم سکولز"), kept
  as `static/img/arqam-banner.png` (and the original .webp), used exactly as sent at the top of the date sheet and the
  result card (R15-1, R15-5). (Claude: since the banner already carries the name, the separate title in Helvetica
  Inserat is used only where the name is written as text.)
- **Lead, 24 Nov 2026 — R15-10 decided**: result reports show **pass / fail at 33%** and **positions (1st, 2nd,
  3rd)**. (Claude: 33% of the exam's total marks, as the 33% pass rule TASEMS already uses; positions by percentage,
  equal percentages share a position.)

## Round 16 (24 Nov 2026) — noted, not built yet (build when the lead says "haan ji, ab kar do")
- R16-1. **Date sheet — subject names on one line** (lead, 24 Nov 2026): "Mathematics" breaks, its last "s" going to a
  second line. Every subject name must fit on one line: the class columns a little wider (and the type sized to fit).
- R16-2. **Date sheet — the logo does not show** (lead, 24 Nov 2026, on the installed v24): the logo banner must show
  at the top of the date sheet. (Claude: on the test build it shows in the PDF; to check on Windows whether the
  banner file is found when the PDF is made there, and whether the lead means the Date sheet *page* on the screen —
  which has no logo — or the PDF.)
- R16-3. **Exam → Edit — "Exams start on / end on" once, at the top** (lead, 24 Nov 2026): the two dates are the same
  for every class, so they should not sit inside each class's box. Put them **once, right under the exam's name**
  (e.g. "Periodic Assessment – I") at the top of the page — above the class buttons (Play Group, Nursery, Prep …) and
  above / beside "Date sheet" and "Generate date sheet (PDF)" — and saved on their own, not with a class.
- R16-4. **Exams → Date sheet page (on the screen) — layout** (lead, 24 Nov 2026, photo of Periodic Assessment – II,
  10–17 Nov 2026, Play Group to Pre-Nine):
  - The day written **under the date** (e.g. "10-11-26" and below it "Tue"), not beside it.
  - More open: columns wider and clearly visible; **every box the same size**, each with room for **three lines**
    (the longest now, "Social Studies + Tarjama Tul Quran", takes three).
  - Everything in each box **centred both ways** (across and up-down).
  - (Also from the photo: the lead's date sheet uses "+" for two papers on a day and "Biology/Computer" for a choice;
    both kept as typed.)
- R16-5. **Results — the whole school's result too** (lead, 24 Nov 2026): on an exam's Results page, the class-wise
  table ("All classes") is there; at its end add **the whole school's result** for that exam — a total row / summary:
  students, passed, failed, pass rate, average and highest for the whole branch (Claude: also in the print, PDF and
  Excel; optionally the school's top three students by percentage).
- R16-6. **Result card — the logo does not show** (lead, 24 Nov 2026, photo of the installed v24: the card shows only
  the words "The Arqam Schools" where the banner should be — the same as R16-2 on the date sheet). (Claude: the PDF
  is made with the image's file path written as `file://` + the folder; on Windows that folder is like
  `C:\Program Files\…`, which does not make a valid address, so the picture is not found. To fix by building the
  address the proper way (`Path.as_uri()`) for the banner, logos and fonts in every PDF, and test it with a Windows
  folder path.)
- R16-7. **Result card — type and lines** (lead, 24 Nov 2026, same photo):
  - **Bold and larger**: the title "RESULT OF PERIODIC ASSESSMENT – II" (lead: bigger type too).
  - **Bold**: the four labels **Name, ADM.NO., Class, Section**; the table
    headings **SUBJECT, TOTAL MARKS, OBTAINED MARKS** (and 1–2 points larger); the rows **TOTAL MARKS** and
    **PERCENTAGE** (lead, same day: the subject names — English, Mathematics, E.V.S, Kids Book, Urdu … — stay
    **not bold**);
    **ATTENTIVE, PUNCTUAL, NEATNESS, PARTICIPATION**; **Remarks**.
  - Name / ADM.NO. / Class / Section lines: **shorter**, and **raised** so the line sits right under the written
    value (now it falls well below it); **Class and Section moved further to the right**.
  - **Remarks**: its line runs **all the way to the right**, ending where the Head / Principal line ends; the two
    remark lines **the same** (now the first is dark, the second light) with **more space between them**.
  - **Teacher** and **Head/ Principal**: both signature lines **the same length**, and each word **centred under its
    own line**.
- R16-8. **Result card — the line at the foot** (lead, 24 Nov 2026): it shows "The Arqam Schools" twice (the name
  plus an address that itself starts with the school's name). The foot shows **only the branch's address exactly as
  written in Setup → Branch details**, nothing added before it — the same as the date sheet.
- R16-9. **"Admission number" is called "Computer code"** (lead, 24 Nov 2026): everywhere in TASEMS a student's
  admission number (Admission no., Admission number, ADM.NO.) is renamed **Computer code**, and in short
  **COMP.code** (like EMP.code for staff) — student list and record, forms, imports and Excel sheets, exams (marks
  table, marks Excel, sheet to fill by hand, result cards, result reports, progress report), slips, ID cards,
  certificates, vouchers and every other place. Only the name changes: the numbers themselves stay the same.
  (Claude: about 65 places; the Urdu wording changes too, and the marks reader skill's instructions.)
- R16-10. **"Marks & cards" renamed "Marks & Results"** (lead, 24 Nov 2026): on Exams & Results (the section buttons)
  and the page's own heading / links.
- R16-11. **Marks & Results — the marks table headings** (lead, 24 Nov 2026):
  - Under each subject's name its total marks **in brackets**, e.g. "English" and below it "(20)"; the Total column
    the same, e.g. "(100)"; the "%" column as it is.
  - The last column's heading **"Result card"** (in place of "Card"), and in each row **only the print icon** (no
    word "Card" beside it).
