import datetime
import os
import threading
import urllib.parse
from typing import Set, Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, SuspiciousOperation
from django.core.files.storage import FileSystemStorage
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import QuerySet, Count, F, When, Case, Max, DecimalField
from django.db.models.functions import Greatest, Least
from django.db.models.query_utils import Q
from django.db.models.signals import post_save, pre_delete
from django.dispatch.dispatcher import receiver
from django.utils import timezone
from django.utils.deconstruct import deconstructible

import wwwforms.models


# This is a separate directory for Django-controlled uploaded files.
# Unlike /media, this directory is not directly externally accesible,
# but it still needs to be configured in nginx (with internal;) for
# X-Accel-Redirect to work.
# See https://www.nginx.com/resources/wiki/start/topics/examples/xsendfile/
@deconstructible
class UploadStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, location=settings.SENDFILE_ROOT, base_url=settings.SENDFILE_URL, **kwargs)


_latest_camp = threading.local()


class Camp(models.Model):
    year = models.IntegerField(primary_key=True, null=False, blank=False)
    proposal_end_date = models.DateField(null=True, blank=True)
    program_finalized = models.BooleanField(default=False)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    forms = models.ManyToManyField(wwwforms.models.Form, blank=True, related_name='years', verbose_name='Formularze')
    form_question_birth_date = models.ForeignKey(wwwforms.models.FormQuestion, blank=True, null=True, on_delete=models.SET_NULL, related_name='+', verbose_name='Data urodzenia', help_text='Pole typu Data lub PESEL')
    form_question_arrival_date = models.ForeignKey(wwwforms.models.FormQuestion, blank=True, null=True, on_delete=models.SET_NULL, related_name='+', verbose_name='Data przyjazdu', help_text='Pole typu Data')
    form_question_departure_date = models.ForeignKey(wwwforms.models.FormQuestion, blank=True, null=True, on_delete=models.SET_NULL, related_name='+', verbose_name='Data wyjazdu', help_text='Pole typu Data')

    def clean(self):
        if (self.start_date is not None) != (self.end_date is not None):
            raise ValidationError('Daty rozpoczęcia i zakończenia muszą być albo ustawione, albo nieustawione')
        if (self.proposal_end_date is not None) and (self.start_date is not None) and self.proposal_end_date > self.start_date:
            raise ValidationError('Data zakończenia przyjmowania propozycji warsztatów nie może być późniejsza niż data ich rozpoczęcia')

        if self.form_question_birth_date and not self.forms.filter(pk=self.form_question_birth_date.form.pk).exists():
            raise ValidationError({'form_question_birth_date': 'Musi być z tegorocznego formularza'})
        if self.form_question_birth_date and self.form_question_birth_date.data_type not in (wwwforms.models.FormQuestion.TYPE_DATE, wwwforms.models.FormQuestion.TYPE_PESEL):
            raise ValidationError({'form_question_birth_date': 'Musi być datą lub PESELem'})

        if self.form_question_arrival_date and not self.forms.filter(pk=self.form_question_arrival_date.form.pk).exists():
            raise ValidationError({'form_question_arrival_date': 'Musi być z tegorocznego formularza'})
        if self.form_question_departure_date and not self.forms.filter(pk=self.form_question_departure_date.form.pk).exists():
            raise ValidationError({'form_question_departure_date': 'Musi być z tegorocznego formularza'})
        if self.form_question_arrival_date and self.form_question_departure_date and self.form_question_arrival_date.form != self.form_question_departure_date.form:
            raise ValidationError({'form_question_arrival_date': 'Muszą być z tego samego formularza', 'form_question_departure_date': 'Muszą być z tego samego formularza'})
        if self.form_question_arrival_date and self.form_question_arrival_date.data_type != wwwforms.models.FormQuestion.TYPE_DATE:
            raise ValidationError({'form_question_arrival_date': 'Musi być datą'})
        if self.form_question_departure_date and self.form_question_departure_date.data_type != wwwforms.models.FormQuestion.TYPE_DATE:
            raise ValidationError({'form_question_departure_date': 'Musi być datą'})
        if self.form_question_arrival_date and self.form_question_departure_date and self.form_question_arrival_date == self.form_question_departure_date:
            raise ValidationError({'form_question_arrival_date': 'Muszą być różnymi polami', 'form_question_departure_date': 'Muszą być różnymi polami'})
        if bool(self.form_question_arrival_date) != bool(self.form_question_departure_date):
            raise ValidationError({'form_question_arrival_date': 'Muszą być oba ustawione lub oba nieustawione', 'form_question_departure_date': 'Muszą być oba ustawione lub oba nieustawione'})

        super().clean()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        get_latest_by = 'year'
        ordering = ['year']

    def __str__(self):
        return 'WWW%d (%d)' % (self.year % 100 - 4, self.year)

    def is_program_finalized(self) -> bool:
        return not self.is_qualification_editable() or self.program_finalized

    def are_proposals_open(self) -> bool:
        if self.proposal_end_date:
            return self.are_workshops_editable() and datetime.datetime.now().date() <= self.proposal_end_date
        elif self.start_date:
            return self.are_workshops_editable() and datetime.datetime.now().date() < self.start_date
        else:
            return self.are_workshops_editable()

    def are_workshops_editable(self) -> bool:
        return self == Camp.current()

    def is_qualification_editable(self) -> bool:
        if self.start_date:
            return self.are_workshops_editable() and datetime.datetime.now().date() < self.start_date
        else:
            return self.are_workshops_editable()

    def are_solutions_editable(self) -> bool:
        return self.is_qualification_editable()

    @staticmethod
    def current():
        if hasattr(_latest_camp, 'v'):
            return _latest_camp.v
        else:
            return Camp.objects.latest()


