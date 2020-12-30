from django.core.checks import register, Warning, Error
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import requests


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


@register
def check_email(app_configs, **kwargs):
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        return [Warning(
            "Missing email sender login and/or password",
            hint="Make sure settings EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are set",
            id='wwwapp.W003'
        )]
    return []


@register
def check_media_root(app_configs, **kwargs):
    if not settings.MEDIA_ROOT:
        return [Error(
            "Missing MEDIA_ROOT storage setting",
            hint="Make sure setting MEDIA_ROOT is set",
            id='wwwapp.W004'
        )]

    try:
        path = default_storage.save('check.txt', ContentFile(b'Check'))
    except OSError as e:
        return [Error(
            "Error when trying to write file to media_storage: " + str(e),
            hint="Check if you can write to MEDIA_ROOT AND the path is correct "
                 "(Django will attempt to create non existing directories)",
            id='wwwapp.E008'
        )]

    errors = []
    if not settings.DEBUG:
        for host in settings.ALLOWED_HOSTS:
            url = "https://" + host + settings.MEDIA_URL + 'check.txt'
            try:
                if requests.get(url).text != "Check":
                    errors.append(Warning(
                        "Problem with hosting of media on url " + url,
                        hint="Check if nginx is configured properly to host " + settings.MEDIA_ROOT + " on " + settings.MEDIA_URL,
                        id='wwwapp.W007'
                    ))
            except requests.RequestException:
                errors.append(Warning(
                    "Could not get test media file on url " + url,
                    hint="Check if nginx is configured properly to host " + settings.MEDIA_ROOT + " on " + settings.MEDIA_URL,
                    id='wwwapp.W006'
                ))

    default_storage.delete(path)
    return errors
