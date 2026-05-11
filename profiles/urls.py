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
    # Hierarchy: state / county-or-city / city-under-county
    path(
        "therapists/<slug:therapist_slug>/<slug:state_slug>/",
        views.therapist_area_page,
        name="therapist_state",
    ),
    path(
        "therapists/<slug:therapist_slug>/<slug:state_slug>/<slug:location_slug>/",
        views.therapist_area_page,
        name="therapist_area",
    ),
    path(
        "therapists/<slug:therapist_slug>/<slug:state_slug>/<slug:county_slug>/<slug:city_slug>/",
        views.therapist_city_page,
        name="therapist_city",
    ),
    # Legacy "in" URLs → 301 redirects
    path(
        "therapists/<slug:therapist_slug>/in/<slug:state_slug>/",
        views.therapist_in_redirect,
        name="therapist_state_old",
    ),
    path(
        "therapists/<slug:therapist_slug>/in/<slug:state_slug>/<slug:location_slug>/",
        views.therapist_in_redirect,
        name="therapist_area_old",
    ),
    re_path(r"^therapists/photo-proxy/?$", views.photo_proxy, name="photo_proxy"),
]
