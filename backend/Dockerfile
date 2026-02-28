FROM python:3.11-slim

ARG INSTALL_LOCAL_ML=false
ARG INSTALL_OPTIONAL_LLM_FALLBACKS=false

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv

COPY requirements-runtime.txt requirements-optional-llm.txt requirements-local-ml.txt ./

RUN pip install --upgrade pip && \
    pip install --prefer-binary -r requirements-runtime.txt && \
    if [ "$INSTALL_OPTIONAL_LLM_FALLBACKS" = "true" ]; then pip install --prefer-binary -r requirements-optional-llm.txt; fi && \
    if [ "$INSTALL_LOCAL_ML" = "true" ]; then pip install --prefer-binary -r requirements-local-ml.txt; fi

COPY . .

RUN mkdir -p /app/staticfiles /app/media /app/logs /app/ml_models && \
    adduser --disabled-password --gecos "" appuser && \
    chmod +x /app/docker-entrypoint.sh && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn car_diagnosis_system.wsgi:application --bind 0.0.0.0:8000 --workers 4"]
