import datetime
import hashlib
import json
import os
import sys
import mimetypes
from urllib.parse import urljoin

import bleach
from dateutil.relativedelta import relativedelta
from wsgiref.util import FileWrapper
from typing import Dict

from django.db.models.query import Prefetch

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import SuspiciousOperation
from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpRequest, HttpResponseForbidden
from django.http.response import HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django_bleach.utils import get_bleach_default_options

from .forms import ArticleForm, UserProfileForm, UserForm, WorkshopForm, \
    UserProfilePageForm, WorkshopPageForm, UserCoverLetterForm, UserInfoPageForm, WorkshopParticipantPointsForm, \
    TinyMCEUpload
from .models import Article, UserProfile, Workshop, WorkshopParticipant, \
    WorkshopUserProfile, ResourceYearPermission, Camp
from .templatetags.wwwtags import qualified_mark


def get_context(request):
    context = {}

    context['has_workshops'] = False

    if request.user.is_authenticated:
        if Workshop.objects.filter(lecturer__user=request.user).exists():
            context['has_workshops'] = True

        visible_resources = ResourceYearPermission.objects.exclude(access_url__exact="")
        if request.user.has_perm('wwwapp.access_all_resources'):
            context['resources'] = visible_resources
        else:
            try:
                user_profile = UserProfile.objects.get(user=request.user)
                context['resources'] = visible_resources.filter(year__in=user_profile.all_participation_years())
            except UserProfile.DoesNotExist:
                context['resources'] = []

    context['google_analytics_key'] = settings.GOOGLE_ANALYTICS_KEY
    context['articles_on_menubar'] = Article.objects.filter(on_menubar=True).all()
    context['current_year'] = Camp.objects.latest()

    return context


def program_view(request, year=None):
    if year is None:
        url = reverse('program', args=[Camp.objects.latest().pk])
        args = request.META.get('QUERY_STRING', '')
        if args:
            url = "%s?%s" % (url, args)
        return redirect(url)

    year = get_object_or_404(Camp, pk=year)

    context = get_context(request)
    context['title'] = 'Program %s' % str(year)

    if request.user.is_authenticated:
        user_participation = set(Workshop.objects.filter(participants__user=request.user).all())
    else:
        user_participation = set()

    workshops = Workshop.objects.filter(Q(status='Z') | Q(status='X'), type__year=year).order_by('title').prefetch_related('lecturer', 'lecturer__user', 'category')
    context['workshops'] = [(workshop, (workshop in user_participation)) for workshop
                            in workshops]

    if request.user.is_authenticated:
        qualifications = WorkshopParticipant.objects.filter(participant__user=request.user, workshop__type__year=year).prefetch_related('workshop')
        if not any(qualification.qualification_result is not None for qualification in qualifications):
            qualifications = None
        context['your_qualifications'] = qualifications

    return render(request, 'program.html', context)


