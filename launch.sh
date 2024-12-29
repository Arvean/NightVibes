#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Function to display usage information
usage() {
  echo "Usage: $0 {start|stop|restart|status|prune}"
  echo ""
  echo "Commands:"
  echo "  start     Build images, start services, apply migrations, and create superuser"
  echo "  stop      Stop all running services"
  echo "  restart   Stop and then start services"
  echo "  status    Show status of services"
  echo "  prune     Remove unused Docker data"
  echo ""
  exit 1
}

# Function to start services
start_services() {
  echo "Building Docker images..."
  docker-compose build

  echo "Starting services in detached mode..."
  docker-compose up -d

  echo "Waiting for services to be ready..."
  # Optional: Wait for the database to be ready
  sleep 10

  echo "Applying Django migrations..."
  docker-compose exec web python manage.py migrate

  echo "Creating Django superuser (if not exists)..."
  # Check if superuser exists before creating
  SUPERUSER_EXISTS=$(docker-compose exec web python manage.py shell -c "from django.contrib.auth import get_user_model; print(get_user_model().objects.filter(is_superuser=True).exists())" | tr -d '\r\n')
  
  if [ "$SUPERUSER_EXISTS" = "False" ]; then
    docker-compose exec web python manage.py createsuperuser
  else
    echo "Superuser already exists. Skipping creation."
  fi

  echo "Services started successfully."
}

# Function to stop services
stop_services() {
  echo "Stopping services..."
  docker-compose down

  echo "Services stopped."
}

# Function to restart services
restart_services() {
  stop_services
  start_services
}

# Function to show status of services
status_services() {
  docker-compose ps
}

# Function to prune unused Docker data
prune_docker() {
  echo "Pruning unused Docker data..."
  docker system prune -f
  echo "Pruning completed."
}

# Check if at least one argument is provided
if [ $# -lt 1 ]; then
  usage
fi

# Handle commands
case "$1" in
  start)
    start_services
    ;;
  
  stop)
    stop_services
    ;;
  
  restart)
    restart_services
    ;;
  
  status)
    status_services
    ;;
  
  prune)
    prune_docker
    ;;
  
  *)
    echo "Invalid command: $1"
    usage
    ;;
esac
