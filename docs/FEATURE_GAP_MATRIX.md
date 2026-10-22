# Feature gap matrix

Each feature area from the upgrade brief, compared with what TASEMS has today (audit of 17 Oct 2026) and with
the reference video (analysed 17 Oct 2026, see REFERENCE_FEATURE_ANALYSIS.md). Rows marked **[ref]** are features
seen in the reference video.

**Categories:** A = implemented and working · B = working, needs UI/UX improvement · C = partially implemented ·
D = missing · E = not relevant / excluded unless approved.
**Approval:** ✱ = needed project-lead approval (scope change, earlier decision, or paid service). **All ✱ items
were approved on 17 Oct 2026** (Hifz, payroll, accounting, inventory, paid usage-based services) — see D-056 to D-060.

## 1. Head Office Dashboard — **B / C**
| Feature | Today | Cat. |
| --- | --- | --- |
| Today's registers and diaries per branch | Done (1f) | B |
| Network KPIs (students, attendance %, collection, defaulters, admissions) with trends | Not built | D |
| Branch comparison / league tables, charts | Not built | D |
| Filter by head office → region → branch | Data exists; no screen | C |
| [ref] Income / expense / profit cards (today, month, year), "Show/Hide" money toggle | Fees only; no expenses yet | D |
| [ref] Class-wise attendance table, fee paid/unpaid by month chart, latest admissions | Not built | D |
| [ref] Quick-launch shortcuts | Not built | D |

## 2. Multi-Branch Management — **C**
| Feature | Today | Cat. |
| --- | --- | --- |
| Head offices, regions, branches, campuses, company/franchise, royalty % | Models + Django admin | C |
| Purpose-built branch management screens | Not built (D-012: admin is temporary) | D |
| Searchable branch selector for 350+ branches | Plain dropdown | B |
| Branch profile page (principal, staff count, students, fees) | Not built | D |

## 3. Student Management — **A / B / C**
| Feature | Today | Cat. |
| --- | --- | --- |
| Register, search, filter, add, edit, history, Excel and PDF import | Done | A/B |
| Student profile with tabs (attendance, fees, results, diary) | Data exists on separate screens | C |
| Student photo | Not built | D |
| Session rollover / promotion to next class | Not built | D |
| Withdrawal / transfer / graduation status | Status field exists; no guided workflow | C |
| School leaving and character certificates | Not built | D |
| Student ID cards (print) | Not built | D |
| Bulk actions (section change, print) | Not built | D |
| [ref] Year attendance history per student (month × day grid) | Monthly view in parent portal only | C |
| [ref] Student info reports: active, inactive, class-wise, pass-out | Lists exist; no printable set | C |

## 4. Admissions Management — **A / B**
| Feature | Today | Cat. |
| --- | --- | --- |
| Inquiry pipeline, follow-ups, visits, admit → voucher, reports | Done (3c) | A/B |
| Admission test / assessment marks | Stage exists in pipeline; no marks | C |
| Online inquiry form for the website | Not built | D |
| Document checklist (B-Form, photos, previous result) | Not built | D |
| [ref] Printable admission form (filled) and blank admission form | Not built | D |
| [ref] Bulk admission from Excel | Done (student Excel import) | A |
| [ref] Admissions today / this month reports | Report exists by source/class/status | B |

## 5. Parent Management — **C**
| Feature | Today | Cat. |
| --- | --- | --- |
| Guardian records, primary contact, sibling link by CNIC | Done | A |
| Parent portal (diary, attendance, fees, results) | Done (3a+) | A/B |
| Parent directory screen (all families, children, balances) | Not built | D |
| Parent portal as installable app (PWA) | Planned in D-002 | D |
| [ref] Family tree report, parent credit report, defaulter parents (family-wise) report | Defaulters by student only | D |
| [ref] Parent complaints / requests | Not built | D |

## 6. Staff Management — **A / B**
| Feature | Today | Cat. |
| --- | --- | --- |
| Staff register, import, profile, link to login | Done (3a) | A/B |
| Staff documents (CNIC copy, degrees), photo | Not built | D |
| Recruitment, appraisals | Not built | D ✱ |
| [ref] Experience certificate | Not built | D |
| [ref] Staff ID cards | Not built | D |

## 7. Attendance — **A / B**
| Feature | Today | Cat. |
| --- | --- | --- |
| Student daily register, corrections, absentees, branch summary | Done (1c) | A/B |
| Staff biometric import, daily/monthly, corrections | Done (3a) | A/B |
| Public-holiday calendar for student registers | Not built (known gap) | D |
| Attendance charts and monthly reports per class | Partial | C |
| Absence SMS/WhatsApp to parents (automatic) | Not built; needs paid provider | D ✱ |
| [ref] Printable attendance sheets and summaries (student, staff) | Staff month Excel; student absentees | C |
| [ref] Webcam / selfie staff attendance | Not built; biometric machines are used (D-011) | E |
| [ref] Subject/lecture and hourly attendance | Once a day by decision (D-020) | E |
| [ref] Biometric device management screen | File import only (D-042) | C |

## 8. Fee Management — **A / B**
| Feature | Today | Cat. |
| --- | --- | --- |
| Rates, vouchers, sibling, discounts, arrears, fine, receive, receipts, defaulters, collection, royalty, JazzCash Excel | Done (2b) | A/B |
| Bulk voucher printing for a full branch | Works but slow (~23 s / 32 vouchers) | B |
| Fee rate / bank details setup without Django admin | Admin only | C |
| Online payment from the parent portal; Bank Alfalah API | Deferred (D-050) | E ✱ |
| Fee reminders by SMS/WhatsApp | Not built; paid provider | D ✱ |
| [ref] Family voucher (all children on one voucher) and family fee collection | Sibling rule exists; vouchers per student | D |
| [ref] 12-month paid/unpaid strip on the voucher | Not on voucher | D |
| [ref] Transport fee | No transport module | E |

