import datetime
import hashlib
import json
import os
import sys
from urllib.parse import urljoin

import bleach
from dateutil.relativedelta import relativedelta
from typing import Dict

from django.db.models.expressions import F
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
from django.http.response import HttpResponseBadRequest, HttpResponseNotFound, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.template import Template, Context
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_bleach.utils import get_bleach_default_options
from django_sendfile import sendfile

from wwwforms.models import Form, FormQuestionAnswer, FormQuestion, pesel_extract_date
from .forms import ArticleForm, UserProfileForm, UserForm, \
    UserProfilePageForm, WorkshopForm, UserCoverLetterForm, WorkshopParticipantPointsForm, \
    TinyMCEUpload, SolutionFileFormSet, SolutionForm
from .models import Article, UserProfile, Workshop, WorkshopParticipant, \
    WorkshopUserProfile, ResourceYearPermission, Camp, Solution
from .templatetags.wwwtags import qualified_mark


def get_context(request):
    context = {}

    if request.user.is_authenticated:
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
    context['years'] = Camp.objects.all()
    context['current_year'] = Camp.current()

    return context


def redirect_to_view_for_latest_year(target_view_name):
    def view(request):
        url = reverse(target_view_name, args=[Camp.current().pk])
        args = request.META.get('QUERY_STRING', '')
        if args:
            url = "%s?%s" % (url, args)
        return redirect(url)
    return view


def program_view(request, year):
    year = get_object_or_404(Camp, pk=year)

    context = {}
    context['title'] = 'Program %s' % str(year)

    if request.user.is_authenticated:
        user_participation = set(year.workshops.filter(participants__user=request.user).all())
    else:
        user_participation = set()

    workshops = year.workshops.filter(Q(status='Z') | Q(status='X')).order_by('title').prefetch_related('lecturer', 'lecturer__user', 'type', 'category')
    context['workshops'] = [(workshop, (workshop in user_participation)) for workshop
                            in workshops]
    if request.user.is_authenticated and year == Camp.current():
        context['has_results'] = WorkshopParticipant.objects.filter(
            workshop__year=year, participant=request.user.userprofile, qualification_result__isnull=False
        ).exists()
    else:
        context['has_results'] = False

    context['selected_year'] = year
    return render(request, 'program.html', context)


def profile_view(request, user_id):
    """
    This function allows to view other people's profile by id.
    However, to view them easily some kind of resolver might be needed as we don't have usernames.
    """
    context = {}
    user_id = int(user_id)
    user = get_object_or_404(User.objects.prefetch_related(
        'userprofile',
        'userprofile__user',
        'userprofile__workshop_profile',
        'userprofile__lecturer_workshops',
        'userprofile__lecturer_workshops__year',
    ), pk=user_id)

    is_my_profile = (request.user == user)
    can_see_all_users = request.user.has_perm('wwwapp.see_all_users')
    can_see_all_workshops = request.user.has_perm('wwwapp.see_all_workshops')

    can_qualify = request.user.has_perm('wwwapp.change_workshop_user_profile')
    context['can_qualify'] = can_qualify
    context['workshop_profile'] = WorkshopUserProfile.objects.filter(
        user_profile=user.userprofile, year=Camp.current())

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect_to_login(reverse('profile', args=[user_id]))
        if not can_qualify:
            return HttpResponseForbidden()
        (edition_profile, _) = WorkshopUserProfile.objects.get_or_create(
            user_profile=user.userprofile, year=Camp.current())
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
        return redirect('profile', user.pk)

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
        context['lecturer_workshops'] = user.userprofile.lecturer_workshops.prefetch_related('type').all().order_by('year')
    else:
        context['lecturer_workshops'] = user.userprofile.lecturer_workshops.prefetch_related('type').filter(Q(status='Z') | Q(status='X')).order_by('year')
    context['can_see_all_workshops'] = can_see_all_workshops

    return render(request, 'profile.html', context)


