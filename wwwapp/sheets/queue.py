"""Transaction-safe scheduling and leasing for Google Sheets snapshots."""

from datetime import timedelta
from uuid import uuid4

from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q

from wwwapp.models import CampGoogleSheetsIntegration


STALE_CLAIM_AFTER = timedelta(minutes=10)
RETRY_DELAYS = (1, 2, 4, 8, 16, 30)


def request_sync_after_commit(camp_ids):
    """Mark enabled integrations dirty only after their write commits."""
    camp_ids = tuple(set(camp_ids))
    if not camp_ids:
        return

    def request():
        from django.utils import timezone

        CampGoogleSheetsIntegration.objects.filter(
            camp_id__in=camp_ids, enabled=True).update(
                dirty=True, next_sync_at=timezone.now())

    transaction.on_commit(request)


def claim_due_integrations(now):
    """Lease all due integrations, reclaiming abandoned leases."""
    stale_before = now - STALE_CLAIM_AFTER
    claimed = []
    with transaction.atomic():
        due = CampGoogleSheetsIntegration.objects.select_for_update(skip_locked=True).filter(
            enabled=True,
            dirty=True,
            next_sync_at__lte=now,
        ).filter(Q(claimed_at__isnull=True) | Q(claimed_at__lt=stale_before))
        for integration in due:
            integration.claim_token = uuid4()
            integration.claimed_at = now
            integration.last_attempt_at = now
            integration.save(update_fields=['claim_token', 'claimed_at', 'last_attempt_at'])
            claimed.append(integration)
    return claimed


def complete_sync(integration_id, claim_token, started_at, now):
    """Release a successful lease without losing a request made during it."""
    with transaction.atomic():
        integration = _claimed_integration(integration_id, claim_token)
        if integration is None:
            return False

        newer_request = integration.next_sync_at and integration.next_sync_at > started_at
        integration.dirty = bool(newer_request)
        integration.next_sync_at = integration.next_sync_at if newer_request else None
        integration.claim_token = None
        integration.claimed_at = None
        integration.attempt_count = 0
        integration.last_success_at = now
        integration.last_error = ''
        integration.save()
    return True


def fail_sync(integration_id, claim_token, error, now):
    """Release a failed lease and schedule its capped exponential retry."""
    with transaction.atomic():
        integration = _claimed_integration(integration_id, claim_token)
        if integration is None:
            return False

        integration.attempt_count += 1
        delay_index = min(integration.attempt_count - 1, len(RETRY_DELAYS) - 1)
        integration.dirty = True
        integration.next_sync_at = now + timedelta(minutes=RETRY_DELAYS[delay_index])
        integration.claim_token = None
        integration.claimed_at = None
        integration.last_error = _error_message(error)
        integration.save()
    return True


def request_hourly_reconciliation(now):
    """Request a fresh snapshot for every enabled integration."""
    CampGoogleSheetsIntegration.objects.filter(enabled=True).update(
        dirty=True, next_sync_at=now)


def _claimed_integration(integration_id, claim_token):
    try:
        integration = CampGoogleSheetsIntegration.objects.select_for_update().get(
            pk=integration_id, claim_token=claim_token)
    except (CampGoogleSheetsIntegration.DoesNotExist, ValidationError):
        return None
    return integration


def _error_message(error):
    message = '%s: %s' % (error.__class__.__name__, str(error))
    return message[:2000]
