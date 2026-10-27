"""Pure business rules: no database needed."""

from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from habits.models import Goal, Habit
from habits.services import (
    STREAK_MILESTONES,
    DayStatus,
    GoalStatus,
    consistency_change,
    consistency_percent,
    current_streak,
    day_counts,
    day_status,
    goal_progress_percent,
    goal_status,
    longest_streak,
    milestones_reached,
    next_milestone,
    period_counts,
)

from .helpers import TODAY, days_ago


def daily_habit(pk=1, start=None):
    return Habit(pk=pk, name="h", start_date=start or days_ago(60))


def weekday_habit(weekdays, pk=1, start=None):
    return Habit(
        pk=pk,
        name="h",
        frequency_type=Habit.Frequency.WEEKDAYS,
        weekdays=weekdays,
        start_date=start or days_ago(60),
    )


def run_of(length, ending_days_ago=0):
    return {days_ago(ending_days_ago + i) for i in range(length)}


class CurrentStreakTests(SimpleTestCase):
    def test_no_checkins_is_zero(self):
        self.assertEqual(current_streak(daily_habit(), set(), TODAY), 0)

    def test_counts_consecutive_days_including_today(self):
        self.assertEqual(current_streak(daily_habit(), run_of(5), TODAY), 5)

    def test_unchecked_today_does_not_break_streak(self):
        self.assertEqual(current_streak(daily_habit(), run_of(4, ending_days_ago=1), TODAY), 4)

    def test_missed_yesterday_resets_to_zero(self):
        self.assertEqual(current_streak(daily_habit(), run_of(4, ending_days_ago=2), TODAY), 0)

    def test_missed_day_inside_run_stops_count(self):
        dates = run_of(2) | run_of(5, ending_days_ago=3)
        self.assertEqual(current_streak(daily_habit(), dates, TODAY), 2)

    def test_does_not_count_before_start_date(self):
        habit = daily_habit(start=days_ago(2))
        self.assertEqual(current_streak(habit, run_of(10), TODAY), 3)

    def test_weekday_habit_skips_unscheduled_days(self):
        # TODAY is a Monday. Scheduled Mon/Wed/Fri: today, last Fri, last Wed.
        habit = weekday_habit("024")
        dates = {TODAY, days_ago(3), days_ago(5)}
        self.assertEqual(current_streak(habit, dates, TODAY), 3)

    def test_weekday_habit_missed_scheduled_day_breaks(self):
        habit = weekday_habit("024")
        dates = {TODAY, days_ago(5)}  # last Friday missed
        self.assertEqual(current_streak(habit, dates, TODAY), 1)


class LongestStreakTests(SimpleTestCase):
    def test_returns_longest_run_ever(self):
        dates = run_of(2) | run_of(6, ending_days_ago=10)
        self.assertEqual(longest_streak(daily_habit(), dates, TODAY), 6)

    def test_unchecked_today_keeps_current_run(self):
        dates = run_of(3, ending_days_ago=1)
        self.assertEqual(longest_streak(daily_habit(), dates, TODAY), 3)

    def test_no_checkins_is_zero(self):
        self.assertEqual(longest_streak(daily_habit(), set(), TODAY), 0)


class MilestoneTests(SimpleTestCase):
    def test_milestones_are_fixed(self):
        self.assertEqual(STREAK_MILESTONES, (3, 7, 14, 30))

    def test_milestones_reached_at_edges(self):
        self.assertEqual(milestones_reached(2), ())
        self.assertEqual(milestones_reached(3), (3,))
        self.assertEqual(milestones_reached(14), (3, 7, 14))
        self.assertEqual(milestones_reached(45), (3, 7, 14, 30))

    def test_next_milestone(self):
        self.assertEqual(next_milestone(0), 3)
        self.assertEqual(next_milestone(3), 7)
        self.assertEqual(next_milestone(29), 30)

    def test_no_next_milestone_after_thirty(self):
        self.assertIsNone(next_milestone(30))
        self.assertIsNone(next_milestone(100))


