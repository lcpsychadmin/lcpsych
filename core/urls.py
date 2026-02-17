from django.urls import path, re_path
from . import views
from .feeds import LatestPostsFeed

urlpatterns = [
    path('', views.home, name='home'),
    path('_preview/', views.import_preview, name='import_preview'),
    path('blog/', views.post_list, name='post_list'),
    path('blog/feed/', LatestPostsFeed(), name='post_feed'),
    path('blog/<slug:slug>/', views.post_detail, name='post_detail'),
    path('search/', views.search, name='search'),
    path('our-team/', views.our_team, name='our_team'),
    path('about-us/', views.about_us, name='about_us'),
    path('insurance/', views.insurance, name='insurance'),
    path('contact-us/', views.contact_us, name='contact_us'),
    path('faq/', views.faq, name='faq'),
    path('join-our-team/', views.join_our_team, name='join_our_team'),
    path('services/<slug:slug>/', views.service_detail, name='service_detail'),
    # Local stubs for WordPress endpoints referenced by copied scripts
    path('__stub/wp-admin/admin-ajax.php', views.wp_admin_ajax_stub, name='wp_admin_ajax_stub'),
    path('__stub/wp-json/', views.wp_json_stub, name='wp_json_root_stub'),
    re_path(r'^__stub/wp-json/.*$', views.wp_json_stub, name='wp_json_stub'),
    # Absorb Cloudflare RUM beacons without CSRF
    path('cdn-cgi/rum', views.cloudflare_rum, name='cloudflare_rum'),
    # Stub Cloudflare email decode script to avoid 404s from copied markup
    re_path(r'^cdn-cgi/scripts/.+/cloudflare-static/email-decode\.min\.js$',
            views.cloudflare_email_decode_js,
            name='cloudflare_email_decode_js'),
    # Catch-all for imported pages (with or without trailing slash)
    re_path(r'^(?P<path>.+)/?$', views.page_detail, name='page_detail'),
]
