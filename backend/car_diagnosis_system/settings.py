"""
Django settings for Car Diagnosis System.
This configuration uses environment variables for security.
"""
import os
from pathlib import Path
import environ

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Read .env file
environ.Env.read_env(os.path.join(BASE_DIR.parent, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
DEFAULT_INSECURE_SECRET_KEY = 'django-insecure-change-this-in-production'
SECRET_KEY = env('SECRET_KEY', default=DEFAULT_INSECURE_SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG', default=False)

IS_PRODUCTION = not DEBUG
PUBLIC_FRONTEND_API_ENABLED = env.bool('PUBLIC_FRONTEND_API_ENABLED', default=True)
ALLOWED_HOSTS = env.list(
    'ALLOWED_HOSTS',
    default=['localhost', '127.0.0.1'] if DEBUG else []
)
if IS_PRODUCTION:
    if SECRET_KEY == DEFAULT_INSECURE_SECRET_KEY:
        raise ValueError("A strong SECRET_KEY must be configured in production.")
    if not ALLOWED_HOSTS:
        raise ValueError("ALLOWED_HOSTS must be explicitly configured in production.")
    if '*' in ALLOWED_HOSTS:
        raise ValueError("Wildcard ALLOWED_HOSTS is not permitted in production.")

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'drf_yasg',

    # Local apps
    'apps.customers',
    'apps.cars',
    'apps.complaints',
    'apps.chat',
    'apps.ml_models',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'car_diagnosis_system.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'car_diagnosis_system.wsgi.application'

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', default='car_diagnosis_db'),
        'USER': env('DB_USER', default='postgres'),
        'PASSWORD': env('DB_PASSWORD', default='postgres'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Cairo'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# STATICFILES_DIRS = []  # Not needed for this project structure

# Media files (User uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny'
        if DEBUG else
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# CORS Settings
CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=(
    ['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:3000', 'http://127.0.0.1:3000']
    if DEBUG else []
))
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = False
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# Security Headers / Cookie Hardening
SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=IS_PRODUCTION)
CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=IS_PRODUCTION)
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=IS_PRODUCTION)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000 if IS_PRODUCTION else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', default=IS_PRODUCTION)
SECURE_HSTS_PRELOAD = env.bool('SECURE_HSTS_PRELOAD', default=False)

# Celery Configuration
CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# ML Model Settings
ML_MODEL_PATH = BASE_DIR / 'ml_models'
BERT_TOKENIZER_PATH = BASE_DIR / 'ml_models' / 'bert_tokenizer'
LABEL_ENCODER_PATH = BASE_DIR / 'ml_models' / 'label_encoder.pkl'
TRAINED_MODEL_PATH = BASE_DIR / 'ml_models' / 'the_model.h5'

# Multi-modal RAG Settings
RAG_DATA_STATIC_DIR = Path(env('RAG_DATA_STATIC_DIR', default=str(BASE_DIR.parent / 'data' / 'static')))
RAG_DATA_UPLOADS_DIR = Path(env('RAG_DATA_UPLOADS_DIR', default=str(BASE_DIR.parent / 'data' / 'uploads')))
RAG_COMPLAINT_DOCS_DIR = Path(env('RAG_COMPLAINT_DOCS_DIR', default=str(MEDIA_ROOT / 'complaint_docs')))
RAG_EXTRACTED_IMAGES_DIR = Path(env('RAG_EXTRACTED_IMAGES_DIR', default=str(BASE_DIR.parent / 'data' / 'extracted_images')))
RAG_DATA_DIR = Path(env('RAG_DATA_DIR', default=str(BASE_DIR.parent / 'rag data')))  # Existing car manuals
RAG_FAISS_DB_DIR = Path(env('RAG_FAISS_DB_DIR', default=str(BASE_DIR / 'faiss_db')))
RAG_USE_VISION_ON_INDEX = env.bool('RAG_USE_VISION_ON_INDEX', default=False)
RAG_MAX_IMAGES_PER_DOCUMENT = env.int('RAG_MAX_IMAGES_PER_DOCUMENT', default=80)
RAG_RETRIEVAL_TIMEOUT_SECONDS = env.float('RAG_RETRIEVAL_TIMEOUT_SECONDS', default=20.0)

