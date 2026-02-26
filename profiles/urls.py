from django.urls import path, re_path
from django.views.generic import RedirectView
from . import views

app_name = "profiles"

urlpatterns = [
    path("profiles/", RedirectView.as_view(pattern_name="profiles:profile_list", permanent=True)),
    path("profiles/<slug:slug>/", RedirectView.as_view(pattern_name="profiles:profile_detail", permanent=True)),
    path("therapists/", views.profiles_list, name="profile_list"),
    path("therapists/edit/", views.profile_edit, name="profile_edit"),
    path("therapists/<slug:slug>/", views.profile_detail, name="profile_detail"),
    re_path(r"^therapists/photo-proxy/?$", views.photo_proxy, name="photo_proxy"),
]
