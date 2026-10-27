from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import UserProfile


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="sheva_test", password="Test-password-123"
        )
        UserProfile.objects.filter(user=cls.user).update(is_onboarded=True, onboarded_at=timezone.now())
        get_user_model().objects.create_user(
            username="inactive_test", password="Test-password-123", is_active=False
        )

    def setUp(self):
        self.login_url = reverse("accounts:login")
        self.logout_url = reverse("accounts:logout")
        self.dashboard_url = reverse("dashboard:index")

    def credentials(self, **extra):
        return {"username": self.user.username, "password": "Test-password-123", **extra}

    def test_login_is_public_and_uses_shared_styles(self):
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        positions = [html.index(path) for path in [
            "css/tokens.css", "css/global.css", "css/components.css", "accounts/css/login.css"
        ]]
        self.assertEqual(positions, sorted(positions))
        self.assertContains(response, 'type="password"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertNotContains(response, "pratinjau")

    def test_valid_login_establishes_session_and_renders_dashboard(self):
        response = self.client.post(self.login_url, self.credentials(), follow=True)
        self.assertEqual(response.redirect_chain, [(self.dashboard_url, 302)])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.user.pk))
        self.assertContains(response, "sheva_test")
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)
        self.assertEqual(self.client.get(self.dashboard_url).status_code, 200)

    def test_bad_password_preserves_only_username(self):
        response = self.client.post(self.login_url, self.credentials(password="wrong-secret"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Username atau password salah.")
        self.assertContains(response, 'value="sheva_test"')
        self.assertNotContains(response, "wrong-secret")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_unknown_and_inactive_users_get_same_error(self):
        for username in ["unknown_test", "inactive_test"]:
            with self.subTest(username=username):
                response = self.client.post(self.login_url, self.credentials(username=username))
                self.assertContains(response, "Username atau password salah.")
                self.assertNotIn(SESSION_KEY, self.client.session)

    def test_empty_fields_are_validated_on_server(self):
        response = self.client.post(self.login_url, {})
        self.assertContains(response, "Masukkan username.")
        self.assertContains(response, "Masukkan password.")
        self.assertContains(response, 'aria-invalid="true"', count=2)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_long_username_has_indonesian_error(self):
        response = self.client.post(self.login_url, self.credentials(username="x" * 151))
        self.assertContains(response, "Username maksimal 150 karakter.")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_username_is_escaped_when_redisplayed(self):
        response = self.client.post(self.login_url, self.credentials(username='<script>alert(1)</script>'))
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")

    def test_safe_next_survives_get_and_post(self):
        target = reverse("carbon:index") + "?period=week"
        response = self.client.get(self.login_url, {"next": target})
        self.assertContains(response, f'name="next" value="{target}"')
        response = self.client.post(self.login_url, self.credentials(next=target))
        self.assertRedirects(response, target, fetch_redirect_response=False)

    def test_unsafe_or_auth_next_falls_back_to_dashboard(self):
        for target in [
            "https://evil.example/", "//evil.example/", "javascript:alert(1)",
            self.login_url, self.login_url + "?next=/", self.logout_url,
            reverse("accounts:register"),
        ]:
            with self.subTest(target=target):
                client = Client()
                response = client.post(self.login_url, self.credentials(next=target))
                self.assertRedirects(response, self.dashboard_url, fetch_redirect_response=False)

    def test_https_login_cannot_redirect_to_http(self):
        response = self.client.post(
            self.login_url, self.credentials(next="http://testserver/dashboard/"), secure=True
        )
        self.assertRedirects(response, self.dashboard_url, fetch_redirect_response=False)

    def test_authenticated_user_redirected_from_login_and_register(self):
        self.client.force_login(self.user)
        for url in [self.login_url, reverse("accounts:register")]:
            response = self.client.get(url)
            self.assertRedirects(response, self.dashboard_url, fetch_redirect_response=False)

    def test_anonymous_dashboard_requires_login(self):
        response = self.client.get(self.dashboard_url)
        self.assertRedirects(response, self.login_url + "?next=" + self.dashboard_url)

    def test_logout_get_only_confirms_and_post_clears_session(self):
        self.client.force_login(self.user)
        response = self.client.get(self.logout_url)
        self.assertContains(response, "Ya, keluar")
        self.assertIn(SESSION_KEY, self.client.session)
        session = self.client.session
        session["private_test_value"] = "private"
        session.save()
        response = self.client.post(self.logout_url)
        self.assertRedirects(response, reverse("main:landing"))
        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertNotIn("private_test_value", self.client.session)
        self.assertEqual(self.client.get(self.dashboard_url).status_code, 302)

    def test_anonymous_logout_redirects_to_login(self):
        self.assertRedirects(
            self.client.get(self.logout_url), self.login_url + "?next=" + self.logout_url
        )

    def test_login_rotates_existing_session_key(self):
        session = self.client.session
        session["before_login"] = True
        session.save()
        old_key = session.session_key
        self.client.post(self.login_url, self.credentials())
        self.assertNotEqual(self.client.session.session_key, old_key)

    def test_login_and_logout_require_csrf_tokens(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.login_url, self.credentials()).status_code, 403)
        response = client.get(self.login_url)
        token = response.cookies["csrftoken"].value
        self.assertEqual(client.post(
            self.login_url, self.credentials(csrfmiddlewaretoken=token)
        ).status_code, 302)
        self.assertEqual(client.post(self.logout_url).status_code, 403)
        self.assertIn(SESSION_KEY, client.session)
        response = client.get(self.logout_url)
        token = response.cookies["csrftoken"].value
        self.assertEqual(client.post(self.logout_url, {"csrfmiddlewaretoken": token}).status_code, 302)
        self.assertNotIn(SESSION_KEY, client.session)

    def test_authentication_responses_are_not_cached(self):
        response = self.client.get(self.login_url)
        self.assertIn("no-store", response["Cache-Control"])
        self.client.force_login(self.user)
        response = self.client.get(self.logout_url)
        self.assertIn("no-store", response["Cache-Control"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RegistrationAndProfileTests(TestCase):
    def setUp(self):
        self.register_url = reverse("accounts:register")
        self.onboarding_url = reverse("accounts:onboarding")
        self.profile_url = reverse("accounts:profile")
        self.dashboard_url = reverse("dashboard:index")

    def registration(self, **extra):
        return {
            "username": "new_mossly", "email": "New@example.com",
            "display_name": "Nama Baru", "password1": "Strong-random-pass-483!",
            "password2": "Strong-random-pass-483!", **extra,
        }

    def create_user(self, name="existing", completed=False):
        user = get_user_model().objects.create_user(
            username=name, email=f"{name}@example.com", password="Strong-random-pass-483!"
        )
        if completed:
            UserProfile.objects.filter(user=user).update(
                is_onboarded=True, onboarded_at=timezone.now()
            )
        return user

    def preferences(self, **extra):
        return {"avatar": "leaf", "primary_mode": "", "focus_areas": ["energi", "plastik"],
                "share_achievements": "on", **extra}

    def test_register_get_renders_fields_without_creating_user(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        for name in self.registration():
            self.assertContains(response, f'name="{name}"')
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_register_creates_hashed_user_profile_and_logs_in(self):
        data = self.registration(is_staff="on", is_superuser="on", is_onboarded="on")
        response = self.client.post(self.register_url, data)
        self.assertRedirects(response, self.onboarding_url)
        user = get_user_model().objects.get(username=data["username"])
        self.assertEqual(user.email, "new@example.com")
        self.assertNotEqual(user.password, data["password1"])
        self.assertTrue(user.check_password(data["password1"]))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.profile.display_name, "Nama Baru")
        self.assertFalse(user.profile.is_onboarded)
        self.assertIsNone(user.profile.onboarded_at)
        self.assertTrue(user.profile.share_achievements)
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))

    def test_registration_rejects_case_insensitive_duplicate_username_and_email(self):
        self.create_user("existing")
        for extra in [{"username": "EXISTING"}, {"email": "EXISTING@EXAMPLE.COM"}]:
            with self.subTest(extra=extra):
                response = self.client.post(self.register_url, self.registration(**extra))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(get_user_model().objects.count(), 1)
                self.assertNotIn(SESSION_KEY, self.client.session)

    def test_registration_rejects_missing_invalid_and_weak_values(self):
        cases = [
            {"email": "invalid"}, {"username": "contains spaces"}, {"display_name": "   "},
            {"password2": "different"}, {"password1": "12345678", "password2": "12345678"},
            {"password1": "abc", "password2": "abc"}, {"username": "x" * 151},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                response = self.client.post(self.register_url, self.registration(**extra))
                self.assertTrue(response.context["form"].errors)
                self.assertEqual(get_user_model().objects.count(), 0)
                self.assertNotContains(response, 'value="Strong-random-pass-483!"')
        response = self.client.post(self.register_url, {})
        self.assertContains(response, "Bagian ini wajib diisi.")

    def test_registration_failure_does_not_echo_password_or_html(self):
        response = self.client.post(self.register_url, self.registration(
            display_name='<script>alert("name")</script>', password2="mismatch"
        ))
        self.assertNotContains(response, '<script>alert("name")</script>')
        self.assertNotContains(response, 'value="mismatch"')
        self.assertNotContains(response, 'value="Strong-random-pass-483!"')

    def test_onboarding_and_profile_require_login(self):
        for url in [self.onboarding_url, self.profile_url]:
            self.assertRedirects(self.client.get(url), reverse("accounts:login") + "?next=" + url)

    def test_login_routes_incomplete_user_to_onboarding(self):
        user = self.create_user()
        response = self.client.post(reverse("accounts:login"), {
            "username": user.username, "password": "Strong-random-pass-483!",
            "next": reverse("carbon:index"),
        })
        self.assertRedirects(response, self.onboarding_url)
        response = self.client.post(self.onboarding_url, self.preferences())
        self.assertRedirects(response, reverse("carbon:index"), fetch_redirect_response=False)

    def test_existing_user_missing_profile_can_login(self):
        user = self.create_user()
        user.profile.delete()
        response = self.client.post(reverse("accounts:login"), {
            "username": user.username, "password": "Strong-random-pass-483!",
        })
        self.assertRedirects(response, self.onboarding_url)
        self.assertEqual(UserProfile.objects.filter(user=user).count(), 1)

    def test_authenticated_incomplete_user_redirected_from_register_and_profile(self):
        self.client.force_login(self.create_user())
        for url in [self.register_url, self.profile_url, reverse("accounts:login")]:
            self.assertRedirects(self.client.get(url), self.onboarding_url)

    def test_onboarding_saves_only_profile_and_respects_opt_out(self):
        from carbon.models import TransportMode, Trip
        user = self.create_user()
        mode = TransportMode.objects.get(code="jalan")
        mode_count = TransportMode.objects.count()
        self.client.force_login(user)
        self.assertTrue(self.client.get(self.onboarding_url).context["form"].initial["share_achievements"])
        response = self.client.post(self.onboarding_url, {
            "avatar": "tree", "primary_mode": str(mode.pk), "focus_areas": ["transportasi"]
        })
        self.assertRedirects(response, self.dashboard_url)
        profile = UserProfile.objects.get(user=user)
        self.assertTrue(profile.is_onboarded)
        self.assertIsNotNone(profile.onboarded_at)
        self.assertEqual(profile.primary_mode, mode)
        self.assertEqual(profile.focus_areas, ["transportasi"])
        self.assertFalse(profile.share_achievements)
        self.assertEqual(Trip.objects.count(), 0)
        self.assertEqual(TransportMode.objects.count(), mode_count)

    def test_optional_mode_and_focus_can_be_empty(self):
        user = self.create_user()
        self.client.force_login(user)
        response = self.client.post(self.onboarding_url, self.preferences(focus_areas=[]))
        self.assertRedirects(response, self.dashboard_url)
        profile = UserProfile.objects.get(user=user)
        self.assertIsNone(profile.primary_mode)
        self.assertEqual(profile.focus_areas, [])

    def test_invalid_preferences_do_not_mark_onboarding_complete(self):
        from carbon.models import TransportMode
        user = self.create_user()
        self.client.force_login(user)
        inactive = TransportMode.objects.get(code="bus")
        cases = [{"avatar": "unknown"}, {"focus_areas": ["unknown"]},
                 {"focus_areas": ["energi", "energi"]}, {"primary_mode": str(inactive.pk)},
                 {"primary_mode": "999999"}]
        for extra in cases:
            with self.subTest(extra=extra):
                response = self.client.post(self.onboarding_url, self.preferences(**extra))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["form"].errors)
                user.profile.refresh_from_db()
                self.assertFalse(user.profile.is_onboarded)
                self.assertIsNone(user.profile.onboarded_at)

    def test_onboarding_cannot_be_repeated(self):
        user = self.create_user(completed=True)
        before = user.profile.onboarded_at
        self.client.force_login(user)
        for method in [self.client.get, self.client.post]:
            self.assertRedirects(method(self.onboarding_url, self.preferences()), self.dashboard_url)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.avatar, "sprout")
        self.assertEqual(user.profile.onboarded_at, before)

    def test_unsafe_pending_next_is_discarded(self):
        self.client.force_login(self.create_user())
        session = self.client.session
        session["accounts_onboarding_next"] = "https://evil.example/"
        session.save()
        self.assertRedirects(self.client.post(self.onboarding_url, self.preferences()), self.dashboard_url)
        self.assertNotIn("accounts_onboarding_next", self.client.session)

    def test_profile_updates_only_current_users_preferences(self):
        owner = self.create_user(completed=True)
        other = self.create_user("other", completed=True)
        self.client.force_login(owner)
        response = self.client.post(self.profile_url, self.preferences(
            display_name="Nama baru", user=other.pk, is_staff=True, is_onboarded=False,
        ), follow=True)
        self.assertContains(response, "Profil berhasil disimpan.")
        owner.refresh_from_db()
        owner.profile.refresh_from_db()
        other.profile.refresh_from_db()
        self.assertEqual(owner.profile.display_name, "Nama baru")
        self.assertTrue(owner.profile.is_onboarded)
        self.assertEqual(owner.profile.avatar, "leaf")
        self.assertEqual(other.profile.display_name, "other")
        self.assertFalse(owner.is_staff)
        self.assertContains(response, "Avatar Daun")

    def test_invalid_profile_preserves_saved_values(self):
        user = self.create_user(completed=True)
        self.client.force_login(user)
        response = self.client.post(self.profile_url, self.preferences(display_name="", avatar="invalid"))
        self.assertEqual(response.status_code, 200)
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.display_name, user.username)
        self.assertEqual(user.profile.avatar, "sprout")

    def test_profile_mode_can_be_deleted_without_deleting_profile(self):
        from carbon.models import TransportMode
        user = self.create_user(completed=True)
        mode = TransportMode.objects.create(code="test-mode", name="Moda Tes", geoapify_profile="walk")
        UserProfile.objects.filter(user=user).update(primary_mode=mode)
        mode.delete()
        user.profile.refresh_from_db()
        self.assertIsNone(user.profile.primary_mode)

    def test_new_forms_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.register_url, self.registration()).status_code, 403)
        user = self.create_user()
        client.force_login(user)
        self.assertEqual(client.post(self.onboarding_url, self.preferences()).status_code, 403)
        UserProfile.objects.filter(user=user).update(is_onboarded=True, onboarded_at=timezone.now())
        self.assertEqual(client.post(self.profile_url, self.preferences(display_name="x")).status_code, 403)
        self.assertEqual(UserProfile.objects.get(user=user).display_name, user.username)

    def test_complete_registration_onboarding_dashboard_profile_logout(self):
        response = self.client.post(self.register_url, self.registration(), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Langkah awalmu")
        response = self.client.post(self.onboarding_url, self.preferences(), follow=True)
        self.assertContains(response, "Nama Baru")
        self.assertContains(response, reverse("accounts:profile"))
        self.assertEqual(self.client.get(self.profile_url).status_code, 200)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("main:landing"))
        self.assertNotIn(SESSION_KEY, self.client.session)
