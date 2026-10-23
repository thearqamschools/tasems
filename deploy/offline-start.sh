#!/bin/sh
# Start command for the offline test copy on an office computer (docker-compose.offline.yml,
# docs/OFFLINE_INSTALL.md). Keys are made once on that computer and kept with its data.
set -e
KEYS="${MEDIA_ROOT:-/app/media}/.offline-keys.env"
if [ ! -f "$KEYS" ]; then
  python - > "$KEYS" <<'PY'
import base64, os, secrets
print(f"export SECRET_KEY='{secrets.token_urlsafe(50)}'")
print(f"export FIELD_ENCRYPTION_KEY='{base64.urlsafe_b64encode(os.urandom(32)).decode()}'")
PY
  chmod 600 "$KEYS"
fi
. "$KEYS"
python manage.py migrate --noinput
python manage.py seed_tasems
if [ "$DEMO_MODE" = "True" ]; then
  python manage.py seed_demo || echo "Demo data not loaded (see the message above)."
fi
python manage.py run_jobs &
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 90
