import datetime
from typing import Optional

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models


def pesel_validate(pesel: str) -> None:
    # We accept empty PESEL (don't raise exception) for legacy reasons.
    if not pesel:
        return

    # https://en.wikipedia.org/wiki/PESEL#Format
    if len(pesel) != 11:
        raise ValidationError('Długość numeru PESEL jest niepoprawna ({}).'.format(len(pesel)))
    if not pesel.isdigit():
        raise ValidationError('PESEL nie składa się z samych cyfr.')

    pesel_digits = [int(digit) for digit in pesel]
    checksum_mults = [1, 3, 7, 9] * 2 + [1, 3, 1]
    if sum(x*y for x, y in zip(pesel_digits, checksum_mults)) % 10 != 0:
        raise ValidationError('Suma kontrolna PESEL się nie zgadza.')

    if not pesel_extract_date(pesel):
        raise ValidationError('Data urodzenia zawarta w numerze PESEL nie istnieje.')


def pesel_extract_date(pesel: Optional[str]) -> datetime.date or None:
    """
    Takes PESEL (string that starts with at least 6 digits) and returns
    birth date associated with it.
    """
    if not pesel or len(pesel) < 6:
        return None

    try:
        year, month, day = [int(pesel[i:i+2]) for i in range(0, 6, 2)]
    except ValueError:
        return None
    years_from_month = [1900, 2000, 2100, 2200, 1800]
    count, month = divmod(month, 20)
    year += years_from_month[count]
    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


class VisibleManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_visible=True)


class Form(models.Model):
    name = models.SlugField(max_length=50, blank=False, unique=True, verbose_name='Nazwa', help_text='(w URLach)')
    title = models.CharField(max_length=50, blank=False, verbose_name='Tytuł')
    description = models.TextField(max_length=100000, blank=True, verbose_name='Opis', help_text='Krótki opis wyświetlany na górze formulaza')
    is_visible = models.BooleanField(default=True, verbose_name='Widoczny?')

    objects = models.Manager()
    visible_objects = VisibleManager()

    class Meta:
        verbose_name = 'formularz'
        verbose_name_plural = 'formularze'
        permissions = [('see_form_results', 'Can see form results')]

    @property
    def has_any_answers(self):
        return FormQuestionAnswer.objects.filter(question__form=self).count()

    def __str__(self):
        return self.title + (' (ukryty)' if not self.is_visible else '')


class FormQuestion(models.Model):
    TYPE_NUMBER = 'n'
    TYPE_STRING = 's'
    TYPE_TEXTBOX = 't'
    TYPE_DATE = 'd'
    TYPE_CHOICE = 'c'
    TYPE_MULTIPLE_CHOICE = 'm'
    TYPE_SELECT = 'C'
    TYPE_PESEL = 'P'
    TYPE_PHONE = 'p'

    TYPE_CHOICES = [
        (TYPE_NUMBER, 'Liczba'),
        (TYPE_STRING, 'Tekst'),
        (TYPE_TEXTBOX, 'Tekst (wiele linii)'),
        (TYPE_DATE, 'Data'),
        (TYPE_SELECT, 'Lista rozwijana'),
        (TYPE_CHOICE, 'Wybór jednokrotny'),
        (TYPE_MULTIPLE_CHOICE, 'Wybór wielokrotny'),
        (TYPE_PESEL, 'PESEL'),
        (TYPE_PHONE, 'Numer telefonu'),
    ]

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name='questions', verbose_name='Formularz')
    title = models.CharField(max_length=150, blank=False, verbose_name='Tekst pytania')
    data_type = models.CharField(max_length=1, blank=False, choices=TYPE_CHOICES, verbose_name='Typ odpowiedzi')
    is_required = models.BooleanField(default=True, verbose_name='Wymagane?')
    is_locked = models.BooleanField(default=False, verbose_name='Edycja zablokowana?', help_text='Zablokuj możliwość edycji odpowiedzi na to pytanie')
    order = models.PositiveIntegerField(default=0, blank=False, null=False)

    class Meta:
        ordering = ['order']
        verbose_name = 'pytanie'
        verbose_name_plural = 'pytania'

    @property
    def has_any_answers(self):
        return self.answers.count() > 0

    @property
    def is_searchable(self):
        return self.data_type in (FormQuestion.TYPE_STRING, FormQuestion.TYPE_PESEL, FormQuestion.TYPE_PHONE)

    @property
    def is_orderable(self):
        return self.data_type in (FormQuestion.TYPE_STRING, FormQuestion.TYPE_NUMBER, FormQuestion.TYPE_DATE)

    @property
    def is_enum(self):
        return self.data_type in (FormQuestion.TYPE_CHOICE, FormQuestion.TYPE_SELECT)

    @property
    def datatables_type_hint(self):
        if self.data_type == FormQuestion.TYPE_PHONE:
            return "phoneNumber"
        return ""

    def value_field_name(self):
        if self.data_type == FormQuestion.TYPE_NUMBER:
            return 'value_number'
        elif self.data_type in (FormQuestion.TYPE_STRING, FormQuestion.TYPE_TEXTBOX, FormQuestion.TYPE_PESEL, FormQuestion.TYPE_PHONE):
            return 'value_string'
        elif self.data_type == FormQuestion.TYPE_DATE:
            return 'value_date'
        elif self.data_type in (FormQuestion.TYPE_CHOICE, FormQuestion.TYPE_MULTIPLE_CHOICE, FormQuestion.TYPE_SELECT):
            return 'value_choices'
        else:
            raise ValueError('Invalid data type: ' + self.data_type)

    def clean(self):
        if self.has_any_answers:
            orig = FormQuestion.objects.get(pk=self.pk)
            errors = {}
            if self.data_type != orig.data_type:
                errors['data_type'] = 'Unable to change data_type if question already has answers'
            if errors:
                raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        if self.value_field_name() != 'value_choices':
            self.options.all().delete()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.form.title) + ': "' + self.title + '"'


