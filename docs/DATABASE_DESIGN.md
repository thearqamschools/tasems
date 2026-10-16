# Database design (as built)

PostgreSQL 16, one database, shared schema. Migrations are versioned in each app's `migrations/` folder; never change production by hand.

## Modules and tables

| App | Table | Owned by | Notes |
| --- | --- | --- | --- |
| organisation | HeadOffice | Network | Faisalabad, Lahore |
| organisation | Region | Head office | Cities/areas a head office supervises |
| organisation | Branch | Head office (+ region) | `ownership` company/franchise, `royalty_percent` (default 8.00) |
| organisation | AcademicSession | Network | Only one may be current (database constraint) |
| accounts | User | — | Custom user: phone, Urdu name, preferred language |
| accounts | Role | Network | Permission bundle, allowed scopes, `requires_mfa` |
| accounts | RoleAssignment | — | User × role × scope target; database check ensures the target matches the scope |
| academics | ClassLevel, Subject, CurriculumSubject | Network | One syllabus across the network |
| academics | Section | Branch | Unique per branch + session + class + name |
| people | Student | Branch | Admission number unique within a branch; status history via audit log |
| people | Guardian | Branch | Linked to students through StudentGuardian; one primary contact per student |
| people | Enrolment | Branch | One per student per session; roll number unique within a section |
| attendance | AttendanceRecord | Branch | One per student per day (unique); indexed by branch+date+status and section+date; partition by month at national scale |
| attendance | SectionAttendance | Branch | One per section per day with totals; what dashboards read |
| exams | GradingScheme, GradingComponent | Network | The result pattern as data; one default scheme, optional per stage |
| exams | Exam, Paper | Network or branch | Paper = class × subject × total marks |
| exams | Mark | Branch | One per paper per student; corrections audited |
| exams | Rating | Branch | Teacher marks for non-exam parts; subject empty for student-level parts |
| exams | ResultRemark | Branch | Class teacher and principal remarks per exam |
| fees | FeeHead | Network | Voucher columns: Admission, Reg., Tuition, Annual, S.V.W., Gen. Exp., Others, Fine |
| fees | FeeRate | Branch | Amount per head, class (or all classes) and start date; sibling amount |
| fees | BranchFeeSettings | Branch | Due day, late fine, bank details and printed text |
| fees | PaymentChannel | Network or branch | Payment options printed on the back of the voucher |
| fees | VoucherCounter | Network | One voucher-number sequence for the whole network |
| fees | Voucher | Branch | The printed bill: months, due date, arrears, payable, late fine, status |
| fees | Charge | Branch | One head for one month; never deleted, only cancelled; one automatic charge per head per month |
| fees | Payment | Branch | Money received; never deleted, only reversed |
| fees | PaymentAllocation | Branch | Which charges a payment paid (oldest first); rebuilt per student |
| fees | Concession | Branch | Special discount with approval |
| hr | Employee | Branch | Staff record; code and machine ID unique per branch; optional link to a login |
| hr | HRSettings | Branch | Duty time, grace, half-day time, working days |
| hr | Holiday | Network or branch | Staff days off |
| hr | LeaveType | Network | Casual, Sick, Other; days per session set by head office |
| hr | LeaveRequest | Branch | Request, approval by someone else, working days counted |
| hr | Punch | Branch | One machine punch; unique per person and moment |
| hr | StaffDay | Branch | One per person per day: first in, last out, status; hand corrections kept |
| parents | ParentAccount | — | One login per parent mobile number; children found through guardian links |
| parents | AccessCode | — | One-time set-up/reset code, hashed, 14 days |
| admissions | Inquiry | Branch | One family's inquiry for one child; status, next follow-up, person responsible; link to the student once admitted |
| admissions | FollowUp | Branch | Calls, messages, visits, notes and status changes on an inquiry's timeline |
| core | AuditEvent | — | Append-only; read-only in admin |

## Isolation rules

1. Every branch-owned table has `branch_id` (indexed).
2. Code reads branch data only through `Model.objects.for_user(user)`; admin screens use `ScopedAdminMixin`.
3. Cross-branch links are rejected (enrolment ↔ section, guardian ↔ student).
4. PostgreSQL row-level security as a second lock on every branch-owned table (DECISIONS D-006, D-028).

## Rules carried from the master plan

- A student is stored once; each session adds an Enrolment.
- Official records are corrected, not silently overwritten; every change is in the audit log.
- Money is stored as exact decimals (12 digits, 2 decimals), never floating point.
