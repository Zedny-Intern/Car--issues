# Project Setup & Run Commands (English Only)

This file contains the essential commands to set up and run the project from scratch on your local machine.

## Prerequisites
- Ensure **Docker Desktop** is installed and running.
- Open your terminal (PowerShell or CMD) in the project root directory.

## 1. Environment Setup

### Create .env file
```bash
# Copy the example environment file
copy .env.example .env
```
*Note: Open `.env` and add your API keys (GROQ_API_KEY, etc.) if needed.*

### Create Required Directories
Ensure these directories exist to avoid Docker errors:
```bash
# Create frontend static and media directories
mkdir frontend\static
mkdir frontend\media

# Create ML models directory (if not exists)
mkdir backend\apps\ml_models\bert_tokenizer
```
*Important: Ensure `the_model.h5` and `label_encoder.pkl` are placed inside `backend/apps/ml_models/`.*

## 2. Docker Execution

### Build and Start Services
```bash
# Build images and start containers in detached mode
docker-compose up -d --build
```

### Check Status
```bash
# Verify all containers are running
docker-compose ps
```

## 3. Database Setup

### Run Migrations
```bash
# Apply database migrations
docker-compose exec backend python manage.py migrate
```

### Create Admin User (Optional)
```bash
# Create a superuser for the admin panel
docker-compose exec backend python manage.py createsuperuser
```

## 4. Access the Application

- **Frontend**: http://localhost
- **Admin Panel**: http://localhost/admin

## 5. Common Maintenance Commands

### View Logs
```bash
# Follow logs for all services
docker-compose logs -f

# Follow logs for backend only
docker-compose logs -f backend
```

### Restart Backend (after code changes)
```bash
docker-compose restart
```

### Stop System
```bash
# Stop and remove containers
docker-compose down
```