@login_required()
def mydata_profile_view(request):
    context = {}

    if request.method == "POST":
        user_form = UserForm(request.POST, instance=request.user)
        user_profile_form = UserProfileForm(request.POST, instance=request.user.userprofile)
        if user_form.is_valid() and user_profile_form.is_valid():
            user_form.save()
            user_profile_form.save()
            messages.info(request, 'Zapisano.', extra_tags='auto-dismiss')
            return redirect('mydata_profile')
    else:
        user_form = UserForm(instance=request.user)
        user_profile_form = UserProfileForm(instance=request.user.userprofile)

    context['user_form'] = user_form
    context['user_profile_form'] = user_profile_form
    context['title'] = 'Mój profil'

    return render(request, 'mydata_profile.html', context)


@login_required()
def mydata_profile_page_view(request):
    context = {}

    if request.method == "POST":
        user_profile_page_form = UserProfilePageForm(request.POST, instance=request.user.userprofile)
        if user_profile_page_form.is_valid():
            user_profile_page_form.save()
            messages.info(request, 'Zapisano.', extra_tags='auto-dismiss')
            return redirect('mydata_profile_page')
    else:
        user_profile_page_form = UserProfilePageForm(instance=request.user.userprofile)

    context['user_profile_page_form'] = user_profile_page_form
    context['title'] = 'Mój profil'

    return render(request, 'mydata_profilepage.html', context)


@login_required()
def mydata_cover_letter_view(request):
    context = {}

    if request.method == "POST":
        user_cover_letter_form = UserCoverLetterForm(request.POST, instance=request.user.userprofile)
        if user_cover_letter_form.is_valid():
            user_cover_letter_form.save()
            messages.info(request, 'Zapisano.', extra_tags='auto-dismiss')
            return redirect('mydata_cover_letter')
    else:
        user_cover_letter_form = UserCoverLetterForm(instance=request.user.userprofile)

    context['user_cover_letter_form'] = user_cover_letter_form
    context['title'] = 'Mój profil'

    return render(request, 'mydata_coverletter.html', context)


@login_required()
def mydata_status_view(request):
    context = {}
    user_profile = UserProfile.objects.prefetch_related(
        'workshop_profile',
        'lecturer_workshops',
        'lecturer_workshops__year',
    ).get(user=request.user)
    current_year = Camp.current()

    participation_data = user_profile.all_participation_data()
    for p in participation_data:
        p['qualification_results'] = []

    qualifications = WorkshopParticipant.objects.filter(participant=user_profile).select_related('workshop', 'workshop__year', 'solution').all()
    for q in qualifications:
        participation_for_year = next(filter(lambda x: x['year'] == q.workshop.year, participation_data), None)
        if participation_for_year is None:
            participation_for_year = {'year': q.workshop.year, 'type': 'participant', 'status': None, 'qualification_results': []}
            participation_data.append(participation_for_year)
        participation_for_year['qualification_results'].append(q)
    participation_data.sort(key=lambda x: x['year'].year, reverse=True)

    current_status = next(filter(lambda x: x['year'] == current_year, participation_data), None)
    past_status = list(filter(lambda x: x['year'] != current_year, participation_data))

    context['title'] = 'Mój profil'
    context['gender'] = user_profile.gender
    context['has_completed_profile'] = user_profile.is_completed
    context['has_cover_letter'] = len(user_profile.cover_letter) >= 50
    context['current_status'] = current_status
    context['past_status'] = past_status

    return render(request, 'mydata_status.html', context)


@login_required()
def mydata_forms_view(request):
    context = {}

    context['user_info_forms'] = Form.visible_objects.all()
    context['title'] = 'Mój profil'

    return render(request, 'mydata_forms.html', context)


def can_edit_workshop(workshop, user):
    """
    Determines whether the user can see the edit views
    (but he may not be able to actually edit if if this is a workshop from a past edition - he can only see read-only
    state in that case)
    """
    if user.is_authenticated:
        is_lecturer = workshop.lecturer.filter(user=user).exists()
        has_perm_to_edit = is_lecturer or user.has_perm('wwwapp.edit_all_workshops')
        return has_perm_to_edit, is_lecturer
    else:
        return False, False


