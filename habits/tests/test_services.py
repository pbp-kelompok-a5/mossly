"""State-changing services: check-ins, progress, and Dashboard events."""

from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from habits import services
from habits.models import Goal, HabitCheckIn, SustainabilityEvent

from .helpers import (
    TODAY,
    FrozenClockMixin,
    days_ago,
    freeze_time,
    make_goal,
    make_habit,
    make_user,
)


def milestone_events(habit=None):
    queryset = SustainabilityEvent.objects.filter(
        event_type=SustainabilityEvent.EventType.HABIT_MILESTONE
    )
    if habit is not None:
        queryset = queryset.filter(habit=habit)
    return queryset


class CheckInTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.habit = make_habit(self.user)

    def check_in_days(self, *offsets):
        for n in offsets:
            services.check_in(self.habit, days_ago(n))

    def test_check_in_defaults_to_today(self):
        services.check_in(self.habit)
        self.assertTrue(self.habit.checkins.filter(checkin_date=TODAY).exists())

    def test_checking_in_twice_keeps_one_row(self):
        services.check_in(self.habit)
        services.check_in(self.habit)
        self.assertEqual(self.habit.checkins.count(), 1)

    def test_future_check_in_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.check_in(self.habit, TODAY + timedelta(days=1))

    def test_unscheduled_day_is_rejected(self):
        habit = make_habit(self.user, frequency_type="weekdays", weekdays="1")  # Tuesdays
        with self.assertRaises(ValidationError):
            services.check_in(habit, TODAY)  # Monday

    def test_third_day_sends_milestone_event(self):
        self.check_in_days(2, 1)
        self.assertFalse(milestone_events().exists())
        created = services.check_in(self.habit)
        self.assertEqual([e.milestone_days for e in created], [3])
        event = milestone_events(self.habit).get()
        self.assertEqual(event.user, self.user)
        self.assertEqual(event.title_snapshot, "Bawa tumbler")
        self.assertEqual(event.payload, {"streak_days": 3})

    def test_recheck_and_undo_never_duplicate_milestone(self):
        self.check_in_days(2, 1, 0)
        services.check_in(self.habit)
        services.undo_check_in(self.habit)
        created = services.check_in(self.habit)
        self.assertEqual(created, [])
        self.assertEqual(milestone_events(self.habit).count(), 1)

    def test_undo_keeps_sent_event(self):
        self.check_in_days(2, 1, 0)
        services.undo_check_in(self.habit)
        self.assertFalse(self.habit.checkins.filter(checkin_date=TODAY).exists())
        self.assertEqual(milestone_events(self.habit).count(), 1)

    def test_undo_only_removes_today(self):
        self.check_in_days(1, 0)
        services.undo_check_in(self.habit)
        self.assertEqual(
            list(self.habit.checkins.values_list("checkin_date", flat=True)), [days_ago(1)]
        )

    def test_jumping_past_milestones_sends_each_once(self):
        # Fill a 7-day run with a gap, then close the gap in one step.
        self.check_in_days(6, 5, 4, 2, 1, 0)
        self.assertEqual(
            sorted(milestone_events(self.habit).values_list("milestone_days", flat=True)), [3]
        )
        created = services.check_in(self.habit, days_ago(3))
        self.assertEqual([e.milestone_days for e in created], [7])
        self.assertEqual(
            sorted(milestone_events(self.habit).values_list("milestone_days", flat=True)), [3, 7]
        )

    def test_milestone_reached_again_after_break_is_not_resent(self):
        self.check_in_days(10, 9, 8)  # reached 3, then broke
        self.check_in_days(2, 1, 0)  # reached 3 again
        self.assertEqual(milestone_events(self.habit).count(), 1)

    def test_deleting_habit_keeps_events(self):
        self.check_in_days(2, 1, 0)
        habit_pk = self.habit.pk
        self.habit.delete()
        self.assertFalse(HabitCheckIn.objects.filter(habit_id=habit_pk).exists())
        event = milestone_events().get()
        self.assertIsNone(event.habit)
        self.assertEqual(event.title_snapshot, "Bawa tumbler")

    def test_database_rejects_duplicate_milestone_event(self):
        self.check_in_days(2, 1, 0)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SustainabilityEvent.objects.create(
                user=self.user,
                event_type=SustainabilityEvent.EventType.HABIT_MILESTONE,
                habit=self.habit,
                milestone_days=3,
                title_snapshot="dup",
            )


