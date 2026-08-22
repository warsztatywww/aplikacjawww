import datetime

from django.contrib.auth.models import User
from django.test.testcases import TestCase
from django.urls import reverse

from wwwapp.models import Camp, WorkshopType, Workshop, WorkshopParticipant, CampParticipant


class TestWorkshopRating(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2020, start_date=datetime.date(2020, 7, 3), end_date=datetime.date(2020, 7, 15))
        self.year_2020 = Camp.objects.get()

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

        self.rate_url = reverse('rate_workshop', args=[self.year_2020.pk, self.workshop.name])

    def test_requires_login(self):
        response = self.client.post(self.rate_url, {'rating': 5})
        self.assertEqual(response.status_code, 200)
        self.assertIn('redirect', response.json())

    def test_sets_rating(self):
        self.client.force_login(self.participant_user)
        response = self.client.post(self.rate_url, {'rating': 5})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rating'], 5)
        self.wp.refresh_from_db()
        self.assertEqual(self.wp.rating, 5)

    def test_rejects_out_of_range(self):
        self.client.force_login(self.participant_user)
        response = self.client.post(self.rate_url, {'rating': 6})
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.json())
        self.wp.refresh_from_db()
        self.assertIsNone(self.wp.rating)

    def test_rejects_invalid_value(self):
        self.client.force_login(self.participant_user)
        response = self.client.post(self.rate_url, {'rating': 'abc'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.json())

    def test_unregistered_user_cannot_rate(self):
        other_user = User.objects.create_user(username='other', password='user123')
        self.client.force_login(other_user)
        response = self.client.post(self.rate_url, {'rating': 3})
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.json())

    def test_model_validators_reject_out_of_range(self):
        from django.core.exceptions import ValidationError
        self.wp.rating = 6
        with self.assertRaises(ValidationError):
            self.wp.full_clean()
        self.wp.rating = 0
        with self.assertRaises(ValidationError):
            self.wp.full_clean()
        self.wp.rating = 5
        self.wp.full_clean()