def workshop_page_view(request, year, name):
    workshop = get_object_or_404(Workshop, year=year, name=name)
    has_perm_to_edit, is_lecturer = can_edit_workshop(workshop, request.user)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")

    if request.user.is_authenticated:
        registered = workshop.participants.filter(user=request.user).exists()
    else:
        registered = False

    context = {}
    context['title'] = workshop.title
    context['workshop'] = workshop
    context['registered'] = registered
    context['is_lecturer'] = is_lecturer
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = \
        has_perm_to_edit or request.user.has_perm('wwwapp.see_all_workshops')

    return render(request, 'workshoppage.html', context)


@login_required()
def workshop_edit_view(request, year, name=None):
    if name is None:
        year = get_object_or_404(Camp, pk=year)
        workshop = None
        title = 'Nowe warsztaty'
        has_perm_to_edit, is_lecturer = year.are_proposals_open(), True
    else:
        workshop = get_object_or_404(Workshop, year=year, name=name)
        title = workshop.title
        has_perm_to_edit, is_lecturer = can_edit_workshop(workshop, request.user)

    has_perm_to_see_all = request.user.has_perm('wwwapp.see_all_workshops')
    if workshop and not has_perm_to_edit and not has_perm_to_see_all:
        return HttpResponseForbidden()

    if workshop and request.method == 'POST' and 'qualify' in request.POST:
        if not request.user.has_perm('wwwapp.change_workshop_status') or not workshop.is_workshop_editable():
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
        return redirect('workshop_edit', workshop.year.pk, workshop.name)

    # Generate the parts of the workshop URL displayed in the workshop slug editor
    workshop_url = request.build_absolute_uri(
        reverse('workshop_page', kwargs={'year': 9999, 'name': 'SOMENAME'}))
    workshop_url = workshop_url.split('SOMENAME')
    workshop_url[0:1] = workshop_url[0].split('9999')

    profile_warnings = []
    if is_lecturer:  # The user is one of the lecturers for this workshop
        if len(request.user.userprofile.profile_page) <= 50:  # The user does not have their profile page filled in
            profile_warnings.append(Template("""
                    <strong>Nie uzupełnił{% if user.userprofile.gender == 'F' %}aś{% else %}eś{% endif %} swojej
                    <a target="_blank" href="{% url 'mydata_profile_page' %}">strony profilowej</a>.</strong>
                    Powiedz potencjalnym uczestnikom coś więcej o sobie!
                """).render(Context({'user': request.user})))

    if workshop or has_perm_to_edit:
        workshop_template = Article.objects.get(
            name="template_for_workshop_page").content

        if not workshop:
            initial_workshop = Workshop()
            initial_workshop.year = year
        else:
            initial_workshop = workshop

        if request.method == 'POST' and 'qualify' not in request.POST:
            if not has_perm_to_edit:
                return HttpResponseForbidden()
            form = WorkshopForm(request.POST, request.FILES, workshop_url=workshop_url,
                                instance=initial_workshop, has_perm_to_edit=has_perm_to_edit,
                                has_perm_to_disable_uploads=request.user.has_perm('wwwapp.edit_all_workshops'),
                                profile_warnings=profile_warnings)
            if form.is_valid():
                new = workshop is None
                workshop = form.save(commit=False)
                if new:
                    assert workshop.year == year
                if workshop.page_content == workshop_template:
                    # If the workshop page was not filled in, do not save the template to db
                    workshop.page_content = ""
                workshop.save()
                form.save_m2m()
                if new:
                    user_profile = UserProfile.objects.get(user=request.user)
                    workshop.lecturer.add(user_profile)
                    workshop.save()
                if new:
                    messages.info(request, format_html(
                        'Twoje zgłoszenie zostało zapisane. Jego status i możliwość dalszej edycji znajdziesz w zakładce "<a href="{}">Status kwalifikacji</a>"',
                        reverse('mydata_status')
                    ))
                else:
                    messages.info(request, 'Zapisano.', extra_tags='auto-dismiss')
                return redirect('workshop_edit', form.instance.year.pk, form.instance.name)
        else:
            if workshop and workshop.is_publicly_visible() and not workshop.page_content:
                workshop.page_content = workshop_template
            form = WorkshopForm(instance=initial_workshop, workshop_url=workshop_url, has_perm_to_edit=has_perm_to_edit,
                                has_perm_to_disable_uploads=request.user.has_perm('wwwapp.edit_all_workshops'),
                                profile_warnings=profile_warnings)
    else:
        form = None

    context = {}
    context['title'] = title
    context['workshop'] = workshop
    context['is_lecturer'] = is_lecturer
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = has_perm_to_edit or has_perm_to_see_all

    context['form'] = form

    return render(request, 'workshopedit.html', context)


