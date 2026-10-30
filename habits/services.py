"""Business rules for habits and goals.

Every derived number (streak, day status, consistency, goal progress) is
computed here, on read, and never stored. Functions that change state also
write Dashboard events in the same transaction.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
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


# A goal is "nearing its deadline" within this many days and below target.
NEAR_DEADLINE_DAYS = 7

# Units counted in whole numbers; kg CO2e may be fractional.
WHOLE_NUMBER_UNITS = (Goal.Unit.KALI, Goal.Unit.HARI)


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


def longest_run(habit, checkin_dates, start, end):
    """Longest run of consecutive scheduled days with a check-in in [start, end]."""
    best = run = 0
    day = max(start, habit.start_date)
    while day <= end:
        if is_scheduled(habit, day):
            if day in checkin_dates:
                run += 1
                best = max(best, run)
            else:
                run = 0
        day += ONE_DAY
    return best


def longest_streak(habit, checkin_dates, today):
    # An unchecked today ends the loop, so it never cuts the best run short.
    return longest_run(habit, checkin_dates, habit.start_date, today)


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


# --- History: heatmap, periods, per-habit statistics -----------------------------


def heat_level(scheduled, done):
    """Heatmap level 0-4 for a day: 0 = nothing done, 4 = every habit done.

    Buckets: 1 = 1-39%, 2 = 40-69%, 3 = 70-99%. The percent is rounded down
    so a day only reaches level 4 when it is truly complete.
    """
    if scheduled == 0 or done == 0:
        return 0
    if done >= scheduled:
        return 4
    percent = done * 100 // scheduled
    if percent < 40:
        return 1
    if percent < 70:
        return 2
    return 3


def perfect_days(habits, checkins_by_habit, start, end, today):
    """Days in [start, end] (never past today) on which every scheduled habit was done."""
    count = 0
    day = start
    while day <= min(end, today):
        scheduled, done = day_counts(habits, checkins_by_habit, day)
        if scheduled and done >= scheduled:
            count += 1
        day += ONE_DAY
    return count


def month_bounds(year, month):
    first = date(year, month, 1)
    last = date(year + month // 12, month % 12 + 1, 1) - ONE_DAY
    return first, last


def shift_month(year, month, delta):
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def missed_habits(habits, checkins_by_habit, day):
    """Habits scheduled on a day that got no check-in."""
    return [
        habit for habit in habits
        if is_scheduled(habit, day) and day not in checkins_by_habit.get(habit.pk, ())
    ]


def strongest_weekday(habit, checkin_dates, start, end):
    """Weekday (0 = Monday) with the most check-ins in [start, end], or None.

    Ties go to the earlier weekday.
    """
    counts = [0] * 7
    for day in checkin_dates:
        if start <= day <= end and is_scheduled(habit, day):
            counts[day.weekday()] += 1
    best = max(counts)
    return counts.index(best) if best else None


def habit_month_stats(habit, checkin_dates, year, month, today):
    """Check-ins, scheduled days so far, success rate, longest run, strongest day."""
    first, last = month_bounds(year, month)
    end = min(last, today)
    scheduled = done = 0
    day = max(first, habit.start_date)
    while day <= end:
        if is_scheduled(habit, day):
            scheduled += 1
            done += day in checkin_dates
        day += ONE_DAY
    return {
        "done": done,
        "scheduled": scheduled,
        "rate": consistency_percent(done, scheduled),
        "longest": longest_run(habit, checkin_dates, first, end),
        "strongest_weekday": strongest_weekday(habit, checkin_dates, first, end),
    }


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


def days_until(deadline, today):
    """Whole days from today to the deadline; 0 on the deadline day."""
    return (deadline - today).days


def is_near_deadline(goal, progress, today):
    return (
        goal_status(goal, progress, today) == GoalStatus.ACTIVE
        and progress < goal.target_value
        and 0 <= days_until(goal.deadline, today) <= NEAR_DEADLINE_DAYS
    )

def check_amount(unit, amount):
    """Reject fractions for units that are counted in whole numbers."""
    amount = Decimal(amount)
    if unit in WHOLE_NUMBER_UNITS and amount != amount.to_integral_value():
        raise ValidationError("Untuk satuan kali atau hari, isi dengan bilangan bulat.")


def toggle_checklist_item(item):
    """Flip a checklist item. The checklist never decides goal completion."""
    item.is_done = not item.is_done
    item.done_at = timezone.now() if item.is_done else None
    item.save(update_fields=["is_done", "done_at"])
    return item


def refresh_goal_after_edit(goal):
    """Bring the stored status in line after the target or dates changed.

    An expired goal whose deadline moved to today or later becomes active
    again; any goal may now meet its target and complete (once).
    """
    today = local_today()
    with transaction.atomic():
        goal = Goal.objects.select_for_update().get(pk=goal.pk)
        if goal.status == Goal.Status.EXPIRED and goal.deadline >= today:
            goal.status = Goal.Status.ACTIVE
            goal.save(update_fields=["status"])
        complete_goal_if_reached(goal)
    expire_overdue_goals(Goal.objects.filter(pk=goal.pk), today)


def expire_overdue_goals(goals, today=None):
    """Mark active goals whose deadline has passed below target as "expired".

    There is no background job, so this runs whenever the module's pages or
    progress logging touch the goals. Returns the number of goals updated.
    """
    today = today or local_today()
    updated = 0
    for goal in goals.filter(status=Goal.Status.ACTIVE, deadline__lt=today):
        if goal_progress_total(goal) < goal.target_value:
            goal.status = Goal.Status.EXPIRED
            goal.save(update_fields=["status"])
            updated += 1
    return updated


def log_goal_progress(goal, amount, note=""):
    """Add progress to an active goal; return the completion event, if any."""
    check_amount(goal.unit, amount)
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
