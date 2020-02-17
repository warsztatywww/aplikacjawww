from django.core.checks import register, Warning
from django.conf import settings


@register
def check_auth(app_configs, **kwargs):
    errors = []
    if not settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY or not settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET:
        errors.append(
            Warning(
                "Google API keys are missing. Login via Google will be disabled!",
                hint="Make sure environment variables SOCIAL_AUTH_GOOGLE_OAUTH2_KEY and SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET are provided.",
                id='wwwapp.W001',
            )
        )

    if not settings.SOCIAL_AUTH_FACEBOOK_KEY or not settings.SOCIAL_AUTH_FACEBOOK_SECRET:
        errors.append(
            Warning(
                "Facebook API keys missing. Login via Facebook will be disabled!",
                hint="Make sure environment variables SOCIAL_AUTH_FACEBOOK_KEY and SOCIAL_AUTH_FACEBOOK_SECRET are provided.",
                id='wwwapp.W002',
            )
        )

    return errors