def profile_view(request, user_id):
    """
    This function allows to view other people's profile by id.
    However, to view them easily some kind of resolver might be needed as we don't have usernames.
    """
    context = get_context(request)
    user_id = int(user_id)
    user = get_object_or_404(User.objects.prefetch_related(
        'userprofile',
        'userprofile__user',
        'userprofile__user_info',
        'userprofile__workshop_profile',
        'userprofile__lecturer_workshops',
        'userprofile__lecturer_workshops__type__year',
    ), pk=user_id)

    is_my_profile = (request.user == user)
    can_see_all_users = request.user.has_perm('wwwapp.see_all_users')
    can_see_all_workshops = request.user.has_perm('wwwapp.see_all_workshops')

    can_qualify = request.user.has_perm('wwwapp.change_workshop_user_profile')
    context['can_qualify'] = can_qualify
    context['workshop_profile'] = WorkshopUserProfile.objects.filter(
        user_profile=user.userprofile, year=Camp.objects.latest())

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect_to_login(reverse('profile', args=[user_id]))
        if not can_qualify:
            return HttpResponseForbidden()
        (edition_profile, _) = WorkshopUserProfile.objects.get_or_create(
            user_profile=user.userprofile, year=Camp.objects.latest())
        if request.POST['qualify'] == 'accept':
            edition_profile.status = WorkshopUserProfile.STATUS_ACCEPTED
            edition_profile.save()
        elif request.POST['qualify'] == 'reject':
            edition_profile.status = WorkshopUserProfile.STATUS_REJECTED
            edition_profile.save()
        elif request.POST['qualify'] == 'cancel':
            edition_profile.status = WorkshopUserProfile.STATUS_CANCELLED
            edition_profile.save()
        elif request.POST['qualify'] == 'delete':
            edition_profile.delete()
            edition_profile = None
        else:
            raise SuspiciousOperation("Invalid argument")
        user.userprofile.refresh_from_db(fields=['workshop_profile'])
        context['workshop_profile'] = edition_profile

    context['title'] = "{0.first_name} {0.last_name}".format(user)
    context['profile_page'] = user.userprofile.profile_page
    context['is_my_profile'] = is_my_profile
    context['gender'] = user.userprofile.gender

    if can_see_all_users or is_my_profile:
        context['profile'] = user.userprofile
        context['participation_data'] = user.userprofile.all_participation_data()
        if not can_see_all_workshops and not is_my_profile:
            # If the current user can't see non-public workshops, remove them from the list
            for participation in context['participation_data']:
                participation['workshops'] = [w for w in participation['workshops'] if w.is_publicly_visible()]

    if can_see_all_workshops or is_my_profile:
        context['lecturer_workshops'] = user.userprofile.lecturer_workshops.prefetch_related('type').all().order_by('type__year')
    else:
        context['lecturer_workshops'] = user.userprofile.lecturer_workshops.prefetch_related('type').filter(Q(status='Z') | Q(status='X')).order_by('type__year')
    context['can_see_all_workshops'] = can_see_all_workshops

    return render(request, 'profile.html', context)


@login_required()
def my_profile_edit_view(request):
    context = get_context(request)
    user_profile = UserProfile.objects.get(user=request.user)

    user_form = UserForm(instance=request.user)
    user_profile_form = UserProfileForm(instance=user_profile)
    user_profile_page_form = UserProfilePageForm(instance=user_profile)
    user_cover_letter_form = UserCoverLetterForm(instance=user_profile)
    user_info_page_form = UserInfoPageForm(instance=user_profile.user_info)

    if request.method == "POST":
        page = request.POST['page']
        if page == 'data':
            user_form = UserForm(request.POST, instance=request.user)
            user_profile_form = UserProfileForm(request.POST, instance=user_profile)
            if user_form.is_valid() and user_profile_form.is_valid():
                user_form.save()
                user_profile_form.save()
                messages.info(request, 'Zapisano.')
        elif page == 'profile_page':
            user_profile_page_form = UserProfilePageForm(request.POST, instance=user_profile)
            if user_profile_page_form.is_valid():
                user_profile_page_form.save()
                messages.info(request, 'Zapisano.')
        elif page == 'cover_letter':
            user_cover_letter_form = UserCoverLetterForm(request.POST, instance=user_profile)
            if user_cover_letter_form.is_valid():
                user_cover_letter_form.save()
                messages.info(request, 'Zapisano.')
        elif page == 'user_info':
            user_info_page_form = UserInfoPageForm(request.POST, instance=user_profile.user_info)
            if user_info_page_form.is_valid():
                user_info_page_form.save()
                messages.info(request, 'Zapisano.')
        else:
            raise SuspiciousOperation('Invalid page')

    user_form.helper.form_tag = False
    user_profile_form.helper.form_tag = False
    context['user_form'] = user_form
    context['user_profile_form'] = user_profile_form
    context['user_profile_page_form'] = user_profile_page_form
    context['user_cover_letter_form'] = user_cover_letter_form
    context['user_info_page_form'] = user_info_page_form
    context['title'] = 'Mój profil'

    return render(request, 'profileedit.html', context)


