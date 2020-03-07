import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group, User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.shortcuts import render, redirect
from django.urls import reverse
from social_core.pipeline.partial import partial_step
from social_django.models import UserSocialAuth

from .models import UserProfile
from .views import get_context


def login_view(request):
    if 'partial_pipeline_token' in request.session:
        del request.session['partial_pipeline_token']

    if request.user.is_authenticated:
        # This should never happen if the login flow worked correctly but I'm leaving this here just in case there are any broken users in the database already
        # (aka I'm too afraid to remove it)
        user_profile, just_created = UserProfile.objects.get_or_create(user=request.user)
        if just_created:
            logging.getLogger('django.request').error(
                'User profile was missing for %s. This should have never happened.', request.user,
                extra={'request': request})

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

        new_backend = current_partial.backend
        context = get_context(request)
        context['allow_account_creation'] = True
        context['new_provider'] = new_backend
        context['partial_token'] = current_partial.token
        match_users = []

        email = details.get('email')
        if email:
            context['email'] = email
            match_users = list(strategy.storage.user.get_users_by_email(email))
            if len(match_users) == 1 and response.get('email_verified'):
                # Don't perform additional validation when the mail was validated by google
                return {
                    'user': match_users[0],
                    'is_new': False,
                }
            elif match_users:
                context['allow_account_creation'] = False
        else:
            context['email'] = None

        if context['allow_account_creation'] and request.GET.get('new_account'):
            return

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
            return render(request, 'loginMerge.html', context)


def resume_partial(request, provider):
    request.session['partial_pipeline_token'] = request.GET.get('partial_token')
    request.session['next'] = '/'
    if request.user.is_authenticated:
        return redirect(reverse('social:complete', args=(provider,)))
    else:
        return redirect(reverse('social:complete', args=(provider,)) + "?new_account=1")

# Register a receiver called whenever a User object is saved.
# Add all created Users to group allUsers.
@receiver(post_save, sender=User, dispatch_uid='user_post_save_handler')
def user_post_save(sender, instance, created, **kwargs):
    if created:
        group, group_created = Group.objects.get_or_create(name='allUsers')
        group.user_set.add(instance)
