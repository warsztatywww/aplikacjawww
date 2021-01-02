from django.contrib import admin

from wwwforms.models import Form, FormQuestion, FormQuestionAnswer


class FormQuestionInline(admin.TabularInline):
    model = FormQuestion
    extra = 0
    show_change_link = True
    fields = ('title', 'data_type', 'is_required')
    readonly_fields = ('form',)

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
            'fields': ('name', 'title')
        }),
        ('Pola specjalne', {
            'description': 'Ustawienie tych parametrów spowoduje włączenie specjalnej obsługi tych pól',
            'fields': ('arrival_date', 'departure_date')
        }),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        if obj:
            form.base_fields['arrival_date'].queryset = form.base_fields['arrival_date'].queryset.filter(form=obj)
            form.base_fields['departure_date'].queryset = form.base_fields['departure_date'].queryset.filter(form=obj)
        return form

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj:
            fieldsets = [fieldsets[0]]
        return fieldsets


class FormQuestionAnswerInline(admin.TabularInline):
    model = FormQuestionAnswer
    extra = 0
    fields = ('user',)
    readonly_fields = ('user',)
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        fields.append(obj.value_field_name())
        return fields


class FormQuestionAdmin(admin.ModelAdmin):
    model = FormQuestion
    inlines = [FormQuestionAnswerInline]

    def reset_answers(self, request, queryset):
        FormQuestionAnswer.objects.filter(question__in=queryset).delete()
    reset_answers.short_description = 'Wyczyść odpowiedzi'

    actions = [reset_answers]

    def get_inlines(self, request, obj):
        if not obj:
            return []
        return super().get_inlines(request, obj)

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


admin.site.register(Form, FormAdmin)
admin.site.register(FormQuestion, FormQuestionAdmin)
