from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.validators import MaxLengthValidator
from django.db import transaction
from django.urls import reverse

from carbon.models import TransportMode
from .models import UserProfile


class LoginForm(AuthenticationForm):
    """Validasi autentikasi Django dengan pesan berbahasa Indonesia."""

    error_messages = {
        "invalid_login": "Username atau password salah. Silakan coba lagi.",
        "inactive": "Username atau password salah. Silakan coba lagi.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].error_messages.update({
            "required": "Masukkan username.",
            "max_length": "Username maksimal %(limit_value)s karakter.",
        })
        self.fields["password"].error_messages["required"] = "Masukkan password."
        # AuthenticationForm mengatur maxlength widget dari model; tambahkan
        # batas yang sama pada validasi server untuk request POST langsung.
        self.fields["username"].validators.append(
            MaxLengthValidator(self.fields["username"].max_length)
        )



class RegisterForm(UserCreationForm):
    email = forms.EmailField(label="Email", max_length=254)
    display_name = forms.CharField(label="Nama tampilan", max_length=80)
    umur = forms.IntegerField(
        label="Umur", min_value=18,
        help_text="Minimal 18 tahun untuk membuat akun.",
        error_messages={"min_value": "Umur minimal 18 tahun."},
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "umur", "display_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configure_fields(self)
        self.fields["username"].label = "Username"
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Konfirmasi password"
        self.fields["username"].widget.attrs["autocomplete"] = "username"
        self.fields["username"].widget.attrs.update({
            "hx-get": reverse("accounts:check_username"),
            "hx-trigger": "input changed delay:400ms",
            "hx-target": "#username-availability",
            "hx-swap": "innerHTML",
            "hx-params": "username",
            "hx-sync": "this:replace",
            "hx-indicator": "#username-check-indicator",
            "aria-describedby": "id_username_helptext id_username_error username-availability",
        })
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["display_name"].widget.attrs["autocomplete"] = "nickname"
        for name in ("password1", "password2"):
            self.fields[name].widget.attrs["autocomplete"] = "new-password"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        # Kesepakatan MVP: validasi jalur registrasi; User.email bawaan
        # belum memiliki unique constraint. Jangan ubah skema auth kelompok.
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email ini sudah digunakan.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.display_name = self.cleaned_data["display_name"]
            profile.umur = self.cleaned_data["umur"]
            profile.save(update_fields=["display_name", "umur"])
        return user


def configure_fields(form):
    for name, field in form.fields.items():
        field.error_messages["required"] = "Bagian ini wajib diisi."
        field.error_messages["invalid"] = "Masukkan nilai yang valid."
        field.error_messages["max_length"] = "Maksimal %(limit_value)s karakter."
        if isinstance(field.widget, forms.CheckboxSelectMultiple):
            field.widget.attrs["class"] = "auth-choice-list"
        elif isinstance(field.widget, forms.CheckboxInput):
            field.widget.attrs["class"] = "auth-checkbox"
        else:
            field.widget.attrs["class"] = "input"
        field.widget.attrs["aria-describedby"] = f"id_{name}_helptext id_{name}_error"


class PreferencesForm(forms.ModelForm):
    focus_areas = forms.MultipleChoiceField(
        label="Area fokus", choices=UserProfile.FocusArea.choices,
        widget=forms.CheckboxSelectMultiple, required=False,
        help_text="Pilih hal yang ingin kamu mulai. Boleh lebih dari satu atau kosong.",
    )

    class Meta:
        model = UserProfile
        fields = ("avatar", "primary_mode", "focus_areas", "share_achievements")
        labels = {"avatar": "Avatar", "primary_mode": "Moda transportasi utama",
                  "share_achievements": "Bagikan achievement ke komunitas"}
        help_texts = {
            "primary_mode": "Opsional. Pilihan ini menjadi preferensi awal, bukan catatan perjalanan.",
            "share_achievements": "Jika dimatikan, achievement tetap didapat tanpa post otomatis.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["primary_mode"].queryset = TransportMode.objects.filter(is_active=True)
        self.fields["primary_mode"].empty_label = "Belum memilih"
        configure_fields(self)


class ProfileForm(PreferencesForm):
    class Meta(PreferencesForm.Meta):
        fields = ("display_name", *PreferencesForm.Meta.fields)
        labels = {**PreferencesForm.Meta.labels, "display_name": "Nama tampilan"}


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label="Password saat ini", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    confirm = forms.BooleanField(
        label="Saya memahami bahwa akun dan data terkait akan dihapus permanen.",
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        configure_fields(self)
        self.fields["confirm"].error_messages["required"] = "Centang persetujuan penghapusan akun."

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("Password tidak sesuai.")
        return password
