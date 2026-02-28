import logging
from datetime import date, datetime, time, timedelta
from typing import Any, cast
from urllib.parse import quote as urlquote
from zoneinfo import ZoneInfo

import msal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group, User
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.mail import send_mail
from django.core.cache import cache
from django.db.models import Avg, Case, Count, FloatField, Q, Value, CharField, When
from django.db.models.functions import Cast, Concat, TruncDate, ExtractWeekDay
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .forms import (
    ActivationSetPasswordForm,
    LoginForm,
    InviteUserForm,
    ServiceForm,
    PaymentFeeRowForm,
    InsuranceProviderForm,
    InsuranceExclusionForm,
    FAQItemForm,
    WhatWeDoItemForm,
    WhatWeDoSectionForm,
    AboutSectionForm,
    OurPhilosophyForm,
    InspirationalQuoteForm,
    CompanyQuoteForm,
    ContactInfoForm,
    StaticPageSEOForm,
    SocialProfileForm,
)
from .models import EmailConfirmation
from core.models import (
    Service,
    PaymentFeeRow,
    InsuranceProvider,
    InsuranceExclusion,
    FAQItem,
    WhatWeDoItem,
    WhatWeDoSection,
    AboutSection,
    OurPhilosophy,
    InspirationalQuote,
    CompanyQuote,
    ContactInfo,
    StaticPageSEO,
    JoinOurTeamSubmission,
    SocialProfile,
    SocialPlatform,
    AnalyticsEvent,
    AnalyticsEventType,
    Page,
)
from profiles.forms import AdminTherapistProfileForm, ClientFocusForm, LicenseTypeForm
from profiles.models import ClientFocus, LicenseType, TherapistProfile
from blog.models import Post


logger = logging.getLogger(__name__)


def is_admin(user: Any) -> bool:
    # Accept Any to handle request.user typing from auth backends.
    return bool(getattr(user, "is_superuser", False) or getattr(user, "groups", None) and user.groups.filter(name="admin").exists())


def is_office_manager(user: Any) -> bool:
    return bool(getattr(user, "groups", None) and user.groups.filter(name="office_manager").exists())


def _create_user_invitation(
    email: str,
    is_admin_flag: bool,
    is_therapist_flag: bool,
    is_office_manager_flag: bool,
) -> tuple[User, TherapistProfile | None, str]:
    normalized_email = email.lower()
    user, _ = User.objects.get_or_create(
        username=normalized_email,
        defaults={"email": normalized_email, "is_active": True},
    )
    user.email = normalized_email
    if not user.is_active:
        user.is_active = True
    user.save()

    admin_group, _ = Group.objects.get_or_create(name="admin")
    therapist_group, _ = Group.objects.get_or_create(name="therapist")
    office_manager_group, _ = Group.objects.get_or_create(name="office_manager")
    if is_admin_flag:
        user.groups.add(admin_group)
    if is_therapist_flag:
        user.groups.add(therapist_group)
    if is_office_manager_flag:
        user.groups.add(office_manager_group)

    therapist_profile = None
    if is_therapist_flag:
        therapist_profile, _ = TherapistProfile.objects.get_or_create(user=user)

    EmailConfirmation.objects.filter(user=user, used_at__isnull=True).delete()
    token = EmailConfirmation.generate_token()
    EmailConfirmation.objects.create(user=user, token=token)
    return user, therapist_profile, token


def _activation_url(request: HttpRequest, token: str) -> str:
    activate_path = reverse("accounts:activate", args=[token])
    base_url = getattr(settings, "BASE_URL", "").rstrip("/")
    if base_url:
        return f"{base_url}{activate_path}"
    return request.build_absolute_uri(activate_path)


def _login_url(request: HttpRequest) -> str:
    # Always point emails at the standard login page; it links to Azure SSO as needed.
    login_path = reverse("accounts:login")
    base_url = getattr(settings, "BASE_URL", "").rstrip("/")
    if base_url:
        return f"{base_url}{login_path}"
    return request.build_absolute_uri(login_path)


