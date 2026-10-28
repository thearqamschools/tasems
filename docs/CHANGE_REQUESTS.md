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

## Round 3 (28 Oct 2026) — NOTED ONLY, not built yet
The lead is listing changes one by one. **Build nothing until the lead says "haan ji, ab kar do"**, then all together
(next Windows installer: v6).

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
