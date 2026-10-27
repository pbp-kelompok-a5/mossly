"""Business rules for habits and goals.

Every derived number (streak, day status, consistency, goal progress) is
computed here, on read, and never stored. Functions that change state also
write Dashboard events in the same transaction.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Goal, GoalProgressLog, Habit, HabitCheckIn, SustainabilityEvent

STREAK_MILESTONES = (3, 7, 14, 30)

ONE_DAY = timedelta(days=1)


class DayStatus:
    DONE = "done"
    PARTIAL = "partial"
    MISSED = "missed"
    TODAY = "today"
    UPCOMING = "upcoming"
    EMPTY = "empty"  # nothing was scheduled that day


class GoalStatus:
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"


def local_today():
    return timezone.localdate()


# --- Habits: schedule and streak ---------------------------------------------


def is_scheduled(habit, day):
    """Whether the habit expects a check-in on this local date."""
    if day < habit.start_date:
        return False
    if habit.frequency_type == Habit.Frequency.WEEKDAYS:
        return day.weekday() in habit.weekday_numbers
    return True


def current_streak(habit, checkin_dates, today):
    """Consecutive scheduled days with a check-in, counting back from today.

    An unchecked today does not break the streak yet, because the day is not
    over. Unscheduled days are skipped rather than counted as missed.
    """
    day = today if today in checkin_dates else today - ONE_DAY
    streak = 0
    while day >= habit.start_date:
        if is_scheduled(habit, day):
            if day not in checkin_dates:
                break
            streak += 1
        day -= ONE_DAY
    return streak


def longest_streak(habit, checkin_dates, today):
    best = run = 0
    day = habit.start_date
    while day <= today:
        if is_scheduled(habit, day):
            if day in checkin_dates:
                run += 1
                best = max(best, run)
            elif day < today:
                run = 0
        day += ONE_DAY
    return best


def milestones_reached(streak):
    return tuple(m for m in STREAK_MILESTONES if m <= streak)


def next_milestone(streak):
    """The next milestone to aim for, or None once every milestone is reached."""
    return next((m for m in STREAK_MILESTONES if m > streak), None)


# --- Habits: day status and consistency --------------------------------------


def day_counts(habits, checkins_by_habit, day):
    """(scheduled, done) for one day across the given habits.

    checkins_by_habit maps habit id to a set of check-in dates.
    """
    scheduled = done = 0
    for habit in habits:
        if is_scheduled(habit, day):
            scheduled += 1
            if day in checkins_by_habit.get(habit.pk, ()):
                done += 1
    return scheduled, done


def day_status(scheduled, done, day, today):
    if day > today:
        return DayStatus.UPCOMING
    if scheduled == 0:
        return DayStatus.EMPTY
    if done >= scheduled:
        return DayStatus.DONE
    # Today can still be completed, so it is never shown as missed or partial.
    if day == today:
        return DayStatus.TODAY
    if done == 0:
        return DayStatus.MISSED
    return DayStatus.PARTIAL


def period_counts(habits, checkins_by_habit, start, end, today):
    """(done, expected) check-ins between start and end, never past today."""
    done = expected = 0
    day = start
    last = min(end, today)
    while day <= last:
        scheduled, done_today = day_counts(habits, checkins_by_habit, day)
        expected += scheduled
        done += done_today
        day += ONE_DAY
    return done, expected


def consistency_percent(done, expected):
    """Integer percent (rounded half up), or None when nothing was expected."""
    if expected <= 0:
        return None
    return (done * 200 + expected) // (expected * 2)


def consistency_change(current, previous):
    """Percentage-point change, or None when either period has no data."""
    if current is None or previous is None:
        return None
    return current - previous


def checkins_by_habit(habits, start=None, end=None):
    """Load check-in dates for the given habits as {habit_id: set(dates)}."""
    queryset = HabitCheckIn.objects.filter(habit__in=habits)
    if start is not None:
        queryset = queryset.filter(checkin_date__gte=start)
    if end is not None:
        queryset = queryset.filter(checkin_date__lte=end)
    result = {habit.pk: set() for habit in habits}
    for habit_id, checkin_date in queryset.values_list("habit_id", "checkin_date"):
        result.setdefault(habit_id, set()).add(checkin_date)
    return result


# --- Habits: state changes ---------------------------------------------------


def check_in(habit, day=None):
    """Record a check-in and return any milestone events it newly created."""
    today = local_today()
    day = day or today
    if day > today:
        raise ValidationError("Check-in hanya bisa untuk hari ini atau sebelumnya.")
    if not is_scheduled(habit, day):
        raise ValidationError("Habit ini tidak dijadwalkan pada hari tersebut.")

    with transaction.atomic():
        # Lock the habit so concurrent check-ins cannot both write a milestone.
        habit = Habit.objects.select_for_update().get(pk=habit.pk)
        HabitCheckIn.objects.get_or_create(habit=habit, checkin_date=day)
        dates = set(habit.checkins.values_list("checkin_date", flat=True))
        # The longest run, not only the current one, so back-filling an old
        # gap still counts every milestone the habit has truly reached.
        streak = longest_streak(habit, dates, today)
        return _record_milestones(habit, streak)


def undo_check_in(habit):
    """Remove today's check-in. Events already sent are never retracted."""
    HabitCheckIn.objects.filter(habit=habit, checkin_date=local_today()).delete()


