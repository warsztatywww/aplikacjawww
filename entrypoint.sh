#!/bin/sh

echo "Collecting static files"
rm -rf /usr/src/static/*
python manage.py collectstatic

echo "Waiting for postgres..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL started"
python manage.py migrate

exec "$@"