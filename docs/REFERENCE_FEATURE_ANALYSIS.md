# Reference feature analysis

Reference: "School Management System FULL DEMO 2023 — School ERP App in Pakistan" (YouTube `Xiu8PA_eeVQ`).
Analysed 17 Oct 2026 from the MP4 supplied by the project lead (37 min 04 s, 640×360).

## Method and limits

- 194 distinct screens were extracted by scene-change detection and reviewed, plus a frame every 8 seconds.
- **The video is 360p:** page titles, KPI captions, report headings and printed documents are readable;
  most menu sub-items, table column headers and form labels are not. Items marked *(likely)* were read from
  blurred text and should be confirmed.
- **No audio was used:** speech-to-text models could not be downloaded in the build environment, so the spoken
  narration is not part of this analysis.
- The reference is analysed for **workflows and completeness only**. Its layout, artwork, names and branding
  are not copied.

## 1. Overall structure

| Element | What the reference shows |
| --- | --- |
| Sidebar | Long single-level list of ~30 modules with expandable sub-menus; dark blue background; icons on each item; red badges on some items |
| Top bar | Student search box, language switch ("English"), **campus switcher** ("Main Campus", with "Are you sure to change the campus?" confirmation), quick-action icons with counters, user menu, log out |
| Footer | "Running Session: 2023-2024" with a **session switcher**, website link, logged-in user |
| Quick-launch strip | A row of ~20 coloured icon buttons above the dashboard for the most used screens |
| Module landing pages | Pattern used everywhere: **4 KPI cards** on top, then a **"Printable … Reports"** panel listing 4–6 reports, each with a Print button |
| Lists | Data tables with page size, Copy / Excel / CSV / PDF / Print export buttons, search, coloured action buttons per row |
| Confirmations | Modal "Are you sure?" dialogs before campus switch, deletions, actions |
| Empty states | Illustration + short message (e.g. ID card printing before a class is chosen) |
| Printed documents | Browser print pages with school logo, name, address, title, table, "Remarks (if any)" line and print timestamp |
| Mobile apps (advertised) | Admin portal, Staff portal, Student portal, Parent portal, Payments, Homework, Timetable, Digital/Self attendance |

## 2. Screens and features by area

### Admin dashboard
- 12 KPI cards: Unpaid invoices, *(likely)* Unpaid amount, Income today, Expense today, Profit today,
  Income this month, Expense this month, Profit this month, Income this year, Expense this year,
  Profit this year, Current session.
- **"Show/Hide Details"** toggle masks money figures as `****` (privacy when others can see the screen).
- Widgets: Monthly income & expense overview (bar chart), Latest admissions (photos + dates),
  Staff attendance overview (present / absent today), Month-wise paid/unpaid fee chart for the current year,
  totals for students / teachers / staff / students present today with attendance %, **class-wise attendance
  table** (class, strength, present, absent, leave, …), month-wise income chart, staff-present donut chart.

### Admission management
- Sub-menu: Admit student, **Admit bulk students** (Excel upload with sample file and instructions),
  Admission requests *(likely online)*, Admission inquiries, Admission reports.
- Reports page KPIs: Admissions today, Admissions this month, Active students, Deactivated students.
- Printable: New admissions (today), Monthly admissions, **Admission forms** (filled), **Blank admission form**.

### Student management
- Sub-menu *(likely)*: Student information, Student promotion, Student attendance, Student timeline,
  Student info reports.
- Student list filtered by campus, class, section and type; per-row actions: profile/fee, **Certificates &
  reports**, edit, delete.
- **School Leaving Certificate** (two copies per page: office and student).
- **Character Certificate** (two copies).
- **Student attendance history** for a whole year (month × day grid) with a monthly summary.
- Info reports KPIs: Total, Male, Female, *(likely)* Pass-out students. Printable: All active students,
  All inactive students, Class-wise student report, *(likely)* Pass-out students.

### Parent accounts
- KPIs: Total parents, *(likely)* Parents with dues, Active accounts, *(likely)* Inactive accounts.
- Printable: All parents, Parent credit report, **Family tree report**, **Defaulter parents report**
  (per family: each child, unpaid invoices, total due, remarks line).
- Sub-menu *(likely)*: Manage accounts, Account requests, Parent complaints.

