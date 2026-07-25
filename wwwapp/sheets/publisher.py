"""Publish a claimed camp integration without holding a database transaction."""

from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from googleapiclient.errors import HttpError

from wwwapp.models import CampGoogleSheetsIntegration
from wwwapp.sheets.google import GoogleSheetsAccessError, GoogleSheetsClient
from wwwapp.sheets.projections import lecturer_projection, participant_projection, workshop_projection
from wwwapp.sheets.queue import complete_sync, fail_sync


MANAGED_TABS = (('Uczestnicy', participant_projection), ('Prowadzący', lecturer_projection),
                ('Warsztaty', workshop_projection))


def publish_integration(integration_id, claim_token):
    """Publish all tabs for a valid lease and persist its outcome."""
    integration = CampGoogleSheetsIntegration.objects.select_related('camp').get(pk=integration_id)
    if integration.claim_token != claim_token or not integration.enabled:
        return False
    started_at = integration.claimed_at
    try:
        client = GoogleSheetsClient.from_settings()
        for tab_name, projection_factory in MANAGED_TABS:
            sheet_id = client.ensure_managed_sheet(integration, tab_name)
            client.replace_snapshot(integration.spreadsheet_id, sheet_id,
                                    projection_factory(integration.camp))
    except (GoogleSheetsAccessError, HttpError, ImproperlyConfigured) as error:
        fail_sync(integration_id, claim_token, error, timezone.now())
        return False
    except Exception as error:
        fail_sync(integration_id, claim_token, error, timezone.now())
        raise
    return complete_sync(integration_id, claim_token, started_at, timezone.now())