def cache_latest_camp_middleware(get_response):
    def middleware(request):
        _latest_camp.v = Camp.objects.latest()
        response = get_response(request)
        del _latest_camp.v
        return response
    return middleware


@receiver(pre_delete, sender=Camp)
def protect_last_camp(sender, instance, using, **kwargs):
    # I'm way too lazy to check if current_year exists everywhere,
    # and that scenario will not really ever happen in production

    # The add_camp_model migration makes sure that the initial Camp object is created
    if not Camp.objects.exclude(pk=instance.pk).exists():
        # TODO: This does not display a nice message in the admin panel for some reason but who cares
        raise ValidationError('At least one Camp object must exist')


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='user_profile')

    gender = models.CharField(max_length=10, choices=[('M', 'Mężczyzna'), ('F', 'Kobieta'),],
                              null=True, default=None, blank=True)
    school = models.CharField(max_length=100, default="", blank=True)
    matura_exam_year = models.PositiveSmallIntegerField(null=True, default=None, blank=True)
    how_do_you_know_about = models.CharField(max_length=1000, default="", blank=True)
    profile_page = models.TextField(max_length=100000, blank=True, default="")
    secret_notes = models.TextField(max_length=100000, blank=True, default="")

    def is_participating_in(self, year: Camp) -> bool:
        return self.is_participant_in(year) or self.is_lecturer_in(year)

    def is_participant_in(self, year: Camp) -> bool:
        return self.camp_participation_status_for(year) == 'Z'

    def is_lecturer_in(self, year: Camp) -> bool:
        return self.lecturer_workshops.filter(year=year, status='Z').exists()

    def all_participation_data(self):
        """
        Returns the participation data from CampParticipant objects joined with data about lectures
        """

        data = []

        # Get data from CampParticipiant objects
        for camp_participant in self.camp_participation.all():
            data.append({'year': camp_participant.year, 'status': camp_participant.status, 'type': 'participant', 'workshops': [], 'camp_participant': camp_participant})

        # Get data about lectures
        lecturer_workshops = self.lecturer_workshops.all()
        for year in set([workshop.year for workshop in lecturer_workshops]):
            lecturer_workshops_for_year = [x for x in lecturer_workshops if x.year == year]

            data_for_year = next(filter(lambda x: x['year'] == year, data), None)
            if not data_for_year:
                data_for_year = {'year': year, 'status': None, 'type': 'lecturer', 'workshops': lecturer_workshops_for_year, 'camp_participant': None}
                data.append(data_for_year)
            else:
                data_for_year['workshops'] = lecturer_workshops_for_year

            # If the user was a participant, their participation status takes precedence
            # Otherwise, use the lecturer status
            if not data_for_year['status']:
                # If there was at least one accepted workshop, the lecturer was accepted. Otherwise, if at least one
                # workshop was cancelled, the participation of the lecturer was cancelled. Otherwise, the lecturer
                # was rejected.
                if any(workshop.status == 'Z' for workshop in lecturer_workshops_for_year):
                    data_for_year['status'] = 'Z'
                elif any(workshop.status == 'X' for workshop in lecturer_workshops_for_year):
                    data_for_year['status'] = 'X'
                elif all(workshop.status for workshop in lecturer_workshops_for_year):
                    data_for_year['status'] = 'O'
                else:
                    data_for_year['status'] = None
                data_for_year['type'] = 'lecturer'

        data.sort(key=lambda x: -x['year'].year)
        return data

    def workshop_results_by_year(self):
        participation_data = self.all_participation_data()
        for p in participation_data:
            if p['camp_participant']:
                p['qualification_results'] = p['camp_participant'].workshop_participation.all()
            else:
                p['qualification_results'] = []
        return participation_data

    def all_participation_years(self) -> Set[Camp]:
        """
        All years user was qualified or had a lecture
        :return: list of years (integers)
        """
        return self.participant_years().union(self.lecturer_years())

    def participant_years(self) -> Set[Camp]:
        """
        Years user qualified
        :return: list of years (integers)
        """
        return set([profile.year for profile in self.camp_participation.filter(status=CampParticipant.STATUS_ACCEPTED)])

    def lecturer_years(self) -> Set[Camp]:
        """
        Years user had a lecture
        :return: list of years (integers)
        """
        return set([workshop.year for workshop in self.lecturer_workshops.filter(status='Z')])

    def camp_participation_status_for(self, year: Camp) -> Optional[str]:
        profile = self.camp_participation_for(year)
        return profile.status if profile else None

    def camp_participation_for(self, year: Camp) -> Optional['CampParticipant']:
        try:
            return self.camp_participation.get(year=year)
        except CampParticipant.DoesNotExist:
            return None

    @property
    def is_completed(self) -> bool:
        """
        Check if all required info (except cover letter and profile page) is filled in
        """
        return bool(self.gender) and \
               bool(self.school) and \
               bool(self.matura_exam_year) and \
               bool(self.user.first_name) and \
               bool(self.user.last_name) and \
               bool(self.user.email)

    def __str__(self):
        return "{0.first_name} {0.last_name}".format(self.user)

    class Meta:
        permissions = [('see_all_users', 'Can see all users'),
                       ('export_workshop_registration', 'Can download workshop registration data'),
                       ('use_secret_notes', 'Can see and edit secret notes about users')]


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)