class InviteUserView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return is_admin(self.request.user)

    def get(self, request: HttpRequest) -> HttpResponse:
        form = InviteUserForm()
        return render(request, "accounts/invite.html", {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = InviteUserForm(request.POST)
        if not form.is_valid():
            return render(request, "accounts/invite.html", {"form": form})

        email = form.cleaned_data["email"].lower()
        is_admin_flag = form.cleaned_data["is_admin"]
        is_therapist_flag = form.cleaned_data["is_therapist"]
        is_office_manager_flag = form.cleaned_data.get("is_office_manager", False)

        _user, _profile, token = _create_user_invitation(
            email,
            is_admin_flag,
            is_therapist_flag,
            is_office_manager_flag,
        )
        login_url = _login_url(request)

        site_name = getattr(settings, "SITE_NAME", "L+C Psychological Services")
        subject = f"You're invited to {site_name}"
        body = (
            f"Hi,\n\nAn account was created for you on {site_name}.\n"
            f"Sign in with your LCPsych email and Office 365 password here:\n{login_url}\n\n"
            "If you did not expect this invitation, you can ignore this email."
        )

        try:
            send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [email], fail_silently=False)
            messages.success(request, f"Invitation sent to {email}.")
            redirect_target = reverse("accounts:invite")
        except Exception:
            if not settings.DEBUG:
                raise
            messages.success(request, f"Invitation ready for {email}.")
            redirect_target = reverse("accounts:invite")

        if settings.DEBUG:
            redirect_target = f"{redirect_target}?login_url={urlquote(login_url)}&email={urlquote(email)}"
        return redirect(redirect_target)


class ManageTherapistsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/site_settings.html"
    section_slug: str | None = None
    success_url_name = "settings"

    def _redirect_to_self(self, extra_query: str = "") -> HttpResponse:
        """Redirect back to the current settings page (override per section view)."""
        base_url = reverse(self.success_url_name)
        return redirect(f"{base_url}{extra_query}")

    def _send_password_reset(self, request: HttpRequest, user: User) -> HttpResponse:
        EmailConfirmation.objects.filter(user=user, used_at__isnull=True).delete()
        token = EmailConfirmation.generate_token()
        EmailConfirmation.objects.create(user=user, token=token)
        activate_url = _activation_url(request, token)

        site_name = getattr(settings, "SITE_NAME", "L+C Psychological Services")
        subject = f"Reset your {site_name} password"
        greeting = user.get_full_name() or user.email or "there"
        body = (
            f"Hi {greeting},\n\n"
            f"An admin requested a password reset for your {site_name} account.\n"
            f"Set a new password here:\n{activate_url}\n\n"
            "If you did not expect this reset, contact your admin."
        )

        try:
            logger.info(
                "password_reset_send",
                extra={
                    "user_id": user.pk,
                    "user_email": user.email,
                    "site": site_name,
                },
            )
            send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [user.email], fail_silently=False)
            messages.success(request, f"Password reset link sent to {user.email}.")
        except Exception:
            logger.exception(
                "password_reset_send_failed",
                extra={"user_id": user.pk, "user_email": user.email},
            )
            if not settings.DEBUG:
                raise
            messages.success(request, f"Password reset link ready for {user.email}.")

        redirect_url = ""
        if settings.DEBUG:
            redirect_url = f"?activation_url={urlquote(activate_url)}&email={urlquote(user.email)}"
        return self._redirect_to_self(redirect_url)

    def test_func(self):
        return is_admin(self.request.user)

    def _build_context(
        self,
        request: HttpRequest,
        form: InviteUserForm | None = None,
        debug_activation_url: str = "",
        debug_email: str = "",
        fee_form: PaymentFeeRowForm | None = None,
        editing_fee: PaymentFeeRow | None = None,
        insurance_form: InsuranceProviderForm | None = None,
        editing_insurance: InsuranceProvider | None = None,
        insurance_exclusion_form: InsuranceExclusionForm | None = None,
        editing_insurance_exclusion: InsuranceExclusion | None = None,
        faq_form: FAQItemForm | None = None,
        editing_faq: FAQItem | None = None,
        whatwedo_section_form: WhatWeDoSectionForm | None = None,
        whatwedo_item_form: WhatWeDoItemForm | None = None,
        editing_whatwedo_item: WhatWeDoItem | None = None,
        about_section_form: AboutSectionForm | None = None,
        philosophy_form: OurPhilosophyForm | None = None,
        inspirational_form: InspirationalQuoteForm | None = None,
        company_form: CompanyQuoteForm | None = None,
        contact_form: ContactInfoForm | None = None,
        active_page: str = "",
    ) -> dict:
        invite_form = form or InviteUserForm(initial={"is_therapist": True})
        therapists = (
            TherapistProfile.objects.select_related("user", "license_type")
            .prefetch_related("client_focuses")
            .order_by("last_name", "first_name", "pk")
        )
        users_qs = (
            User.objects.select_related("therapist_profile")
            .prefetch_related("groups")
            .order_by("therapist_profile__home_order", "last_name", "first_name", "email")
        )
        user_rows: list[dict] = []
        for user in users_qs:
            groups = set(user.groups.values_list("name", flat=True))
            profile = getattr(user, "therapist_profile", None)
            user_rows.append(
                {
                    "user": user,
                    "profile": profile,
                    "is_admin": is_admin(user),
                    "is_office_manager": "office_manager" in groups,
                    "is_therapist": "therapist" in groups or profile is not None,
                }
            )
        unassigned_users = (
            User.objects.filter(groups__name="therapist")
            .filter(therapist_profile__isnull=True)
            .order_by("email")
            .distinct()
        )
        payment_fees = PaymentFeeRow.objects.order_by("category", "order", "id")
        insurance_providers = InsuranceProvider.objects.order_by("order", "name", "id")
        insurance_exclusions = InsuranceExclusion.objects.order_by("order", "name", "id")
        faq_items = FAQItem.objects.order_by("order", "id")
        whatwedo_section = WhatWeDoSection.objects.order_by("id").first()
        if not whatwedo_section:
            whatwedo_section = WhatWeDoSection.objects.create()
        whatwedo_items = WhatWeDoItem.objects.order_by("order", "id")
        about_section = AboutSection.objects.order_by("id").first()
        if not about_section:
            about_section = AboutSection.objects.create()
        philosophy_section = OurPhilosophy.objects.order_by("id").first()
        if not philosophy_section:
            philosophy_section = OurPhilosophy.objects.create()
        inspirational_quote = InspirationalQuote.objects.order_by("id").first()
        if not inspirational_quote:
            inspirational_quote = InspirationalQuote.objects.create(
                quote=(
                    "Say yes. Whatever it is, say yes with your whole heart & simple as it sounds, "
                    "that's all the excuse life needs to grab you by the hands & start to dance."
                ),
                author="Brian Andreas",
            )
        company_quote = CompanyQuote.objects.order_by("id").first()
        if not company_quote:
            company_quote = CompanyQuote.objects.create(
                quote=(
                    "Your mental health is a journey, not a destination. "
                    "We're here to walk with you every step of the way."
                ),
                author="L+C Psychological Services",
            )
        contact_section = (
            ContactInfo.objects.filter(is_active=True).order_by("id").first()
            or ContactInfo.objects.order_by("id").first()
        )
        if not contact_section:
            contact_section = ContactInfo.objects.create()
        return {
            "active_page": active_page,
            "invite_form": invite_form,
            "therapists": therapists,
            "user_rows": user_rows,
            "unassigned_users": unassigned_users,
            "debug_activation_url": debug_activation_url,
            "debug_activation_email": debug_email,
            "payment_fees": payment_fees,
            "payment_fee_form": fee_form or PaymentFeeRowForm(),
            "payment_fee_editing": editing_fee,
            "insurance_providers": insurance_providers,
            "insurance_provider_form": insurance_form or InsuranceProviderForm(),
            "insurance_provider_editing": editing_insurance,
            "insurance_exclusions": insurance_exclusions,
            "insurance_exclusion_form": insurance_exclusion_form or InsuranceExclusionForm(),
            "insurance_exclusion_editing": editing_insurance_exclusion,
            "faq_items": faq_items,
            "faq_form": faq_form or FAQItemForm(),
            "faq_editing": editing_faq,
            "whatwedo_section": whatwedo_section,
            "whatwedo_section_form": whatwedo_section_form or WhatWeDoSectionForm(instance=whatwedo_section),
            "whatwedo_items": whatwedo_items,
            "whatwedo_item_form": whatwedo_item_form or WhatWeDoItemForm(),
            "whatwedo_item_editing": editing_whatwedo_item,
            "about_section": about_section,
            "about_section_form": about_section_form or AboutSectionForm(instance=about_section),
            "philosophy_section": philosophy_section,
            "philosophy_form": philosophy_form or OurPhilosophyForm(instance=philosophy_section),
            "inspirational_quote": inspirational_quote,
            "inspirational_form": inspirational_form or InspirationalQuoteForm(instance=inspirational_quote),
            "company_quote": company_quote,
            "company_form": company_form or CompanyQuoteForm(instance=company_quote),
            "contact_info": contact_section,
            "contact_form": contact_form or ContactInfoForm(instance=contact_section),
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        debug_activation_url = request.GET.get("activation_url", "") if settings.DEBUG else ""
        debug_email = request.GET.get("email", "") if settings.DEBUG else ""
        edit_fee_id = request.GET.get("edit_fee")
        edit_insurance_id = request.GET.get("edit_insurance")
        edit_insurance_exclusion_id = request.GET.get("edit_insurance_exclusion")
        edit_faq_id = request.GET.get("edit_faq")
        edit_whatwedo_item_id = request.GET.get("edit_whatwedo_item")
        editing_fee = None
        fee_form = None
        editing_insurance = None
        insurance_form = None
        editing_insurance_exclusion = None
        insurance_exclusion_form = None
        editing_faq = None
        faq_form = None
        editing_whatwedo_item = None
        whatwedo_item_form = None
        if edit_fee_id:
            editing_fee = get_object_or_404(PaymentFeeRow, pk=edit_fee_id)
            fee_form = PaymentFeeRowForm(instance=editing_fee)
        if edit_insurance_id:
            editing_insurance = get_object_or_404(InsuranceProvider, pk=edit_insurance_id)
            insurance_form = InsuranceProviderForm(instance=editing_insurance)
        if edit_insurance_exclusion_id:
            editing_insurance_exclusion = get_object_or_404(InsuranceExclusion, pk=edit_insurance_exclusion_id)
            insurance_exclusion_form = InsuranceExclusionForm(instance=editing_insurance_exclusion)
        if edit_faq_id:
            editing_faq = get_object_or_404(FAQItem, pk=edit_faq_id)
            faq_form = FAQItemForm(instance=editing_faq)
        if edit_whatwedo_item_id:
            editing_whatwedo_item = get_object_or_404(WhatWeDoItem, pk=edit_whatwedo_item_id)
            whatwedo_item_form = WhatWeDoItemForm(instance=editing_whatwedo_item)
        ctx = self._build_context(
            request,
            debug_activation_url=debug_activation_url,
            debug_email=debug_email,
            fee_form=fee_form,
            editing_fee=editing_fee,
            insurance_form=insurance_form,
            editing_insurance=editing_insurance,
            insurance_exclusion_form=insurance_exclusion_form,
            editing_insurance_exclusion=editing_insurance_exclusion,
            faq_form=faq_form,
            editing_faq=editing_faq,
            whatwedo_item_form=whatwedo_item_form,
            editing_whatwedo_item=editing_whatwedo_item,
            active_page=self.section_slug or "therapists",
        )
        return render(request, self.template_name, ctx)

    def post(self, request: HttpRequest) -> HttpResponse:
        action_raw = request.POST.get("action", "")
        action = action_raw.strip()
        post_keys = list(request.POST.keys())
        logger.info("action_received action_raw=%r action=%r post_keys=%s", action_raw, action, post_keys)
        active_page = self.section_slug or "therapists"

        if action in {"reset_password", "reset_password_user"}:
            if action == "reset_password":
                profile_id = request.POST.get("profile_id")
                profile = get_object_or_404(TherapistProfile, pk=profile_id)
                user = profile.user
                logger.info(
                    "password_reset_action",
                    extra={"action": action, "profile_id": profile_id, "user_id": user.pk, "user_email": user.email},
                )
                return self._send_password_reset(request, user)

            user_id = request.POST.get("user_id")
            user = get_object_or_404(User, pk=user_id)
            logger.info(
                "password_reset_action",
                extra={"action": action, "user_id": user.pk, "user_email": user.email},
            )
            return self._send_password_reset(request, user)

        if action == "send_login_link":
            user_id = request.POST.get("user_id")
            user = get_object_or_404(User, pk=user_id)
            if not user.email:
                messages.error(request, "User has no email address on file.")
                return self._redirect_to_self()

            login_url = _login_url(request)
            site_name = getattr(settings, "SITE_NAME", "L+C Psychological Services")
            subject = f"Sign in to {site_name}"
            greeting = user.get_full_name() or user.email or "there"
            body = (
                f"Hi {greeting},\n\n"
                f"Sign in with your LCPsych email and Office 365 password here:\n{login_url}\n\n"
                "If you did not expect this email, you can ignore it."
            )

            try:
                send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [user.email], fail_silently=False)
                messages.success(request, f"Login link sent to {user.email}.")
            except Exception:
                logger.exception("send_login_link_failed", extra={"user_id": user.pk, "user_email": user.email})
                if not settings.DEBUG:
                    raise
                messages.success(request, f"Login link ready for {user.email}.")

            return self._redirect_to_self()

        if action == "invite":
            form = InviteUserForm(request.POST)
            if not form.is_valid():
                ctx = self._build_context(request, form=form, active_page=active_page)
                return render(request, self.template_name, ctx)

            email = form.cleaned_data["email"].lower()
            is_admin_flag = form.cleaned_data["is_admin"]
            is_therapist_flag = form.cleaned_data["is_therapist"]
            is_office_manager_flag = form.cleaned_data.get("is_office_manager", False)
            _user, _profile, token = _create_user_invitation(
                email,
                is_admin_flag,
                is_therapist_flag,
                is_office_manager_flag,
            )
            activate_url = _activation_url(request, token)

            site_name = getattr(settings, "SITE_NAME", "L+C Psychological Services")
            subject = f"You're invited to {site_name}"
            body = (
                f"Hi,\n\nAn account was created for you on {site_name}.\n"
                f"Please confirm your email and set your password here:\n{activate_url}\n\n"
                "If you did not expect this invitation, you can ignore this email."
            )

            try:
                send_mail(subject, body, getattr(settings, "DEFAULT_FROM_EMAIL", None), [email], fail_silently=False)
                messages.success(request, f"Invitation sent to {email}.")
            except Exception:
                if not settings.DEBUG:
                    raise
                messages.success(request, f"Invitation ready for {email}.")

            redirect_qs = ""
            if settings.DEBUG:
                redirect_qs = f"?activation_url={urlquote(activate_url)}&email={urlquote(email)}"
            return self._redirect_to_self(redirect_qs)

        if action == "payment_save":
            object_id = request.POST.get("object_id")
            editing_fee = get_object_or_404(PaymentFeeRow, pk=object_id) if object_id else None
            fee_form = PaymentFeeRowForm(request.POST, instance=editing_fee)
            if fee_form.is_valid():
                saved = fee_form.save()
                verb = "updated" if editing_fee else "added"
                logger.info(
                    "payment_fee_saved",
                    extra={
                        "object_id": object_id,
                        "saved_id": saved.id,
                        "fee_name": saved.name,
                        "category": saved.category,
                        "order": saved.order,
                    },
                )
                messages.success(request, f"Fee row '{saved.name}' {verb}.")
                return self._redirect_to_self()

            logger.info(
                "payment_fee_invalid",
                extra={
                    "object_id": object_id,
                    "errors": fee_form.errors.get_json_data(),
                },
            )
            ctx = self._build_context(
                request,
                fee_form=fee_form,
                editing_fee=editing_fee,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "payment_delete":
            object_id = request.POST.get("object_id")
            row = get_object_or_404(PaymentFeeRow, pk=object_id)
            name = row.name
            row.delete()
            messages.success(request, f"Deleted fee row '{name}'.")
            return self._redirect_to_self()

        if action == "insurance_save":
            object_id = request.POST.get("object_id")
            editing_insurance = get_object_or_404(InsuranceProvider, pk=object_id) if object_id else None
            # Include uploaded logo files so ImageField saves correctly
            insurance_form = InsuranceProviderForm(request.POST, request.FILES, instance=editing_insurance)
            if insurance_form.is_valid():
                saved = insurance_form.save()
                verb = "updated" if editing_insurance else "added"
                messages.success(request, f"Insurance provider '{saved.name}' {verb}.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                insurance_form=insurance_form,
                editing_insurance=editing_insurance,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "insurance_delete":
            object_id = request.POST.get("object_id")
            row = get_object_or_404(InsuranceProvider, pk=object_id)
            name = row.name
            row.delete()
            messages.success(request, f"Deleted insurance provider '{name}'.")
            return self._redirect_to_self()

        if action == "insurance_exclusion_save":
            object_id = request.POST.get("object_id")
            editing_insurance_exclusion = get_object_or_404(InsuranceExclusion, pk=object_id) if object_id else None
            insurance_exclusion_form = InsuranceExclusionForm(request.POST, instance=editing_insurance_exclusion)
            if insurance_exclusion_form.is_valid():
                saved = insurance_exclusion_form.save()
                verb = "updated" if editing_insurance_exclusion else "added"
                messages.success(request, f"Non-accepted provider '{saved.name}' {verb}.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                insurance_exclusion_form=insurance_exclusion_form,
                editing_insurance_exclusion=editing_insurance_exclusion,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "insurance_exclusion_delete":
            object_id = request.POST.get("object_id")
            row = get_object_or_404(InsuranceExclusion, pk=object_id)
            name = row.name
            row.delete()
            messages.success(request, f"Deleted non-accepted provider '{name}'.")
            return self._redirect_to_self()

        if action == "faq_save":
            object_id = request.POST.get("object_id")
            editing_faq = get_object_or_404(FAQItem, pk=object_id) if object_id else None
            faq_form = FAQItemForm(request.POST, instance=editing_faq)
            if faq_form.is_valid():
                saved = faq_form.save()
                verb = "updated" if editing_faq else "added"
                messages.success(request, f"FAQ '{saved.question}' {verb}.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                faq_form=faq_form,
                editing_faq=editing_faq,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "faq_delete":
            object_id = request.POST.get("object_id")
            row = get_object_or_404(FAQItem, pk=object_id)
            name = row.question
            row.delete()
            messages.success(request, f"Deleted FAQ '{name}'.")
            return self._redirect_to_self()

        if action == "about_save":
            section = AboutSection.objects.order_by("id").first()
            if not section:
                section = AboutSection.objects.create()
            about_form = AboutSectionForm(request.POST, instance=section)
            if about_form.is_valid():
                saved = about_form.save()
                messages.success(request, f"Updated '{saved.about_title}' content.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                about_section_form=about_form,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "philosophy_save":
            section = OurPhilosophy.objects.order_by("id").first()
            if not section:
                section = OurPhilosophy.objects.create()
            philosophy_form = OurPhilosophyForm(request.POST, instance=section)
            if philosophy_form.is_valid():
                saved = philosophy_form.save()
                messages.success(request, f"Updated '{saved.title}' content.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                philosophy_form=philosophy_form,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "inspirational_save":
            section = InspirationalQuote.objects.order_by("id").first()
            if not section:
                section = InspirationalQuote.objects.create()
            inspirational_form = InspirationalQuoteForm(request.POST, instance=section)
            if inspirational_form.is_valid():
                saved = inspirational_form.save()
                messages.success(request, "Updated inspirational quote content.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                inspirational_form=inspirational_form,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "company_save":
            section = CompanyQuote.objects.order_by("id").first()
            if not section:
                section = CompanyQuote.objects.create()
            company_form = CompanyQuoteForm(request.POST, instance=section)
            if company_form.is_valid():
                saved = company_form.save()
                messages.success(request, "Updated company quote content.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                company_form=company_form,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "contact_save":
            section = (
                ContactInfo.objects.filter(is_active=True).order_by("id").first()
                or ContactInfo.objects.order_by("id").first()
            )
            if not section:
                section = ContactInfo.objects.create()
            contact_form = ContactInfoForm(request.POST, instance=section)
            if contact_form.is_valid():
                saved = contact_form.save()
                messages.success(request, "Updated contact section content.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                contact_form=contact_form,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "whatwedo_section_save":
            section = WhatWeDoSection.objects.order_by("id").first()
            if not section:
                section = WhatWeDoSection.objects.create()
            section_form = WhatWeDoSectionForm(request.POST, instance=section)
            if section_form.is_valid():
                saved = section_form.save()
                messages.success(request, f"Updated '{saved.title}' copy.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                whatwedo_section_form=section_form,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "whatwedo_item_save":
            object_id = request.POST.get("object_id")
            editing_item = get_object_or_404(WhatWeDoItem, pk=object_id) if object_id else None
            item_form = WhatWeDoItemForm(request.POST, instance=editing_item)
            if item_form.is_valid():
                saved = item_form.save()
                verb = "updated" if editing_item else "added"
                messages.success(request, f"What We Do item '{saved.text}' {verb}.")
                return self._redirect_to_self()

            ctx = self._build_context(
                request,
                whatwedo_item_form=item_form,
                editing_whatwedo_item=editing_item,
                active_page=active_page,
            )
            return render(request, self.template_name, ctx)

        if action == "whatwedo_item_delete":
            object_id = request.POST.get("object_id")
            row = get_object_or_404(WhatWeDoItem, pk=object_id)
            name = row.text
            row.delete()
            messages.success(request, f"Deleted What We Do item '{name}'.")
            return self._redirect_to_self()

        if action in {"set_publish", "set_accepts"}:
            profile_id = request.POST.get("profile_id")
            value = request.POST.get("value") == "1"
            profile = get_object_or_404(TherapistProfile, pk=profile_id)
            if action == "set_publish":
                profile.is_published = value
                profile.save(update_fields=["is_published", "updated_at"])
                state = "published" if value else "hidden"
                messages.success(request, f"{profile.display_name} is now {state}.")
            else:
                profile.accepts_new_clients = value
                profile.save(update_fields=["accepts_new_clients", "updated_at"])
                state = "accepting" if value else "not accepting"
                messages.success(request, f"{profile.display_name} is now {state} new clients.")
            return self._redirect_to_self()

        if action == "delete_user":
            user_id = request.POST.get("user_id")
            user = get_object_or_404(User, pk=user_id)
            if is_admin(user):
                messages.error(request, "Admins cannot be deleted here.")
                return self._redirect_to_self()
            email = user.email or "user"
            user.delete()
            messages.success(request, f"Deleted {email}.")
            return self._redirect_to_self()

        if action == "delete_therapist":
            profile_id = request.POST.get("profile_id")
            profile = get_object_or_404(TherapistProfile, pk=profile_id)
            name = profile.display_name or profile.user.email or "therapist"
            user = profile.user
            if is_admin(user):
                messages.error(request, "Admins cannot be deleted here.")
                return self._redirect_to_self()
            therapist_group = Group.objects.filter(name="therapist").first()
            profile.delete()
            if therapist_group:
                user.groups.remove(therapist_group)
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"] if hasattr(user, "updated_at") else ["is_active"])
            messages.success(request, f"Deleted therapist profile for {name} and deactivated their account.")
            return self._redirect_to_self()

        if action == "create_profile":
            user_id = request.POST.get("user_id")
            user = get_object_or_404(User, pk=user_id)
            profile, created = TherapistProfile.objects.get_or_create(user=user)
            therapist_group, _ = Group.objects.get_or_create(name="therapist")
            user.groups.add(therapist_group)
            if created:
                messages.success(request, f"Profile created for {user.email}.")
            else:
                messages.info(request, f"{user.email} already has a profile.")
            return self._redirect_to_self()

        # Default: if no recognized action, redirect back safely
        messages.error(request, "No action was performed.")
        return self._redirect_to_self()


class SocialPostingSettingsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/settings_social_posting.html"
    platform_order = [
        SocialPlatform.INSTAGRAM,
        SocialPlatform.X,
        SocialPlatform.FACEBOOK_PAGE,
        SocialPlatform.GOOGLE_BUSINESS,
        SocialPlatform.LINKEDIN_PAGE,
    ]

    def test_func(self):
        return is_admin(self.request.user)

    def _profiles(self):
        profiles = []
        for platform in self.platform_order:
            profile, _ = SocialProfile.objects.get_or_create(platform=platform)
            profiles.append(profile)
        return profiles

    def _forms(self, bound_platform: str | None = None, bound_form: SocialProfileForm | None = None):
        profile_forms: list[tuple[SocialProfile, SocialProfileForm]] = []
        for profile in self._profiles():
            if bound_platform and profile.platform == bound_platform and bound_form is not None:
                profile_forms.append((profile, bound_form))
            else:
                profile_forms.append((profile, SocialProfileForm(prefix=profile.platform, instance=profile)))
        return profile_forms

    def get(self, request: HttpRequest) -> HttpResponse:
        ctx = {
            "profile_forms": self._forms(),
            "active_page": "social_posting",
        }
        return render(request, self.template_name, ctx)

    def post(self, request: HttpRequest) -> HttpResponse:
        platform = request.POST.get("platform")
        if not platform:
            messages.error(request, "Missing platform selection.")
            return redirect(reverse("accounts:settings_social_posting"))

        profile, _ = SocialProfile.objects.get_or_create(platform=platform)
        form = SocialProfileForm(request.POST, prefix=platform, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, f"Saved settings for {profile.get_platform_display()}.")  # type: ignore[attr-defined]
            return redirect(reverse("accounts:settings_social_posting"))

        ctx = {
            "profile_forms": self._forms(bound_platform=platform, bound_form=form),
            "active_page": "social_posting",
        }
        return render(request, self.template_name, ctx)


class VisitorStatsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/settings_visitor_stats.html"

    @staticmethod
    def _format_ms(ms: int | float | None) -> str:
        if not ms or ms <= 0:
            return "<1s"
        total_seconds = int(round(ms / 1000))
        minutes, seconds = divmod(total_seconds, 60)
        if minutes:
            return f"{minutes}m {seconds:02d}s"
        return f"{seconds}s"

    def test_func(self):
        return is_admin(self.request.user)

    def get(self, request: HttpRequest) -> HttpResponse:
        tz_name = "America/New_York"
        profile = getattr(request.user, "therapist_profile", None)
        if profile and getattr(profile, "timezone", ""):
            tz_name = profile.timezone

        try:
            tzinfo = ZoneInfo(tz_name)
        except Exception:
            tzinfo = timezone.get_default_timezone()
            tz_name = timezone.get_default_timezone_name()

        today = timezone.localtime(timezone.now(), timezone=tzinfo).date()
        default_end = today
        default_start = default_end - timedelta(days=29)

        def _parse_date(val: str | None, fallback: date) -> date:
            if not val:
                return fallback
            try:
                return datetime.strptime(val, "%Y-%m-%d").date()
            except ValueError:
                return fallback

        start_date = _parse_date(request.GET.get("start"), default_start)
        end_date = _parse_date(request.GET.get("end"), default_end)
        if end_date < start_date:
            end_date = start_date

        max_span_days = 365
        if (end_date - start_date).days > max_span_days:
            start_date = end_date - timedelta(days=max_span_days)

        start_dt = timezone.make_aware(datetime.combine(start_date, time.min), timezone=tzinfo)
        end_dt = timezone.make_aware(datetime.combine(end_date + timedelta(days=1), time.min), timezone=tzinfo)

        all_events = AnalyticsEvent.objects.filter(created__gte=start_dt, created__lt=end_dt)
        events = all_events.filter(is_authenticated=False)

        person_expr = Case(
            When(~Q(ip_hash="") & ~Q(user_agent=""), then=Concat("ip_hash", Value("|"), "user_agent")),
            When(~Q(ip_hash=""), then="ip_hash"),
            default="session_id",
            output_field=CharField(),
        )

        device_os_expr = Case(
            When(user_agent__icontains="android", then=Value("Android")),
            When(user_agent__icontains="iphone", then=Value("iOS")),
            When(user_agent__icontains="ipad", then=Value("iPadOS")),
            When(user_agent__icontains="mac os", then=Value("macOS")),
            When(user_agent__icontains="macintosh", then=Value("macOS")),
            When(user_agent__icontains="windows", then=Value("Windows")),
            When(user_agent__icontains="linux", then=Value("Linux")),
            When(user_agent__icontains="cros", then=Value("ChromeOS")),
            default=Value("Other"),
            output_field=CharField(),
        )

        device_type_expr = Case(
            When(Q(user_agent__icontains="ipad") | Q(user_agent__icontains="tablet"), then=Value("Tablet")),
            When(
                Q(user_agent__icontains="mobile")
                | Q(user_agent__icontains="iphone")
                | Q(user_agent__icontains="android"),
                then=Value("Mobile"),
            ),
            default=Value("Desktop"),
            output_field=CharField(),
        )

        events = events.annotate(person_key=person_expr, device_os=device_os_expr, device_type=device_type_expr)

        click_events = events.filter(event_type=AnalyticsEventType.CLICK)
        page_views = events.filter(event_type=AnalyticsEventType.PAGE_VIEW)
        total_page_views = page_views.count()
        avg_time_ms = page_views.aggregate(avg=Avg("duration_ms"))['avg'] or 0
        avg_time_label = self._format_ms(avg_time_ms)
        unique_sessions = events.values("person_key").distinct().count()

        rage_clicks_qs = events.filter(event_type=AnalyticsEventType.RAGE_CLICK)
        dead_clicks_qs = events.filter(event_type=AnalyticsEventType.DEAD_CLICK)
        hover_qs = events.filter(event_type=AnalyticsEventType.HOVER_INTENT)
        exit_qs = events.filter(event_type=AnalyticsEventType.SESSION_EXIT)

        schedule_open_qs = click_events.filter(label="schedule_modal_open")
        schedule_existing_qs = click_events.filter(label="schedule_existing_select")
        schedule_new_qs = click_events.filter(label="schedule_new_select")
        schedule_no_selection_qs = click_events.filter(label="schedule_no_selection")

        schedule_clicks_by_day = (
            click_events.filter(
                label__in=[
                    "schedule_modal_open",
                    "schedule_new_select",
                    "schedule_existing_select",
                ]
            )
            .annotate(day=TruncDate("created"))
            .values("day", "label")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        schedule_daily_map: dict[date, dict[str, int | str]] = {}
        for row in schedule_clicks_by_day:
            day_key = row["day"]
            entry = schedule_daily_map.setdefault(
                day_key,
                {
                    "day": day_key,
                    "opens": 0,
                    "new": 0,
                    "existing": 0,
                },
            )
            label = row["label"]
            if label == "schedule_modal_open":
                entry["opens"] = row["count"]
            elif label == "schedule_new_select":
                entry["new"] = row["count"]
            elif label == "schedule_existing_select":
                entry["existing"] = row["count"]

        def _fmt_day(day_val: date) -> str:
            try:
                return day_val.strftime("%a, %b %d")
            except Exception:
                return str(day_val)

        schedule_daily = []
        for day_key in sorted(schedule_daily_map.keys()):
            entry = schedule_daily_map[day_key]
            schedule_daily.append(
                {
                    "day": day_key,
                    "day_label": _fmt_day(day_key),
                    "opens": entry.get("opens", 0),
                    "new": entry.get("new", 0),
                    "existing": entry.get("existing", 0),
                }
            )

        schedule_sources = list(
            schedule_open_qs.values("metadata__source")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        def _label_counts(qs):
            return list(
                qs.values("path", "label")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

        cta_excluded_labels = ["schedule_new_select", "schedule_existing_select"]
        cta_events = click_events.exclude(label__in=cta_excluded_labels)

        # Use modal opens as the single schedule CTA event to avoid double-counting alongside the per-button click labels.
        schedule_cta_labels = [
            "schedule_modal_open",
        ]
        call_cta_labels = [
            "cta_call_header",
            "cta_call_hero",
            "cta_call_contact_home",
            "cta_call_contact_section_primary",
            "cta_call_contact_section_office",
        ]
        email_cta_labels = [
            "cta_email_contact_home",
            "cta_email_contact_section_primary",
            "cta_email_contact_section_office",
        ]

        all_cta_labels = schedule_cta_labels + call_cta_labels + email_cta_labels

        schedule_cta_clicks = _label_counts(cta_events.filter(label__in=schedule_cta_labels))
        call_cta_clicks = _label_counts(cta_events.filter(label__in=call_cta_labels))
        email_cta_clicks = _label_counts(cta_events.filter(label__in=email_cta_labels))

        cta_clicks_combined = [
            {"category": "Schedule", **row} for row in schedule_cta_clicks
        ] + [
            {"category": "Call", **row} for row in call_cta_clicks
        ] + [
            {"category": "Email", **row} for row in email_cta_clicks
        ]
        cta_clicks_combined.sort(key=lambda r: r.get("count", 0), reverse=True)

        weekday_map: dict[int, dict[str, int | str]] = {}

        weekday_events = (
            events.annotate(weekday=ExtractWeekDay("created"))
            .values("weekday")
            .annotate(sessions=Count("person_key", distinct=True))
        )
        for row in weekday_events:
            weekday = int(row.get("weekday") or 0)
            entry = weekday_map.setdefault(
                weekday,
                {"weekday": weekday, "weekday_label": "", "sessions": 0, "page_views": 0, "cta_clicks": 0},
            )
            entry["sessions"] = row.get("sessions", 0) or 0

        weekday_page_views = (
            page_views.annotate(weekday=ExtractWeekDay("created"))
            .values("weekday")
            .annotate(page_views=Count("id"))
        )
        for row in weekday_page_views:
            weekday = int(row.get("weekday") or 0)
            entry = weekday_map.setdefault(
                weekday,
                {"weekday": weekday, "weekday_label": "", "sessions": 0, "page_views": 0, "cta_clicks": 0},
            )
            entry["page_views"] = row.get("page_views", 0) or 0

        weekday_cta = (
            cta_events.filter(label__in=all_cta_labels)
            .annotate(weekday=ExtractWeekDay("created"))
            .values("weekday")
            .annotate(cta_clicks=Count("id"))
        )
        for row in weekday_cta:
            weekday = int(row.get("weekday") or 0)
            entry = weekday_map.setdefault(
                weekday,
                {"weekday": weekday, "weekday_label": "", "sessions": 0, "page_views": 0, "cta_clicks": 0},
            )
            entry["cta_clicks"] = row.get("cta_clicks", 0) or 0

        weekday_labels = {1: "Sun", 2: "Mon", 3: "Tue", 4: "Wed", 5: "Thu", 6: "Fri", 7: "Sat"}
        by_weekday = []
        for weekday in range(1, 8):
            entry = weekday_map.get(
                weekday,
                {"weekday": weekday, "weekday_label": "", "sessions": 0, "page_views": 0, "cta_clicks": 0},
            )
            entry["weekday_label"] = weekday_labels.get(weekday, str(weekday))
            by_weekday.append(entry)

        rage_click_count = rage_clicks_qs.count()
        dead_click_count = dead_clicks_qs.count()

        exit_events_raw = list(
            exit_qs.order_by("person_key", "-created", "-id")
            .values(
                "person_key",
                "path",
                "metadata__exit_scroll",
                "metadata__click_path",
                "created",
            )
        )

        # Keep only the last exit event per session so exits represent the final page seen.
        latest_exit_by_session: dict[str, dict] = {}
        for row in exit_events_raw:
            session_key = row.get("person_key") or ""
            created = row.get("created")
            existing = latest_exit_by_session.get(session_key)
            if not existing:
                latest_exit_by_session[session_key] = row
                continue

            existing_created = existing.get("created")
            if created and not existing_created:
                latest_exit_by_session[session_key] = row
            elif created and existing_created and created > existing_created:
                latest_exit_by_session[session_key] = row

        exit_events_dedup: list[dict] = list(latest_exit_by_session.values())
        exit_event_count = len(exit_events_dedup)

        rage_hotspots = list(
            rage_clicks_qs.values("label")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        dead_hotspots = list(
            dead_clicks_qs.values("label")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        hover_targets = list(
            hover_qs.values("label")
            .annotate(count=Count("id"), avg_duration=Avg("duration_ms"))
            .order_by("-count")
        )
        for row in hover_targets:
            row["avg_duration_label"] = self._format_ms(row.get("avg_duration") or 0)

        avg_hover_ms = hover_qs.aggregate(avg=Avg("duration_ms"))["avg"] or 0
        avg_hover_label = self._format_ms(avg_hover_ms)

        exit_sessions = len(latest_exit_by_session)
        exit_rate = round((exit_sessions / unique_sessions) * 100, 1) if unique_sessions else 0

        path_map: dict[str, dict[str, int]] = {}

        for row in exit_events_dedup:
            path = row.get("path") or ""
            entry = path_map.setdefault(path, {"count": 0})
            entry["count"] = int(entry["count"]) + 1

        exit_by_path = []
        for path, entry in path_map.items():
            exit_by_path.append(
                {
                    "path": path,
                    "count": entry["count"],
                }
            )
        exit_by_path.sort(key=lambda r: r.get("count", 0), reverse=True)

        click_path_map: dict[str, dict[str, int | set[str]]] = {}

        # Track CTA categories clicked per session (Schedule/Call/Email).
        cta_label_map = {lbl: "Schedule" for lbl in schedule_cta_labels}
        cta_label_map.update({lbl: "Call" for lbl in call_cta_labels})
        cta_label_map.update({lbl: "Email" for lbl in email_cta_labels})

        session_cta_types: dict[str, set[str]] = {}
        for row in cta_events.filter(label__in=all_cta_labels).values("person_key", "label"):
            session_key = row.get("person_key") or ""
            category = cta_label_map.get(row.get("label") or "")
            if not category:
                continue
            entry = session_cta_types.setdefault(session_key, set())
            entry.add(category)

        page_title_map: dict[str, str] = {}

        def _add_title(path_val: str, title_val: str) -> None:
            norm = (path_val or "").strip("/")
            if norm in page_title_map:
                return
            page_title_map[norm] = title_val

        for p in Page.objects.all().values("path", "title"):
            _add_title(p.get("path") or "", p.get("title") or "")

        for entry in StaticPageSEO.objects.all().values("slug", "page_name"):
            _add_title(entry.get("slug") or "", entry.get("page_name") or "")

        for t in TherapistProfile.objects.filter(is_published=True).values("slug", "salutation", "first_name", "last_name"):
            slug = t.get("slug") or ""
            salutation = (t.get("salutation") or "").strip()
            first = (t.get("first_name") or "").strip()
            last = (t.get("last_name") or "").strip()
            name_parts = [p for p in [first, last] if p]
            name = " ".join(name_parts) or slug or "Therapist"
            if salutation:
                name = f"{salutation} {name}".strip()
            _add_title(f"therapists/{slug}", name)

        for post in Post.objects.filter(status=Post.STATUS_PUBLISHED).values("slug", "title"):
            _add_title(f"blog/{post.get('slug') or ''}", post.get("title") or "")

        def _path_to_title(path_val: str) -> str:
            norm = (path_val or "").strip("/")
            if not norm:
                return "Home"
            return page_title_map.get(norm, path_val or "(unknown)")

        session_pages: dict[str, list[str]] = {}
        for row in page_views.order_by("person_key", "created", "id").values("person_key", "path"):
            session_key = row.get("person_key") or ""
            path = row.get("path") or ""
            session_pages.setdefault(session_key, []).append(path)

        for session_key, paths in session_pages.items():
            # Build a simple navigation sequence of page titles, ignoring clicks/buttons.
            deduped_paths: list[str] = []
            for p in paths:
                if not p:
                    continue
                if not deduped_paths or deduped_paths[-1] != p:
                    deduped_paths.append(p)

            if not deduped_paths:
                continue

            title_sequence = " > ".join([_path_to_title(p) for p in deduped_paths])
            entry = click_path_map.setdefault(title_sequence, {"count": 0, "cta_types": set()})
            entry["count"] = int(entry["count"]) + 1
            if session_key in session_cta_types:
                entry["cta_types"].update(session_cta_types.get(session_key, set()))

        click_paths = []
        for sequence, entry in click_path_map.items():
            click_paths.append(
                {
                    "metadata__click_path": sequence,
                    "count": entry["count"],
                    "cta_labels": sorted(entry.get("cta_types", set())),
                }
            )
        click_paths.sort(key=lambda r: r.get("count", 0), reverse=True)

        page_views_by_day = list(
            page_views.annotate(day=TruncDate("created"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        cta_clicks_by_day = list(
            cta_events.filter(label__in=all_cta_labels)
            .annotate(day=TruncDate("created"))
            .values("day")
            .annotate(cta_clicks=Count("id"))
            .order_by("day")
        )

        sessions_by_day = list(
            events.annotate(day=TruncDate("created"))
            .values("day")
            .annotate(sessions=Count("person_key", distinct=True))
            .order_by("day")
        )

        daily_map: dict[date, dict[str, int]] = {}
        for row in page_views_by_day:
            daily_map[row["day"]] = {"page_views": row["count"], "sessions": 0, "cta_clicks": 0}
        for row in sessions_by_day:
            existing = daily_map.setdefault(row["day"], {"page_views": 0, "sessions": 0, "cta_clicks": 0})
            existing["sessions"] = row["sessions"]
        for row in cta_clicks_by_day:
            existing = daily_map.setdefault(row["day"], {"page_views": 0, "sessions": 0, "cta_clicks": 0})
            existing["cta_clicks"] = row["cta_clicks"]

        chart_by_day = []
        max_value = 0
        for day_key, row in daily_map.items():
            max_value = max(max_value, row["page_views"], row["sessions"])
        max_value = max_value or 1
        for day_key in sorted(daily_map.keys()):
            row = daily_map[day_key]
            chart_by_day.append(
                {
                    "day": day_key,
                    "page_views": row["page_views"],
                    "sessions": row["sessions"],
                    "page_views_pct": round((row["page_views"] / max_value) * 100, 1),
                    "sessions_pct": round((row["sessions"] / max_value) * 100, 1),
                }
            )

        table_by_day = [
            {
                "day": entry["day"],
                "day_label": _fmt_day(entry["day"]),
                "page_views": entry["page_views"],
                "sessions": entry["sessions"],
                "cta_clicks": daily_map.get(entry["day"], {}).get("cta_clicks", 0),
            }
            for entry in chart_by_day
        ]

        top_pages = list(
            page_views.values("path")
            .annotate(count=Count("id"), avg_duration=Avg("duration_ms"))
            .order_by("-count")
        )
        for row in top_pages:
            row["avg_duration_label"] = self._format_ms(row.get("avg_duration") or 0)
            row["page_title"] = _path_to_title(row.get("path") or "")

        top_clicks_exclude = [
            "menu_toggle",
            "mobile_nav_toggle",
            "nav_toggle",
            "menu-toggle",
            "mobile-menu-toggle",
            "continue with microsoft",
            "",
        ]
        top_clicks = list(
            events.filter(event_type=AnalyticsEventType.CLICK)
            .exclude(label__in=top_clicks_exclude)
            .exclude(path__startswith="/admin")
            .exclude(metadata__href__icontains="/admin")
            .exclude(metadata__target__icontains="modal")
            .values("label", "path")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        for row in top_clicks:
            row["page_title"] = _path_to_title(row.get("path") or "")

        current_host = request.get_host()
        landing_referrers = list(
            events.exclude(
                Q(metadata__landing_referrer__icontains="localhost")
                | Q(metadata__landing_referrer__icontains="127.0.0.1")
                | Q(metadata__landing_referrer__icontains=current_host)
            )
            .values("metadata__landing_referrer")
            .annotate(
                sessions=Count("person_key", distinct=True),
                events=Count("id"),
            )
            .order_by("-sessions")
        )

        avg_scroll = (
            events.filter(event_type=AnalyticsEventType.SCROLL)
            .aggregate(avg=Avg("scroll_percent"))
            .get("avg")
            or 0
        )

        locations = list(
            events.exclude(country_code="")
            .values("country_code", "region", "city", "timezone")
            .annotate(count=Count("id"), sessions=Count("person_key", distinct=True))
            .order_by("-sessions", "-count")
        )

        device_os_stats = list(
            events.values("device_os", "device_type")
            .annotate(sessions=Count("person_key", distinct=True), events=Count("id"))
            .order_by("-sessions", "device_os", "device_type")
        )

        ctx = {
            "active_page": "visitor_stats",
            "start_date": start_date,
            "end_date": end_date,
            "range_days": (end_date - start_date).days + 1,
            "range_label": f"{start_date.strftime('%b %d, %Y')} — {end_date.strftime('%b %d, %Y')}",
            "total_page_views": total_page_views,
            "avg_time_ms": int(avg_time_ms),
            "avg_time_label": avg_time_label,
            "unique_sessions": unique_sessions,
            "by_day": table_by_day,
            "by_weekday": by_weekday,
            "chart_by_day": chart_by_day,
            "top_pages": top_pages,
            "top_clicks": top_clicks,
            "landing_referrers": landing_referrers,
            "avg_scroll": int(avg_scroll),
            "locations": locations,
            "device_os_stats": device_os_stats,
            "rage_hotspots": rage_hotspots,
            "dead_hotspots": dead_hotspots,
            "hover_targets": hover_targets,
            "avg_hover_label": avg_hover_label,
            "hover_event_count": hover_qs.count(),
            "exit_rate": exit_rate,
            "exit_by_path": exit_by_path,
            "avg_exit_scroll": round(exit_qs.aggregate(avg=Avg(Cast("metadata__exit_scroll", FloatField())))["avg"] or 0),
            "click_paths": click_paths,
            "exit_sessions": exit_sessions,
            "rage_click_count": rage_click_count,
            "dead_click_count": dead_click_count,
            "exit_event_count": exit_event_count,
            "active_timezone": tz_name,
            "schedule_modal_open_count": schedule_open_qs.count(),
            "schedule_existing_select_count": schedule_existing_qs.count(),
            "schedule_new_select_count": schedule_new_qs.count(),
            "schedule_no_selection_count": schedule_no_selection_qs.count(),
            "schedule_sources": schedule_sources,
            "cta_clicks": cta_clicks_combined,
            "schedule_cta_total": sum(row.get("count", 0) for row in schedule_cta_clicks),
            "call_cta_total": sum(row.get("count", 0) for row in call_cta_clicks),
            "email_cta_total": sum(row.get("count", 0) for row in email_cta_clicks),
            "schedule_daily": schedule_daily,
        }
        return render(request, self.template_name, ctx)


class InviteSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_invite.html"
    success_url_name = "accounts:settings_invite"
    section_slug = "invite"


class AboutSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_about.html"
    success_url_name = "accounts:settings_about"
    section_slug = "about"


class PhilosophySettingsView(ManageTherapistsView):
    template_name = "accounts/settings_philosophy.html"
    success_url_name = "accounts:settings_philosophy"
    section_slug = "philosophy"


class QuotesSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_quotes.html"
    success_url_name = "accounts:settings_quotes"
    section_slug = "quotes"


class ContactSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_contact.html"
    success_url_name = "accounts:settings_contact"
    section_slug = "contact"


class WhatWeDoSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_whatwedo.html"
    success_url_name = "accounts:settings_whatwedo"
    section_slug = "whatwedo"


class FAQSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_faq.html"
    success_url_name = "accounts:settings_faq"
    section_slug = "faq"


class InsuranceSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_insurance.html"
    success_url_name = "accounts:settings_insurance"
    section_slug = "insurance"


class PaymentSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_payment.html"
    success_url_name = "accounts:settings_payment"
    section_slug = "payment"


class PublishedSettingsView(ManageTherapistsView):
    template_name = "accounts/settings_published.html"
    success_url_name = "accounts:settings_published"
    section_slug = "published"


class ManageJoinSubmissionsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/manage_join_submissions.html"

    def test_func(self):
        user = self.request.user
        return is_admin(user) or is_office_manager(user)

    def get(self, request: HttpRequest) -> HttpResponse:
        submissions = (
            JoinOurTeamSubmission.objects.filter(is_reviewed=False)
            .select_related("reviewed_by")
            .order_by("-created")
        )
        forward_users_queryset = (
            User.objects.filter(is_active=True, groups__name__in=["admin", "office_manager", "therapist"])
            .select_related("therapist_profile")
            .order_by("last_name", "first_name", "email")
            .distinct()
        )

        forward_users: list[dict] = []
        for user in forward_users_queryset:
            if not user.email:
                continue

            profile = getattr(user, "therapist_profile", None)
            salutation = (profile.salutation if profile else "") or ""
            first_name = (profile.first_name if profile else user.first_name) or ""
            last_name = (profile.last_name if profile else user.last_name) or ""

            parts = [p.strip() for p in (salutation, first_name, last_name) if p and p.strip()]
            label = " ".join(parts).strip()
            if not label:
                label = (user.get_full_name() or "").strip()
            if not label:
                label = user.email.strip()

            forward_users.append({
                "id": user.pk,
                "email": user.email.strip(),
                "label": label,
            })
        return render(
            request,
            self.template_name,
            {
                "submissions": submissions,
                "forward_users": forward_users,
            },
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        action = request.POST.get("action")
        submission_id = request.POST.get("submission_id")
        submission = get_object_or_404(JoinOurTeamSubmission, pk=submission_id)

        if action == "mark_reviewed":
            submission.is_reviewed = True
            submission.reviewed_at = timezone.now()
            submission.reviewed_by = request.user
            submission.save(update_fields=["is_reviewed", "reviewed_at", "reviewed_by", "updated"])
            messages.success(request, f"Marked {submission.full_name} as reviewed.")
        elif action == "forward":
            target_email = (request.POST.get("target_email") or "").strip().lower()
            note = (request.POST.get("note") or "").strip()
            mark_reviewed_flag = request.POST.get("mark_reviewed_after_forward") == "1"
            target_user_id = request.POST.get("target_user_id")

            if not target_email and target_user_id:
                user_candidate = User.objects.filter(pk=target_user_id, is_active=True).first()
                if user_candidate and user_candidate.email:
                    target_email = user_candidate.email.strip().lower()
            if not target_email:
                messages.error(request, "Add an email to forward this submission.")
                return redirect("accounts:join_submissions")

            resume_url = ""
            try:
                if submission.resume:
                    resume_url = request.build_absolute_uri(submission.resume.url)
            except Exception:
                resume_url = ""

            subject = f"Join Our Team submission from {submission.full_name}"
            lines = [
                f"Name: {submission.full_name}",
                f"Email: {submission.email}",
                "",
                "Message:",
                submission.message,
            ]
            if resume_url:
                lines.extend(["", f"Resume: {resume_url}"])
            if note:
                lines.extend(["", f"Forwarded note: {note}"])
            body = "\n".join(lines)

            try:
                send_mail(
                    subject,
                    body,
                    getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    [target_email],
                    fail_silently=False,
                )
                messages.success(request, f"Forwarded to {target_email}.")
            except Exception:
                if not settings.DEBUG:
                    raise
                messages.success(request, f"Forward prepared for {target_email} (email send skipped in DEBUG).")

            if mark_reviewed_flag:
                submission.is_reviewed = True
                submission.reviewed_at = timezone.now()
                submission.reviewed_by = request.user
                submission.save(update_fields=["is_reviewed", "reviewed_at", "reviewed_by", "updated"])
                messages.success(request, "Marked as reviewed after forwarding.")
        else:
            messages.error(request, "Unsupported action.")

        return redirect("accounts:join_submissions")


class ManageServicesView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/manage_services.html"

    def test_func(self):
        return is_admin(self.request.user)

    def _context(self, form: ServiceForm | None = None, editing: Service | None = None) -> dict:
        services = Service.objects.order_by("order", "title")
        return {
            "form": form or ServiceForm(),
            "editing": editing,
            "services": services,
            "active_page": "services",
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        edit_id = request.GET.get("edit")
        editing = None
        form = None
        if edit_id:
            editing = get_object_or_404(Service, pk=edit_id)
            form = ServiceForm(instance=editing)
        return render(request, self.template_name, self._context(form=form, editing=editing))


class ManageSEOSettingsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/manage_seo.html"

    DEFAULT_STATIC_PAGES = [
        ("home", "Home"),
        ("our-team", "Our Team"),
        ("about-us", "About Us"),
        ("services", "Services"),
        ("insurance", "Insurance & Payment"),
        ("contact-us", "Contact Us"),
        ("faq", "Frequently Asked Questions"),
    ]

    def test_func(self):
        return is_admin(self.request.user)

    def _ensure_defaults(self):
        default_map = {slug: name for slug, name in self.DEFAULT_STATIC_PAGES}
        for slug, name in self.DEFAULT_STATIC_PAGES:
            StaticPageSEO.objects.get_or_create(slug=slug, defaults={"page_name": name})
        return default_map

    def _context(self, form: StaticPageSEOForm | None = None, editing: StaticPageSEO | None = None) -> dict:
        self._ensure_defaults()
        entries = StaticPageSEO.objects.order_by("page_name", "slug")
        contact_info = (
            ContactInfo.objects.filter(is_active=True).order_by("id").first()
            or ContactInfo.objects.order_by("id").first()
        )
        if not contact_info:
            contact_info = ContactInfo.objects.create()
        return {
            "form": form or StaticPageSEOForm(),
            "editing": editing,
            "entries": entries,
            "default_slugs": {slug for slug, _ in self.DEFAULT_STATIC_PAGES},
            "contact_form": ContactInfoForm(instance=contact_info),
            "contact_info": contact_info,
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        edit_id = request.GET.get("edit")
        editing = None
        form = None
        if edit_id:
            editing = get_object_or_404(StaticPageSEO, pk=edit_id)
            form = StaticPageSEOForm(instance=editing)
        return render(request, self.template_name, self._context(form=form, editing=editing))

    def post(self, request: HttpRequest) -> HttpResponse:
        default_map = self._ensure_defaults()
        form_type = request.POST.get("form_type", "page_seo")

        if form_type == "local_seo":
            contact_info = (
                ContactInfo.objects.filter(is_active=True).order_by("id").first()
                or ContactInfo.objects.order_by("id").first()
            )
            if not contact_info:
                contact_info = ContactInfo.objects.create()
            contact_form = ContactInfoForm(request.POST, instance=contact_info)
            if contact_form.is_valid():
                contact_form.save()
                messages.success(request, "Local SEO details updated (address, phone, hours, map).")
                return redirect("accounts:seo_settings")
            # Return page with contact form errors alongside SEO form
            return render(
                request,
                self.template_name,
                self._context(form=StaticPageSEOForm(), editing=None) | {"contact_form": contact_form},
            )

        action = request.POST.get("action", "save")

        if action == "delete":
            object_id = request.POST.get("object_id")
            entry = get_object_or_404(StaticPageSEO, pk=object_id)
            if entry.slug in default_map:
                messages.error(request, f"'{entry.page_name}' is a required static page and cannot be deleted.")
                return redirect("accounts:seo_settings")
            name = entry.page_name
            entry.delete()
            messages.success(request, f"Removed SEO entry '{name}'.")
            return redirect("accounts:seo_settings")

        object_id = request.POST.get("object_id")
        editing = get_object_or_404(StaticPageSEO, pk=object_id) if object_id else None
        form = StaticPageSEOForm(request.POST, request.FILES, instance=editing)
        if form.is_valid():
            entry = form.save()
            verb = "updated" if editing else "created"
            messages.success(request, f"SEO settings for '{entry.page_name}' {verb}.")
            return redirect("accounts:seo_settings")

        return render(request, self.template_name, self._context(form=form, editing=editing))


class ManageTherapistProfileView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/manage_therapist_profile.html"

    def test_func(self):
        return is_admin(self.request.user)

    def _get_profile(self, pk: int) -> TherapistProfile:
        return get_object_or_404(
            TherapistProfile.objects.select_related("user", "license_type").prefetch_related("client_focuses", "services"),
            pk=pk,
        )

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        profile = self._get_profile(pk)
        form = AdminTherapistProfileForm(instance=profile)
        return render(
            request,
            self.template_name,
            {
                "profile": profile,
                "form": form,
            },
        )

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        profile = self._get_profile(pk)
        form = AdminTherapistProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save()
            messages.success(request, f"Updated profile for {profile.display_name}.")
            return redirect("accounts:therapist_edit", pk=profile.pk)

        return render(
            request,
            self.template_name,
            {
                "profile": profile,
                "form": form,
            },
        )


class ManageLicenseTypesView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/manage_license_types.html"

    def test_func(self):
        return is_admin(self.request.user)

    def _context(self, form: LicenseTypeForm | None = None, editing: LicenseType | None = None) -> dict:
        license_types = LicenseType.objects.annotate(therapist_count=Count("therapists")).order_by("name")
        return {
            "form": form or LicenseTypeForm(),
            "editing": editing,
            "license_types": license_types,
            "active_page": "license_types",
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        edit_id = request.GET.get("edit")
        editing = None
        form = None
        if edit_id:
            editing = get_object_or_404(LicenseType, pk=edit_id)
            form = LicenseTypeForm(instance=editing)
        return render(request, self.template_name, self._context(form=form, editing=editing))

    def post(self, request: HttpRequest) -> HttpResponse:
        action = request.POST.get("action", "save")
        if action == "delete":
            object_id = request.POST.get("object_id")
            license_type = get_object_or_404(LicenseType, pk=object_id)
            name = license_type.name
            license_type.delete()
            messages.success(request, f"Removed license type '{name}'.")
            return redirect("accounts:license_types")

        object_id = request.POST.get("object_id")
        editing = get_object_or_404(LicenseType, pk=object_id) if object_id else None
        form = LicenseTypeForm(request.POST, instance=editing)
        if form.is_valid():
            license_type = form.save()
            verb = "updated" if editing else "added"
            messages.success(request, f"License type '{license_type.name}' {verb}.")
            return redirect("accounts:license_types")
        return render(request, self.template_name, self._context(form=form, editing=editing))


class ManageClientFocusesView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/manage_client_focuses.html"

    def test_func(self):
        return is_admin(self.request.user)

    def _context(self, form: ClientFocusForm | None = None, editing: ClientFocus | None = None) -> dict:
        client_focuses = ClientFocus.objects.annotate(therapist_count=Count("therapists")).order_by("name")
        return {
            "form": form or ClientFocusForm(),
            "editing": editing,
            "client_focuses": client_focuses,
            "active_page": "client_focuses",
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        edit_id = request.GET.get("edit")
        editing = None
        form = None
        if edit_id:
            editing = get_object_or_404(ClientFocus, pk=edit_id)
            form = ClientFocusForm(instance=editing)
        return render(request, self.template_name, self._context(form=form, editing=editing))

    def post(self, request: HttpRequest) -> HttpResponse:
        action = request.POST.get("action", "save")
        if action == "delete":
            object_id = request.POST.get("object_id")
            client_focus = get_object_or_404(ClientFocus, pk=object_id)
            name = client_focus.name
            client_focus.delete()
            messages.success(request, f"Removed client focus '{name}'.")
            return redirect("accounts:client_focuses")

        object_id = request.POST.get("object_id")
        editing = get_object_or_404(ClientFocus, pk=object_id) if object_id else None
        form = ClientFocusForm(request.POST, instance=editing)
        if form.is_valid():
            client_focus = form.save()
            verb = "updated" if editing else "added"
            messages.success(request, f"Client focus '{client_focus.name}' {verb}.")
            return redirect("accounts:client_focuses")
        return render(request, self.template_name, self._context(form=form, editing=editing))


class ActivateView(View):
    def get(self, request: HttpRequest, token: str) -> HttpResponse:
        conf = EmailConfirmation.objects.filter(token=token, used_at__isnull=True).first()
        if not conf:
            raise Http404("Invalid or expired activation link.")
        form = ActivationSetPasswordForm(user=conf.user)
        return render(request, "accounts/activate.html", {"form": form, "token": token})

    def post(self, request: HttpRequest, token: str) -> HttpResponse:
        conf = EmailConfirmation.objects.filter(token=token, used_at__isnull=True).select_related("user").first()
        if not conf:
            raise Http404("Invalid or expired activation link.")
        form = ActivationSetPasswordForm(conf.user, request.POST)
        if not form.is_valid():
            return render(request, "accounts/activate.html", {"form": form, "token": token})
        form.save()
        conf.used_at = timezone.now()
        conf.save(update_fields=["used_at"])
        login(request, conf.user)
        return redirect("profiles:profile_edit")


class LogoutView(View):
    """Explicit logout view to ensure session is cleared and redirect occurs reliably."""

    def get(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        next_url = request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect("core:home")

    def post(self, request: HttpRequest) -> HttpResponse:
        return self.get(request)


def _build_msal_client() -> msal.ConfidentialClientApplication:
    if not settings.AZURE_AD_ENABLED:
        raise Http404("Azure AD not configured.")
    if not settings.AZURE_AD_AUTHORITY or not settings.AZURE_AD_CLIENT_ID or not settings.AZURE_AD_CLIENT_SECRET:
        raise Http404("Azure AD credentials missing.")
    return msal.ConfidentialClientApplication(
        client_id=settings.AZURE_AD_CLIENT_ID,
        client_credential=settings.AZURE_AD_CLIENT_SECRET,
        authority=settings.AZURE_AD_AUTHORITY,
    )


def _azure_scopes() -> list[str]:
    # Provide only non-reserved scopes; MSAL will add openid/profile/offline_access automatically
    return ["email"]


class AzureLoginView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        if not settings.AZURE_AD_ENABLED:
            raise Http404("Azure AD not configured.")

        next_url = request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            request.session["azure_next"] = next_url

        cca = _build_msal_client()
        flow = cca.initiate_auth_code_flow(
            scopes=_azure_scopes(),
            redirect_uri=settings.AZURE_AD_REDIRECT_URI,
        )
        logger.info(
            "azure_login_flow",
            extra={
                "auth_uri": flow.get("auth_uri"),
                "host": request.get_host(),
                "redirect_uri": settings.AZURE_AD_REDIRECT_URI,
                "state": flow.get("state"),
            },
        )
        request.session["azure_auth_flow"] = flow
        cache.set(f"azure_flow:{flow.get('state')}", {"flow": flow, "next": request.session.get("azure_next")}, timeout=600)
        return redirect(flow["auth_uri"])


class AzureCallbackView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        if not settings.AZURE_AD_ENABLED:
            raise Http404("Azure AD not configured.")

        session_cookie_name = getattr(settings, "SESSION_COOKIE_NAME", "sessionid")
        session_cookie_val = request.COOKIES.get(session_cookie_name)
        raw_cookie_header = request.META.get("HTTP_COOKIE", "")
        has_session_cookie = bool(session_cookie_val)
        next_from_session_raw = request.session.get("azure_next")

        flow = request.session.pop("azure_auth_flow", None)
        cached = None
        if not flow:
            cached = cache.get(f"azure_flow:{request.GET.get('state')}") if request.GET.get("state") else None
            if cached:
                flow = cached.get("flow")
                logger.info(
                    "azure_callback_flow_restored_from_cache state=%s has_flow=%s has_cached_next=%s",
                    request.GET.get("state"),
                    bool(flow),
                    bool(cached.get("next")) if cached else False,
                )

        logger.info(
            (
                "azure_callback_start host=%s state=%s has_session_flow=%s has_cached_flow=%s "
                "session_key=%s has_session_cookie=%s session_cookie_len=%s next_session=%s "
                "next_cache=%s next_param=%s"
            ),
            request.get_host(),
            request.GET.get("state"),
            bool(flow),
            bool(cached),
            request.session.session_key,
            has_session_cookie,
            len(session_cookie_val) if session_cookie_val else 0,
            next_from_session_raw,
            cached.get("next") if cached else None,
            request.GET.get("next"),
        )
        logger.info("azure_callback_cookie_header %s", raw_cookie_header)

        if not flow:
            request.session.flush()
            messages.error(request, "Session expired. Please start sign-in again.")
            return redirect(reverse("accounts:azure_login"))

        if request.GET.get("state") != flow.get("state"):
            logger.warning("azure_login_state_mismatch", extra={"expected": flow.get("state"), "got": request.GET.get("state")})
            request.session.flush()
            cache.delete(f"azure_flow:{request.GET.get('state')}")
            messages.error(request, "Sign-in session mismatch. Please start sign-in again.")
            return redirect(reverse("accounts:azure_login"))

        cca = _build_msal_client()
        result = cca.acquire_token_by_auth_code_flow(flow, request.GET)
        if not result or "error" in result:
            logger.error(
                "azure_login_error",
                extra={
                    "error": result.get("error") if result else "unknown",
                    "description": result.get("error_description") if result else "unknown",
                },
            )
            return HttpResponse("Azure sign-in failed. Please try again.", status=400)

        claims = result.get("id_token_claims") or {}
        email = claims.get("preferred_username") or claims.get("email") or claims.get("upn")
        if not email:
            return HttpResponse("No email returned from Azure.", status=400)

        email = email.lower()

        # Keep username and email aligned to the Azure email, preferring an existing username match.
        username_match = User.objects.filter(username__iexact=email).first()
        email_match = User.objects.filter(email__iexact=email).first()

        if username_match is not None:
            user: User = username_match
        elif email_match is not None:
            user = email_match
        else:
            user = User.objects.create(username=email, email=email, is_active=True)

        # If a separate email-only user exists, log and keep the username-anchored record to avoid conflicts.
        if username_match and email_match and username_match.pk != email_match.pk:
            logger.warning(
                "azure_login_user_conflict",
                extra={"username_pk": username_match.pk, "email_pk": email_match.pk, "email": email},
            )

        # Sync core fields; only change username if it is safe to do so.
        username_conflict = User.objects.filter(username=email).exclude(pk=user.pk).exists()
        updates = {}
        if user.username.lower() != email and not username_conflict:
            user.username = email
            updates["username"] = email
        if user.email.lower() != email:
            user.email = email
            updates["email"] = email
        if not user.is_active:
            user.is_active = True
            updates["is_active"] = True
        if updates:
            user.save(update_fields=list(updates.keys()))

        # Ensure therapists can land on /therapists/edit/ without looping back to login.
        # Default any new Azure SSO account into the therapist group unless it already has an allowed role.
        if not user.groups.filter(name__in=["therapist", "admin", "office_manager"]).exists():
            therapist_group, _ = Group.objects.get_or_create(name="therapist")
            user.groups.add(therapist_group)

        # Explicit backend ensures Django persists auth without relying on prior authenticate()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        current_session_key = request.session.session_key
        logger.info(
            "azure_login_post_auth session_key=%s incoming_cookie_name=%s incoming_cookie_val=%s incoming_cookie_len=%s",
            current_session_key,
            session_cookie_name,
            session_cookie_val,
            len(session_cookie_val) if session_cookie_val else 0,
        )
        logger.info(
            "azure_login_success",
            extra={
                "user_id": user.pk,
                "user_email": user.email,
                "session_key": current_session_key,
                "session_cookie_domain": getattr(settings, "SESSION_COOKIE_DOMAIN", None),
                "session_cookie_samesite": getattr(settings, "SESSION_COOKIE_SAMESITE", None),
            },
        )
        request.session.save()
        session_cookie_domain = getattr(settings, "SESSION_COOKIE_DOMAIN", None)
        session_cookie_samesite = getattr(settings, "SESSION_COOKIE_SAMESITE", "Lax")
        session_cookie_secure = getattr(settings, "SESSION_COOKIE_SECURE", False)
        session_cookie_path = "/"
        next_from_session = request.session.pop("azure_next", None)
        next_from_cache = cached.get("next") if cached else None
        next_from_param = request.GET.get("next")

        resolved_next_source = None
        next_url = None
        if next_from_session and url_has_allowed_host_and_scheme(next_from_session, allowed_hosts={request.get_host()}):
            next_url = next_from_session
            resolved_next_source = "session"
        elif next_from_cache and url_has_allowed_host_and_scheme(next_from_cache, allowed_hosts={request.get_host()}):
            next_url = next_from_cache
            resolved_next_source = "cache"
        elif next_from_param and url_has_allowed_host_and_scheme(next_from_param, allowed_hosts={request.get_host()}):
            next_url = next_from_param
            resolved_next_source = "param"

        logger.info(
            "azure_callback_next_resolution session=%s cache=%s param=%s resolved_source=%s resolved=%s",
            next_from_session,
            next_from_cache,
            next_from_param,
            resolved_next_source,
            next_url,
        )
        response = redirect(next_url) if next_url else redirect(settings.LOGIN_REDIRECT_URL or "/")
        # Clear any stale host-only and domain cookies (common Safari duplication), then set the fresh session cookie explicitly.
        cookie_domains = [None]
        if session_cookie_domain:
            cookie_domains.extend({session_cookie_domain, session_cookie_domain.lstrip('.')})
        # Also clear legacy default name to prevent collisions when the name changes.
        legacy_cookie_name = "sessionid"
        clear_paths = {session_cookie_path, settings.AZURE_AD_REDIRECT_URI or "/accounts/azure/callback"}
        for dom in cookie_domains:
            for p in clear_paths:
                response.delete_cookie(session_cookie_name, domain=dom, path=p)
                response.delete_cookie(legacy_cookie_name, domain=dom, path=p)
        response.set_cookie(
            session_cookie_name,
            request.session.session_key,
            domain=session_cookie_domain,
            path=session_cookie_path,
            secure=session_cookie_secure,
            samesite=session_cookie_samesite,
            httponly=True,
            max_age=60 * 60 * 24,  # one-day persistence to encourage Safari to adopt
        )
        return response


class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm

    def get_success_url(self):
        next_url = self.get_redirect_url()
        if next_url:
            return next_url

        user = self.request.user
        try:
            is_therapist = user.groups.filter(name="therapist").exists()
        except Exception:
            is_therapist = False
        if is_therapist:
            return reverse("profiles:profile_edit")

        return reverse("core:home")
