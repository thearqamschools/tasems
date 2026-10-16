#!/bin/sh
# Restore drill: proves a backup can actually be restored. Run at least once a term.
# Restores into a separate database (tasems_restore_check) and compares row counts.
# Usage: ./deploy/restore_drill.sh /var/backups/tasems/tasems_2026-10-16_0215.dump.enc
set -eu
. ./.env.prod
FILE="$1"
DC="docker compose -f docker-compose.prod.yml --env-file .env.prod"

$DC exec -T db psql -U postgres -c "DROP DATABASE IF EXISTS tasems_restore_check;" -c "CREATE DATABASE tasems_restore_check;"
openssl enc -d -aes-256-cbc -pbkdf2 -pass "file:$BACKUP_PASSPHRASE_FILE" -in "$FILE" \
  | $DC exec -T db pg_restore -U postgres --no-owner -d tasems_restore_check

for t in people_student attendance_attendancerecord diary_diary core_auditevent; do
  live=$($DC exec -T db psql -U postgres -d tasems -tAc "SELECT count(*) FROM $t")
  restored=$($DC exec -T db psql -U postgres -d tasems_restore_check -tAc "SELECT count(*) FROM $t")
  echo "$t: live=$live restored=$restored"
done
$DC exec -T db psql -U postgres -c "DROP DATABASE tasems_restore_check;"
echo "Restore drill finished. Counts can differ only by changes made since the backup."
