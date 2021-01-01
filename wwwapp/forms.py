from crispy_forms.bootstrap import FormActions, StrictButton, PrependedAppendedText, Alert
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Button, Div, HTML
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.forms import ModelChoiceField, ModelMultipleChoiceField, DateInput
from django.forms import ModelForm, FileInput, FileField
from django.forms.fields import ImageField
from django.forms.forms import Form
from django.urls import reverse
from django_select2.forms import Select2MultipleWidget, Select2Widget
from tinymce.widgets import TinyMCE
from django.conf import settings

from .models import UserProfile, Article, Workshop, WorkshopCategory, \
    WorkshopType, UserInfo, WorkshopUserProfile, WorkshopParticipant, Camp


class UserProfilePageForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(UserProfilePageForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.include_media = False
        self.helper.layout.fields.append(FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-default'),
            HTML('<a class="btn" href="{% url "profile" user.id %}" target="_blank" title="Otwiera się w nowej karcie">Podgląd twojego profilu</a>'),
        ))

    class Meta:
        model = UserProfile
        fields = ['profile_page']
        labels = {'profile_page': "Strona profilowa"}
        widgets = {'profile_page': TinyMCE()}


class UserCoverLetterForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(UserCoverLetterForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.include_media = False
        self.helper.layout.fields.append(FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-default'),
            HTML('<a class="btn" href="{% url "profile" user.id %}" target="_blank" title="Otwiera się w nowej karcie">Podgląd twojego profilu</a>'),
        ))

    class Meta:
        model = UserProfile
        fields = ['cover_letter']
        labels = {'cover_letter': "List motywacyjny"}
        widgets = {'cover_letter': TinyMCE()}


class UserInfoPageForm(ModelForm):
    def __init__(self, *args, year, **kwargs):
        super(UserInfoPageForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.include_media = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-3'
        self.helper.field_class = 'col-lg-9'
        self.helper.layout.fields.append(FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-default'),
        ))

        self.year = year
        self.fields['start_date'].widget = DateInput(attrs={'data-default-date': year.start_date or '', 'data-start-date': year.start_date or '', 'data-end-date': year.end_date or ''})
        self.fields['end_date'].widget = DateInput(attrs={'data-default-date': year.end_date or '', 'data-start-date': year.start_date or '', 'data-end-date': year.end_date or ''})

    def clean_start_date(self):
        if self.cleaned_data['start_date']:
            if self.cleaned_data['start_date'] < self.year.start_date:
                raise ValidationError('Warsztaty rozpoczynają się ' + str(self.year.start_date))
            if self.cleaned_data['start_date'] > self.year.end_date:
                raise ValidationError('Warsztaty kończą się ' + str(self.year.end_date))
            if 'end_date' in self.cleaned_data and self.cleaned_data['end_date']:
                if self.cleaned_data['start_date'] > self.cleaned_data['end_date']:
                    raise ValidationError('Nie możesz wyjechać wcześniej niż przyjechać! :D')
        return self.cleaned_data['start_date']

    def clean_end_date(self):
        if self.cleaned_data['end_date']:
            if self.cleaned_data['end_date'] < self.year.start_date:
                raise ValidationError('Warsztaty rozpoczynają się ' + str(self.year.start_date))
            if self.cleaned_data['end_date'] > self.year.end_date:
                raise ValidationError('Warsztaty kończą się ' + str(self.year.end_date))
            if 'start_date' in self.cleaned_data and self.cleaned_data['start_date']:
                if self.cleaned_data['start_date'] > self.cleaned_data['end_date']:
                    raise ValidationError('Nie możesz wyjechać wcześniej niż przyjechać! :D')
        return self.cleaned_data['end_date']

    class Meta:
        model = UserInfo
        fields = ['pesel', 'address', 'phone', 'start_date', 'end_date', 'tshirt_size', 'comments']
        labels = {
            'pesel': 'Pesel',
            'address': 'Adres zameldowania',
            'phone': 'Numer telefonu',
            'start_date': 'Data przyjazdu :-)',
            'end_date': 'Data wyjazdu :-(',
            'tshirt_size': 'Rozmiar koszulki',
            'comments': 'Dodatkowe uwagi (np. wegetarianin, uczulony na X, ale też inne)',
        }


class UserProfileForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False  # We have to put two Forms in one <form> :(
        self.helper.disable_csrf = True  # Already added by UserForm
        self.helper.include_media = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-10'
        self.helper.layout.fields.append(FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-default'),
            HTML('<a class="btn" href="{% url "profile" user.id %}" target="_blank" title="Otwiera się w nowej karcie">Podgląd twojego profilu</a>'),
        ))

    class Meta:
        model = UserProfile
        fields = ['gender', 'school', 'matura_exam_year', 'how_do_you_know_about']
        labels = {
            'gender': 'Płeć',
            'school': 'Szkoła lub uniwersytet',
            'matura_exam_year': 'Rok zdania matury',
            'how_do_you_know_about': 'Skąd wiesz o WWW?',
        }


class UserForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False  # We have to put two Forms in one <form> :(
        self.helper.include_media = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-lg-2'
        self.helper.field_class = 'col-lg-10'

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        labels = {
            'first_name': 'Imię',
            'last_name': 'Nazwisko',
            'email': 'E-mail',
        }


class ArticleForm(ModelForm):
    # These articles have a special purpose - their names cannot be changed because they are used in code,
    # and they are not supposed to ever have a title in the database or be placed on the menubar
    SPECIAL_ARTICLES = {
        'index': 'Strona główna',
        'template_for_workshop_page': 'Szablon strony warsztatów'
    }

    class Meta:
        model = Article
        fields = ['title', 'name', 'on_menubar', 'content']
        labels = {
            'title': 'Tytuł',
            'name': 'Nazwa (w URLach)',
            'on_menubar': 'Umieść w menu',
            'content': 'Treść',
        }

    def __init__(self, user, article_url, *args, **kwargs):
        super(ModelForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.include_media = False

        mce_attrs = {}
        if self.instance and self.instance.pk:
            mce_attrs = settings.TINYMCE_DEFAULT_CONFIG_WITH_IMAGES.copy()
            mce_attrs['automatic_uploads'] = True
            mce_attrs['images_upload_url'] = reverse('article_edit_upload', kwargs={'name': self.instance.name})
        self.fields['content'].widget = TinyMCE(mce_attrs=mce_attrs)

        is_special = kwargs['instance'] and kwargs['instance'].pk and \
                     kwargs['instance'].name in ArticleForm.SPECIAL_ARTICLES.keys()

        layout = []
        if is_special:
            del self.fields['name']
            del self.fields['title']
            del self.fields['on_menubar']
        else:
            layout.append(PrependedAppendedText('name',
                article_url[0],
                article_url[1]
            ))
            layout.append('title')
            layout.append('on_menubar')

            if not user.has_perm('wwwapp.can_put_on_menubar'):
                self.fields['on_menubar'].disabled = True
        layout.append('content')
        layout.append(FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-default'),
        ))
        self.helper.layout = Layout(*layout)

        self.helper.layout.fields.append(FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-default')
        ))


