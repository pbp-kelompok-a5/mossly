from datetime import date, datetime, timedelta
from functools import wraps
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import display, services
from .forms import GoalForm, GoalProgressForm, HabitForm
from .models import Goal, GoalChecklistItem, GoalProgressLog, Habit, HabitCheckIn, SustainabilityEvent

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
        return redirect("habits:habit_detail", habit.pk)
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


def htmx_login_required(view):
    """Seperti @login_required, tapi request HTMX dibalas header HX-Redirect.

    Redirect biasa akan diikuti HTMX, lalu halaman login ikut terpasang di dalam
    baris habit (lihat catatan @login_required pada Tutorial 05).
    """
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated and request.headers.get("HX-Request"):
            response = HttpResponse(status=401)
            response["HX-Redirect"] = f"{reverse('accounts:login')}?next={reverse('habits:index')}"
            return response
        return login_required(view)(request, *args, **kwargs)
    return wrapped


def _row_partial(request, habit):
    """Satu baris habit untuk HTMX: hanya <li> ini yang diganti, tanpa reload."""
    today = services.local_today()
    dates = set(habit.checkins.values_list("checkin_date", flat=True))
    return render(request, "habits/components/habit_row.html", {"row": _habit_row(habit, dates, today)})


@htmx_login_required
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
            if request.headers.get("HX-Request"):
                # Muat ulang penuh supaya dialog milestone tampil.
                response = HttpResponse()
                response["HX-Refresh"] = "true"
                return response
    if request.headers.get("HX-Request"):
        return _row_partial(request, habit)
    return _redirect_back(request, "habits:index")