@login_required()
def workshop_proposal_view(request, name=None):
    new = (name is None)
    if new:
        workshop = None
        title = 'Nowe warsztaty'
        has_perm_to_edit = Camp.objects.latest().are_proposals_open()
    else:
        workshop = get_object_or_404(Workshop, name=name)
        title = workshop.title
        has_perm_to_edit = can_edit_workshop(workshop, request.user)

    # Workshop proposals are only visible to admins
    has_perm_to_see_all = request.user.has_perm('wwwapp.see_all_workshops')
    if workshop and not has_perm_to_edit and not has_perm_to_see_all:
        return HttpResponseForbidden()

    if request.method == 'POST' and 'qualify' in request.POST:
        if not request.user.has_perm('wwwapp.change_workshop_status'):
            return HttpResponseForbidden()
        if request.POST['qualify'] == 'accept':
            workshop.status = Workshop.STATUS_ACCEPTED
            workshop.save()
        elif request.POST['qualify'] == 'reject':
            workshop.status = Workshop.STATUS_REJECTED
            workshop.save()
        elif request.POST['qualify'] == 'cancel':
            workshop.status = Workshop.STATUS_CANCELLED
            workshop.save()
        elif request.POST['qualify'] == 'delete':
            workshop.status = None
            workshop.save()
        else:
            raise SuspiciousOperation("Invalid argument")

    if has_perm_to_edit:
        if request.method == 'POST' and 'qualify' not in request.POST:
            form = WorkshopForm(request.POST, instance=workshop)
            if form.is_valid():
                workshop = form.save(commit=False)
                workshop.save()
                form.save_m2m()
                if new:
                    user_profile = UserProfile.objects.get(user=request.user)
                    workshop.lecturer.add(user_profile)
                    workshop.save()
                messages.info(request, 'Zapisano.')
                return redirect('workshop_proposal', form.instance.name)
        else:
            form = WorkshopForm(instance=workshop)
    else:
        form = None

    context = get_context(request)
    context['title'] = title
    context['workshop'] = workshop
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = has_perm_to_edit or has_perm_to_see_all

    context['form'] = form

    return render(request, 'workshopproposal.html', context)


def can_edit_workshop(workshop, user):
    if user.is_authenticated:
        return workshop.lecturer.filter(user=user).exists() \
               or user.has_perm('wwwapp.edit_all_workshops')
    else:
        return False


def workshop_page_view(request, name):
    workshop = get_object_or_404(Workshop, name=name)
    has_perm_to_edit = can_edit_workshop(workshop, request.user)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")

    context = get_context(request)
    context['title'] = workshop.title
    context['workshop'] = workshop
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = \
        has_perm_to_edit or request.user.has_perm('wwwapp.see_all_workshops')

    return render(request, 'workshoppage.html', context)