class DayStatusTests(SimpleTestCase):
    def test_future_day_is_upcoming(self):
        self.assertEqual(day_status(3, 0, TODAY + timedelta(days=1), TODAY), DayStatus.UPCOMING)

    def test_nothing_scheduled_is_empty(self):
        self.assertEqual(day_status(0, 0, days_ago(1), TODAY), DayStatus.EMPTY)

    def test_all_done_is_done(self):
        self.assertEqual(day_status(3, 3, days_ago(1), TODAY), DayStatus.DONE)
        self.assertEqual(day_status(3, 3, TODAY, TODAY), DayStatus.DONE)

    def test_some_done_is_partial(self):
        self.assertEqual(day_status(6, 5, days_ago(1), TODAY), DayStatus.PARTIAL)

    def test_none_done_is_missed(self):
        self.assertEqual(day_status(3, 0, days_ago(1), TODAY), DayStatus.MISSED)

    def test_unfinished_today_is_today(self):
        self.assertEqual(day_status(3, 1, TODAY, TODAY), DayStatus.TODAY)
        self.assertEqual(day_status(3, 0, TODAY, TODAY), DayStatus.TODAY)

    def test_habit_created_later_does_not_count_for_earlier_days(self):
        old = daily_habit(pk=1)
        new = daily_habit(pk=2, start=TODAY)
        checkins = {1: {days_ago(1)}, 2: set()}
        self.assertEqual(day_counts([old, new], checkins, days_ago(1)), (1, 1))
        self.assertEqual(day_counts([old, new], checkins, TODAY), (2, 0))


class ConsistencyTests(SimpleTestCase):
    def test_no_expected_checkins_is_none(self):
        self.assertIsNone(consistency_percent(0, 0))

    def test_integer_percent_rounds_half_up(self):
        self.assertEqual(consistency_percent(2, 3), 67)
        self.assertEqual(consistency_percent(1, 8), 13)  # 12.5
        self.assertEqual(consistency_percent(3, 3), 100)
        self.assertEqual(consistency_percent(0, 5), 0)

    def test_period_never_counts_future_days(self):
        habit = daily_habit()
        checkins = {1: run_of(3)}
        done, expected = period_counts(
            [habit], checkins, days_ago(2), TODAY + timedelta(days=10), TODAY
        )
        self.assertEqual((done, expected), (3, 3))

    def test_change_hidden_without_previous_data(self):
        self.assertIsNone(consistency_change(80, None))
        self.assertIsNone(consistency_change(None, 70))
        self.assertEqual(consistency_change(82, 70), 12)


class GoalRuleTests(SimpleTestCase):
    def goal(self, **fields):
        fields.setdefault("target_value", Decimal("20"))
        fields.setdefault("deadline", TODAY)
        return Goal(title="g", **fields)

    def test_progress_percent_edges(self):
        self.assertEqual(goal_progress_percent(Decimal("0"), Decimal("20")), 0)
        self.assertEqual(goal_progress_percent(Decimal("19.99"), Decimal("20")), 99)
        self.assertEqual(goal_progress_percent(Decimal("20"), Decimal("20")), 100)
        self.assertEqual(goal_progress_percent(Decimal("35"), Decimal("20")), 100)

    def test_deadline_day_itself_is_still_active(self):
        self.assertEqual(goal_status(self.goal(), Decimal("5"), TODAY), GoalStatus.ACTIVE)

    def test_below_target_after_deadline_is_expired(self):
        goal = self.goal(deadline=days_ago(1))
        self.assertEqual(goal_status(goal, Decimal("19"), TODAY), GoalStatus.EXPIRED)

    def test_completed_goal_stays_completed_after_deadline(self):
        goal = self.goal(deadline=days_ago(5), status=Goal.Status.COMPLETED)
        self.assertEqual(goal_status(goal, Decimal("20"), TODAY), GoalStatus.COMPLETED)