class CampParticipant(models.Model):
    # for each year
    STATUS_ACCEPTED = 'Z'
    STATUS_REJECTED = 'O'
    STATUS_CANCELLED = 'X'
    STATUS_CHOICES = [
        (STATUS_ACCEPTED, 'Zaakceptowany'),
        (STATUS_REJECTED, 'Odrzucony'),
        (STATUS_CANCELLED, 'Odwołany')
    ]

    year = models.ForeignKey(Camp, on_delete=models.PROTECT, related_name='participants')
    user_profile = models.ForeignKey('UserProfile', null=True, related_name='camp_participation', on_delete=models.CASCADE)

    cover_letter = models.TextField(max_length=100000, blank=True, default="")

    status = models.CharField(max_length=10,
                              choices=STATUS_CHOICES,
                              null=True, default=None, blank=True)

    class Meta:
        unique_together = ('user_profile', 'year')

    def __str__(self):
        return '%s: %s, %s' % (self.year, self.user_profile, self.status)

    # Unlike the Workshop and WorkshopParticipant list counts, the CampParticipant list counts are not calculated on the database side
    # The reason behind that is that:
    # 1) Using WorkshopParticipant.is_qualified from a custom WorkshopParticipant manager in a CampParticipant manager is not supported by Django
    # 2) For a good reason: the resulting query would become big and pretty cursed
    # 3) We need to fetch all WorkshopParticipant objects for display on the tooltip anyway...
    # All of these methods make sure that you prefetched workshop_participation, to avoid accidental N+1 errors. Make
    # sure to not perform any operations that can't be fetched from the prefetch cache in these methods (no .count,
    # no .filter, only .all and iterate the data on the Python side)

    def _ensure_wp_prefetched(self):
        if not hasattr(self, '_prefetched_objects_cache') or 'workshop_participation' not in self._prefetched_objects_cache:
            raise AttributeError('Please prefetch workshop_participation before using the count methods')
        for wp in self.workshop_participation.all():
            if not WorkshopParticipant.workshop.is_cached(wp):
                raise AttributeError('Please prefetch workshop_participation__workshop before using the count methods')

    def _ensure_wp_and_solutions_prefetched(self):
        self._ensure_wp_prefetched()
        for wp in self.workshop_participation.all():
            if not WorkshopParticipant.solution.is_cached(wp):
                raise AttributeError('Please prefetch workshop_participation__solution before using the count methods')

    @property
    def workshop_count(self):
        self._ensure_wp_prefetched()
        return len(self.workshop_participation.all())

    @property
    def accepted_workshop_count(self):
        self._ensure_wp_prefetched()
        return sum(1 if wp.workshop.is_qualifying and wp.is_qualified else 0 for wp in self.workshop_participation.all())

    @property
    def solution_count(self):
        self._ensure_wp_and_solutions_prefetched()
        return sum(1 if wp.workshop.is_qualifying and wp.workshop.solution_uploads_enabled and hasattr(wp, 'solution') else 0 for wp in self.workshop_participation.all())

    @property
    def to_be_checked_solution_count(self):
        # uploaded solutions + workshops with uploads disabled but scoring enabled (solutions sent outside of the system)
        self._ensure_wp_and_solutions_prefetched()
        no_upload_workshops = sum(1 if wp.workshop.is_qualifying and not wp.workshop.solution_uploads_enabled else 0 for wp in self.workshop_participation.all())
        return self.solution_count + no_upload_workshops

    @property
    def checked_solution_count(self):
        self._ensure_wp_and_solutions_prefetched()
        return sum(1 if wp.workshop.is_qualifying and wp.qualification_result is not None else 0 for wp in self.workshop_participation.all())

    @property
    def checked_solution_percentage(self):
        if self.to_be_checked_solution_count == 0:
            return -1
        else:
            return self.checked_solution_count / self.to_be_checked_solution_count * 100.0

    @property
    def result_in_percent(self):
        self._ensure_wp_prefetched()
        return sum(wp.result_in_percent or 0 for wp in self.workshop_participation.all())


