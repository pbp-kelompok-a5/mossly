"""Server-side validation of habits and goals."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from habits.models import Goal, Habit

from .helpers import TODAY, FrozenClockMixin, days_ago, make_user


class HabitValidationTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def habit(self, **fields):
        fields.setdefault("name", "Pilah sampah")
        return Habit(user=self.user, **fields)

    def assert_invalid(self, obj, field):
        with self.assertRaises(ValidationError) as ctx:
            obj.full_clean()
        self.assertIn(field, ctx.exception.message_dict)

    def test_valid_daily_habit(self):
        habit = self.habit()
        habit.full_clean()
        self.assertEqual(habit.start_date, TODAY)

    def test_name_longer_than_80_is_rejected(self):
        self.assert_invalid(self.habit(name="x" * 81), "name")

    def test_weekdays_required_for_weekday_habit(self):
        self.assert_invalid(self.habit(frequency_type="weekdays"), "weekdays")

    def test_invalid_weekday_digits_are_rejected(self):
        self.assert_invalid(self.habit(frequency_type="weekdays", weekdays="07"), "weekdays")
        self.assert_invalid(self.habit(frequency_type="weekdays", weekdays="11"), "weekdays")

    def test_weekdays_are_normalised(self):
        weekly = self.habit(frequency_type="weekdays", weekdays="420")
        weekly.full_clean()
        self.assertEqual(weekly.weekdays, "024")
        daily = self.habit(weekdays="135")
        daily.full_clean()
        self.assertEqual(daily.weekdays, "")

    def test_times_per_week_frequency_is_not_offered_yet(self):
        self.assert_invalid(self.habit(frequency_type="times_per_week"), "frequency_type")

    def test_times_per_week_range(self):
        self.assert_invalid(self.habit(times_per_week=0), "times_per_week")
        self.assert_invalid(self.habit(times_per_week=8), "times_per_week")

    def test_unknown_icon_is_rejected(self):
        self.assert_invalid(self.habit(icon="rocket"), "icon")


class GoalValidationTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def goal(self, **fields):
        fields.setdefault("title", "30 hari tanpa beli botol plastik")
        fields.setdefault("category", Goal.Category.PLASTIK)
        fields.setdefault("target_value", 30)
        fields.setdefault("unit", Goal.Unit.HARI)
        fields.setdefault("deadline", TODAY)
        return Goal(user=self.user, **fields)

    def assert_invalid(self, obj, field):
        with self.assertRaises(ValidationError) as ctx:
            obj.full_clean()
        self.assertIn(field, ctx.exception.message_dict)

    def test_deadline_equal_to_start_is_valid(self):
        self.goal(start_date=TODAY, deadline=TODAY).full_clean()

    def test_deadline_before_start_is_rejected(self):
        self.assert_invalid(self.goal(start_date=TODAY, deadline=days_ago(1)), "deadline")

    def test_target_must_be_positive(self):
        self.assert_invalid(self.goal(target_value=0), "target_value")
        self.assert_invalid(self.goal(target_value=-5), "target_value")

    def test_title_longer_than_120_is_rejected(self):
        self.assert_invalid(self.goal(title="x" * 121), "title")

    def test_unknown_category_is_rejected(self):
        self.assert_invalid(self.goal(category="energi"), "category")
