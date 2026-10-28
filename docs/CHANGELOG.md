# Changelog

## 0.37.0 — 2026-10-28 — Parent Tree prints straight on the network receipt printer (Windows installer v7)

Changed
- Parent Tree no longer opens a print window or a new window (it did not print on the office computer). A click
  sends the slip straight to the branch's **receipt printer on the office network** (LAN, port 9100, ESC/POS) and a
  short note says "Parent Tree printed: 2 students." — or what is wrong (no printer set, printer off).
- Setup → Branches: new box **Receipt printer (network address)**, e.g. 192.168.1.100.
- The slip on paper: logo, THE ARQAM SCHOOLS, address and phones, Parent Name, date and time, then Campus | Code |
  Student Name | Class | Section (long names continue on the next line), "Thank you", paper cut.
- Works when TASEMS runs on a computer in the same office network as the printer (the offline Windows copy). A
  server on the internet cannot reach an office printer; that is for later, when TASEMS goes online.

## 0.36.0 — 2026-10-28 — Round 3: sections, campuses, Parent Tree slip (Windows installer v6)

Changed
- Setup → Classes and sections: separate columns **Class | Section | Boys / Girls | Campus**.
- **Campus is required** for every section. Sections made before are placed automatically only when their branch
  has one campus that fits; the others show "Choose a campus". A boys and girls section may be in the girls
  (or boys) campus, as Play Group to Class 5 are; a boys section cannot be in a girls campus and the other way round.
- "Boys and girls" is written **"Boys and Girls"**.
- Class names in words without "Class": **One, Two … Eight, Pre-Nine, Nine, Ten** (Play Group, Nursery, Prep and
  Hifz-e-Quran unchanged). Renamed for every branch on the next start; import still accepts "Class 1", "Pre-9", "1".
- Campus lists show only the campus name, **Girls Campus first, then Boys Campus**.
- Add / Edit student: the **Father email** field is removed (the student's Email stays; saved father emails are
  kept).
- Students list: **Parent mobile** shows the father's and the mother's mobile (Excel too).
- Setup → Branches: **Phone 1, Phone 2, Mobile 1, Mobile 2** (with Address). Vouchers, family vouchers,
  payslips, parent messages and the Parent Tree slip show the ones filled in. Samanabad: 041-2660265,
  041-2406479, 0339-2406479.

Added
- **Parent Tree** slip for the 80 mm receipt printer (SPEEDX 400UL), like the old software's: logo, school,
  address and phones, father's name, date and time, then Campus | Comp. Code | Student Name | Class | Section for the
  child and every brother and sister still at school (same father CNIC). From the printer icon on each row of the
  Students list, the icon by the student's name, or the **Parent Tree** button after Edit student. Only for
  current students. One click opens the print window without leaving the page.
- Demo: Girls Campus and Boys Campus in the demo branches.

## 0.35.1 — 2026-10-28 — Windows installer version numbers

Changed
- The Windows installer now carries a version number, starting at **5**: TASEMS-Setup-v5.exe, then v6, v7…
  for every new exe. The number shows in the file name, the installer, the TASEMS window and Windows
  "Installed apps". It is kept in `windows/VERSION`.

## 0.35.0 — 2026-10-28 — Import: numbers taken as written