def legacy_workshop_redirect_view(request, name):
    # To keep the old links working
    # Workshops from editions <= 2020 should be unique
    workshop = get_object_or_404(Workshop.objects.filter(name=name).order_by('year')[:1])
    return redirect('workshop_page', workshop.year.pk, workshop.name, permanent=True)


def legacy_qualification_problems_redirect_view(request, name):
    # To keep the old links working
    # Workshops from editions <= 2020 should be unique
    workshop = get_object_or_404(Workshop.objects.filter(name=name).order_by('year')[:1])
    return redirect('qualification_problems', workshop.year.pk, workshop.name, permanent=True)


@login_required()
def workshop_participants_view(request, year, name):
    workshop = get_object_or_404(Workshop, year__pk=year, name=name)
    has_perm_to_edit, is_lecturer = can_edit_workshop(workshop, request.user)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")

    if not (has_perm_to_edit or request.user.has_perm('wwwapp.see_all_workshops')):
        return HttpResponseForbidden()

    context = {}
    context['title'] = workshop.title
    context['workshop'] = workshop
    context['is_lecturer'] = is_lecturer
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = True

    context['workshop_participants'] = WorkshopParticipant.objects.filter(workshop=workshop).select_related(
            'workshop', 'workshop__year', 'participant', 'participant__user', 'solution')

    for participant in context['workshop_participants']:
        participant.form = WorkshopParticipantPointsForm(instance=participant, auto_id='%s_'+str(participant.id))
    
    return render(request, 'workshopparticipants.html', context)


