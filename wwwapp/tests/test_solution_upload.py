import datetime
import os

import mock
import pytz
from django.contrib.auth.models import User
from django.contrib.messages.api import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.testcases import TestCase
from django.urls import reverse
from freezegun import freeze_time

from wwwapp.models import WorkshopType, WorkshopCategory, Workshop, Camp, WorkshopParticipant, Solution, SolutionFile, \
    CampParticipant


class SolutionUploadViews(TestCase):
    def setUp(self):
        # TODO: This is weird because of the constraint that one Camp object needs to exist at all times
        Camp.objects.all().update(year=2020, start_date=datetime.date(2020, 7, 3), end_date=datetime.date(2020, 7, 15))
        self.year_2020 = Camp.objects.get()
        self.year_2019 = Camp.objects.create(year=2019)

        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')
        self.lecturer_user = User.objects.create_user(
            username='lecturer', email='lecturer@example.com', password='user123')
        self.participant_user = User.objects.create_user(
            username='participant', email='participant@example.com', password='user123')

        WorkshopType.objects.create(year=self.year_2020, name='This type')
        WorkshopCategory.objects.create(year=self.year_2020, name='This category')

        self.workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='This type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            solution_uploads_enabled=True,
            qualification_problems=SimpleUploadedFile('problems.pdf', os.urandom(1024 * 1024)),
            qualification_threshold=5,
            max_points=10,
        )
        self.workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category'))
        self.workshop.lecturer.add(self.lecturer_user.user_profile)
        self.workshop.save()

        cp = CampParticipant.objects.create(user_profile=self.participant_user.user_profile, year=self.year_2020)
        cp.workshop_participation.create(workshop=self.workshop)

    def _assert_solution_upload_not_accessible(self, code=403):
        response = self.client.get(reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertEqual(response.status_code, code)

        with mock.patch('wwwapp.models.Solution.save', autospec=True, side_effect=Solution.save) as save_solution:
            with mock.patch('wwwapp.models.SolutionFile.save', autospec=True, side_effect=SolutionFile.save) as save_solution_file:
                response = self.client.post(reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]), {
                    'message': 'To są testy',
                    'files-INITIAL_FORMS': '0',
                    'files-TOTAL_FORMS': '2',
                    'files-0-id': '',
                    'files-0-file': SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)),
                    'files-0-DELETE': '',
                    'files-1-id': '',
                    'files-1-file': SimpleUploadedFile('attachment.zip', os.urandom(1024 * 1024)),
                    'files-1-DELETE': '',
                })
                self.assertEqual(response.status_code, code)
                save_solution.assert_not_called()
                save_solution_file.assert_not_called()

    def _assert_solution_upload_accessible(self, can_edit=True):
        response = self.client.get(reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertEqual(response.status_code, 200)
        initial_forms = response.context['form_attachments'].management_form.initial['INITIAL_FORMS']

        with mock.patch('wwwapp.models.Solution.save', autospec=True, side_effect=Solution.save) as save_solution:
            with mock.patch('wwwapp.models.SolutionFile.save', autospec=True, side_effect=SolutionFile.save) as save_solution_file:
                response = self.client.post(reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]), {
                    'message': 'To są testy',
                    'files-INITIAL_FORMS': str(initial_forms),
                    'files-TOTAL_FORMS': '2',
                    'files-0-id': '',
                    'files-0-file': SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)),
                    'files-0-DELETE': '',
                    'files-1-id': '',
                    'files-1-file': SimpleUploadedFile('attachment.zip', os.urandom(1024 * 1024)),
                    'files-1-DELETE': '',
                })
                if can_edit:
                    self.assertRedirects(response, reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]))
                    messages = get_messages(response.wsgi_request)
                    self.assertEqual(len(messages), 1)
                    self.assertEqual(list(messages)[0].message, 'Zapisano.')
                    save_solution.assert_called()
                    save_solution_file.assert_called()
                else:
                    self.assertEqual(response.status_code, 403)
                    save_solution.assert_not_called()
                    save_solution_file.assert_not_called()

    @freeze_time('2020-05-01 12:00:00')
    def test_solution_upload_not_accepted(self):
        self.workshop.status = Workshop.STATUS_REJECTED
        self.workshop.save()

        self.client.force_login(self.participant_user)
        self._assert_solution_upload_not_accessible(403)

    @freeze_time('2020-05-01 12:00:00')
    def test_solution_upload_blocked_no_qual_problems(self):
        self.workshop.qualification_problems = None
        self.workshop.save()

        self.client.force_login(self.participant_user)
        self._assert_solution_upload_not_accessible(403)

    @freeze_time('2020-05-01 12:00:00')
    def test_solution_upload_blocked_not_participant(self):
        WorkshopParticipant.objects.all().delete()

        self.client.force_login(self.participant_user)
        self._assert_solution_upload_not_accessible(403)

    @freeze_time('2020-05-01 12:00:00')
    def test_solution_upload_blocked_not_logged_in(self):
        response = self.client.get(reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]))

    @freeze_time('2020-12-01 12:00:00')
    def test_solution_upload_blocked_after_deadline_not_sent(self):
        self.client.force_login(self.participant_user)
        self._assert_solution_upload_not_accessible(403)

    @freeze_time('2020-12-01 12:00:00')
    def test_solution_upload_readonly_after_deadline_sent(self):
        Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile))
        self.client.force_login(self.participant_user)
        self._assert_solution_upload_accessible(can_edit=False)

    @freeze_time('2020-05-01 12:00:00')
    def test_solution_upload_accessible_empty(self):
        self.client.force_login(self.participant_user)
        self._assert_solution_upload_accessible(can_edit=True)

        solution = Solution.objects.get(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile))
        self.assertEqual(solution.message, 'To są testy')
        self.assertEqual(solution.last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))
        files = solution.files.all()
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))
        self.assertEqual(files[1].last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))

    @freeze_time('2020-05-01 12:00:00')
    def test_solution_upload_accessible_edit(self):
        with freeze_time('2020-01-01 00:00:00'):
            initial_solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='iks de')

        self.client.force_login(self.participant_user)
        self._assert_solution_upload_accessible(can_edit=True)

        solution = Solution.objects.get(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile))
        self.assertEqual(solution.pk, initial_solution.pk)
        self.assertEqual(solution.message, 'To są testy')
        self.assertEqual(solution.last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))
        files = solution.files.all()
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))
        self.assertEqual(files[1].last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))

    @freeze_time('2020-05-01 12:00:00')
    def test_solution_add_file(self):
        with freeze_time('2020-01-01 00:00:00'):
            initial_solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
            initial_solution_file = initial_solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]), {
            'message': 'To są testy',
            'files-INITIAL_FORMS': '1',
            'files-TOTAL_FORMS': '2',
            'files-0-id': initial_solution_file.id,
            'files-0-DELETE': '',
            'files-1-id': '',
            'files-1-file': SimpleUploadedFile('attachment.zip', os.urandom(1024 * 1024)),
            'files-1-DELETE': '',
        })
        self.assertRedirects(response, reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        solution = Solution.objects.get(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile))
        self.assertEqual(solution.pk, initial_solution.pk)
        self.assertEqual(solution.message, 'To są testy')
        self.assertEqual(solution.last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))  # even though the message has not changed, the attachments did
        files = solution.files.all()
        self.assertEqual(len(files), 2)
        self.assertEqual(files[0].last_changed, datetime.datetime(2020, 1, 1, 00, 00, 00, tzinfo=pytz.utc))  # this file has not changed, so the modification date should stay
        self.assertEqual(files[1].last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))

    @freeze_time('2020-05-01 12:00:00')
    def test_solution_delete_file(self):
        with freeze_time('2020-01-01 00:00:00'):
            initial_solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
            initial_solution_file = initial_solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))
        self.assertEqual(SolutionFile.objects.filter(solution=initial_solution).count(), 1)
        self.assertEqual(SolutionFile.all_objects.filter(solution=initial_solution).count(), 1)

        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]), {
            'message': 'To są testy',
            'files-INITIAL_FORMS': '1',
            'files-TOTAL_FORMS': '1',
            'files-0-id': initial_solution_file.id,
            'files-0-DELETE': 'on',
        })
        self.assertRedirects(response, reverse('workshop_my_solution', args=[self.workshop.year.pk, self.workshop.name]))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        solution = Solution.objects.get(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile))
        self.assertEqual(solution.pk, initial_solution.pk)
        self.assertEqual(solution.message, 'To są testy')
        self.assertEqual(solution.last_changed, datetime.datetime(2020, 5, 1, 12, 00, 00, tzinfo=pytz.utc))  # even though the message has not changed, the attachments did
        files = solution.files.all()
        self.assertEqual(len(files), 0)

        self.assertEqual(SolutionFile.objects.filter(solution=initial_solution).count(), 0)
        self.assertEqual(SolutionFile.all_objects.filter(solution=initial_solution).count(), 1)

    def test_download_my_solution_file(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('workshop_my_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution_file.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), solution_file.file.read())

    def test_download_my_solution_file_unauthenticated(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        response = self.client.get(reverse('workshop_my_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution_file.id]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshop_my_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution_file.id]))

    def test_download_my_solution_file_other(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        admin_cp, _ = CampParticipant.objects.get_or_create(user_profile=self.admin_user.user_profile, year=self.workshop.year)
        admin_participant = admin_cp.workshop_participation.create(workshop=self.workshop)
        solution2 = Solution.objects.create(workshop_participant=admin_participant, message='To są testy')
        solution2_file = solution2.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('workshop_my_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution2_file.id]))
        self.assertEqual(response.status_code, 404)

    def test_view_solution_lecturer(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('workshop_solution', args=[self.workshop.year.pk, self.workshop.name, solution.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, solution.message)
        self.assertContains(response, self.participant_user.get_full_name())

    def test_view_solution_admin(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('workshop_solution', args=[self.workshop.year.pk, self.workshop.name, solution.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, solution.message)
        self.assertContains(response, self.participant_user.get_full_name())

    def test_view_solution_participant(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('workshop_solution', args=[self.workshop.year.pk, self.workshop.name, solution.id]))
        self.assertEqual(response.status_code, 403)  # even though this is his solution, he should not be using this endpoint

    def test_view_solution_unauthenticated(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        response = self.client.get(reverse('workshop_solution', args=[self.workshop.year.pk, self.workshop.name, solution.id]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshop_solution', args=[self.workshop.year.pk, self.workshop.name, solution.id]))

    def test_download_solution_file_lecturer(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('workshop_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution.id, solution_file.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), solution_file.file.read())

    def test_download_solution_file_admin(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('workshop_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution.id, solution_file.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), solution_file.file.read())

    def test_download_solution_file_participant(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('workshop_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution.id, solution_file.id]))
        self.assertEqual(response.status_code, 403)  # even though this is his solution, he should not be using this endpoint

    def test_download_solution_file_unauthenticated(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        response = self.client.get(reverse('workshop_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution.id, solution_file.id]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshop_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution.id, solution_file.id]))

    def test_download_safe_extension(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.pdf', os.urandom(1024 * 1024)))

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('workshop_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution.id, solution_file.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertNotIn('attachment', response['Content-Disposition'])

    def test_download_unsafe_extension(self):
        solution = Solution.objects.create(workshop_participant=WorkshopParticipant.objects.get(workshop=self.workshop, camp_participation__user_profile=self.participant_user.user_profile), message='To są testy')
        solution_file = solution.files.create(file=SimpleUploadedFile('solution.js', os.urandom(1024 * 1024)))

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('workshop_solution_file', args=[self.workshop.year.pk, self.workshop.name, solution.id, solution_file.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Content-Type'], 'application/octet-stream')
        self.assertIn('attachment', response['Content-Disposition'])
