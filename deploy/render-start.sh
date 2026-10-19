#!/bin/sh
# Start command for the Render.com demo server (render.yaml). Fictional data only (docs/DEMO.md).
# A script rather than an inline `sh -c "..."`: Render passes dockerCommand without shell quoting.
set -e
python manage.py migrate --noinput
python manage.py seed_demo
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 2 --timeout 90
