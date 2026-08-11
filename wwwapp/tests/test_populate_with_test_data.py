from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from wwwapp.management.commands.populate_with_test_data import Command
from wwwapp.models import Invoice, UploadStorage, UserProfile, Workshop


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
        field = Invoice._meta.get_field('attachment')
        original_storage = field.storage
        with TemporaryDirectory() as sendfile_root:
            with override_settings(SENDFILE_ROOT=sendfile_root):
                field.storage = UploadStorage()
                try:
                    call_command('populate_with_test_data', quiet=True)

                    invoices = Invoice.objects.all()

                    self.assertEqual(
                        set(invoices.values_list('status', flat=True)),
                        set(Invoice.Status.values),
                    )
                    self.assertEqual(
                        invoices.values('user_id').distinct().count(),
                        len(Invoice.Status.values),
                    )
                    camp_year = invoices.first().camp_id
                    self.assertEqual(
                        set(invoices.exclude(internal_number=None).values_list(
                            'internal_number',
                            flat=True,
                        )),
                        {
                            f'WWW_{camp_year}_K_0001',
                            f'WWW_{camp_year}_K_0002',
                        },
                    )
                    self.assertEqual(
                        invoices.filter(internal_number__isnull=False)
                        .values('status')
                        .distinct()
                        .count(),
                        2,
                    )
                    for invoice in invoices:
                        with self.subTest(invoice=invoice.pk):
                            self.assertTrue(
                                invoice.attachment.storage.exists(invoice.attachment.name),
                            )
                            with invoice.attachment.open('rb') as attachment:
                                self.assertTrue(attachment.read().startswith(b'%PDF-'))
                finally:
                    field.storage = original_storage
