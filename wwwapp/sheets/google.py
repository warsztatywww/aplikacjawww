"""Small Google Sheets API adapter with safe full-snapshot replacement."""

import json
import os
from datetime import datetime

from django.core.exceptions import ImproperlyConfigured
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


SCOPE = 'https://www.googleapis.com/auth/spreadsheets'


class GoogleSheetsAccessError(Exception):
    """Raised when the configured service account cannot access a spreadsheet."""


class GoogleSheetsClient:
    def __init__(self, service):
        self.service = service

    @classmethod
    def from_environment(cls):
        raw_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        if not raw_json:
            raise ImproperlyConfigured('GOOGLE_SERVICE_ACCOUNT_JSON must contain service-account JSON.')
        try:
            info = json.loads(raw_json)
            credentials = Credentials.from_service_account_info(info, scopes=[SCOPE])
        except (ValueError, TypeError) as error:
            raise ImproperlyConfigured('GOOGLE_SERVICE_ACCOUNT_JSON is not valid service-account JSON.') from error
        return cls(build('sheets', 'v4', credentials=credentials, cache_discovery=False))

    def validate_spreadsheet(self, spreadsheet_id):
        try:
            return self.service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        except Exception as error:
            raise GoogleSheetsAccessError('Unable to access the configured spreadsheet; share it with the service account.') from error

    def ensure_managed_sheet(self, integration, tab_name):
        field = _sheet_field(tab_name)
        spreadsheet = self.validate_spreadsheet(integration.spreadsheet_id)
        sheets = spreadsheet.get('sheets', [])
        existing_id = getattr(integration, field)
        if existing_id is not None:
            if any(sheet['properties']['sheetId'] == existing_id for sheet in sheets):
                return existing_id
        title_matches = [sheet for sheet in sheets if sheet['properties']['title'] == tab_name]
        requests = []
        if title_matches:
            backup = self._backup_name(tab_name, sheets)
            requests.append({'updateSheetProperties': {'properties': {
                'sheetId': title_matches[0]['properties']['sheetId'], 'title': backup},
                'fields': 'title'}})
        requests.append({'addSheet': {'properties': {'title': tab_name}}})
        response = self.service.spreadsheets().batchUpdate(
            spreadsheetId=integration.spreadsheet_id, body={'requests': requests}).execute()
        sheet_id = response['replies'][-1]['addSheet']['properties']['sheetId']
        setattr(integration, field, sheet_id)
        integration.save(update_fields=[field])
        return sheet_id

    def replace_snapshot(self, spreadsheet_id, sheet_id, projection):
        rows = [[_cell_value(cell) for cell in row] for row in projection.rows]
        values = [[column.header for column in projection.columns]] + rows
        metadata = self.validate_spreadsheet(spreadsheet_id)
        sheet = next(item for item in metadata['sheets'] if item['properties']['sheetId'] == sheet_id)
        title = sheet['properties']['title'].replace("'", "''")
        range_name = "'%s'" % title
        self.service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={'requests': [{'repeatCell': {
                'range': {'sheetId': sheet_id},
                'cell': {'userEnteredFormat': {}},
                'fields': 'userEnteredFormat'}}]}).execute()
        self.service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id, range=range_name, body={}).execute()
        self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range='%s!A1' % range_name,
            valueInputOption='USER_ENTERED', body={'values': values}).execute()

    def _backup_name(self, tab_name, sheets):
        titles = {sheet['properties']['title'] for sheet in sheets}
        base = '%s (backup %s)' % (tab_name, datetime.utcnow().strftime('%Y-%m-%d %H%M%S'))
        name = base
        suffix = 2
        while name in titles:
            name = '%s (%s)' % (base, suffix)
            suffix += 1
        return name


def _sheet_field(tab_name):
    return {'Uczestnicy': 'participants_sheet_id', 'Prowadzący': 'lecturers_sheet_id',
            'Warsztaty': 'workshops_sheet_id'}[tab_name]


def _cell_value(cell):
    value = str(cell.value) if cell.value is not None else ''
    if cell.url:
        return '=HYPERLINK("%s","%s")' % (cell.url.replace('"', '""'), value.replace('"', '""'))
    return "'%s" % value if value.startswith(('=', '+', '-', '@')) else value
