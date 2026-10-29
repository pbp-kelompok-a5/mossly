from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from community.models import Thread
from habits import services as habit_services
from habits.models import Goal

from .badges import BADGES
from .models import Achievement, UserAchievement


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