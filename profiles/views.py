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
from core.models import OfficeLocation
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
    offices = (
        OfficeLocation.objects
        .filter(therapists=profile, is_active=True)
        .order_by("order", "name")
    )
    return render(request, "profiles/profile_detail.html", {
        "profile": profile,
        "offices": offices,
    })


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


def _build_scoped_sections(locations, therapist_slug, current_location, current_state):
    """
    Build location sections scoped to the current page area:
      - county_cities: other cities in same county (city page) / cities in county (county page)
      - sibling_counties: other county-level entries in the same state
      - other_states: other states the therapist serves
    """
    from collections import OrderedDict
    from geo.models import GeoLocation

    all_locs = list(
        locations.select_related("state", "county")
        .order_by("state__name", "county__name", "name")
    )

    current_county_id = None
    if current_location:
        if current_location.location_type == GeoLocation.CITY and current_location.county_id:
            current_county_id = current_location.county_id
        elif current_location.location_type == GeoLocation.COUNTY:
            current_county_id = current_location.id

    county_cities: list = []
    sibling_counties: OrderedDict = OrderedDict()
    other_states: OrderedDict = OrderedDict()

    for loc in all_locs:
        is_current = current_location is not None and loc.pk == current_location.pk
        if is_current:
            continue

        if loc.state_id == current_state.id:
            if current_county_id and loc.location_type == GeoLocation.CITY and loc.county_id == current_county_id:
                url = f"/therapists/{therapist_slug}/{loc.state.slug}/{loc.county.slug}/{loc.slug}/"
                county_cities.append({"loc": loc, "url": url})
            elif loc.location_type == GeoLocation.COUNTY:
                if loc.id not in sibling_counties:
                    sibling_counties[loc.id] = {
                        "loc": loc,
                        "url": f"/therapists/{therapist_slug}/{loc.state.slug}/{loc.slug}/",
                    }
            elif loc.location_type == GeoLocation.CITY and loc.county_id and loc.county_id != current_county_id:
                # City in a different county — represent via its county
                cid = loc.county_id
                if cid not in sibling_counties:
                    sibling_counties[cid] = {
                        "loc": loc.county,
                        "url": f"/therapists/{therapist_slug}/{loc.state.slug}/{loc.county.slug}/",
                    }
            elif loc.location_type == GeoLocation.CITY and not loc.county_id:
                key = f"city_{loc.id}"
                if key not in sibling_counties:
                    sibling_counties[key] = {
                        "loc": loc,
                        "url": f"/therapists/{therapist_slug}/{loc.state.slug}/{loc.slug}/",
                    }
        else:
            if loc.state_id not in other_states:
                other_states[loc.state_id] = {
                    "state": loc.state,
                    "url": f"/therapists/{therapist_slug}/{loc.state.slug}/",
                }

    return {
        "county_cities": county_cities,
        "sibling_counties": list(sibling_counties.values()),
        "other_states": list(other_states.values()),
    }


def _build_location_hierarchy(locations, therapist_slug, current_location=None):
    """
    Organise a GeoLocation queryset into a hierarchy for template display:
    [{state, county_groups: [{county, cities: [{loc, is_current, url}]}],
      standalone: [{loc, is_current, url}]}]
    """
    from collections import OrderedDict
    from geo.models import GeoLocation
    state_map = OrderedDict()
    for loc in locations.select_related("state", "county").order_by("state__name", "county__name", "name"):
        sid = loc.state_id
        if sid not in state_map:
            state_map[sid] = {"state": loc.state, "county_map": OrderedDict(), "standalone": []}
        is_current = current_location is not None and loc.pk == current_location.pk
        if loc.location_type == GeoLocation.CITY and loc.county_id:
            url = f"/therapists/{therapist_slug}/{loc.state.slug}/{loc.county.slug}/{loc.slug}/"
            cid = loc.county_id
            if cid not in state_map[sid]["county_map"]:
                state_map[sid]["county_map"][cid] = {"county": loc.county, "cities": []}
            state_map[sid]["county_map"][cid]["cities"].append({"loc": loc, "is_current": is_current, "url": url})
        else:
            url = f"/therapists/{therapist_slug}/{loc.state.slug}/{loc.slug}/"
            state_map[sid]["standalone"].append({"loc": loc, "is_current": is_current, "url": url})
    return [
        {"state": sg["state"], "county_groups": list(sg["county_map"].values()), "standalone": sg["standalone"]}
        for sg in state_map.values()
    ]


