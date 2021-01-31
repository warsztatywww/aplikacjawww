from cms.sitemaps import CMSSitemap
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import logout_then_login
from django.contrib.sitemaps.views import sitemap
from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import include, path
from django.views.generic import RedirectView

import wwwapp.urls
from aplikacjawww_djangocms import auth, views

admin.autodiscover()

urlpatterns = [
    path("sitemap.xml", sitemap, {"sitemaps": {"cmspages": CMSSitemap}}),
    path(
        'favicon.ico',
        RedirectView.as_view(
            url=staticfiles_storage.url('images/favicon.ico'),
            permanent=False),
        name="favicon"
    ),
    path('tinymce/', include('tinymce.urls')),
    path('gallery/', include('gallery.urls')),
    path('admin/', admin.site.urls),
    path('accounts/logout/', logout_then_login, name='logout'),
    path('accounts/login/', auth.login_view, name='login'),
    path('accounts/', include('social_django.urls', namespace='social')),
    path('accounts/verified/', auth.finish_merge_verification, name='finish_merge_verification')
]
urlpatterns += wwwapp.urls.urlpatterns
urlpatterns += [
    path('article/<slug:name>/', views.legacy_article_url_redirect, name='article'),
    path('', include('cms.urls'))
]

# This is only needed when using runserver.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
