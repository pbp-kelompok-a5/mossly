"""Test kontrak GET Community untuk aplikasi mobile."""

from datetime import datetime

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import Reply, Thread, ThreadLike


class CommunityReadApiTests(APITestCase):
    def setUp(self):
        # Migration menyediakan thread seed; setiap test memakai feed terkontrol.
        Thread.objects.all().delete()
        self.user = get_user_model().objects.create_user(username="eleazar")
        self.other = get_user_model().objects.create_user(username="rara")
        self.other.profile.display_name = "Rara Hijau"
        self.other.profile.avatar = "leaf"
        self.other.profile.save(update_fields=["display_name", "avatar"])
        self.thread = Thread.objects.create(
            author=self.other,
            title="Bawa tumbler",
            body="Mulai dari kebiasaan kecil.",
            category=Thread.Category.TIPS,
        )
        self.list_url = reverse("community_api:thread-list")
        self.detail_url = reverse(
            "community_api:thread-detail", args=[self.thread.pk]
        )
        self.client.force_authenticate(user=self.user)

    def test_endpoints_require_login(self):
        self.client.force_authenticate(user=None)
        for url in [self.list_url, self.detail_url]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertIn("detail", response.json())

    def test_token_authentication(self):
        self.client.force_authenticate(user=None)
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        for url in [self.list_url, self.detail_url]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_invalid_token_is_rejected(self):
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid-token")
        self.assertEqual(
            self.client.get(self.list_url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_feed_contains_other_authors_and_profile(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["category"], "")
        self.assertEqual(len(data["results"]), 1)
        row = data["results"][0]
        self.assertEqual(row["id"], self.thread.pk)
        self.assertEqual(row["title"], "Bawa tumbler")
        self.assertEqual(row["body"], self.thread.body)
        self.assertEqual(row["category"], "tips")
        self.assertEqual(row["author"], {
            "id": self.other.pk,
            "username": "rara",
            "display_name": "Rara Hijau",
            "avatar": "leaf",
        })
        self.assertFalse(row["is_auto_post"])
        self.assertEqual(row["like_count"], 0)
        self.assertEqual(row["reply_count"], 0)
        self.assertIs(row["is_liked"], False)
        for field in ["created_at", "updated_at"]:
            self.assertIsNotNone(datetime.fromisoformat(row[field]).tzinfo)
        self.assertNotIn("email", row["author"])
        self.assertNotIn("password", row["author"])

    def test_empty_feed(self):
        Thread.objects.all().delete()
        self.assertEqual(self.client.get(self.list_url).json(), {
            "category": "",
            "results": [],
            "pagination": {
                "page": 1, "total_pages": 1,
                "has_next": False, "has_previous": False,
            },
        })

    def test_detail_includes_counts_and_current_users_like(self):
        ThreadLike.objects.create(thread=self.thread, user=self.user)
        ThreadLike.objects.create(thread=self.thread, user=self.other)
        for author in [self.user, self.other]:
            Reply.objects.create(thread=self.thread, author=author, body="Setuju!")

        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.json()
        self.assertEqual(row["like_count"], 2)
        self.assertEqual(row["reply_count"], 2)
        self.assertIs(row["is_liked"], True)
        self.assertEqual(row, self.client.get(self.list_url).json()["results"][0])

    def test_other_users_like_does_not_mark_thread_as_liked(self):
        ThreadLike.objects.create(thread=self.thread, user=self.other)
        row = self.client.get(self.detail_url).json()
        self.assertEqual(row["like_count"], 1)
        self.assertIs(row["is_liked"], False)

    def test_personalized_responses_are_not_cacheable_when_switching_accounts(self):
        ThreadLike.objects.create(thread=self.thread, user=self.user)
        for user, is_liked in [(self.user, True), (self.other, False)]:
            self.client.force_authenticate(user=user)
            for url in [self.list_url, self.detail_url]:
                with self.subTest(user=user.username, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    directives = {
                        value.strip() for value in response["Cache-Control"].split(",")
                    }
                    self.assertTrue({
                        "private", "no-store", "no-cache", "max-age=0", "must-revalidate",
                    }.issubset(directives))
                    self.assertIn("Expires", response)
                    data = response.json()
                    row = data["results"][0] if url == self.list_url else data
                    self.assertIs(row["is_liked"], is_liked)

    def test_error_responses_are_not_cacheable(self):
        missing_url = reverse(
            "community_api:thread-detail", args=[self.thread.pk + 1]
        )
        for url, params, expected_status in [
            (self.list_url, {"category": "invalid"}, status.HTTP_400_BAD_REQUEST),
            (self.list_url, {"page": 2}, status.HTTP_404_NOT_FOUND),
            (missing_url, {}, status.HTTP_404_NOT_FOUND),
        ]:
            with self.subTest(url=url, params=params):
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, expected_status)
                self.assertIn("no-store", response["Cache-Control"])

        self.client.force_authenticate(user=None)
        for url in [self.list_url, self.detail_url]:
            with self.subTest(unauthenticated_url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertIn("no-store", response["Cache-Control"])

    def test_empty_display_name_falls_back_to_username(self):
        self.other.profile.display_name = ""
        self.other.profile.save(update_fields=["display_name"])
        row = self.client.get(self.detail_url).json()
        self.assertEqual(row["author"]["display_name"], self.other.username)

    def test_missing_thread_returns_404(self):
        self.thread.delete()
        self.assertEqual(
            self.client.get(self.detail_url).status_code, status.HTTP_404_NOT_FOUND
        )

    def test_combined_category_and_case_insensitive_author_filters(self):
        Thread.objects.create(author=self.user, title="Tips lain", body="Isi", category="tips")
        Thread.objects.create(author=self.other, title="Obrolan", body="Isi", category="general")
        response = self.client.get(self.list_url, {"category": "tips", "author": " RAR "})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["category"], "tips")
        self.assertEqual([row["id"] for row in data["results"]], [self.thread.pk])

    def test_achievement_threads_can_be_read(self):
        achievement = Thread.objects.create(
            author=self.other, title="Pencapaian", body="Hebat!",
            category="achievement", is_auto_post=True,
        )
        data = self.client.get(self.list_url, {"category": "achievement"}).json()
        self.assertEqual([row["id"] for row in data["results"]], [achievement.pk])
        self.assertIs(data["results"][0]["is_auto_post"], True)
        url = reverse("community_api:thread-detail", args=[achievement.pk])
        self.assertEqual(self.client.get(url).status_code, status.HTTP_200_OK)

    def test_blank_filters_and_no_matching_author(self):
        response = self.client.get(self.list_url, {"category": "", "author": "  "})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()["results"]), 1)
        data = self.client.get(self.list_url, {"author": "unknown-user"}).json()
        self.assertEqual(data["results"], [])

    def test_invalid_filters_return_field_errors(self):
        for params, field in [
            ({"category": "unknown"}, "category"),
            ({"page": "abc"}, "page"),
            ({"page": "1.5"}, "page"),
            ({"page": "0"}, "page"),
            ({"page": "-1"}, "page"),
        ]:
            with self.subTest(params=params):
                response = self.client.get(self.list_url, params)
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertIsInstance(response.json()[field], list)

    def test_pagination_is_newest_first_without_duplicate_rows(self):
        extra = [
            Thread.objects.create(author=self.user, title=f"Thread {n}", body="Isi")
            for n in range(9)
        ]
        first = self.client.get(self.list_url).json()
        second = self.client.get(self.list_url, {"page": 2}).json()
        self.assertEqual(len(first["results"]), 8)
        self.assertEqual(len(second["results"]), 2)
        self.assertEqual(first["pagination"], {
            "page": 1, "total_pages": 2, "has_next": True, "has_previous": False,
        })
        self.assertEqual(second["pagination"], {
            "page": 2, "total_pages": 2, "has_next": False, "has_previous": True,
        })
        ids = [row["id"] for row in first["results"] + second["results"]]
        self.assertEqual(ids, [thread.pk for thread in reversed(extra)] + [self.thread.pk])

    def test_page_beyond_last_returns_404(self):
        response = self.client.get(self.list_url, {"page": 2})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_write_methods_are_not_enabled(self):
        for url in [self.list_url, self.detail_url]:
            for method in ["post", "patch", "delete"]:
                with self.subTest(url=url, method=method):
                    response = getattr(self.client, method)(url)
                    self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Thread.objects.filter(pk=self.thread.pk).exists())
