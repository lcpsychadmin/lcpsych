"""
seo_intel/views/settings_modalities.py
----------------------------------------
CRUD management for Modality objects.

Provides list, add, edit, delete, and toggle-active endpoints, all
restricted to staff/superuser via the _staff_required decorator.
"""
from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import slugify


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
def manage_modalities(request):
    """List all modalities; handle add via POST."""
    from core.models import Modality

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "add":
            name = request.POST.get("name", "").strip()[:200]
            slug = request.POST.get("slug", "").strip()[:200] or slugify(name)[:200]
            description = request.POST.get("description", "").strip()
            icon = request.POST.get("icon", "").strip()[:100]
            if name:
                obj, created = Modality.objects.get_or_create(
                    slug=slug,
                    defaults={"name": name, "description": description, "icon": icon, "active": True},
                )
                if created:
                    messages.success(request, f'Modality "{obj.name}" added.')
                else:
                    messages.info(request, f'Slug "{slug}" already exists.')
            else:
                messages.error(request, "Name is required.")
        return redirect(reverse("seo_intel:settings_modalities"))

    modalities = list(Modality.objects.order_by("name"))
    return render(request, "seo_intel/settings/modalities.html", {
        "modalities": modalities,
        "active_page": "settings_modalities",
    })


@_staff_required
def edit_modality(request, pk):
    """Edit an existing modality, including its content blocks and office assignments."""
    from core.models import Modality, OfficeLocation
    from accounts.forms import ModalityContentBlockFormSet

    obj = get_object_or_404(Modality, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "add_office":
            office_pk = request.POST.get("office_pk")
            office = get_object_or_404(OfficeLocation, pk=office_pk)
            office.modalities.add(obj)
            messages.success(request, f'"{office.name}" added.')
            return redirect(reverse("seo_intel:edit_modality", args=[pk]))

        if action == "remove_office":
            office_pk = request.POST.get("office_pk")
            office = get_object_or_404(OfficeLocation, pk=office_pk)
            office.modalities.remove(obj)
            messages.success(request, f'"{office.name}" removed.')
            return redirect(reverse("seo_intel:edit_modality", args=[pk]))

        # Default: save core fields + content blocks
        obj.name = request.POST.get("name", obj.name).strip()[:200]
        slug_val = request.POST.get("slug", "").strip()[:200]
        obj.slug = slug_val or slugify(obj.name)[:200]
        obj.description = request.POST.get("description", "").strip()
        obj.icon = request.POST.get("icon", "").strip()[:100]
        if "featured_image" in request.FILES:
            obj.featured_image = request.FILES["featured_image"]
        elif request.POST.get("featured_image_clear"):
            obj.featured_image = None
        obj.save()

        formset = ModalityContentBlockFormSet(request.POST, instance=obj)
        if formset.is_valid():
            formset.save()
        else:
            assigned_offices = list(obj.offices.order_by("name"))
            assigned_ids = {o.pk for o in assigned_offices}
            unassigned_offices = list(OfficeLocation.objects.filter(is_active=True).exclude(pk__in=assigned_ids).order_by("name"))
            messages.error(request, "Some content blocks had errors and were not saved.")
            return render(request, "seo_intel/settings/modality_edit.html", {
                "obj": obj,
                "block_formset": formset,
                "assigned_offices": assigned_offices,
                "unassigned_offices": unassigned_offices,
                "active_page": "settings_modalities",
            })

        messages.success(request, f'Modality "{obj.name}" updated.')
        return redirect(reverse("seo_intel:edit_modality", args=[pk]))

    formset = ModalityContentBlockFormSet(instance=obj)
    assigned_offices = list(obj.offices.order_by("name"))
    assigned_ids = {o.pk for o in assigned_offices}
    unassigned_offices = list(OfficeLocation.objects.filter(is_active=True).exclude(pk__in=assigned_ids).order_by("name"))
    return render(request, "seo_intel/settings/modality_edit.html", {
        "obj": obj,
        "block_formset": formset,
        "assigned_offices": assigned_offices,
        "unassigned_offices": unassigned_offices,
        "active_page": "settings_modalities",
    })


@_staff_required
def toggle_modality(request, pk):
    """Toggle a modality's active state (POST only)."""
    from core.models import Modality

    if request.method != "POST":
        return redirect(reverse("seo_intel:settings_modalities"))

    obj = get_object_or_404(Modality, pk=pk)
    obj.active = not obj.active
    obj.save()
    status = "activated" if obj.active else "deactivated"
    messages.success(request, f'Modality "{obj.name}" {status}.')
    return redirect(reverse("seo_intel:settings_modalities"))


@_staff_required
def delete_modality(request, pk):
    """Delete a modality (POST only)."""
    from core.models import Modality

    if request.method != "POST":
        return redirect(reverse("seo_intel:settings_modalities"))

    obj = get_object_or_404(Modality, pk=pk)
    name = obj.name
    obj.delete()
    messages.success(request, f'Modality "{name}" deleted.')
    return redirect(reverse("seo_intel:settings_modalities"))
