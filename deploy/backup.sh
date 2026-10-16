#!/bin/sh
# Nightly encrypted database backup. Schedule with cron, e.g.:
#   15 2 * * * cd /opt/tasems && ./deploy/backup.sh >> /var/log/tasems-backup.log 2>&1
# Keeps 14 daily copies here; copy them off this server too (docs/DEPLOYMENT.md).
set -eu
. ./.env.prod
STAMP=$(date +%Y-%m-%d_%H%M)
mkdir -p "$BACKUP_DIR"
OUT="$BACKUP_DIR/tasems_$STAMP.dump.enc"

docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T db \
  pg_dump -U postgres -Fc tasems \
  | openssl enc -aes-256-cbc -pbkdf2 -salt -pass "file:$BACKUP_PASSPHRASE_FILE" -out "$OUT"

# The media volume holds logos; uploaded imports are temporary and not backed up.
docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T web tar -C /app/media -cf - branding 2>/dev/null \
  | openssl enc -aes-256-cbc -pbkdf2 -salt -pass "file:$BACKUP_PASSPHRASE_FILE" -out "$BACKUP_DIR/media_$STAMP.tar.enc" || true

find "$BACKUP_DIR" -name 'tasems_*.dump.enc' -mtime +14 -delete
find "$BACKUP_DIR" -name 'media_*.tar.enc' -mtime +14 -delete
echo "$(date -Iseconds) backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
