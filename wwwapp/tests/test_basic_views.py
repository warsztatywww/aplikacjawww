import datetime

from django.contrib.auth.models import User
from django.test.testcases import TestCase
from django.urls import reverse

from wwwapp.models import Camp, WorkshopType, WorkshopCategory, Workshop, WorkshopParticipant, Article, \
    CampParticipant


# Check if all of the important views at least load without crashing
# This is just so that we have something basic until somebody wries better tests
# TODO: write more proper tests for these views

class TestBasicViews(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2020, start_date=datetime.date(2020, 7, 3), end_date=datetime.date(2020, 7, 15))
        self.year_2020 = Camp.objects.get()

        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')
        self.lecturer_user = User.objects.create_user(
            username='lecturer', email='lecturer@example.com', password='user123')
        self.participant_user = User.objects.create_user(
            username='participant', email='participant@example.com', password='user123')

        self.participant_user.user_profile.profile_page = '<p>O mnie</p>'
        self.participant_user.user_profile.cover_letter = '<p>Jestem fajny</p>'
        self.participant_user.user_profile.how_do_you_know_about = 'nie wiem'
        self.participant_user.user_profile.save()

        self.workshop_type = WorkshopType.objects.create(year=self.year_2020, name='This type')
        self.workshop_category = WorkshopCategory.objects.create(year=self.year_2020, name='This category')

        self.workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=self.workshop_type,
            proposition_description='<p>Testowy opis</p>',
            status=Workshop.STATUS_ACCEPTED,
            qualification_threshold=5,
            max_points=10,
        )
        self.workshop.category.add(self.workshop_category)
        self.workshop.lecturer.add(self.lecturer_user.user_profile)
        self.workshop.save()

        cp = CampParticipant.objects.create(user_profile=self.participant_user.user_profile, year=self.year_2020,
                                            status=CampParticipant.STATUS_ACCEPTED)
        cp.workshop_participation.create(workshop=self.workshop, qualification_result=7.5, comment='Dobrze')

        self.article = Article.objects.create(name='test_article', title='Testowy', content='<b>Test</b>',
                                              modified_by=self.admin_user, on_menubar=True)

    def test_participants_view_works(self):
        response = self.client.get(reverse('participants', args=[self.year_2020.pk]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('participants', args=[self.year_2020.pk]))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('participants', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('participants', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('participants', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 200)

    def test_lecturers_view_works(self):
        response = self.client.get(reverse('lecturers', args=[self.year_2020.pk]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('lecturers', args=[self.year_2020.pk]))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('lecturers', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('lecturers', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('lecturers', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 200)

    def test_all_people_view_works(self):
        response = self.client.get(reverse('all_people'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('all_people'))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('all_people'))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('all_people'))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('all_people'))
        self.assertEqual(response.status_code, 200)

    def test_workshops_view_works(self):
        response = self.client.get(reverse('workshops', args=[self.year_2020.pk]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshops', args=[self.year_2020.pk]))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('workshops', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('workshops', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('workshops', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 200)