class PESELField(models.CharField):
    system_check_removed_details = {
        'msg': (
            'PESELField has been removed except for support in '
            'historical migrations.'
        ),
        'hint': 'Use wwwforms.FormQuestion with PESEL data type instead.',
        'id': 'wwwapp.E900',
    }


class CampInterestEmail(models.Model):
    year = models.ForeignKey(Camp, on_delete=models.CASCADE, related_name='interested_via_email')
    email = models.EmailField()

    def __str__(self):
        return "{} ({})".format(self.email, self.year_id)

    class Meta:
        unique_together = ('year', 'email',)


class ArticleContentHistory(models.Model):
    version = models.IntegerField(editable=False)
    article = models.ForeignKey('Article', null=True, on_delete=models.SET_NULL, related_name='content_history')
    content = models.TextField()
    modified_by = models.ForeignKey(User, null=True, default=None, on_delete=models.SET_NULL, related_name='+')
    time = models.DateTimeField(auto_now_add=True, null=True, editable=False)

    def __str__(self):
        time = '?'
        if self.time:
            time = self.time.strftime('%y-%m-%d %H:%M')
        return '{} (v{} by {} at {})'.format(
            self.article.name if self.article else '<removed article>', self.version, self.modified_by, time)

    class Meta:
        unique_together = ('version', 'article',)
        ordering = ('article', '-version')

    def save(self, *args, **kwargs):
        # start with version 1 and increment it for each version
        current_version = ArticleContentHistory.objects.filter(article=self.article).order_by('-version')[:1]
        self.version = current_version[0].version + 1 if current_version else 1
        self.modified_by = self.article.modified_by
        super(ArticleContentHistory, self).save(*args, **kwargs)


