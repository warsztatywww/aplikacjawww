import datetime

from crispy_forms.bootstrap import FormActions, StrictButton
from crispy_forms.helper import FormHelper
from django import forms
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils.text import format_lazy
import phonenumbers
import phonenumber_field.phonenumber
from phonenumber_field.formfields import PhoneNumberField

from wwwapp.models import Camp
from wwwforms.models import FormQuestion, FormQuestionAnswer, pesel_validate, Form, FormQuestionOption


class TextareaField(forms.CharField):
    widget = forms.widgets.Textarea


class PESELField(forms.CharField):
    default_validators = [pesel_validate]


class SelectChoiceField(forms.ModelChoiceField):
    widget = forms.widgets.Select


class RadioChoiceField(forms.ModelChoiceField):
    widget = forms.widgets.RadioSelect


class CheckboxMultipleChoiceField(forms.ModelMultipleChoiceField):
    widget = forms.widgets.CheckboxSelectMultiple


class FormForm(forms.Form):
    FIELD_TYPES = {
        FormQuestion.TYPE_NUMBER: forms.IntegerField,
        FormQuestion.TYPE_STRING: forms.CharField,
        FormQuestion.TYPE_TEXTBOX: TextareaField,
        FormQuestion.TYPE_PESEL: PESELField,
        FormQuestion.TYPE_DATE: forms.DateField,
        FormQuestion.TYPE_CHOICE: RadioChoiceField,
        FormQuestion.TYPE_MULTIPLE_CHOICE: CheckboxMultipleChoiceField,
        FormQuestion.TYPE_SELECT: SelectChoiceField,
        FormQuestion.TYPE_PHONE: PhoneNumberField,
    }

    def field_name_for_question(self, question):
        return 'question_{}'.format(question.pk)

    def __init__(self, form: Form, user: User, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            year = form.years.latest()
        except Camp.DoesNotExist:
            year = None

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

            field_kwargs = {}
            if question.data_type in (FormQuestion.TYPE_CHOICE, FormQuestion.TYPE_MULTIPLE_CHOICE, FormQuestion.TYPE_SELECT):
                field_kwargs['queryset'] = question.options.all()
                field_kwargs['blank'] = not question.is_required

            if question.data_type == FormQuestion.TYPE_PHONE:
                # Remove after https://github.com/stefanfoulis/django-phonenumber-field/commit/1da0b6a19298934d277e456206c8f222d9ac83ae is released
                field_kwargs['region'] = getattr(settings, "PHONENUMBER_DEFAULT_REGION", None)

            self.fields[field_name] = field_type(label=question.title, initial=value,
                                                 required=question.is_required and not question.is_locked,
                                                 disabled=question.is_locked,
                                                 **field_kwargs)

            if question.data_type == FormQuestion.TYPE_PHONE:
                # django-phonenumber-field defaults to a landline phone in error messages without a way to change it
                # Also, localize the error message, and remove the info that you can use international call prefix
                # because who cares
                region = getattr(settings, "PHONENUMBER_DEFAULT_REGION", None)
                if region:
                    number = phonenumbers.example_number_for_type(region, phonenumbers.PhoneNumberType.MOBILE)
                    example_number = phonenumber_field.phonenumber.to_python(number).as_national
                    self.fields[field_name].error_messages["invalid"] = format_lazy(
                        "Wpisz poprawny numer telefonu (np. {example_number})",
                        example_number=example_number
                    )

            if year:
                if question == year.form_question_arrival_date and question.data_type == FormQuestion.TYPE_DATE:
                    self.fields[field_name].widget = forms.widgets.DateInput(
                        attrs={'data-default-date': year.start_date or '',
                               'data-start-date': year.start_date or '',
                               'data-end-date': year.end_date or ''})
                if question == year.form_question_departure_date and question.data_type == FormQuestion.TYPE_DATE:
                    self.fields[field_name].widget = forms.widgets.DateInput(
                        attrs={'data-default-date': year.end_date or '',
                               'data-start-date': year.start_date or '',
                               'data-end-date': year.end_date or ''})
                if question == year.form_question_birth_date and question.data_type == FormQuestion.TYPE_DATE:
                    self.fields[field_name].widget = forms.widgets.DateInput(
                        attrs={'data-start-date': '1900-01-01',
                               'data-end-date': str(datetime.date.today()) or ''})

        self.helper = FormHelper(self)
        self.helper.include_media = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-3'
        self.helper.field_class = 'col-lg-9'

        self.helper.layout.fields.append(FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-outline-primary btn-lg m-3'),
            css_class='text-right row',
        ))

    def clean(self):
        cleaned_data = super().clean()
        try:
            year = self.form.years.latest()
        except Camp.DoesNotExist:
            year = None
        if year and year.form_question_arrival_date and year.form_question_departure_date:
            arrival_date_field = self.field_name_for_question(year.form_question_arrival_date)
            departure_date_field = self.field_name_for_question(year.form_question_departure_date)
            errors = {}
            arrival_date_set = arrival_date_field in self.cleaned_data and self.cleaned_data[arrival_date_field]
            departure_date_set = departure_date_field in self.cleaned_data and self.cleaned_data[departure_date_field]
            if year.start_date and year.end_date:
                if arrival_date_set:
                    if self.cleaned_data[arrival_date_field] < year.start_date:
                        errors[arrival_date_field] = 'Warsztaty rozpoczynają się ' + str(year.start_date)
                    if self.cleaned_data[arrival_date_field] > year.end_date:
                        errors[arrival_date_field] = 'Warsztaty kończą się ' + str(year.end_date)

                if departure_date_set:
                    if self.cleaned_data[departure_date_field] < year.start_date:
                        errors[departure_date_field] = 'Warsztaty rozpoczynają się ' + str(year.start_date)
                    if self.cleaned_data[departure_date_field] > year.end_date:
                        errors[departure_date_field] = 'Warsztaty kończą się ' + str(year.end_date)
            if not errors and departure_date_set and arrival_date_set:
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
                    if self.answers[field_name].value != self.cleaned_data[field_name]:
                        # Call .save() only if the value actually changed to make sure last_updated updates correctly
                        self.answers[field_name].value = self.cleaned_data[field_name]
                        self.answers[field_name].save()
                else:
                    self.answers[field_name] = FormQuestionAnswer.objects.create(question=question, user=self.user)
                    self.answers[field_name].value = self.cleaned_data[field_name]
                    self.answers[field_name].save()
