from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.authtoken.models import Token


class ApiFoundationTests(TestCase):
    def test_ping_is_public(self):
        response = self.client.get("/api/v1/ping/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["authenticated"], False)

    def test_ping_recognises_token(self):
        user = get_user_model().objects.create_user("lumut", password="rahasia-12345")
        token = Token.objects.create(user=user)
        response = self.client.get("/api/v1/ping/", HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(response.json(), {
            "status": "ok", "app": "mossly", "authenticated": True, "username": "lumut",
        })

    def test_invalid_token_is_rejected(self):
        response = self.client.get("/api/v1/ping/", HTTP_AUTHORIZATION="Token salah")
        self.assertEqual(response.status_code, 401)

    def test_cors_only_on_api(self):
        api = self.client.get("/api/v1/ping/", HTTP_ORIGIN="http://localhost:5555")
        self.assertEqual(api["Access-Control-Allow-Origin"], "*")
        web = self.client.get("/", HTTP_ORIGIN="http://localhost:5555")
        self.assertNotIn("Access-Control-Allow-Origin", web)
