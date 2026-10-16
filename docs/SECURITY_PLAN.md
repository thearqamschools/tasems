# Security plan

| Control | Status |
| --- | --- |
| Secrets only from environment variables / `.env` (never committed) | Done |
| Password rules: 10+ characters, common and numeric-only passwords rejected | Done |
| Role × scope authorisation; branch isolation in application code | Done (tested) |
| Audit log of changes, logins and failed logins; passwords excluded | Done (tested) |
| Secure cookies, no-sniff, clickjacking protection, HTTPS redirect and HSTS switchable per environment | Done (enable in production) |
| Two-factor login for privileged roles (`requires_mfa`) | Milestone 1b |
| Login rate limiting / lockout | Milestone 1b |
| PostgreSQL row-level security | Before Gate 2 |
| Encrypted backups, tested restores | Before pilot |
| Independent penetration test | Before pilot and before national rollout |

## Rules for everyone on the project

- Never paste passwords, API keys or the old system's credentials into chat, code or documents.
- Old-system data is shared as an export or through a read-only account created by IT.
- No real student data on developer laptops; use the seed command and test data.
- Pakistan has no enacted comprehensive data protection law yet; TASEMS is designed to the draft Personal Data Protection Bill standard (parental consent, breach notification, data kept in Pakistan where required). Verify with legal counsel before the pilot.
