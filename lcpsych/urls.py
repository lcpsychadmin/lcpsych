"""
URL configuration for lcpsych project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from django.views.static import serve
from core.sitemaps import StaticViewSitemap, PageSitemap, PostSitemap
from core import views as core_views
from accounts.views import ManageTherapistsView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ckeditor/', include('ckeditor_uploader.urls')),
    path('tinymce/', include('tinymce.urls')),
    path('accounts/', include('accounts.urls')),
    path('blog/', include('blog.urls')),
    path('settings/', ManageTherapistsView.as_view(), name='settings'),
    path('sitemap.xml', sitemap, {
        'sitemaps': {
            'static': StaticViewSitemap,
            'pages': PageSitemap,
            'posts': PostSitemap,
        }
    }, name='django.contrib.sitemaps.views.sitemap'),
    path('location.xml', core_views.location_xml, name='location_xml'),
    path('robots.txt', TemplateView.as_view(
        template_name='robots.txt',
        content_type='text/plain'
    ), name='robots_txt'),
    # Place profiles before core to avoid being shadowed by core catch-all
    path('', include('profiles.urls')),
    path('', include('core.urls')),
]

# Serve media files locally whenever using the filesystem backend (helps when DEBUG=False locally)
_default_storage = settings.STORAGES.get('default', {}) if hasattr(settings, 'STORAGES') else {}
_is_fs_storage = _default_storage.get('BACKEND') == 'django.core.files.storage.FileSystemStorage'
if settings.DEBUG or _is_fs_storage:
    media_patterns = [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
    # Prepend to avoid being shadowed by catch-all routes in core.urls
    urlpatterns = media_patterns + urlpatterns