@require_POST
def save_points_view(request):
    if 'id' not in request.POST:
        raise SuspiciousOperation()

    workshop_participant = WorkshopParticipant.objects.get(id=request.POST['id'])

    has_perm_to_edit, _is_lecturer = can_edit_workshop(workshop_participant.workshop, request.user)
    if not has_perm_to_edit:
        return HttpResponseForbidden()

    if not workshop_participant.workshop.is_qualifying:
        return HttpResponseForbidden("Na te warsztaty nie obowiązuje kwalifikacja")

    if workshop_participant.workshop.solution_uploads_enabled and not hasattr(workshop_participant, 'solution'):
        return HttpResponseForbidden("Nie przesłano rozwiązań")

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
    participants = UserProfile.objects \
        .select_related('user') \
        .prefetch_related(
        'workshop_profile',
        'workshop_profile__year',
        'lecturer_workshops',
        'lecturer_workshops__year',
    )

    if year is not None:
        year = get_object_or_404(Camp, pk=year)
        participants = participants.filter(workshops__year=year)

        lecturers = Workshop.objects.filter(year=year).values_list('lecturer__user__id').distinct()
        participants = participants.exclude(user__id__in=lecturers)

        participants = participants.prefetch_related(
            Prefetch('workshopparticipant_set', queryset=WorkshopParticipant.objects.filter(workshop__year=year)),
            'workshopparticipant_set__workshop',
            'workshopparticipant_set__workshop__year',
        )

    participants = participants.all()

    all_forms = Form.visible_objects.prefetch_related('questions').filter(questions__answers__user__userprofile__in=participants).distinct()
    all_questions = [question for form in all_forms for question in form.questions.all()]
    all_answers = FormQuestionAnswer.objects.prefetch_related('question', 'user').filter(user__userprofile__in=participants, question__in=all_questions).all()

    people = {}

    for participant in participants:
        answers = [next(filter(lambda a: a.question == question and a.user == participant.user, all_answers), None) for question in all_questions]

        # TODO: this is a kinda ugly way of doing it - is_adult is calculate from the first filled in field of type PESEL
        pesel_answer = next(filter(lambda x: x[0].data_type == FormQuestion.TYPE_PESEL and x[1] and x[1].value_string, zip(all_questions, answers)), None)
        pesel = pesel_answer[1].value_string if pesel_answer else None

        birth = pesel_extract_date(pesel)
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
            'form_answers': answers,
        }

        if year:
            for wp in participant.workshopparticipant_set.all():
                assert wp.workshop.year == year
                if wp.workshop.is_qualifying:
                    if wp.qualification_result:
                        people[participant.id]['points'] += float(wp.result_in_percent())
                    if wp.workshop.solution_uploads_enabled and not hasattr(wp, 'solution'):
                        people[participant.id]['infos'].append("{title} : Nie przesłano rozwiązań".format(
                            title=wp.workshop.title
                        ))
                    else:
                        people[participant.id]['infos'].append("{title} : {result:.1f}% : {comment}".format(
                            title=wp.workshop.title,
                            result=wp.result_in_percent() if wp.qualification_result else 0,
                            comment=wp.comment if wp.comment else ""
                        ))
                else:
                    people[participant.id]['infos'].append("{title} : Warsztaty bez kwalifikacji".format(
                        title=wp.workshop.title
                    ))
                people[participant.id]['workshop_count'] += 1
                if wp.is_qualified():
                    people[participant.id]['accepted_workshop_count'] += 1

    people = list(people.values())

    context = {}
    context['title'] = ('Uczestnicy: %s' % year) if year is not None else 'Wszyscy ludzie'
    context['people'] = people
    context['form_questions'] = all_questions
    context['is_all_people'] = year is None

    context['selected_year'] = year
    return render(request, 'participants.html', context)


@login_required()
@permission_required('wwwapp.see_all_users', raise_exception=True)
def lecturers_view(request: HttpRequest, year: int) -> HttpResponse:
    year = get_object_or_404(Camp, pk=year)

    workshops = Workshop.objects.filter(year=year, status=Workshop.STATUS_ACCEPTED).prefetch_related('lecturer', 'lecturer__user')

    people: Dict[int, Dict[str, any]] = {}
    for workshop in workshops:
        for lecturer in workshop.lecturer.all():
            if lecturer.id in people:
                people[lecturer.id]['workshops'].append(workshop)
                continue

            people[lecturer.id] = {
                'user': lecturer.user,
                'workshops': [workshop],
            }

    people_list = list(people.values())

    all_forms = Form.visible_objects.prefetch_related('questions').filter(questions__answers__user__in=[p['user'] for p in people_list]).distinct()
    all_questions = [question for form in all_forms for question in form.questions.all()]
    all_answers = FormQuestionAnswer.objects.prefetch_related('question', 'user').filter(user__in=[p['user'] for p in people_list], question__in=all_questions).all()
    for lecturer in people_list:
        lecturer['form_answers'] = [next(filter(lambda a: a.question == question and a.user == lecturer['user'], all_answers), None) for question in all_questions]

    context = {}
    context['title'] = 'Prowadzący: %s' % year
    context['form_questions'] = all_questions
    context['people'] = people_list

    context['selected_year'] = year
    return render(request, 'lecturers.html', context)


@require_POST
def register_to_workshop_view(request, year, name):
    if not request.user.is_authenticated:
        return JsonResponse({'redirect': reverse('login'), 'error': u'Jesteś niezalogowany'})

    workshop = get_object_or_404(Workshop.objects.prefetch_related('lecturer', 'lecturer__user', 'type', 'category'), year__pk=year, name=name)

    if not workshop.is_qualification_editable():
        return JsonResponse({'error': u'Kwalifikacja na te warsztaty została zakończona.'})

    _, created = WorkshopParticipant.objects.get_or_create(participant=UserProfile.objects.get(user=request.user), workshop=workshop)

    context = {}
    context['workshop'] = workshop
    context['registered'] = True
    content = render(request, '_programworkshop.html', context).content.decode()
    if created:
        return JsonResponse({'content': content})
    else:
        return JsonResponse({'content': content, 'error': u'Już jesteś zapisany na te warsztaty'})


