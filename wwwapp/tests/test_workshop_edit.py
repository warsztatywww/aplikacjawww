import datetime
import io
import os

import mock
from django.contrib.auth.models import User
from django.contrib.messages.api import get_messages
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.testcases import TestCase
from django.urls import reverse
from freezegun import freeze_time

from wwwapp.models import WorkshopType, WorkshopCategory, Workshop, Camp, Article


class WorkshopEditViews(TestCase):
    def setUp(self):
        # TODO: This is weird because of the constraint that one Camp object needs to exist at all times
        Camp.objects.all().update(year=2020, start_date=datetime.date(2020, 7, 3), end_date=datetime.date(2020, 7, 15))
        self.year_2020 = Camp.objects.get()
        self.year_2019 = Camp.objects.create(year=2019)

        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')
        self.normal_user = User.objects.create_user(
            username='user', email='user@example.com', password='user123')
        self.another_user = User.objects.create_user(
            username='user2', email='user2@example.com', password='user123')

        WorkshopType.objects.create(year=self.year_2019, name='Not this type')
        WorkshopType.objects.create(year=self.year_2020, name='This type 1')
        WorkshopType.objects.create(year=self.year_2020, name='This type 2')
        WorkshopCategory.objects.create(year=self.year_2019, name='Not this category')
        WorkshopCategory.objects.create(year=self.year_2020, name='This category 1')
        WorkshopCategory.objects.create(year=self.year_2020, name='This category 2')
        WorkshopCategory.objects.create(year=self.year_2020, name='This category 3')

        self.workshop = Workshop.objects.create(
            title='Bardzo fajne warsztaty',
            name='bardzofajne',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='This type 1'),
            proposition_description='<p>Testowy opis</p>'
        )
        self.workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category 1'))
        self.workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category 2'))
        self.workshop.lecturer.add(self.normal_user.userprofile)
        self.workshop.save()

    @freeze_time('2020-05-01 12:00:00')
    def test_create_proposal_unauthenticated(self):
        response = self.client.get(reverse('workshops_add', args=[self.year_2020.pk]))
        self.assertRedirects(response, reverse('login')+'?next='+reverse('workshops_add', args=[self.year_2020.pk]))

        response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
            'title': 'Fajne warsztaty',
            'name': 'fajne',
            'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
            'category': [
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk,
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 2').pk
            ],
            'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
        })
        self.assertRedirects(response, reverse('login')+'?next='+reverse('workshops_add', args=[self.year_2020.pk]))

    @freeze_time('2020-05-01 12:00:00')
    def test_create_proposal_authenticated(self):
        # Proposal end date is not configured and defaults to workshops start

        # Load the form
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('workshops_add', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Not this type')
        self.assertNotContains(response, 'Not this category')
        self.assertContains(response, 'This type 1')
        self.assertContains(response, 'This type 2')
        self.assertContains(response, 'This category 1')
        self.assertContains(response, 'This category 2')
        self.assertContains(response, 'This category 3')

        # Submit
        response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
            'title': 'Fajne warsztaty',
            'name': 'fajne',
            'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
            'category': [
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk,
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 2').pk
            ],
            'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
        })
        self.assertRedirects(response, reverse('workshop_edit', args=[2020, 'fajne']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')
        workshop = Workshop.objects.filter(name='fajne').get()
        self.assertEqual(workshop.title, 'Fajne warsztaty')
        self.assertEqual(workshop.name, 'fajne')
        self.assertEqual(workshop.year, self.year_2020)
        self.assertEqual(workshop.type, WorkshopType.objects.get(year=self.year_2020, name='This type 1'))
        self.assertSetEqual(set(workshop.category.all()), {
            WorkshopCategory.objects.get(year=self.year_2020, name='This category 1'),
            WorkshopCategory.objects.get(year=self.year_2020, name='This category 2'),
        })
        self.assertHTMLEqual(workshop.proposition_description, '<p>Na tych warsztatach będziemy testować fajną stronę</p>')
        self.assertSetEqual(set(workshop.lecturer.all()), {self.normal_user.userprofile})
        self.assertIsNone(workshop.status)

    @freeze_time('2020-05-01 12:00:00')
    def test_create_proposal_wrong_type_year(self):
        self.client.force_login(self.normal_user)
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
                'title': 'Fajne warsztaty',
                'name': 'fajne',
                'type': WorkshopType.objects.get(year=self.year_2019, name='Not this type').pk,
                'category': [
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk,
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 2').pk
                ],
                'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
            })
            save.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertFormError(response, 'form', 'type', 'Wybierz poprawną wartość. Podana nie jest jednym z dostępnych wyborów.')

    @freeze_time('2020-05-01 12:00:00')
    def test_create_proposal_wrong_category_year(self):
        self.client.force_login(self.normal_user)
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
                'title': 'Fajne warsztaty',
                'name': 'fajne',
                'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
                'category': [
                    WorkshopCategory.objects.get(year=self.year_2019, name='Not this category').pk
                ],
                'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
            })
            save.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertFormError(response, 'form', 'category', 'Wybierz poprawną wartość. 1 nie jest żadną z dostępnych opcji.')

    def test_model_save_workshop_wrong_type_year(self):
        workshop = Workshop.objects.create(
            title='Test',
            name='testtest',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2019, name='Not this type')
        )
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category 1'))
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2020, name='This category 2'))
        workshop.lecturer.add(self.normal_user.userprofile)
        with self.assertRaisesRegexp(ValidationError, 'Typ warsztatów nie jest z tego roku'):
            workshop.full_clean()

    def test_model_save_workshop_wrong_category_year(self):
        workshop = Workshop.objects.create(
            title='Test',
            name='testtest',
            year=self.year_2020,
            type=WorkshopType.objects.get(year=self.year_2020, name='This type 1')
        )
        workshop.category.add(WorkshopCategory.objects.get(year=self.year_2019, name='Not this category'))
        workshop.lecturer.add(self.normal_user.userprofile)
        workshop.save()
        with self.assertRaisesRegexp(ValidationError, 'Kategoria warsztatów nie jest z tego roku'):
            workshop.full_clean()

    @freeze_time('2020-05-01 12:00:00')
    def test_create_proposal_duplicate_slug(self):
        self.client.force_login(self.normal_user)
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
                'title': 'Kolejne bardzo fajne warsztaty',
                'name': 'bardzofajne',
                'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
                'category': [
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk
                ],
                'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
            })
            save.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertFormError(response, 'form', None, 'Workshop z tymi Year i Name już istnieje.')

    @freeze_time('2021-05-01 12:00:00')
    def test_create_proposal_duplicate_slug_different_year(self):
        year_2021 = Camp.objects.create(year=2021)
        type = WorkshopType.objects.create(year=year_2021, name='Future type')
        category = WorkshopCategory.objects.create(year=year_2021, name='Future category')

        self.client.force_login(self.normal_user)
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshops_add', args=[year_2021.pk]), {
                'title': 'Kolejne bardzo fajne warsztaty',
                'name': 'bardzofajne',
                'type': type.pk,
                'category': [
                    category.pk
                ],
                'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
            })
            save.assert_called()

            self.assertRedirects(response, reverse('workshop_edit', args=[2021, 'bardzofajne']))
            messages = get_messages(response.wsgi_request)
            self.assertEqual(len(messages), 1)
            self.assertEqual(list(messages)[0].message, 'Zapisano.')

            self.assertTrue(Workshop.objects.filter(year=self.year_2020, name='bardzofajne').count() == 1)
            self.assertTrue(Workshop.objects.filter(year=year_2021, name='bardzofajne').count() == 1)

    @freeze_time('2020-12-01 12:00:00')
    def test_create_proposal_closed(self):
        # Proposal end date is not configured and defaults to workshops start

        # Load the form
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('workshops_add', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Zgłoszenia warsztatów nie są obecnie aktywne')

        # Submit
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
                'title': 'Fajne warsztaty',
                'name': 'fajne',
                'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
                'category': [
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk,
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 2').pk
                ],
                'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
            })
            save.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Zgłoszenia warsztatów nie są obecnie aktywne')

    @freeze_time('2020-05-01 12:00:00')
    def test_create_proposal_closed_with_explicit_date(self):
        # Proposal end date is configured to be an explicit date, earlier than workshops start
        Camp.objects.filter(year=2020).update(proposal_end_date=datetime.date(2020, 3, 1))

        # Load the form
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('workshops_add', args=[self.year_2020.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Zgłoszenia warsztatów nie są obecnie aktywne')

        # Submit
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
                'title': 'Fajne warsztaty',
                'name': 'fajne',
                'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
                'category': [
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk,
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 2').pk
                ],
                'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
            })
            save.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Zgłoszenia warsztatów nie są obecnie aktywne')

    def _assert_can_edit_proposal(self, user, can_open, can_edit):
        url = reverse('workshop_edit', args=[2020, 'bardzofajne'])

        if user is not None:
            self.client.force_login(user)
        else:
            self.client.logout()
        response = self.client.get(url)
        if not can_open:
            if user is None:
                self.assertRedirects(response, reverse('login') + '?next=' + url)
            else:
                self.assertEqual(response.status_code, 403)
        else:
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Testowy opis')

        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(url, {
                'title': 'Niefajne warsztaty',
                'name': 'niefajne',
                'type': WorkshopType.objects.get(year=self.year_2020, name='This type 2').pk,
                'category': [
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 3').pk,
                ],
                'proposition_description': '<p>PRZEGRAŁEM!!</p>'
            })
            if not can_edit:
                save.assert_not_called()
                if not can_open:
                    if user is None:
                        self.assertRedirects(response, reverse('login') + '?next=' + url)
                    else:
                        self.assertEqual(response.status_code, 403)
                else:
                    self.assertEqual(response.status_code, 200)
            else:
                save.assert_called()
                self.assertRedirects(response, reverse('workshop_edit', args=[2020, 'niefajne']))
                messages = get_messages(response.wsgi_request)
                self.assertEqual(len(messages), 1)
                self.assertEqual(list(messages)[0].message, 'Zapisano.')
                self.assertFalse(Workshop.objects.filter(name='bardzofajne').exists())
                workshop = Workshop.objects.get(name='niefajne')
                self.assertEqual(workshop.title, 'Niefajne warsztaty')
                self.assertEqual(workshop.name, 'niefajne')
                self.assertEqual(workshop.year, self.year_2020)
                self.assertEqual(workshop.type, WorkshopType.objects.get(year=self.year_2020, name='This type 2'))
                self.assertSetEqual(set(workshop.category.all()), {
                    WorkshopCategory.objects.get(year=self.year_2020, name='This category 3'),
                })
                self.assertHTMLEqual(workshop.proposition_description, '<p>PRZEGRAŁEM!!</p>')
                self.assertSetEqual(set(workshop.lecturer.all()), {self.normal_user.userprofile})

    def test_edit_proposal_unauthenticated(self):
        # Unauthenticated user can't view or edit the proposal
        self._assert_can_edit_proposal(None, can_open=False, can_edit=False)

    def test_edit_proposal_not_lecturer(self):
        # Other users can't view or edit the proposal
        self._assert_can_edit_proposal(self.another_user, can_open=False, can_edit=False)

    def test_edit_proposal_lecturer(self):
        # Lecturer can edit the proposal
        self._assert_can_edit_proposal(self.normal_user, can_open=True, can_edit=True)

    def test_edit_proposal_admin(self):
        # Admin can edit the proposal
        self._assert_can_edit_proposal(self.admin_user, can_open=True, can_edit=True)

    def test_edit_accepted_proposal(self):
        # Proposal description cannot be changed once it's accepted or rejected
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()

        self.client.force_login(self.normal_user)

        url = reverse('workshop_edit', args=[2020, 'bardzofajne'])
        response = self.client.post(url, {
            'title': 'Niefajne warsztaty',
            'name': 'niefajne',
            'type': WorkshopType.objects.get(year=self.year_2020, name='This type 2').pk,
            'category': [
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 3').pk,
            ],
            'proposition_description': '<p>PRZEGRAŁEM!!</p>',
            'is_qualifying': '',
            'qualification_threshold': 1337,
            'max_points': 2137,
            'page_content': '<p>Zapraszam na moje warsztaty</p>',
            'page_content_is_public': 'on',
        })
        self.assertRedirects(response, reverse('workshop_edit', args=[2020, 'niefajne']))
        workshop = Workshop.objects.get(name='niefajne')
        self.assertHTMLEqual(workshop.proposition_description, '<p>Testowy opis</p>')

    def test_edit_historical_proposal_lecturer(self):
        # Lecturer can't edit the proposal from previous year
        Camp.objects.create(year=2021)
        self._assert_can_edit_proposal(self.normal_user, can_open=True, can_edit=False)

    def test_edit_historical_proposal_admin(self):
        # Admin can't edit the proposal from previous year
        Camp.objects.create(year=2021)
        self._assert_can_edit_proposal(self.admin_user, can_open=True, can_edit=False)

    def _assert_can_edit_public_page(self, user, can_open, can_see_page_edit, can_edit, can_edit_page):
        url = reverse('workshop_edit', args=[2020, 'bardzofajne'])

        if user is not None:
            self.client.force_login(user)
        else:
            self.client.logout()

        # Open the editor
        response = self.client.get(url)
        if not can_open:
            if user is None:
                self.assertRedirects(response, reverse('login') + '?next=' + url)
            else:
                self.assertEqual(response.status_code, 403)
        else:
            self.assertEqual(response.status_code, 200)

        if can_see_page_edit:
            self.assertContains(response, 'Strona warsztatów')
        elif can_open:
            self.assertNotContains(response, 'Strona warsztatów')

        # Submit the edits
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(url, {
                'title': 'Bardzo fajne warsztaty',
                'name': 'bardzofajne',
                'type': WorkshopType.objects.get(year=2020, name='This type 1').pk,
                'category': [
                    WorkshopCategory.objects.get(year=2020, name='This category 1').pk,
                    WorkshopCategory.objects.get(year=2020, name='This category 2').pk,
                ],
                'proposition_description': '<p>Testowy opis</p>',
                'is_qualifying': '',
                'qualification_threshold': 1337,
                'max_points': 2137,
                'page_content': '<p>Zapraszam na moje warsztaty</p>',
                'page_content_is_public': 'on',
            })
            if not can_edit:
                save.assert_not_called()
                if not can_open:
                    if user is None:
                        self.assertRedirects(response, reverse('login') + '?next=' + url)
                    else:
                        self.assertEqual(response.status_code, 403)
                else:
                    self.assertEqual(response.status_code, 200)
            else:
                save.assert_called()
                self.assertRedirects(response, url)
                messages = get_messages(response.wsgi_request)
                self.assertEqual(len(messages), 1)
                self.assertEqual(list(messages)[0].message, 'Zapisano.')

                workshop = Workshop.objects.get(name='bardzofajne')
                if can_edit_page:
                    self.assertEqual(workshop.is_qualifying, False)
                    self.assertEqual(workshop.qualification_threshold, 1337)
                    self.assertEqual(workshop.max_points, 2137)
                    self.assertHTMLEqual(workshop.page_content, '<p>Zapraszam na moje warsztaty</p>')
                    self.assertEqual(workshop.page_content_is_public, True)
                else:
                    self.assertEqual(workshop.is_qualifying, True)
                    self.assertIsNone(workshop.qualification_threshold)
                    self.assertIsNone(workshop.max_points)
                    self.assertEqual(workshop.page_content, '')
                    self.assertEqual(workshop.page_content_is_public, False)

    def test_edit_public_page_unauthenticated(self):
        # Unauthenticated user can't edit the public page
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self._assert_can_edit_public_page(None,
                                          can_open=False, can_see_page_edit=False, can_edit=False, can_edit_page=False)

    def test_edit_public_page_not_lecturer(self):
        # Other users can't edit the public page
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self._assert_can_edit_public_page(self.another_user,
                                          can_open=False, can_see_page_edit=False, can_edit=False, can_edit_page=False)

    def test_edit_public_page_lecturer(self):
        # Lecturer can edit the public page
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self._assert_can_edit_public_page(self.normal_user,
                                          can_open=True, can_see_page_edit=True, can_edit=True, can_edit_page=True)

    def test_edit_public_page_admin(self):
        # Admin can edit the public page
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self._assert_can_edit_public_page(self.admin_user,
                                          can_open=True, can_see_page_edit=True, can_edit=True, can_edit_page=True)

    def test_edit_public_page_not_accepted_lecturer(self):
        # Lecturer can't edit the public page until it's accepted
        self.workshop.status = None
        self.workshop.save()
        self._assert_can_edit_public_page(self.normal_user,
                                          can_open=True, can_see_page_edit=False, can_edit=True, can_edit_page=False)

    def test_edit_public_page_not_accepted_admin(self):
        # Admin can't edit the public page until it's accepted
        self.workshop.status = None
        self.workshop.save()
        self._assert_can_edit_public_page(self.admin_user,
                                          can_open=True, can_see_page_edit=False, can_edit=True, can_edit_page=False)

    def test_edit_public_page_rejected_lecturer(self):
        # Lecturer can't edit the public page if it's rejected
        self.workshop.status = Workshop.STATUS_REJECTED
        self.workshop.save()
        self._assert_can_edit_public_page(self.normal_user,
                                          can_open=True, can_see_page_edit=False, can_edit=True, can_edit_page=False)

    def test_edit_public_page_rejected_admin(self):
        # Admin can't edit the public page if it's rejected
        self.workshop.status = Workshop.STATUS_REJECTED
        self.workshop.save()
        self._assert_can_edit_public_page(self.admin_user,
                                          can_open=True, can_see_page_edit=False, can_edit=True, can_edit_page=False)

    def test_edit_public_page_cancelled_lecturer(self):
        # Lecturer can edit the public page when cancelled
        self.workshop.status = Workshop.STATUS_CANCELLED
        self.workshop.save()
        self._assert_can_edit_public_page(self.normal_user,
                                          can_open=True, can_see_page_edit=True, can_edit=True, can_edit_page=True)

    def test_edit_public_page_cancelled_admin(self):
        # Admin can edit the public page when cancelled
        self.workshop.status = Workshop.STATUS_CANCELLED
        self.workshop.save()
        self._assert_can_edit_public_page(self.admin_user,
                                          can_open=True, can_see_page_edit=True, can_edit=True, can_edit_page=True)

    def test_edit_historical_public_page_lecturer(self):
        # Lecturer can't edit the public page from previous year
        Camp.objects.create(year=2021)
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self._assert_can_edit_public_page(self.normal_user,
                                          can_open=True, can_see_page_edit=True, can_edit=False, can_edit_page=False)

    def test_edit_historical_public_page_admin(self):
        # Admin can't edit the public page from previous year
        Camp.objects.create(year=2021)
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self._assert_can_edit_public_page(self.admin_user,
                                          can_open=True, can_see_page_edit=True, can_edit=False, can_edit_page=False)

    def test_edit_qual_problems_add(self):
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self.client.force_login(self.normal_user)

        data = os.urandom(1024 * 1024)

        url = reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name])
        response = self.client.post(url, {
            'title': 'Bardzo fajne warsztaty',
            'name': 'bardzofajne',
            'type': WorkshopType.objects.get(year=2020, name='This type 1').pk,
            'category': [
                WorkshopCategory.objects.get(year=2020, name='This category 1').pk,
                WorkshopCategory.objects.get(year=2020, name='This category 2').pk,
            ],
            'qualification_problems': io.BytesIO(data),
            'is_qualifying': 'on',
            'qualification_threshold': '',
            'max_points': '',
            'page_content': '',
            'page_content_is_public': '',
        })
        self.assertRedirects(response, url)
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        response = self.client.get(reverse('qualification_problems', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)

    def test_edit_qual_problems_change(self):
        self.workshop.qualification_problems = SimpleUploadedFile('problems.pdf', os.urandom(1024 * 1024))
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self.client.force_login(self.normal_user)

        data = os.urandom(1024 * 1024)

        url = reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name])
        response = self.client.post(url, {
            'title': 'Bardzo fajne warsztaty',
            'name': 'bardzofajne',
            'type': WorkshopType.objects.get(year=2020, name='This type 1').pk,
            'category': [
                WorkshopCategory.objects.get(year=2020, name='This category 1').pk,
                WorkshopCategory.objects.get(year=2020, name='This category 2').pk,
            ],
            'qualification_problems': io.BytesIO(data),
            'is_qualifying': 'on',
            'qualification_threshold': '',
            'max_points': '',
            'page_content': '',
            'page_content_is_public': '',
        })
        self.assertRedirects(response, url)
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        response = self.client.get(reverse('qualification_problems', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)

    def test_edit_qual_problems_no_change(self):
        data = os.urandom(1024 * 1024)
        self.workshop.qualification_problems = SimpleUploadedFile('problems.pdf', data)
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self.client.force_login(self.normal_user)

        url = reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name])
        response = self.client.post(url, {
            'title': 'Bardzo fajne warsztaty',
            'name': 'bardzofajne',
            'type': WorkshopType.objects.get(year=2020, name='This type 1').pk,
            'category': [
                WorkshopCategory.objects.get(year=2020, name='This category 1').pk,
                WorkshopCategory.objects.get(year=2020, name='This category 2').pk,
            ],
            'is_qualifying': 'on',
            'qualification_threshold': '',
            'max_points': '',
            'page_content': '',
            'page_content_is_public': '',
        })
        self.assertRedirects(response, url)
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        response = self.client.get(reverse('qualification_problems', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)

    def test_view_empty_qual_problems(self):
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        response = self.client.get(reverse('qualification_problems', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertEqual(response.status_code, 404)

    def test_view_proposal_qual_problems(self):
        data = os.urandom(1024 * 1024)
        self.workshop.qualification_problems = SimpleUploadedFile('problems.pdf', data)
        self.workshop.status = None
        self.workshop.save()
        response = self.client.get(reverse('qualification_problems', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertEqual(response.status_code, 403)

    def test_view_qual_problems(self):
        data = os.urandom(1024 * 1024)
        self.workshop.qualification_problems = SimpleUploadedFile('problems.pdf', data)
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        response = self.client.get(reverse('qualification_problems', args=[self.workshop.year.pk, self.workshop.name]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, data)

    def test_view_public_page_proposal(self):
        # Nobody can see the public page until the proposal is accepted
        self.workshop.status = None
        self.workshop.save()

        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.another_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertEqual(response.status_code, 403)

    def test_view_public_page_nonpublic(self):
        # Nobody can see the public page until it's marked as completed
        self.workshop.page_content = '<p>opis iks de</p>'
        self.workshop.page_content_is_public = False
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()

        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertContains(response, 'Prowadzący warsztatów nie wstawił jeszcze opisu.')
        self.assertNotContains(response, 'opis iks de')

        self.client.force_login(self.another_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertContains(response, 'Prowadzący warsztatów nie wstawił jeszcze opisu.')
        self.assertNotContains(response, 'opis iks de')

        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertContains(response, 'Nie opublikowałeś jeszcze opisu!')
        self.assertNotContains(response, 'opis iks de')

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertContains(response, 'Prowadzący warsztatów nie wstawił jeszcze opisu.')
        self.assertNotContains(response, 'opis iks de')

    def test_view_public_page(self):
        self.workshop.page_content = '<p>opis iks de</p>'
        self.workshop.page_content_is_public = True
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()

        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertNotContains(response, 'Nie opublikowałeś jeszcze opisu!')
        self.assertNotContains(response, 'Prowadzący warsztatów nie wstawił jeszcze opisu.')
        self.assertContains(response, 'opis iks de')

        self.client.force_login(self.another_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertNotContains(response, 'Nie opublikowałeś jeszcze opisu!')
        self.assertNotContains(response, 'Prowadzący warsztatów nie wstawił jeszcze opisu.')
        self.assertContains(response, 'opis iks de')

        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertNotContains(response, 'Nie opublikowałeś jeszcze opisu!')
        self.assertNotContains(response, 'Prowadzący warsztatów nie wstawił jeszcze opisu.')
        self.assertContains(response, 'opis iks de')

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('workshop_page', args=[2020, 'bardzofajne']))
        self.assertNotContains(response, 'Nie opublikowałeś jeszcze opisu!')
        self.assertNotContains(response, 'Prowadzący warsztatów nie wstawił jeszcze opisu.')
        self.assertContains(response, 'opis iks de')

    def test_unauthed_cannot_set_workshop_status(self):
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'accept'})
            save.assert_not_called()
            self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]))
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'reject'})
            save.assert_not_called()
            self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]))
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'delete'})
            save.assert_not_called()
            self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]))
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'cancel'})
            save.assert_not_called()
            self.assertRedirects(response, reverse('login') + '?next=' + reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]))

    def test_user_cannot_set_workshop_status(self):
        self.client.force_login(self.normal_user)
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'accept'})
            save.assert_not_called()
            self.assertEqual(response.status_code, 403)
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'reject'})
            save.assert_not_called()
            self.assertEqual(response.status_code, 403)
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'delete'})
            save.assert_not_called()
            self.assertEqual(response.status_code, 403)
        with mock.patch('wwwapp.models.Workshop.save', autospec=True, side_effect=Workshop.save) as save:
            response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'cancel'})
            save.assert_not_called()
            self.assertEqual(response.status_code, 403)

    def test_admin_can_accept_workshop(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'accept'})
        self.assertRedirects(response, reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]))

        self.workshop.refresh_from_db()
        self.assertEqual(self.workshop.status, Workshop.STATUS_ACCEPTED)

    def test_admin_can_reject_workshop(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'reject'})
        self.assertRedirects(response, reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]))

        self.workshop.refresh_from_db()
        self.assertEqual(self.workshop.status, Workshop.STATUS_REJECTED)

    def test_admin_can_cancel_workshop(self):
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'cancel'})
        self.assertRedirects(response, reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]))

        self.workshop.refresh_from_db()
        self.assertEqual(self.workshop.status, Workshop.STATUS_CANCELLED)

    def test_admin_can_delete_workshop_status(self):
        self.workshop.status = Workshop.STATUS_ACCEPTED
        self.workshop.save()
        self.client.force_login(self.admin_user)
        response = self.client.post(reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]), {'qualify': 'delete'})
        self.assertRedirects(response, reverse('workshop_edit', args=[self.workshop.year.pk, self.workshop.name]))

        self.workshop.refresh_from_db()
        self.assertIsNone(self.workshop.status)

    @freeze_time('2020-05-01 12:00:00')
    def test_template_not_added_to_proposals(self):
        template_for_workshop_page = Article.objects.get(name="template_for_workshop_page")
        template_for_workshop_page.content = 'This is the template.'
        template_for_workshop_page.save()

        self.client.force_login(self.admin_user)
        # Add proposal
        response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
            'title': 'Fajne warsztaty',
            'name': 'fajne',
            'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
            'category': [
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk,
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 2').pk
            ],
            'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
        })
        self.assertRedirects(response, reverse('workshop_edit', args=[2020, 'fajne']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        # Template should not be added yet
        workshop = Workshop.objects.filter(name='fajne').get()
        self.assertEqual(workshop.page_content, '')

        # Edit proposal
        response = self.client.post(reverse('workshop_edit', args=[2020, 'fajne']), {
            'title': 'Niefajne warsztaty',
            'name': 'fajne',
            'type': WorkshopType.objects.get(year=self.year_2020, name='This type 2').pk,
            'category': [
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 3').pk,
            ],
            'proposition_description': '<p>PRZEGRAŁEM!!</p>'
        })
        self.assertRedirects(response, reverse('workshop_edit', args=[2020, 'fajne']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        # Template should not be added yet
        workshop.refresh_from_db()
        self.assertEqual(workshop.page_content, '')

    @freeze_time('2020-05-01 12:00:00')
    def test_template_added_to_accepted(self):
        template_for_workshop_page = Article.objects.get(name="template_for_workshop_page")
        template_for_workshop_page.content = 'This is the template.'
        template_for_workshop_page.save()

        self.client.force_login(self.admin_user)
        # Add proposal
        response = self.client.post(reverse('workshops_add', args=[self.year_2020.pk]), {
            'title': 'Fajne warsztaty',
            'name': 'fajne',
            'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
            'category': [
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk,
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 2').pk
            ],
            'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>'
        })
        self.assertRedirects(response, reverse('workshop_edit', args=[2020, 'fajne']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        # Template should not be added yet
        workshop = Workshop.objects.filter(name='fajne').get()
        self.assertEqual(workshop.page_content, '')

        # Accept proposal
        response = self.client.post(reverse('workshop_edit', args=[2020, 'fajne']), {'qualify': 'accept'})
        self.assertRedirects(response, reverse('workshop_edit', args=[2020, 'fajne']))

        # Template should not be added yet
        workshop.refresh_from_db()
        self.assertEqual(workshop.page_content, '')

        # Open the editor
        response = self.client.get(reverse('workshop_edit', args=[2020, 'fajne']))

        # The template should be auto filled in
        self.assertContains(response, template_for_workshop_page.content)

        # But not stored to DB until you click save
        workshop.refresh_from_db()
        self.assertEqual(workshop.page_content, '')

        # If you save edits without touching the template...
        response = self.client.post(reverse('workshop_edit', args=[2020, 'fajne']), {
            'title': 'Fajne warsztaty',
            'name': 'fajne',
            'type': WorkshopType.objects.get(year=self.year_2020, name='This type 1').pk,
            'category': [
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 1').pk,
                WorkshopCategory.objects.get(year=self.year_2020, name='This category 2').pk
            ],
            'proposition_description': '<p>Na tych warsztatach będziemy testować fajną stronę</p>',
            'is_qualifying': '',
            'qualification_threshold': 1337,
            'max_points': 2137,
            'page_content': template_for_workshop_page.content,
            'page_content_is_public': '',
        })
        self.assertRedirects(response, reverse('workshop_edit', args=[2020, 'fajne']))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        # ... the template should not get saved to db
        workshop.refresh_from_db()
        self.assertEqual(workshop.page_content, '')
