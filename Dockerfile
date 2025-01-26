FROM python:3.9-slim

# Set work directory
WORKDIR /app

# Install system dependencies for GeoDjango and netcat
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    netcat-openbsd  \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt /app/

RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy project
COPY . /app/

# Copy and set entrypoint script
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Expose port 8000
EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Command to run
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]