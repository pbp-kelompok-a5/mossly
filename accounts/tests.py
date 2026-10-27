from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="sheva_test", password="Test-password-123"
        )
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
