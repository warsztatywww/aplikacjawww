import datetime

from django.test.testcases import TestCase
from django.urls import reverse
from freezegun import freeze_time

from wwwapp.models import Camp, User, CampParticipant, Workshop, WorkshopType


class TextIndexView(TestCase):
    def setUp(self):
        Camp.objects.all().update(year=2020, start_date=datetime.date(2020, 7, 3), end_date=datetime.date(2020, 7, 15))
        self.year_2020 = Camp.objects.get()
        self.admin_user = User.objects.create_superuser(username='admin', email='admin@example.com', password='admin123')
        self.user = User.objects.create_user(username='participant', email='participant@example.com', password='user123')
        self.workshop_type = WorkshopType.objects.create(year=self.year_2020, name="type")
        CampParticipant.objects.create(year=self.year_2020, user_profile=self.user.user_profile)


    def test_user_cannot_edit_index(self):
        response = self.client.get(reverse("index"))
        self.assertNotContains(response, 'Edytuj')

    def test_admin_can_edit_index(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'Edytuj')

    @freeze_time('2020-05-01 12:00:00')
    def test_callout_present_when_workshop_proposals_are_open(self):
        self.year_2020.proposal_end_date = datetime.date(2020, 5, 2)
        self.year_2020.save()
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'callout')
        self.assertContains(response, 'Obecnie trwają zgłoszenia warsztatów')

    @freeze_time('2020-05-01 12:00:00')
    def test_callout_present_when_registration_is_open(self):
        self.year_2020.proposal_end_date = datetime.date(2020, 4, 1)
        self.year_2020.save()
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'callout')
        self.assertContains(response, 'Dostępny jest')

    @freeze_time('2020-07-03 12:00:00')
    def test_callout_not_present_after_camp_starts(self):
        response = self.client.get(reverse("index"))
        self.assertNotContains(response, 'callout')

    @freeze_time('2020-05-01 12:00:00')
    def test_mail_notification_present_if_workshops_are_not_present(self):
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'Powiadomienia')
        self.assertContains(response, 'Powiadom mnie, gdy rozpocznie się rejestracja')

    @freeze_time('2020-05-01 12:00:00')
    def test_mail_notification_present_if_workshops_are_not_present_and_user_logged_in(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'Powiadomienia')
        self.assertContains(response, 'Powiadomimy Cię, gdy rozpocznie się rejestracja')

    @freeze_time('2020-05-01 12:00:00')
    def test_mail_notification_not_present_if_workshops_are_present(self):
        Workshop.objects.create(year=self.year_2020, name="Warsztaty", title="Tytuł", type=self.workshop_type, status=Workshop.STATUS_ACCEPTED)
        response = self.client.get(reverse("index"))
        self.assertNotContains(response, 'Powiadomienia')
        self.assertNotContains(response, 'Powiadom mnie, gdy rozpocznie się rejestracja')
    
    @freeze_time('2020-05-01 12:00:00')
    def test_mail_notification_present_when_no_accepted_or_rejected_workshops(self):
        Workshop.objects.create(year=self.year_2020, name="Warsztaty", title="Tytuł", type=self.workshop_type, status=None)
        response = self.client.get(reverse("index"))
        self.assertContains(response, 'Powiadomienia')
        self.assertContains(response, 'Powiadom mnie, gdy rozpocznie się rejestracja')