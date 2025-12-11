# Backend Dockerfile for Django Car Diagnosis System

FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    python3-dev \
    musl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt


# Copy project
COPY . .

# Create necessary directories
RUN mkdir -p /app/staticfiles /app/media /app/logs /app/ml_models

# Collect static files (will be overridden in docker-compose command)
# RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run migrations and start server
CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn car_diagnosis_system.wsgi:application --bind 0.0.0.0:8000 --workers 4"]
