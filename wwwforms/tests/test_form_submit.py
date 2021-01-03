import datetime

from django.contrib.auth.models import User
from django import forms
from django.contrib.messages.api import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import make_aware
from freezegun import freeze_time

from wwwforms.forms import TextareaField
from wwwforms.models import Form, FormQuestion


class FormSubmitTest(TestCase):
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

        # Admin's responses - should never show up when the user opens the form
        self.question1.answers.create(user=self.admin_user, value_number=1337)
        self.question2.answers.create(user=self.admin_user, value_string='red')
        self.question3.answers.create(user=self.admin_user, value_string='The text.')
        self.question4.answers.create(user=self.admin_user, value_date=datetime.date(2001, 1, 1))

    def test_view_form(self):
        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('form', args=[self.form.name]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['title'], self.form.title)
        self.assertIsInstance(response.context['form'].fields['question_{}'.format(self.question1.pk)], forms.IntegerField)
        self.assertIsInstance(response.context['form'].fields['question_{}'.format(self.question2.pk)], forms.CharField)
        self.assertIsInstance(response.context['form'].fields['question_{}'.format(self.question3.pk)], TextareaField)
        self.assertIsInstance(response.context['form'].fields['question_{}'.format(self.question4.pk)], forms.DateField)
        self.assertEqual(response.context['form'].fields['question_{}'.format(self.question1.pk)].required, self.question1.is_required)
        self.assertEqual(response.context['form'].fields['question_{}'.format(self.question2.pk)].required, self.question2.is_required)
        self.assertEqual(response.context['form'].fields['question_{}'.format(self.question3.pk)].required, self.question3.is_required)
        self.assertEqual(response.context['form'].fields['question_{}'.format(self.question4.pk)].required, self.question4.is_required)
        self.assertIsNone(response.context['form'].fields['question_{}'.format(self.question1.pk)].initial)
        self.assertIsNone(response.context['form'].fields['question_{}'.format(self.question2.pk)].initial)
        self.assertIsNone(response.context['form'].fields['question_{}'.format(self.question3.pk)].initial)
        self.assertIsNone(response.context['form'].fields['question_{}'.format(self.question4.pk)].initial)

    def test_view_form_existing(self):
        self.question1.answers.create(user=self.normal_user, value_number=31337)
        self.question2.answers.create(user=self.normal_user, value_string='blue')
        self.question4.answers.create(user=self.normal_user, value_date=datetime.date(2019, 1, 1))

        self.client.force_login(self.normal_user)
        response = self.client.get(reverse('form', args=[self.form.name]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['title'], self.form.title)
        self.assertEqual(response.context['form'].fields['question_{}'.format(self.question1.pk)].initial, 31337)
        self.assertEqual(response.context['form'].fields['question_{}'.format(self.question2.pk)].initial, 'blue')
        self.assertIsNone(response.context['form'].fields['question_{}'.format(self.question3.pk)].initial)
        self.assertEqual(response.context['form'].fields['question_{}'.format(self.question4.pk)].initial, datetime.date(2019, 1, 1))

    def test_view_form_unauthenticated(self):
        response = self.client.get(reverse('form', args=[self.form.name]))
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('form', args=[self.form.name]))

    @freeze_time('2021-01-03 12:34:56')
    def test_submit_form_initial(self):
        self.client.force_login(self.normal_user)
        response = self.client.post(reverse('form', args=[self.form.name]), {
            'question_{}'.format(self.question1.pk): '42',
            'question_{}'.format(self.question2.pk): 'gold',
            'question_{}'.format(self.question3.pk): 'This is a very long paragraph of text.',
            'question_{}'.format(self.question4.pk): '2021-01-01',
        })
        self.assertRedirects(response, reverse('form', args=[self.form.name]))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        answer1 = self.question1.answers.get(user=self.normal_user)
        answer2 = self.question2.answers.get(user=self.normal_user)
        answer3 = self.question3.answers.get(user=self.normal_user)
        answer4 = self.question4.answers.get(user=self.normal_user)
        self.assertEqual(answer1.value_number, 42)
        self.assertEqual(answer2.value_string, 'gold')
        self.assertEqual(answer3.value_string, 'This is a very long paragraph of text.')
        self.assertEqual(answer4.value_date, datetime.date(2021, 1, 1))
        self.assertEqual(answer1.last_changed, make_aware(datetime.datetime(2021, 1, 3, 12, 34, 56)))
        self.assertEqual(answer2.last_changed, make_aware(datetime.datetime(2021, 1, 3, 12, 34, 56)))
        self.assertEqual(answer3.last_changed, make_aware(datetime.datetime(2021, 1, 3, 12, 34, 56)))
        self.assertEqual(answer4.last_changed, make_aware(datetime.datetime(2021, 1, 3, 12, 34, 56)))

    @freeze_time('2021-01-03 12:34:56')
    def test_submit_form_update(self):
        with freeze_time('2021-01-01 12:00:00'):
            old_answer1 = self.question1.answers.create(user=self.normal_user, value_number=31337)
            old_answer2 = self.question2.answers.create(user=self.normal_user, value_string='blue')

        self.client.force_login(self.normal_user)
        response = self.client.post(reverse('form', args=[self.form.name]), {
            'question_{}'.format(self.question1.pk): '31337',
            'question_{}'.format(self.question2.pk): 'gold',
            'question_{}'.format(self.question3.pk): 'This is a very long paragraph of text.',
            'question_{}'.format(self.question4.pk): '2021-01-01',
        })
        self.assertRedirects(response, reverse('form', args=[self.form.name]))
        messages = get_messages(response.wsgi_request)
        self.assertEqual(len(messages), 1)
        self.assertEqual(list(messages)[0].message, 'Zapisano.')

        answer1 = self.question1.answers.get(user=self.normal_user)
        answer2 = self.question2.answers.get(user=self.normal_user)
        answer3 = self.question3.answers.get(user=self.normal_user)
        answer4 = self.question4.answers.get(user=self.normal_user)
        self.assertEqual(answer1.pk, old_answer1.pk)
        self.assertEqual(answer2.pk, old_answer2.pk)
        self.assertEqual(answer1.value_number, 31337)
        self.assertEqual(answer2.value_string, 'gold')
        self.assertEqual(answer3.value_string, 'This is a very long paragraph of text.')
        self.assertEqual(answer4.value_date, datetime.date(2021, 1, 1))
        self.assertEqual(answer1.last_changed, make_aware(datetime.datetime(2021, 1, 1, 12, 00, 00)))
        self.assertEqual(answer2.last_changed, make_aware(datetime.datetime(2021, 1, 3, 12, 34, 56)))
        self.assertEqual(answer3.last_changed, make_aware(datetime.datetime(2021, 1, 3, 12, 34, 56)))
        self.assertEqual(answer4.last_changed, make_aware(datetime.datetime(2021, 1, 3, 12, 34, 56)))

    def test_submit_form_unauthenticated(self):
        response = self.client.post(reverse('form', args=[self.form.name]), {
            'question_{}'.format(self.question1.pk): '42',
            'question_{}'.format(self.question2.pk): 'gold',
            'question_{}'.format(self.question3.pk): 'This is a very long paragraph of text.',
            'question_{}'.format(self.question4.pk): '2021-01-01',
        })
        self.assertRedirects(response, reverse('login') + '?next=' + reverse('form', args=[self.form.name]))
