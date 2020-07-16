from django.core.checks import register, Warning, Error
from django.conf import settings
import os


@register
def check_auth(app_configs, **kwargs):
    errors = []
    problem_class = Warning if settings.DEBUG else Error
    if not {'SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', 'SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET'} <= os.environ.keys():
        errors.append(
            problem_class(
                "Google API keys are missing. Login via Google will be disabled!",
                hint="Make sure environment variables SOCIAL_AUTH_GOOGLE_OAUTH2_KEY and SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET are provided.",
                id='wwwapp.W001',
            )
        )

    if not {'SOCIAL_AUTH_FACEBOOK_KEY', 'SOCIAL_AUTH_FACEBOOK_SECRET'} <= os.environ.keys():
        errors.append(
            problem_class(
                "Facebook API keys missing. Login via Facebook will be disabled!",
                hint="Make sure environment variables SOCIAL_AUTH_FACEBOOK_KEY and SOCIAL_AUTH_FACEBOOK_SECRET are provided.",
                id='wwwapp.W002',
            )
        )

    return errors
