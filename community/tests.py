from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from dashboard.models import Achievement, UserAchievement

from .models import Reply, Thread, ThreadLike
from .services import publish_achievement


class CommunityTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="rara",
            password="test-password",
        )
        self.other = get_user_model().objects.create_user(
            username="bima",
            password="test-password",
        )
        self.thread = Thread.objects.create(
            author=self.owner,
            title="Bawa tumbler",
            body="Mulai dari kebiasaan kecil.",
            category=Thread.Category.TIPS,
        )
        self.owner.profile.display_name = "Rara Hijau"
        self.owner.profile.avatar = "leaf"
        self.owner.profile.save(update_fields=["display_name", "avatar"])
        self.client.force_login(self.owner)

    def test_authentication_is_required_for_all_community_pages(self):
        self.client.logout()
        routes = [
            ("index", []),
            ("create", []),
            ("detail", [self.thread.pk]),
            ("edit", [self.thread.pk]),
            ("delete", [self.thread.pk]),
            ("like", [self.thread.pk]),
        ]

        for name, args in routes:
            with self.subTest(route=name):
                response = self.client.get(reverse(f"community:{name}", args=args))
                self.assertEqual(response.status_code, 302)
                self.assertIn("/accounts/login/", response.url)

    def test_feed_filters_and_pagination(self):
        Thread.objects.bulk_create(
            [
                Thread(
                    author=self.owner,
                    title=f"Cerita {index}",
                    body="Cerita",
                    category=Thread.Category.GENERAL,
                )
                for index in range(10)
            ]
        )

        response = self.client.get(reverse("community:index"))
        self.assertEqual(len(response.context["page_obj"]), 8)
        self.assertContains(response, "Selanjutnya")

        response = self.client.get(
            reverse("community:index"),
            {"category": Thread.Category.TIPS},
        )
        self.assertContains(response, "Bawa tumbler")
        self.assertEqual(len(response.context["page_obj"]), 1)

        response = self.client.get(
            reverse("community:index"),
            {"category": Thread.Category.ACHIEVEMENT},
        )
        self.assertContains(response, "Belum ada cerita di kategori ini")

    def test_feed_filter_supports_async_updates(self):
        response = self.client.get(
            reverse("community:index"),
            {"category": Thread.Category.TIPS},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], Thread.Category.TIPS)
        self.assertIn("Bawa tumbler", response.json()["thread_html"])
        self.assertIn("hx-post=", response.json()["thread_html"])

    def test_threads_json_endpoint_returns_thread_data(self):
        response = self.client.get(
            reverse("community:threads_json"),
            {"category": Thread.Category.TIPS},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["category"], Thread.Category.TIPS)
        self.assertEqual(payload["results"][0]["title"], "Bawa tumbler")
        self.assertEqual(payload["results"][0]["author"]["display_name"], "Rara Hijau")
        self.assertEqual(payload["results"][0]["detail_url"], f"/community/{self.thread.pk}/")

    def test_feed_filters_by_author_username(self):
        Thread.objects.create(
            author=self.other,
            title="Cerita Bima",
            body="Cerita dari pengguna lain.",
            category=Thread.Category.GENERAL,
        )

        response = self.client.get(reverse("community:index"), {"author": " RAR "})
        self.assertContains(response, "Bawa tumbler")
        self.assertNotContains(response, "Cerita Bima")

    def test_feed_counts_likes_and_replies_independently(self):
        ThreadLike.objects.create(thread=self.thread, user=self.owner)
        ThreadLike.objects.create(thread=self.thread, user=self.other)
        Reply.objects.create(thread=self.thread, author=self.owner, body="Setuju!")
        Reply.objects.create(thread=self.thread, author=self.other, body="Aku juga.")

        response = self.client.get(reverse("community:index"))
        thread = next(
            item
            for item in response.context["page_obj"].object_list
            if item.pk == self.thread.pk
        )

        self.assertEqual(thread.like_count, 2)
        self.assertEqual(thread.reply_count, 2)

    def test_thread_author_uses_profile_name_and_avatar(self):
        response = self.client.get(reverse("community:detail", args=[self.thread.pk]))
        self.assertContains(response, "Rara Hijau")
        self.assertContains(response, "@rara")
        self.assertContains(response, 'aria-label="Avatar Daun"')
        self.assertContains(response, 'd="M4 20 18 6M5 16C2 7 10 3 21 3c0 11-4 19-13 16"')

    def test_create_validation_author_and_allowed_categories(self):
        url = reverse("community:create")
        self.assertEqual(self.client.get(url).status_code, 200)

        response = self.client.post(
            url,
            {"title": "  ", "body": " ", "category": Thread.Category.TIPS},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)

        response = self.client.post(
            url,
            {
                "title": "Badge palsu",
                "body": "Tidak boleh menjadi post otomatis.",
                "category": Thread.Category.ACHIEVEMENT,
                "author": self.other.pk,
                "is_auto_post": True,
                "user_achievement": 999,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("category", response.context["form"].errors)
        self.assertFalse(Thread.objects.filter(title="Badge palsu").exists())

        response = self.client.post(
            url,
            {
                "title": "Naik KRL",
                "body": "Lebih hemat",
                "category": Thread.Category.TIPS,
                "author": self.other.pk,
                "is_auto_post": True,
            },
        )
        self.assertEqual(response.status_code, 302)
        thread = Thread.objects.get(title="Naik KRL")
        self.assertEqual(thread.author, self.owner)
        self.assertFalse(thread.is_auto_post)
        self.assertIsNone(thread.user_achievement_id)

    def test_edit_and_ownership(self):
        url = reverse("community:edit", args=[self.thread.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(
            url,
            {
                "title": "Tumbler baru",
                "body": "Ceritaku",
                "category": Thread.Category.GENERAL,
            },
        )
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.title, "Tumbler baru")

        self.client.force_login(self.other)
        for name in ("edit", "delete"):
            with self.subTest(route=name):
                url = reverse(f"community:{name}", args=[self.thread.pk])
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, {"title": "Hacked"}).status_code, 404)

        self.assertTrue(Thread.objects.filter(pk=self.thread.pk).exists())

    def test_reply_validation_and_escaping(self):
        url = reverse("community:detail", args=[self.thread.pk])
        response = self.client.post(url, {"body": " "})
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(self.thread.replies.count(), 0)

        self.client.post(
            url,
            {"body": "<script>alert(1)</script>", "author": self.other.pk},
        )
        self.assertEqual(self.thread.replies.get().author, self.owner)
        response = self.client.get(url)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_reply_endpoint_supports_async_submission(self):
        response = self.client.post(
            reverse("community:detail", args=[self.thread.pk]),
            {"body": "Balasan tanpa memuat ulang halaman."},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply_count"], 1)
        self.assertIn("Balasan tanpa memuat ulang halaman.", response.json()["reply_html"])
        self.assertEqual(self.thread.replies.count(), 1)

    def test_like_is_explicit_unique_idempotent_and_post_only(self):
        url = reverse("community:like", args=[self.thread.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

        for _ in range(2):
            self.client.post(url, {"action": "like"})
        like = ThreadLike.objects.get(thread=self.thread, user=self.owner)
        self.assertIsNotNone(like.created_at)
        self.assertEqual(ThreadLike.objects.count(), 1)

        response = self.client.get(reverse("community:detail", args=[self.thread.pk]))
        self.assertContains(response, "Diapresiasi")

        for _ in range(2):
            self.client.post(url, {"action": "unlike"})
        self.assertEqual(ThreadLike.objects.count(), 0)

    def test_index_like_button_uses_thread_like_endpoint(self):
        response = self.client.get(reverse("community:index"))
        self.assertContains(response, 'aria-label="Beri apresiasi"')
        self.assertContains(response, 'aria-label="Lihat 0 balasan"')
        self.assertContains(response, f'href="{reverse("community:detail", args=[self.thread.pk])}#replies"')

        response = self.client.post(
            reverse("community:like", args=[self.thread.pk]),
            {"action": "like", "next": reverse("community:index")},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("community:index"))
        self.assertTrue(ThreadLike.objects.filter(thread=self.thread, user=self.owner).exists())

    def test_like_endpoint_supports_async_toggle(self):
        url = reverse("community:like", args=[self.thread.pk])
        headers = {
            "HTTP_X_REQUESTED_WITH": "XMLHttpRequest",
            "HTTP_ACCEPT": "application/json",
        }

        response = self.client.post(url, {"action": "toggle"}, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"is_liked": True, "like_count": 1})

        response = self.client.post(url, {"action": "toggle"}, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"is_liked": False, "like_count": 0})

    def test_like_endpoint_supports_htmx(self):
        response = self.client.post(
            reverse("community:like", args=[self.thread.pk]),
            {"action": "like", "variant": "feed"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hx-post=")
        self.assertContains(response, "Hapus apresiasi")
        self.assertTrue(ThreadLike.objects.filter(thread=self.thread, user=self.owner).exists())

    def test_delete_cascades_replies_and_likes(self):
        Reply.objects.create(thread=self.thread, author=self.other, body="Bagus!")
        ThreadLike.objects.create(thread=self.thread, user=self.other)
        url = reverse("community:delete", args=[self.thread.pk])

        self.assertContains(self.client.get(url), "Hapus cerita ini?")
        self.client.post(url)

        self.assertFalse(Thread.objects.filter(pk=self.thread.pk).exists())
        self.assertEqual(Reply.objects.count(), 0)
        self.assertEqual(ThreadLike.objects.count(), 0)

    def test_achievement_service_creates_one_auto_post(self):
        achievement = Achievement.objects.create(
            code="moss_sprout",
            name="Tunas",
            description="Streak tujuh hari.",
            icon="sprout",
            category=Achievement.Category.HABIT,
            threshold=7,
        )
        award = UserAchievement.objects.create(
            user=self.owner,
            achievement=achievement,
        )

        thread = publish_achievement(user_achievement=award)
        self.assertEqual(publish_achievement(user_achievement=award), thread)
        self.assertTrue(thread.is_auto_post)
        self.assertEqual(thread.category, Thread.Category.ACHIEVEMENT)
        self.assertEqual(thread.user_achievement, award)
        self.assertEqual(thread.body, achievement.description)
        self.assertEqual(self.client.get(reverse("community:edit", args=[thread.pk])).status_code, 404)
        self.assertContains(
            self.client.get(reverse("community:detail", args=[thread.pk])),
            "Post Otomatis",
        )

    def test_achievement_service_respects_sharing_preference(self):
        self.owner.profile.share_achievements = False
        self.owner.profile.save(update_fields=["share_achievements"])
        achievement = Achievement.objects.create(
            code="first_thread",
            name="Suara Pertama",
            description="Membuat thread pertama.",
            icon="message-circle",
            category=Achievement.Category.COMMUNITY,
            threshold=1,
        )
        award = UserAchievement.objects.create(
            user=self.owner,
            achievement=achievement,
        )

        self.assertIsNone(publish_achievement(user_achievement=award))
        self.assertFalse(Thread.objects.filter(user_achievement=award).exists())

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.post(
            reverse("community:like", args=[self.thread.pk]),
            {"action": "like"},
        )
        self.assertEqual(response.status_code, 403)
