#!/bin/sh
# Start command for the Render.com demo server (render.yaml). Fictional data only (docs/DEMO.md).
# A script rather than an inline `sh -c "..."`: Render passes dockerCommand without shell quoting.
set -e
python manage.py migrate --noinput
# seed_demo refuses a database that has non-demo students; the site must still start, so only warn.
python manage.py seed_demo || echo "WARNING: demo data not loaded (see the message above). The site starts anyway."
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}" --workers 2 --timeout 90
