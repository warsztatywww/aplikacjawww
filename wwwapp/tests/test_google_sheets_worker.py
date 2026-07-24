from unittest import mock

from django.test import TestCase
from django.utils import timezone

from wwwapp.models import Camp, CampGoogleSheetsIntegration
from wwwapp.sheets.publisher import publish_integration
from wwwapp.sheets.queue import claim_due_integrations


class GoogleSheetsWorkerTests(TestCase):
    def test_publish_writes_three_managed_tabs_then_completes(self):
        integration = CampGoogleSheetsIntegration.objects.create(
            camp=Camp.objects.get(), spreadsheet_id='sheet', enabled=True, dirty=True,
            next_sync_at=timezone.now())
        claim = claim_due_integrations(timezone.now())[0]
        client = mock.Mock()
        client.ensure_managed_sheet.side_effect = [1, 2, 3]
        with mock.patch('wwwapp.sheets.publisher.GoogleSheetsClient.from_environment',
                        return_value=client):
            publish_integration(claim.pk, claim.claim_token)
        integration.refresh_from_db()
        self.assertFalse(integration.dirty)
        self.assertEqual([call.args[1] for call in client.ensure_managed_sheet.call_args_list],
                         ['Uczestnicy', 'Prowadzący', 'Warsztaty'])
