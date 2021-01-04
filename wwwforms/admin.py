from adminsortable2.admin import SortableInlineAdminMixin
from django.contrib import admin, messages
from django.contrib.admin.exceptions import DisallowedModelAdminToField
from django.contrib.admin.options import csrf_protect_m, TO_FIELD_VAR, IS_POPUP_VAR
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db import transaction, router
from django import forms
from django.http.response import HttpResponseRedirect
from django.template import Template, Context
from django.urls import path, reverse
from django.utils.translation import gettext_lazy as _

from wwwforms.models import Form, FormQuestion, FormQuestionAnswer, FormQuestionOption


class FormQuestionInline(SortableInlineAdminMixin, admin.TabularInline):
    model = FormQuestion
    extra = 0
    show_change_link = True
    can_delete = False
    fields = ('title', 'data_type', 'is_required', 'is_locked', 'reset_answers_or_delete_action')
    readonly_fields = ('form', 'reset_answers_or_delete_action')

    def reset_answers_or_delete_action(self, obj):
        if obj and obj.pk:
            return Template(
                '<a class="button" {% if obj.has_any_answers %}href="{% url "admin:wwwforms_formquestion_reset" obj.pk %}"{% else %}disabled{% endif %}>Zresetuj odpowiedzi</a>'
                '&nbsp;&nbsp;&nbsp;'
                '<a href="{% url "admin:wwwforms_formquestion_delete" obj.pk %}" class="button">Usuń pytanie</a>'
            ).render(Context({'obj': obj}))
        return ''
    reset_answers_or_delete_action.short_description = 'Zresetuj odpowiedzi / usuń'

    # TODO: I wanted to disable it for individual questions, but Django doesn't support it (╯°□°）╯︵ ┻━┻
    # https://stackoverflow.com/questions/6727372/get-readonly-fields-in-a-tabularinline-class-in-django/12869505#12869505
    # You get an error on save instead, deal with it

    # def get_readonly_fields(self, request, obj=None):
    #     print(obj)
    #     readonly_fields = list(super().get_readonly_fields(request, obj))
    #     if any(q.has_any_answers for q in obj.questions.all()):
    #         readonly_fields.extend(['data_type'])
    #     return readonly_fields


