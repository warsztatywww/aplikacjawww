"""Run the Google Sheets snapshot worker."""

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from wwwapp.sheets.publisher import publish_integration
from wwwapp.sheets.queue import claim_due_integrations, request_hourly_reconciliation


class Command(BaseCommand):
    help = 'Publish due camp Google Sheets snapshots.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true')
        parser.add_argument('--reconcile', action='store_true')
        parser.add_argument('--sleep-seconds', type=int, default=30)

    def handle(self, *args, **options):
        if options['reconcile']:
            request_hourly_reconciliation(timezone.now())
            return
        while True:
            claims = claim_due_integrations(timezone.now())
            for claim in claims:
                publish_integration(claim.pk, claim.claim_token)
            if options['once']:
                return
            if not claims:
                time.sleep(options['sleep_seconds'])