class DayRolloverTests(TestCase):
    """A day is the local calendar day in Asia/Jakarta (UTC+7)."""

    def setUp(self):
        self.user = make_user()
        self.habit = make_habit(self.user)

    def test_one_second_before_midnight_wib_is_still_previous_day(self):
        with freeze_time(datetime(2026, 10, 25, 16, 59, 59, tzinfo=dt_timezone.utc)):
            services.check_in(self.habit)
        self.assertEqual(self.habit.checkins.get().checkin_date, TODAY - timedelta(days=1))

    def test_midnight_wib_starts_new_day(self):
        with freeze_time(datetime(2026, 10, 25, 17, 0, tzinfo=dt_timezone.utc)):
            services.check_in(self.habit)
        self.assertEqual(self.habit.checkins.get().checkin_date, TODAY)

    def test_streak_survives_until_midnight_then_counts_from_yesterday(self):
        with freeze_time(datetime(2026, 10, 25, 16, 0, tzinfo=dt_timezone.utc)):
            services.check_in(self.habit)  # 25 Oct, 23:00 WIB
        with freeze_time(datetime(2026, 10, 25, 18, 0, tzinfo=dt_timezone.utc)):
            dates = {c.checkin_date for c in self.habit.checkins.all()}
            today = services.local_today()  # 26 Oct, 01:00 WIB
            self.assertEqual(services.current_streak(self.habit, dates, today), 1)


class GoalProgressTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.goal = make_goal(self.user)  # target 20 kali, deadline in 4 days

    def goal_events(self):
        return SustainabilityEvent.objects.filter(
            event_type=SustainabilityEvent.EventType.GOAL_COMPLETED
        )

    def test_below_target_stays_active_without_event(self):
        self.assertIsNone(services.log_goal_progress(self.goal, Decimal("19")))
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, Goal.Status.ACTIVE)
        self.assertFalse(self.goal_events().exists())

    def test_progress_is_sum_of_logs(self):
        services.log_goal_progress(self.goal, Decimal("5"))
        services.log_goal_progress(self.goal, Decimal("2.5"))
        self.assertEqual(services.goal_progress_total(self.goal), Decimal("7.5"))

    def test_exactly_at_target_completes_and_sends_event(self):
        services.log_goal_progress(self.goal, Decimal("12"))
        event = services.log_goal_progress(self.goal, Decimal("8"), "Pulang naik KRL")
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, Goal.Status.COMPLETED)
        self.assertIsNotNone(self.goal.completed_at)
        self.assertEqual(event.goal, self.goal)
        self.assertEqual(event.title_snapshot, "Naik transportasi umum 20 kali")
        self.assertEqual(
            event.payload,
            {"target": 20, "unit": "kali", "category": "transportasi", "days_before_deadline": 4},
        )

    def test_completion_on_deadline_day_reports_zero_days_early(self):
        goal = make_goal(self.user, deadline=TODAY, target_value=Decimal("2.5"), unit="kg_co2e")
        event = services.log_goal_progress(goal, Decimal("2.5"))
        self.assertEqual(event.payload["days_before_deadline"], 0)
        self.assertEqual(event.payload["target"], 2.5)

    def test_completed_goal_rejects_more_progress_and_never_duplicates(self):
        services.log_goal_progress(self.goal, Decimal("20"))
        with self.assertRaises(ValidationError):
            services.log_goal_progress(self.goal, Decimal("1"))
        self.goal.refresh_from_db()
        self.assertIsNone(services.complete_goal_if_reached(self.goal))
        self.assertEqual(self.goal_events().count(), 1)

    def test_resaving_after_target_change_does_not_duplicate(self):
        services.log_goal_progress(self.goal, Decimal("20"))
        self.goal.refresh_from_db()
        self.goal.target_value = Decimal("10")
        self.goal.save()
        with transaction.atomic():
            services.complete_goal_if_reached(self.goal)
        self.assertEqual(self.goal_events().count(), 1)

    def test_lowering_target_to_progress_completes_goal(self):
        services.log_goal_progress(self.goal, Decimal("10"))
        self.goal.target_value = Decimal("10")
        self.goal.save()
        with transaction.atomic():
            event = services.complete_goal_if_reached(self.goal)
        self.assertIsNotNone(event)

    def test_expired_goal_rejects_progress(self):
        goal = make_goal(self.user, start_date=days_ago(30), deadline=days_ago(1))
        with self.assertRaises(ValidationError):
            services.log_goal_progress(goal, Decimal("1"))
        self.assertFalse(goal.progress_logs.exists())

    def test_deleting_goal_keeps_event(self):
        services.log_goal_progress(self.goal, Decimal("20"))
        self.goal.delete()
        event = self.goal_events().get()
        self.assertIsNone(event.goal)
        self.assertEqual(event.payload["days_before_deadline"], 4)

    def test_database_rejects_duplicate_goal_event(self):
        services.log_goal_progress(self.goal, Decimal("20"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            SustainabilityEvent.objects.create(
                user=self.user,
                event_type=SustainabilityEvent.EventType.GOAL_COMPLETED,
                goal=self.goal,
                title_snapshot="dup",
            )
