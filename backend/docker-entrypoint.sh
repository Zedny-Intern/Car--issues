#!/bin/sh
set -eu

STATIC_DIR="${STATIC_ROOT:-/app/staticfiles}"
MEDIA_DIR="${MEDIA_ROOT:-/app/media}"
RAG_STATIC_DIR="${RAG_DATA_STATIC_DIR:-/data/static}"
RAG_UPLOADS_DIR="${RAG_DATA_UPLOADS_DIR:-/data/uploads}"
RAG_EXTRACTED_DIR="${RAG_EXTRACTED_IMAGES_DIR:-/data/extracted_images}"
RAG_FAISS_DIR="${RAG_FAISS_DB_DIR:-/data/faiss_db}"

ensure_dir() {
    mkdir -p "$1"
}

ensure_dir "$STATIC_DIR"
ensure_dir "$MEDIA_DIR"
ensure_dir "$RAG_STATIC_DIR"
ensure_dir "$RAG_UPLOADS_DIR"
ensure_dir "$RAG_EXTRACTED_DIR"
ensure_dir "$RAG_FAISS_DIR"

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

exec sh -c "
python manage.py migrate &&
python manage.py collectstatic --noinput &&
python manage.py prime_runtime --async &&
exec gunicorn car_diagnosis_system.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 300 --graceful-timeout 120
"
