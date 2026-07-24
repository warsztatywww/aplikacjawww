"""Schedule snapshots after changes to camp-owned export data."""

from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from wwwapp.models import Camp, CampParticipant, Solution, UserProfile, Workshop, WorkshopParticipant
from wwwapp.sheets.queue import request_sync_after_commit


def _camp_ids(instance):
    if isinstance(instance, Camp):
        return [instance.pk]
    if isinstance(instance, Workshop):
        return [instance.year_id]
    if isinstance(instance, CampParticipant):
        return [instance.year_id]
    if isinstance(instance, WorkshopParticipant):
        return [instance.workshop.year_id]
    if isinstance(instance, Solution):
        return [instance.workshop_participant.workshop.year_id]
    if isinstance(instance, UserProfile):
        return set(instance.camp_participation.values_list('year_id', flat=True)) | set(
            instance.lecturer_workshops.values_list('year_id', flat=True))
    return []


def _schedule(sender, instance, **kwargs):
    request_sync_after_commit(_camp_ids(instance))


for _model in (Camp, CampParticipant, Workshop, WorkshopParticipant, Solution, UserProfile):
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
