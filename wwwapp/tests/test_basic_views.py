import datetime

from django.contrib.auth.models import User
from django.test.testcases import TestCase
from django.urls import reverse

from wwwapp.models import Camp, WorkshopType, WorkshopCategory, Workshop, WorkshopParticipant, Article, \
    WorkshopUserProfile


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

        self.participant_user.userprofile.profile_page = '<p>O mnie</p>'
        self.participant_user.userprofile.cover_letter = '<p>Jestem fajny</p>'
        self.participant_user.userprofile.how_do_you_know_about = 'nie wiem'
        self.participant_user.userprofile.save()

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
        self.workshop.lecturer.add(self.lecturer_user.userprofile)
        self.workshop.save()

        WorkshopParticipant.objects.create(workshop=self.workshop, participant=self.participant_user.userprofile,
                                           qualification_result=7.5, comment='Dobrze')

        WorkshopUserProfile.objects.create(user_profile=self.participant_user.userprofile, year=self.year_2020,
                                           status=WorkshopUserProfile.STATUS_ACCEPTED)

        self.article = Article.objects.create(name='test_article', title='Testowy', content='<b>Test</b>',
                                              modified_by=self.admin_user, on_menubar=True)

    def test_index_works(self):
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('index'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

    def test_article_view_works(self):
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edytuj')

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('article', args=[self.article.name]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Edytuj')

    def test_participant_view_works(self):
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

    def test_lecturer_view_works(self):
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

    def test_your_workshops_view_works(self):
        response = self.client.get(reverse('yourWorkshops'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('yourWorkshops'))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('yourWorkshops'))
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('yourWorkshops'))
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('yourWorkshops'))
        self.assertEqual(response.status_code, 200)

    def test_all_workshops_view_works(self):
        response = self.client.get(reverse('allWorkshops'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('allWorkshops'))

        self.client.force_login(self.participant_user)
        response = self.client.get(reverse('allWorkshops'))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.lecturer_user)
        response = self.client.get(reverse('allWorkshops'))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('allWorkshops'))
        self.assertEqual(response.status_code, 200)