class FormAdmin(admin.ModelAdmin):
    model = Form
    inlines = [FormQuestionInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'title', 'description', 'is_visible', 'reset_answers_action')
        }),
        ('Pola specjalne', {
            'description': 'Ustawienie tych parametrów spowoduje włączenie specjalnej obsługi tych pól',
            'fields': ('arrival_date', 'departure_date')
        }),
    )
    readonly_fields = ('reset_answers_action',)

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        if obj:
            form.base_fields['arrival_date'].queryset = form.base_fields['arrival_date'].queryset.filter(form=obj)
            form.base_fields['departure_date'].queryset = form.base_fields['departure_date'].queryset.filter(form=obj)
        return form

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj:
            # Hide the special field settings (this is a new form, so no fields exist yet)
            fieldsets = [fieldsets[0]]
        return fieldsets

    def reset_answers_action(self, obj):
        return Template(
            '<a class="button" {% if obj.has_any_answers %}href="{% url "admin:wwwforms_form_reset" obj.pk %}"{% else %}disabled{% endif %}>Zresetuj odpowiedzi</a>'
        ).render(Context({'obj': obj}))
    reset_answers_action.short_description = 'Zresetuj odpowiedzi'

    def get_urls(self):
        return [
            path('<path:object_id>/reset/', self.admin_site.admin_view(self.reset_view),
                 name='%s_%s_reset' % (self.model._meta.app_label, self.model._meta.model_name)),
        ] + super().get_urls()

    @csrf_protect_m
    def reset_view(self, request, object_id, extra_context=None):
        # based on ModelAdmin.delete_view, slightly modified to delete obj.questions.answers.all() instead of obj
        with transaction.atomic(using=router.db_for_write(self.model)):
            opts = self.model._meta
            app_label = opts.app_label

            to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
            if to_field and not self.to_field_allowed(request, to_field):
                raise DisallowedModelAdminToField("The field %s cannot be referenced." % to_field)

            obj = self.get_object(request, unquote(object_id), to_field)

            if obj is None:
                return self._get_obj_does_not_exist_redirect(request, opts, object_id)

            # Populate deleted_objects, a data structure of all related objects that
            # will also be deleted.
            qs = FormQuestionAnswer.objects.filter(question__form=obj).prefetch_related('question', 'question__form', 'user')
            deleted_objects, model_count, perms_needed, protected = self.get_deleted_objects(qs, request)

            if request.POST and not protected:  # The user has confirmed the deletion.
                if perms_needed:
                    raise PermissionDenied
                obj_display = str(obj)
                attr = str(to_field) if to_field else opts.pk.attname
                obj_id = obj.serializable_value(attr)

                qs.delete()

                self.message_user(
                    request,
                    _('The %(name)s “%(obj)s” was deleted successfully.') % {
                        'name': 'odpowiedzi do wszystkich pytań z formularza',
                        'obj': obj_display,
                    },
                    messages.SUCCESS,
                )

                if self.has_change_permission(request, None):
                    post_url = reverse(
                        'admin:%s_%s_change' % (opts.app_label, opts.model_name),
                        args=[obj_id],
                        current_app=self.admin_site.name,
                    )
                else:
                    post_url = reverse('admin:index', current_app=self.admin_site.name)
                return HttpResponseRedirect(post_url)

            if perms_needed or protected:
                title = _("Cannot delete %(name)s") % {"name": 'odpowiedzi do wszystkich pytań z formularza'}
            else:
                title = _("Are you sure?")

            context = {
                **self.admin_site.each_context(request),
                'title': title,
                'object_name': 'wszystkie odpowiedzi do wszystkich pytań z formularza',
                'object': obj,
                'deleted_objects': deleted_objects,
                'model_count': dict(model_count).items(),
                'perms_lacking': perms_needed,
                'protected': protected,
                'opts': opts,
                'app_label': app_label,
                'preserved_filters': self.get_preserved_filters(request),
                'is_popup': IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
                'to_field': to_field,
                **(extra_context or {}),
            }

            return self.render_delete_form(request, context)


