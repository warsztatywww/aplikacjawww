import datetime

import mock
from django.contrib.auth.models import User
from django.contrib.messages.api import get_messages
from django.test.testcases import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from freezegun import freeze_time

from wwwapp.templatetags import wwwtags
from wwwapp.models import WorkshopType, WorkshopCategory, Workshop, WorkshopParticipant, WorkshopUserProfile, Camp


class CampQualificationViews(TestCase):
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

        self.participant_user.userprofile.profile_page = '<p>O mnie</p>'
        self.participant_user.userprofile.cover_letter = '<p>Jestem fajny</p>'
        self.participant_user.userprofile.how_do_you_know_about = 'nie wiem'
        self.participant_user.userprofile.save()

        WorkshopType.objects.create(year=self.year_2019, name='Not this type')
        WorkshopType.objects.create(year=self.year_2020, name='This type')
        WorkshopCategory.objects.create(year=self.year_2019, name='Not this category')
        WorkshopCategory.objects.create(year=self.year_2020, name='This category')

        self.workshop1 = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='This type'),
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            qualification_threshold=5,
            max_points=10,
        )
        self.workshop1.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category'))
        self.workshop1.lecturer.add(self.lecturer_user.userprofile)
        self.workshop1.save()

        self.workshop2 = Workshop.objects.create(
            title='Jeszcze fajniejsze warsztaty',
            name='fajniejsze',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='This type'),
            proposition_description='<p>yay</p>',
            status=Workshop.STATUS_ACCEPTED,
            qualification_threshold=5,
            max_points=10,
        )
        self.workshop2.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category'))
        self.workshop2.lecturer.add(self.lecturer_user.userprofile)
        self.workshop2.save()

        WorkshopParticipant.objects.create(workshop=self.workshop1, participant=self.participant_user.userprofile,
                                           qualification_result=7.5, comment='Dobrze')
        WorkshopParticipant.objects.create(workshop=self.workshop2, participant=self.participant_user.userprofile,
                                           qualification_result=2.5, comment='Słabo')

    def test_percentage_result(self):
        self.assertEqual(
            WorkshopParticipant.objects.get(workshop=self.workshop1, participant=self.participant_user.userprofile).result_in_percent(),
            75.0)
        self.assertEqual(
            WorkshopParticipant.objects.get(workshop=self.workshop2, participant=self.participant_user.userprofile).result_in_percent(),
            25.0)

        sum = 0.0
        for participant in WorkshopParticipant.objects.filter(participant=self.participant_user.userprofile):
            sum += float(participant.result_in_percent())
        self.assertEqual(sum, 100.0)

    @override_settings(MAX_POINTS_PERCENT=200)
    def test_percentage_huge(self):
        participant = WorkshopParticipant.objects.get(workshop=self.workshop1, participant=self.participant_user.userprofile)
        participant.qualification_result = 2137
        participant.save()
        self.assertEqual(participant.result_in_percent(), 200.0)

    def test_percentage_negative(self):
        participant = WorkshopParticipant.objects.get(workshop=self.workshop1, participant=self.participant_user.userprofile)
        participant.qualification_result = -2137
        participant.save()
        self.assertEqual(participant.result_in_percent(), 0.0)

    def test_profile_page_unauthenticated(self):
        # Unauthed users see only the profile page
        response = self.client.get(reverse('profile', args=[self.participant_user.pk]))
        self.assertContains(response, 'O mnie')
        self.assertNotContains(response, 'Jestem fajny')
        self.assertNotContains(response, 'nie wiem')

    def test_profile_page_self(self):
        # You see everything on your own profile page
        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('profile', args=[self.participant_user.pk]))
        self.assertContains(response, 'O mnie')
        self.assertContains(response, 'Jestem fajny')
        self.assertContains(response, 'nie wiem')

    def test_profile_page_admin(self):
        # Admins see everything on your own profile page
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('profile', args=[self.participant_user.pk]))
        self.assertContains(response, 'O mnie')
        self.assertContains(response, 'Jestem fajny')
        self.assertContains(response, 'nie wiem')

    def test_profile_page_other(self):
        # Others see only your profile page
        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('profile', args=[self.participant_user.pk]))
        self.assertContains(response, 'O mnie')
        self.assertNotContains(response, 'Jestem fajny')
        self.assertNotContains(response, 'nie wiem')

    def test_edit_profile_unauthed(self):
        # Trying to edit the profile unauthed redirects to login page
        response = self.client.get(reverse('mydata_profile'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('mydata_profile'))

        response = self.client.post(reverse('mydata_profile'), {
            'first_name': 'Użytkownik',
            'last_name': 'Testowy',
            'email': 'test@example.com',
            'gender': 'M',
            'school': 'Internet WWW',
            'matura_exam_year': 2038,
            'how_do_you_know_about': 'GitHub',
        })
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('mydata_profile'))

        response = self.client.get(reverse('mydata_profile_page'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('mydata_profile_page'))

        response = self.client.post(reverse('mydata_profile_page'), {
            'profile_page': '<p>mój profil</p>',
        })
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('mydata_profile_page'))

        response = self.client.get(reverse('mydata_cover_letter'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('mydata_cover_letter'))

        response = self.client.post(reverse('mydata_cover_letter'), {
            'cover_letter': '<p>mój list</p>',
        })
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('mydata_cover_letter'))

        response = self.client.get(reverse('mydata_user_info'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('mydata_user_info'))

        response = self.client.post(reverse('mydata_user_info'), {
            'pesel': '98101672714',
            'address': 'Test!',
            'phone': '601123456',
            'start_date': '03.07.2020',
            'end_date': '15.07.2020',
            'tshirt_size': 'XS',
            'comments': 'to działa?',
        })
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('mydata_user_info'))

    def test_edit_profile(self):
        self.client.force_login(self.participant_user)

        response = self.client.post(reverse('mydata_profile'), {
            'first_name': 'Użytkownik',
            'last_name': 'Testowy',
            'email': 'test@example.com',
            'gender': 'M',
            'school': 'Internet WWW',
            'matura_exam_year': 2038,
            'how_do_you_know_about': 'GitHub',
        })
        self.assertRedirects(response, reverse('mydata_profile'))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        response = self.client.post(reverse('mydata_profile_page'), {
            'profile_page': '<p>mój profil</p>',
        })
        self.assertRedirects(response, reverse('mydata_profile_page'))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        response = self.client.post(reverse('mydata_cover_letter'), {
            'cover_letter': '<p>mój list</p>',
        })
        self.assertRedirects(response, reverse('mydata_cover_letter'))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        response = self.client.post(reverse('mydata_user_info'), {
            'pesel': '98101672714',
            'address': 'Test!',
            'phone': '601123456',
            'start_date': '03.07.2020',
            'end_date': '15.07.2020',
            'tshirt_size': 'XS',
            'comments': 'to działa?',
        })
        self.assertRedirects(response, reverse('mydata_user_info'))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        self.participant_user.refresh_from_db()
        self.participant_user.userprofile.refresh_from_db()
        self.participant_user.userprofile.user_info.refresh_from_db()
        self.assertEqual(self.participant_user.first_name, 'Użytkownik')
        self.assertEqual(self.participant_user.last_name, 'Testowy')
        self.assertEqual(self.participant_user.email, 'test@example.com')
        self.assertEqual(self.participant_user.userprofile.gender, 'M')
        self.assertEqual(self.participant_user.userprofile.school, 'Internet WWW')
        self.assertEqual(self.participant_user.userprofile.matura_exam_year, 2038)
        self.assertEqual(self.participant_user.userprofile.how_do_you_know_about, 'GitHub')
        self.assertHTMLEqual(self.participant_user.userprofile.profile_page, '<p>mój profil</p>')
        self.assertHTMLEqual(self.participant_user.userprofile.cover_letter, '<p>mój list</p>')
        self.assertEqual(self.participant_user.userprofile.user_info.pesel, '98101672714')
        self.assertEqual(self.participant_user.userprofile.user_info.address, 'Test!')
        self.assertEqual(self.participant_user.userprofile.user_info.phone, '601123456')
        self.assertEqual(self.participant_user.userprofile.user_info.start_date.year, 2020)
        self.assertEqual(self.participant_user.userprofile.user_info.start_date.month, 7)
        self.assertEqual(self.participant_user.userprofile.user_info.start_date.day, 3)
        self.assertEqual(self.participant_user.userprofile.user_info.end_date.year, 2020)
        self.assertEqual(self.participant_user.userprofile.user_info.end_date.month, 7)
        self.assertEqual(self.participant_user.userprofile.user_info.end_date.day, 15)
        self.assertEqual(self.participant_user.userprofile.user_info.tshirt_size, 'XS')
        self.assertEqual(self.participant_user.userprofile.user_info.comments, 'to działa?')

    def test_pesel_validation(self):
        self.client.force_login(self.participant_user)

        response = self.client.post(reverse('mydata_user_info'), {
            'pesel': '98101672710',
            'address': '',
            'phone': '',
            'start_date': '',
            'end_date': '',
            'tshirt_size': 'no_idea',
            'comments': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'user_info_page_form', 'pesel', 'Suma kontrolna PESEL się nie zgadza.')

        response = self.client.post(reverse('mydata_user_info'), {
            'pesel': '9810167271',
            'address': '',
            'phone': '',
            'start_date': '',
            'end_date': '',
            'tshirt_size': 'no_idea',
            'comments': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'user_info_page_form', 'pesel', 'Długość numeru PESEL jest niepoprawna (10).')

        response = self.client.post(reverse('mydata_user_info'), {
            'page': 'user_info',
            'pesel': 'abcdefghijk',
            'address': '',
            'phone': '',
            'start_date': '',
            'end_date': '',
            'tshirt_size': 'no_idea',
            'comments': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'user_info_page_form', 'pesel', 'PESEL nie składa się z samych cyfr.')

        response = self.client.post(reverse('mydata_user_info'), {
            'page': 'user_info',
            'pesel': '12345678903',
            'address': '',
            'phone': '',
            'start_date': '',
            'end_date': '',
            'tshirt_size': 'no_idea',
            'comments': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'user_info_page_form', 'pesel', 'Data urodzenia zawarta w numerze PESEL nie istnieje.')

    def test_unauthed_cannot_set_status(self):
        with mock.patch('wwwapp.models.WorkshopUserProfile.save', autospec=True, side_effect=WorkshopUserProfile.save) as save:
            response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'accept'})
            save.assert_not_called()
            self.assertRedirects(response, reverse('login') + '?next=' + reverse('profile', args=[self.participant_user.pk]))
        with mock.patch('wwwapp.models.WorkshopUserProfile.save', autospec=True, side_effect=WorkshopUserProfile.save) as save:
            response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'reject'})
            save.assert_not_called()
            self.assertRedirects(response, reverse('login') + '?next=' + reverse('profile', args=[self.participant_user.pk]))
        WorkshopUserProfile.objects.create(year=self.year_2020, user_profile=self.participant_user.userprofile, status=WorkshopUserProfile.STATUS_ACCEPTED)
        with mock.patch('wwwapp.models.WorkshopUserProfile.save', autospec=True, side_effect=WorkshopUserProfile.save) as save:
            response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'delete'})
            save.assert_not_called()
            self.assertRedirects(response, reverse('login') + '?next=' + reverse('profile', args=[self.participant_user.pk]))
        with mock.patch('wwwapp.models.WorkshopUserProfile.save', autospec=True, side_effect=WorkshopUserProfile.save) as save:
            response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'cancel'})
            save.assert_not_called()
            self.assertRedirects(response, reverse('login') + '?next=' + reverse('profile', args=[self.participant_user.pk]))

    def test_user_cannot_set_status(self):
        self.client.force_login(self.participant_user)
        with mock.patch('wwwapp.models.WorkshopUserProfile.save', autospec=True, side_effect=WorkshopUserProfile.save) as save:
            response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'accept'})
            save.assert_not_called()
            self.assertEqual(response.status_code, 403)
        with mock.patch('wwwapp.models.WorkshopUserProfile.save', autospec=True, side_effect=WorkshopUserProfile.save) as save:
            response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'reject'})
            save.assert_not_called()
            self.assertEqual(response.status_code, 403)
        WorkshopUserProfile.objects.create(year=self.year_2020, user_profile=self.participant_user.userprofile, status=WorkshopUserProfile.STATUS_ACCEPTED)
        with mock.patch('wwwapp.models.WorkshopUserProfile.save', autospec=True, side_effect=WorkshopUserProfile.save) as save:
            response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'delete'})
            save.assert_not_called()
            self.assertEqual(response.status_code, 403)
        with mock.patch('wwwapp.models.WorkshopUserProfile.save', autospec=True, side_effect=WorkshopUserProfile.save) as save:
            response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'cancel'})
            save.assert_not_called()
            self.assertEqual(response.status_code, 403)

    def test_admin_can_accept(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'accept'})
        self.assertEqual(response.status_code, 200)

        wup = WorkshopUserProfile.objects.get(year=self.year_2020, user_profile=self.participant_user.userprofile)
        self.assertEqual(wup.status, WorkshopUserProfile.STATUS_ACCEPTED)

        self.assertContains(response, '<span class="qualified">✔')

    def test_admin_can_reject(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'reject'})
        self.assertEqual(response.status_code, 200)

        wup = WorkshopUserProfile.objects.get(year=self.year_2020, user_profile=self.participant_user.userprofile)
        self.assertEqual(wup.status, WorkshopUserProfile.STATUS_REJECTED)

        self.assertContains(response, '<span class="not-qualified">✘')

    def test_admin_can_cancel(self):
        WorkshopUserProfile.objects.create(year=self.year_2020, user_profile=self.participant_user.userprofile, status=WorkshopUserProfile.STATUS_ACCEPTED)
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'cancel'})
        self.assertEqual(response.status_code, 200)

        wup = WorkshopUserProfile.objects.get(year=self.year_2020, user_profile=self.participant_user.userprofile)
        self.assertEqual(wup.status, WorkshopUserProfile.STATUS_CANCELLED)

        self.assertContains(response, '<span class="maybe-qualified">😞')

    def test_admin_can_delete_status(self):
        WorkshopUserProfile.objects.create(year=self.year_2020, user_profile=self.participant_user.userprofile, status=WorkshopUserProfile.STATUS_ACCEPTED)
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'delete'})
        self.assertEqual(response.status_code, 200)

        self.assertFalse(WorkshopUserProfile.objects.filter(year=self.year_2020, user_profile=self.participant_user.userprofile).exists())

        self.assertNotContains(response, '<span class="qualified">✔')
        self.assertNotContains(response, '<span class="not-qualified">✘')
        self.assertNotContains(response, '<span class="maybe-qualified">😞')

    def test_admin_cannot_double_accept(self):
        WorkshopUserProfile.objects.create(year=self.year_2020, user_profile=self.participant_user.userprofile, status=WorkshopUserProfile.STATUS_ACCEPTED)
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'accept'})
        self.assertEqual(response.status_code, 200)

        wup = WorkshopUserProfile.objects.get(year=self.year_2020, user_profile=self.participant_user.userprofile)
        self.assertEqual(wup.status, WorkshopUserProfile.STATUS_ACCEPTED)

        self.assertContains(response, '<span class="qualified">✔')

    def test_admin_cannot_double_reject(self):
        WorkshopUserProfile.objects.create(year=self.year_2020, user_profile=self.participant_user.userprofile, status=WorkshopUserProfile.STATUS_REJECTED)
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'reject'})
        self.assertEqual(response.status_code, 200)

        wup = WorkshopUserProfile.objects.get(year=self.year_2020, user_profile=self.participant_user.userprofile)
        self.assertEqual(wup.status, WorkshopUserProfile.STATUS_REJECTED)

        self.assertContains(response, '<span class="not-qualified">✘')

    def test_admin_cannot_double_delete_status(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('profile', args=[self.participant_user.pk]), {'qualify': 'delete'})
        self.assertEqual(response.status_code, 200)

        self.assertFalse(WorkshopUserProfile.objects.filter(year=self.year_2020, user_profile=self.participant_user.userprofile).exists())

        self.assertNotContains(response, '<span class="qualified">✔')
        self.assertNotContains(response, '<span class="not-qualified">✘')
        self.assertNotContains(response, '<span class="maybe-qualified">😞')
