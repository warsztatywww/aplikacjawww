"""Schedule snapshots after changes to camp-owned export data."""

from django.contrib.auth.models import User
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_delete
from django.dispatch import receiver

from wwwapp.models import (Camp, CampInterestEmail, CampParticipant, Solution, UserProfile,
                           Workshop, WorkshopParticipant)
from wwwapp.sheets.queue import request_sync_after_commit
from wwwforms.models import Form, FormQuestion, FormQuestionAnswer, FormQuestionOption


def _camp_ids(instance):
    if isinstance(instance, Camp):
        return [instance.pk]
    if isinstance(instance, Workshop):
        return [instance.year_id]
    if isinstance(instance, CampParticipant):
        return [instance.year_id]
    if isinstance(instance, CampInterestEmail):
        return [instance.year_id]
    if isinstance(instance, WorkshopParticipant):
        return [instance.workshop.year_id]
    if isinstance(instance, Solution):
        return [instance.workshop_participant.workshop.year_id]
    if isinstance(instance, UserProfile):
        return set(instance.camp_participation.values_list('year_id', flat=True)) | set(
            instance.lecturer_workshops.values_list('year_id', flat=True))
    return []


def _form_camp_ids(form_id):
    return Camp.objects.filter(forms__pk=form_id).values_list('pk', flat=True)


def _form_instance_camp_ids(instance):
    if isinstance(instance, Form):
        return _form_camp_ids(instance.pk)
    if isinstance(instance, FormQuestion):
        return _form_camp_ids(instance.form_id)
    if isinstance(instance, FormQuestionOption):
        return _form_camp_ids(instance.question.form_id)
    if isinstance(instance, FormQuestionAnswer):
        return _form_camp_ids(instance.question.form_id)
    if isinstance(instance, User):
        return _camp_ids(instance.user_profile) if hasattr(instance, 'user_profile') else []
    return []


def _schedule(sender, instance, **kwargs):
    camp_ids = getattr(instance, '_sheets_camp_ids', None)
    if camp_ids is None:
        camp_ids = set(_camp_ids(instance)) | set(_form_instance_camp_ids(instance))
    request_sync_after_commit(camp_ids)


def _capture_delete_camps(sender, instance, **kwargs):
    instance._sheets_camp_ids = set(_camp_ids(instance)) | set(_form_instance_camp_ids(instance))


for _model in (Camp, CampInterestEmail, CampParticipant, Workshop, WorkshopParticipant, Solution,
               UserProfile, User, Form, FormQuestion, FormQuestionOption, FormQuestionAnswer):
    pre_delete.connect(_capture_delete_camps, sender=_model,
                       dispatch_uid='sheets-capture-%s' % _model.__name__)
    post_save.connect(_schedule, sender=_model, dispatch_uid='sheets-save-%s' % _model.__name__)
    post_delete.connect(_schedule, sender=_model, dispatch_uid='sheets-delete-%s' % _model.__name__)


@receiver(m2m_changed, sender=Workshop.lecturer.through)
@receiver(m2m_changed, sender=Workshop.category.through)
def workshop_relation_changed(sender, instance, action, **kwargs):
    if action.startswith('post_'):
        request_sync_after_commit([instance.year_id])


@receiver(m2m_changed, sender=Camp.forms.through)
def camp_forms_changed(sender, instance, action, **kwargs):
    if action.startswith('post_'):
        request_sync_after_commit([instance.pk])


@receiver(m2m_changed, sender=FormQuestionAnswer.value_choices.through)
def answer_choices_changed(sender, instance, action, **kwargs):
    if action.startswith('post_'):
        request_sync_after_commit(_form_camp_ids(instance.question.form_id))
