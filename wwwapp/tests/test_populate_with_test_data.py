from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from wwwapp.models import UserProfile, Workshop


@override_settings(DEBUG=True, PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher'])
class PopulateWithTestData(TestCase):
    def test_populate_command(self):
        args = []
        opts = {}
        call_command('populate_with_test_data', *args, **opts)

        self.assertEquals(User.objects.count(), 51)
        self.assertEquals(UserProfile.objects.count(), 51)
        self.assertEquals(Workshop.objects.count(), 5)
