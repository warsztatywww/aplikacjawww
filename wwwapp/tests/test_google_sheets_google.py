import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from wwwapp.sheets.google import GoogleSheetsClient, _cell_value
from wwwapp.sheets.projections import TableCell


class GoogleSheetsClientTests(SimpleTestCase):
    @override_settings(GOOGLE_SERVICE_ACCOUNT_JSON=None)
    def test_missing_settings_credential_has_actionable_error(self):
        with mock.patch.dict(os.environ, {'GOOGLE_SERVICE_ACCOUNT_JSON': '{}'}):
            with self.assertRaisesRegex(ImproperlyConfigured, 'local_settings.py'):
                GoogleSheetsClient.from_settings()

    def test_formula_leading_user_data_is_literal(self):
        self.assertEqual(_cell_value(TableCell('=SUM(A1:A2)')), "'=SUM(A1:A2)")

    def test_only_server_generated_urls_become_formulas(self):
        self.assertEqual(_cell_value(TableCell('Alice', '/profile/1/')),
                         '=HYPERLINK("/profile/1/","Alice")')
