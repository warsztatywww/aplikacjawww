from .settings_common import *

SECRET_KEY = ')_7av^!cy(wfx=k#3*7x+(=j^fzv+ot^1@sh9s9t=8$bu@r(z$'

DEBUG = True
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

INSTALLED_APPS = INSTALLED_APPS + ('debug_toolbar',)

MIDDLEWARE = ('debug_toolbar.middleware.DebugToolbarMiddleware',) + MIDDLEWARE

ROOT_URLCONF = 'wwwapp.urls'

WSGI_APPLICATION = 'wwwapp.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'database.sqlite3',
    }
}

MEDIA_ROOT = os.path.join(BASE_DIR, *MEDIA_URL.strip("/").split("/"))

GOOGLE_ANALYTICS_KEY = None

if {'SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', 'SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET'} <= os.environ.keys():
    SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ['SOCIAL_AUTH_GOOGLE_OAUTH2_KEY']
    SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ['SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET']
    AUTHENTICATION_BACKENDS.append('social_core.backends.google.GoogleOAuth2')
else:
    logger.warning("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY or SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET not provided. Login via Google will be disabled!")

if {'SOCIAL_AUTH_FACEBOOK_KEY', 'SOCIAL_AUTH_FACEBOOK_SECRET'} <= os.environ.keys():
    SOCIAL_AUTH_FACEBOOK_KEY = os.environ['SOCIAL_AUTH_FACEBOOK_KEY']
    SOCIAL_AUTH_FACEBOOK_SECRET = os.environ['SOCIAL_AUTH_FACEBOOK_SECRET']
    AUTHENTICATION_BACKENDS.append('social_core.backends.facebook.FacebookOAuth2')
else:
    logger.warning("SOCIAL_AUTH_FACEBOOK_KEY or SOCIAL_AUTH_FACEBOOK_SECRET not provided. Login via Facebook will be disabled!")
