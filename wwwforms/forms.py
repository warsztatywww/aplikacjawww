from crispy_forms.bootstrap import FormActions, StrictButton
from crispy_forms.helper import FormHelper
from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from wwwapp.models import Camp
from wwwforms.models import FormQuestion, FormQuestionAnswer, pesel_validate, Form


class TextareaField(forms.CharField):
    widget = forms.widgets.Textarea


class PESELField(forms.CharField):
    default_validators = [pesel_validate]


class FormForm(forms.Form):
    FIELD_TYPES = {
        FormQuestion.TYPE_NUMBER: forms.IntegerField,
        FormQuestion.TYPE_STRING: forms.CharField,
        FormQuestion.TYPE_TEXTBOX: TextareaField,
        FormQuestion.TYPE_PESEL: PESELField,
        FormQuestion.TYPE_DATE: forms.DateField,
    }

    def field_name_for_question(self, question):
        return 'question_{}'.format(question.pk)

    def __init__(self, form: Form, user: User, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # TODO: This is ugly - makes wwwforms have a circular reference to wwwapp, and should it even be hardcoded to 'latest'?
        current_year = Camp.objects.latest()

        self.form = form
        self.user = user
        self.questions = form.questions.all()
        answers_qs = FormQuestionAnswer.objects.prefetch_related('question').filter(question__in=self.questions, user=user).all()
        self.answers = {}
        for question in self.questions:
            field_name = self.field_name_for_question(question)
            field_type = self.FIELD_TYPES[question.data_type]

            self.answers[field_name] = next(filter(lambda x: x.question == question, answers_qs), None)
            value = self.answers[field_name].value if self.answers[field_name] is not None else None

            self.fields[field_name] = field_type(label=question.title, required=question.is_required,
                                                 initial=value, disabled=question.is_locked)

            if question.data_type == FormQuestion.TYPE_DATE:
                if question == form.arrival_date:
                    self.fields[field_name].widget = forms.widgets.DateInput(
                        attrs={'data-default-date': current_year.start_date or '',
                               'data-start-date': current_year.start_date or '',
                               'data-end-date': current_year.end_date or ''})
                if question == form.departure_date:
                    self.fields[field_name].widget = forms.widgets.DateInput(
                        attrs={'data-default-date': current_year.end_date or '',
                               'data-start-date': current_year.start_date or '',
                               'data-end-date': current_year.end_date or ''})

        self.helper = FormHelper(self)
        self.helper.include_media = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-3'
        self.helper.field_class = 'col-lg-9'

        self.helper.layout.fields.append(FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-default')
        ))

    def clean(self):
        cleaned_data = super().clean()

        if self.form.arrival_date and self.form.departure_date:
            arrival_date_field = self.field_name_for_question(self.form.arrival_date)
            departure_date_field = self.field_name_for_question(self.form.departure_date)
            current_year = Camp.objects.latest()
            if current_year.start_date and current_year.end_date:
                errors = {}

                if self.cleaned_data[arrival_date_field]:
                    if self.cleaned_data[arrival_date_field] < current_year.start_date:
                        errors[arrival_date_field] = 'Warsztaty rozpoczynają się ' + str(current_year.start_date)
                    if self.cleaned_data[arrival_date_field] > current_year.end_date:
                        errors[arrival_date_field] = 'Warsztaty kończą się ' + str(current_year.end_date)

                if self.cleaned_data[departure_date_field]:
                    if self.cleaned_data[departure_date_field] < current_year.start_date:
                        errors[departure_date_field] = 'Warsztaty rozpoczynają się ' + str(current_year.start_date)
                    if self.cleaned_data[departure_date_field] > current_year.end_date:
                        errors[departure_date_field] = 'Warsztaty kończą się ' + str(current_year.end_date)

                if not errors and self.cleaned_data[arrival_date_field] and self.cleaned_data[departure_date_field]:
                    if self.cleaned_data[arrival_date_field] > self.cleaned_data[departure_date_field]:
                        errors[arrival_date_field] = 'Nie możesz wyjechać wcześniej niż przyjechać! :D'
                        errors[departure_date_field] = 'Nie możesz wyjechać wcześniej niż przyjechać! :D'

                if errors:
                    raise ValidationError(errors)

        return cleaned_data

    def save(self):
        for question in self.questions:
            field_name = self.field_name_for_question(question)
            if not self.fields[field_name].disabled:
                if self.answers[field_name]:
                    self.answers[field_name].value = self.cleaned_data[field_name]
                    self.answers[field_name].save()
                else:
                    self.answers[field_name] = FormQuestionAnswer.objects.create(question=question, user=self.user, value=self.cleaned_data[field_name])