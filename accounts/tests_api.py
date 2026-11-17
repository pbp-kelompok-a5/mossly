"""Uji kontrak Accounts untuk Flutter dan kompatibilitas dengan akun web."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase

from .models import UserProfile


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountsApiTests(APITestCase):
    password = "Rimbun!Lembah-7284"

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="pemilik", email="pemilik@example.test", password=cls.password
        )
        cls.other = User.objects.create_user(
            username="tetangga", email="tetangga@example.test", password=cls.password
        )
        cls.inactive = User.objects.create_user(
            username="nonaktif", password=cls.password, is_active=False
        )

    def setUp(self):
        self.register_url = reverse("accounts_api:register")
        self.login_url = reverse("accounts_api:login")
        self.logout_url = reverse("accounts_api:logout")
        self.me_url = reverse("accounts_api:me")

    def registration(self, **extra):
        return {
            "username": "pengguna_baru",
            "email": "baru@example.test",
            "display_name": "Nama Baru",
            "umur": 18,
            "password1": self.password,
            "password2": self.password,
            **extra,
        }

    def authenticate(self, user=None):
        token, _ = Token.objects.get_or_create(user=user or self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        return token

    def test_register_creates_hashed_password_profile_and_usable_token(self):
        response = self.client.post(self.register_url, self.registration(), format="json")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        user = get_user_model().objects.get(username="pengguna_baru")
        self.assertTrue(user.check_password(self.password))
        self.assertNotEqual(user.password, self.password)
        self.assertEqual(data["token"], Token.objects.get(user=user).key)
        self.assertEqual(data["user"]["id"], user.pk)
        self.assertEqual(data["user"]["username"], user.username)
        self.assertEqual(data["user"]["email"], "baru@example.test")
        self.assertEqual(data["user"]["display_name"], "Nama Baru")
        self.assertEqual(data["user"]["umur"], 18)
        self.assertFalse(data["user"]["is_onboarded"])
        self.assertIsNone(data["user"]["onboarded_at"])
        self.assertIn("no-store", response["Cache-Control"])
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {data["token"]}')
        self.assertEqual(self.client.get(self.me_url).json(), data["user"])
        self.assertNotIn(self.password, response.content.decode())
        for key in ("password", "password1", "password2", "is_staff", "is_superuser"):
            self.assertNotIn(key, data["user"])

    def test_register_uses_web_normalisation(self):
        data = self.registration(username="ｎｅｗ＿ｕｓｅｒ", email="NORMAL@example.test")
        response = self.client.post(self.register_url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["username"], "new_user")
        self.assertEqual(response.json()["user"]["email"], "normal@example.test")

    def test_register_rejects_duplicate_username_case_insensitively(self):
        before = get_user_model().objects.count()
        for username in ["pemilik", "PEMILIK", "ｐｅｍｉｌｉｋ"]:
            with self.subTest(username=username):
                response = self.client.post(
                    self.register_url, self.registration(username=username), format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("username", response.json())
        self.assertEqual(get_user_model().objects.count(), before)

    def test_register_reuses_email_validation(self):
        for email in ["PEMILIK@example.test", "invalid-email", "x" * 255 + "@example.test"]:
            with self.subTest(email=email):
                response = self.client.post(
                    self.register_url, self.registration(email=email), format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("email", response.json())
        self.assertFalse(get_user_model().objects.filter(username="pengguna_baru").exists())

    def test_register_rejects_invalid_age_and_missing_fields(self):
        for age in [None, "", 17, -1, "seventeen", 18.5, True, 32768, 10**30]:
            with self.subTest(age=age):
                response = self.client.post(
                    self.register_url, self.registration(umur=age), format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("umur", response.json())
        response = self.client.post(self.register_url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        for field in self.registration():
            self.assertIn(field, response.json())
        self.assertFalse(get_user_model().objects.filter(username="pengguna_baru").exists())

    def test_register_reuses_password_and_name_validation(self):
        cases = [
            {"password2": "different-password"},
            {"password1": "123", "password2": "123"},
            {"password1": "password", "password2": "password"},
            {"password1": "pengguna_baru", "password2": "pengguna_baru"},
            {"display_name": ""}, {"display_name": "x" * 81},
            {"username": "not valid"}, {"username": "x" * 151},
        ]
        for extra in cases:
            with self.subTest(fields=list(extra)):
                response = self.client.post(
                    self.register_url, self.registration(**extra), format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertFalse(get_user_model().objects.filter(username="pengguna_baru").exists())

    def test_register_ignores_privileged_fields(self):
        response = self.client.post(self.register_url, self.registration(
            is_staff=True, is_superuser=True, user_id=self.other.pk,
            is_onboarded=True, onboarded_at="2026-11-17T00:00:00Z",
        ), format="json")
        self.assertEqual(response.status_code, 201)
        user = get_user_model().objects.get(username="pengguna_baru")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.profile.is_onboarded)
        self.assertIsNone(user.profile.onboarded_at)
        self.assertEqual(response.json()["user"]["id"], user.pk)

    @patch("accounts.api_views.Token.objects.get_or_create", side_effect=IntegrityError)
    def test_register_rolls_back_if_token_creation_fails(self, _token):
        users_before = get_user_model().objects.count()
        profiles_before = UserProfile.objects.count()
        response = self.client.post(self.register_url, self.registration(), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(get_user_model().objects.count(), users_before)
        self.assertEqual(UserProfile.objects.count(), profiles_before)

    def test_api_registered_account_can_login_through_existing_web(self):
        self.assertEqual(
            self.client.post(self.register_url, self.registration(), format="json").status_code,
            201,
        )
        response = self.client.post(reverse("accounts:login"), {
            "username": "pengguna_baru", "password": self.password,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("accounts:onboarding"))

    def test_web_registered_account_can_login_through_api(self):
        self.assertEqual(
            self.client.post(reverse("accounts:register"), self.registration()).status_code,
            302,
        )
        self.client.logout()
        response = self.client.post(self.login_url, {
            "username": "pengguna_baru", "password": self.password,
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], "pengguna_baru")
        self.assertEqual(len(response.json()["token"]), 40)

    def test_login_returns_same_existing_token(self):
        before = self.authenticate()
        self.client.credentials()
        for _ in range(2):
            response = self.client.post(self.login_url, {
                "username": "pemilik", "password": self.password,
            }, format="json")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["token"], before.key)
            self.assertEqual(response.json()["user"]["id"], self.user.pk)
            self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(Token.objects.filter(user=self.user).count(), 1)

    def test_login_rejects_unknown_inactive_and_wrong_password_consistently(self):
        responses = []
        for username, password in [
            ("unknown", self.password), ("nonaktif", self.password), ("pemilik", "wrong"),
        ]:
            response = self.client.post(self.login_url, {
                "username": username, "password": password,
            }, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("non_field_errors", response.json())
            self.assertNotIn("token", response.json())
            responses.append(response.json())
        self.assertEqual(responses[0], responses[1])
        self.assertEqual(responses[0], responses[2])
        self.assertFalse(Token.objects.exists())

    def test_login_preserves_password_spaces(self):
        user = get_user_model().objects.create_user("spasi", password=" Rimbun!-7284 ")
        response = self.client.post(self.login_url, {
            "username": user.username, "password": " Rimbun!-7284 ",
        }, format="json")
        self.assertEqual(response.status_code, 200)

    def test_login_rejects_missing_credentials(self):
        response = self.client.post(self.login_url, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())
        self.assertIn("password", response.json())

    def test_logout_revokes_only_current_user_token(self):
        token = self.authenticate()
        old_key = token.key
        other = Token.objects.create(user=self.other)
        response = self.client.post(self.logout_url, {"user_id": self.other.pk}, format="json")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertFalse(Token.objects.filter(user=self.user).exists())
        self.assertTrue(Token.objects.filter(key=other.key).exists())
        self.assertEqual(self.client.get(self.me_url).status_code, 401)
        self.client.credentials()
        logged_in = self.client.post(self.login_url, {
            "username": "pemilik", "password": self.password,
        }, format="json")
        self.assertEqual(logged_in.status_code, 200)
        self.assertNotEqual(logged_in.json()["token"], old_key)

    def test_logout_and_me_require_authentication(self):
        self.assertEqual(self.client.post(self.logout_url, {}, format="json").status_code, 401)
        self.assertEqual(self.client.get(self.me_url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Token not-a-real-token")
        self.assertEqual(self.client.post(self.logout_url, {}, format="json").status_code, 401)
        self.assertEqual(self.client.get(self.me_url).status_code, 401)

    def test_me_returns_current_user_only_and_preserves_legacy_profile_support(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.me_url, {"user_id": self.other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["id"], self.user.pk)
        self.assertEqual(response.json()["username"], "pemilik")
        self.assertNotIn(self.other.email, response.content.decode())
        self.assertNotIn("password", response.json())
        self.assertIn("no-store", response["Cache-Control"])
        UserProfile.objects.filter(user=self.user).delete()
        self.assertEqual(self.client.get(self.me_url).status_code, 200)
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_me_includes_real_preferences(self):
        from carbon.models import TransportMode
        profile = self.user.profile
        profile.primary_mode = TransportMode.objects.get(code="jalan")
        profile.focus_areas = ["energi"]
        profile.share_achievements = False
        profile.save()
        self.authenticate()
        data = self.client.get(self.me_url).json()
        self.assertEqual(data["primary_mode"]["code"], "jalan")
        self.assertEqual(data["focus_areas"], ["energi"])
        self.assertFalse(data["share_achievements"])

    def test_inactive_user_token_is_rejected(self):
        self.authenticate(self.inactive)
        self.assertEqual(self.client.get(self.me_url).status_code, 401)

    def test_session_authentication_still_works_without_changing_web_logout(self):
        self.client.force_login(self.user)
        token = Token.objects.create(user=self.user)
        self.assertEqual(self.client.get(self.me_url).status_code, 200)
        self.assertEqual(self.client.post(self.logout_url, {}, format="json").status_code, 204)
        self.assertFalse(Token.objects.filter(key=token.key).exists())
        self.assertEqual(self.client.get(self.me_url).status_code, 200)

    def test_public_api_registration_does_not_require_web_csrf_cookie(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(self.register_url, self.registration(), format="json")
        self.assertEqual(response.status_code, 201)
        client.credentials(HTTP_AUTHORIZATION=f'Token {response.json()["token"]}')
        self.assertEqual(client.post(self.logout_url, {}, format="json").status_code, 204)

    def test_unsupported_methods_are_rejected(self):
        self.authenticate()
        for url in [self.register_url, self.login_url, self.logout_url]:
            self.assertEqual(self.client.get(url).status_code, 405)
        for method in [self.client.post, self.client.patch, self.client.delete]:
            self.assertEqual(method(self.me_url, {}, format="json").status_code, 405)