# Embedding Models (free, local)
TEXT_EMBEDDING_BACKEND = env('TEXT_EMBEDDING_BACKEND', default='cohere')
TEXT_EMBEDDING_MODEL = env('TEXT_EMBEDDING_MODEL', default='embed-v4.0')
TEXT_EMBEDDING_DIMENSION = env.int('TEXT_EMBEDDING_DIMENSION', default=512)
ENABLE_LOCAL_TEXT_EMBEDDINGS = env.bool('ENABLE_LOCAL_TEXT_EMBEDDINGS', default=False)
LOCAL_TEXT_EMBEDDING_MODEL = env('LOCAL_TEXT_EMBEDDING_MODEL', default='all-MiniLM-L6-v2')

# Lightweight classifier defaults to Cohere/keyword fallback unless explicitly enabled.
ENABLE_LOCAL_CLASSIFIER = env.bool('ENABLE_LOCAL_CLASSIFIER', default=False)

# Multi-modal LLM (Ollama - free, local)
OLLAMA_BASE_URL = env('OLLAMA_BASE_URL', default='http://host.docker.internal:11434')
OLLAMA_TEXT_MODEL = env('OLLAMA_TEXT_MODEL', default='gpt-oss:120b-cloud')
LLM_PROVIDER_STRATEGY = env(
    'LLM_PROVIDER_STRATEGY',
    default='local_first' if DEBUG else 'cohere_first',
).lower()
if LLM_PROVIDER_STRATEGY not in {'local_first', 'cohere_first'}:
    LLM_PROVIDER_STRATEGY = 'local_first' if DEBUG else 'cohere_first'

# AI API Keys for LangChain
OPENAI_API_KEY = env('OPENAI_API_KEY', default='')
GROQ_API_KEY = env('GROQ_API_KEY', default='')
USE_GROQ = env.bool('USE_GROQ', default=False)

# Cohere (Primary for command/vision)
USE_COHERE = env.bool('USE_COHERE', default=True)
COHERE_API_KEY = env('COHERE_API_KEY', default='')
COHERE_COMMAND_MODEL = env('COHERE_COMMAND_MODEL', default='command-a-03-2025')
COHERE_COMMAND_FALLBACK_MODELS = env.list(
    'COHERE_COMMAND_FALLBACK_MODELS',
    default=['command-a-03-2025', 'command-r-08-2024', 'command-r7b-12-2024']
)
COHERE_VISION_MODEL = env('COHERE_VISION_MODEL', default='command-a-vision-07-2025')
COHERE_EMBED_MODEL = env('COHERE_EMBED_MODEL', default='embed-v4.0')
COHERE_EMBED_OUTPUT_DIMENSION = env.int('COHERE_EMBED_OUTPUT_DIMENSION', default=TEXT_EMBEDDING_DIMENSION)
COHERE_EMBED_INPUT_TYPE_DOCUMENT = env('COHERE_EMBED_INPUT_TYPE_DOCUMENT', default='search_document')
COHERE_EMBED_INPUT_TYPE_QUERY = env('COHERE_EMBED_INPUT_TYPE_QUERY', default='search_query')
COHERE_TEMPERATURE = env.float('COHERE_TEMPERATURE', default=0.3)
COHERE_MAX_TOKENS = env.int('COHERE_MAX_TOKENS', default=1024)
COHERE_IMAGE_CHAT_ENABLED = env.bool('COHERE_IMAGE_CHAT_ENABLED', default=USE_COHERE)
COHERE_IMAGE_SCOPE = env('COHERE_IMAGE_SCOPE', default='general').lower()
if COHERE_IMAGE_SCOPE not in {'general', 'car_only', 'mixed_auto_bias'}:
    COHERE_IMAGE_SCOPE = 'general'
COHERE_IMAGE_MAX_IMAGES_PER_MESSAGE = env.int('COHERE_IMAGE_MAX_IMAGES_PER_MESSAGE', default=3)

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)