### Staff management
- KPIs: Total teachers, Present today, Absent today; staff list with photo, designation, actions.
- **Experience certificate** (two copies, signed by Incharge and Principal), printable by certificate type.
- **Staff salary report** (monthly, per employee, with paid/unpaid status).

### ID card printing
- Print student ID cards, Print staff cards, ID card settings (design/colours, *(likely)* front/back).

### Accountants
- KPIs: Total, Active, Restricted accounts; list with on/off toggles for access; separate user type for fee staff.

### Attendance
- Student attendance and staff attendance sub-menus.
- **Webcam / self attendance** for staff (camera capture with "Are you all done?" confirmation).
- KPIs: Present staff today, Absent staff today, Present students today, Absent students today.
- Printable: Student attendance sheet, Staff attendance sheet, Staff attendance summary,
  Student attendance summary, **Subject/lecture attendance summary**, **Staff hourly attendance summary**.

### Online classes
- Online class list with "Start class" ("Are you ready?") opening a third-party video meeting.

### Timetable management
- Weekly timetable per class and section (Monday–Saturday), print timetable.

### Fee payment and accounting
- Student fee management: per-student fee lines, status (paid/unpaid), collect payment, payment history.
- **Payment receipt** (two copies) and **fee voucher with three copies** (bank, school, student), barcode,
  fee description, arrears, fine after due date, validity and due dates, **12-month paid/unpaid strip**.
- **Class-wise bulk voucher printing** and **family-wise vouchers** (all children of one family on one voucher).
- **Family fee collection** screen: all children's invoices together, sub-total, totals before/after due date,
  collect / print family voucher.
- Accounting sub-menu *(likely)*: Generate monthly fee, Generate custom fee, Generate transport fee,
  Fee types / fee heads, Family fee vouchers, Expense *(manage)*, Direct payment, Defaulters, Print vouchers.
- **Expense report** and income/expense totals (income, expense, profit for a period).

### Point of sale and stock (inventory)
- **Point of sale**: scan product barcode, cart, total, payment, printed **sales receipt**; product categories.
- Stock KPIs: Total products, Out of stock, Sales today, Sales this month.
- Printable: Total products, Out-of-stock products, **Monthly sales & profit**, Low-stock products.

### Examinations
- **Examination slip** (roll-number slip) with photo and the student's **date sheet** (date, day, subject,
  start/end time, duration, room) plus instructions.
- **Result card** with logo, student details, subject marks grid, totals.
- Print exam awards / results by campus, class, section and session *(likely award list)*.

### Communication and other modules (sidebar, late in the video)
- Study material — LMS *(likely)*, Leave management, **SMS management**, **Mobile app notifications**
  (notification templates with placeholders such as `{student_name}`, send to staff / parents, history),
  **WhatsApp notifications**, **Email alerts**, School website management *(likely)*, Manage campuses,
  Admin users management, Transport, **Manage biometric devices**.
- **Settings**: school name, logo, theme colours and ID-card/letterhead design.

## 3. Strengths worth adopting (adapted, not copied)

1. Every module opens on a **summary page**: KPI cards + a list of printable reports. Simple for office staff.
2. **Family view of fees** (family voucher, family collection, defaulter parents report).
3. **Certificates** (leaving, character, experience) and **ID cards** printed from the system.
4. **Exam slips with date sheet**, result cards, award lists.
5. **Show/Hide money** toggle on dashboards.
6. Consistent **export buttons** (Excel/CSV/PDF/Print) on lists.
7. **Notification templates** with placeholders for SMS/WhatsApp/app messages.

## 4. Weaknesses to avoid

1. ~30 flat sidebar items; hard to scan → TASEMS uses **8 grouped sections**, permission-filtered.
2. Saturated multi-colour KPI cards (red/orange/blue/grey/green with no meaning) → TASEMS uses colour only for
   status, with brand colours for identity.
3. Dense tables with many coloured buttons per row → one primary action + a row menu.
4. Browser-print documents with no Urdu support → TASEMS keeps server-made PDFs with correct Nastaliq.
5. Single school with campuses → TASEMS must scale to 350+ branches and two head offices.
6. No sign of branch-level data isolation, audit log or two-step sign-in → TASEMS keeps its stronger controls.
