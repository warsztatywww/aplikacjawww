import os
import datetime

from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve(strict=True).parent.parent

# E-mail settings

ADMINS = (('Sebastian Jaszczur', 'sebastian.jaszczur+aplikacjawww@gmail.com'),
          ('Marcin Wrochna', 'mwrochna+django@gmail.com'),
          ('Michał Zieliński', 'michal@zielinscy.org.pl'),
          ('Artur Puzio', 'wwwdjango@puzio.waw.pl'),
          ('Krzysztof Haładyn', 'krzys_h@interia.pl'),
          )

MANAGERS = ADMINS

# Application definition

INSTALLED_APPS = (
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'social_django',
    'crispy_forms',
    'phonenumber_field',
    'django_select2',
    'adminsortable2',
    'django_bleach',
    'tinymce',
    'wwwforms',
    'wwwapp',
    'django_cleanup',
    'imagekit',
    'gallery',
)

SOCIAL_AUTH_JSONFIELD_ENABLED = True


MIDDLEWARE = (
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'wwwapp.auth.CustomSocialAuthExceptionMiddleware',
    'wwwapp.models.cache_latest_camp_middleware',
)

ROOT_URLCONF = 'wwwapp.urls'

WSGI_APPLICATION = 'wwwapp.wsgi.application'

# Set cripsy forms template pack
CRISPY_TEMPLATE_PACK = 'bootstrap4'
SELECT2_BOOTSTRAP = True

# Which HTML tags are allowed
BLEACH_ALLOWED_TAGS = [
    'p', 'b', 'i', 'u', 'em', 'strong', 'a', 'pre', 'div', 'strong', 'sup', 'sub', 'ol', 'ul', 'li', 'address',
    'span', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'code', 'table', 'tbody', 'tr', 'td', 'hr', 'img',
    'br',
]

# Which HTML attributes are allowed
BLEACH_ALLOWED_ATTRIBUTES = [
    'href', 'title', 'style', 'alt', 'src', 'dir', 'class', 'border', 'cellpadding', 'cellspacing', 'id',
    'name', 'align', 'width', 'height', 'target', 'rel',
]

# Which CSS properties are allowed in 'style' attributes (assuming
# style is an allowed attribute)
BLEACH_ALLOWED_STYLES = [
    'font-family', 'font-weight', 'text-decoration', 'font-variant', 'float',
    'height', 'width', 'min-height', 'min-width', 'max-height', 'max-width',
    'margin', 'margin-top', 'margin-bottom', 'margin-right', 'margin-left',
    'padding', 'padding-top', 'padding-bottom', 'padding-left', 'padding-right',
    'text-align', 'title', 'page-break-after', 'display', 'color', 'background-color',
    'font-size', 'line-height', 'border-collapse', 'border-spacing', 'empty-cells', 'border',
    'list-style-type',
]

# Strip unknown tags if True, replace with HTML escaped characters if
# False
BLEACH_STRIP_TAGS = True

# Strip comments, or leave them in.
BLEACH_STRIP_COMMENTS = False

# Logging and authentication

LOGIN_URL = '/accounts/login/'

LOGIN_REDIRECT_URL = '/me/status/'

LOGIN_ERROR_URL = '/accounts/login/'

AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.ModelBackend',
                           'social_core.backends.google.GoogleOAuth2',
                           'social_core.backends.facebook.FacebookOAuth2']

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'social_core.pipeline.user.get_username',
    'wwwapp.auth.merge_accounts',
    'social_core.pipeline.user.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    # We do not want any fields to auto update
    # 'social_core.pipeline.user.user_details',
)

SOCIAL_AUTH_USER_FIELDS = ['email', 'first_name', 'last_name', 'username']

SOCIAL_AUTH_GOOGLE_OAUTH2_USE_UNIQUE_USER_ID = True
SOCIAL_AUTH_GOOGLE_OAUTH2_SCOPE = ['openid', 'profile', 'email']
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY')
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET')

