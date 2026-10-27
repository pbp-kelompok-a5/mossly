from django.contrib.auth.forms import AuthenticationForm
from django.core.validators import MaxLengthValidator


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
