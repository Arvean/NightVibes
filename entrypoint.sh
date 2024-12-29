#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Make database migrations
echo "Making migrations..."
python3 manage.py makemigrations

# Apply database migrations
echo "Applying migrations..."
python3 manage.py migrate

# Start server
echo "Starting server..."
exec "$@"