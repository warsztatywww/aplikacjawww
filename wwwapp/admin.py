from typing import Optional

from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models.base import Model
from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError
from django.http.request import HttpRequest

import wwwforms.models
from wwwapp.sheets.google import GoogleSheetsAccessError, GoogleSheetsClient
from wwwapp.sheets.queue import request_sync_after_commit
from .models import Article, UserProfile, ArticleContentHistory, \
    WorkshopCategory, Workshop, WorkshopType, WorkshopParticipant, \
    CampParticipant, ResourceYearPermission, Camp, Solution, SolutionFile, CampInterestEmail, \
    CampGoogleSheetsIntegration

admin.site.unregister(User)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    show_change_link = True


class MyUserAdmin(UserAdmin):
    inlines = [UserProfileInline, ]


admin.site.register(User, MyUserAdmin)


class WorkshopInline(admin.TabularInline):
    model = UserProfile.lecturer_workshops.through
    extra = 0
    show_change_link = True


class CampParticipantInline(admin.TabularInline):
    model = CampParticipant
    extra = 0
    show_change_link = True


class CampGoogleSheetsIntegrationInline(admin.StackedInline):
    model = CampGoogleSheetsIntegration
    extra = 0
    max_num = 1
    fields = ('spreadsheet_id', 'enabled', 'participants_sheet_id', 'lecturers_sheet_id',
              'workshops_sheet_id', 'dirty', 'next_sync_at', 'claimed_at', 'attempt_count',
              'last_attempt_at', 'last_success_at', 'last_error')
    readonly_fields = ('participants_sheet_id', 'lecturers_sheet_id', 'workshops_sheet_id',
                       'dirty', 'next_sync_at', 'claimed_at', 'attempt_count', 'last_attempt_at',
                       'last_success_at', 'last_error')

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        parent_clean = formset.clean

        def clean(instance):
            parent_clean(instance)
            for form in instance.forms:
                if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                    continue
                if form.cleaned_data.get('enabled'):
                    try:
                        GoogleSheetsClient.from_settings().validate_spreadsheet(
                            form.cleaned_data['spreadsheet_id'])
                    except (GoogleSheetsAccessError, ValidationError) as error:
                        form.add_error('spreadsheet_id', str(error))
        formset.clean = clean
        return formset


class WorkshopParticipantInline(admin.TabularInline):
    model = WorkshopParticipant
    extra = 0
    show_change_link = True


class UserProfileAdmin(admin.ModelAdmin):
    model = UserProfile
    inlines = [CampParticipantInline, WorkshopInline]


admin.site.register(UserProfile, UserProfileAdmin)


class WorkshopAdmin(admin.ModelAdmin):
    def make_acccepted(self, _request, queryset):
        queryset.update(status='Z')
    make_acccepted.short_description = "Zmień status na Zaakceptowane"

    def make_refused(self, _request, queryset):
        queryset.update(status='O')
    make_refused.short_description = "Zmień status na Odrzucone"

    def make_cancelled(self, _request, queryset):
        queryset.update(status='X')
    make_cancelled.short_description = "Zmień status na Odwołane"

    def make_clear(self, _request, queryset):
        queryset.update(status=None)
    make_clear.short_description = "Zmień status na Null"

    actions = [make_acccepted, make_refused, make_cancelled, make_clear]
    inlines = [WorkshopParticipantInline]


admin.site.register(Workshop, WorkshopAdmin)


class WorkshopCategoryAdminInline(admin.TabularInline):
    model = WorkshopCategory
    extra = 0


class WorkshopTypeAdminInline(admin.TabularInline):
    model = WorkshopType
    extra = 0