@login_required()
def workshop_page_edit_view(request, name):
    workshop = get_object_or_404(Workshop, name=name)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")
    if not can_edit_workshop(workshop, request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = WorkshopPageForm(request.POST, request.FILES,
                                instance=workshop)
        if form.is_valid():
            workshop = form.save(commit=False)
            workshop.save()
            form.save_m2m()
            user_profile = UserProfile.objects.get(user=request.user)
            workshop.lecturer.add(user_profile)
            workshop.save()
            messages.info(request, 'Zapisano.')
            return redirect('workshop_page_edit', form.instance.name)
    else:
        if not workshop.page_content:
            workshop_template = Article.objects.get(
                name="template_for_workshop_page").content
            workshop.page_content = workshop_template
            workshop.save()
        form = WorkshopPageForm(instance=workshop)

    context = get_context(request)
    context['title'] = workshop.title
    context['workshop'] = workshop
    context['form'] = form
    context['has_perm_to_edit'] = True
    context['has_perm_to_view_details'] = True

    return render(request, 'workshoppageedit.html', context)


@login_required()
def workshop_participants_view(request, name):
    workshop = get_object_or_404(Workshop, name=name)
    has_perm_to_edit = can_edit_workshop(workshop, request.user)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")

    if not (has_perm_to_edit or request.user.has_perm('wwwapp.see_all_workshops')):
        return HttpResponseForbidden()

    context = get_context(request)
    context['title'] = '%s - uczestnicy' % workshop.title
    context['workshop'] = workshop
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = True

    context['workshop_participants'] = WorkshopParticipant.objects.filter(workshop=workshop).prefetch_related(
            'workshop', 'participant', 'participant__user')

    for participant in context['workshop_participants']:
        participant.form = WorkshopParticipantPointsForm(instance=participant, auto_id='%s_'+str(participant.id))
    
    return render(request, 'workshopparticipants.html', context)


def save_points_view(request):
    if 'id' not in request.POST:
        raise SuspiciousOperation()

    workshop_participant = WorkshopParticipant.objects.get(id=request.POST['id'])

    has_perm_to_edit = can_edit_workshop(workshop_participant.workshop, request.user)
    if not has_perm_to_edit:
        return HttpResponseForbidden()

    form = WorkshopParticipantPointsForm(request.POST, instance=workshop_participant)
    if not form.is_valid():
        return JsonResponse({'error': form.errors.as_text()})
    workshop_participant = form.save()

    return JsonResponse({'qualification_result': workshop_participant.qualification_result,
                         'comment': workshop_participant.comment,
                         'mark': qualified_mark(workshop_participant.is_qualified())})


@login_required()
@permission_required('wwwapp.see_all_users', raise_exception=True)
def participants_view(request, year=None):
    participants = UserProfile.objects.prefetch_related(
        'user',
        'user_info',
        'workshop_profile',
        'workshop_profile__year',
        'lecturer_workshops',
        'lecturer_workshops__type__year',
    ).all()

    if year is not None:
        year = get_object_or_404(Camp, pk=year)
        participants = participants.filter(workshops__type__year=year)

        lecturers = Workshop.objects.filter(type__year=year).values_list('lecturer__user').distinct()
        participants = participants.exclude(user__id__in=lecturers)

        participants = participants.prefetch_related(
            Prefetch('workshopparticipant_set', queryset=WorkshopParticipant.objects.filter(workshop__type__year=year)),
            'workshopparticipant_set__workshop',
            'workshopparticipant_set__workshop__type__year',
        )

    people = {}

    for participant in participants:
        birth = participant.user_info.get_birth_date()
        is_adult = None
        if birth is not None:
            if year is not None and year.start_date:
                is_adult = year.start_date >= birth + relativedelta(years=18)
            else:
                is_adult = datetime.date.today() >= birth + relativedelta(years=18)

        workshop_profile = None
        if year is not None:
            workshop_profile = participant.workshop_profile.all()
            workshop_profile = list(filter(lambda x: x.year == year, workshop_profile))
            workshop_profile = workshop_profile[0] if workshop_profile else None

        participation_data = participant.all_participation_data()
        if not request.user.has_perm('wwwapp.see_all_workshops'):
            # If the current user can't see non-public workshops, remove them from the list
            for participation in participation_data:
                participation['workshops'] = [w for w in participation['workshops'] if w.is_publicly_visible()]

        people[participant.id] = {
            'user': participant.user,
            'birth': birth,
            'is_adult': is_adult,
            'pesel': participant.user_info.pesel,
            'address': participant.user_info.address,
            'phone': participant.user_info.phone,
            'tshirt_size': participant.user_info.tshirt_size,
            'matura_exam_year': participant.matura_exam_year,
            'accepted_workshop_count': 0,
            'workshop_count': 0,
            'has_letter': bool(participant.cover_letter and len(participant.cover_letter) > 50),
            'status': workshop_profile.status if workshop_profile else None,
            'status_display': workshop_profile.get_status_display if workshop_profile else None,
            'participation_data': participation_data,
            'school': participant.school,
            'points': 0.0,
            'infos': [],
            'how_do_you_know_about': participant.how_do_you_know_about,
            'comments': participant.user_info.comments,
            'start_date': participant.user_info.start_date,
            'end_date': participant.user_info.end_date,
        }

        if year:
            for wp in participant.workshopparticipant_set.all():
                assert wp.workshop.type.year == year
                if wp.qualification_result:
                    people[participant.id]['points'] += float(wp.result_in_percent())
                people[participant.id]['infos'].append("{title} : {result:.1f}% : {comment}".format(
                    title=wp.workshop.title,
                    result=wp.result_in_percent() if wp.qualification_result else 0,
                    comment=wp.comment if wp.comment else ""
                ))
                people[participant.id]['workshop_count'] += 1
                if wp.is_qualified():
                    people[participant.id]['accepted_workshop_count'] += 1

    people = list(people.values())

    context = get_context(request)
    context['title'] = ('Uczestnicy: %s' % year) if year is not None else 'Wszyscy ludzie'
    context['people'] = people
    context['is_all_people'] = year is None

    return render(request, 'participants.html', context)


@login_required()
@permission_required('wwwapp.see_all_users', raise_exception=True)
def lecturers_view(request: HttpRequest, year: int) -> HttpResponse:
    year = get_object_or_404(Camp, pk=year)

    workshops = Workshop.objects.filter(type__year=year, status=Workshop.STATUS_ACCEPTED).prefetch_related('lecturer', 'lecturer__user', 'lecturer__user_info')

    people: Dict[int, Dict[str, any]] = {}
    for workshop in workshops:
        for lecturer in workshop.lecturer.all():
            if lecturer.id in people:
                people[lecturer.id]['workshops'].append(workshop.info_for_client_link())
                continue

            birth = lecturer.user_info.get_birth_date()
            is_adult = None
            if birth is not None and year.start_date:
                is_adult = year.start_date >= birth + relativedelta(years=18)

            people[lecturer.id] = {
                'user': lecturer.user,
                'birth': birth,
                'is_adult': is_adult,
                'pesel': lecturer.user_info.pesel,
                'address': lecturer.user_info.address,
                'phone': lecturer.user_info.phone,
                'tshirt_size': lecturer.user_info.tshirt_size,
                'comments': lecturer.user_info.comments,
                'start_date': lecturer.user_info.start_date,
                'end_date': lecturer.user_info.end_date,
                'workshops': [workshop.info_for_client_link()],
            }

    people_list = list(people.values())

    context = get_context(request)
    context['title'] = 'Prowadzący: %s' % year
    context['people'] = people_list

    return render(request, 'lecturers.html', context)


def register_to_workshop_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'redirect': reverse('login'), 'error': u'Jesteś niezalogowany'})

    if 'workshop_name' not in request.POST:
        raise SuspiciousOperation()

    workshop_name = request.POST['workshop_name']
    workshop = get_object_or_404(Workshop, name=workshop_name)

    if not workshop.is_qualification_editable():
        return JsonResponse({'error': u'Kwalifikacja na te warsztaty została zakończona.'})

    _, created = WorkshopParticipant.objects.get_or_create(participant=UserProfile.objects.get(user=request.user), workshop=workshop)

    context = get_context(request)
    context['workshop'] = workshop
    context['registered'] = True
    content = render(request, '_programworkshop.html', context).content.decode()
    if created:
        return JsonResponse({'content': content})
    else:
        return JsonResponse({'content': content, 'error': u'Już jesteś zapisany na te warsztaty'})


