from urllib.parse import quote as urlquote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Group, User
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.core.mail import send_mail
from django.db.models import Count
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .forms import (
    ActivationSetPasswordForm,
    InviteUserForm,
    ServiceForm,
    PaymentFeeRowForm,
    FAQItemForm,
    WhatWeDoItemForm,
    WhatWeDoSectionForm,
    AboutSectionForm,
    OurPhilosophyForm,
    InspirationalQuoteForm,
    CompanyQuoteForm,
    ContactInfoForm,
    StaticPageSEOForm,
)
from .models import EmailConfirmation
from core.models import (
    Service,
    PaymentFeeRow,
    FAQItem,
    WhatWeDoItem,
    WhatWeDoSection,
    AboutSection,
    OurPhilosophy,
    InspirationalQuote,
    CompanyQuote,
    ContactInfo,
    StaticPageSEO,
)
from profiles.forms import AdminTherapistProfileForm, ClientFocusForm, LicenseTypeForm
from profiles.models import ClientFocus, LicenseType, TherapistProfile


def is_admin(user: User) -> bool:
    return user.is_superuser or user.groups.filter(name="admin").exists()


def _create_user_invitation(
    email: str,
    is_admin_flag: bool,
    is_therapist_flag: bool,
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
    if is_admin_flag:
        user.groups.add(admin_group)
    if is_therapist_flag:
        user.groups.add(therapist_group)

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

        _user, _profile, token = _create_user_invitation(email, is_admin_flag, is_therapist_flag)
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
            redirect_target = reverse("accounts:invite")
        except Exception:
            if not settings.DEBUG:
                raise
            messages.success(request, f"Invitation ready for {email}.")
            redirect_target = reverse("accounts:invite")

        if settings.DEBUG:
            redirect_target = f"{redirect_target}?activation_url={urlquote(activate_url)}&email={urlquote(email)}"
        return redirect(redirect_target)


class ManageTherapistsView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = "accounts/manage_therapists.html"

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
    ) -> dict:
        invite_form = form or InviteUserForm(initial={"is_therapist": True})
        therapists = (
            TherapistProfile.objects.select_related("user", "license_type")
            .prefetch_related("client_focuses")
            .order_by("last_name", "first_name", "pk")
        )
        unassigned_users = (
            User.objects.filter(groups__name="therapist")
            .filter(therapist_profile__isnull=True)
            .order_by("email")
            .distinct()
        )
        payment_fees = PaymentFeeRow.objects.order_by("category", "order", "id")
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
        contact_section = ContactInfo.objects.order_by("id").first()
        if not contact_section:
            contact_section = ContactInfo.objects.create()
        return {
            "invite_form": invite_form,
            "therapists": therapists,
            "unassigned_users": unassigned_users,
            "debug_activation_url": debug_activation_url,
            "debug_activation_email": debug_email,
            "payment_fees": payment_fees,
            "payment_fee_form": fee_form or PaymentFeeRowForm(),
            "payment_fee_editing": editing_fee,
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
        edit_faq_id = request.GET.get("edit_faq")
        edit_whatwedo_item_id = request.GET.get("edit_whatwedo_item")
        editing_fee = None
        fee_form = None
        editing_faq = None
        faq_form = None
        editing_whatwedo_item = None
        whatwedo_item_form = None
        if edit_fee_id:
            editing_fee = get_object_or_404(PaymentFeeRow, pk=edit_fee_id)
            fee_form = PaymentFeeRowForm(instance=editing_fee)
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
            faq_form=faq_form,
            editing_faq=editing_faq,
            whatwedo_item_form=whatwedo_item_form,
            editing_whatwedo_item=editing_whatwedo_item,
        )
        return render(request, self.template_name, ctx)

    def post(self, request: HttpRequest) -> HttpResponse:
        action = request.POST.get("action")

        if action == "invite":
            form = InviteUserForm(request.POST)
            if not form.is_valid():
                ctx = self._build_context(request, form=form)
                return render(request, self.template_name, ctx)

            email = form.cleaned_data["email"].lower()
            is_admin_flag = form.cleaned_data["is_admin"]
            is_therapist_flag = form.cleaned_data["is_therapist"]
            _user, _profile, token = _create_user_invitation(email, is_admin_flag, is_therapist_flag)
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

            redirect_url = reverse("accounts:therapists")
            if settings.DEBUG:
                redirect_url = f"{redirect_url}?activation_url={urlquote(activate_url)}&email={urlquote(email)}"
            return redirect(redirect_url)

        if action == "payment_save":
            object_id = request.POST.get("object_id")
            editing_fee = get_object_or_404(PaymentFeeRow, pk=object_id) if object_id else None
            fee_form = PaymentFeeRowForm(request.POST, instance=editing_fee)
            if fee_form.is_valid():
                saved = fee_form.save()
                verb = "updated" if editing_fee else "added"
                messages.success(request, f"Fee row '{saved.name}' {verb}.")
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                fee_form=fee_form,
                editing_fee=editing_fee,
            )
            return render(request, self.template_name, ctx)

        if action == "payment_delete":
            object_id = request.POST.get("object_id")
            row = get_object_or_404(PaymentFeeRow, pk=object_id)
            name = row.name
            row.delete()
            messages.success(request, f"Deleted fee row '{name}'.")
            return redirect("accounts:therapists")

        if action == "faq_save":
            object_id = request.POST.get("object_id")
            editing_faq = get_object_or_404(FAQItem, pk=object_id) if object_id else None
            faq_form = FAQItemForm(request.POST, instance=editing_faq)
            if faq_form.is_valid():
                saved = faq_form.save()
                verb = "updated" if editing_faq else "added"
                messages.success(request, f"FAQ '{saved.question}' {verb}.")
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                faq_form=faq_form,
                editing_faq=editing_faq,
            )
            return render(request, self.template_name, ctx)

        if action == "faq_delete":
            object_id = request.POST.get("object_id")
            row = get_object_or_404(FAQItem, pk=object_id)
            name = row.question
            row.delete()
            messages.success(request, f"Deleted FAQ '{name}'.")
            return redirect("accounts:therapists")

        if action == "about_save":
            section = AboutSection.objects.order_by("id").first()
            if not section:
                section = AboutSection.objects.create()
            about_form = AboutSectionForm(request.POST, instance=section)
            if about_form.is_valid():
                saved = about_form.save()
                messages.success(request, f"Updated '{saved.about_title}' content.")
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                about_section_form=about_form,
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
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                philosophy_form=philosophy_form,
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
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                inspirational_form=inspirational_form,
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
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                company_form=company_form,
            )
            return render(request, self.template_name, ctx)

        if action == "contact_save":
            section = ContactInfo.objects.order_by("id").first()
            if not section:
                section = ContactInfo.objects.create()
            contact_form = ContactInfoForm(request.POST, instance=section)
            if contact_form.is_valid():
                saved = contact_form.save()
                messages.success(request, "Updated contact section content.")
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                contact_form=contact_form,
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
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                whatwedo_section_form=section_form,
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
                return redirect("accounts:therapists")

            ctx = self._build_context(
                request,
                whatwedo_item_form=item_form,
                editing_whatwedo_item=editing_item,
            )
            return render(request, self.template_name, ctx)

        if action == "whatwedo_item_delete":
            object_id = request.POST.get("object_id")
            row = get_object_or_404(WhatWeDoItem, pk=object_id)
            name = row.text
            row.delete()
            messages.success(request, f"Deleted What We Do item '{name}'.")
            return redirect("accounts:therapists")

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
            return redirect("accounts:therapists")

        if action == "delete_therapist":
            profile_id = request.POST.get("profile_id")
            profile = get_object_or_404(TherapistProfile, pk=profile_id)
            name = profile.display_name or profile.user.email or "therapist"
            user = profile.user
            therapist_group = Group.objects.filter(name="therapist").first()
            profile.delete()
            if therapist_group:
                user.groups.remove(therapist_group)
            messages.success(request, f"Deleted therapist profile for {name}.")
            return redirect("accounts:therapists")

        if action == "create_profile":
            user_id = request.POST.get("user_id")
            user = get_object_or_404(User, pk=user_id)
            profile, created = TherapistProfile.objects.get_or_create(user=user)
            if created:
                messages.success(request, f"Profile created for {user.email}.")
            else:
                messages.info(request, f"{user.email} already has a profile.")
            return redirect("accounts:therapists")

        messages.error(request, "Unsupported action.")
        return redirect("accounts:therapists")


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
        contact_info = ContactInfo.objects.order_by("id").first()
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
            contact_info = ContactInfo.objects.order_by("id").first()
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
        return redirect("home")

    def post(self, request: HttpRequest) -> HttpResponse:
        return self.get(request)


class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"

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

        return reverse("home")