@htmx_login_required
@require_POST
def habit_undo_check_in(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    services.undo_check_in(habit)
    if request.headers.get("HX-Request"):
        return _row_partial(request, habit)
    return _redirect_back(request, "habits:index")


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
    goals = request.user.goals.prefetch_related("checklist_items", "progress_logs")
    # Filter kategori lewat query string, mis. /goal/?category=plastik
    category = request.GET.get("category", "")
    if category in Goal.Category.values:
        goals = goals.filter(category=category)
    else:
        category = ""
    goals = list(goals)
    context = {
        "category": category,
        "categories": Goal.Category.choices,
        "month_name": display.MONTH_NAMES[today.month - 1],
        # Example goals show whenever nothing is active, with or without history.
        "suggestions": [
            {**item, "deadline": (today + timedelta(days=item["days"] - 1)).isoformat()}
            for item in display.GOAL_SUGGESTIONS
        ],
        **_goal_form_context(GoalForm(initial=_goal_initial(request, today)), today),
    }
    if not goals and not category:
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


# --- History and habit detail ----------------------------------------------------

HISTORY_PERIODS = (("month", "Bulan ini"), ("3m", "3 bulan"), ("year", "Tahun"))
# The activity log covers recent days only; skipped habits are listed for the
# last week so older gaps do not fill the log.
ACTIVITY_DAYS = 30
ACTIVITY_LIMIT = 15
MISSED_DAYS_SHOWN = 7
MOST_CONSISTENT_SHOWN = 3


def _month_cells(first, last, today, level_for):
    """Calendar cells for one month, Monday first, with blanks before day 1.

    level_for(day) returns the heatmap level for a past or current day.
    """
    cells = [None] * first.weekday()
    day = first
    while day <= last:
        upcoming = day > today
        cells.append({
            "day": day.day,
            "label": display.long_date(day),
            "level": None if upcoming else level_for(day),
            "is_today": day == today,
            "is_upcoming": upcoming,
        })
        day += timedelta(days=1)
    return cells


def _year_weeks(year, today, level_for):
    """Week columns for a year grid: each column runs Monday to Sunday."""
    first = date(year, 1, 1)
    start = first - timedelta(days=first.weekday())
    last = date(year, 12, 31)
    weeks = []
    labelled_month = None
    while start <= last:
        week = [start + timedelta(days=offset) for offset in range(7)]
        in_year = [day for day in week if day.year == year]
        # Label a column with its first day's month, once per month, so a
        # week that only ends in a new month stays under the old one.
        label = ""
        if in_year and in_year[0].month != labelled_month:
            labelled_month = in_year[0].month
            label = display.MONTH_SHORT[labelled_month - 1]
        days = []
        for day in week:
            if day.year != year:
                days.append(None)
                continue
            upcoming = day > today
            days.append({
                "label": display.long_date(day),
                "level": None if upcoming else level_for(day),
                "is_today": day == today,
                "is_upcoming": upcoming,
            })
        weeks.append({"label": label, "days": days})
        start += timedelta(days=7)
    return weeks


def _month_summary(habits, checkins, year, month, today):
    first, last = services.month_bounds(year, month)
    done, expected = services.period_counts(habits, checkins, first, last, today)
    return {
        "name": display.MONTH_NAMES[month - 1],
        "first": first,
        "last": last,
        "done": done,
        "percent": services.consistency_percent(done, expected),
        "perfect": services.perfect_days(habits, checkins, first, last, today),
        "is_upcoming": first > today,
    }


def _activity_log(user, habits, checkins, today):
    """Recent check-ins, milestones, new habits, goal progress, and skipped habits."""
    since = today - timedelta(days=ACTIVITY_DAYS)
    since_moment = timezone.make_aware(datetime.combine(since, datetime.min.time()))
    by_pk = {habit.pk: habit for habit in habits}
    entries = []

    def add(day, moment, icon, tint, title, subtitle):
        entries.append({"day": day, "moment": moment, "icon": icon, "tint": tint,
                        "title": title, "subtitle": subtitle})

    for checkin in HabitCheckIn.objects.filter(habit__user=user, checkin_date__gte=since):
        habit = by_pk[checkin.habit_id]
        streak = services.current_streak(habit, checkins[habit.pk], checkin.checkin_date)
        add(checkin.checkin_date, checkin.checked_at, "check", "moss-200",
            f"Check-in: {habit.name}", f"{streak} hari berturut-turut")
    for event in user.sustainability_events.filter(occurred_at__gte=since_moment):
        day = timezone.localdate(event.occurred_at)
        if event.event_type == SustainabilityEvent.EventType.HABIT_MILESTONE:
            add(day, event.occurred_at, "trophy", "moss-100",
                f"Streak {event.milestone_days} hari: {event.title_snapshot}",
                "Milestone terkirim ke Personal Dashboard")
        else:
            add(day, event.occurred_at, "goal", "moss-200",
                f"Goal selesai: {event.title_snapshot}", "Terkirim ke Personal Dashboard")
    logs = GoalProgressLog.objects.filter(goal__user=user, logged_at__gte=since_moment).select_related("goal")
    for log in logs:
        amount = f"+{display.format_amount(log.amount)} {display.UNIT_SHORT[log.goal.unit]}"
        add(timezone.localdate(log.logged_at), log.logged_at, "target", "clay-100",
            f"Progres: {log.goal.title}", f"{amount} · {log.note}" if log.note else amount)
    for habit in habits:
        created = timezone.localdate(habit.created_at)
        if created >= since:
            subtitle = "Streak pertamamu dimulai hari ini" if created == today else "Mulai dicatat"
            add(created, habit.created_at, habit.icon, habit.tint, f"Habit baru: {habit.name}", subtitle)
    for offset in range(1, MISSED_DAYS_SHOWN + 1):
        day = today - timedelta(days=offset)
        missed = services.missed_habits(habits, checkins, day)
        if missed:
            add(day, None, "circle-alert", "clay-100", f"Melewatkan {len(missed)} habit",
                display.join_names(habit.name for habit in missed))

    # Newest day first; within a day, timed entries newest first, then skipped habits.
    entries.sort(
        key=lambda entry: (entry["day"], entry["moment"] is not None, entry["moment"] or since_moment),
        reverse=True,
    )
    groups = []
    for entry in entries[:ACTIVITY_LIMIT]:
        label = display.relative_date(entry["day"], today)
        if label not in ("Hari ini", "Kemarin"):
            label = display.day_month_long(entry["day"])
        if not groups or groups[-1]["label"] != label:
            groups.append({"label": label, "entries": []})
        entry["time"] = display.clock(entry["moment"]) if entry["moment"] else ""
        groups[-1]["entries"].append(entry)
    return groups


def _history_hero(period, months, overall, today):
    """Eyebrow and title for the selected period.

    With no habit scheduled in the period there is no consistency to show, so
    the hero switches to a gentle invitation (no_habits, with a subtitle)
    instead of 0%.
    """
    current = months[-1]
    eyebrow = {
        "month": f"{current['name']} {today.year}",
        "3m": "3 bulan terakhir",
        "year": f"Tahun {today.year}",
    }[period]
    if overall["percent"] is None:
        scope = "bulan ini" if period == "month" else "di periode ini"
        return {
            "eyebrow": eyebrow,
            "no_habits": True,
            "title": f"Belum ada habit yang dicatat {scope}",
            "subtitle": "Tambahkan habit untuk melihat konsistensimu di sini. "
                        "Progres dan goal yang selesai tetap tercatat di log aktivitas.",
        }

    if period == "month":
        previous = months[-2]
        change = services.consistency_change(current["percent"], previous["percent"])
        if change and change > 0:
            title = f"Konsistensimu {current['percent']}% bulan ini, naik {change}% dari {previous['name']}"
        else:
            title = f"Konsistensimu {current['percent']}% bulan ini"
    elif period == "3m":
        known = [month for month in months if month["percent"] is not None]
        if len(known) > 1 and current["percent"] is not None and current["percent"] > known[0]["percent"]:
            title = f"Konsistensimu naik dari {known[0]['percent']}% ke {current['percent']}%"
        elif current["percent"] is not None:
            title = f"Konsistensimu {current['percent']}% tiga bulan ini"
        else:
            title = "Belum ada habit yang dicatat bulan ini"
    else:
        title = f"{overall['done']} check-in sejak Januari {today.year}"
    return {"eyebrow": eyebrow, "title": title}


@login_required
def history(request):
    today = services.local_today()
    period = request.GET.get("period")
    if period not in dict(HISTORY_PERIODS):
        period = "month"
    user = request.user
    habits = list(user.habits.all())
    checkins = services.checkins_by_habit(habits)

    def level_for(day):
        return services.heat_level(*services.day_counts(habits, checkins, day))

    this_first, this_last = services.month_bounds(today.year, today.month)
    context = {
        "period": period,
        "periods": [
            {"key": key, "label": label, "url": f"{reverse('habits:history')}?period={key}"}
            for key, label in HISTORY_PERIODS
        ],
        "month_name": display.MONTH_NAMES[today.month - 1],
        "year": today.year,
        "day_names": display.DAY_SHORT,
        "day_initials": display.DAY_INITIALS,
    }
    has_activity = (
        any(checkins.values())
        or GoalProgressLog.objects.filter(goal__user=user).exists()
        or user.sustainability_events.exists()
    )
    if not has_activity:
        cells = _month_cells(this_first, this_last, today, lambda day: 0)
        for cell in cells:
            if cell:  # nothing recorded yet: every day reads as an open outline
                cell["is_upcoming"] = True
        context.update(is_empty=True, month_cells=cells)
        return render(request, "habits/history/history.html", context)

    deltas = {"month": (-1, 0), "3m": (-2, -1, 0)}.get(period)
    if deltas:
        months = [
            _month_summary(habits, checkins, *services.shift_month(today.year, today.month, delta), today)
            for delta in deltas
        ]
        start = months[0]["first"] if period == "3m" else this_first
        end = this_last
    else:
        months = [_month_summary(habits, checkins, today.year, month, today) for month in range(1, 13)]
        start, end = date(today.year, 1, 1), date(today.year, 12, 31)
    done, expected = services.period_counts(habits, checkins, start, end, today)
    overall = {
        "done": done,
        "percent": services.consistency_percent(done, expected),
        "perfect": services.perfect_days(habits, checkins, start, end, today),
    }
    for month in months:
        month["cells"] = _month_cells(month["first"], month["last"], today, level_for)

    current = months[-1] if period != "year" else months[today.month - 1]
    consistent = []
    for habit in habits:
        stats = services.habit_month_stats(habit, checkins[habit.pk], today.year, today.month, today)
        if stats["rate"] is not None:
            consistent.append({"name": habit.name, "percent": stats["rate"]})
    consistent.sort(key=lambda item: item["percent"], reverse=True)

    context.update(
        is_empty=False,
        hero=_history_hero(period, months, overall, today),
        overall=overall,
        months=months,
        month_cells=months[-1]["cells"] if period == "month" else None,
        year_weeks=_year_weeks(today.year, today, level_for) if period == "year" else None,
        summary={
            "checkins": current["done"],
            "perfect": current["perfect"],
            "goals_completed": user.sustainability_events.filter(
                event_type=SustainabilityEvent.EventType.GOAL_COMPLETED,
                occurred_at__gte=timezone.make_aware(datetime.combine(this_first, datetime.min.time())),
            ).count(),
            "longest": max((services.longest_streak(h, checkins[h.pk], today) for h in habits), default=0),
        },
        most_consistent=consistent[:MOST_CONSISTENT_SHOWN],
        activity=_activity_log(user, habits, checkins, today),
    )
    return render(request, "habits/history/history.html", context)


@login_required
def habit_detail(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    today = services.local_today()
    dates = set(habit.checkins.values_list("checkin_date", flat=True))
    streak = services.current_streak(habit, dates, today)
    target = services.next_milestone(streak)
    stats = services.habit_month_stats(habit, dates, today.year, today.month, today)
    first, last = services.month_bounds(today.year, today.month)

    cells = [None] * first.weekday()
    day = first
    while day <= last:
        if day > today:
            state = "upcoming"
        elif not services.is_scheduled(habit, day):
            state = "off"
        elif day in dates:
            state = "done"
        elif day == today:
            state = "today"
        else:
            state = "missed"
        cells.append({"day": day.day, "label": display.long_date(day), "state": state, "is_today": day == today})
        day += timedelta(days=1)

    sent = {
        event.milestone_days: event
        for event in habit.events.filter(event_type=SustainabilityEvent.EventType.HABIT_MILESTONE)
    }
    ladder = []
    for days in services.STREAK_MILESTONES:
        if days in sent:
            when = display.day_month(timezone.localdate(sent[days].occurred_at))
            ladder.append({"days": days, "state": "reached", "note": f"Terkirim ke Dashboard · {when}"})
        elif days == target:
            ladder.append({"days": days, "state": "next", "note": f"{days - streak} hari lagi"})
        else:
            ladder.append({"days": days, "state": "locked", "note": "Belum terbuka"})

    last_checkin = habit.checkins.first()
    if last_checkin is None:
        last_text = "Belum ada check-in."
    else:
        on = "hari ini" if last_checkin.checkin_date == today else display.day_month_long(last_checkin.checkin_date)
        last_text = f"Check-in terakhir {on} pukul {display.clock(last_checkin.checked_at)}."
    frequency = display.frequency_text(habit)
    schedule = frequency if habit.frequency_type == Habit.Frequency.DAILY else f"Setiap {frequency}"
    strongest = stats["strongest_weekday"]

    context = {
        "habit": habit,
        "time_label": habit.get_time_of_day_display(),
        "subtitle": f"{schedule}, dimulai {display.full_date(habit.start_date)}. {last_text}",
        "is_done_today": today in dates,
        "is_scheduled_today": services.is_scheduled(habit, today),
        "streak": streak,
        "target": target,
        "ring_percent": streak * 100 // target if target else 100,
        "month_name": display.MONTH_NAMES[today.month - 1],
        "day_names": display.DAY_SHORT,
        "cells": cells,
        "stats": {
            "checkins": f"{stats['done']} dari {stats['scheduled']} hari",
            "rate": f"{stats['rate']}%" if stats["rate"] is not None else "–",
            "longest": f"{stats['longest']} hari",
            "strongest": display.DAY_NAMES[strongest] if strongest is not None else "–",
        },
        "ladder": ladder,
        "frequency": frequency,
        "milestone": _pop_milestone(request),
    }
    return render(request, "habits/habit/habit_detail.html", context)


# --- JSON (data delivery, juga untuk Flutter di Proyek Akhir) ---------------------


@login_required
def habits_json(request):
    data = list(request.user.habits.values("id", "name", "time_of_day", "start_date"))
    return JsonResponse(data, safe=False)


@login_required
def goals_json(request):
    goals = request.user.goals.all()
    category = request.GET.get("category")
    if category in Goal.Category.values:
        goals = goals.filter(category=category)
    data = [
        {
            "id": goal.pk,
            "title": goal.title,
            "category": goal.category,
            "target_value": float(goal.target_value),
            "unit": goal.unit,
            "progress": float(services.goal_progress_total(goal)),
            "deadline": goal.deadline.isoformat(),
            "status": goal.status,
        }
        for goal in goals
    ]
    return JsonResponse(data, safe=False)