def unregister_from_workshop_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'redirect': reverse('login'), 'error': u'Jesteś niezalogowany'})

    if 'workshop_name' not in request.POST:
        raise SuspiciousOperation()

    workshop_name = request.POST['workshop_name']
    workshop = get_object_or_404(Workshop, name=workshop_name)
    profile = UserProfile.objects.get(user=request.user)
    workshop_participant = WorkshopParticipant.objects.filter(workshop=workshop, participant=profile).first()

    if not workshop.is_qualification_editable():
        return JsonResponse({'error': u'Kwalifikacja na te warsztaty została zakończona.'})

    if workshop_participant:
        if workshop_participant.qualification_result is not None or workshop_participant.comment:
            return JsonResponse({'error': u'Masz już wyniki z tej kwalifikacji - nie możesz się wycofać.'})

        workshop_participant.delete()

    context = get_context(request)
    context['workshop'] = workshop
    context['registered'] = False
    content = render(request, '_programworkshop.html', context).content.decode()
    if workshop_participant:
        return JsonResponse({'content': content})
    else:
        return JsonResponse({'content': content, 'error': u'Nie jesteś zapisany na te warsztaty'})


@permission_required('wwwapp.export_workshop_registration')
def data_for_plan_view(request, year: int) -> HttpResponse:
    year = get_object_or_404(Camp, pk=year)

    data = {}

    participant_profiles_raw = UserProfile.objects.filter(workshop_profile__year=year, workshop_profile__status='Z')

    lecturer_profiles_raw = set()
    workshop_ids = set()
    workshops = []
    for workshop in Workshop.objects.filter(status='Z', type__year=year):
        workshop_data = {'wid': workshop.id,
                         'name': workshop.title,
                         'lecturers': [lect.id for lect in
                                       workshop.lecturer.all()]}
        for lecturer in workshop.lecturer.all():
            if lecturer not in participant_profiles_raw:
                lecturer_profiles_raw.add(lecturer)
        workshop_ids.add(workshop.id)
        workshops.append(workshop_data)
    data['workshops'] = workshops

    users = []
    user_ids = set()

    def clean_date(date: datetime.date or None, min: datetime.date, max: datetime.date, default: datetime.date) -> datetime.date:
        if date is None or (min is not None and date < min) or (max is not None and date > max):
            return default
        return date

    current_year = Camp.objects.latest()
    for user_type, profiles in [('Lecturer', lecturer_profiles_raw),
                                ('Participant', participant_profiles_raw)]:
        for up in profiles:
            user = {
                'uid': up.id,
                'name': up.user.get_full_name(),
                'type': user_type,
            }
            if year == current_year:
                # TODO: UserInfo data is valid for the current year only
                user.update({
                    'start': clean_date(up.user_info.start_date, year.start_date, year.end_date, year.start_date),
                    'end': clean_date(up.user_info.end_date, year.start_date, year.end_date, year.end_date)
                })
            users.append(user)
            user_ids.add(up.id)

    data['users'] = users

    participation = []
    for wp in WorkshopParticipant.objects.filter(workshop__id__in=workshop_ids, participant__id__in=user_ids):
        participation.append({
            'wid': wp.workshop.id,
            'uid': wp.participant.id,
        })
    data['participation'] = participation

    return JsonResponse(data, json_dumps_params={'indent': 4})


