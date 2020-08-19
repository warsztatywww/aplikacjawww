from django.urls import path, include
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import logout_then_login
from django.contrib.staticfiles.storage import staticfiles_storage
from django.views.generic import RedirectView, TemplateView
from django.conf import settings

from . import views, mail_views
from .auth import login_view, finish_merge_verification

urlpatterns = [
    path(
        'favicon.ico',
        RedirectView.as_view(
            url=staticfiles_storage.url('images/favicon.ico'),
            permanent=False),
        name="favicon"
    ),
    path('tinymce/', include('tinymce.urls')),
    path('logout/', logout_then_login, name='logout'),
    path('admin/', admin.site.urls),
    path('gallery/', include('gallery.urls')),
    path('login/', login_view, name='login'),
    path('accounts/', include('social_django.urls', namespace='social')),
    path('accounts/verified/', finish_merge_verification, name='finish_merge_verification'),
    path('profile/<int:user_id>/', views.profile_view, name='profile'),
    path('profile/', views.my_profile_edit_view, name='edit_my_profile'),
    path('article/<slug:name>/', views.article_view, name='article'),
    path('article/<slug:name>/edit/', views.article_edit_view, name='article_edit'),
    path('addArticle/', views.article_edit_view, name='article_add'),
    path('upload/<slug:type>/<slug:name>/', views.upload_file, name='upload'),
    path('articleNameList/', views.article_name_list_view, name='articleNameList'),
    path('workshop/<slug:name>/', views.workshop_page_view, name='workshop_page'),
    path('workshop/<slug:name>/priv/', views.workshop_proposal_view, name='workshop_proposal'),
    path('workshop/<slug:name>/edit/', views.workshop_page_edit_view, name='workshop_page_edit'),
    path('workshop/<slug:name>/participants/', views.workshop_participants_view, name='workshop_participants'),
    path('savePoints/', views.save_points_view, name='save_points'),
    path('register/', views.register_to_workshop_view, name='register_to_workshop'),
    path('unregister/', views.unregister_from_workshop_view, name='unregister_from_workshop'),
    path('qualProblems/<slug:workshop_name>/', views.qualification_problems_view, name='qualification_problems'),
    path('addWorkshop/', views.workshop_proposal_view, name='addWorkshop'),
    path('yourWorkshops/', views.your_workshops_view, name='yourWorkshops'),
    path('allWorkshops/', views.all_workshops_view, name='allWorkshops'),
    path('<int:year>/dataForPlan/', views.data_for_plan_view, name='dataForPlan'),
    path('<int:year>/participants/', views.participants_view, name='participants'),
    path('<int:year>/lecturers/', views.lecturers_view, name='lecturers'),
    path('people/', views.participants_view, name='all_people'),
    path('emails/', views.emails_view, name='emails'),
    path('filterEmails/', mail_views.filtered_emails_view, name='filter_emails'),
    path('filterEmails/<int:year>/<int:filter_id>/', mail_views.filtered_emails_view, name='filter_emails'),
    path('template_for_workshop_page/', views.template_for_workshop_page_view, name='template_for_workshop_page'),
    path('program/', views.program_view, name='latest_program'),
    path('<int:year>/program/', views.program_view, name='program'),
    path('resource_auth/', views.resource_auth_view, name='resource_auth'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('cloud/', views.cloud_access_view, name='cloud_access'),
    path('', views.index_view, name='index'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
