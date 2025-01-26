#!/bin/bash

# Wait for postgres to be ready
echo "Waiting for postgres..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "PostgreSQL started"

# Make migrations and migrate
python manage.py makemigrations
python manage.py migrate

# Start server
exec "$@"