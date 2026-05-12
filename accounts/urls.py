from django.urls import path, re_path
from . import views

app_name = "accounts"

urlpatterns = [
    # Accept both with and without trailing slashes to match Azure redirect URIs exactly.
    re_path(r"^azure/login/?$", views.AzureLoginView.as_view(), name="azure_login"),
    re_path(r"^azure/callback/?$", views.AzureCallbackView.as_view(), name="azure_callback"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("invite/", views.InviteUserView.as_view(), name="invite"),
    path("settings/invite/", views.InviteSettingsView.as_view(), name="settings_invite"),
    path("settings/about/", views.AboutSettingsView.as_view(), name="settings_about"),
    path("settings/philosophy/", views.PhilosophySettingsView.as_view(), name="settings_philosophy"),
    path("settings/quotes/", views.QuotesSettingsView.as_view(), name="settings_quotes"),
    path("settings/hero/", views.HeroSettingsView.as_view(), name="settings_hero"),
    path("settings/contact/", views.ContactSettingsView.as_view(), name="settings_contact"),
    path("settings/offices/", views.OfficesSettingsView.as_view(), name="settings_offices"),
    path("settings/what-we-do/", views.WhatWeDoSettingsView.as_view(), name="settings_whatwedo"),
    path("settings/faq/", views.FAQSettingsView.as_view(), name="settings_faq"),
    path("settings/insurance/", views.InsuranceSettingsView.as_view(), name="settings_insurance"),
    path("settings/payment/", views.PaymentSettingsView.as_view(), name="settings_payment"),
    path("settings/areas-served/", views.AreasServedSettingsView.as_view(), name="settings_areas_served"),
    path("settings/social-posting/", views.SocialPostingSettingsView.as_view(), name="settings_social_posting"),
    path("settings/social-posting/test/", views.SocialPlatformTestView.as_view(), name="settings_social_posting_test"),
    path("settings/social-posting/preview/", views.SocialPreviewView.as_view(), name="settings_social_posting_preview"),
    path("settings/social-posting/send-test/", views.SocialSendTestPostView.as_view(), name="settings_social_posting_send_test"),
    path("settings/url-removal/", views.UrlRemovalView.as_view(), name="settings_url_removal"),
    path("settings/visitor-stats/active.json", views.ActiveSessionsApiView.as_view(), name="settings_visitor_active"),
    path(
        "settings/visitor-stats/active/<str:session_key>.json",
        views.ActiveSessionDetailApiView.as_view(),
        name="settings_visitor_active_detail",
    ),
    path(
        "settings/visitor-stats/location-sessions.json",
        views.LocationSessionsApiView.as_view(),
        name="settings_visitor_location_sessions",
    ),
    path("settings/visitor-stats/", views.VisitorStatsView.as_view(), name="settings_visitor_stats"),
    path("settings/published/", views.PublishedSettingsView.as_view(), name="settings_published"),
    path("services/", views.ManageServicesView.as_view(), name="services"),
    path("seo-settings/", views.ManageSEOSettingsView.as_view(), name="seo_settings"),
    path("therapists/", views.ManageTherapistsView.as_view(), name="therapists"),
    path("settings/", views.ManageTherapistsView.as_view(), name="settings"),
    path("therapists/<int:pk>/edit/", views.ManageTherapistProfileView.as_view(), name="therapist_edit"),
    path("therapists/license-types/", views.ManageLicenseTypesView.as_view(), name="license_types"),
    path("therapists/client-focuses/", views.ManageClientFocusesView.as_view(), name="client_focuses"),
    path("join-submissions/", views.ManageJoinSubmissionsView.as_view(), name="join_submissions"),
    path("activate/<str:token>/", views.ActivateView.as_view(), name="activate"),
]