SOCIAL_AUTH_FACEBOOK_SCOPE = ['public_profile', 'email']
SOCIAL_AUTH_FACEBOOK_PROFILE_EXTRA_PARAMS = {
    'locale': 'pl_PL',
    'fields': 'id, name, first_name, last_name, email',
}
SOCIAL_AUTH_FACEBOOK_KEY = os.getenv('SOCIAL_AUTH_FACEBOOK_KEY')
SOCIAL_AUTH_FACEBOOK_SECRET = os.getenv('SOCIAL_AUTH_FACEBOOK_SECRET')

# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = 'pl'

TIME_ZONE = 'Europe/Warsaw'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Default primary key field type
# https://docs.djangoproject.com/en/3.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.2/howto/static-files/
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
    os.path.join(BASE_DIR, 'static'),
)
STATIC_ROOT = os.path.join(BASE_DIR, os.pardir, 'static')
STATIC_URL = '/static/'

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

MEDIA_URL = '/media/'
SENDFILE_URL = '/uploads/'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.request',
                'django.template.context_processors.debug',
                'django.template.context_processors.media',
                'django.template.context_processors.i18n',
                'django.template.context_processors.static',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect',
                'wwwapp.views.get_context',
            ],
        },
    },
]

SELECT2_JS = ''
SELECT2_CSS = ''

TINYMCE_JS_URL = os.path.join(STATIC_URL, "dist/tinymce.js")
TINYMCE_JS_ROOT = None
TINYMCE_DEFAULT_CONFIG = {
    'language': 'pl',
    'theme': 'silver',
    'plugins': 'preview paste searchreplace autolink code visualblocks visualchars image link media codesample table charmap hr nonbreaking anchor toc advlist lists wordcount textpattern emoticons autosave',
    'removed_menuitems': 'newdocument',
    'toolbar': 'undo redo | bold italic underline strikethrough | fontselect fontsizeselect formatselect | alignleft aligncenter alignright alignjustify | outdent indent | numlist bullist | link',
    'content_style': 'body { margin: 2rem; }',
    'height': 500,
    'branding': False,
    'image_advtab': True,
    'paste_data_images': False,
    'relative_urls': False,
    'remove_script_host': True,
    'link_list': '/articleNameList/',
    'valid_elements': '@[%s],%s' % ('|'.join(BLEACH_ALLOWED_ATTRIBUTES), ','.join(BLEACH_ALLOWED_TAGS)),
    'valid_styles': {'*': ','.join(BLEACH_ALLOWED_STYLES)},
}
TINYMCE_DEFAULT_CONFIG_WITH_IMAGES = {  # Additional settings for editors where image upload is allowed
    'plugins': 'preview paste searchreplace autolink code visualblocks visualchars image link media codesample table charmap hr nonbreaking anchor toc advlist lists wordcount imagetools textpattern quickbars emoticons autosave',
    'toolbar': 'undo redo | bold italic underline strikethrough | fontselect fontsizeselect formatselect | alignleft aligncenter alignright alignjustify | outdent indent | numlist bullist | image media link codesample',
    'paste_data_images': True,
    'file_picker_types': 'image',
    'file_picker_callback': 'tinymce_local_file_picker',
}

INTERNAL_IPS = [
    '127.0.0.1',
]

# Max amount of points that a participant can get during qualification (relative to configured max_points for a given workshop)
# This allows to give some people bonus points above 100%
MAX_POINTS_PERCENT = 200

GALLERY_LOGO_PATH = 'images/logo_transparent.png'
GALLERY_TITLE = 'Galeria WWW'
GALLERY_FOOTER_INFO = 'Wakacyjne Warsztaty Wielodyscyplinarne'
GALLERY_FOOTER_EMAIL = ''

X_FRAME_OPTIONS = 'DENY'

PHONENUMBER_DEFAULT_REGION = 'PL'
