from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest import mock

from django.contrib.auth import get_user_model

from habits.models import Goal, Habit

# 12:00 WIB on Monday 2026-10-26.
FIXED_NOW = datetime(2026, 10, 26, 5, 0, tzinfo=dt_timezone.utc)
TODAY = date(2026, 10, 26)


def days_ago(n):
    return TODAY - timedelta(days=n)


def freeze_time(instant):
    """Pin Django's clock; localdate() reads it, so the local day follows."""
    return mock.patch("django.utils.timezone.now", return_value=instant)


class FrozenClockMixin:
    """Run every test at FIXED_NOW unless the test patches the clock itself."""

    def setUp(self):
        super().setUp()
        patcher = freeze_time(FIXED_NOW)
        patcher.start()
        self.addCleanup(patcher.stop)


def make_user(username="tania"):
    return get_user_model().objects.create_user(username=username, password="pw-12345")


def make_habit(user, **fields):
    fields.setdefault("name", "Bawa tumbler")
    fields.setdefault("start_date", days_ago(60))
    return Habit.objects.create(user=user, **fields)


def make_goal(user, **fields):
    fields.setdefault("title", "Naik transportasi umum 20 kali")
    fields.setdefault("category", Goal.Category.TRANSPORTASI)
    fields.setdefault("target_value", 20)
    fields.setdefault("unit", Goal.Unit.KALI)
    fields.setdefault("start_date", days_ago(25))
    fields.setdefault("deadline", TODAY + timedelta(days=4))
    return Goal.objects.create(user=user, **fields)
