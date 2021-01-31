from aplikacjawww_djangocms.settings_common import *

SECRET_KEY = ')_7av^!cy(wfx=k#3*7x+(=j^fzv+ot^1@sh9s9t=8$bu@r(z$'

DEBUG = True
TEMPLATES[0]['OPTIONS']['debug'] = DEBUG
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

INSTALLED_APPS = INSTALLED_APPS + ['debug_toolbar']

MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE

GOOGLE_ANALYTICS_KEY = None
