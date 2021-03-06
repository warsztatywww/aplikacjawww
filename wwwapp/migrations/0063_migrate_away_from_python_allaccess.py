# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-03-07 06:29
from __future__ import unicode_literals

from django.db import migrations
from django.conf import settings


def forwards_func(apps, schema_editor):
    try:
        AccountAccess = apps.get_model('allaccess', 'AccountAccess')
        Provider = apps.get_model('allaccess', 'Provider')
        UserSocialAuth = apps.get_model('social_django', 'UserSocialAuth')
    except LookupError:
        # The old app isn't installed.
        return

    for access in AccountAccess.objects.all():
        if access.user is None or access.user == 0:
            print("Skipping null user of %s" % str(access))
            continue
        if access.provider.name == 'facebook':
            UserSocialAuth(provider='facebook', uid=access.identifier, user=access.user, extra_data=access.access_token).save()
        elif access.provider.name == 'google':
            UserSocialAuth(provider='google-oauth2', uid=access.identifier, user=access.user, extra_data=access.access_token).save()
        else:
            raise RuntimeError(f"Got unknown provider: {access.provider.name}! Aborting migration!")
    AccountAccess.objects.all().delete()
    Provider.objects.all().delete()


def reverse_func(apps, schema_editor):
    try:
        AccountAccess = apps.get_model('allaccess', 'AccountAccess')
        Provider = apps.get_model('allaccess', 'Provider')
        UserSocialAuth = apps.get_model('social_django', 'UserSocialAuth')
    except LookupError:
        return

    legacy_google_provider = Provider(
        name="google",
        authorization_url="https://accounts.google.com/o/oauth2/auth",
        access_token_url="https://accounts.google.com/o/oauth2/token",
        profile_url="https://www.googleapis.com/plus/v1/people/me",
        consumer_key=settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
        consumer_secret=settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET)
    legacy_google_provider.save()

    legacy_facebook_provider = Provider(
        name="facebook",
        authorization_url="https://www.facebook.com/v6.0/dialog/oauth",
        access_token_url="https://graph.facebook.com/v6.0/oauth/access_token",
        profile_url="https://graph.facebook.com/v6.0/me?fields=id,first_name,last_name,email",
        consumer_key=settings.SOCIAL_AUTH_FACEBOOK_KEY,
        consumer_secret=settings.SOCIAL_AUTH_FACEBOOK_SECRET)
    legacy_facebook_provider.save()

    for social_user in UserSocialAuth.objects.all():
        if social_user.provider == "facebook":
            AccountAccess(identifier=social_user.uid, user=social_user.user, provider=legacy_facebook_provider, access_token=social_user.extra_data).save()
        elif social_user.provider == "google-oauth2":
            AccountAccess(identifier=social_user.uid, user=social_user.user, provider=legacy_google_provider, access_token=social_user.extra_data).save()
        else:
            raise RuntimeError(f"Got unknown provider: {social_user.provider}! Aborting rollback!")
    UserSocialAuth.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('wwwapp', '0062_auto_20200816_1023'),
        ('social_django', '0008_partial_timestamp'),
    ]

    operations = [
        migrations.RunPython(forwards_func, reverse_func),
    ]
