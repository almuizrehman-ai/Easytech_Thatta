"""
Production settings for EASYTECH THATTA.

Usage:
    Set environment variable:
        DJANGO_SETTINGS_MODULE=config.settings_production

Loads base settings, then overrides production-critical values.

Never DEBUG=True here.
Never commit secrets — read from environment.
"""
from decouple import Csv, config

from .settings import *  # noqa: F401, F403  (base settings)


# ============================================================
# CORE — MANDATORY OVERRIDES
# ============================================================
DEBUG = False  # hard-coded — never override via env in prod

# No default — MUST be set in environment or app crashes (fail-fast)
SECRET_KEY = config('SECRET_KEY')

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='',
    cast=Csv(),
)

# CSRF trusted origins (full URLs with scheme)
CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='',
    cast=Csv(),
)


# ============================================================
# HTTPS / TLS HARDENING
# ============================================================
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# HSTS — 1 year, include subdomains, preloadable
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 8 * 60 * 60  # 8 hours (shorter in prod)

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # JS needs to read the token
CSRF_COOKIE_SAMESITE = 'Lax'

# Content security
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True  # legacy but harmless
X_FRAME_OPTIONS = 'DENY'
REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Permissions policy (modern header)
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'


# ============================================================
# SECRET CONFIGURATION
# ============================================================
# Database — MUST be MySQL in production
DB_ENGINE = config('DB_ENGINE', default='mysql')
if DB_ENGINE != 'mysql':
    raise RuntimeError(
        "Production requires DB_ENGINE=mysql. "
        f"Got: {DB_ENGINE}. SQLite is for development only."
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
        'ATOMIC_REQUESTS': True,  # wrap each request in a transaction
    }
}


# ============================================================
# STATIC FILES — via WhiteNoise
# ============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # <-- add
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom rate limiting middleware
    'config.middleware.rate_limit.RateLimitMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ============================================================
# MEDIA FILES
# ============================================================
# In production, media should be served by Nginx (not Django)
# MEDIA_URL and MEDIA_ROOT stay the same; Nginx config guides this.


# ============================================================
# CACHING
# ============================================================
# Default to local memory — swap to Redis for multi-worker setups
CACHES = {
    'default': {
        'BACKEND': config(
            'CACHE_BACKEND',
            default='django.core.cache.backends.locmem.LocMemCache',
        ),
        'LOCATION': config('CACHE_LOCATION', default='easystech-cache'),
    }
}

# For Redis (uncomment and install django-redis):
# CACHES['default'] = {
#     'BACKEND': 'django_redis.cache.RedisCache',
#     'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/0'),
#     'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
# }


# ============================================================
# SESSIONS
# ============================================================
# Default session backend is DB — fine for single-server.
# For multi-server, use cached_db (requires Redis or Memcached).


# ============================================================
# PASSWORD VALIDATION (STRICT)
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12},  # 12 in prod
    },
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ============================================================
# LOGGING
# ============================================================
import os

LOG_DIR = os.environ.get('LOG_DIR', '/var/log/easystech')
# Fallback for dev testing of prod settings
if not os.path.isdir(LOG_DIR):
    LOG_DIR = os.path.join(BASE_DIR, 'logs')  # noqa: F405
    os.makedirs(LOG_DIR, exist_ok=True)


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name} :: {message}',
            'style': '{',
        },
        'json': {
            'format': '{{"time":"{asctime}","level":"{levelname}","logger":"{name}","msg":"{message}"}}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'app_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'app.log'),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOG_DIR, 'error.log'),
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 10,
            'formatter': 'verbose',
            'level': 'ERROR',
        },
    },
    'root': {
        'handlers': ['console', 'app_file'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['error_file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['error_file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'audit': {
            'handlers': ['app_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# ============================================================
# EMAIL (for error notifications)
# ============================================================
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.console.EmailBackend',
)
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@easystech.pk')

# Admin error emails
ADMINS = [
    (config('ADMIN_NAME', default='EASYTECH Admin'),
     config('ADMIN_EMAIL', default='admin@easystech.pk')),
]
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Only send email on 500 errors when configured
if EMAIL_HOST:
    ADMINS = ADMINS


# ============================================================
# SENTRY (OPTIONAL — error monitoring)
# ============================================================
SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False,
            environment=config('SENTRY_ENV', default='production'),
        )
    except ImportError:
        # Sentry optional — silently skip
        pass


# ============================================================
# ADMIN URL OBSCURING (SECURITY THROUGH OBSCURITY + REAL SECURITY)
# ============================================================
# Move /admin/ to a less-guessable path.
# In production, set env ADMIN_URL=something-secret/
ADMIN_URL = config('ADMIN_URL', default='admin/')
if not ADMIN_URL.endswith('/'):
    ADMIN_URL += '/'


# ============================================================
# FILE UPLOAD LIMITS
# ============================================================
FILE_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024  # 3 MB (stricter than dev)
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024


# ============================================================
# TIMEZONE
# ============================================================
# Keep Asia/Karachi
TIME_ZONE = 'Asia/Karachi'
USE_TZ = True


# ============================================================
# RATE LIMITING (see config/middleware/rate_limit.py)
# ============================================================
# Custom middleware — see File 2 below.
RATE_LIMIT_LOGIN_ATTEMPTS = 5        # per IP
RATE_LIMIT_LOGIN_WINDOW_SECONDS = 300  # 5 minutes
RATE_LIMIT_WINDOW_SECONDS = 60         # default window for other actions