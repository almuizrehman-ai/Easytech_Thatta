"""
Django settings for EASYTECH THATTA Institute Management System.
"""
from pathlib import Path
from decouple import Csv, config

# ============================================================
# BASE PATHS
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# SECURITY
# ============================================================
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-dev-key-do-not-use-in-production',
)
DEBUG = config('DEBUG', default=False, cast=bool) # Production mein default False

ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='*', # Railway ke liye '*' best hai jab tak custom domain na ho
    cast=Csv(),
)

CSRF_TRUSTED_ORIGINS = config(
    'CSRF_TRUSTED_ORIGINS',
    default='http://127.0.0.1,http://localhost,https://*.railway.app',
    cast=Csv(),
)

# Production Security Headers
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)
    SESSION_COOKIE_SECURE = config('SESSION_COOKIE_SECURE', default=True, cast=bool)
    CSRF_COOKIE_SECURE = config('CSRF_COOKIE_SECURE', default=True, cast=bool)
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ============================================================
# APPLICATIONS
# ============================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party
    'whitenoise.runserver_nostatic', # WhiteNoise dev server ke liye

    # Local applications
    'accounts',
    'dashboard',
    'courses',
    'batches',
    'students',
    'fees',
    'audit',
    'reports',
    'staff',
]

# ============================================================
# MIDDLEWARE
# ============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # WhiteNoise production ke liye
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ============================================================
# URLS / WSGI / ASGI
# ============================================================
ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ============================================================
# TEMPLATES
# ============================================================
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
            'builtins': [],
        },
    },
]

# ============================================================
# DATABASE
# ============================================================
DB_ENGINE = config('DB_ENGINE', default='sqlite').strip().lower()

if DB_ENGINE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': config('DB_NAME', default='easystech_db'),
            'USER': config('DB_USER', default='root'),
            'PASSWORD': config('DB_PASSWORD', default=''),
            'HOST': config('DB_HOST', default='127.0.0.1'),
            'PORT': config('DB_PORT', default='3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            'CONN_MAX_AGE': 60,
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 20,
            },
        }
    }

# ============================================================
# AUTHENTICATION & AUTHORIZATION
# ============================================================
AUTH_USER_MODEL = 'accounts.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:redirect_after_login'
LOGOUT_REDIRECT_URL = 'accounts:login'

# ============================================================
# INTERNATIONALIZATION
# ============================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Karachi'
USE_I18N = True
USE_TZ = True

# ============================================================
# STATIC & MEDIA
# ============================================================
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise production configuration
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ============================================================
# MESSAGES -> BOOTSTRAP ALERT CLASSES
# ============================================================
from django.contrib.messages import constants as message_constants

MESSAGE_TAGS = {
    message_constants.DEBUG: 'secondary',
    message_constants.INFO: 'info',
    message_constants.SUCCESS: 'success',
    message_constants.WARNING: 'warning',
    message_constants.ERROR: 'danger',
}

# ============================================================
# LOGGING
# ============================================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '[{levelname}] {asctime} {name} :: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# ============================================================
# MISC
# ============================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DEFAULT_CURRENCY = 'PKR'
DEFAULT_CURRENCY_SYMBOL = 'Rs.'
