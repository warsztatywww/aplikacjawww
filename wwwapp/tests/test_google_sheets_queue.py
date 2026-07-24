from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from wwwapp.models import Camp, CampGoogleSheetsIntegration
from wwwapp.sheets.queue import (claim_due_integrations, complete_sync, fail_sync,
                                 request_hourly_reconciliation,
                                 request_sync_after_commit)


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


class GoogleSheetsQueueTests(TestCase):
    def setUp(self):
        self.camp = Camp.objects.get()

    def make_enabled_integration(self):
        return CampGoogleSheetsIntegration.objects.create(
            camp=self.camp, spreadsheet_id='spreadsheet', enabled=True)

    def test_rolled_back_transaction_does_not_mark_dirty(self):
        integration = self.make_enabled_integration()

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                request_sync_after_commit([self.camp.pk])
                raise RuntimeError('rollback')

        integration.refresh_from_db()
        self.assertFalse(integration.dirty)

    def test_rapid_requests_coalesce_to_one_claim(self):
        self.make_enabled_integration()
        with self.captureOnCommitCallbacks(execute=True):
            request_sync_after_commit([self.camp.pk])
            request_sync_after_commit([self.camp.pk])

        self.assertEqual(len(claim_due_integrations(timezone.now())), 1)

    def test_disabled_integrations_are_not_requested(self):
        integration = CampGoogleSheetsIntegration.objects.create(
            camp=self.camp, spreadsheet_id='spreadsheet', enabled=False)
        with self.captureOnCommitCallbacks(execute=True):
            request_sync_after_commit([self.camp.pk])
        integration.refresh_from_db()

        self.assertFalse(integration.dirty)

    def test_stale_claim_is_reclaimed(self):
        integration = self.make_enabled_integration()
        now = timezone.now()
        integration.dirty = True
        integration.next_sync_at = now
        integration.claimed_at = now - timedelta(minutes=11)
        integration.save()

        claimed = claim_due_integrations(now)

        self.assertEqual([item.pk for item in claimed], [integration.pk])

    def test_wrong_token_does_not_complete_claim(self):
        integration = self.make_enabled_integration()
        with self.captureOnCommitCallbacks(execute=True):
            request_sync_after_commit([self.camp.pk])
        claimed = claim_due_integrations(timezone.now())[0]

        complete_sync(claimed.pk, 'wrong-token', claimed.claimed_at, timezone.now())
        integration.refresh_from_db()

        self.assertTrue(integration.dirty)

    def test_failure_uses_exponential_backoff(self):
        integration = self.make_enabled_integration()
        with self.captureOnCommitCallbacks(execute=True):
            request_sync_after_commit([self.camp.pk])
        now = timezone.now()
        claim = claim_due_integrations(now)[0]
        fail_sync(claim.pk, claim.claim_token, RuntimeError('first'), now)
        integration.refresh_from_db()
        self.assertEqual(integration.next_sync_at, now + timedelta(minutes=1))

    def test_hourly_reconciliation_requests_all_enabled_integrations(self):
        integration = self.make_enabled_integration()
        request_hourly_reconciliation(timezone.now())
        integration.refresh_from_db()

        self.assertTrue(integration.dirty)
