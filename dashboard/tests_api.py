from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .badges import BADGES


class DashboardApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tania", password="rahasia-123")

    def test_summary_requires_login(self):
        response = self.client.get("/api/v1/dashboard/summary/")
        self.assertEqual(response.status_code, 401)

    def test_summary_returns_data(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/dashboard/summary/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["badges"]["total"], len(BADGES))

    def test_summary_rejects_post(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post("/api/v1/dashboard/summary/")
        self.assertEqual(response.status_code, 405)

    def test_badges_requires_login(self):
        response = self.client.get("/api/v1/dashboard/badges/")
        self.assertEqual(response.status_code, 401)

    def test_badges_lists_all(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get("/api/v1/dashboard/badges/").json()
        self.assertEqual(data["total"], len(BADGES))
        self.assertEqual(len(data["badges"]), len(BADGES))

    def test_badges_filter_by_category(self):
        self.client.force_authenticate(user=self.user)
        data = self.client.get("/api/v1/dashboard/badges/", {"kategori": "habit"}).json()
        self.assertTrue(data["badges"])
        self.assertTrue(all(b["category"] == "habit" for b in data["badges"]))

    def test_badges_invalid_category(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/dashboard/badges/", {"kategori": "ngawur"})
        self.assertEqual(response.status_code, 400)