from django.db import IntegrityError
from django.test import TestCase

from wwwapp.models import Camp, CampGoogleSheetsIntegration


class GoogleSheetsIntegrationModelTests(TestCase):
    def setUp(self):
        self.camp = Camp.objects.get()

    def test_camp_has_at_most_one_google_sheets_integration(self):
        CampGoogleSheetsIntegration.objects.create(
            camp=self.camp, spreadsheet_id='spreadsheet-a')

        with self.assertRaises(IntegrityError):
            CampGoogleSheetsIntegration.objects.create(
                camp=self.camp, spreadsheet_id='spreadsheet-b')

    def test_disabling_retains_the_last_snapshot_identity(self):
        integration = CampGoogleSheetsIntegration.objects.create(
            camp=self.camp,
            spreadsheet_id='spreadsheet',
            enabled=True,
            participants_sheet_id=123,
        )
        integration.enabled = False
        integration.save()
        integration.refresh_from_db()

        self.assertEqual(integration.participants_sheet_id, 123)