def qualification_problems_view(request, workshop_name):
    workshop = get_object_or_404(Workshop, name=workshop_name)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")
    if not workshop.qualification_problems:
        return HttpResponseNotFound("Nie ma jeszcze zadań kwalifikacyjnych")

    filename = workshop.qualification_problems.path

    wrapper = FileWrapper(open(filename, "rb"))
    response = HttpResponse(wrapper, content_type=mimetypes.guess_type(filename)[0])
    response['Content-Length'] = os.path.getsize(filename)
    return response


def article_view(request, name):
    context = get_context(request)

    art = get_object_or_404(Article, name=name)
    title = art.title
    can_edit_article = request.user.has_perm('wwwapp.change_article')

    bleach_args = get_bleach_default_options().copy()
    if art.name == 'index':
        bleach_args['tags'] += ['iframe']  # Allow iframe on main page for Facebook embed
    article_content_clean = mark_safe(bleach.clean(art.content, **bleach_args))

    context['title'] = title
    context['article'] = art
    context['article_content_clean'] = article_content_clean
    context['can_edit'] = can_edit_article

    return render(request, 'article.html', context)


@login_required()
def article_edit_view(request, name=None):
    context = get_context(request)
    new = (name is None)
    if new:
        art = None
        title = 'Nowy artykuł'
        has_perm = request.user.has_perm('wwwapp.add_article')
    else:
        art = get_object_or_404(Article, name=name)
        title = art.title
        has_perm = request.user.has_perm('wwwapp.change_article')

    if not has_perm:
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = ArticleForm(request.user, request.POST, instance=art)
        if form.is_valid():
            article = form.save(commit=False)
            article.modified_by = request.user
            article.save()
            form.save_m2m()
            messages.info(request, 'Zapisano.')
            return redirect('article', form.instance.name)
    else:
        form = ArticleForm(request.user, instance=art)

    context['title'] = title
    context['article'] = art
    context['form'] = form

    return render(request, 'articleedit.html', context)


