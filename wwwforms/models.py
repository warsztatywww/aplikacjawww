import datetime

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


def pesel_extract_date(pesel: str) -> datetime.date or None:
    """
    Takes PESEL (string that starts with at least 6 digits) and returns
    birth date associated with it.
    """
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


class Form(models.Model):
    name = models.SlugField(max_length=50, blank=False, unique=True, verbose_name='Nazwa', help_text='(w URLach)')
    title = models.CharField(max_length=50, blank=False, verbose_name='Tytuł')

    arrival_date = models.ForeignKey('FormQuestion', blank=True, null=True, on_delete=models.SET_NULL, related_name='+', verbose_name='Data przyjazdu')
    departure_date = models.ForeignKey('FormQuestion', blank=True, null=True, on_delete=models.SET_NULL, related_name='+', verbose_name='Data wyjazdu')

    class Meta:
        verbose_name = 'formularz'
        verbose_name_plural = 'formularze'
        permissions = [('see_form_results', 'Can see form results')]

    @property
    def has_any_answers(self):
        return FormQuestionAnswer.objects.filter(question__form=self).count()

    def clean(self):
        if self.arrival_date and self.arrival_date.form != self:
            raise ValidationError({'arrival_date': 'Musi być z tego formularza'})
        if self.departure_date and self.departure_date.form != self:
            raise ValidationError({'departure_date': 'Musi być z tego formularza'})
        if self.arrival_date and self.arrival_date.data_type != FormQuestion.TYPE_DATE:
            raise ValidationError({'arrival_date': 'Musi być datą'})
        if self.departure_date and self.departure_date.data_type != FormQuestion.TYPE_DATE:
            raise ValidationError({'departure_date': 'Musi być datą'})
        if self.arrival_date and self.departure_date and self.arrival_date == self.departure_date:
            raise ValidationError({'arrival_date': 'Muszą być różnymi polami', 'departure_date': 'Muszą być różnymi polami'})
        if bool(self.arrival_date) != bool(self.departure_date):
            raise ValidationError({'arrival_date': 'Muszą być oba ustawione lub oba nieustawione', 'departure_date': 'Muszą być oba ustawione lub oba nieustawione'})

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class FormQuestion(models.Model):
    TYPE_NUMBER = 'n'
    TYPE_STRING = 's'
    TYPE_TEXTBOX = 't'
    TYPE_DATE = 'd'
    TYPE_PESEL = 'P'

    TYPE_CHOICES = [
        (TYPE_NUMBER, 'Liczba'),
        (TYPE_STRING, 'Tekst'),
        (TYPE_TEXTBOX, 'Tekst (wiele linii)'),
        (TYPE_DATE, 'Data'),
        (TYPE_PESEL, 'PESEL'),
    ]

    form = models.ForeignKey(Form, on_delete=models.CASCADE, editable=False, related_name='questions')
    title = models.CharField(max_length=150, blank=False, verbose_name='Tekst pytania')
    data_type = models.CharField(max_length=1, blank=False, choices=TYPE_CHOICES, verbose_name='Typ odpowiedzi')
    is_required = models.BooleanField(default=True, verbose_name='Wymagane?')
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
        return self.data_type in (FormQuestion.TYPE_STRING, FormQuestion.TYPE_PESEL)

    @property
    def is_orderable(self):
        return self.data_type in (FormQuestion.TYPE_STRING, FormQuestion.TYPE_NUMBER, FormQuestion.TYPE_DATE)

    def value_field_name(self):
        if self.data_type == FormQuestion.TYPE_NUMBER:
            return 'value_number'
        elif self.data_type in (FormQuestion.TYPE_STRING, FormQuestion.TYPE_TEXTBOX, FormQuestion.TYPE_PESEL):
            return 'value_string'
        elif self.data_type == FormQuestion.TYPE_DATE:
            return 'value_date'
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
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.form) + ': "' + self.title + '"'


class FormQuestionAnswer(models.Model):
    question = models.ForeignKey(FormQuestion, on_delete=models.CASCADE, editable=False, related_name='answers')
    user = models.ForeignKey(User, on_delete=models.CASCADE, editable=False, related_name='+')
    value_number = models.IntegerField(blank=True, null=True)
    value_string = models.CharField(max_length=100000, blank=True, null=True)
    value_date = models.DateField(blank=True, null=True)

    ALL_VALUE_FIELDS = ['value_number', 'value_string', 'value_date']

    class Meta:
        verbose_name = 'odpowiedź'
        verbose_name_plural = 'odpowiedzi'
        unique_together = ('question', 'user')

    @property
    def value(self):
        return getattr(self, self.question.value_field_name())

    @value.setter
    def value(self, value):
        for field_name in self.ALL_VALUE_FIELDS:
            setattr(self, field_name, None)
        setattr(self, self.question.value_field_name(), value)

    def clean(self):
        must_be_empty = self.ALL_VALUE_FIELDS.copy()
        must_be_empty.remove(self.question.value_field_name())
        must_be_set = []
        if self.question.is_required:
            must_be_set.append(self.question.value_field_name())

        for field_name in must_be_empty:
            field = getattr(self, field_name)
            if field:
                raise ValidationError({field_name: 'Must be empty'})
        for field_name in must_be_set:
            field = getattr(self, field_name)
            if not field:
                raise ValidationError({field_name: 'Must be filled'})

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