@require_POST
def unregister_from_workshop_view(request, year, name):
    if not request.user.is_authenticated:
        return JsonResponse({'redirect': reverse('login'), 'error': u'Jesteś niezalogowany'})

    workshop = get_object_or_404(Workshop.objects.prefetch_related('lecturer', 'lecturer__user', 'type', 'category'), year__pk=year, name=name)
    profile = UserProfile.objects.get(user=request.user)
    workshop_participant = WorkshopParticipant.objects.filter(workshop=workshop, participant=profile).first()

    if not workshop.is_qualification_editable():
        return JsonResponse({'error': u'Kwalifikacja na te warsztaty została zakończona.'})

    if workshop_participant:
        if workshop_participant.qualification_result is not None or workshop_participant.comment:
            return JsonResponse({'error': u'Masz już wyniki z tej kwalifikacji - nie możesz się wycofać.'})

        if hasattr(workshop_participant, 'solution'):
            return JsonResponse({'error': u'Nie możesz wycofać się z warsztatów, na które przesłałeś już rozwiązania.'})

        workshop_participant.delete()

    context = {}
    context['workshop'] = workshop
    context['registered'] = False
    content = render(request, '_programworkshop.html', context).content.decode()
    if workshop_participant:
        return JsonResponse({'content': content})
    else:
        return JsonResponse({'content': content, 'error': u'Nie jesteś zapisany na te warsztaty'})


@login_required()
def workshop_solution(request, year, name, solution_id=None):
    workshop = get_object_or_404(Workshop, year__pk=year, name=name)
    if not workshop.is_publicly_visible():
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")
    if not workshop.can_access_solution_upload():
        return HttpResponseForbidden('Na te warsztaty nie można obecnie przesyłać rozwiązań')
    has_perm_to_edit, is_lecturer = can_edit_workshop(workshop, request.user)

    if solution_id is None:
        # My solution
        try:
            workshop_participant = workshop.workshopparticipant_set \
                .select_related('solution', 'participant__user') \
                .get(participant__user=request.user)
        except WorkshopParticipant.DoesNotExist:
            return HttpResponseForbidden('Nie jesteś zapisany na te warsztaty')
        solution = workshop_participant.solution if hasattr(workshop_participant, 'solution') else None
        if not solution:
            if workshop.are_solutions_editable():
                solution = Solution(workshop_participant=workshop_participant)
            else:
                return HttpResponseForbidden('Nie przesłałeś rozwiązania na te warsztaty')
    else:
        # Selected solution
        if not has_perm_to_edit and not request.user.has_perm('wwwapp.see_all_workshops'):
            return HttpResponseForbidden()
        solution = get_object_or_404(
            Solution.objects
                .select_related('workshop_participant', 'workshop_participant__participant__user')
                .filter(workshop_participant__workshop=workshop),
            pk=solution_id)

    is_solution_editable = solution_id is None and workshop.is_qualification_editable()
    form = SolutionForm(instance=solution, is_editable=is_solution_editable)
    formset = SolutionFileFormSet(instance=solution, is_editable=is_solution_editable)
    grading_form = WorkshopParticipantPointsForm(instance=solution.workshop_participant, participant_view=solution_id is None)

    if request.method == 'POST' and solution_id is None:
        if not is_solution_editable:
            return HttpResponseForbidden()
        form = SolutionForm(request.POST, request.FILES, instance=solution, is_editable=is_solution_editable)
        formset = SolutionFileFormSet(request.POST, request.FILES, instance=solution, is_editable=is_solution_editable)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.info(request, 'Zapisano.', extra_tags='auto-dismiss')
            return redirect('workshop_my_solution', year, name)
    if request.method == 'POST' and solution_id is not None:
        if not has_perm_to_edit:
            return HttpResponseForbidden()
        grading_form = WorkshopParticipantPointsForm(request.POST, instance=solution.workshop_participant)
        if grading_form.is_valid():
            grading_form.save()
            messages.info(request, 'Zapisano.')
            return redirect('workshop_solution', year, name, solution.pk)

    context = {}
    context['title'] = workshop.title
    context['workshop'] = workshop
    context['solution'] = solution
    context['form'] = form
    context['form_attachments'] = formset
    context['grading_form'] = grading_form
    context['is_editable'] = is_solution_editable
    context['is_mine'] = solution_id is None
    context['is_lecturer'] = is_lecturer
    context['has_perm_to_edit'] = has_perm_to_edit
    context['has_perm_to_view_details'] = has_perm_to_edit or request.user.has_perm('wwwapp.see_all_workshops')
    return render(request, 'workshopsolution.html', context)


