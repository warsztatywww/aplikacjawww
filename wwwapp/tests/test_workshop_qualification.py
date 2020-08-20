import datetime

import mock
from django.contrib.auth.models import User
from django.test.testcases import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from freezegun import freeze_time

from wwwapp.templatetags import wwwtags
from wwwapp.models import WorkshopType, WorkshopCategory, Workshop, WorkshopParticipant


@override_settings(
    CURRENT_YEAR=2020,
    WORKSHOPS_START_DATE=datetime.date(2020, 7, 3),
    WORKSHOPS_END_DATE=datetime.date(2020, 7, 15)
)
class WorkshopQualificationViews(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')
        self.lecturer_user = User.objects.create_user(
            username='lecturer', email='lecturer@example.com', password='user123')
        self.participant_user = User.objects.create_user(
            username='participant', email='participant@example.com', password='user123')

        WorkshopType.objects.create(year=2019, name='Not this type')
        WorkshopType.objects.create(year=2020, name='This type')
        WorkshopCategory.objects.create(year=2019, name='Not this category')
        WorkshopCategory.objects.create(year=2020, name='This category')

        self.workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            type=WorkshopType.objects.get(year=2020, name='This type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED
        )
        self.workshop.category.add(WorkshopCategory.objects.get(year=2020, name='This category'))
        self.workshop.lecturer.add(self.lecturer_user.userprofile)
        self.workshop.save()

        self.workshop_proposal = Workshop.objects.create(
            title='To tylko propozycja',
            name='propozycja',
            type=WorkshopType.objects.get(year=2020, name='This type'),
            proposition_description='<p>nie akceptuj tego</p>',
            status=None
        )
        self.workshop_proposal.category.add(WorkshopCategory.objects.get(year=2020, name='This category'))
        self.workshop_proposal.lecturer.add(self.lecturer_user.userprofile)
        self.workshop_proposal.save()

        self.previous_year_workshop = Workshop.objects.create(
            title='Jakiś staroć',
            name='starocie',
            type=WorkshopType.objects.get(year=2019, name='Not this type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED
        )
        self.previous_year_workshop.category.add(WorkshopCategory.objects.get(year=2019, name='Not this category'))
        self.previous_year_workshop.lecturer.add(self.lecturer_user.userprofile)
        self.previous_year_workshop.save()

    def test_latest_program_redirect(self):
        response = self.client.get(reverse('program'))
        self.assertRedirects(response, reverse('year_program', args=[2020]))

    def test_latest_program_redirect_keeps_qs(self):
        response = self.client.get(reverse('program') + '?this=is&my=query&string=XD')
        self.assertRedirects(response, reverse('year_program', args=[2020]) + '?this=is&my=query&string=XD')

    def test_view_program(self):
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertContains(response, 'Bardzo fajne warsztaty')
        self.assertNotContains(response, 'To tylko propozycja')
        self.assertNotContains(response, 'Jakiś staroć')

        response = self.client.get(reverse('year_program', args=[2019]))
        self.assertNotContains(response, 'Bardzo fajne warsztaty')
        self.assertNotContains(response, 'To tylko propozycja')
        self.assertContains(response, 'Jakiś staroć')

    @freeze_time('2020-05-01 12:00:00')
    def test_view_program_can_register_unauthenticated(self):
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertContains(response, 'Zapisz się')

    @freeze_time('2020-05-01 12:00:00')
    def test_view_program_can_register_user(self):
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertContains(response, 'Zapisz się')

    @freeze_time('2020-05-01 12:00:00')
    def test_view_program_can_unregister_user(self):
        WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertContains(response, 'Wypisz się')

    @freeze_time('2020-12-01 12:00:00')
    def test_view_program_cannot_register(self):
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertNotContains(response, 'Zapisz się')

    @freeze_time('2020-12-01 12:00:00')
    def test_view_program_cannot_unregister(self):
        WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertNotContains(response, 'Wypisz się')
        self.assertContains(response, 'Byłeś zapisany')

    @freeze_time('2020-05-01 12:00:00')
    def test_redirect_register_unauthenticated(self):
        # User not logged in, redirect to login
        response = self.client.post(reverse('register_to_workshop'), {'workshop_name': self.workshop.name})
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('redirect', data)
        self.assertNotIn('content', data)
        self.assertEqual(data['error'], 'Jesteś niezalogowany')
        self.assertURLEqual(data['redirect'], reverse('login'))

    @freeze_time('2020-05-01 12:00:00')
    def test_can_register_user(self):
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('register_to_workshop'), {'workshop_name': self.workshop.name})
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertNotIn('error', data)
        self.assertIn('content', data)
        self.assertIn('Wypisz się', data['content'])
        self.assertTrue(WorkshopParticipant.objects.filter(workshop=self.workshop, participant=self.participant_user.userprofile).exists())

    @freeze_time('2020-05-01 12:00:00')
    def test_cant_register_user_again(self):
        # User already registered, can't register again
        WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('register_to_workshop'), {'workshop_name': self.workshop.name})
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertIn('content', data)
        self.assertEqual(data['error'], 'Już jesteś zapisany na te warsztaty')

    @freeze_time('2020-05-01 12:00:00')
    def test_can_unregister_user(self):
        WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('unregister_from_workshop'), {'workshop_name': self.workshop.name})
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertNotIn('error', data)
        self.assertIn('content', data)
        self.assertIn('Zapisz się', data['content'])
        self.assertFalse(WorkshopParticipant.objects.filter(workshop=self.workshop, participant=self.participant_user.userprofile).exists())

    @freeze_time('2020-05-01 12:00:00')
    def test_cant_unregister_user_again(self):
        # User not registered, can't unregister
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('unregister_from_workshop'), {'workshop_name': self.workshop.name})
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertIn('content', data)
        self.assertEqual(data['error'], 'Nie jesteś zapisany na te warsztaty')

    @freeze_time('2020-12-01 12:00:00')
    def test_cannot_register(self):
        # After workshops started, registration cannot be changed
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('register_to_workshop'), {'workshop_name': self.workshop.name})
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertNotIn('content', data)
        self.assertEqual(data['error'], 'Kwalifikacja na te warsztaty została zakończona.')
        self.assertFalse(WorkshopParticipant.objects.filter(workshop=self.workshop, participant=self.participant_user.userprofile).exists())

    @freeze_time('2020-12-01 12:00:00')
    def test_cannot_unregister(self):
        # After workshops started, registration cannot be changed
        WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('unregister_from_workshop'), {'workshop_name': self.workshop.name})
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertNotIn('content', data)
        self.assertEqual(data['error'], 'Kwalifikacja na te warsztaty została zakończona.')
        self.assertTrue(WorkshopParticipant.objects.filter(workshop=self.workshop, participant=self.participant_user.userprofile).exists())

    @freeze_time('2020-05-01 12:00:00')
    def test_cannot_unregister_with_results(self):
        # User cannot unregister after he has qualification results for this workshop
        WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile, qualification_result=15)
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('unregister_from_workshop'), {'workshop_name': self.workshop.name})
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertNotIn('content', data)
        self.assertEqual(data['error'], 'Masz już wyniki z tej kwalifikacji - nie możesz się wycofać.')
        self.assertTrue(WorkshopParticipant.objects.filter(workshop=self.workshop, participant=self.participant_user.userprofile).exists())

    def _test_can_edit_points(self, user, can_view, can_edit):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)

        url = reverse('workshop_participants', args=[self.workshop.name])

        if user is not None:
            self.client.force_login(user)
        else:
            self.client.logout()

        # Open the editor
        response = self.client.get(url)
        if not can_view:
            if user is None:
                self.assertRedirects(response, reverse('login') + '?next=' + url)
            else:
                self.assertEqual(response.status_code, 403)
        else:
            self.assertEqual(response.status_code, 200)

        # Submit the edits
        with mock.patch('wwwapp.models.WorkshopParticipant.save', autospec=True, side_effect=WorkshopParticipant.save) as save:
            response = self.client.post(reverse('save_points'), {
                'id': participant.id,
                'qualification_result': 1234,
                'comment': 'Dobrze!',
            })
            if not can_edit:
                save.assert_not_called()
                if not can_view:
                    self.assertEqual(response.status_code, 403)
                else:
                    self.assertEqual(response.status_code, 200)
            else:
                save.assert_called()
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertIn('qualification_result', data)
                self.assertIn('comment', data)
                self.assertIn('mark', data)
                self.assertEqual(data['qualification_result'], '1234')
                self.assertEqual(data['comment'], 'Dobrze!')

                participant = WorkshopParticipant.objects.get(workshop=self.workshop, participant=self.participant_user.userprofile)
                self.assertEqual(participant.qualification_result, 1234)
                self.assertEqual(participant.comment, 'Dobrze!')

    @freeze_time('2020-05-01 12:00:00')
    def test_edit_points_unauthenticated(self):
        # Unauthenticated user can't view participants or edit points
        self._test_can_edit_points(None, False, False)

    @freeze_time('2020-05-01 12:00:00')
    def test_edit_points_not_lecturer(self):
        # Other users can't view participants or edit points
        self._test_can_edit_points(self.participant_user, False, False)

    @freeze_time('2020-05-01 12:00:00')
    def test_edit_points_lecturer(self):
        # Lecturer can view participants and edit points until workshops start
        self._test_can_edit_points(self.lecturer_user, True, True)

    @freeze_time('2020-05-01 12:00:00')
    def test_edit_points_admin(self):
        # Admin can view participants and edit points until workshops start
        self._test_can_edit_points(self.admin_user, True, True)

    @freeze_time('2020-12-01 12:00:00')
    def test_edit_points_lecturer_after(self):
        # Lecturer can view participants but not edit points after workshops start
        self._test_can_edit_points(self.lecturer_user, True, False)

    @freeze_time('2020-12-01 12:00:00')
    def test_edit_points_admin_after(self):
        # Admin can view participants but not edit points after workshops start
        self._test_can_edit_points(self.admin_user, True, False)

    @freeze_time('2020-05-01 12:00:00')
    @override_settings(CURRENT_YEAR=2021)
    def test_edit_points_lecturer_historical(self):
        # Lecturer can view participants but not edit points from previous years
        self._test_can_edit_points(self.lecturer_user, True, False)

    @freeze_time('2020-05-01 12:00:00')
    @override_settings(CURRENT_YEAR=2021)
    def test_edit_points_admin_historical(self):
        # Admin can view participants but not edit points from previous years
        self._test_can_edit_points(self.admin_user, True, False)

    @freeze_time('2020-05-01 12:00:00')
    def test_mark_accepted(self):
        self.workshop.qualification_threshold = 5
        self.workshop.max_points = 10
        self.workshop.save()
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 7.5
        })
        data = response.json()
        self.assertEqual(data['mark'], wwwtags.qualified_mark(True))

        # Check after page reload
        response = self.client.get(reverse('workshop_participants', args=[self.workshop.name]))
        self.assertContains(response, wwwtags.qualified_mark(True))

        # Check participant view
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertContains(response, wwwtags.qualified_mark(True))

    @freeze_time('2020-05-01 12:00:00')
    def test_mark_rejected(self):
        self.workshop.qualification_threshold = 5
        self.workshop.max_points = 10
        self.workshop.save()
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 2.5
        })
        data = response.json()
        self.assertEqual(data['mark'], wwwtags.qualified_mark(False))

        # Check after page reload
        response = self.client.get(reverse('workshop_participants', args=[self.workshop.name]))
        self.assertContains(response, wwwtags.qualified_mark(False))

        # Check participant view
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertContains(response, wwwtags.qualified_mark(False))

    @freeze_time('2020-05-01 12:00:00')
    def test_mark_none(self):
        self.workshop.qualification_threshold = None
        self.workshop.max_points = None
        self.workshop.save()
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 5
        })
        data = response.json()
        self.assertEqual(data['mark'], wwwtags.qualified_mark(None))

        # Check after page reload
        response = self.client.get(reverse('workshop_participants', args=[self.workshop.name]))
        self.assertContains(response, wwwtags.qualified_mark(None))

        # Check participant view
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('year_program', args=[2020]))
        self.assertContains(response, wwwtags.qualified_mark(None))