class Article(models.Model):
    name = models.SlugField(max_length=50, null=False, blank=False, unique=True)
    title = models.CharField(max_length=50, null=True, blank=True)
    content = models.TextField(max_length=100000, blank=True)
    modified_by = models.ForeignKey(User, null=True, default=None, on_delete=models.SET_NULL, related_name='+')
    on_menubar = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0, blank=False, null=False)

    class Meta:
        permissions = (('can_put_on_menubar', 'Can put on menubar'),)
        ordering = ['order']

    def __str__(self):
        return '{} "{}"'.format(self.name, self.title)

    def save(self, *args, **kwargs):
        super(Article, self).save(*args, **kwargs)
        # save summary history
        content_history = self.content_history.all()
        if not content_history or self.content != content_history[0].content:
            new_content = ArticleContentHistory(article=self, content=self.content)
            new_content.save()


class WorkshopCategory(models.Model):
    year = models.ForeignKey(Camp, on_delete=models.PROTECT, editable=False)
    name = models.CharField(max_length=100, blank=False, null=False)

    class Meta:
        unique_together = ('year', 'name',)

    def __str__(self):
        return '%s: %s' % (self.year, self.name)


class WorkshopType(models.Model):
    year = models.ForeignKey(Camp, on_delete=models.PROTECT, editable=False)
    name = models.CharField(max_length=100, blank=False, null=False)

    class Meta:
        unique_together = ('year', 'name',)

    def __str__(self):
        return '%s: %s' % (self.year, self.name)


class WorkshopManager(models.Manager):
    def get_queryset(self) -> QuerySet['Workshop']:
        return super().get_queryset().alias(
            registered_count=Count('participants'),
            solution_count=Case(
                When(is_qualifying=True, solution_uploads_enabled=True, then=Count('participants__solution')),
                default=None
            ),
            checked_solution_count=Case(
                When(is_qualifying=True, solution_uploads_enabled=True, then=Count('participants__qualification_result', filter=Q(participants__solution__isnull=False))),
                When(is_qualifying=True, solution_uploads_enabled=False, then=Count('participants__qualification_result')),
                default=None,
            ),
            qualified_count=Case(
                When(is_qualifying=True, qualification_threshold__isnull=False, then=Count('participants', filter=Q(participants__qualification_result__gte=F('qualification_threshold')))),
                default=None
            ),
        )

    def with_counts(self) -> QuerySet['Workshop']:
        return self.annotate(
            registered_count=F('registered_count'),
            solution_count=F('solution_count'),
            checked_solution_count=F('checked_solution_count'),
            qualified_count=F('qualified_count'),
        )


