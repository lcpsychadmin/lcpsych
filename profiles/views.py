from typing import cast
from urllib.parse import quote as urlquote, urlparse

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import AbstractUser
from django.core.mail import send_mail
from django.db.models import Q
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    StreamingHttpResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import EmailConfirmation
from .forms import TherapistProfileForm
from .models import TherapistProfile


raw_hosts = getattr(settings, "PROFILE_IMAGE_HOSTS", "")
ALLOWED_IMAGE_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()] or [
    getattr(settings, "PROFILE_IMAGE_HOST", "lc-psych.s3.amazonaws.com"),
]
ALLOWED_IMAGE_PREFIXES = (
    "therapists/photos/",
    "media/therapists/photos/",  # local dev MEDIA_URL paths
)


def is_therapist_or_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name__in=["therapist", "admin"]).exists()
    )


def profile_detail(request: HttpRequest, slug: str) -> HttpResponse:
    queryset = (
        TherapistProfile.objects.select_related("user", "license_type")
        .prefetch_related("client_focuses", "services")
    )

    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.groups.filter(name__in=["admin"]).exists():
            visibility_filter = Q()
        else:
            visibility_filter = Q(is_published=True) | Q(user=request.user)
    else:
        visibility_filter = Q(is_published=True)

    profile = get_object_or_404(queryset.filter(visibility_filter), slug=slug)
    return render(request, "profiles/profile_detail.html", {"profile": profile})


@login_required
@user_passes_test(is_therapist_or_admin)
def profile_edit(request: HttpRequest) -> HttpResponse:
    user = cast(AbstractUser, request.user)
    if not user.is_authenticated:
        return HttpResponseForbidden("auth required")

    debug_activation_url = request.GET.get("activation_url", "") if settings.DEBUG else ""
    debug_email = request.GET.get("email", "") if settings.DEBUG else ""
    profile, _ = TherapistProfile.objects.get_or_create(
        user=user,
        defaults={
            "first_name": user.first_name,
            "last_name": user.last_name,
            "accepts_new_clients": True,
        },
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reset_password":
            EmailConfirmation.objects.filter(user=user, used_at__isnull=True).delete()
            token = EmailConfirmation.generate_token()
            EmailConfirmation.objects.create(user=user, token=token)
            activate_path = reverse("accounts:activate", args=[token])
            base_url = getattr(settings, "BASE_URL", "").rstrip("/")
            activate_url = f"{base_url}{activate_path}" if base_url else request.build_absolute_uri(activate_path)

            site_name = getattr(settings, "SITE_NAME", "L+C Psychological Services")
            subject = f"Reset your {site_name} password"
            greeting = user.get_full_name() or user.email or "there"
            body = (
                f"Hi {greeting},\n\n"
                f"Use this link to set a new password for your {site_name} account:\n{activate_url}\n\n"
                "If you did not request this reset, you can ignore this email."
            )

            try:
                send_mail(
                    subject,
                    body,
                    getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    [user.email],
                    fail_silently=False,
                )
                messages.success(request, f"Password reset link sent to {user.email}.")
            except Exception:
                if not settings.DEBUG:
                    raise
                messages.success(request, f"Password reset link ready for {user.email}.")

            redirect_url = reverse("profiles:profile_edit")
            if settings.DEBUG:
                redirect_url = f"{redirect_url}?activation_url={urlquote(activate_url)}&email={urlquote(user.email)}"
            return redirect(redirect_url)

        form = TherapistProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = user
            profile.save()
            form.save_m2m()
            return redirect("profiles:profile_detail", slug=profile.slug)
    else:
        form = TherapistProfileForm(instance=profile)

    return render(
        request,
        "profiles/profile_edit.html",
        {
            "form": form,
            "profile": profile,
            "debug_activation_url": debug_activation_url,
            "debug_email": debug_email,
        },
    )


def profiles_list(request: HttpRequest) -> HttpResponse:
    profiles = (
        TherapistProfile.objects.filter(is_published=True)
        .select_related("license_type", "user")
        .prefetch_related("client_focuses", "services", "top_services")
    )

    query = (request.GET.get("q") or "").strip()
    if query:
        profiles = profiles.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(license_type__name__icontains=query)
            | Q(services__title__icontains=query)
            | Q(client_focuses__name__icontains=query)
        )

    new_only = request.GET.get("new") == "1"
    if new_only:
        profiles = profiles.filter(accepts_new_clients=True)

    profiles = profiles.distinct()

    return render(
        request,
        "profiles/profile_list.html",
        {
            "profiles": profiles,
            "query": query,
            "new_only": new_only,
        },
    )


@login_required
@user_passes_test(is_therapist_or_admin)
def photo_proxy(request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
    image_url = request.GET.get("url", "")
    if not image_url:
        return HttpResponseBadRequest("url required")

    parsed = urlparse(image_url)
    if not parsed.netloc and image_url.startswith("/"):
        # Allow relative media URLs from the same host (e.g., /media/therapists/...)
        image_url = request.build_absolute_uri(image_url)
        parsed = urlparse(image_url)
    request_host = (request.get_host() or "").lower()
    allowed_hosts = {h.lower() for h in ALLOWED_IMAGE_HOSTS}
    if request_host:
        allowed_hosts.add(request_host)

    if parsed.netloc.lower() not in allowed_hosts:
        return HttpResponseForbidden("host not allowed")

    path = parsed.path.lstrip("/")
    if not any(path.startswith(prefix) for prefix in ALLOWED_IMAGE_PREFIXES):
        return HttpResponseForbidden("path not allowed")

    try:
        upstream = requests.get(image_url, stream=True, timeout=10)
    except requests.RequestException:
        return HttpResponse("fetch failed", status=502)

    if upstream.status_code != 200:
        return HttpResponse("fetch failed", status=502)

    content_type = upstream.headers.get("Content-Type", "image/jpeg")
    resp = StreamingHttpResponse(upstream.iter_content(65536), content_type=content_type, status=200)
    resp["Access-Control-Allow-Origin"] = request.headers.get("Origin") or "*"
    resp["Vary"] = "Origin"
    resp["Cache-Control"] = "public, max-age=300"

    content_length = upstream.headers.get("Content-Length")
    if content_length:
        resp["Content-Length"] = content_length

    return resp
