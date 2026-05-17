"""
seo_intel/views/settings_office_modalities.py
-----------------------------------------------
Assign/remove modalities per OfficeLocation.
Supports standard POST and HTMX inline toggling.
"""
from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse


def _staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.conf import settings as _s
            login_url = getattr(_s, "LOGIN_URL", "/accounts/login/")
            return redirect(f"{login_url}?{REDIRECT_FIELD_NAME}={request.path}")
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper


@_staff_required
def office_modalities(request):
    """
    List all active offices with their assigned modalities.
    Handles batch assignment via POST form submission.
    """
    from core.models import Modality, OfficeLocation

    offices = list(
        OfficeLocation.objects.filter(is_active=True)
        .prefetch_related("modalities")
        .order_by("order", "name")
    )
    all_modalities = list(Modality.objects.filter(active=True).order_by("name"))

    if request.method == "POST":
        office_pk = request.POST.get("office_pk")
        if office_pk:
            office = get_object_or_404(OfficeLocation, pk=office_pk)
            selected_ids = [int(x) for x in request.POST.getlist("modality_ids") if x.isdigit()]
            office.modalities.set(selected_ids)
            messages.success(request, f'Modalities updated for "{office.name}".')
        return redirect(reverse("seo_intel:settings_office_modalities"))

    return render(request, "seo_intel/settings/office_modalities.html", {
        "offices": offices,
        "all_modalities": all_modalities,
        "active_page": "settings_office_modalities",
    })


@_staff_required
def toggle_office_modality(request, office_pk, modality_pk):
    """
    HTMX endpoint: toggle a single modality on a single office.
    Returns a minimal HTML snippet with the new checkbox state.
    """
    from core.models import Modality, OfficeLocation

    if request.method != "POST":
        return HttpResponse(status=405)

    office = get_object_or_404(OfficeLocation, pk=office_pk)
    modality = get_object_or_404(Modality, pk=modality_pk)

    if office.modalities.filter(pk=modality_pk).exists():
        office.modalities.remove(modality)
        checked = False
    else:
        office.modalities.add(modality)
        checked = True

    checked_attr = 'checked' if checked else ''
    html = (
        f'<input type="checkbox" {checked_attr} '
        f'hx-post="{reverse("seo_intel:toggle_office_modality", args=[office_pk, modality_pk])}" '
        f'hx-swap="outerHTML" '
        f'title="Toggle {modality.name}" />'
    )
    return HttpResponse(html)