def therapist_area_page(
    request: HttpRequest,
    therapist_slug: str,
    state_slug: str,
    location_slug: str = "",
) -> HttpResponse:
    """
    Intersectional page: a specific therapist serving a state or county/standalone-city.
    URLs:
      /therapists/<therapist_slug>/<state_slug>/
      /therapists/<therapist_slug>/<state_slug>/<location_slug>/
    Cities that belong to a county redirect to the 4-segment canonical URL.
    """
    from geo.models import GeoState, GeoLocation
    from geo.utils.availability import get_locations_for_therapist

    profile = get_object_or_404(TherapistProfile, slug=therapist_slug, is_published=True)

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        from django.http import Http404
        raise Http404

    location = None
    if location_slug:
        try:
            location = GeoLocation.objects.select_related("county").get(
                state=state, slug=location_slug, is_active=True
            )
        except GeoLocation.DoesNotExist:
            from django.http import Http404
            raise Http404

        # Redirect city-under-county to canonical 4-segment URL
        if location.location_type == GeoLocation.CITY and location.county_id:
            from django.shortcuts import redirect
            return redirect(
                f"/therapists/{therapist_slug}/{state_slug}/{location.county.slug}/{location_slug}/",
                permanent=True,
            )

    therapist_locations = get_locations_for_therapist(profile)

    if location:
        if location.location_type == GeoLocation.COUNTY:
            from django.db.models import Q
            in_area = therapist_locations.filter(
                Q(pk=location.pk) | Q(county=location)
            ).exists()
        else:
            in_area = therapist_locations.filter(pk=location.pk).exists()
    else:
        in_area = therapist_locations.filter(state=state).exists()

    if not in_area:
        from django.http import Http404
        raise Http404

    all_services = profile.services.all()
    offices = OfficeLocation.objects.filter(therapists=profile, is_active=True).order_by("order", "name")
    area_name = (
        f"{location.name}, {state.abbreviation}" if location else state.name
    )

    return render(request, "profiles/therapist_area.html", {
        "profile": profile,
        "state": state,
        "location": location,
        "area_name": area_name,
        "all_services": all_services,
        "offices": offices,
        "therapist_locations": therapist_locations,
        "location_groups": _build_location_hierarchy(therapist_locations, profile.slug, location),
        "scoped_sections": _build_scoped_sections(therapist_locations, profile.slug, location, state),
        "seo_title": f"{profile.display_name} | Therapist in {area_name}",
        "seo_description": (
            f"{profile.display_name} offers therapy services in {area_name} "
            f"at L+C Psychological Services. Schedule an appointment today."
        ),
    })


def therapist_city_page(
    request: HttpRequest,
    therapist_slug: str,
    state_slug: str,
    county_slug: str,
    city_slug: str,
) -> HttpResponse:
    """
    Intersectional page: a specific therapist serving a city nested under a county.
    URL: /therapists/<therapist_slug>/<state_slug>/<county_slug>/<city_slug>/
    """
    from geo.models import GeoState, GeoLocation
    from geo.utils.availability import get_locations_for_therapist

    profile = get_object_or_404(TherapistProfile, slug=therapist_slug, is_published=True)

    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
    except GeoState.DoesNotExist:
        from django.http import Http404
        raise Http404

    try:
        county = GeoLocation.objects.get(
            state=state, slug=county_slug, location_type=GeoLocation.COUNTY, is_active=True
        )
    except GeoLocation.DoesNotExist:
        from django.http import Http404
        raise Http404

    try:
        location = GeoLocation.objects.select_related("county").get(
            state=state, slug=city_slug, county=county, is_active=True
        )
    except GeoLocation.DoesNotExist:
        from django.http import Http404
        raise Http404

    therapist_locations = get_locations_for_therapist(profile)
    if not therapist_locations.filter(pk=location.pk).exists():
        from django.http import Http404
        raise Http404

    all_services = profile.services.all()
    offices = OfficeLocation.objects.filter(therapists=profile, is_active=True).order_by("order", "name")
    area_name = f"{location.name}, {state.abbreviation}"

    return render(request, "profiles/therapist_area.html", {
        "profile": profile,
        "state": state,
        "location": location,
        "area_name": area_name,
        "all_services": all_services,
        "offices": offices,
        "therapist_locations": therapist_locations,
        "location_groups": _build_location_hierarchy(therapist_locations, profile.slug, location),
        "scoped_sections": _build_scoped_sections(therapist_locations, profile.slug, location, state),
        "seo_title": f"{profile.display_name} | Therapist in {area_name}",
        "seo_description": (
            f"{profile.display_name} offers therapy services in {area_name} "
            f"at L+C Psychological Services. Schedule an appointment today."
        ),
    })


def therapist_in_redirect(
    request: HttpRequest,
    therapist_slug: str,
    state_slug: str,
    location_slug: str = "",
) -> HttpResponse:
    """
    301 redirect from legacy /therapists/<slug>/in/<state>/[<loc>/] URLs
    to the new hierarchy URLs without "in".
    """
    from django.shortcuts import redirect
    from geo.models import GeoState, GeoLocation

    if not location_slug:
        return redirect(f"/therapists/{therapist_slug}/{state_slug}/", permanent=True)

    # Try to resolve whether this location is a city under a county
    try:
        state = GeoState.objects.get(slug=state_slug, is_active=True)
        location = GeoLocation.objects.select_related("county").get(
            state=state, slug=location_slug, is_active=True
        )
        if location.location_type == GeoLocation.CITY and location.county_id:
            return redirect(
                f"/therapists/{therapist_slug}/{state_slug}/{location.county.slug}/{location_slug}/",
                permanent=True,
            )
    except (GeoState.DoesNotExist, GeoLocation.DoesNotExist):
        pass

    return redirect(
        f"/therapists/{therapist_slug}/{state_slug}/{location_slug}/",
        permanent=True,
    )


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
