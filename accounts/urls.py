from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("invite/", views.InviteUserView.as_view(), name="invite"),
    path("services/", views.ManageServicesView.as_view(), name="services"),
    path("therapists/", views.ManageTherapistsView.as_view(), name="therapists"),
    path("therapists/<int:pk>/edit/", views.ManageTherapistProfileView.as_view(), name="therapist_edit"),
    path("therapists/license-types/", views.ManageLicenseTypesView.as_view(), name="license_types"),
    path("therapists/client-focuses/", views.ManageClientFocusesView.as_view(), name="client_focuses"),
    path("activate/<str:token>/", views.ActivateView.as_view(), name="activate"),
]
