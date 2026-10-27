"""Access control and request handling for state-changing views."""

from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from habits.models import Goal, Habit, SustainabilityEvent

from .helpers import TODAY, FrozenClockMixin, days_ago, make_goal, make_habit, make_user


class AccessTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.habit = make_habit(self.owner)
        self.goal = make_goal(self.owner)

    def habit_urls(self):
        return [
            reverse(name, args=[self.habit.pk])
            for name in ("habits:habit_check_in", "habits:habit_undo_check_in", "habits:habit_delete")
        ]

    def goal_urls(self):
        return [
            reverse(name, args=[self.goal.pk])
            for name in ("habits:goal_log_progress", "habits:goal_delete")
        ]

    def test_anonymous_is_redirected_to_login(self):
        login_url = reverse("accounts:login")
        for url in [reverse("habits:index")] + self.habit_urls() + self.goal_urls():
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertRedirects(
                    response, f"{login_url}?next={url}", fetch_redirect_response=False
                )

    def test_other_users_objects_return_404(self):
        self.client.force_login(self.other)
        for url in self.habit_urls() + self.goal_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {"amount": "1"}).status_code, 404)
        self.assertTrue(Habit.objects.filter(pk=self.habit.pk).exists())
        self.assertTrue(Goal.objects.filter(pk=self.goal.pk).exists())
        self.assertFalse(self.habit.checkins.exists())
        self.assertFalse(self.goal.progress_logs.exists())

    def test_state_changes_require_post(self):
        self.client.force_login(self.owner)
        # Delete answers GET with its confirmation page instead (tested below).
        post_only = [url for url in self.habit_urls() if not url.endswith("/delete/")]
        for url in post_only + self.goal_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_delete_get_shows_confirmation_without_deleting(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("habits:habit_delete", args=[self.habit.pk]))
        self.assertContains(response, "Hapus habit ini?")
        self.assertTrue(Habit.objects.filter(pk=self.habit.pk).exists())

    def test_edit_page_of_other_users_habit_returns_404(self):
        self.client.force_login(self.other)
        url = reverse("habits:habit_edit", args=[self.habit.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"name": "Diambil"}).status_code, 404)
        self.habit.refresh_from_db()
        self.assertEqual(self.habit.name, "Bawa tumbler")

    def test_state_changes_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for url in self.habit_urls() + self.goal_urls():
            with self.subTest(url=url):
                self.assertEqual(client.post(url).status_code, 403)
        self.assertTrue(Habit.objects.filter(pk=self.habit.pk).exists())


class HabitActionTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.habit = make_habit(self.user)
        self.client.force_login(self.user)

    def post(self, name):
        return self.client.post(reverse(name, args=[self.habit.pk]))

    def test_check_in_and_undo(self):
        response = self.post("habits:habit_check_in")
        self.assertRedirects(response, reverse("habits:index"), fetch_redirect_response=False)
        self.assertTrue(self.habit.checkins.filter(checkin_date=TODAY).exists())
        self.post("habits:habit_undo_check_in")
        self.assertFalse(self.habit.checkins.exists())

    def test_delete_removes_habit_and_checkins_but_keeps_events(self):
        for n in (2, 1):
            self.habit.checkins.create(checkin_date=days_ago(n))
        self.post("habits:habit_check_in")  # reaches 3 days
        self.post("habits:habit_delete")
        self.assertFalse(Habit.objects.exists())
        self.assertEqual(SustainabilityEvent.objects.count(), 1)


class GoalActionTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.goal = make_goal(self.user)
        self.client.force_login(self.user)
        self.url = reverse("habits:goal_log_progress", args=[self.goal.pk])

    def test_log_progress(self):
        self.client.post(self.url, {"amount": "3", "note": "Ke kampus"})
        log = self.goal.progress_logs.get()
        self.assertEqual(log.amount, Decimal("3"))
        self.assertEqual(log.note, "Ke kampus")

    def test_invalid_amount_is_rejected(self):
        for amount in ("0", "-2", "abc", ""):
            with self.subTest(amount=amount):
                self.client.post(self.url, {"amount": amount})
        self.assertFalse(self.goal.progress_logs.exists())

    def test_delete_goal(self):
        self.client.post(reverse("habits:goal_delete", args=[self.goal.pk]))
        self.assertFalse(Goal.objects.exists())