Changed
- Student and staff import no longer stops on a phone number that is not a Pakistani mobile: the number is
  saved exactly as written (students: parent's phone; staff: other phone) and listed as a note.
- Other small problems are also notes, not errors: a wrong or future date of birth and a wrong CNIC are left
  empty, a wrong admission date becomes the session start, an unknown relationship becomes Guardian, a wrong
  monthly fee is left empty. They can be corrected later on each record's page.
- Only rows that cannot be saved still stop the import (missing name or admission no, duplicate admission no,
  unknown class or section, gender). For those, a second button imports all the other rows and lists the rows
  left out.
- Several numbers in one cell ("0300-1234567 / 0321-7654321") use the first mobile number.

## 0.34.1 — 2026-10-23 — Windows: master login on first start

Changed
- With an empty school (choice 2), the TASEMS window now asks for the master login the first time, so no Start
  menu shortcut is needed. A "TASEMS master login" shortcut is also put on the desktop.

## 0.34.0 — 2026-10-23 — Delete records made by mistake

Added
- A **Delete** button on: branches, regions, academic sessions, campuses, sections, fee rates, banks, discount
  types (Setup), logins, students, staff, admission inquiries, shop items and notices.
- Who: the **master login** (superuser) everywhere; **head office / network administrators** in the branches they
  look after; the **Director** in the branch. Branches, regions, sessions, logins and network lists also need the
  matching Setup right, so a Director cannot delete the branch itself or a session. Nobody deletes their own login.
- The page first shows what will be deleted with it (e.g. a student's class place, an inquiry's follow-ups) and
  asks for a reason; the deletion is recorded in the history with that reason.
- Records with history are kept: if fees, payments, attendance, marks, stock moves and so on depend on it, the
  page lists them instead of deleting (use Leave school / not in use for those).

## 0.33.1 — 2026-10-23 — Windows installer fix

Fixed
- First start on Windows stopped with "invalid value for parameter TimeZone: UTC": the Windows PostgreSQL build
  had no time zone files. They are now added from the same PostgreSQL version (16.2).
- The installer stops a running TASEMS database before replacing the program, and a failed start no longer
  leaves the database running.

## 0.33.0 — 2026-10-23 — Windows installer (TASEMS-Setup.exe)

Added
- **TASEMS-Setup.exe** (docs/WINDOWS_INSTALL.md): installs TASEMS on one Windows computer like ordinary software —
  no Rancher Desktop or Docker, no internet. Desktop and Start-menu shortcuts: TASEMS, Make master login, Backup
  data, Stop database, Uninstall. First start asks: demo data or an empty school. Data is kept when updating or
  uninstalling.
- `windows/launcher.py` (starts PostgreSQL on this computer only, prepares the database with the same ordinary app
  role as the real server, runs TASEMS with waitress and opens the browser) and `windows/build_installer.sh`
  (builds the installer on Linux from official Python, PyPI, PostgreSQL and GTK packages).

## 0.32.0 — 2026-10-23 — Offline test copy on an office computer

Added
- **Offline test copy** (docs/OFFLINE_INSTALL.md): TASEMS with its own database on one Windows computer, using
  the free Rancher Desktop; open it on that computer or from other office computers at http://IP:8000. Double-click
  files in `offline\`: start (with demo data, or empty with two-step sign-in), stop, make a master login, back up,
  reset. Keys are made on that computer the first time. Internet is needed only once, to install.
- Setting `LOCAL_NETWORK` for that copy only: plain http on the office network (cookies without https).
- `.dockerignore` (keeps local files, media and secrets out of the image) and `.gitattributes` (Windows line
  endings for .bat files, Linux line endings for .sh files).

Checked: the start script on a fresh PostgreSQL 16 container with the production database role (row-level
security on), demo data loaded, and signing in as demo-network from another address (http://IP:8000).
The image build itself could not run in the development environment (no access to Debian's package servers);
it is the same Dockerfile the demo server builds.

## 0.31.0 — 2026-10-23 — Certificates on Letter paper; TAS reference numbers

Changed
- Leaving and character certificates print on **Letter** size (was A4); the letterhead space stays 50 mm at the
  top and 30 mm at the bottom.
- **Reference numbers** are made automatically as **TAS-<HO or branch initials>-<city code>-0001**: TAS = The Arqam
  Schools; HO for a head office campus, otherwise the initials of the branch's name; FSD for Faisalabad, LHR for
  Lahore. The Samanabad head office campus now gives TAS-HO-FSD-0001 (no city name in it). Two branches with the
  same initials in one city get TAS-GC-FSD and TAS-GC2-FSD. Certificates already issued keep their number.
- Setup → Branches: new "City code" (filled in for Faisalabad and Lahore; head office enters it for other cities)
  and "Head office campus".

## 0.30.2 — 2026-10-23

Fixed
- School leaving certificate: when no leaving date is given, the sentence no longer ends with "to .".

Added
- docs/WHATSAPP_COST_ESTIMATE.md: what one-click WhatsApp sending (vouchers, birthdays, notices) needs and costs.
  Not built; waiting for approval.

## 0.30.1 — 2026-10-23 — Two-step sign-in for the Admin

Changed
- The **Admin** (admissions officer) login now needs two-step sign-in (a code from an authenticator app), like the
  Director and the Accountant, because it receives fees. On the real server each Admin sets it up at the next
  sign-in; the demo server stays without it.

## 0.30.0 — 2026-10-23 — Logins by designation (project lead's table)

Changed
- **Director** (branch owner) can now do everything in the branch, not only see it — including receiving fees,
  approving discounts, fee rates, expenses, payroll and shop.
- **Principal** no longer receives fees or sees fee figures, expenses, accounting or the shop; sees payroll (read
  only) and the **fee defaulters list** only. Staff, Hifz, notices and needs attention stay.
- **Vice Principal / Coordinator** now see the fee defaulters list (nothing else about fees).
- **Accountant** now has payroll in full (salaries, finalise, payslips), the shop in full (items, cancelling
  sales) and cancels expenses and other income.
- **Admin** (admissions officer) can now receive fees.
- Only the Director, the Accountant and the Admin receive fees. Menus, reports and dashboards follow these rights.
- docs/DESIGNATION_PERMISSIONS.md updated to the approved table.

## 0.29.1 — 2026-10-23 — Project lead's answers

Changed
- **Payroll**: a half day now cuts half a day's pay (salary ÷ days in the month ÷ 2); late arrivals are still not
  cut. The per-day rate stays salary ÷ days in that month. Payslips, the payroll page and its Excel show half days.
- **Needs attention**: the starting limits (3 days, 75 percentage, 10 points, 2 months, 3 times) are confirmed.

## 0.29.0 — 2026-10-23 — M13 (free part): students needing attention

Added
- **Needs attention** (Overview menu, and in Reports under Students): students to check on, worked out by plain
  rules from records TASEMS already keeps — no AI, no outside service, no cost:
  - absent several school days in a row (leave does not count);
  - low attendance over the last 30 days (after at least 5 register days);
  - latest exam below the pass mark set in exam setup;
  - marks fell since the previous exam;
  - monthly fee unpaid for several months (only for people who can see fees);
  - Hifz sabaq not ready several times in 14 days (only for people who can see Hifz).
- The limits are on the page and can be changed; the starting values (3 days, 75 percentage, 10 points,
  2 months, 3 times) are suggestions until head office confirms them.
- Each student shows the reasons and the parent's mobile; counts per signal, filter by class and signal,
  Excel and Print. Principals and coordinators see the whole branch; class teachers see their own classes.

The paid AI part of M13 (Claude API) is not started: it needs the project lead's approval and a spending limit
(see AI_COST_ESTIMATE.md).

## 0.28.1 — 2026-10-23 — Hifz: project lead's answers

Changed
- **Para tests** are taken by the Qari or a senior Qari (Hifz teacher login), for any Hifz student of the branch;
  principals and coordinators can still record them, and only they can cancel one.
- **Grades** (Excellent, Good, Average, Weak) stay in English in both languages.
- Hifz completion certificate: not made (skipped by the project lead).

## 0.28.0 — 2026-10-23 — M12: Hifz-e-Quran

Added
- **Hifz** (Academics → Hifz): for each Hifz section, the day's sheet — for every student the Sabaq (para, surah
  and ayaat, lines, mistakes), Sabqi and Manzil (paras revised, mistakes), a grade and remarks; status Heard /
  Not ready / Absent. The para continues from the last lesson; students absent or on leave in the attendance
  register start as absent. Hifz students in regular classes (marked Hifz on their record) are included.
- **Para tests**: principals and coordinators record a para heard in full (passed / to repeat, mistakes); paras
  memorised before joining can be entered once. Passed paras fill a 30-para grid; all 30 = Hifz complete.
- **Hifz record** of each student (also linked from the student's page): paras memorised, current para, days heard,
  not ready, average mistakes, para tests and the month's lessons, with Excel.
- **Hifz progress report** by section and month (Excel and Print), and a Hifz section in Reports.
- **Parents**: a Hifz tab for Hifz children — paras memorised, current para and the last 14 lessons.
- Who: Hifz teachers (Qari) record their own section for the day; principals and coordinators record or correct
  any school day and record para tests; branch owners, regional directors and head office view. Saturday counts
  as a Hifz day, as for attendance. Corrections are recorded in the history.
- Demo: a fictional Hifz section with a Qari login (demo-qari), six boys and three weeks of lessons.

Not deployed (the demo updates automatically when pushed).

## 0.27.0 — 2026-10-22 — M11: shop & stock

Added
- **Shop & stock** (Finance → Shop & stock): each branch's books, uniforms and stationery with category, class,
  barcode, sale price and a reorder level. Stock is a ledger: stock received (with purchase price and note), items
  issued free, count corrections, sales and returns are each one recorded line; stock can never go below zero.
- **Sell** (Finance → Sell): scan a barcode or type the name, set the quantity, then complete the sale as
  **Cash**, **Bank** (which bank) or **Add to the student's fee account** (by admission no.). Cash and bank sales
  are recorded as other income (books and stationery sale / uniform sale), so they appear in the cash & bank book
  and profit & loss; fee-account sales appear on the student's next voucher under Others. Printable receipt.
- **Cancel a sale** (principals, with a reason): the items return to stock and the income or fee charge is
  cancelled; the sale is kept, marked cancelled.
- **Reports**: stock in hand with value, low and out of stock; sales for any dates with cash / bank / fee-account
  totals and totals by item; each item's stock card. All with Excel and Print. A Shop & stock section in Reports.
- Who: principals keep the item list and cancel sales; accountants sell and record stock in / out; branch owners,
  regional directors and head office see stock and sales. A few fictional items added to the demo campus.

Not deployed (the demo updates automatically when pushed).

## 0.26.0 — 2026-10-22 — M10: payroll

Added
- **Payroll** (Staff → Payroll), on the project lead's rules of 22 Oct 2026: every staff member has a fixed monthly
  salary; each day of absence or unpaid leave is cut at salary ÷ days in that month (half days and late arrivals
  are not cut). Someone who joins or leaves during the month is paid for the days on the staff.
- **Salaries and bank details** page (principals); salaries are kept apart from the staff record so only people
  with payroll rights see them; every change is in the history.
- **Finalise the month** (once it is over): payslips keep the figures even if attendance changes later; a month
  can be reopened with a reason. **Payslips** as PDF (two per A4, official logo) and a **bank sheet** in Excel.
- Who: principals set salaries and finalise; accountants, branch owners, regional directors and head office see
  payroll. Fictional salaries added to the demo staff.
- docs/AI_COST_ESTIMATE.md: the paid service the AI features need and an estimate of its cost.

Not deployed (the demo updates automatically when pushed).

## 0.25.0 — 2026-10-22 — M9: accounting

Added
- **Other income** (Expenses → Other income): money received other than fees, with a starter list of income heads
  (forms, books and stationery, uniform, canteen, events, rent, donations, bank profit, sale of old items, other);
  cash or which bank; cancelling keeps the record with a reason.
- **Cash & bank book**: for cash in hand, each of the branch's banks, and online payments not tied to a bank —
  opening balance, each day's fees (one line per day), other income and expenses, running and closing balance,
  for any dates. Principals enter the real opening balance on a day; the book counts forward from it.
- **Profit & loss** for any dates: fees received (cash / bank and online) and other income by head, less expenses
  by head, giving the surplus or deficit. A franchise's royalty on those fees is shown for information.
- **Income and expenses by branch** for head office and regional roles: every branch they look after, with totals.
- All with Excel and Print; also listed in Reports.

Not deployed (the demo updates automatically when pushed).

## 0.24.0 — 2026-10-22 — M8: notices and parent communication

Added
- **Notices** (Overview → Notices): circulars for parents, staff or both; for one branch, every branch of a head
  office, or the whole network (by those who look after it); optionally only for some classes; show-from and
  show-until dates; PDF/photo attachment kept private. Parents see them at the top of the parent portal with a
  "New" mark; staff see staff notices on their dashboard. The sender sees how many people opened each notice; a
  notice can be withdrawn.
- **Messages to parents** without a paid SMS service: choose a message template and who it is for (fee defaulters,
  students absent today, one class, all parents). Each message is filled in from TASEMS (student, class, fees owed,
  months unpaid, branch phone …). Send one by one with a WhatsApp button (the chat opens with the text ready) or
  download an Excel list for the branch's own SMS tool. Nothing is sent automatically; downloads are recorded.
- Four starter templates (fee reminder in Urdu and English, absence in Urdu, general message); head office edits
  them. Numbers and phone numbers stay left-to-right inside Urdu messages.
- **Parent portal as an app**: parents can add it to the phone's home screen; a "no internet" page is shown when
  offline. Children's details are never stored on the phone.

Roles: principals post notices and prepare messages for their branch; head office and network administrators also
post for every branch they look after; network administrators keep the message templates.

Not deployed (the demo updates automatically when pushed).

## 0.23.0 — 2026-10-22 — M7: academic management

Added
- **Subject teachers**: for each section, who teaches each subject (Academics → Timetable → Subject teachers).
- **Timetable**: the branch's bell times (periods and breaks), each class's week (Monday–Friday, and Saturday for
  classes that come on Saturday), each teacher's week and "My timetable" for teachers. A timetable that would put a
  teacher in two classes at the same time is not saved; clashes caused later are listed on the Timetable page.
  Printable.
- **Holiday calendar**: holidays of the session for this branch, or for every branch (head office). Each holiday is
  for students, staff or both. On a students' holiday no attendance register or diary is due; on a staff holiday
  staff are not counted absent. Existing holidays count for both.
- **Date sheet** for each exam (date and time of every paper), printable by class. Dates of a network-wide exam are
  set only by network exam setup, since they print for every branch.
- **Exam slips** (admit cards) with the student's photo, class, roll number and the class's date sheet, four per A4.
- **Award list** for each paper and section (roll no., name, marks entered or blank, signatures), with Excel.

Not deployed (the demo updates automatically when pushed).

## 0.22.0 — 2026-10-22 — M6: reports centre, family vouchers, background printing

Added
- **Reports** (Overview → Reports): for each module the person may open — Students, Attendance, Fees,
  Admissions, Exams, Staff, Expenses — four of today's figures and the list of printable reports.
- New reports: **Class strength** (boys, girls, Hifz per class and section, with totals), **New admissions**
  between two dates, **Monthly attendance by class** (register days, attendance %, absences, leave, late).
  All with Excel and Print.
- **Family vouchers** (Finance → Family vouchers): all children of one father (same CNIC) on one voucher with
  one Voucher ID from the same counter as other vouchers (never repeated). Three copies with barcode, each
  child's own voucher ID and amount, and the family total. Receiving it (family page, Barcode page, search, or
  a JazzCash file) pays each child's own voucher in full; a JazzCash amount that does not match the family total
  is refused rather than split by guesswork. A family whose children's vouchers change gets a new family voucher;
  the old one is marked replaced.
- **Background printing**: printing more than 100 vouchers or family vouchers at once makes the PDF in the
  background; a page shows progress and the download link ("My print jobs"). Only the person who asked can
  download it; files are removed after 7 days. Replaces the old "600 at most" limit.

Not deployed (the demo updates automatically when pushed).

## 0.21.0 — 2026-10-22 — M5: module restyle (lists, print, parent portal)

Added
- **Excel and Print on every list**: Students, Absent students, Vouchers, Defaulters (each student and by family), Fee collection, Royalty (statement and branch), Staff, Expenses, Admission inquiries, Monthly staff sheet. The Excel file holds every row that matches the filters (not only the page on screen), with the school, branch and date on top. Print on a list with several pages prints the whole list.
- Printouts show only the list: menus, filters and buttons are hidden; a line with the branch and the date is printed on top; the DEMO marker stays on demo printouts.

Changed
- Filters look the same everywhere (a filter card, or a compact row for a single date or month).
- Empty lists show the same "nothing here" panel with an icon.
- Fees home: the row of nine buttons is now a grid of quick links with icons ("Generate vouchers", "Barcode" added).
- Parent portal on phones: the top bar fits on one line, fee vouchers are shown as cards (month, Voucher ID, due date, amount, Paid or PDF), no sideways scrolling; the school's phone numbers are shown when no child is linked.

Not deployed (the demo updates automatically when pushed).

## 0.20.0 — 2026-10-22 — Project lead's follow-ups to round 2

Changed
- Fee head "Generator charges" removed (switched off instead if it was already used); AC charges stay. "Gen. Exp." is now named "Generator expenses", as on the school's voucher.
- Leaving and character certificates are printed on the school's letterhead: no logo, school name, border or footer, only the certificate title, with room at the top and bottom of the page.
- Certificate reference numbers: each branch has its own start (Setup → Branches, "reference number start"), e.g. HO-FAISALABAD-FSD-0001 for the head office campus. One series per branch for both certificates, never repeated. Older certificates keep their number with L/C added.

Added
- Expense heads: the usual school list (salaries, rent, utilities, books, exams, labs, IT, furniture, repairs, building, security, advertising, events, sports, refreshments, medical, staff welfare, training, postage, bank charges, taxes, royalty, other). Branch-own heads are not offered for now.
- docs/DESIGNATION_PERMISSIONS.md: the current designation → login role table, for the project lead to mark changes.

Not deployed (the demo updates automatically when pushed).

## 0.19.0 — 2026-10-22 — Project lead's changes, round 2: vouchers

Added
- Vouchers → "Generate vouchers": month, class (All, each class, Hifz Boys, Hifz Girls), section, and tick boxes for the other fees to add.
- Fee heads "Generator charges" and "AC charges" (amounts per branch in Fee rates).
- Receive fee: "Change other fees on this voucher" — change, remove or add other fees; the monthly fee and late fine cannot be changed; the Voucher ID stays the same; changes are recorded in the history.

Changed
- Vouchers no longer have an Arrears column: unpaid months show month by month with their fines.
- Menu "Make vouchers" is now "Generate vouchers".

Not deployed (the demo updates automatically when pushed).

## 0.18.0 — 2026-10-22 — M4: student lifecycle

Added
- Student photo (resized, private) on the profile; profile sections (details, family, brothers and sisters, classes, certificates, history); brothers and sisters by father's CNIC.
- Leave school: withdrawn / left, transferred out or graduated, with fees owed shown first; school leaving certificate and character certificate as numbered A4 PDFs with the official logo.
- Promotion to the next session: copy this year's sections, then class by class promote, keep in the same class, graduate (Class 10) or leave out; nothing changes in the current year.
- Student ID cards (credit-card size, 10 per A4 sheet) for one student or a class/section, with photo and admission-number barcode.
- Defaulters by family (one row per father, children and total owed).

Changed
- The demo server starts even when demo data cannot be loaded (e.g. other students were entered).

Not deployed.

## 0.17.0 — 2026-10-19 — Project lead's changes, batch 4: royalty and expenses

Added
- Royalty: paid, pending and total due for every branch on the royalty statement; each branch's royalty month by month with unpaid royalty carried forward; head office records "Royalty received" with a slip photo; branches see their own royalty.
- Expenses (Finance → Expenses): record an expense with head, amount, what for, paid to, cash or bank, bill photo; month totals by head and cash/bank; net cash today (cash fees received minus cash spent); cancelling keeps the record with a reason.
- Demo: royalty payments for some franchises and a few expenses.

Not deployed (demo updates automatically).

## 0.16.0 — 2026-10-19 — Project lead's changes, batches 1–3: students, attendance, staff, fees

Changed
- Students list: separate Class and Section columns, Father name column, order Admission no → Name → Father name → Class → Section → Parent mobile → Status; Class then Section filters; search also by father name; "Add a student" and "Import from Excel" at the top; status "Withdrawn / Left".
- Admission numbers: numbers only, next number filled in automatically.
- Add/Edit student: student email, current and permanent address; Class → Section (only that class's sections) → Subject group (Biology/Computer, Pre-9th to 10th); roll number optional; Family details for father (name, mobile, email, occupation, organisation), mother and guardian (with relationship); Reference and Notes; father CNIC required.
- No Urdu entry boxes in any form (students, Setup, users); the Excel template no longer has Urdu columns.
- Setup offers the usual section names (Rose, Jasmine, Daisy, Pansy, Tulip); the demo uses them, and older demos are updated on their next start.

- Admission inquiries: menu renamed, "Add inquiry" at the top, notes labelled "Description".
- Attendance: Class, Section, Present, Absent, Leave, Register order; absent students by class and section, with father's and mother's mobiles.
- Staff: "Add staff member" and "Import staff from Excel" at the top; father name required, separate husband name, present and permanent address, designation from a fixed list (Director … Lawyer), CV upload (JPG/PDF, private).
- Fees: Cash or Bank with each branch's own banks (Setup); who received each payment shown everywhere; today's total with cash per person and each bank on the Fees page, Daily collection and the dashboard; Daily collection columns Date → Voucher ID → Student → Father → Method → Received by; Finance → Barcode quick receive by Voucher ID; optional receipt photo on a payment (private).
- Discounts: head office's list of discounts, chosen on the admission form; 100% discounts wait for approval.

Fixed
- The Father CNIC box cut off a CNIC typed with dashes at 13 characters.

Not deployed (demo updates automatically). 201 automated tests.

## 0.15.0 — 2026-10-19 — Settings and branch management (Phase 4, M3)

Added
- Setup area (/setup/), shown to people who may change setup: classes and sections (class teacher, boys/girls group, campus, capacity), campuses, fee rates per class from a chosen month, voucher and bank settings, branches and regions, academic sessions with "Make current".
- Users and roles: search staff logins, add a login with its first role, give and end roles, reset a password, switch a login off and on. New and reset passwords are random, shown once and never stored in the history.
- My password: every staff member can change their own password from the top bar.
- Access rule (D-066): roles can be given only inside your own area; roles that manage logins, structure or the audit log only by someone who holds those powers there; nobody changes their own access; superusers are protected.
- Urdu for all new text and clear labels on every setup form. 17 setup tests (194 in total).

Changed
- Settings menu: "Setup" opens the new screens; the admin site is now "Advanced setup" (staff accounts only).

Not deployed.

## 0.14.0 — 2026-10-19 — Role dashboards (Phase 4, M2)

Added
- The home page is now a dashboard built from what each person may see: quick actions; class teachers see today's register and diary for each of their classes (with one-press links) and students absent three or more days in a row; principals see today's attendance with a class-wise table and a 14-day chart, this month's fees (billed, received, % collected, owed, received today) with a daily chart and payment methods, admissions and student records; head office and anyone with several branches see network totals, a 14-day attendance chart, a branch table with attendance and fee-collection meters, filters by head office and region, five orderings and the royalty due this month; staff with a login see their own attendance this month.
- "Hide amounts" switch on money figures, remembered on each browser.
- Charts drawn on the server (no chart library): one series in the brand colour, value on hover and keyboard focus, and a table view under each chart.
- Urdu for all dashboard text. 12 dashboard tests (177 in total).

Changed
- Teacher's home: the register link reads "Change register" once today's register is taken.

Not deployed.

## 0.13.0 — 2026-10-17 — Design system (Phase 1: UI/UX foundation)

Added
- One organised stylesheet with design tokens (logo colours, spacing, type scale, shapes) and shared components: page header, buttons (primary, secondary, quiet, danger, small, busy, disabled), cards, KPI figures, tables with totals, filter bars, form fields (required mark, error state), badges, messages, callouts, empty states, tabs, pagination. Every existing screen picks them up without changes to its address or behaviour.
- Confirmation dialog before cancelling a voucher or charge, reversing a payment, cancelling approved leave or withdrawing a leave request (the same button and values are sent after "Yes, continue"; works without JavaScript as before).
- Every form that saves shows "busy" after the first press and ignores further presses, so a payment cannot be saved twice.
- Student search in the top bar (opens the student list with the same search); running academic session at the foot of the sidebar.
- Living style guide at /design-system/ (staff accounts) and docs/DESIGN_SYSTEM.md.
- Urdu for all new text. 4 more automated tests (165 in total).

Fixed
- In Urdu, the attendance register's script stopped because a translation contains quotation marks: live counts and the draft kept on the phone did not work. Strings in scripts are now escaped (with a test).
- Branch name in the top bar is cut from the correct end in Urdu.

Not deployed.

## 0.12.0 — 2026-10-17 — New staff screen frame and official colours (Phase 4, M1)

Added
- Collapsible left sidebar with grouped menu (Overview, Students, Academics, Finance, Staff, Settings) and icons; it remembers being collapsed, slides in on phones, and mirrors for Urdu. Shows only pages the person may open, including pages that were reachable only from inside a module (absent students, admissions report, vouchers, defaulters, daily collection, discounts, staff attendance, monthly sheet, leave).
- Top bar with a searchable branch picker grouped by head office (type to filter; built for 350+ branches; works without JavaScript), language switch, signed-in user and sign out.
- Official colours taken from the logo: blue #3E4095 and red #ED3237 (D-061); status colours kept separate; all text colours pass WCAG AA contrast.
- Local Lucide icon sprite (ISC licence, 36 icons, ~11 KB); no outside services.
- 12 automated tests (161 in total): every menu item opens for every demo role, the branch picker, and the hidden actions below.

Fixed
- Buttons that led to a "Forbidden" page are no longer shown: "Remarks for result cards" and "Enter teacher ratings" for sections the person may not change, "Receive" on fee vouchers for people who do not take payments, and "Take register" on the home screen on days the class does not attend.

Not deployed.

## 0.11.0 — 2026-10-17 — Demo server

Added
- `manage.py seed_demo`: fictional demo data (classes, students, parents, staff, attendance, diary, Mid-Term marks, fees, staff punches, inquiries) and demo logins for every role; refuses a database with real students.
- DEMO_MODE: no two-step sign-in, "DEMO" bar on every page; `check_security` fails while it is on.
- render.yaml for a one-click demo on Render.com; docs/DEMO.md with logins and what to try.
- Docker image: listens on $PORT, media folder writable by the app user.
- 149 automated tests.

Not deployed.

## 0.10.2 — 2026-10-17 — Import from the previous software

Added
- Student import accepts the previous software's "Student Data" PDF report as it is, besides the Excel template.
- New import columns: Other Mobile, Father Occupation, Monthly Fee; Admission Date optional (session start used, shown before import).
- "Agreed fee" special discount type: the student pays exactly this monthly fee; carried over from the old software on import.
- 147 automated tests.

Not deployed.

## 0.10.1 — 2026-10-17 — Official logo

Added
- The official The Arqam Schools logo on fee vouchers (all three copies and the back), result cards, daily diaries, staff and parent sign-in pages, the top bar and the browser tab icon. Used exactly as provided.

Not deployed.

## 0.10.0 — 2026-10-16 — Milestone 3c: Admissions

Added
- Inquiry form (only the essentials required), from any source; follow-up person and next follow-up date.
- Pipeline: due today, open, all; filters by class, source, status, "only mine"; campus visits today.
- Inquiry page: call and WhatsApp buttons (ready message, opens the parent's chat), siblings at school and earlier inquiries by mobile number, follow-up with status change, full history.
- Admit: student record made from the inquiry, then straight to the admission fee voucher.
- Report by source, class, status and reasons for not joining; Excel download.
- Row-level security on admissions tables; Urdu; 146 automated tests.

Not deployed.

## 0.9.0 — 2026-10-16 — Parent portal

Added
- Parent sign-in with mobile number and password; lockout after repeated failures.
- First-time set-up and password reset with a one-time code printed by the school (one family or a whole class).
- Each child: daily diary (image and PDF), monthly attendance, fee balance, vouchers (PDF) and payments, published result cards (PDF).
- Parents see only their own children, in any branch; staff screens refuse them.
- English and Urdu, phone-sized; 140 automated tests.

Not deployed.

## 0.8.1 — 2026-10-16 — Staff: confirmed timings and unpaid leave

Changed
- Samanabad staff duty time 07:45–13:45, Monday to Saturday (seeded; editable in Setup).
- Leave has no fixed allowance and is unpaid; the monthly sheet and its Excel show "unpaid days" (absent + unpaid leave) for salary deduction.

Not deployed.

## 0.8.0 — 2026-10-16 — Milestone 3a: Staff (HR) and staff attendance

Added
- Staff register: add, edit, search; staff list import from Excel with row-by-row checks.
- Attendance machine file import (Excel, CSV, or the machine's .dat/.txt log), matched by machine ID; the same file imported twice adds nothing.
- Daily status per person: present, late, half day, absent, on leave, holiday, off day — from per-branch duty time, grace minutes and half-day time.
- Principal corrections with a reason, kept and audited; daily and monthly views; monthly Excel for payroll.
- Leave requests (by the person or the principal), approval by someone else, balances per session; "My attendance" for staff with a login.
- Row-level security on staff tables; Urdu translations; 133 automated tests.

Fixed
- Father's CNIC typed with dashes (33100-1234567-1) was refused on the student form.

Not deployed.

## 0.7.1 — 2026-10-16 — Fees: confirmed rules and JazzCash files

Changed
- Royalty is 8% of all fees received in the month (confirmed).
- Re-admission column removed from the voucher (there is no re-admission fee).

Added
- Voucher list for JazzCash: unpaid vouchers of a month as an Excel file.
- Payments from a file: JazzCash's (or a bank's) paid list imported by Voucher ID; every row checked first (unknown or cancelled vouchers, repeats, already recorded), then recorded with the normal rules.
- 121 automated tests.

Not deployed.

## 0.7.0 — 2026-10-16 — Milestone 2b: Fees

Added
- Fee heads matching the school's voucher; per-branch fee rates by class with start dates; Samanabad fees seeded as confirmed.
- Father's name and CNIC on the student record and Excel import; brothers and sisters recognised by CNIC for the sibling fee.
- Monthly vouchers for the whole branch or chosen classes, with a check before anything is made; annual charges in April, summer vacation work in July; students already billed are skipped.
- Single-student vouchers: admission, registration, annual or other charges, several months together.
- Unpaid balance carried to the next voucher with the Rs 200 late fine once per late voucher; due date the 10th or the day made.
- Printed voucher: A4 with School, Bank and Student copies, barcode, bank details from Setup, and the Fee Payment Options back page (English and Urdu).
- Receive payment by scanning or typing the Voucher ID: cash, bank deposit, transfer, JazzCash, Alfa app; transaction ID required for non-cash; receipt; reversal with reason.
- Student fee account, special discounts with approval by someone else, defaulters list, daily collection, royalty statement for head office.
- Row-level security on fee tables; 119 automated tests.

Not deployed.

## 0.6.0 — 2026-10-16 — Milestone 2a: Examinations and results

Added
- Approved result pattern stored as data: Final 50, Mid-Term 25, Attendance 5 (automatic), Discipline 5, Neatness 5, Summer vacation work 5, Class work & homework 5.
- Exams (network-wide or per branch) with papers per class and subject, each with its own total.
- Marks entry per paper and section: half marks, absent / absent with leave, checks against the paper total, nothing saved until all values are valid; corrections audited.
- Teacher ratings screen for discipline (once per student) and neatness, summer work, class work (per subject).
- Results per section: percentage, grade, pass, positions (1st–3rd), and exactly what is still missing per student.
- Mid-Term progress report and annual result card: one A4 page per student, PDF for a student or the whole section; class teacher and principal remarks.
- Row-level security on marks, ratings and remarks.
- 92 automated tests.

Not deployed.

## 0.5.0 — 2026-10-16 — Milestone 1f: Pilot hardening and head office view

Added
- PostgreSQL row-level security on every branch-owned table; each signed-in request is limited to the user's branches inside the database too.
- `manage.py check_security` for go-live (database role, row-level security, DEBUG, keys, HTTPS settings).
- Fonts served from TASEMS itself as small WOFF2 files; no outside font service.
- Head office home: today's registers taken and diaries published, per branch, with unfinished branches first.
- `/healthz` for uptime monitoring.
- Production setup: Docker Compose with Caddy (automatic HTTPS), ordinary `tasems_app` database role, WhiteNoise static files, only logo files publicly served.
- Encrypted nightly backup script and restore-drill script; deployment guide.
- Uploaded Excel files older than a day are removed automatically.
- 79 automated tests.

Not deployed.

## 0.4.0 — 2026-10-16 — Milestone 1d: Daily Diary

Added
- Daily Learning Overview per section and school day, matching the school's current diary layout.
- In Class Learning and Home Learning Tasks per subject, with deadline defaulting to the next school day of that class.
- Subjects with nothing in a part of the diary are left out of that part; Urdu text detected and set right-to-left in Nastaliq.
- Draft and publish; class teacher writes own sections (today and up to 7 days ahead); principal and coordinator any day.
- Theme of the week, week number and quote: network-wide from head office, or per branch.
- One-page A4 PDF and a 1080-px-wide image for WhatsApp; fonts bundled with the system.
- Subjects of the Class 4 diary seeded; other classes' subjects entered by head office.
- 73 automated tests.

Not deployed.

## 0.3.0 — 2026-10-16 — Milestone 1c: Student attendance

Added
- Daily register per section (once a day): present by default; absent, leave and late with an optional note.
- Who can mark: class teacher for own sections, today only; principal and academic coordinator for any section and any past day of the session. Corrections are written to the audit log student by student.
- Draft kept on the phone if the connection drops; restored when the page is opened again.
- Absent students page with parent mobile (tap to call) and students absent 3 or more days in a row; printable.
- Today page: registers taken, attendance %, absent and leave counts, my classes; head office branch summary.
- 60 automated tests.

Not deployed.

## 0.2.0 — 2026-10-16 — Milestone 1b: Staff access and student register

Added
- Sign-in page (username or mobile number), lockout after 5 failed attempts in 15 minutes.
- Two-step sign-in for privileged roles: authenticator app (QR set-up), encrypted keys, codes cannot be reused, 8 one-time backup codes. Admin site uses the same sign-in.
- English and Urdu interface (Urdu right-to-left, Nastaliq font); language follows each user's preference.
- Branch switcher for head office and regional staff.
- Home screen: active students, Hifz students, missing parent contacts, unplaced students, students by stage, my classes, branch table for head office.
- Student register: search by name, admission number or parent mobile; filters by class, section, status; add and edit with class and primary contact; siblings share a parent contact; record history.
- Excel import: template download, row-by-row problem report, all-or-nothing save, sections created automatically (boys/girls from Class 6).
- 49 automated tests.

Not deployed.

## 0.1.0 — 2026-10-16 — Milestone 1a: Foundation

Added
- Django 5.2 project with PostgreSQL, environment-based settings, English/Urdu language setup, Pakistan time zone.
- Organisation: head offices, regions, branches (ownership and royalty %), academic sessions.
- Accounts: custom user, roles, scoped role assignments, role-based permission backend.
- Branch isolation helpers (`for_user`, `has_branch_perm`, scoped admin).
- Academics: class levels, subjects, curriculum mapping, sections.
- People: students, guardians, student–guardian links, enrolments.
- Append-only audit log.
- `seed_tasems` command (confirmed facts only): 15 class levels incl. Prep and Pre-9.
- Boys/girls separation from Class 6: section gender group and enrolment check.
- Campus (building) under Branch for separate boys/girls buildings; sections can be placed in a campus.
- 27 automated tests; GitHub Actions CI (lint, checks, migrations, tests); Dockerfile and docker-compose.

Not deployed.
