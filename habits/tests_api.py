"""Test endpoint DRF modul habit.

Waktu dibekukan di Senin, 26 Oktober 2026 (FrozenClockMixin from tests/helpers.py class), jadi streak,
jadwal, dan sisa hari selalu sama di mana pun test dijalankan.
"""
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from habits.models import Goal, GoalChecklistItem, GoalProgressLog, Habit, HabitCheckIn
from habits.tests.helpers import FIXED_NOW, TODAY, FrozenClockMixin, days_ago, make_goal, make_habit, make_user


class HabitListApiTests(FrozenClockMixin, APITestCase):
    url = reverse("habits_api:habit-list")

    def setUp(self):
        super().setUp()
        self.user = make_user("tania")
        self.client.force_authenticate(user=self.user)

    def check_in(self, habit, *days_back):
        for n in days_back:
            HabitCheckIn.objects.create(habit=habit, checkin_date=days_ago(n))

    def test_requires_login(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_list(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {
            "date": "2026-10-26", "scheduled_today": 0, "done_today": 0, "habits": [],
        })

    def test_lists_habit_with_streak_and_today_status(self):
        habit = make_habit(self.user, icon=Habit.Icon.CUP_SODA, time_of_day=Habit.TimeOfDay.PAGI)
        self.check_in(habit, 2, 1, 0)  # kemarin lusa, kemarin, hari ini

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["scheduled_today"], 1)
        self.assertEqual(data["done_today"], 1)
        self.assertEqual(data["habits"], [{
            "id": habit.pk,
            "name": "Bawa tumbler",
            "icon": "cup-soda",
            "tint": habit.tint,
            "time_of_day": "pagi",
            "frequency_type": "daily",
            "weekdays": None,
            "start_date": days_ago(60).isoformat(),
            "is_scheduled_today": True,
            "is_done_today": True,
            "current_streak": 3,
            "longest_streak": 3,
            "next_milestone": 7,
        }])

    def test_unchecked_today_does_not_break_streak(self):
        habit = make_habit(self.user)
        self.check_in(habit, 2, 1)

        row = self.client.get(self.url).json()["habits"][0]

        self.assertFalse(row["is_done_today"])
        self.assertEqual(row["current_streak"], 2)

    def test_habit_not_scheduled_today_is_not_counted(self):
        # TODAY hari Senin (0); habit ini hanya hari Selasa (1).
        make_habit(self.user, frequency_type=Habit.Frequency.WEEKDAYS, weekdays=[1])
        make_habit(self.user, name="Pilah sampah")

        data = self.client.get(self.url).json()

        self.assertEqual(data["scheduled_today"], 1)
        self.assertEqual([h["is_scheduled_today"] for h in data["habits"]], [False, True])
        self.assertEqual(data["habits"][0]["weekdays"], [1])

    def test_other_users_habits_are_hidden(self):
        make_habit(make_user("orang_lain"), name="Rahasia")
        mine = make_habit(self.user)

        data = self.client.get(self.url).json()

        self.assertEqual([h["id"] for h in data["habits"]], [mine.pk])
        self.assertEqual(data["scheduled_today"], 1)

    def test_post_is_not_allowed_yet(self):
        response = self.client.post(self.url, {"name": "Baru"})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class GoalListApiTests(FrozenClockMixin, APITestCase):
    url = reverse("habits_api:goal-list")

    def setUp(self):
        super().setUp()
        self.user = make_user("tania")
        self.client.force_authenticate(user=self.user)

    def test_requires_login(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_list(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [])

    def test_lists_goal_with_progress_and_checklist(self):
        goal = make_goal(self.user)  # target 20 kali, deadline 4 hari lagi
        GoalProgressLog.objects.create(goal=goal, amount=Decimal("7"))
        GoalProgressLog.objects.create(goal=goal, amount=Decimal("5"))
        done = GoalChecklistItem.objects.create(goal=goal, label="Cek jadwal KRL", is_done=True)
        todo = GoalChecklistItem.objects.create(goal=goal, label="Isi saldo", position=1)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), [{
            "id": goal.pk,
            "title": "Naik transportasi umum 20 kali",
            "category": "transportasi",
            "target_value": 20.0,
            "unit": "kali",
            "start_date": days_ago(25).isoformat(),
            "deadline": (TODAY + timedelta(days=4)).isoformat(),
            "status": "active",
            "progress": 12.0,
            "percent": 60,
            "days_left": 4,
            "is_near_deadline": True,
            "completed_at": None,
            "checklist": [
                {"id": done.pk, "label": "Cek jadwal KRL", "is_done": True},
                {"id": todo.pk, "label": "Isi saldo", "is_done": False},
            ],
        }])

    def test_numbers_are_sent_as_numbers(self):
        goal = make_goal(self.user, unit=Goal.Unit.KG_CO2E, target_value=Decimal("10.5"))
        GoalProgressLog.objects.create(goal=goal, amount=Decimal("2.25"))

        row = self.client.get(self.url).json()[0]

        self.assertEqual(row["target_value"], 10.5)
        self.assertEqual(row["progress"], 2.25)
        self.assertIsInstance(row["target_value"], float)

    def test_overdue_goal_is_expired_and_saved(self):
        goal = make_goal(self.user, start_date=days_ago(10), deadline=days_ago(1))

        row = self.client.get(self.url).json()[0]

        self.assertEqual(row["status"], "expired")
        self.assertEqual(row["days_left"], -1)
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.EXPIRED)

    def test_completed_goal_keeps_its_status(self):
        make_goal(self.user, status=Goal.Status.COMPLETED, completed_at=FIXED_NOW)

        row = self.client.get(self.url).json()[0]

        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["completed_at"], "2026-10-26T12:00:00+07:00")

    def test_other_users_goals_are_hidden(self):
        make_goal(make_user("orang_lain"), title="Rahasia")
        mine = make_goal(self.user)

        data = self.client.get(self.url).json()

        self.assertEqual([g["id"] for g in data], [mine.pk])

    def test_filter_by_category(self):
        make_goal(self.user, category=Goal.Category.TRANSPORTASI)
        plastik = make_goal(self.user, category=Goal.Category.PLASTIK, unit=Goal.Unit.HARI)

        data = self.client.get(self.url, {"category": "plastik"}).json()

        self.assertEqual([g["id"] for g in data], [plastik.pk])

    def test_empty_category_means_no_filter(self):
        make_goal(self.user, category=Goal.Category.TRANSPORTASI)
        make_goal(self.user, category=Goal.Category.PLASTIK)

        response = self.client.get(self.url, {"category": ""})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()), 2)

    def test_invalid_category_is_rejected(self):
        response = self.client.get(self.url, {"category": "ngawur"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json(), {"category": ["Pilihan kategori tidak valid."]})