@login_required()
def workshop_solution_file(request, year, name, file_pk, solution_id=None):
    workshop = get_object_or_404(Workshop, year__pk=year, name=name)
    if not workshop.is_publicly_visible():
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")
    if not workshop.can_access_solution_upload():
        return HttpResponseForbidden('Na te warsztaty nie można obecnie przesyłać rozwiązań')

    if not solution_id:
        # My solution
        try:
            workshop_participant = workshop.workshopparticipant_set \
                .select_related('solution', 'participant__user') \
                .get(participant__user=request.user)
        except WorkshopParticipant.DoesNotExist:
            return HttpResponseForbidden('Nie jesteś zapisany na te warsztaty')
        solution = workshop_participant.solution if hasattr(workshop_participant, 'solution') else None
        if not solution:
            return HttpResponseForbidden('Nie przesłałeś rozwiązania na te warsztaty')
    else:
        # Selected solution
        has_perm_to_edit, _is_lecturer = can_edit_workshop(workshop, request.user)
        if not has_perm_to_edit and not request.user.has_perm('wwwapp.see_all_workshops'):
            return HttpResponseForbidden()
        solution = get_object_or_404(
            Solution.objects
                .select_related('workshop_participant', 'workshop_participant__participant__user')
                .filter(workshop_participant__workshop=workshop),
            pk=solution_id)

    solution_file = get_object_or_404(solution.files.all(), pk=file_pk)
    return sendfile(request, solution_file.file.path)


@permission_required('wwwapp.export_workshop_registration')
def data_for_plan_view(request, year: int) -> HttpResponse:
    year = get_object_or_404(Camp, pk=year)

    data = {}

    participant_profiles_raw = UserProfile.objects.filter(workshop_profile__year=year, workshop_profile__status='Z')

    lecturer_profiles_raw = set()
    workshop_ids = set()
    workshops = []
    for workshop in Workshop.objects.filter(status='Z', year=year):
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

    current_year = Camp.current()
    for user_type, profiles in [('Lecturer', lecturer_profiles_raw),
                                ('Participant', participant_profiles_raw)]:
        for up in profiles:
            user = {
                'uid': up.id,
                'name': up.user.get_full_name(),
                'type': user_type,
            }
            users.append(user)
            user_ids.add(up.id)

    if year == current_year:
        # TODO: Form data is valid for the current year only
        start_dates = {answer.user.userprofile.id: answer.value_date for answer in FormQuestionAnswer.objects.prefetch_related('user', 'user__userprofile').filter(question=F('question__form__arrival_date'), question__form__is_visible=True, user__userprofile__in=user_ids, value_date__isnull=False)}
        end_dates = {answer.user.userprofile.id: answer.value_date for answer in FormQuestionAnswer.objects.prefetch_related('user', 'user__userprofile').filter(question=F('question__form__departure_date'), question__form__is_visible=True, user__userprofile__in=user_ids, value_date__isnull=False)}

        for user in users:
            start_date = start_dates[user['uid']] if user['uid'] in start_dates else None
            end_date = end_dates[user['uid']] if user['uid'] in end_dates else None

            user.update({
                'start': clean_date(start_date, year.start_date, year.end_date, year.start_date),
                'end': clean_date(end_date, year.start_date, year.end_date, year.end_date)
            })

    data['users'] = users

    participation = []
    for wp in WorkshopParticipant.objects.filter(workshop__id__in=workshop_ids, participant__id__in=user_ids):
        participation.append({
            'wid': wp.workshop.id,
            'uid': wp.participant.id,
        })
    data['participation'] = participation

    return JsonResponse(data, json_dumps_params={'indent': 4})


