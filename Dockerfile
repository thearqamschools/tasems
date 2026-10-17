FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home tasems
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN SECRET_KEY=build-only FIELD_ENCRYPTION_KEY=Y2ktb25seS1ub3Qtc2VjcmV0LWtleS0zMmJ5dGVzISE= DATABASE_URL=postgres://x@localhost/x python manage.py collectstatic --noinput

RUN mkdir -p /app/media && chown -R tasems /app/media
USER tasems
EXPOSE 8000
CMD ["sh", "-c", "gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 60"]