def _record_milestones(habit, streak):
    already_sent = set(
        SustainabilityEvent.objects.filter(
            habit=habit, event_type=SustainabilityEvent.EventType.HABIT_MILESTONE
        ).values_list("milestone_days", flat=True)
    )
    created = []
    for days in milestones_reached(streak):
        if days in already_sent:
            continue
        created.append(
            SustainabilityEvent.objects.create(
                user=habit.user,
                event_type=SustainabilityEvent.EventType.HABIT_MILESTONE,
                habit=habit,
                milestone_days=days,
                title_snapshot=habit.name,
                payload={"streak_days": days},
            )
        )
    return created


# --- Goals -------------------------------------------------------------------


def goal_progress_total(goal):
    total = goal.progress_logs.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


def goal_progress_percent(progress, target):
    """Rounded down so a goal never reads 100% before it is actually reached."""
    if target <= 0:
        return 0
    return min(100, int(progress * 100 // target))


def goal_status(goal, progress, today):
    """The goal's status as of today, even if the stored value is not refreshed yet."""
    if goal.status == Goal.Status.COMPLETED:
        return GoalStatus.COMPLETED
    if goal.status == Goal.Status.EXPIRED:
        return GoalStatus.EXPIRED
    if today > goal.deadline and progress < goal.target_value:
        return GoalStatus.EXPIRED
    return GoalStatus.ACTIVE


def expire_overdue_goals(goals, today=None):
    """Store "expired" on active goals past their deadline and below target.

    There is no background job, so this runs whenever the module's pages or
    progress logging touch the goals. Returns the number of goals updated.
    """
    today = today or local_today()
    overdue = (
        goals.filter(status=Goal.Status.ACTIVE, deadline__lt=today)
        .annotate(
            progress=Coalesce(
                Sum("progress_logs__amount"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
        .filter(progress__lt=F("target_value"))
        .values("pk")
    )
    return Goal.objects.filter(pk__in=overdue).update(status=Goal.Status.EXPIRED)


def log_goal_progress(goal, amount, note=""):
    """Add progress to an active goal; return the completion event, if any."""
    # Outside the transaction below, so a rejected log does not roll it back.
    expire_overdue_goals(Goal.objects.filter(pk=goal.pk))
    with transaction.atomic():
        goal = Goal.objects.select_for_update().get(pk=goal.pk)
        if goal.status != Goal.Status.ACTIVE:
            raise ValidationError("Progres hanya bisa dicatat untuk goal yang masih aktif.")
        GoalProgressLog.objects.create(goal=goal, amount=amount, note=note)
        return complete_goal_if_reached(goal)


def complete_goal_if_reached(goal):
    """Mark the goal completed and write its event once progress meets the target.

    Must run inside the transaction that changed the progress or the target.
    """
    if goal.status != Goal.Status.ACTIVE:
        return None
    if goal_progress_total(goal) < goal.target_value:
        return None

    now = timezone.now()
    goal.status = Goal.Status.COMPLETED
    goal.completed_at = now
    goal.save(update_fields=["status", "completed_at"])

    event, _ = SustainabilityEvent.objects.get_or_create(
        goal=goal,
        event_type=SustainabilityEvent.EventType.GOAL_COMPLETED,
        defaults={
            "user": goal.user,
            "title_snapshot": goal.title,
            "occurred_at": now,
            "payload": {
                "target": _json_number(goal.target_value),
                "unit": goal.unit,
                "category": goal.category,
                "days_before_deadline": (goal.deadline - timezone.localdate(now)).days,
            },
        },
    )
    return event


def _json_number(value):
    value = Decimal(value)
    return int(value) if value == value.to_integral_value() else float(value)
