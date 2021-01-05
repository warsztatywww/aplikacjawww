import logging

from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.shortcuts import render, redirect
from django.urls import reverse
from social_core.pipeline.partial import partial_step
from social_django.middleware import SocialAuthExceptionMiddleware
from social_django.models import UserSocialAuth

from .models import UserProfile
from .views import get_context


def login_view(request):
    session_clear = [ 'partial_pipeline_token',
                      'merge_confirmation_token',
                      'merge_confirmation_backend',
                      'merge_confirmation_new_account',
                      'merge_confirmation_next',
                    ]
    for key in session_clear:
        # This shouldn't be necessary but it's here "just in case"
        request.session.pop(key, None)

    if request.user.is_authenticated:
        # This should never happen if the login flow worked correctly but I'm leaving this here just in case there are any broken users in the database already
        # (aka I'm too afraid to remove it)
        user_profile, just_created = UserProfile.objects.get_or_create(user=request.user)
        if just_created:
            logging.getLogger('django.request').error(
                'User profile was missing for %s. This should have never happened.', request.user,
                extra={'request': request})
        return redirect('mydata_status')

    # Make sure to call get_context after UserInfo and UserProfile get created, since they are required
    # to figure out what to show on the menu bar
    context = get_context(request)
    return render(request, 'login.html', context)


@partial_step(save_to_session=False)
def merge_accounts(strategy, details, request, response, current_partial, user=None, is_new=False, *args, **kwargs):
    if is_new:
        if user:
            # This happens in 2 cases - when an already logged in user logs in with a different provider
            # or when someone confirmed the ownership of an account
            return {
                'user': user,
                'is_new': False,
            }

        if strategy.session_get('merge_confirmation_new_account'):
            # The user asked for a new account and we are allowed to create a new account
            strategy.session_pop('merge_confirmation_new_account')
            return

        new_backend = current_partial.backend
        context = get_context(request)
        context['allow_account_creation'] = True
        context['new_provider'] = new_backend
        match_users = []

        email = details.get('email')
        if email:
            context['email'] = email
            match_users = list(strategy.storage.user.get_users_by_email(email))
            if match_users:
                context['allow_account_creation'] = False
        else:
            context['email'] = None

        last_name = details.get('last_name')
        first_name = details.get('first_name')
        if not match_users and last_name:
            context['name'] = last_name
            query = strategy.storage.user.user_model().objects.filter(last_name=last_name)
            if first_name:
                context['name'] = first_name + ' ' + last_name
                query = query.filter(first_name=first_name)
            match_users = match_users + list(query.all())
        else:
            context['name'] = None

        # If there are matches, let the user select an account for connection
        if match_users:
            context['matches'] = []
            for matchUser in match_users:
                match = {'name': matchUser.first_name + ' ' + matchUser.last_name,
                         'email': matchUser.email,
                         'providers': []}
                for matchAccess in UserSocialAuth.objects.filter(user=matchUser.id).all():
                    match['providers'].append(matchAccess.provider)
                context['matches'].append(match)

            strategy.session_set('merge_confirmation_backend', new_backend)
            strategy.session_set('merge_confirmation_token', current_partial.token)
            if context['allow_account_creation']:
                strategy.session_set('merge_confirmation_new_account', True)
            next_url = strategy.session_get('next')
            if next_url:
                strategy.session_set('merge_confirmation_next', next_url)

            return render(request, 'loginMerge.html', context)


def finish_merge_verification(request):
    if {'merge_confirmation_backend', 'merge_confirmation_token'} <= request.session.keys():
        # Under no circumstances should partial_pipeline_token be set before as when the user logs into a different
        # provider python-social-auth will nuke the partial from the DB and the pipeline won't resume
        request.session['partial_pipeline_token'] = request.session['merge_confirmation_token']
        request.session['next'] = request.session.get('merge_confirmation_next', '/')
        return redirect(reverse('social:complete', args=(request.session['merge_confirmation_backend'],)))
    else:
        return redirect('/')


# Register a receiver called whenever a User object is saved.
# Add all created Users to group allUsers.
@receiver(post_save, sender=User, dispatch_uid='user_post_save_handler')
def user_post_save(sender, instance, created, **kwargs):
    if created:
        group, group_created = Group.objects.get_or_create(name='allUsers')
        group.user_set.add(instance)


class CustomSocialAuthExceptionMiddleware(SocialAuthExceptionMiddleware):
    def raise_exception(self, request, exception):
        # SocialAuthExceptionMiddleware is disabled when DEBUG=True, and there is no other way to override that...
        return False