class WorkshopForm(ModelForm):
    # Note that the querysets for category and type are overwritten in __init__, but the argument is required here
    category = ModelMultipleChoiceField(label="Kategorie", queryset=WorkshopCategory.objects.all(),
                                        widget=Select2MultipleWidget(attrs={'width': '200px'}))
    type = ModelChoiceField(label="Rodzaj zajęć", queryset=WorkshopType.objects.all(),
                            widget=Select2Widget(attrs={'width': '200px'}))

    qualification_problems = FileField(required=False, widget=FileInput(), label='Zadania kwalifikacyjne (zalecany format PDF):')

    class Meta:
        model = Workshop
        fields = ['title', 'name', 'type', 'category', 'proposition_description',
                  'qualification_problems', 'is_qualifying',
                  'max_points', 'qualification_threshold',
                  'page_content', 'page_content_is_public']
        labels = {
            'title': 'Tytuł',
            'name': 'Nazwa (w URLach)',
            'proposition_description': 'Opis propozycji warsztatów',
            'is_qualifying': 'Czy warsztaty są kwalifikujące',
            'max_points': 'Maksymalna liczba punktów możliwa do uzyskania z obowiązkowych zadań',
            'qualification_threshold': 'Minimalna liczba punktów potrzebna do kwalifikacji',
            'page_content': 'Strona warsztatów',
            'page_content_is_public': 'Zaznacz, jeśli opis jest gotowy i może już być publiczny.'
        }
        help_texts = {
            'is_qualifying': '(odznacz, jeśli nie zamierzasz dodawać zadań i robić kwalifikacji)',
            'qualification_threshold': '(wpisz dopiero po sprawdzeniu zadań)',
        }

    def __init__(self, *args, workshop_url, has_perm_to_edit=True, profile_warnings=None, **kwargs):
        super(ModelForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.include_media = False

        # Disable fields that should be disabled
        if not self.instance.is_workshop_editable() or not has_perm_to_edit:
            for field in self.fields.values():
                field.disabled = True

        if self.instance.status:
            # The proposition cannot be edited once the workshop has a status set
            self.fields['proposition_description'].disabled = True

        # Make sure only current category and type choices are displayed
        if self.instance is None:
            raise ValueError('WorkshopForm must be provided with an instance with the .year field already set')
        year = self.instance.year
        self.fields['category'].queryset = WorkshopCategory.objects.filter(year=year)
        self.fields['type'].queryset = WorkshopType.objects.filter(year=year)

        # Configure TinyMCE settings
        mce_attrs = {}
        mce_attrs['readonly'] = self.fields['proposition_description'].disabled  # does not seem to respect the Django field settings for some reason
        self.fields['proposition_description'].widget = TinyMCE(mce_attrs=mce_attrs)

        mce_attrs = settings.TINYMCE_DEFAULT_CONFIG_WITH_IMAGES.copy()
        if self.instance and self.instance.pk:
            mce_attrs['automatic_uploads'] = True
            mce_attrs['images_upload_url'] = reverse('workshop_edit_upload', kwargs={'year': self.instance.year.pk, 'name': self.instance.name})
        mce_attrs['readonly'] = self.fields['page_content'].disabled  # does not seem to respect the Django field settings for some reason
        self.fields['page_content'].widget = TinyMCE(mce_attrs=mce_attrs)

        # Layout
        self.fieldset_general = Fieldset(
            "Ogólne",
            Div(
                Div(PrependedAppendedText('name',
                    workshop_url[0] + '<b>' + str(year.pk) + '</b>' + workshop_url[1],
                    workshop_url[2]
                ), css_class='col-lg-12'),
                Div('title', css_class='col-lg-12'),
                css_class='row'
            ),
            Div(
                Div('type', css_class='col-lg-6'),
                Div('category', css_class='col-lg-6'),
                css_class='row'
            ),
        )
        if profile_warnings:
            for message in profile_warnings:
                self.fieldset_general.fields.append(Alert(content=message, dismiss=False, css_class='alert-info'))
        self.fieldset_proposal = Fieldset(
            "Opis propozycji",
            'proposition_description',
        )
        self.fieldset_qualification = Fieldset(
            "Kwalifikacja",
            'is_qualifying',
            Div(
                'qualification_problems',
                Div(
                    Div('max_points', css_class='col-lg-6'),
                    Div('qualification_threshold', css_class='col-lg-6'),
                    css_class='row'
                ),
                css_id='qualification_settings'
            ),
        )
        self.fieldset_public_page = Fieldset(
            "Strona warsztatów",
            'page_content',
            'page_content_is_public'
        )
        self.fieldset_submit = FormActions(
            StrictButton('Zapisz', type='submit', css_class='btn-default'),
        )

        if not self.instance or not self.instance.is_publicly_visible():
            for field in [
                  'qualification_problems', 'is_qualifying',
                  'max_points', 'qualification_threshold',
                  'page_content', 'page_content_is_public']:
                del self.fields[field]

            self.helper.layout = Layout(
                self.fieldset_general,
                self.fieldset_proposal,
                self.fieldset_submit,
            )
        else:
            if not has_perm_to_edit:
                self.helper.layout = Layout(
                    self.fieldset_general,
                    self.fieldset_proposal,
                    self.fieldset_qualification,
                    self.fieldset_public_page,
                )
            else:
                self.helper.layout = Layout(
                    self.fieldset_general,
                    self.fieldset_proposal,
                    self.fieldset_qualification,
                    self.fieldset_public_page,
                    self.fieldset_submit,
                )

    def clean(self):
        super(WorkshopForm, self).clean()
        if not self.instance.is_workshop_editable():
            raise ValidationError('Nie można edytować warsztatów z poprzednich lat')

    def validate_unique(self):
        # Must remove year field from exclude in order
        # for the unique_together constraint to be enforced.
        exclude = self._get_validation_exclusions()
        exclude.remove('year')

        try:
            self.instance.validate_unique(exclude=exclude)
        except ValidationError as e:
            self._update_errors(e.message_dict)


class WorkshopParticipantPointsForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(WorkshopParticipantPointsForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            # autocomplete=off fixes a problem on Firefox where the form fields don't reset on reload, making the save button visibility desync
            field.widget.attrs.update({'class': 'form-control', 'autocomplete': 'off'})
            field.required = False

        if not self.instance.workshop.is_qualification_editable():
            for field in self.fields.values():
                field.disabled = True

    class Meta:
        model = WorkshopParticipant
        fields = ['qualification_result', 'comment']

    def clean(self):
        super(WorkshopParticipantPointsForm, self).clean()
        if not self.instance.workshop.is_qualification_editable():
            raise ValidationError('Nie można edytować warsztatów z poprzednich lat')

        # Only apply changes to the fields that were actually sent
        for k, v in self.cleaned_data.items():
            if k not in self.data:
                self.cleaned_data[k] = getattr(self.instance, k, self.cleaned_data[k])


class TinyMCEUpload(Form):
    file = ImageField()
