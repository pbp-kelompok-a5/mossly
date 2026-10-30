from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters

from .forms import DeleteAccountForm, LoginForm, PreferencesForm, ProfileForm, RegisterForm
from .models import UserProfile


def get_profile(user):
    profile, _ = UserProfile.objects.get_or_create(
        user=user, defaults={"display_name": user.get_full_name()[:80] or user.get_username()[:80]}
    )
    return profile


def account_destination(user):
    return "dashboard:index" if get_profile(user).is_onboarded else "accounts:onboarding"


class AccountsLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        target = super().get_success_url()
        if not get_profile(self.request.user).is_onboarded:
            self.request.session["accounts_onboarding_next"] = target
            return reverse("accounts:onboarding")
        return target

    def get_redirect_url(self):
        # LoginView sudah menolak host asing. Hindari juga putaran redirect
        # ke halaman autentikasi sendiri lewat parameter next.
        target = super().get_redirect_url()
        auth_paths = {
            reverse("accounts:login"),
            reverse("accounts:register"),
            reverse("accounts:logout"),
            reverse("accounts:onboarding"),
            reverse("accounts:delete"),
        }
        if urlsplit(target).path.rstrip("/") in {
            path.rstrip("/") for path in auth_paths
        }:
            return ""
        return target


login_view = AccountsLoginView.as_view()


@sensitive_post_parameters("password1", "password2")
@never_cache
@require_http_methods(["GET", "POST"])
@csrf_protect
def register_view(request):
    if request.user.is_authenticated:
        return redirect(account_destination(request.user))
    with translation.override("id"):
        form = RegisterForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
            except IntegrityError:
                form.add_error(None, "Akun tidak dapat dibuat. Periksa username dan coba lagi.")
            else:
                login(request, user)
                return redirect("accounts:onboarding")
        return render(request, "accounts/register.html", {"form": form})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def onboarding_view(request):
    profile = get_profile(request.user)
    if profile.is_onboarded:
        return redirect("dashboard:index")
    with translation.override("id"):
        form = PreferencesForm(request.POST if request.method == "POST" else None, instance=profile)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                # Lock mencegah pengiriman ulang mengganti hasil onboarding yang selesai.
                current = UserProfile.objects.select_for_update().get(pk=profile.pk)
                if not current.is_onboarded:
                    for name in form.Meta.fields:
                        setattr(current, name, form.cleaned_data[name])
                    current.is_onboarded = True
                    current.onboarded_at = timezone.now()
                    current.full_clean()
                    current.save()
            target = request.session.pop("accounts_onboarding_next", "")
            if (url_has_allowed_host_and_scheme(target, {request.get_host()}, require_https=request.is_secure())
                    and urlsplit(target).path.rstrip("/") not in {
                        reverse(f"accounts:{name}").rstrip("/")
                        for name in ("login", "register", "onboarding", "logout", "delete")
                    }):
                return redirect(target)
            return redirect("dashboard:index")
        return render(request, "accounts/onboarding.html", {"form": form})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def profile_view(request):
    profile = get_profile(request.user)
    if not profile.is_onboarded:
        return redirect("accounts:onboarding")
    with translation.override("id"):
        form = ProfileForm(request.POST if request.method == "POST" else None, instance=profile)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Profil berhasil disimpan.")
            return redirect("accounts:profile")
        return render(request, "accounts/profile.html", {"form": form, "profile": profile})


@never_cache
@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def logout_view(request):
    if request.method == "POST":
        logout(request)
        return redirect("main:landing")
    return render(request, "accounts/logout.html")


@never_cache
@require_http_methods(["GET"])
def check_username(request):
    raw_username = request.GET.get("username", "")
    state, message = "empty", "Ketik username untuk memeriksa ketersediaan."
    if raw_username.strip():
        with translation.override("id"):
            field = RegisterForm().fields["username"]
            try:
                username = field.clean(raw_username)
                # UserCreationForm juga memvalidasi model saat _post_clean;
                # jalur hint harus menjalankan validator username model yang sama.
                username = get_user_model()._meta.get_field("username").clean(username, None)
            except ValidationError as error:
                state, message = "invalid", error.messages[0]
            else:
                if get_user_model().objects.filter(username__iexact=username).exists():
                    state, message = "taken", "Username sudah digunakan."
                else:
                    state, message = "available", "Username tersedia. Ketersediaan diperiksa ulang saat daftar."
    return render(request, "accounts/_username_availability.html", {"state": state, "message": message})


@never_cache
@require_http_methods(["GET"])
def current_user_json(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Silakan login terlebih dahulu."}, status=401)
    profile = UserProfile.objects.select_related("primary_mode").filter(user=request.user).first()
    if profile is None:
        return JsonResponse({"error": "Profil belum tersedia."}, status=404)
    mode = profile.primary_mode
    return JsonResponse({
        "id": request.user.pk,
        "username": request.user.get_username(),
        "display_name": profile.display_name,
        "avatar": profile.avatar,
        "umur": profile.umur,
        "is_onboarded": profile.is_onboarded,
        "onboarded_at": profile.onboarded_at,
        "primary_mode": {"id": mode.pk, "code": mode.code, "name": mode.name} if mode else None,
        "focus_areas": profile.focus_areas,
        "share_achievements": profile.share_achievements,
    })


@sensitive_post_parameters("password")
@never_cache
@login_required
@require_http_methods(["GET", "POST"])
@csrf_protect
def delete_account(request):
    with translation.override("id"):
        form = DeleteAccountForm(request.user, request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                user = get_object_or_404(get_user_model().objects.select_for_update(), pk=request.user.pk)
                # Periksa ulang jika password berubah saat request sedang diproses.
                if user.check_password(form.cleaned_data["password"]):
                    user.delete()
                    deleted = True
                else:
                    form.add_error("password", "Password tidak sesuai.")
                    deleted = False
            if deleted:
                logout(request)
                return redirect("main:landing")
        return render(request, "accounts/delete_account.html", {"form": form})
