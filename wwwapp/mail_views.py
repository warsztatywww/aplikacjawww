from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, get_object_or_404

from .forms import MailFilterForm
from .models import Workshop, CampParticipant, Camp
from .views import get_context

_registered_filters = dict()


def _register_as_email_filter(filter_id, name):
    def decorator(method):
        if filter_id in _registered_filters and _registered_filters[filter_id] != method:
            raise NameError("Filter '{}' already registered!".format(name))
        _registered_filters[filter_id] = (method, name)
        return method
    return decorator


@_register_as_email_filter('all', 'wszyscy (uczestnicy zainteresowani tegoroczną edycją oraz prowadzący)')
def _all(year):
    return set(_all_participants(year)) | set(_all_lecturers(year))


@_register_as_email_filter('allRegistered', 'wszyscy (uczestnicy zapisani na co najmniej jeden warsztat oraz prowadzący)')
def _all_registered(year):
    return set(_all_registered_participants(year)) | set(_all_lecturers(year))


def _get_user_objects_of_lecturers_of_workshops(workshops):
    users = set()
    for workshop in workshops:
        for user_profile in workshop.lecturer.all():
            users.add(user_profile.user)
    return users


@_register_as_email_filter('allLecturers', 'wszyscy prowadzący')
def _all_lecturers(year):
    all_workshops = year.workshops.all()
    return _get_user_objects_of_lecturers_of_workshops(all_workshops)


@_register_as_email_filter('acceptedLecturers', 'prowadzący zaakceptowanych warsztatów')
def _accepted_lecturers(year):
    accepted_workshops = year.workshops.filter(status=Workshop.STATUS_ACCEPTED)
    return _get_user_objects_of_lecturers_of_workshops(accepted_workshops)


@_register_as_email_filter('deniedLecturers', 'prowadzący odrzuconych warsztatów')
def _denied_lecturers(year):
    denied_workshops = year.workshops.filter(status=Workshop.STATUS_REJECTED)
    return _get_user_objects_of_lecturers_of_workshops(denied_workshops)


@_register_as_email_filter('allParticipants', 'wszyscy uczestnicy zainteresowani tegoroczną edycją')
def _all_participants(year):
    return [profile.user_profile.user for profile in
            year.participants.all() if not profile.user_profile.lecturer_workshops.filter(year=year).exists()]


@_register_as_email_filter('allNotRegisteredParticipants', 'wszyscy uczestnicy zainteresowani tegoroczną edycją, którzy nie zapisali się jeszcze na żaden warsztat')
def _all_not_registered_participants(year):
    return [profile.user_profile.user for profile in
            year.participants.all() if not profile.workshop_participation.exists() and not profile.user_profile.lecturer_workshops.filter(year=year).exists()]


@_register_as_email_filter('allRegisteredParticipants', 'wszyscy uczestnicy zapisani na co najmniej jeden warsztat')
def _all_registered_participants(year):
    all_workshops = Workshop.objects.filter(year=year)
    registered_users = set()
    for workshop in all_workshops:
        for participant in workshop.participants.all():
            registered_users.add(participant.camp_participation.user_profile)
    return [user_profile.user for user_profile in
            registered_users if not user_profile.lecturer_workshops.filter(year=year).exists()]


@_register_as_email_filter('allQualified', 'wszyscy uczestnicy o statusie zakwalifikowanym')
def _all_qualified(year):
    return [profile.user_profile.user for profile in
            year.participants.all() if profile.status == 'Z']


@_register_as_email_filter('allRefused', 'wszyscy uczestnicy o statusie odrzuconym')
def _all_refused(year):
    return [profile.user_profile.user for profile in
            year.participants.all() if profile.status == 'O']


@login_required()
@permission_required('wwwapp.see_all_users', raise_exception=True)
def filtered_emails_view(request, year):
    context = get_context(request)
    year = get_object_or_404(Camp, pk=year)

    if request.method == 'POST':
        form = MailFilterForm(_registered_filters, request.POST)
        if form.is_valid():
            context['show_results'] = True
            context['chosen_filter_name'] = form.filter_name
            context['filtered_users'] = form.filter_method(year)
    else:
        form = MailFilterForm(_registered_filters)

    context['title'] = 'Filtrowane emaile użytkowników'
    context['form'] = form

    context['selected_year'] = year
    return render(request, 'filteredEmails.html', context)
