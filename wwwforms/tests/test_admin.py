import datetime

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from wwwforms.models import Form, FormQuestion, FormQuestionAnswer


class FormAdminSiteTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123', first_name='Admin', last_name='User')
        self.normal_user = User.objects.create_user(
            username='user', email='user@example.com', password='admin123', first_name='Normal', last_name='User')

        self.form = Form.objects.create(name='test_form', title='Test form')
        self.question1 = self.form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        self.question2 = self.form.questions.create(title='Favorite color', data_type=FormQuestion.TYPE_STRING, is_required=True)
        self.question3 = self.form.questions.create(title='Essay', data_type=FormQuestion.TYPE_TEXTBOX, is_required=False)
        self.question4 = self.form.questions.create(title='Gimme a date', data_type=FormQuestion.TYPE_DATE, is_required=False)

        self.answer_admin_1 = self.question1.answers.create(user=self.admin_user, value_number=1337)
        self.answer_admin_2 = self.question2.answers.create(user=self.admin_user, value_string='red')
        self.answer_admin_4 = self.question4.answers.create(user=self.admin_user, value_date=datetime.date(2001, 1, 1))

        self.answer_normal_2 = self.question2.answers.create(user=self.normal_user, value_string='blue')

    def test_admin(self):
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin:wwwforms_form_changelist'))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('admin:wwwforms_form_add'))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('admin:wwwforms_form_change', args=[self.form.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('admin:wwwforms_form_delete', args=[self.form.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('admin:wwwforms_formquestion_changelist'))
        self.assertEqual(response.status_code, 200)  # TODO: this should really be disabled...
        response = self.client.get(reverse('admin:wwwforms_formquestion_add'))
        self.assertEqual(response.status_code, 403)  # cannot add here (only through inline)
        response = self.client.get(reverse('admin:wwwforms_formquestion_change', args=[self.question2.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse('admin:wwwforms_formquestion_delete', args=[self.question2.pk]))
        self.assertEqual(response.status_code, 200)

    def test_admin_reset_question(self):
        self.client.force_login(self.admin_user)
        self.assertEqual(self.question2.answers.count(), 2)

        response = self.client.get(reverse('admin:wwwforms_formquestion_reset', args=[self.question2.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.question2.answers.count(), 2)
        self.assertSetEqual(set(response.context['deleted_objects']), {
            'Odpowiedź: {}'.format(self.answer_admin_2),
            'Odpowiedź: {}'.format(self.answer_normal_2),
        })

        response = self.client.post(reverse('admin:wwwforms_formquestion_reset', args=[self.question2.pk]), {'post': 'yes'})
        self.assertRedirects(response, reverse('admin:wwwforms_formquestion_change', args=[self.question2.pk]))
        self.assertEqual(self.question2.answers.count(), 0)

    def test_admin_reset_form(self):
        self.client.force_login(self.admin_user)
        self.assertEqual(FormQuestionAnswer.objects.filter(question__form=self.form).count(), 4)

        response = self.client.get(reverse('admin:wwwforms_form_reset', args=[self.form.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(FormQuestionAnswer.objects.filter(question__form=self.form).count(), 4)
        self.assertSetEqual(set(response.context['deleted_objects']), {
            'Odpowiedź: {}'.format(self.answer_admin_1),
            'Odpowiedź: {}'.format(self.answer_admin_2),
            'Odpowiedź: {}'.format(self.answer_admin_4),
            'Odpowiedź: {}'.format(self.answer_normal_2),
        })

        response = self.client.post(reverse('admin:wwwforms_form_reset', args=[self.form.pk]), {'post': 'yes'})
        self.assertRedirects(response, reverse('admin:wwwforms_form_change', args=[self.form.pk]))
        self.assertEqual(FormQuestionAnswer.objects.filter(question__form=self.form).count(), 0)