class Workshop(models.Model):
    """
    Workshop taking place during a specific workshop/year
    """
    STATUS_ACCEPTED = 'Z'
    STATUS_REJECTED = 'O'
    STATUS_CANCELLED = 'X'
    STATUS_CHOICES = [
        (STATUS_ACCEPTED, 'Zaakceptowane'),
        (STATUS_REJECTED, 'Odrzucone'),
        (STATUS_CANCELLED, 'Odwołane')
    ]

    year = models.ForeignKey(Camp, on_delete=models.PROTECT, null=False, related_name='workshops')
    name = models.SlugField(max_length=50, null=False, blank=False)
    title = models.CharField(max_length=50)
    proposition_description = models.TextField(max_length=100000, blank=True)
    type = models.ForeignKey(WorkshopType, on_delete=models.PROTECT, null=False)
    category = models.ManyToManyField(WorkshopCategory, blank=True)
    lecturer = models.ManyToManyField(UserProfile, blank=True, related_name='lecturer_workshops')
    status = models.CharField(max_length=10,
                              choices=STATUS_CHOICES,
                              null=True, default=None, blank=True)
    short_description = models.CharField(max_length=140, blank=True)
    page_content = models.TextField(max_length=100000, blank=True)
    page_content_is_public = models.BooleanField(default=False)

    is_qualifying = models.BooleanField(default=True)
    qualification_problems = models.FileField(null=True, blank=True, upload_to="qualification", storage=UploadStorage())
    solution_uploads_enabled = models.BooleanField(default=True)
    qualification_threshold = models.DecimalField(null=True, blank=True, decimal_places=2, max_digits=6, validators=[MinValueValidator(0)])
    max_points = models.DecimalField(null=True, blank=True, decimal_places=2, max_digits=6, validators=[MinValueValidator(0)])

    objects = WorkshopManager()

    def is_workshop_editable(self) -> bool:
        return self.year.are_workshops_editable()

    def is_qualification_editable(self) -> bool:
        return self.year.is_qualification_editable()

    def are_solutions_editable(self) -> bool:
        return self.year.are_solutions_editable()

    def can_access_solution_upload(self) -> bool:
        """
        Check if all preconditions to be able to access the solution upload form are met. The solution upload form
        can be opened only when the solution uploads are enabled, the workshop is qualifying and the qualification
        problems have been uploaded.
        Note: This does not mean that the solution is currently editable.
        """
        return self.solution_uploads_enabled and self.is_qualifying and self.qualification_problems

    def clean(self):
        super(Workshop, self).clean()
        if hasattr(self, 'year'):
            if hasattr(self, 'type'):
                if self.type.year != self.year:
                    raise ValidationError({'type': 'Typ warsztatów nie jest z tego roku'})
            if self.pk is not None:  # "needs to have an ID before this many-to-many relation can be used"
                for cat in self.category.all():
                    if cat.year != self.year:
                        raise ValidationError({'category': 'Kategoria warsztatów nie jest z tego roku'})
        if self.max_points is None and self.qualification_threshold is not None:
            raise ValidationError('Maksymalna liczba punktów musi być ustawiona jeśli próg kwalifikacji jest ustawiony')

    class Meta:
        base_manager_name = 'objects'
        permissions = (('see_all_workshops', 'Can see all workshops'),
                       ('edit_all_workshops', 'Can edit all workshops'),
                       ('change_workshop_status', 'Can change workshop status'))
        unique_together = ['year', 'name']

    def __str__(self):
        return str(self.year) + ': ' + (' (' + self.status + ') ' if self.status else '') + self.title

    @property
    def to_be_checked_solution_count(self):
        if self.solution_uploads_enabled:
            return self.solution_count
        else:
            return self.registered_count

    @property
    def checked_solution_percentage(self):
        if not self.is_qualifying or self.to_be_checked_solution_count == 0:
            return -1
        else:
            return self.checked_solution_count / self.to_be_checked_solution_count * 100.0

    def is_publicly_visible(self):
        """
        Should the workshop be publicly visible? (accepted or cancelled)
        """
        return self.status == 'Z' or self.status == 'X'


class WorkshopParticipantManager(models.Manager):
    def get_queryset(self) -> QuerySet['WorkshopParticipant']:
        return super().get_queryset().annotate(
            is_qualified=Case(
                When(workshop__is_qualifying=True, qualification_result__isnull=False, workshop__qualification_threshold__isnull=False, then=
                    Case(
                        When(qualification_result__gte=F('workshop__qualification_threshold'), then=True),
                        default=False
                    )
                ),
                default=None
            ),
            result_in_percent=Case(
                # For old [<2020] workshops we didn't have the max_points variable - use the max of qualification results instead in that case
                When(workshop__is_qualifying=True, qualification_result__isnull=False, then=
                    Greatest(Least(Case(
                        When(workshop__max_points__isnull=False, then=F('qualification_result') / F('workshop__max_points')),
                        default=F('qualification_result') / Max('workshop__participants__qualification_result')
                    ) * 100.0, settings.MAX_POINTS_PERCENT, output_field=DecimalField()), 0.0, output_field=DecimalField())
                ),
                default=None
            )
        )


class WorkshopParticipant(models.Model):
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name='participants')
    camp_participation = models.ForeignKey(CampParticipant, on_delete=models.CASCADE, related_name='workshop_participation')

    qualification_result = models.DecimalField(null=True, blank=True, decimal_places=2, max_digits=6, validators=[MinValueValidator(0)], verbose_name='Liczba punktów')
    comment = models.TextField(max_length=10000, null=True, default=None, blank=True, verbose_name='Komentarz')

    objects = WorkshopParticipantManager()

    def clean(self):
        super(WorkshopParticipant, self).clean()
        if self.workshop.year != self.camp_participation.year:
            raise ValidationError("You can't participate in a workshop from another year...")

    class Meta:
        base_manager_name = 'objects'
        unique_together = [('workshop', 'camp_participation')]
        ordering = ['id']

    def __str__(self):
        return '{}: {}'.format(self.workshop, self.camp_participation.user_profile)


