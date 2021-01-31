from aplikacjawww_djangocms.settings_common import *

SECRET_KEY = None  # set in local_settings

DEBUG = False
ALLOWED_HOSTS = ['warsztatywww.pl']

# E-mail settings

EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = None  # set in local_settings
EMAIL_USE_TLS = True
EMAIL_HOST_PASSWORD = None  # set in local_settings

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'aplikacjawww',
        'USER': 'app',
    }
}

GOOGLE_ANALYTICS_KEY = 'UA-12926426-8'

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

MEDIA_ROOT = None  # set in local_settings
SENDFILE_ROOT = None  # set in local_settings
SENDFILE_BACKEND = 'django_sendfile.backends.nginx'

# Append hashes to filenames for better caching
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

try:
    from .local_settings import *
except ModuleNotFoundError:
    import warnings
    warnings.warn("Missing local_settings.py file")
