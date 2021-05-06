#!/bin/sh

set -o pipefail -o nounset


echo >&2 "Collecting static files."
rm -rf /usr/src/static/*
python3 manage.py collectstatic

echo >&2 "Waiting for postgres..."
while ! nc -z db 5432; do
	sleep 0.1
done
echo >&2 "PostgreSQL started."

echo >&2 "Migrating database."
python3 manage.py migrate

echo >&2 "Creating admin user (username: admin, password: admin)."
export DJANGO_SUPERUSER_EMAIL=admin@admin.admin
export DJANGO_SUPERUSER_PASSWORD=admin \
export DJANGO_SUPERUSER_USERNAME=admin
# This will fail if admin user already exists.
python3 manage.py createsuperuser --noinput || true

exec gunicorn wwwapp.wsgi:application --bind 0.0.0.0:8000
