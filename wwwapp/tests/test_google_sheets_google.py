import os
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from wwwapp.sheets.google import GoogleSheetsClient, _cell_value
from wwwapp.sheets.projections import TableCell


class GoogleSheetsClientTests(SimpleTestCase):
    def test_missing_service_account_json_has_actionable_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ImproperlyConfigured, 'GOOGLE_SERVICE_ACCOUNT_JSON'):
                GoogleSheetsClient.from_environment()

    def test_formula_leading_user_data_is_literal(self):
        self.assertEqual(_cell_value(TableCell('=SUM(A1:A2)')), "'=SUM(A1:A2)")

    def test_only_server_generated_urls_become_formulas(self):
        self.assertEqual(_cell_value(TableCell('Alice', '/profile/1/')),
                         '=HYPERLINK("/profile/1/","Alice")')