def article_name_list_view(request):
    articles = Article.objects.all()
    article_list = [{'title': 'Artykuł: ' + (article.title or article.name), 'value': reverse('article', kwargs={'name': article.name})} for article in articles]

    workshops = Workshop.objects.filter(Q(status='Z') | Q(status='X')).order_by('-type__year')
    workshop_list = [{'title': 'Warsztaty (' + str(workshop.type.year) + '): ' + workshop.title, 'value': reverse('workshop_page', kwargs={'name': workshop.name})} for workshop in workshops]

    return JsonResponse(article_list + workshop_list, safe=False)


@login_required()
def your_workshops_view(request):
    workshops = Workshop.objects.filter(lecturer__user=request.user)
    return render_workshops(request, 'Twoje warsztaty', True, workshops)


@login_required()
@permission_required('wwwapp.see_all_workshops', raise_exception=True)
def all_workshops_view(request):
    workshops = Workshop.objects.all()
    return render_workshops(request, 'Wszystkie warsztaty', False, workshops)


def render_workshops(request, title, link_to_edit, workshops):
    context = get_context(request)

    years = Camp.objects.all().reverse()
    context['workshops'] = [
        {'year': year,
         'workshops': [workshop for workshop in workshops if workshop.type.year == year]}
        for year in years]
    context['title'] = title
    context['link_to_edit'] = link_to_edit

    return render(request, 'listworkshop.html', context)


def as_article(name):
    # We want to make sure that article with this name exists.
    # try-except is needed because of some migration/initialization problems.
    try:
        Article.objects.get_or_create(name=name)
    except OperationalError:
        print("WARNING: Couldn't create article named", name,
              "; This should happen only during migration.", file=sys.stderr)
    except ProgrammingError:
        print("WARNING: Couldn't create article named", name,
              "; This should happen only during migration.", file=sys.stderr)

    def page(request):
        return article_view(request, name)
    return page


index_view = as_article("index")
template_for_workshop_page_view = as_article("template_for_workshop_page")


def resource_auth_view(request):
    """
    View checking permission for resource (header X-Original-URI). Returns 200
    when currently logged in user should be granted access to resource and 403
    when access should be denied.

    See https://docs.nginx.com/nginx/admin-guide/security-controls/configuring-subrequest-authentication/
    for intended usage.
    """
    if not request.user.is_authenticated:
        return HttpResponseForbidden("You need to login.")
    if request.user.has_perm('wwwapp.access_all_resources'):
        return HttpResponse("Glory to WWW and the ELITARNY MIMUW!!!")

    user_profile = UserProfile.objects.get(user=request.user)

    uri = request.META.get('HTTP_X_ORIGINAL_URI', '')

    for resource in ResourceYearPermission.resources_for_uri(uri):
        if user_profile.is_participating_in(resource.year):
            return HttpResponse("Welcome!")
    return HttpResponseForbidden("What about NO!")


@login_required()
@require_http_methods(["POST"])
@csrf_exempt
def upload_file(request, type, name):
    """
    Handle a file upload from TinyMCE
    """

    target_dir = None
    if type == "article":
        article = get_object_or_404(Article, name=name)
        target_dir = "images/articles/{}/".format(article.name)
        if not request.user.has_perm('wwwapp.change_article'):
            return HttpResponseForbidden()
    elif type == "workshop":
        workshop = get_object_or_404(Workshop, name=name)
        if not can_edit_workshop(workshop, request.user) or not workshop.is_publicly_visible() or not workshop.is_workshop_editable():
            return HttpResponseForbidden()
        target_dir = "images/workshops/{}/".format(workshop.name)
    else:
        raise SuspiciousOperation()
    assert target_dir is not None

    form = TinyMCEUpload(request.POST, request.FILES)
    if not form.is_valid():
        data = {'errors': [v for k, v in form.errors.items()]}
        return HttpResponseBadRequest(json.dumps(data))

    os.makedirs(os.path.join(settings.MEDIA_ROOT, target_dir), exist_ok=True)

    f = request.FILES['file']

    h = hashlib.sha256()
    for chunk in f.chunks():
        h.update(chunk)
    h = h.hexdigest()

    name = h + os.path.splitext(f.name)[1]

    with open(os.path.join(settings.MEDIA_ROOT, target_dir, name), 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)

    return JsonResponse({'location': urljoin(urljoin(settings.MEDIA_URL, target_dir), name)})