class FormQuestionAnswerInlineForm(forms.ModelForm):
    value_choices = forms.ModelMultipleChoiceField(widget=forms.widgets.CheckboxSelectMultiple, queryset=FormQuestionOption.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields[self.instance.question.value_field_name()].required = self.instance.question.is_required
            if self.instance.question.value_field_name() == 'value_choices':
                self.fields['value_choices'].queryset = self.instance.question.options.all()


class FormQuestionAnswerInline(admin.TabularInline):
    form = FormQuestionAnswerInlineForm
    model = FormQuestionAnswer
    extra = 0
    fields = ('user', 'last_changed')
    readonly_fields = ('user', 'last_changed')
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        fields.append(obj.value_field_name())
        return fields


class FormQuestionOptionInline(SortableInlineAdminMixin, admin.TabularInline):
    model = FormQuestionOption
    extra = 0
    fields = ('title',)
    show_change_link = False


class FormQuestionAdmin(admin.ModelAdmin):
    model = FormQuestion
    fields = ('form', 'title', 'data_type', 'is_required', 'is_locked', 'reset_answers_action')
    readonly_fields = ('reset_answers_action',)

    def get_inlines(self, request, obj):
        if not obj:
            return []
        elif obj.value_field_name() == 'value_choices':
            return [FormQuestionOptionInline, FormQuestionAnswerInline]
        else:
            return [FormQuestionAnswerInline]

    def reset_answers_action(self, obj):
        return Template(
            '<a class="button" {% if obj.has_any_answers %}href="{% url "admin:wwwforms_formquestion_reset" obj.pk %}"{% else %}disabled{% endif %}>Zresetuj odpowiedzi</a>'
        ).render(Context({'obj': obj}))
    reset_answers_action.short_description = 'Zresetuj odpowiedzi'

    def get_urls(self):
        return [
            path('<path:object_id>/reset/', self.admin_site.admin_view(self.reset_view),
                 name='%s_%s_reset' % (self.model._meta.app_label, self.model._meta.model_name)),
        ] + super().get_urls()

    @csrf_protect_m
    def reset_view(self, request, object_id, extra_context=None):
        # based on ModelAdmin.delete_view, slightly modified to delete obj.answers.all() instead of obj
        with transaction.atomic(using=router.db_for_write(self.model)):
            opts = self.model._meta
            app_label = opts.app_label

            to_field = request.POST.get(TO_FIELD_VAR, request.GET.get(TO_FIELD_VAR))
            if to_field and not self.to_field_allowed(request, to_field):
                raise DisallowedModelAdminToField("The field %s cannot be referenced." % to_field)

            obj = self.get_object(request, unquote(object_id), to_field)

            if obj is None:
                return self._get_obj_does_not_exist_redirect(request, opts, object_id)

            # Populate deleted_objects, a data structure of all related objects that
            # will also be deleted.
            qs = obj.answers.prefetch_related('question', 'question__form', 'user')
            deleted_objects, model_count, perms_needed, protected = self.get_deleted_objects(qs, request)

            if request.POST and not protected:  # The user has confirmed the deletion.
                if perms_needed:
                    raise PermissionDenied
                obj_display = str(obj)
                attr = str(to_field) if to_field else opts.pk.attname
                obj_id = obj.serializable_value(attr)

                qs.delete()

                self.message_user(
                    request,
                    _('The %(name)s “%(obj)s” was deleted successfully.') % {
                        'name': 'odpowiedzi do pytania',
                        'obj': obj_display,
                    },
                    messages.SUCCESS,
                )

                if self.has_change_permission(request, None):
                    post_url = reverse(
                        'admin:%s_%s_change' % (opts.app_label, opts.model_name),
                        args=[obj_id],
                        current_app=self.admin_site.name,
                    )
                else:
                    post_url = reverse('admin:index', current_app=self.admin_site.name)
                return HttpResponseRedirect(post_url)

            if perms_needed or protected:
                title = _("Cannot delete %(name)s") % {"name": 'odpowiedzi do pytania'}
            else:
                title = _("Are you sure?")

            context = {
                **self.admin_site.each_context(request),
                'title': title,
                'object_name': 'wszystkie odpowiedzi do pytania',
                'object': obj,
                'deleted_objects': deleted_objects,
                'model_count': dict(model_count).items(),
                'perms_lacking': perms_needed,
                'protected': protected,
                'opts': opts,
                'app_label': app_label,
                'preserved_filters': self.get_preserved_filters(request),
                'is_popup': IS_POPUP_VAR in request.POST or IS_POPUP_VAR in request.GET,
                'to_field': to_field,
                **(extra_context or {}),
            }

            return self.render_delete_form(request, context)

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj.has_any_answers:
            readonly_fields.append('data_type')
        return readonly_fields

    def has_module_permission(self, request):
        # This prevents the editor from appearing on the main page list. We still want the editor itself
        # for show_change_link in Form to work
        return False

    def has_add_permission(self, request):
        return False

    # After editing a question, return to the form editor, not question list
    def _response_post_save(self, request, obj):
        return HttpResponseRedirect(
            reverse('admin:wwwforms_form_change', args=[obj.form.pk],
                    current_app=self.admin_site.name))

    def response_post_save_add(self, request, obj):
        return self._response_post_save(request, obj)

    def response_post_save_change(self, request, obj):
        return self._response_post_save(request, obj)


admin.site.register(Form, FormAdmin)
admin.site.register(FormQuestion, FormQuestionAdmin)
