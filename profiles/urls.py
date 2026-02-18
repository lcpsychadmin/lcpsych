from django.urls import path, re_path
from . import views

app_name = "profiles"

urlpatterns = [
    path("therapists/", views.profiles_list, name="profile_list"),
    path("therapists/edit/", views.profile_edit, name="profile_edit"),
    path("therapists/<slug:slug>/", views.profile_detail, name="profile_detail"),
    re_path(r"^therapists/photo-proxy/?$", views.photo_proxy, name="photo_proxy"),
]
