import datetime
import os

import mock
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.testcases import TestCase
from django.urls import reverse
from freezegun import freeze_time

from wwwapp.models import WorkshopType, WorkshopCategory, Workshop, \
    WorkshopParticipant, Camp
from wwwapp.templatetags import wwwtags


class WorkshopQualificationViews(TestCase):
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
        self.participant_user2 = User.objects.create_user(
            username='participant2', email='participant2@example.com', password='user2_123')

        WorkshopType.objects.create(year=self.year_2019, name='Not this type')
        WorkshopType.objects.create(year=self.year_2020, name='This type')
        WorkshopCategory.objects.create(year=self.year_2019, name='Not this category')
        WorkshopCategory.objects.create(year=self.year_2020, name='This category')

        self.workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='This type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            solution_uploads_enabled=False,
            qualification_problems=SimpleUploadedFile('problems.pdf', os.urandom(1024 * 1024)),
            qualification_threshold=5,
            max_points=10,
        )
        self.workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category'))
        self.workshop.lecturer.add(self.lecturer_user.userprofile)
        self.workshop.save()

        self.workshop_proposal = Workshop.objects.create(
            title='To tylko propozycja',
            name='propozycja',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='This type'),
            proposition_description='<p>nie akceptuj tego</p>',
            status=None,
            solution_uploads_enabled=False
        )
        self.workshop_proposal.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category'))
        self.workshop_proposal.lecturer.add(self.lecturer_user.userprofile)
        self.workshop_proposal.save()

        self.previous_year_workshop = Workshop.objects.create(
            title='Jakiś staroć',
            name='starocie',
            year=self.year_2019,
            type=WorkshopType.objects.get(year=self.year_2019, name='Not this type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            solution_uploads_enabled=False
        )
        self.previous_year_workshop.category.add(WorkshopCategory.objects.get(year=self.year_2019, name='Not this category'))
        self.previous_year_workshop.lecturer.add(self.lecturer_user.userprofile)
        self.previous_year_workshop.save()

    def test_latest_program_redirect(self):
        response = self.client.get(reverse('latest_program'))
        self.assertRedirects(response, reverse('program', args=[2020]))

    def test_latest_program_redirect_keeps_qs(self):
        response = self.client.get(reverse('latest_program') + '?this=is&my=query&string=XD')
        self.assertRedirects(response, reverse('program', args=[2020]) + '?this=is&my=query&string=XD')

    def test_view_program(self):
        response = self.client.get(reverse('program', args=[2020]))
        self.assertContains(response, 'Bardzo fajne warsztaty')
        self.assertNotContains(response, 'To tylko propozycja')
        self.assertNotContains(response, 'Jakiś staroć')

        response = self.client.get(reverse('program', args=[2019]))
        self.assertNotContains(response, 'Bardzo fajne warsztaty')
        self.assertNotContains(response, 'To tylko propozycja')
        self.assertContains(response, 'Jakiś staroć')

    @freeze_time('2020-05-01 12:00:00')
    def test_view_program_can_register_unauthenticated(self):
        response = self.client.get(reverse('program', args=[2020]))
        self.assertContains(response, 'Zapisz się')

    @freeze_time('2020-05-01 12:00:00')
    def test_view_program_can_register_user(self):
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('program', args=[2020]))
        self.assertContains(response, 'Zapisz się')

    @freeze_time('2020-05-01 12:00:00')
    def test_view_program_can_unregister_user(self):
        WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('program', args=[2020]))
        self.assertContains(response, 'Wypisz się')

    @freeze_time('2020-12-01 12:00:00')
    def test_view_program_cannot_register(self):
        response = self.client.get(reverse('program', args=[2020]))
        self.assertNotContains(response, 'Zapisz się')

    @freeze_time('2020-12-01 12:00:00')
    def test_view_program_cannot_unregister(self):
        WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('program', args=[2020]))
        self.assertNotContains(response, 'Wypisz się')
        self.assertContains(response, 'Byłeś zapisany')

    @freeze_time('2020-05-01 12:00:00')
    def test_redirect_register_unauthenticated(self):
        # User not logged in, redirect to login
        response = self.client.post(reverse('register_to_workshop', args=[self.workshop.year.pk, self.workshop.name]))
        data = response.json()
        self.assertIn('error', data)
        self.assertIn('redirect', data)
        self.assertNotIn('content', data)
        self.assertEqual(data['error'], 'Jesteś niezalogowany')
        self.assertURLEqual(data['redirect'], reverse('login'))

    @freeze_time('2020-05-01 12:00:00')
    def test_can_register_user(self):
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('register_to_workshop', args=[self.workshop.year.pk, self.workshop.name]))
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertNotIn('error', data)
        self.assertIn('content', data)
        self.assertIn('Wypisz się', data['content'])
        self.assertTrue(WorkshopParticipant.objects.filter(workshop=self.workshop, user_profile=self.participant_user.userprofile).exists())

    @freeze_time('2020-05-01 12:00:00')
    def test_cant_register_user_again(self):
        # User already registered, can't register again
        WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('register_to_workshop', args=[self.workshop.year.pk, self.workshop.name]))
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertIn('content', data)
        self.assertEqual(data['error'], 'Już jesteś zapisany na te warsztaty')

    @freeze_time('2020-05-01 12:00:00')
    def test_can_unregister_user(self):
        WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('unregister_from_workshop', args=[self.workshop.year.pk, self.workshop.name]))
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertNotIn('error', data)
        self.assertIn('content', data)
        self.assertIn('Zapisz się', data['content'])
        self.assertFalse(WorkshopParticipant.objects.filter(workshop=self.workshop, user_profile=self.participant_user.userprofile).exists())

    @freeze_time('2020-05-01 12:00:00')
    def test_cant_unregister_user_again(self):
        # User not registered, can't unregister
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('unregister_from_workshop', args=[self.workshop.year.pk, self.workshop.name]))
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertIn('content', data)
        self.assertEqual(data['error'], 'Nie jesteś zapisany na te warsztaty')

    @freeze_time('2020-12-01 12:00:00')
    def test_cannot_register(self):
        # After workshops started, registration cannot be changed
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('register_to_workshop', args=[self.workshop.year.pk, self.workshop.name]))
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertNotIn('content', data)
        self.assertEqual(data['error'], 'Kwalifikacja na te warsztaty została zakończona.')
        self.assertFalse(WorkshopParticipant.objects.filter(workshop=self.workshop, user_profile=self.participant_user.userprofile).exists())

    @freeze_time('2020-12-01 12:00:00')
    def test_cannot_unregister(self):
        # After workshops started, registration cannot be changed
        WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('unregister_from_workshop', args=[self.workshop.year.pk, self.workshop.name]))
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertNotIn('content', data)
        self.assertEqual(data['error'], 'Kwalifikacja na te warsztaty została zakończona.')
        self.assertTrue(WorkshopParticipant.objects.filter(workshop=self.workshop, user_profile=self.participant_user.userprofile).exists())

    @freeze_time('2020-05-01 12:00:00')
    def test_cannot_unregister_with_results(self):
        # User cannot unregister after he has qualification results for this workshop
        WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile, qualification_result=15)
        self.client.force_login(self.participant_user)
        response = self.client.post(reverse('unregister_from_workshop', args=[self.workshop.year.pk, self.workshop.name]))
        data = response.json()
        self.assertNotIn('redirect', data)
        self.assertIn('error', data)
        self.assertNotIn('content', data)
        self.assertEqual(data['error'], 'Masz już wyniki z tej kwalifikacji - nie możesz się wycofać.')
        self.assertTrue(WorkshopParticipant.objects.filter(workshop=self.workshop, user_profile=self.participant_user.userprofile).exists())

    def _test_can_edit_points(self, user, can_view, can_edit):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        url = reverse('workshop_participants', args=[self.workshop.year.pk, self.workshop.name])

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
                'qualification_result': 2.5,
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
                self.assertEqual(data['qualification_result'], '2.5')
                self.assertEqual(data['comment'], 'Dobrze!')

                participant = WorkshopParticipant.objects.get(workshop=self.workshop, user_profile=self.participant_user.userprofile)
                self.assertEqual(participant.qualification_result, 2.5)
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
    def test_edit_points_lecturer_historical(self):
        # Lecturer can view participants but not edit points from previous years
        Camp.objects.create(year=2021)
        self._test_can_edit_points(self.lecturer_user, True, False)

    @freeze_time('2020-05-01 12:00:00')
    def test_edit_points_admin_historical(self):
        Camp.objects.create(year=2021)
        # Admin can view participants but not edit points from previous years
        self._test_can_edit_points(self.admin_user, True, False)

    @freeze_time('2020-05-01 12:00:00')
    def test_mark_accepted(self):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 7.5
        })
        data = response.json()
        self.assertEqual(data['mark'], wwwtags.qualified_mark(True))

        # Check after page reload
        response = self.client.get(reverse('workshop_participants', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertContains(response, wwwtags.qualified_mark(True))

        # Check participant view
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('mydata_status'))
        self.assertContains(response, wwwtags.qualified_mark(True))

    @freeze_time('2020-05-01 12:00:00')
    def test_mark_rejected(self):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 2.5
        })
        data = response.json()
        self.assertEqual(data['mark'], wwwtags.qualified_mark(False))

        # Check after page reload
        response = self.client.get(reverse('workshop_participants', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertContains(response, wwwtags.qualified_mark(False))

        # Check participant view
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('mydata_status'))
        self.assertContains(response, wwwtags.qualified_mark(False))

    @freeze_time('2020-05-01 12:00:00')
    def test_mark_none(self):
        self.workshop.qualification_threshold = None
        self.workshop.max_points = 10
        self.workshop.save()
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 5
        })
        data = response.json()
        self.assertEqual(data['mark'], wwwtags.qualified_mark(None))

        # Check after page reload
        response = self.client.get(reverse('workshop_participants', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertContains(response, wwwtags.qualified_mark(None))

        # Check participant view
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('mydata_status'))
        self.assertContains(response, wwwtags.qualified_mark(None))

    def assertUsersSeeOnlyTheirOwn(self, url, users_and_data):
        all_data = []
        for _, data in users_and_data:
            all_data += data

        for user, data in users_and_data:
            self.client.force_login(user)
            response = self.client.get(url)
            for el in data:
                self.assertContains(response, el)
            for el in all_data:
                if el not in data:
                    self.assertNotContains(response, el)

    @freeze_time('2020-05-01 12:00:00')
    def test_user_can_see_grade(self):
        WorkshopParticipant.objects.create(workshop=self.workshop,
                                           user_profile=self.participant_user.userprofile,
                                           qualification_result=4,
                                           comment="No mogło być lepiej...")

        wp2 = WorkshopParticipant.objects.create(workshop=self.workshop,
                                                 user_profile=self.participant_user2.userprofile)
        user1_data = (self.participant_user, [
                "4,00 / 10,00",
                "No mogło być lepiej...",
                wwwtags.qualified_mark(False)
            ])
        self.assertUsersSeeOnlyTheirOwn(reverse('mydata_status'), [
            user1_data,
            (self.participant_user2, [wwwtags.qualified_mark(None)]),
        ])
        wp2.qualification_result=12
        wp2.comment="Świetnie!!! Poza skalą!"
        wp2.save()
        self.assertUsersSeeOnlyTheirOwn(reverse('mydata_status'), [
            user1_data,
            (self.participant_user2, [
                "12,00 / 10,00",
                "Świetnie!!! Poza skalą!",
                wwwtags.qualified_mark(True)
            ]),
        ])

    @freeze_time('2020-05-01 12:00:00')
    def test_user_can_see_grade_notification_on_program_page(self):
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('program', args=[2020]))
        self.assertNotContains(response, "Sprawdź wyniki w zakładce")
        WorkshopParticipant.objects.create(workshop=self.workshop,
                                           user_profile=self.participant_user.userprofile,
                                           qualification_result=4,
                                           comment="No mogło być lepiej...")
        response = self.client.get(reverse('program', args=[2020]))
        self.assertContains(response, "Sprawdź wyniki w zakładce")
        response = self.client.get(reverse('program', args=[2019]))
        self.assertNotContains(response, "Sprawdź wyniki w zakładce")

    # NOTE: all of the below tests should work for the editor in solution view as well (they are the exact same form, but in different places)

    @freeze_time('2020-05-01 12:00:00')
    def test_submit_invalid_score_toomanydecimal(self):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 5.125
        })
        self.assertJSONEqual(response.content, {'error': '* qualification_result\n  * Upewnij się, że liczba ma nie więcej niż 2 cyfry po przecinku.'})

    @freeze_time('2020-05-01 12:00:00')
    def test_submit_invalid_score_toomanydigits(self):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 100000
        })
        self.assertJSONEqual(response.content, {'error': '* qualification_result\n  * Upewnij się, że liczba ma nie więcej niż 4 cyfry przed przecinkiem.'})

    @freeze_time('2020-05-01 12:00:00')
    def test_submit_invalid_score_toomanydigits2(self):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 1000000
        })
        self.assertJSONEqual(response.content, {'error': '* qualification_result\n  * Upewnij się, że łącznie nie ma więcej niż 6 cyfr.'})

    @freeze_time('2020-05-01 12:00:00')
    def test_submit_invalid_score_notdigits(self):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 'abc'
        })
        self.assertJSONEqual(response.content, {'error': '* qualification_result\n  * Wpisz liczbę.'})

    @freeze_time('2020-05-01 12:00:00')
    def test_submit_invalid_score_abovemax(self):
        self.workshop.max_points = 10
        self.workshop.save()
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 100
        })
        self.assertJSONEqual(response.content, {'error': '* qualification_result\n  * Nie możesz postawić więcej niż 200% maksymalnej liczby punktów'})

    @freeze_time('2020-05-01 12:00:00')
    def test_submit_invalid_score_belowzero(self):
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': -1
        })
        self.assertJSONEqual(response.content, {'error': '* qualification_result\n  * Upewnij się, że ta wartość jest większa lub równa 0.'})

    @freeze_time('2020-05-01 12:00:00')
    def test_submit_invalid_score_unknownmax(self):
        self.workshop.max_points = None
        self.workshop.save()
        participant = WorkshopParticipant.objects.create(workshop=self.workshop, user_profile=self.participant_user.userprofile)

        # Check save response
        self.client.force_login(self.lecturer_user)
        response = self.client.post(reverse('save_points'), {
            'id': participant.id,
            'qualification_result': 5
        })
        self.assertJSONEqual(response.content, {'error': '* qualification_result\n  * Przed wpisaniem wyników, ustaw maksymalną liczbę punktów możliwą do uzyskania'})
