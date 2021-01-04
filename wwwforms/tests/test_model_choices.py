from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from wwwforms.models import Form, FormQuestion


class ModelChoicesTest(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', email='admin@example.com', password='admin123')

    def test_create_question_with_choices(self):
        form = Form.objects.create(name='test_form', title='Test form')
        single_question = form.questions.create(title='Give me one', data_type=FormQuestion.TYPE_CHOICE, is_required=False)
        single_question_1 = single_question.options.create(title='Option 1')
        single_question_2 = single_question.options.create(title='Option 2')
        single_question_3 = single_question.options.create(title='Option 3')
        multiple_question = form.questions.create(title='Give me one', data_type=FormQuestion.TYPE_MULTIPLE_CHOICE, is_required=False)
        multiple_question_1 = multiple_question.options.create(title='Option 1')
        multiple_question_2 = multiple_question.options.create(title='Option 2')
        multiple_question_3 = multiple_question.options.create(title='Option 3')

    def test_no_choices_for_non_choice_questions(self):
        form = Form.objects.create(name='test_form', title='Test form')
        single_question = form.questions.create(title='Give me one', data_type=FormQuestion.TYPE_STRING)
        self.assertRaises(ValidationError, lambda: single_question.options.create(title='Option'))

    def test_create_answer_with_choices(self):
        form = Form.objects.create(name='test_form', title='Test form')
        single_question = form.questions.create(title='Give me one', data_type=FormQuestion.TYPE_CHOICE, is_required=False)
        single_question_1 = single_question.options.create(title='Option 1')
        single_question_2 = single_question.options.create(title='Option 2')
        single_question_3 = single_question.options.create(title='Option 3')
        multiple_question = form.questions.create(title='Give me one', data_type=FormQuestion.TYPE_MULTIPLE_CHOICE, is_required=False)
        multiple_question_1 = multiple_question.options.create(title='Option 1')
        multiple_question_2 = multiple_question.options.create(title='Option 2')
        multiple_question_3 = multiple_question.options.create(title='Option 3')

        single_answer = single_question.answers.create(user=self.admin_user)
        single_answer.value = single_question_1

        multiple_answer = multiple_question.answers.create(user=self.admin_user)
        multiple_answer.value = [multiple_question_1, multiple_question_3]