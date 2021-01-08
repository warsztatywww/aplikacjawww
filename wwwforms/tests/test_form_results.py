import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from wwwforms.models import Form, FormQuestion


class FormResultsTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')
        self.normal_user = User.objects.create_user(
            username='user', email='user@example.com', password='admin123')

        self.form = Form.objects.create(name='test_form', title='Test form')
        self.question1 = self.form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        self.question2 = self.form.questions.create(title='Favorite color', data_type=FormQuestion.TYPE_STRING, is_required=True)
        self.question3 = self.form.questions.create(title='Essay', data_type=FormQuestion.TYPE_TEXTBOX, is_required=False)
        self.question4 = self.form.questions.create(title='Gimme a date', data_type=FormQuestion.TYPE_DATE, is_required=False)

        self.answer_admin_1 = self.question1.answers.create(user=self.admin_user, value_number=1337)
        self.answer_admin_2 = self.question2.answers.create(user=self.admin_user, value_string='red')
        self.answer_admin_4 = self.question4.answers.create(user=self.admin_user, value_date=datetime.date(2001, 1, 1))

        self.answer_normal_2 = self.question2.answers.create(user=self.normal_user, value_string='blue')

    def test_view_list(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('form_list'))
        self.assertEqual(response.status_code, 200)

    def test_view_list_no_permissions(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('form_list'))
        self.assertEqual(response.status_code, 403)

    def test_view_list_unauthenticated(self):
        response = self.client.get(reverse('form_list'))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('form_list'))

    def test_view_results(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('form_results', args=[self.form.name]))
        self.assertEqual(response.status_code, 200)
        self.assertSequenceEqual(response.context['questions'],
                                 [self.question1, self.question2, self.question3, self.question4])
        self.assertSetEqual(set(response.context['answers'].keys()), {self.admin_user, self.normal_user})
        self.assertSequenceEqual(response.context['answers'][self.admin_user],
                                 [self.answer_admin_1, self.answer_admin_2, None, self.answer_admin_4])
        self.assertSequenceEqual(response.context['answers'][self.normal_user],
                                 [None, self.answer_normal_2, None, None])

    def test_view_results_no_permissions(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('form_results', args=[self.form.name]))
        self.assertEqual(response.status_code, 403)

    def test_view_results_unauthenticated(self):
        response = self.client.get(reverse('form_results', args=[self.form.name]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('form_results', args=[self.form.name]))
