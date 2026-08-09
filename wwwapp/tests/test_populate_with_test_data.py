from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from wwwapp.management.commands.populate_with_test_data import Command
from wwwapp.models import Invoice, InvoiceSequence, UserProfile, Workshop


@override_settings(DEBUG=True, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PopulateWithTestData(TestCase):
    def test_populate_command(self):
        args = []
        opts = {'quiet': True}  # Use quiet flag to suppress output during tests
        call_command('populate_with_test_data', *args, **opts)

        self.assertEqual(User.objects.count(), Command.NUM_OF_USERS+1)
        self.assertEqual(UserProfile.objects.count(), Command.NUM_OF_USERS+1)
        self.assertEqual(Workshop.objects.count(), Command.NUM_OF_WORKSHOPS_CURRENT +
                         Command.NUM_OF_WORKSHOPS_PREVIOUS + Command.NUM_OF_WORKSHOPS_OLDEST)

    def test_populate_command_creates_invoices_for_each_status_and_user(self):
        call_command('populate_with_test_data', quiet=True)

        invoices = Invoice.objects.all()

        self.assertEqual(set(invoices.values_list('status', flat=True)), set(Invoice.Status.values))
        self.assertEqual(invoices.values('user_id').distinct().count(), len(Invoice.Status.values))
        sequence = InvoiceSequence.objects.get(
            camp=invoices.first().camp,
            invoice_type=Invoice.Type.KSEF,
        )
        self.assertEqual(sequence.last_allocated, 2)
        self.assertEqual(
            invoices.filter(internal_number__isnull=False).values('status').distinct().count(),
            2,
        )
