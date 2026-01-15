from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import TherapistProfileForm
from .models import TherapistProfile


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
    profile, _ = TherapistProfile.objects.get_or_create(
        user=request.user,
        defaults={
            "first_name": request.user.first_name,
            "last_name": request.user.last_name,
            "accepts_new_clients": True,
        },
    )

    if request.method == "POST":
        form = TherapistProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            form.save_m2m()
            return redirect("profiles:profile_detail", slug=profile.slug)
    else:
        form = TherapistProfileForm(instance=profile)

    return render(request, "profiles/profile_edit.html", {"form": form, "profile": profile})


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
