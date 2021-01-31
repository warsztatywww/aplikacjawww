from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

from . import views, mail_views
import wwwforms.views as wwwforms_views

urlpatterns = [
    path('profile/<int:user_id>/', views.profile_view, name='profile'),
    path('me/profile/', views.mydata_profile_view, name='mydata_profile'),
    path('me/profile_page/', views.mydata_profile_page_view, name='mydata_profile_page'),
    path('me/cover_letter/', views.mydata_cover_letter_view, name='mydata_cover_letter'),
    path('me/status/', views.mydata_status_view, name='mydata_status'),
    path('me/forms/', views.mydata_forms_view, name='mydata_forms'),
    path('forms/', wwwforms_views.form_list_view, name='form_list'),
    path('forms/<slug:name>/', wwwforms_views.form_view, name='form'),
    path('forms/<slug:name>/results/', wwwforms_views.form_results_view, name='form_results'),
    path('addArticle/', views.article_edit_view, name='article_add'),
    path('articleNameList/', views.article_name_list_view, name='articleNameList'),
    path('workshop/<slug:name>/', views.legacy_workshop_redirect_view),
    path('qualProblems/<slug:name>/', views.legacy_qualification_problems_redirect_view),
    path('<int:year>/workshop/<slug:name>/', views.workshop_page_view, name='workshop_page'),
    path('<int:year>/workshop/<slug:name>/edit/', views.workshop_edit_view, name='workshop_edit'),
    path('<int:year>/workshop/<slug:name>/edit/upload/', views.workshop_edit_upload_file, name='workshop_edit_upload'),
    path('<int:year>/workshop/<slug:name>/participants/', views.workshop_participants_view, name='workshop_participants'),
    path('<int:year>/workshop/<slug:name>/qualProblems/', views.qualification_problems_view, name='qualification_problems'),
    path('<int:year>/workshop/<slug:name>/register/', views.register_to_workshop_view, name='register_to_workshop'),
    path('<int:year>/workshop/<slug:name>/unregister/', views.unregister_from_workshop_view, name='unregister_from_workshop'),
    path('<int:year>/workshop/<slug:name>/solution/', views.workshop_solution, name='workshop_my_solution'),
    path('<int:year>/workshop/<slug:name>/solution/file/<int:file_pk>/', views.workshop_solution_file, name='workshop_my_solution_file'),
    path('<int:year>/workshop/<slug:name>/solution/<int:solution_id>/', views.workshop_solution, name='workshop_solution'),
    path('<int:year>/workshop/<slug:name>/solution/<int:solution_id>/file/<int:file_pk>/', views.workshop_solution_file, name='workshop_solution_file'),
    path('savePoints/', views.save_points_view, name='save_points'),
    path('<int:year>/workshops/add/', views.workshop_edit_view, name='workshops_add'),
    path('<int:year>/workshops/', views.workshops_view, name='workshops'),
    path('<int:year>/dataForPlan/', views.data_for_plan_view, name='dataForPlan'),
    path('<int:year>/emails/', mail_views.filtered_emails_view, name='emails'),
    path('<int:year>/participants/', views.participants_view, name='participants'),
    path('<int:year>/lecturers/', views.lecturers_view, name='lecturers'),
    path('people/', views.participants_view, name='all_people'),
    path('template_for_workshop_page/', views.template_for_workshop_page_view, name='template_for_workshop_page'),
    path('program/', views.program_view, name='latest_program'),
    path('<int:year>/program/', views.program_view, name='program'),
    path('resource_auth/', views.resource_auth_view, name='resource_auth'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
