from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from community.models import Thread
from habits import services as habit_services
from habits.models import Goal

from . import services
from .badges import BADGES
from .models import Achievement, EmissionTarget, UserAchievement


class DashboardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tania", password="rahasia-123")
        self.client.force_login(self.user)

    def finish_goal(self):
        goal = Goal.objects.create(
            user=self.user,
            title="Pilah sampah tiap hari",
            category=Goal.Category.SAMPAH,
            target_value=1,
            unit=Goal.Unit.KALI,
            deadline=timezone.localdate() + timedelta(days=10),
        )
        habit_services.log_goal_progress(goal, 1)

    def test_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("dashboard:index")).status_code, 302)

    def test_empty_dashboard_seeds_badges(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["is_empty"])
        self.assertEqual(Achievement.objects.count(), len(BADGES))
        self.assertEqual(UserAchievement.objects.count(), 0)

    def test_finished_goal_awards_badge_and_posts_to_community(self):
        self.finish_goal()
        response = self.client.get(reverse("dashboard:index"))
        codes = set(self.user.achievements.values_list("achievement__code", flat=True))
        self.assertEqual(codes, {"first_goal", "early_finish"})
        self.assertIsNotNone(response.context["new_badge"])
        self.assertEqual(
            Thread.objects.filter(author=self.user, category=Thread.Category.ACHIEVEMENT).count(), 2
        )

    def test_badge_is_awarded_once_and_modal_shows_once(self):
        self.finish_goal()
        self.client.get(reverse("dashboard:index"))
        again = self.client.get(reverse("dashboard:index"))
        self.assertIsNone(again.context["new_badge"])
        self.assertEqual(self.user.achievements.count(), 2)
        self.assertEqual(Thread.objects.filter(author=self.user).count(), 2)

    def test_sharing_off_keeps_badge_but_skips_post(self):
        self.user.profile.share_achievements = False
        self.user.profile.save()
        self.finish_goal()
        self.client.get(reverse("dashboard:index"))
        self.assertEqual(self.user.achievements.count(), 2)
        self.assertEqual(Thread.objects.filter(author=self.user).count(), 0)

    def test_badges_page_groups_all_badges(self):
        response = self.client.get(reverse("dashboard:badges"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_badges"], len(BADGES))
        self.assertEqual(sum(g["total"] for g in response.context["groups"]), len(BADGES))


class EmissionTargetTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("tania", password="rahasia-123")
        self.other = User.objects.create_user("isybal", password="rahasia-123")
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.first = self.today.replace(day=1)

    def make_target(self, user=None, kg="20"):
        return EmissionTarget.objects.create(
            user=user or self.user, month=self.first, target_kg=Decimal(kg)
        )

    def test_pages_require_login(self):
        self.client.logout()
        for name in ("targets", "target_create", "api_summary"):
            self.assertEqual(self.client.get(reverse(f"dashboard:{name}")).status_code, 302)

    def test_create_target(self):
        response = self.client.post(
            reverse("dashboard:target_create"),
            {"month": self.first.strftime("%Y-%m"), "target_kg": "20"},
        )
        self.assertRedirects(response, reverse("dashboard:targets"))
        target = EmissionTarget.objects.get(user=self.user)
        self.assertEqual(target.month, self.first)
        self.assertEqual(target.target_kg, Decimal("20"))

    def test_duplicate_month_is_rejected(self):
        self.make_target()
        response = self.client.post(
            reverse("dashboard:target_create"),
            {"month": self.first.strftime("%Y-%m"), "target_kg": "30"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(EmissionTarget.objects.filter(user=self.user).count(), 1)

    def test_invalid_value_is_rejected(self):
        for value in ("0", "-5", "abc", "10001"):
            response = self.client.post(
                reverse("dashboard:target_create"),
                {"month": self.first.strftime("%Y-%m"), "target_kg": value},
            )
            self.assertEqual(response.status_code, 200)
        self.assertFalse(EmissionTarget.objects.exists())

    def test_edit_updates_target(self):
        target = self.make_target()
        response = self.client.post(
            reverse("dashboard:target_edit", args=[target.pk]), {"target_kg": "15.5"}
        )
        self.assertRedirects(response, reverse("dashboard:targets"))
        target.refresh_from_db()
        self.assertEqual(target.target_kg, Decimal("15.50"))

    def test_delete_needs_post(self):
        target = self.make_target()
        url = reverse("dashboard:target_delete", args=[target.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(EmissionTarget.objects.filter(pk=target.pk).exists())
        self.client.post(url)
        self.assertFalse(EmissionTarget.objects.filter(pk=target.pk).exists())

    def test_other_users_target_is_hidden(self):
        target = self.make_target(user=self.other)
        for name in ("target_edit", "target_delete"):
            url = reverse(f"dashboard:{name}", args=[target.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {"target_kg": "1"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("dashboard:targets")).context["targets"], [])

    def test_target_overview_without_emission(self):
        self.assertIsNone(services.target_overview(self.user, self.today)["row"])
        self.make_target()
        row = services.target_overview(self.user, self.today)["row"]
        self.assertEqual((row["percent"], row["state"], row["is_current"]), (0, "ok", True))

    def test_api_summary_only_returns_own_data(self):
        self.make_target(kg="10")
        self.make_target(user=self.other, kg="99")
        response = self.client.get(reverse("dashboard:api_summary"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["target_kg"], 10.0)
        self.assertEqual(data["emission_kg"], 0.0)
        self.assertEqual(data["badges"]["total"], len(BADGES))
        self.assertEqual(self.client.post(reverse("dashboard:api_summary")).status_code, 405)


class BadgeFilterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tania", password="rahasia-123")
        self.client.force_login(self.user)
        self.url = reverse("dashboard:badges")

    def test_filter_by_category(self):
        response = self.client.get(self.url, {"kategori": "habit"})
        self.assertTemplateUsed(response, "badges.html")
        self.assertEqual([g["key"] for g in response.context["groups"]], ["habit"])
        self.assertEqual(len(response.context["tabs"]), 4)

    def test_unknown_category_shows_all(self):
        response = self.client.get(self.url, {"kategori": "tidak-ada"})
        self.assertEqual(response.context["active"], "all")
        self.assertEqual(len(response.context["groups"]), 4)

    def test_htmx_request_returns_partial_only(self):
        response = self.client.get(self.url, {"kategori": "goal"}, HTTP_HX_REQUEST="true")
        self.assertTemplateUsed(response, "dashboard_parts/badge_browser.html")
        self.assertTemplateNotUsed(response, "badges.html")