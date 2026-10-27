from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import display, services
from .forms import GoalProgressForm, HabitForm
from .models import Goal, Habit, SustainabilityEvent

# Session key holding the milestone event to celebrate on the next page load.
MILESTONE_SESSION_KEY = "habits_new_milestone"
SENT_EVENTS_SHOWN = 3


def _display_name(user):
    # display_name belongs to the Login module's user model once it exists.
    return getattr(user, "display_name", "") or user.first_name or user.get_username()


def _habit_row(habit, dates, today):
    return {
        "pk": habit.pk,
        "name": habit.name,
        "icon": habit.icon,
        "tint": habit.tint,
        "streak": services.current_streak(habit, dates, today),
        "is_done": today in dates,
        "never_checked_in": not dates,
    }


def _week_strip(habits, checkins, today):
    monday = today - timedelta(days=today.weekday())
    days = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        scheduled, done = services.day_counts(habits, checkins, day)
        days.append(
            {
                "short": display.DAY_SHORT[offset],
                "number": day.day,
                "label": display.long_date(day),
                "status": services.day_status(scheduled, done, day, today),
                "is_today": day == today,
                "scheduled": scheduled,
                "done": done,
            }
        )
    return days


def _next_milestone_card(habits, checkins, today):
    """The habit closest to its next milestone, or a flag when all are reached."""
    best = None
    for habit in habits:
        streak = services.current_streak(habit, checkins[habit.pk], today)
        target = services.next_milestone(streak)
        if target is None:
            continue
        candidate = (target - streak, -streak, habit.name, target, streak)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        return {"all_reached": True}
    days_left, _, name, target, streak = best
    return {"all_reached": False, "target": target, "name": name, "days_left": days_left, "streak": streak}


def _sent_milestones(user, today):
    events = SustainabilityEvent.objects.filter(
        user=user, event_type=SustainabilityEvent.EventType.HABIT_MILESTONE
    )[:SENT_EVENTS_SHOWN]
    return [
        {
            "title": f"{event.title_snapshot} · {event.milestone_days} hari",
            "date": display.short_date(timezone.localdate(event.occurred_at), today),
        }
        for event in events
    ]


def _pop_milestone(request):
    pk = request.session.pop(MILESTONE_SESSION_KEY, None)
    if pk is None:
        return None
    event = SustainabilityEvent.objects.filter(pk=pk, user=request.user).first()
    if event is None:
        return None
    return {
        "days": event.milestone_days,
        "name": event.title_snapshot,
        "badge": display.MILESTONE_BADGES.get(event.milestone_days),
    }


def _form_context(form):
    return {"form": form, "milestone_list": display.milestone_list_text()}


@login_required
def index(request):
    today = services.local_today()
    services.expire_overdue_goals(request.user.goals.all(), today)
    habits = list(request.user.habits.all())
    context = {
        "greeting": display.greeting(timezone.localtime().hour),
        "display_name": _display_name(request.user),
        "milestone": _pop_milestone(request),
        **_form_context(HabitForm()),
    }
    if not habits:
        context.update(is_empty=True, suggestions=display.HABIT_SUGGESTIONS)
        return render(request, "habits/habit_list.html", context)

    checkins = services.checkins_by_habit(habits)
    groups = {key: [] for key in Habit.TimeOfDay.values}
    unscheduled = []
    longest = 0
    for habit in habits:
        dates = checkins[habit.pk]
        longest = max(longest, services.longest_streak(habit, dates, today))
        row = _habit_row(habit, dates, today)
        if services.is_scheduled(habit, today):
            groups[habit.time_of_day].append(row)
        else:
            unscheduled.append(row)

    scheduled, done = services.day_counts(habits, checkins, today)
    context.update(
        is_empty=False,
        today_label=display.long_date(today),
        scheduled_today=scheduled,
        done_today=done,
        remaining_today=scheduled - done,
        done_percent=done * 100 // scheduled if scheduled else 0,
        longest_streak=longest,
        week=_week_strip(habits, checkins, today),
        groups=[
            {
                "label": Habit.TimeOfDay(key).label,
                "icon": display.TIME_OF_DAY_ICONS[key],
                "rows": rows,
                "done": sum(row["is_done"] for row in rows),
            }
            for key, rows in groups.items()
            if rows
        ],
        unscheduled=unscheduled,
        next_milestone=_next_milestone_card(habits, checkins, today),
        sent_milestones=_sent_milestones(request.user, today),
    )
    return render(request, "habits/habit_list.html", context)


@login_required
def habit_create(request):
    if request.method == "POST":
        form = HabitForm(request.POST, instance=Habit(user=request.user))
        if form.is_valid():
            form.save()
            return redirect("habits:index")
    else:
        # Suggestions in the empty state link here with a prefilled name and icon.
        initial = {}
        if request.GET.get("name"):
            initial["name"] = request.GET["name"][:80]
        if request.GET.get("icon") in Habit.Icon.values:
            initial["icon"] = request.GET["icon"]
        form = HabitForm(initial=initial)
    return render(request, "habits/habit_form.html", {**_form_context(form), "is_edit": False})


@login_required
def habit_edit(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    form = HabitForm(request.POST or None, instance=habit)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("habits:index")
    return render(
        request,
        "habits/habit_form.html",
        {**_form_context(form), "is_edit": True, "habit": habit},
    )


@login_required
def habit_delete(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    if request.method == "POST":
        habit.delete()
        return redirect("habits:index")
    return render(request, "habits/habit_confirm_delete.html", {"habit": habit})


@login_required
@require_POST
def habit_check_in(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    try:
        events = services.check_in(habit)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    else:
        if events:
            # Celebrate the highest milestone when several are crossed at once.
            top = max(events, key=lambda event: event.milestone_days)
            request.session[MILESTONE_SESSION_KEY] = top.pk
    return redirect("habits:index")


@login_required
@require_POST
def habit_undo_check_in(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    services.undo_check_in(habit)
    return redirect("habits:index")


@login_required
@require_POST
def goal_log_progress(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    form = GoalProgressForm(request.POST)
    if form.is_valid():
        try:
            services.log_goal_progress(
                goal, form.cleaned_data["amount"], form.cleaned_data["note"]
            )
        except ValidationError as error:
            messages.error(request, error.messages[0])
    else:
        messages.error(request, "Jumlah progres harus lebih dari 0.")
    return redirect("habits:index")


@login_required
@require_POST
def goal_delete(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    goal.delete()
    return redirect("habits:index")
