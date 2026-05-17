"""
seo_intel/views/condition_coverage.py
---------------------------------------
SEO Intelligence coverage dashboard for Conditions.

Same architecture as modality_coverage.py but for Condition objects.
"""
from __future__ import annotations

from functools import wraps

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render


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
def condition_coverage(request):
    """Render the condition coverage dashboard."""
    from core.models import Condition, OfficeLocation

    conditions = list(Condition.objects.order_by("name").prefetch_related(
        "offices",
        "offices__geo_states",
        "offices__geo_locations",
        "offices__therapists",
    ))

    rows = []
    for cond in conditions:
        offices_qs = cond.offices.filter(is_active=True)
        office_count = offices_qs.count()

        state_set = set()
        for office in offices_qs.prefetch_related("geo_states", "geo_locations__state"):
            for gs in office.geo_states.all():
                state_set.add(gs.name)
            for gl in office.geo_locations.all():
                if gl.state:
                    state_set.add(gl.state.name)

        therapist_ids = set()
        for office in offices_qs.prefetch_related("therapists"):
            therapist_ids.update(office.therapists.values_list("pk", flat=True))

        rows.append({
            "condition": cond,
            "office_count": office_count,
            "offices": list(offices_qs.values("name", "slug")),
            "states": sorted(state_set),
            "therapist_count": len(therapist_ids),
            "has_coverage": office_count > 0,
        })

    total = len(rows)
    covered = sum(1 for r in rows if r["has_coverage"])
    missing = total - covered

    return render(request, "seo_intel/condition_coverage.html", {
        "rows": rows,
        "total": total,
        "covered": covered,
        "missing": missing,
        "active_page": "condition_coverage",
    })