class CampAdmin(admin.ModelAdmin):
    model = Camp
    inlines = [WorkshopTypeAdminInline, WorkshopCategoryAdminInline,
               CampGoogleSheetsIntegrationInline]

    fieldsets = (
        (None, {
            'fields': ('year', 'proposal_end_date', 'program_finalized', 'start_date', 'end_date')
        }),
        ('Formularze', {
            'description': 'Ustawienie tych parametrów spowoduje włączenie specjalnej obsługi pól w formularzach',
            'fields': ('forms', 'form_question_birth_date', 'form_question_arrival_date', 'form_question_departure_date')
        }),
    )

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        if obj:
            form.base_fields['form_question_birth_date'].queryset = form.base_fields['form_question_birth_date'].queryset.filter(form__in=obj.forms.all(), data_type__in=(wwwforms.models.FormQuestion.TYPE_DATE, wwwforms.models.FormQuestion.TYPE_PESEL))
            form.base_fields['form_question_arrival_date'].queryset = form.base_fields['form_question_arrival_date'].queryset.filter(form__in=obj.forms.all(), data_type=wwwforms.models.FormQuestion.TYPE_DATE)
            form.base_fields['form_question_departure_date'].queryset = form.base_fields['form_question_departure_date'].queryset.filter(form__in=obj.forms.all(), data_type=wwwforms.models.FormQuestion.TYPE_DATE)
        return form

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in formset.deleted_objects:
            instance.delete()
        for instance in instances:
            enabled_before = instance.pk and CampGoogleSheetsIntegration.objects.get(pk=instance.pk).enabled
            enable_requested = instance.enabled
            if enable_requested:
                instance.enabled = False
            instance.save()
            if instance.enabled:
                client = GoogleSheetsClient.from_settings()
                for tab_name in ('Uczestnicy', 'Prowadzący', 'Warsztaty'):
                    client.ensure_managed_sheet(instance, tab_name)
                request_sync_after_commit([instance.camp_id])
            elif enable_requested:
                try:
                    client = GoogleSheetsClient.from_settings()
                    client.validate_spreadsheet(instance.spreadsheet_id)
                    for tab_name in ('Uczestnicy', 'Prowadzący', 'Warsztaty'):
                        client.ensure_managed_sheet(instance, tab_name)
                except Exception as error:
                    instance.last_error = '%s: %s' % (error.__class__.__name__, error)
                    instance.save(update_fields=['enabled', 'last_error'])
                    messages.error(request, instance.last_error)
                    continue
                instance.enabled = True
                instance.last_error = ''
                instance.save(update_fields=['enabled', 'last_error'])
                request_sync_after_commit([instance.camp_id])
            elif enabled_before:
                instance.dirty = False
                instance.next_sync_at = None
                instance.claimed_at = None
                instance.claim_token = None
                instance.save(update_fields=['dirty', 'next_sync_at', 'claimed_at', 'claim_token'])
        formset.save_m2m()


admin.site.register(Camp, CampAdmin)


class ArticleContentHistoryInlineAdmin(admin.TabularInline):
    model = ArticleContentHistory
    fields = ('version', 'modified_by', 'time')
    readonly_fields = ('version', 'modified_by', 'time')
    extra = 0
    can_delete = False
    show_change_link = True
    ordering = ('-version',)

    def has_add_permission(self, request: HttpRequest, obj: Optional[Model] = ...) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Optional[Model] = ...) -> bool:
        return False


class ArticleContentHistoryAdmin(admin.ModelAdmin):
    model = ArticleContentHistory

    def has_module_permission(self, request: HttpRequest) -> bool:
        # This prevents the editor from appearing on the main page list. We still want the editor itself
        # for show_change_link in ArticleContentHistoryInlineAdmin to work
        return False

    def has_change_permission(self, request: HttpRequest, obj: Optional[Model] = ...) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Optional[Model] = ...) -> bool:
        return False


class ArticleAdmin(SortableAdminMixin, admin.ModelAdmin):
    model = Article
    inlines = [ArticleContentHistoryInlineAdmin]
    readonly_fields = ('modified_by',)
    list_filter = ('on_menubar',)
    list_display = ('name', 'title', 'on_menubar',)


admin.site.register(Article, ArticleAdmin)
admin.site.register(ArticleContentHistory, ArticleContentHistoryAdmin)


class SolutionInline(admin.StackedInline):
    model = Solution
    extra = 0
    show_change_link = True


class WorkshopParticipantAdmin(admin.ModelAdmin):
    model = WorkshopParticipant
    inlines = [SolutionInline]


class CampParticipantAdmin(admin.ModelAdmin):
    model = CampParticipant
    inlines = [WorkshopParticipantInline]

    def make_acccepted(self, _request, queryset):
        queryset.update(status='Z')
    make_acccepted.short_description = "Zmień status na Zaakceptowane"

    def make_refused(self, _request, queryset):
        queryset.update(status='O')
    make_refused.short_description = "Zmień status na Odrzucone"

    def make_cancelled(self, _request, queryset):
        queryset.update(status='X')
    make_cancelled.short_description = "Zmień status na Odwołane"

    def make_clear(self, _request, queryset):
        queryset.update(status=None)
    make_clear.short_description = "Zmień status na Null"

    actions = [make_acccepted, make_refused, make_cancelled, make_clear]


class SolutionFileInlineFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields[self._pk_field.name].queryset = self.model.all_objects


class SolutionFileInline(admin.TabularInline):
    model = SolutionFile
    formset = SolutionFileInlineFormSet
    extra = 1
    show_change_link = False
    fields = ('file', 'last_changed', 'deleted', 'deleted_at')
    readonly_fields = ('last_changed', 'deleted')

    # Change the queryset to include deleted objects
    def get_queryset(self, request):
        queryset = self.model.all_objects
        # The below is copied from the base implementation in BaseModelAdmin to prevent other changes in behavior
        ordering = self.get_ordering(request)
        if ordering:
            queryset = queryset.order_by(*ordering)
        if not self.has_view_or_change_permission(request):
            queryset = queryset.none()
        return queryset


class SolutionAdmin(admin.ModelAdmin):
    model = Solution
    inlines = [SolutionFileInline]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ['workshop_participant']
        else:
            return []


admin.site.register(WorkshopParticipant, WorkshopParticipantAdmin)
admin.site.register(CampParticipant, CampParticipantAdmin)
admin.site.register(CampInterestEmail)
admin.site.register(Solution, SolutionAdmin)

admin.site.register(ResourceYearPermission)
