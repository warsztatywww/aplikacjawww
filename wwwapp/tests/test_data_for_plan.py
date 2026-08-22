import datetime

from django.contrib.auth.models import User, Permission
from django.test.testcases import TestCase
from django.urls import reverse

from wwwapp.models import Camp, WorkshopType, Workshop, WorkshopParticipant, CampParticipant


class TestDataForPlan(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2020, start_date=datetime.date(2020, 7, 3), end_date=datetime.date(2020, 7, 15))
        self.year_2020 = Camp.objects.get()

        self.export_user = User.objects.create_superuser(username='admin', email='admin@example.com', password='admin123')

        self.participant_user = User.objects.create_user(
            username='participant', email='participant@example.com', password='user123')

        self.workshop_type = WorkshopType.objects.create(year=self.year_2020, name='This type')
        self.workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=self.workshop_type,
            status=Workshop.STATUS_ACCEPTED,
        )

        cp = CampParticipant.objects.create(user_profile=self.participant_user.user_profile, year=self.year_2020,
                                            status=CampParticipant.STATUS_ACCEPTED)
        self.wp = cp.workshop_participation.create(workshop=self.workshop)

        self.url = reverse('dataForPlan', args=[self.year_2020.pk])

    def test_exports_rating(self):
        self.wp.rating = 4
        self.wp.save()

        self.client.force_login(self.export_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        participation = response.json()['participation']
        self.assertEqual(len(participation), 1)
        self.assertEqual(participation[0]['rating'], 4)

    def test_exports_null_rating_when_unset(self):
        self.client.force_login(self.export_user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        participation = response.json()['participation']
        self.assertEqual(len(participation), 1)
        self.assertIsNone(participation[0]['rating'])
