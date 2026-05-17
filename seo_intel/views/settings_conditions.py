"""
seo_intel/views/settings_conditions.py
----------------------------------------
CRUD management for Condition objects.
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
def manage_conditions(request):
    """List all conditions; handle add via POST."""
    from core.models import Condition

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "add":
            name = request.POST.get("name", "").strip()[:200]
            slug = request.POST.get("slug", "").strip()[:200] or slugify(name)[:200]
            description = request.POST.get("description", "").strip()
            icon = request.POST.get("icon", "").strip()[:100]
            if name:
                obj, created = Condition.objects.get_or_create(
                    slug=slug,
                    defaults={"name": name, "description": description, "icon": icon, "active": True},
                )
                if created:
                    messages.success(request, f'Condition "{obj.name}" added.')
                else:
                    messages.info(request, f'Slug "{slug}" already exists.')
            else:
                messages.error(request, "Name is required.")
        return redirect(reverse("seo_intel:settings_conditions"))

    conditions = list(Condition.objects.order_by("name"))
    return render(request, "seo_intel/settings/conditions.html", {
        "conditions": conditions,
        "active_page": "settings_conditions",
    })


@_staff_required
def edit_condition(request, pk):
    """Edit an existing condition, including its content blocks and office assignments."""
    from core.models import Condition, OfficeLocation
    from accounts.forms import ConditionContentBlockFormSet

    obj = get_object_or_404(Condition, pk=pk)

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "add_office":
            office_pk = request.POST.get("office_pk")
            office = get_object_or_404(OfficeLocation, pk=office_pk)
            office.conditions.add(obj)
            messages.success(request, f'"{office.name}" added.')
            return redirect(reverse("seo_intel:edit_condition", args=[pk]))

        if action == "remove_office":
            office_pk = request.POST.get("office_pk")
            office = get_object_or_404(OfficeLocation, pk=office_pk)
            office.conditions.remove(obj)
            messages.success(request, f'"{office.name}" removed.')
            return redirect(reverse("seo_intel:edit_condition", args=[pk]))

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

        formset = ConditionContentBlockFormSet(request.POST, instance=obj)
        if formset.is_valid():
            formset.save()
        else:
            assigned_offices = list(obj.offices.order_by("name"))
            assigned_ids = {o.pk for o in assigned_offices}
            unassigned_offices = list(OfficeLocation.objects.filter(is_active=True).exclude(pk__in=assigned_ids).order_by("name"))
            messages.error(request, "Some content blocks had errors and were not saved.")
            return render(request, "seo_intel/settings/condition_edit.html", {
                "obj": obj,
                "block_formset": formset,
                "assigned_offices": assigned_offices,
                "unassigned_offices": unassigned_offices,
                "active_page": "settings_conditions",
            })

        messages.success(request, f'Condition "{obj.name}" updated.')
        return redirect(reverse("seo_intel:edit_condition", args=[pk]))

    formset = ConditionContentBlockFormSet(instance=obj)
    assigned_offices = list(obj.offices.order_by("name"))
    assigned_ids = {o.pk for o in assigned_offices}
    unassigned_offices = list(OfficeLocation.objects.filter(is_active=True).exclude(pk__in=assigned_ids).order_by("name"))
    return render(request, "seo_intel/settings/condition_edit.html", {
        "obj": obj,
        "block_formset": formset,
        "assigned_offices": assigned_offices,
        "unassigned_offices": unassigned_offices,
        "active_page": "settings_conditions",
    })


@_staff_required
def toggle_condition(request, pk):
    """Toggle a condition's active state (POST only)."""
    from core.models import Condition

    if request.method != "POST":
        return redirect(reverse("seo_intel:settings_conditions"))

    obj = get_object_or_404(Condition, pk=pk)
    obj.active = not obj.active
    obj.save()
    status = "activated" if obj.active else "deactivated"
    messages.success(request, f'Condition "{obj.name}" {status}.')
    return redirect(reverse("seo_intel:settings_conditions"))


@_staff_required
def delete_condition(request, pk):
    """Delete a condition (POST only)."""
    from core.models import Condition

    if request.method != "POST":
        return redirect(reverse("seo_intel:settings_conditions"))

    obj = get_object_or_404(Condition, pk=pk)
    name = obj.name
    obj.delete()
    messages.success(request, f'Condition "{name}" deleted.')
    return redirect(reverse("seo_intel:settings_conditions"))
