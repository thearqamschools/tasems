# Changelog

## 0.1.0 — 2026-10-16 — Milestone 1a: Foundation

Added
- Django 5.2 project with PostgreSQL, environment-based settings, English/Urdu language setup, Pakistan time zone.
- Organisation: head offices, regions, branches (ownership and royalty %), academic sessions.
- Accounts: custom user, roles, scoped role assignments, role-based permission backend.
- Branch isolation helpers (`for_user`, `has_branch_perm`, scoped admin).
- Academics: class levels, subjects, curriculum mapping, sections.
- People: students, guardians, student–guardian links, enrolments.
- Append-only audit log.
- `seed_tasems` command (confirmed facts only).
- 23 automated tests; GitHub Actions CI (lint, checks, migrations, tests); Dockerfile and docker-compose.

Not deployed.