## 9. Accounting — **D** ✱
| Feature | Today | Cat. |
| --- | --- | --- |
| Fee income ledger | Done (fee ledger, D-033) | A |
| Expenses (bills, rent, utilities), other income | Not built | D ✱ |
| Cash book / bank book, branch profit and loss | Not built | D ✱ |
| Chart of accounts / double entry | Not built | D ✱ |

## 10. Examination Management — **A / B / C**
| Feature | Today | Cat. |
| --- | --- | --- |
| Exams, papers, marks, ratings, remarks, results, result cards | Done (2a) | A/B |
| Exam setup screen for head office (not admin) | Admin only | C |
| Date sheet, roll-number slips, award lists | Not built | D |
| [ref] Examination slip with photo and date sheet | Not built | D |
| Result analysis (subject averages, pass %) | Partial | C |

## 11. Homework and Daily Diary — **A / B**
| Feature | Today | Cat. |
| --- | --- | --- |
| Daily Diary with home tasks, PDF, WhatsApp image, parent portal | Done (1d) | A/B |
| Subject lists for classes other than Class 4 | Pending school input | C |

## 12. Inventory — **D** ✱
Items, stock in/out, issue to staff, sale of books/uniforms (linked to fee vouchers), low-stock alerts. Not built.
[ref] Point of sale with barcode scanning and sales receipt; reports: total products, out of stock, low stock,
monthly sales & profit.

## 13. Reports — **C**
Reports exist inside each module (absentees, defaulters, collection, royalty, admissions, staff month).
No central **Reports centre** with consistent filters and formats. **C**

## 14. Printing and Exports — **A / C**
| Feature | Today | Cat. |
| --- | --- | --- |
| Diary, voucher, receipt, result card PDFs; several Excel exports | Done | A |
| Consistent "Export to Excel / PDF" on every list | Not consistent | C |
| Background generation for large print jobs | Not built | D |

## 15. HR and Payroll — **C / D** ✱
Monthly attendance sheet with unpaid days exported to Excel (D-045 chose *integrate, not build* payroll).
Salary structure, allowances/deductions, payslips, bank sheet: **not built; reverses D-045 → approval needed.**

## 16. Academic Management — **C**
| Feature | Today | Cat. |
| --- | --- | --- |
| Class levels, subjects, curriculum, sections, class teacher | Done (admin for setup) | A/C |
| Subject–teacher assignment per section | Not built | D |
| [ref] Weekly timetable per class/section, printable | Not built | D |
| [ref] Online classes (third-party video) | Not requested | E |
| [ref] Study material / LMS | Not requested | E |
| Timetable | Not built | D |
| Syllabus / lesson-plan tracking | Not built | D |

## 17. Hifz Management — **D** ✱
Sabaq, Sabqi, Manzil, mistakes, milestones, parent reports. Built in M12 (23 Oct 2026, D-081): daily sheet per
Hifz section, para tests, 30-para progress, section report, parents' Hifz tab.

## 18. AI Teacher Assistant — **D** ✱
Provider chosen (Claude API, D-026). **Deferred (D-027)** until textbook PDFs and API billing are ready. Paid per use.

## 19. AI Question Paper Generator — **D** ✱
Not built. Depends on 18 (textbook content, API billing). Teacher must review every paper before use.

## 20. AI Analytics — **D** ✱
Not built. A rules-based "at-risk" view (attendance streaks, falling marks, unpaid fees) can be built first at
no running cost; AI-written summaries on top need the API.

## 21. Parent Communication — **C**
| Feature | Today | Cat. |
| --- | --- | --- |
| WhatsApp button with ready message (no API) | Done (D-049) | A |
| Notices / circulars shown in the parent portal | Not built | D |
| Bulk SMS / WhatsApp Business API | Not built; paid provider | D ✱ |
| [ref] Message templates with placeholders; sent history | Not built | D |
| [ref] Email alerts | Not built | D |

## 22. User Roles and Permissions — **A / C**
| Feature | Today | Cat. |
| --- | --- | --- |
| Roles × scopes, two-step sign-in, lockout, audit | Done | A |
| User and role management screens (not admin) | Admin only | C |
| Permission matrix view | Not built | D |
| Hide actions a user cannot perform (403 links found in live test) | Bug-level UX issue | B |
| [ref] Enable/disable user access with a toggle | Django admin only | C |
| [ref] School settings: logo, theme colours, letterhead/ID-card design | Diary layout + logo only | C |

## Summary

| Category | Areas |
| --- | --- |
| Mostly A (working) | Students, Admissions, Attendance, Fees, Exams, Diary, Staff, Roles core |
| B (UI/UX) | Everything above — app shell, dashboards, tables, filters, forms |
| C (complete it) | Multi-branch screens, settings outside admin, reports centre, parent directory, academic setup, exports |
| D (new, no approval needed) | Promotion, certificates (leaving, character, experience), ID cards, photos, timetable, notices, holiday calendar, background printing, family vouchers, exam slips, printable report sets, money-hiding dashboards |
| D ✱ (new, approved 17 Oct 2026) | Accounting, Payroll, Inventory, Hifz, AI ×3, SMS/WhatsApp API, recruitment/appraisals |
| E | Bank Alfalah API / online payment (deferred, D-050); [ref] webcam attendance, lecture/hourly attendance, transport, online classes, LMS, student logins (D-009) — excluded unless approved |