class FormQuestionOption(models.Model):
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE, editable=False, related_name='options')
    title = models.CharField(max_length=150, blank=False, verbose_name='Tekst opcji')
    order = models.PositiveIntegerField(default=0, blank=False, null=False)

    def clean(self):
        if self.question.value_field_name() != 'value_choices':
            raise ValidationError('This question type does not take answers')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['order']
        verbose_name = 'opcja'
        verbose_name_plural = 'opcje'

    def __str__(self):
        return self.title


class FormQuestionAnswer(models.Model):
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE, editable=False, related_name='answers')
    user = models.ForeignKey(User, on_delete=models.CASCADE, editable=False, related_name='+')
    last_changed = models.DateTimeField(blank=True, null=True, auto_now=True)
    value_number = models.IntegerField(blank=True, null=True)
    value_string = models.CharField(max_length=100000, blank=True, null=True)
    value_date = models.DateField(blank=True, null=True)
    value_choices = models.ManyToManyField(FormQuestionOption, blank=True, related_name='+')

    ALL_VALUE_FIELDS = ['value_number', 'value_string', 'value_date', 'value_choices']

    class Meta:
        verbose_name = 'odpowiedź'
        verbose_name_plural = 'odpowiedzi'
        unique_together = ('question', 'user')

    @property
    def value(self):
        field_name = self.question.value_field_name()
        if field_name == 'value_choices':
            if self.question.data_type in (FormQuestion.TYPE_CHOICE, FormQuestion.TYPE_SELECT):
                try:
                    return getattr(self, field_name).get()
                except FormQuestionOption.DoesNotExist:
                    return None
            else:
                return getattr(self, field_name).all()
        else:
            return getattr(self, field_name)

    @value.setter
    def value(self, value):
        for field_name in self.ALL_VALUE_FIELDS:
            if field_name == self.question.value_field_name():
                continue
            if field_name == 'value_choices':
                getattr(self, field_name).set([])
            else:
                setattr(self, field_name, None)

        field_name = self.question.value_field_name()
        if field_name == 'value_choices':
            options = value
            if self.question.data_type in (FormQuestion.TYPE_CHOICE, FormQuestion.TYPE_SELECT):
                options = [options] if options else []
            getattr(self, field_name).set(options)
        else:
            setattr(self, field_name, value)

    def pesel_extract_date(self):
        if self.question.data_type != FormQuestion.TYPE_PESEL:
            raise TypeError('Only possible for PESEL fields')
        return pesel_extract_date(self.value)

    def clean(self):
        must_be_empty = self.ALL_VALUE_FIELDS.copy()
        must_be_empty.remove(self.question.value_field_name())
        if 'value_choices' in must_be_empty:
            must_be_empty.remove('value_choices')

        for field_name in must_be_empty:
            field = getattr(self, field_name)
            if field:
                raise ValidationError({field_name: 'Must be empty for data of this type'})

        if self.question.data_type == FormQuestion.TYPE_PESEL:
            try:
                pesel_validate(getattr(self, self.question.value_field_name()))
            except ValidationError as e:
                raise ValidationError({self.question.value_field_name(): e})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.question) + ' - ' + self.user.get_full_name()