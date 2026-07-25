from django.contrib.auth.models import User
from django.test import TestCase

from wwwapp.models import Camp, CampGoogleSheetsIntegration, Workshop, WorkshopType


class GoogleSheetsSignalTests(TestCase):
    def test_workshop_lecturer_change_marks_its_camp_dirty(self):
        camp = Camp.objects.get()
        integration = CampGoogleSheetsIntegration.objects.create(
            camp=camp, spreadsheet_id='sheet', enabled=True)
        workshop_type = WorkshopType.objects.create(year=camp, name='Type')
        workshop = Workshop.objects.create(year=camp, name='workshop', title='Workshop',
                                           type=workshop_type)
        profile = User.objects.create_user('lecturer').user_profile
        with self.captureOnCommitCallbacks(execute=True):
            workshop.lecturer.add(profile)
        integration.refresh_from_db()
        self.assertTrue(integration.dirty)
