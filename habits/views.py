from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import display, services
from .forms import GoalForm, GoalProgressForm, HabitForm
from .models import Goal, GoalChecklistItem, Habit, SustainabilityEvent

# Session key holding the milestone event to celebrate on the next page load.
MILESTONE_SESSION_KEY = "habits_new_milestone"
SENT_EVENTS_SHOWN = 3
RECENT_COMPLETED_SHOWN = 4
GOAL_COMPLETED_MESSAGE = "Goal selesai! Pencapaian ini sudah terkirim ke Personal Dashboard."


def _redirect_back(request, fallback, *args):
    """Return to the page that posted the form when it is on this site."""
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect(fallback, *args)


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
        return render(request, "habits/habit/habit_list.html", context)

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
    return render(request, "habits/habit/habit_list.html", context)


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
    return render(request, "habits/habit/habit_form.html", {**_form_context(form), "is_edit": False})


@login_required
def habit_edit(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    form = HabitForm(request.POST or None, instance=habit)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("habits:index")
    return render(
        request,
        "habits/habit/habit_form.html",
        {**_form_context(form), "is_edit": True, "habit": habit},
    )


@login_required
def habit_delete(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    if request.method == "POST":
        habit.delete()
        return redirect("habits:index")
    return render(request, "habits/habit/habit_confirm_delete.html", {"habit": habit})


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


# --- Goals -------------------------------------------------------------------


def _goal_progress(goal):
    # Uses the prefetched logs, so a list of goals costs no query per goal.
    return sum((log.amount for log in goal.progress_logs.all()), Decimal("0"))


def _goal_card(goal, today):
    progress = _goal_progress(goal)
    items = list(goal.checklist_items.all())
    status = services.goal_status(goal, progress, today)
    days_left = services.days_until(goal.deadline, today)
    unit_short = display.UNIT_SHORT[goal.unit]
    remaining = max(goal.target_value - progress, Decimal("0"))
    if days_left > 0:
        deadline_text = f"Deadline {display.day_month(goal.deadline)} · {days_left} hari lagi"
        time_left = f"dalam {days_left} hari"
    elif days_left == 0:
        deadline_text, time_left = "Deadline hari ini", "hari ini"
    else:
        deadline_text, time_left = f"Deadline {display.day_month(goal.deadline)} · terlewat", ""
    completed_on = timezone.localdate(goal.completed_at) if goal.completed_at else None
    after_one = progress + 1
    preview_text = (
        f"{display.format_amount(after_one)} / {display.format_amount(goal.target_value)} {unit_short}"
        f" ({services.goal_progress_percent(after_one, goal.target_value)}%)"
    )
    return {
        "progress_dialog_id": f"progress-dialog-{goal.pk}",
        "progress_title_id": f"progress-title-{goal.pk}",
        "preview_text": preview_text,
        "pk": goal.pk,
        "title": goal.title,
        "category": goal.get_category_display(),
        "status": status,
        "target_text": f"{display.format_amount(goal.target_value)} {goal.get_unit_display()}",
        "period": display.date_range(goal.start_date, goal.deadline),
        "period_long": display.date_range(goal.start_date, goal.deadline, with_year=True),
        "progress_text": f"{display.format_amount(progress)} / {display.format_amount(goal.target_value)} {unit_short}",
        "percent": services.goal_progress_percent(progress, goal.target_value),
        "progress": progress,
        "target": goal.target_value,
        "unit_short": unit_short,
        "remaining_text": f"{display.format_amount(remaining)} {unit_short}",
        "days_left": days_left,
        "time_left": time_left,
        "deadline_text": deadline_text,
        "is_near": services.is_near_deadline(goal, progress, today),
        "checklist_done": sum(item.is_done for item in items),
        "checklist_total": len(items),
        "completed_at": goal.completed_at,
        "completed_text": f"Selesai {display.day_month(completed_on)}" if completed_on else "",
        "amount_prompt": display.AMOUNT_PROMPTS[goal.unit],
    }


def _goal_initial(request, today):
    """Defaults for a new goal, prefilled from an example goal when given."""
    initial = {"start_date": today}
    params = request.GET
    if params.get("title"):
        initial["title"] = params["title"][:120]
    if params.get("category") in Goal.Category.values:
        initial["category"] = params["category"]
    if params.get("unit") in Goal.Unit.values:
        initial["unit"] = params["unit"]
    if params.get("target", "").isdigit():
        initial["target_value"] = int(params["target"])
    if params.get("days", "").isdigit() and 0 < int(params["days"]) <= 366:
        initial["deadline"] = today + timedelta(days=int(params["days"]) - 1)
    return initial


def _goal_form_context(form, today):
    return {"form": form, "today_iso": today.isoformat()}


def _owned_goal(request, pk):
    return get_object_or_404(
        Goal.objects.prefetch_related("checklist_items", "progress_logs"),
        pk=pk,
        user=request.user,
    )


@login_required
def goal_list(request):
    today = services.local_today()
    services.expire_overdue_goals(request.user.goals.all(), today)
    goals = list(request.user.goals.prefetch_related("checklist_items", "progress_logs"))
    context = {
        "month_name": display.MONTH_NAMES[today.month - 1],
        # Example goals show whenever nothing is active, with or without history.
        "suggestions": [
            {**item, "deadline": (today + timedelta(days=item["days"] - 1)).isoformat()}
            for item in display.GOAL_SUGGESTIONS
        ],
        **_goal_form_context(GoalForm(initial=_goal_initial(request, today)), today),
    }
    if not goals:
        context.update(has_history=False)
        return render(request, "habits/goal/goal_list.html", context)

    cards = [_goal_card(goal, today) for goal in goals]
    active = [card for card in cards if card["status"] == services.GoalStatus.ACTIVE]
    for card, goal in zip(cards, goals):
        if card["status"] == services.GoalStatus.ACTIVE:
            card["progress_form"] = GoalProgressForm(goal=goal)
    completed = sorted(
        (card for card in cards if card["status"] == services.GoalStatus.COMPLETED),
        key=lambda card: card["completed_at"],
        reverse=True,
    )[:RECENT_COMPLETED_SHOWN]
    expired = [card for card in cards if card["status"] == services.GoalStatus.EXPIRED]
    context.update(
        has_history=True,
        active=active,
        near_count=sum(card["is_near"] for card in active),
        nearest=active[0] if active else None,
        completed=completed,
        expired=expired,
    )
    return render(request, "habits/goal/goal_list.html", context)


@login_required
def goal_detail(request, pk):
    today = services.local_today()
    services.expire_overdue_goals(Goal.objects.filter(pk=pk, user=request.user), today)
    goal = _owned_goal(request, pk)
    card = _goal_card(goal, today)
    pace = services.goal_pace(goal, card["progress"], today)
    checklist = [
        {
            "pk": item.pk,
            "label": item.label,
            "is_done": item.is_done,
            "date": display.day_month(timezone.localdate(item.done_at)) if item.done_at else "Belum",
        }
        for item in goal.checklist_items.all()
    ]
    logs = [
        {
            "amount": f"+{display.format_amount(log.amount)}",
            "note": log.note or card["unit_short"],
            "day": display.relative_date(timezone.localdate(log.logged_at), today),
            "time": timezone.localtime(log.logged_at).strftime("%H.%M"),
        }
        for log in goal.progress_logs.all()
    ]
    context = {
        "goal": card,
        "checklist": checklist,
        "logs": logs,
        "pace": {
            "needed": f"{display.format_rate(pace['needed'])} {card['unit_short']} / hari",
            "average": f"{display.format_rate(pace['average'])} {card['unit_short']} / hari",
            "on_track": pace["on_track"],
        },
        "progress_form": GoalProgressForm(goal=goal),
    }
    return render(request, "habits/goal/goal_detail.html", context)


@login_required
def goal_create(request):
    today = services.local_today()
    if request.method == "POST":
        form = GoalForm(request.POST, instance=Goal(user=request.user))
        if form.is_valid():
            goal = form.save()
            services.refresh_goal_after_edit(goal)
            return redirect("habits:goal_list")
    else:
        form = GoalForm(initial=_goal_initial(request, today))
    return render(request, "habits/goal/goal_form.html", {**_goal_form_context(form, today), "is_edit": False})


@login_required
def goal_edit(request, pk):
    goal = _owned_goal(request, pk)
    form = GoalForm(request.POST or None, instance=goal)
    if request.method == "POST" and form.is_valid():
        goal = form.save()
        services.refresh_goal_after_edit(goal)
        return redirect("habits:goal_detail", goal.pk)
    context = {**_goal_form_context(form, services.local_today()), "is_edit": True, "goal": goal}
    return render(request, "habits/goal/goal_form.html", context)


@login_required
def goal_log_progress(request, pk):
    goal = _owned_goal(request, pk)
    form = GoalProgressForm(request.POST or None, goal=goal)
    if request.method == "POST" and form.is_valid():
        try:
            event = services.log_goal_progress(
                goal, form.cleaned_data["amount"], form.cleaned_data["note"]
            )
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            if event:
                messages.success(request, GOAL_COMPLETED_MESSAGE)
        return _redirect_back(request, "habits:goal_detail", goal.pk)
    context = {"goal": _goal_card(goal, services.local_today()), "form": form}
    return render(request, "habits/goal/goal_progress.html", context)


@login_required
def goal_delete(request, pk):
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == "POST":
        goal.delete()
        return redirect("habits:goal_list")
    return render(request, "habits/goal/goal_confirm_delete.html", {"goal": goal})


@login_required
@require_POST
def goal_checklist_toggle(request, pk, item_pk):
    item = get_object_or_404(
        GoalChecklistItem, pk=item_pk, goal__pk=pk, goal__user=request.user
    )
    services.toggle_checklist_item(item)
    return _redirect_back(request, "habits:goal_detail", pk)
