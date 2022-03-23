from typing import Optional

from adminsortable2.admin import SortableAdminMixin
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models.base import Model
from django.forms.models import BaseInlineFormSet
from django.http.request import HttpRequest

from .models import Article, UserProfile, ArticleContentHistory, \
    WorkshopCategory, Workshop, WorkshopType, WorkshopParticipant, \
    CampParticipant, ResourceYearPermission, Camp, Solution, SolutionFile

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


class WorkshopParticipantInline(admin.TabularInline):
    model = WorkshopParticipant
    extra = 0
    show_change_link = True


class UserProfileAdmin(admin.ModelAdmin):
    model = UserProfile
    inlines = [CampParticipantInline, WorkshopParticipantInline, WorkshopInline]


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
    inlines = [WorkshopTypeAdminInline, WorkshopCategoryAdminInline]


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
admin.site.register(CampParticipant)
admin.site.register(Solution, SolutionAdmin)

admin.site.register(ResourceYearPermission)
