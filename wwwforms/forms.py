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

            field_kwargs = {}
            if question.data_type in (FormQuestion.TYPE_CHOICE, FormQuestion.TYPE_MULTIPLE_CHOICE, FormQuestion.TYPE_SELECT):
                field_kwargs['queryset'] = question.options.all()
                field_kwargs['blank'] = not question.is_required

            if question.data_type == FormQuestion.TYPE_PHONE:
                # Remove after https://github.com/stefanfoulis/django-phonenumber-field/commit/1da0b6a19298934d277e456206c8f222d9ac83ae is released
                field_kwargs['region'] = getattr(settings, "PHONENUMBER_DEFAULT_REGION", None)

            if question.is_locked:
                question.is_required=False

            self.fields[field_name] = field_type(label=question.title, required=question.is_required,
                                                 initial=value, disabled=question.is_locked,
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
            StrictButton('Zapisz', type='submit', css_class='btn-outline-primary btn-lg m-3'),
            css_class='text-right row',
        ))

    def clean(self):
        cleaned_data = super().clean()
        if self.form.arrival_date and self.form.departure_date:
            arrival_date_field = self.field_name_for_question(self.form.arrival_date)
            departure_date_field = self.field_name_for_question(self.form.departure_date)
            current_year = Camp.objects.latest()
            if current_year.start_date and current_year.end_date:
                errors = {}
                arrival_date_set = arrival_date_field in self.cleaned_data and self.cleaned_data[arrival_date_field]
                departure_date_set = departure_date_field in self.cleaned_data and self.cleaned_data[departure_date_field]
                if arrival_date_set:
                    if self.cleaned_data[arrival_date_field] < current_year.start_date:
                        errors[arrival_date_field] = 'Warsztaty rozpoczynają się ' + str(current_year.start_date)
                    if self.cleaned_data[arrival_date_field] > current_year.end_date:
                        errors[arrival_date_field] = 'Warsztaty kończą się ' + str(current_year.end_date)

                if departure_date_set:
                    if self.cleaned_data[departure_date_field] < current_year.start_date:
                        errors[departure_date_field] = 'Warsztaty rozpoczynają się ' + str(current_year.start_date)
                    if self.cleaned_data[departure_date_field] > current_year.end_date:
                        errors[departure_date_field] = 'Warsztaty kończą się ' + str(current_year.end_date)
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
