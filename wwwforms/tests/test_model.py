from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from wwwforms.models import Form, FormQuestion, FormQuestionAnswer


class ModelTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')

    def test_form_create(self):
        form = Form.objects.create(name='test_form', title='Test form')
        form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        form.questions.create(title='Favorite color', data_type=FormQuestion.TYPE_STRING, is_required=True)
        form.questions.create(title='Essay', data_type=FormQuestion.TYPE_TEXTBOX, is_required=False)

    def test_answer_create(self):
        form = Form.objects.create(name='test_form', title='Test form')
        question1 = form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        question2 = form.questions.create(title='Favorite color', data_type=FormQuestion.TYPE_STRING, is_required=True)
        question3 = form.questions.create(title='Essay', data_type=FormQuestion.TYPE_TEXTBOX, is_required=False)

        question1.answers.create(user=self.admin_user, value_number=42)
        question2.answers.create(user=self.admin_user, value_string='gold')
        question3.answers.create(user=self.admin_user, value_string='See, this is a very long answer. I am too lazy to write all of it though.')

    def test_answer_create_invalid(self):
        form = Form.objects.create(name='test_form', title='Test form')
        question1 = form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        question2 = form.questions.create(title='Favorite color', data_type=FormQuestion.TYPE_STRING, is_required=True)
        question3 = form.questions.create(title='Essay', data_type=FormQuestion.TYPE_TEXTBOX, is_required=False)

        self.assertRaises(ValidationError, lambda: question1.answers.create(user=self.admin_user, value_string='AAAAAAAA'))
        self.assertRaises(ValidationError, lambda: question2.answers.create(user=self.admin_user, value_number=1337))
        self.assertRaises(ValidationError, lambda: question3.answers.create(user=self.admin_user, value_number=1337))
        self.assertRaises(ValidationError, lambda: question1.answers.create(user=self.admin_user, value_string='AAAAAAAA', value_number=42))
        self.assertRaises(ValidationError, lambda: question2.answers.create(user=self.admin_user, value_number=1337, value_string='BBBBBBBB'))
        self.assertRaises(ValidationError, lambda: question3.answers.create(user=self.admin_user, value_number=1337, value_string='BBBBBBBB'))

    def test_answer_required(self):
        form = Form.objects.create(name='test_form', title='Test form')
        question1 = form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        question2 = form.questions.create(title='Least favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=False)

        self.assertRaises(ValidationError, lambda: question1.answers.create(user=self.admin_user))
        question2.answers.create(user=self.admin_user, value_number=1337)

    def test_form_edit_question_with_answers(self):
        form = Form.objects.create(name='test_form', title='Test form')
        question = form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=False)
        question.answers.create(user=self.admin_user, value_number=42)

        question.data_type = FormQuestion.TYPE_STRING
        self.assertRaises(ValidationError, lambda: question.save())
        question.refresh_from_db()

    def test_delete_form_deletes_everything(self):
        form = Form.objects.create(name='test_form', title='Test form')
        question = form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        question.answers.create(user=self.admin_user, value_number=42)

        form.delete()

        self.assertEqual(Form.objects.count(), 0)
        self.assertEqual(FormQuestion.objects.count(), 0)
        self.assertEqual(FormQuestionAnswer.objects.count(), 0)

    def test_delete_question_deletes_answers(self):
        form = Form.objects.create(name='test_form', title='Test form')
        question = form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        question.answers.create(user=self.admin_user, value_number=42)

        question.delete()

        self.assertEqual(Form.objects.count(), 1)
        self.assertEqual(FormQuestion.objects.count(), 0)
        self.assertEqual(FormQuestionAnswer.objects.count(), 0)

    def test_delete_user_deletes_answers(self):
        form = Form.objects.create(name='test_form', title='Test form')
        question = form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        question.answers.create(user=self.admin_user, value_number=42)

        self.admin_user.delete()

        self.assertEqual(Form.objects.count(), 1)
        self.assertEqual(FormQuestion.objects.count(), 1)
        self.assertEqual(FormQuestionAnswer.objects.count(), 0)

    def test_delete_answer(self):
        form = Form.objects.create(name='test_form', title='Test form')
        question = form.questions.create(title='Favorite number', data_type=FormQuestion.TYPE_NUMBER, is_required=True)
        answer = question.answers.create(user=self.admin_user, value_number=42)

        answer.delete()

        self.assertEqual(Form.objects.count(), 1)
        self.assertEqual(FormQuestion.objects.count(), 1)
        self.assertEqual(FormQuestionAnswer.objects.count(), 0)
