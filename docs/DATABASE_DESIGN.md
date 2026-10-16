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
| core | AuditEvent | — | Append-only; read-only in admin |

## Isolation rules

1. Every branch-owned table has `branch_id` (indexed).
2. Code reads branch data only through `Model.objects.for_user(user)`; admin screens use `ScopedAdminMixin`.
3. Cross-branch links are rejected (enrolment ↔ section, guardian ↔ student).
4. Planned: PostgreSQL row-level security as a second lock (DECISIONS D-006).

## Rules carried from the master plan

- A student is stored once; each session adds an Enrolment.
- Official records are corrected, not silently overwritten; every change is in the audit log.
- Money (from the Fees module) will be stored as exact decimals, never floating point.