class Solution(models.Model):
    workshop_participant = models.OneToOneField(WorkshopParticipant, null=False, blank=False, related_name='solution', on_delete=models.CASCADE)
    last_changed = models.DateTimeField(blank=False, null=False, auto_now=True)
    message = models.TextField(blank=True, verbose_name='Komentarz dla prowadzącego', help_text='Nie wpisuj rozwiązań w tym polu - załącz je jako plik. To pole jest przeznaczone jedynie na szybkie uwagi typu "poprawiłem plik X"')


def solutions_dir(instance, filename):
    workshop_participant = instance.solution.workshop_participant
    return f'solutions/{workshop_participant.workshop.year.pk}/{workshop_participant.workshop.name}/{workshop_participant.camp_participation.user_profile.user.pk}/{filename}'


class SoftDeletionQuerySet(models.QuerySet):
    def delete(self):
        return super().update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at=None)

    def deleted(self):
        return self.exclude(deleted_at=None)


class SoftDeletionManager(models.Manager):
    def __init__(self, *args, **kwargs):
        self.alive_only = kwargs.pop('alive_only', True)
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        if self.alive_only:
            return SoftDeletionQuerySet(self.model).filter(deleted_at=None)
        return SoftDeletionQuerySet(self.model)

    def hard_delete(self):
        return self.get_queryset().hard_delete()


class SolutionFile(models.Model):
    solution = models.ForeignKey(Solution, null=False, blank=False, related_name='files', on_delete=models.CASCADE)
    file = models.FileField(null=False, blank=False, upload_to=solutions_dir, storage=UploadStorage(), verbose_name='Plik')
    last_changed = models.DateTimeField(blank=False, null=False, auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    objects = SoftDeletionManager()
    all_objects = SoftDeletionManager(alive_only=False)

    def delete(self):
        if self.deleted:
            return True
        self.deleted_at = timezone.now()
        self.save()

    def hard_delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)

    @property
    def alive(self):
        return self.deleted_at is None

    @property
    def deleted(self):
        return self.deleted_at is not None

    def __str__(self):
        return os.path.basename(self.file.path) + (' (usunięty)' if self.deleted else '')


class ResourceYearPermission(models.Model):
    """
    Resource associated with a WWW edition (year). Resource can be accessed by
    users who qualified or had a lecture on year. User is granted access to
    root_url and recursively to all files and subdirectories inside.
    """
    display_name = models.CharField(max_length=50, blank=True)
    access_url = models.URLField(blank=True,
                                 help_text="URL dla przycisku w menu. Przycisk nie jest wyświetlany jeśli url jest pusty")
    root_path = models.CharField(max_length=256, null=False, blank=False,
                                 help_text='bez "/" na końcu. np. "/internety/www15"')
    year = models.ForeignKey(Camp, on_delete=models.PROTECT)

    def __str__(self):
        return "{} - {}".format(self.year,
                                self.display_name if self.display_name != "" else self.root_path)

    def clean(self):
        super().clean()
        if self.access_url != "" and self.display_name == "":
            raise ValidationError("Wyświetlana nazwa musi być ustawiona jeśli "
                                  "URL dostępu jest ustawiony")

        if self.root_path.endswith("/"):
            self.root_path = self.root_path[:-1]
        if not self.root_path.startswith("/"):
            self.root_path = "/" + self.root_path

    @staticmethod
    def resources_for_uri(uri: str):
        scheme, netloc, path, query, fragment = urllib.parse.urlsplit(uri)
        path = os.path.normpath(path)  # normalize path
        path_parts = path.split('/')
        if path_parts[0] != "":
            raise SuspiciousOperation("Path has to start with /")
        path_parts = path_parts[1:]

        query = Q(pk__isnull=True)  # always false
        for i in range(len(path_parts)+1):
            query |= Q(root_path='/'+'/'.join(path_parts[:i]))

        # We check all root_url that are prefixes of received url
        return ResourceYearPermission.objects.filter(query)

    class Meta:
        permissions = [('access_all_resources', 'Access all resources'), ]
        ordering = ['year', 'display_name']
