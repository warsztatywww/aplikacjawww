from django.contrib.auth.models import User
from django.test import TestCase

from wwwapp.models import Camp, CampParticipant, Workshop, WorkshopType
from wwwapp.sheets.projections import participant_projection
from wwwforms.models import Form, FormQuestion


class GoogleSheetsProjectionTests(TestCase):
    def test_participant_projection_excludes_accepted_lecturers(self):
        camp = Camp.objects.get()
        user = User.objects.create_user('person', first_name='Ada', last_name='Lovelace')
        CampParticipant.objects.create(year=camp, user_profile=user.user_profile)
        workshop_type = WorkshopType.objects.create(year=camp, name='Type')
        workshop = Workshop.objects.create(year=camp, name='workshop', title='Workshop',
                                           type=workshop_type, status=Workshop.STATUS_ACCEPTED)
        workshop.lecturer.add(user.user_profile)
        self.assertEqual(participant_projection(camp).rows, ())

    def test_duplicate_dynamic_headers_are_disambiguated(self):
        camp = Camp.objects.get()
        form = Form.objects.create(name='form', title='Formularz')
        camp.forms.add(form)
        FormQuestion.objects.create(form=form, title='Miasto', data_type='s')
        FormQuestion.objects.create(form=form, title='Miasto', data_type='s', order=1)
        headers = [column.header for column in participant_projection(camp).columns]
        self.assertEqual(headers.count('Formularz: Miasto'), 1)
        self.assertIn('Formularz: Miasto (2)', headers)
