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

from .forms import ActivationSetPasswordForm, InviteUserForm, ServiceForm
from .models import EmailConfirmation
from core.models import Service
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

        subject = "You're invited to Lake Country Psychology"
        body = (
            "Hi,\n\nAn account was created for you on Lake Country Psychology.\n"
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
        return {
            "invite_form": invite_form,
            "therapists": therapists,
            "unassigned_users": unassigned_users,
            "debug_activation_url": debug_activation_url,
            "debug_activation_email": debug_email,
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        debug_activation_url = request.GET.get("activation_url", "") if settings.DEBUG else ""
        debug_email = request.GET.get("email", "") if settings.DEBUG else ""
        ctx = self._build_context(
            request,
            debug_activation_url=debug_activation_url,
            debug_email=debug_email,
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

            subject = "You're invited to Lake Country Psychology"
            body = (
                "Hi,\n\nAn account was created for you on Lake Country Psychology.\n"
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

    def post(self, request: HttpRequest) -> HttpResponse:
        action = request.POST.get("action", "save")
        if action == "delete":
            object_id = request.POST.get("object_id")
            service = get_object_or_404(Service, pk=object_id)
            title = service.title
            if service.background_image:
                service.background_image.delete(save=False)
            service.delete()
            messages.success(request, f"Removed service '{title}'.")
            return redirect("accounts:services")

        object_id = request.POST.get("object_id")
        editing = get_object_or_404(Service, pk=object_id) if object_id else None
        form = ServiceForm(request.POST, request.FILES, instance=editing)
        if form.is_valid():
            service = form.save()
            verb = "updated" if editing else "created"
            messages.success(request, f"Service '{service.title}' {verb}.")
            return redirect("accounts:services")

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
