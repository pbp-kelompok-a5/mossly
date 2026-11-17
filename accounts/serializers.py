"""Kontrak JSON Accounts, memakai validasi form web yang sudah ada."""
from django.contrib.auth import get_user_model
from django.core.exceptions import NON_FIELD_ERRORS
from rest_framework import serializers
from rest_framework.settings import api_settings

from carbon.models import TransportMode
from .forms import LoginForm, RegisterForm
from .models import UserProfile


def form_errors(form):
    """Ubah error Django Form ke bentuk error field standar DRF."""
    return {
        api_settings.NON_FIELD_ERRORS_KEY if name == NON_FIELD_ERRORS else name: list(messages)
        for name, messages in form.errors.items()
    }


class RegisterSerializer(serializers.ModelSerializer):
    # Deklarasi eksplisit memberi RegisterForm kesempatan menjalankan normalisasi
    # username, validasi email, umur, dan password persis seperti registrasi web.
    username = serializers.CharField()
    email = serializers.CharField()
    display_name = serializers.CharField(write_only=True)
    # Rentang PositiveSmallIntegerField harus aman juga saat deploy PostgreSQL.
    umur = serializers.IntegerField(write_only=True, min_value=18, max_value=32767)
    password1 = serializers.CharField(write_only=True, trim_whitespace=False)
    password2 = serializers.CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "display_name", "umur", "password1", "password2")

    def validate(self, attrs):
        self.registration_form = RegisterForm(data=attrs)
        if not self.registration_form.is_valid():
            raise serializers.ValidationError(form_errors(self.registration_form))
        return attrs

    def create(self, validated_data):
        # save() form melakukan hashing password dan menyimpan UserProfile.
        return self.registration_form.save()


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        form = LoginForm(request=self.context.get("request"), data=attrs)
        if not form.is_valid():
            raise serializers.ValidationError(form_errors(form))
        attrs["user"] = form.get_user()
        return attrs


class TransportModeSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportMode
        fields = ("id", "code", "name")
        read_only_fields = fields


class CurrentUserSerializer(serializers.ModelSerializer):
    """Data akun sendiri; tanpa password, izin admin, atau data pengguna lain."""
    id = serializers.IntegerField(source="user_id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    primary_mode = TransportModeSummarySerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = (
            "id", "username", "email", "display_name", "umur", "avatar",
            "is_onboarded", "onboarded_at", "primary_mode", "focus_areas",
            "share_achievements",
        )
        read_only_fields = fields