def qualification_problems_view(request, year, name):
    workshop = get_object_or_404(Workshop, year__pk=year, name=name)

    if not workshop.is_publicly_visible():  # Accepted or cancelled
        return HttpResponseForbidden("Warsztaty nie zostały zaakceptowane")
    if not workshop.is_qualifying:
        return HttpResponseNotFound("Na te warsztaty nie ma kwalifikacji")
    if not workshop.qualification_problems:
        return HttpResponseNotFound("Nie ma jeszcze zadań kwalifikacyjnych")

    return sendfile(request, workshop.qualification_problems.path)


def article_view(request, name):
    context = {}

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
    context = {}
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

    article_url = request.build_absolute_uri(
        reverse('article', kwargs={'name': 'SOMENAME'}))
    article_url = article_url.split('SOMENAME')
    if art and art.name in ArticleForm.SPECIAL_ARTICLES.keys():
        title = ArticleForm.SPECIAL_ARTICLES[art.name]

    if request.method == 'POST':
        form = ArticleForm(request.user, article_url, request.POST, instance=art)
        if form.is_valid():
            article = form.save(commit=False)
            article.modified_by = request.user
            article.save()
            form.save_m2m()
            messages.info(request, 'Zapisano.', extra_tags='auto-dismiss')
            return redirect('article', form.instance.name)
    else:
        form = ArticleForm(request.user, article_url, instance=art)

    context['title'] = title
    context['article'] = art
    context['form'] = form

    return render(request, 'articleedit.html', context)


def article_name_list_view(request):
    articles = Article.objects.all()
    article_list = [{'title': 'Artykuł: ' + (article.title or article.name), 'value': reverse('article', kwargs={'name': article.name})} for article in articles]

    workshops = Workshop.objects.filter(Q(status='Z') | Q(status='X')).order_by('-year')
    workshop_list = [{'title': 'Warsztaty (' + str(workshop.year) + '): ' + workshop.title, 'value': reverse('workshop_page', kwargs={'year': workshop.year.pk, 'name': workshop.name})} for workshop in workshops]

    return JsonResponse(article_list + workshop_list, safe=False)


@login_required()
@permission_required('wwwapp.see_all_workshops', raise_exception=True)
def workshops_view(request, year):
    year = get_object_or_404(Camp.objects.prefetch_related(
        'workshops',
        'workshops__year',
        'workshops__lecturer',
        'workshops__lecturer__user',
        'workshops__type',
        'workshops__type__year',
        'workshops__category',
        'workshops__category__year',
    ), pk=year)

    context = {}
    context['workshops'] = year.workshops.all()
    context['title'] = 'Warsztaty: %s' % year

    context['selected_year'] = year
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


def _upload_file(request, target_dir):
    """
    Handle a file upload from TinyMCE
    """

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


@login_required()
@require_POST
@csrf_exempt
def article_edit_upload_file(request, name):
    article = get_object_or_404(Article, name=name)
    target_dir = "images/articles/{}/".format(article.name)
    if not request.user.has_perm('wwwapp.change_article'):
        return HttpResponseForbidden()

    return _upload_file(request, target_dir)


@login_required()
@require_POST
@csrf_exempt
def workshop_edit_upload_file(request, year, name):
    workshop = get_object_or_404(Workshop, year__pk=year, name=name)
    has_perm_to_edit, _is_lecturer = can_edit_workshop(workshop, request.user)
    if not has_perm_to_edit or not workshop.is_publicly_visible() or not workshop.is_workshop_editable():
        return HttpResponseForbidden()
    target_dir = "images/workshops/{}/{}/".format(workshop.year.pk, workshop.name)

    return _upload_file(request, target_dir)
