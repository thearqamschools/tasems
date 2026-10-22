# Deployment guide — Samanabad pilot

This sets up TASEMS on one Linux server with HTTPS, a protected database, nightly encrypted backups and uptime monitoring. Nothing here has been run on a real server yet; do it first on a test server.

## 1. Server

| Item | Pilot (Samanabad campus) | Notes |
| --- | --- | --- |
| Machine | 2 vCPU, 4 GB RAM, 80 GB SSD, Ubuntu 24.04 LTS | Grow when more branches join |
| Location | Hosting provider chosen by the project lead | Prefer a provider that can keep data in Pakistan (master plan Part 5) |
| Domain | e.g. `tasems.thearqam.com` | A DNS record pointing to the server's IP |
| Software | Docker Engine with the Compose plugin | Nothing else is installed on the host |

### Background worker (M6, D-074)
Large PDFs (more than 100 vouchers at once) are made by `python manage.py run_jobs`, which must run next to the
web server from the same image and database. On the Render demo `deploy/render-start.sh` starts it. On any
other server run it as a second always-on process (systemd service or a second container with the command
`python manage.py run_jobs`). Without it, large print requests wait in "My print jobs" and are made as soon as
the worker starts. Finished files are removed after 7 days.

## 2. First installation

```bash
git clone https://github.com/thearqamschools/tasems /opt/tasems
cd /opt/tasems
cp deploy/env.prod.example .env.prod
nano .env.prod          # fill in every value; generate long random passwords
chmod 600 .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

On first start the database creates an **ordinary** role `tasems_app` (not a superuser), the app runs migrations and loads the starting data, and Caddy obtains the HTTPS certificate automatically.

Create the first head-office account and check security:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py createsuperuser
docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py check_security --strict
```

`check_security` must say **Security check passed**. If it reports a superuser connection, row-level security is not protecting branch data — fix that before entering real data.

The superuser signs in at `https://<domain>/` and must set up two-step sign-in with an authenticator app. Then, under Setup: set the current academic session, upload the official logos (Setup → Diary layouts), create staff accounts and give each a role.

## 3. Updates

```bash
cd /opt/tasems
./deploy/backup.sh                       # always back up first
git pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

Migrations run automatically on start. Roll back by checking out the previous version and restoring the backup taken just before.

## 4. Backups

1. Create the passphrase file once and keep a copy somewhere safe off the server (a printed copy in the head office safe is fine): `openssl rand -base64 48 > /root/tasems-backup-passphrase && chmod 600 /root/tasems-backup-passphrase`
2. Schedule the nightly backup: `crontab -e` → `15 2 * * * cd /opt/tasems && ./deploy/backup.sh >> /var/log/tasems-backup.log 2>&1`
3. Copy `/var/backups/tasems` off the server every night (a second provider's object storage or a head-office machine). A backup kept only on the same server is lost with the server.
4. Run a restore drill at least once a term: `./deploy/restore_drill.sh /var/backups/tasems/<file>.dump.enc`. It restores into a separate database and compares row counts. Record the result in DEVELOPMENT_PROGRESS.md.

Nightly dumps lose at most one day of data. The master plan targets 15 minutes: before rollout beyond the pilot, move to a managed PostgreSQL service with point-in-time recovery, or add continuous WAL archiving (pgBackRest).

## 5. Monitoring

- `https://<domain>/healthz` answers `{"status": "ok"}` when the app and database work. Add it to a free uptime service (for example UptimeRobot) that alerts the IT team by SMS or e-mail.
- Logs: `docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f web`

## 6. What is protected how

| Risk | Protection |
| --- | --- |
| Someone reads traffic | HTTPS only (Caddy), HSTS |
| Stolen password | Lockout after 5 failures; two-step sign-in for privileged roles |
| A coding mistake shows another branch's data | Application filters **and** PostgreSQL row-level security |
| Server lost | Encrypted nightly backups copied off the server; tested restores |
| Uploaded Excel files exposed | Never served publicly; deleted after import |
| Secrets leaked from Git | `.env.prod` never committed; secrets only on the server |
