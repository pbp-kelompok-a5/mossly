"""Dashboard rules: reads other modules, writes only its own achievement tables.

Every number is computed on read. Badge rules are keyed by Achievement.code
(see badges.py); a badge is awarded the first time its metric reaches the
threshold and is never taken back.
"""

import logging
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Sum
from django.utils import timezone

from carbon.models import Trip
from community.models import Reply, Thread, ThreadLike
from habits import display
from habits import services as habit_services
from habits.models import Goal, GoalProgressLog, SustainabilityEvent

from .badges import (
    ACTIVE_MODE_CODES,
    METRIC_BY_CODE,
    TONE_BY_CATEGORY,
    TRANSIT_MODE_CODES,
    UNIT_BY_CODE,
    ensure_achievements,
)
from .models import Achievement, EmissionTarget, UserAchievement

logger = logging.getLogger(__name__)

WEEKDAY_SHORT = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
NEW_BADGE_DAYS = 3
DASHBOARD_BADGES = 6
CHART_LEFT, CHART_RIGHT = 44, 726
CHART_BASE, CHART_RANGE = 200, 130


def _start_of(day):
    return timezone.make_aware(datetime.combine(day, time.min))


def _emission_between(user, first, last):
    total = Trip.objects.filter(
        user=user,
        traveled_at__gte=_start_of(first),
        traveled_at__lt=_start_of(last + timedelta(days=1)),
    ).aggregate(total=Sum("emission_kg"))["total"]
    return total or Decimal("0")


def month_total(user, year, month):
    first, last = habit_services.month_bounds(year, month)
    return _emission_between(user, first, last)


def _display_name(user):
    try:
        return user.profile.display_name or user.get_username()
    except ObjectDoesNotExist:
        return user.get_username()


def shares_achievements(user):
    try:
        return user.profile.share_achievements
    except ObjectDoesNotExist:
        return False


def collect_metrics(user, today=None):
    today = today or timezone.localdate()
    habits = list(user.habits.all())
    checkins = habit_services.checkins_by_habit(habits)

    streak_best = streak_now = perfect = 0
    for habit in habits:
        dates = checkins[habit.pk]
        streak_best = max(streak_best, habit_services.longest_streak(habit, dates, today))
        streak_now = max(streak_now, habit_services.current_streak(habit, dates, today))
    if habits:
        perfect = habit_services.perfect_days(
            habits, checkins, min(h.start_date for h in habits), today, today
        )

    goals = user.goals.all()
    early = sum(
        1
        for payload in SustainabilityEvent.objects.filter(
            user=user, event_type=SustainabilityEvent.EventType.GOAL_COMPLETED
        ).values_list("payload", flat=True)
        if (payload or {}).get("days_before_deadline", 0) >= 1
    )

    trips = Trip.objects.filter(user=user)
    active_km = trips.filter(mode__code__in=ACTIVE_MODE_CODES).aggregate(
        total=Sum("distance_km")
    )["total"]

    prev_year, prev_month = habit_services.shift_month(today.year, today.month, -1)
    older_year, older_month = habit_services.shift_month(today.year, today.month, -2)
    last_month = month_total(user, prev_year, prev_month)
    older_month_total = month_total(user, older_year, older_month)

    own_threads = Thread.objects.filter(author=user, is_auto_post=False)
    likes_received = ThreadLike.objects.filter(
        thread__author=user, thread__is_auto_post=False
    ).count()

    return {
        "habits": len(habits),
        "streak_best": streak_best,
        "streak_now": streak_now,
        "perfect_days": perfect,
        "goals_total": goals.count(),
        "goals_done": goals.filter(status=Goal.Status.COMPLETED).count(),
        "goals_active": goals.filter(status=Goal.Status.ACTIVE).count(),
        "goals_early": early,
        "trips": trips.count(),
        "light_trips": trips.filter(emission_kg=0).count(),
        "transit_trips": trips.filter(mode__code__in=TRANSIT_MODE_CODES).count(),
        "active_km": int(active_km or 0),
        "lighter_month": int(older_month_total > 0 and last_month < older_month_total),
        "threads": own_threads.count(),
        "tips": own_threads.filter(category=Thread.Category.TIPS).count(),
        "replies": Reply.objects.filter(author=user).count(),
        "likes_received": likes_received,
        "likes_given": ThreadLike.objects.filter(user=user).count(),
    }


def _source_event(user, achievement):
    events = SustainabilityEvent.objects.filter(user=user)
    if achievement.category == Achievement.Category.GOAL:
        return events.filter(event_type=SustainabilityEvent.EventType.GOAL_COMPLETED).first()
    if achievement.code.startswith("moss_"):
        return events.filter(
            event_type=SustainabilityEvent.EventType.HABIT_MILESTONE,
            milestone_days=achievement.threshold,
        ).first()
    return None


def community_event_id(user, achievement):
    return f"dashboard-{user.pk}-{achievement.code}"


def _share(user, awarded):
    if not shares_achievements(user):
        return
    from community.services import publish_achievement

    name = _display_name(user)
    for award in awarded:
        achievement = award.achievement
        try:
            publish_achievement(
                user=user,
                event_id=community_event_id(user, achievement),
                achievement_id=achievement.code,
                name=f"{name} meraih badge {achievement.name}",
                description=f"{achievement.description}.",
                earned_at=award.earned_at,
            )
        except Exception:
            logger.exception("Gagal mengirim badge %s ke Komunitas", achievement.code)


def check_and_award(user, today=None):
    ensure_achievements()
    metrics = collect_metrics(user, today)
    owned = set(user.achievements.values_list("achievement__code", flat=True))
    awarded = []
    for achievement in Achievement.objects.filter(is_active=True):
        if achievement.code in owned:
            continue
        if metrics.get(METRIC_BY_CODE.get(achievement.code), 0) < achievement.threshold:
            continue
        award, created = UserAchievement.objects.get_or_create(
            user=user,
            achievement=achievement,
            defaults={"source_event": _source_event(user, achievement)},
        )
        if created:
            awarded.append(award)
    if awarded:
        _share(user, awarded)
    return metrics, awarded


def badge_rows(user, metrics):
    earned = {
        a.achievement_id: a for a in user.achievements.select_related("achievement")
    }
    cutoff = timezone.now() - timedelta(days=NEW_BADGE_DAYS)
    rows = []
    for achievement in Achievement.objects.filter(is_active=True):
        award = earned.get(achievement.pk)
        value = metrics.get(METRIC_BY_CODE.get(achievement.code), 0)
        shown = min(value, achievement.threshold)
        rows.append(
            {
                "code": achievement.code,
                "name": achievement.name,
                "description": achievement.description,
                "icon": achievement.icon,
                "category": achievement.category,
                "category_label": achievement.get_category_display(),
                "tone": TONE_BY_CATEGORY.get(achievement.category, "moss"),
                "earned": award is not None,
                "is_new": award is not None and award.earned_at >= cutoff,
                "earned_at": award.earned_at if award else None,
                "percent": 100 if award else shown * 100 // achievement.threshold,
                "progress": f"{shown} / {achievement.threshold} {UNIT_BY_CODE[achievement.code]}",
                "threshold": achievement.threshold,
            }
        )
    return rows


def badge_groups(rows):
    groups = []
    for key, label in Achievement.Category.choices:
        items = [r for r in rows if r["category"] == key]
        groups.append(
            {
                "key": key,
                "label": label,
                "items": items,
                "earned": sum(1 for r in items if r["earned"]),
                "total": len(items),
            }
        )
    return groups


def preview_badges(rows):
    earned = sorted((r for r in rows if r["earned"]), key=lambda r: r["earned_at"], reverse=True)
    locked = sorted((r for r in rows if not r["earned"]), key=lambda r: -r["percent"])
    head = earned[: DASHBOARD_BADGES // 2]
    return head + locked[: DASHBOARD_BADGES - len(head)]


def emission_chart(user, today):
    first, last = habit_services.month_bounds(today.year, today.month)
    weeks = (today.day - 1) // 7 + 1
    totals = [Decimal("0")] * weeks
    trips = Trip.objects.filter(
        user=user,
        traveled_at__gte=_start_of(first),
        traveled_at__lt=_start_of(last + timedelta(days=1)),
    ).values_list("traveled_at", "emission_kg")
    for moment, kg in trips:
        index = min((timezone.localtime(moment).day - 1) // 7, weeks - 1)
        totals[index] += kg

    peak = max(totals)
    step = (CHART_RIGHT - CHART_LEFT) / (weeks - 1) if weeks > 1 else 0
    points = []
    for index, value in enumerate(totals):
        x = CHART_LEFT + step * index if weeks > 1 else (CHART_LEFT + CHART_RIGHT) / 2
        y = CHART_BASE - (float(value / peak) * CHART_RANGE if peak else 0)
        points.append(
            {
                "x": f"{x:.1f}",
                "y": f"{y:.1f}",
                "label_y": f"{y - 19:.1f}",
                "value": display.format_rate(value),
                "name": f"Mgg {index + 1}",
                "now": index == weeks - 1,
            }
        )
    line = " ".join(f"{p['x']},{p['y']}" for p in points) if weeks > 1 else ""
    area = (
        f"{line} {points[-1]['x']},{CHART_BASE} {points[0]['x']},{CHART_BASE}"
        if weeks > 1
        else ""
    )

    summary = "Catat perjalananmu untuk melihat grafik emisi bulan ini."
    if totals[0] > 0 and weeks > 1:
        change = round((totals[-1] - totals[0]) / totals[0] * 100)
        direction = "turun" if change < 0 else "naik"
        summary = (
            f"Emisimu {direction} {abs(change)}% sejak minggu pertama. "
            f"Minggu ke-{weeks} masih berjalan."
        )
    elif peak > 0:
        summary = "Minggu pertama bulan ini sudah tercatat. Grafik tumbuh seiring perjalananmu."
    return {"points": points, "line": line, "area": area, "summary": summary, "has_data": peak > 0}


MODE_GROUPS = (
    ("Motor / mobil", ("mobil", "motor"), "var(--color-clay-300)"),
    ("Transportasi umum", ("bus", "kereta"), "var(--color-moss-300)"),
    ("Jalan kaki / sepeda", ("jalan", "sepeda"), "var(--color-moss-700)"),
)


def mode_breakdown(user, today):
    first, last = habit_services.month_bounds(today.year, today.month)
    rows = (
        Trip.objects.filter(
            user=user,
            traveled_at__gte=_start_of(first),
            traveled_at__lt=_start_of(last + timedelta(days=1)),
        )
        .values("mode__code")
        .annotate(kg=Sum("emission_kg"))
    )
    by_code = {r["mode__code"]: r["kg"] or Decimal("0") for r in rows}
    sums = [sum((by_code.get(c, Decimal("0")) for c in codes), Decimal("0")) for _, codes, _ in MODE_GROUPS]
    total = sum(sums, Decimal("0"))
    percents = [round(float(s / total * 100)) if total else 0 for s in sums]
    if total:
        percents[-1] = max(0, 100 - sum(percents[:-1]))
    legend = [
        {"name": name, "percent": pct, "color": color}
        for (name, _, color), pct in zip(MODE_GROUPS, percents)
    ]
    return {
        "total": display.format_rate(total),
        "a": percents[0],
        "b": percents[0] + percents[1],
        "legend": legend,
        "has_data": total > 0,
    }


def habit_overview(user, today):
    habits = list(user.habits.all())
    if not habits:
        return {"has_habits": False, "week": [], "rows": [], "note": ""}
    checkins = habit_services.checkins_by_habit(habits)
    monday = today - timedelta(days=today.weekday())
    week = []
    for offset in range(7):
        day = monday + timedelta(days=offset)
        scheduled, done = habit_services.day_counts(habits, checkins, day)
        status = habit_services.day_status(scheduled, done, day, today)
        week.append(
            {
                "name": WEEKDAY_SHORT[offset],
                "number": day.day,
                "done": status == habit_services.DayStatus.DONE,
                "today": day == today,
            }
        )
    rows = sorted(
        (
            {"name": h.name, "streak": habit_services.current_streak(h, checkins[h.pk], today)}
            for h in habits
        ),
        key=lambda r: -r["streak"],
    )
    note = "Check-in hari ini untuk menjaga streakmu."
    best = rows[0]["streak"]
    upcoming = habit_services.next_milestone(best)
    if best and upcoming:
        note = f"{upcoming - best} hari lagi menuju milestone streak {upcoming} hari."
    elif best:
        note = "Semua milestone streak sudah kamu raih. Pertahankan!"
    return {"has_habits": True, "week": week, "rows": rows[:3], "note": note}


GOAL_TONES = ("moss", "clay", "pink")


def goal_overview(user, today):
    habit_services.expire_overdue_goals(user.goals.all(), today)
    cards = []
    for index, goal in enumerate(user.goals.filter(status=Goal.Status.ACTIVE)[:3]):
        progress = habit_services.goal_progress_total(goal)
        days = habit_services.days_until(goal.deadline, today)
        cards.append(
            {
                "title": goal.title,
                "percent": habit_services.goal_progress_percent(progress, goal.target_value),
                "tone": GOAL_TONES[index % len(GOAL_TONES)],
                "meta": (
                    f"{display.format_amount(progress)} / {display.format_amount(goal.target_value)} "
                    f"{goal.get_unit_display()} · "
                    + (f"{days} hari lagi" if days > 0 else "deadline hari ini")
                ),
            }
        )
    return cards


POST_TONES = {
    Thread.Category.ACHIEVEMENT.value: "clay",
    Thread.Category.TIPS.value: "moss",
    Thread.Category.GENERAL.value: "moss",
}


def community_posts(user):
    threads = (
        Thread.objects.filter(author=user)
        .annotate(
            like_count=Count("likes", distinct=True),
            reply_count=Count("replies", distinct=True),
        )
        .order_by("-created_at", "pk")[:2]
    )
    return [
        {
            "pk": t.pk,
            "title": t.title,
            "tag": t.get_category_display(),
            "tone": POST_TONES.get(t.category, "moss"),
            "meta": (
                f"{'Diposting otomatis' if t.is_auto_post else 'Threadmu'}"
                f" · {t.like_count} like · {t.reply_count} reply"
            ),
        }
        for t in threads
    ]


def _when(moment, today):
    local = timezone.localtime(moment)
    gap = (today - local.date()).days
    if gap <= 0:
        return f"Hari ini, {local:%H.%M}"
    if gap == 1:
        return f"Kemarin, {local:%H.%M}"
    if gap < 7:
        return f"{gap} hari lalu"
    return display.day_month(local.date())


ACCENT, BRAND, MOSS, PINK = (
    "var(--color-bg-accent)",
    "var(--color-bg-brand)",
    "var(--color-moss-300)",
    "var(--color-pink-500, #d97f9c)",
)


def timeline(user, today, limit=5):
    items = []
    for e in SustainabilityEvent.objects.filter(user=user)[:limit]:
        if e.event_type == SustainabilityEvent.EventType.GOAL_COMPLETED:
            items.append((e.occurred_at, f"Goal {e.title_snapshot} selesai", ACCENT))
        else:
            items.append(
                (e.occurred_at, f"Habit {e.title_snapshot} mencapai milestone {e.milestone_days} hari", MOSS)
            )
    for t in Trip.objects.filter(user=user).select_related("mode")[:limit]:
        items.append(
            (
                t.traveled_at,
                f"Perjalanan {t.origin_label} → {t.destination_label} dicatat: "
                f"{display.format_rate(t.emission_kg)} kg CO₂e",
                BRAND,
            )
        )
    for log in GoalProgressLog.objects.filter(goal__user=user).select_related("goal")[:limit]:
        items.append(
            (log.logged_at, f"Progres goal {log.goal.title} bertambah {display.format_amount(log.amount)}", ACCENT)
        )
    for t in Thread.objects.filter(author=user, is_auto_post=False)[:limit]:
        items.append((t.created_at, f"Kamu membuat thread {t.title}", PINK))
    for r in Reply.objects.filter(author=user).select_related("thread")[:limit]:
        items.append((r.created_at, f"Kamu membalas thread {r.thread.title}", PINK))
    for a in UserAchievement.objects.filter(user=user).select_related("achievement")[:limit]:
        items.append((a.earned_at, f"Kamu meraih badge {a.achievement.name}", ACCENT))
    items.sort(key=lambda item: item[0], reverse=True)
    return [
        {"text": text, "when": _when(moment, today), "color": color}
        for moment, text, color in items[:limit]
    ]


def month_label(day):
    return f"{display.MONTH_NAMES[day.month - 1]} {day.year}"


def _target_row(user, target, today):
    used = month_total(user, target.month.year, target.month.month)
    percent = int(used * 100 / target.target_kg)
    diff = abs(target.target_kg - used)
    if used > target.target_kg:
        state, note = "over", f"melebihi {display.format_rate(diff)} kg dari target"
    elif percent >= 80:
        state, note = "warn", f"tersisa {display.format_rate(diff)} kg lagi"
    else:
        state, note = "ok", f"tersisa {display.format_rate(diff)} kg, masih aman"
    return {
        "pk": target.pk,
        "month_label": month_label(target.month),
        "target": display.format_rate(target.target_kg),
        "used": display.format_rate(used),
        "percent": percent,
        "bar": min(percent, 100),
        "state": state,
        "note": note,
        "is_current": (target.month.year, target.month.month) == (today.year, today.month),
    }


def target_overview(user, today):
    target = EmissionTarget.objects.filter(
        user=user, month=today.replace(day=1)
    ).first()
    return {"row": _target_row(user, target, today) if target else None}


def target_list(user, today, limit=24):
    targets = EmissionTarget.objects.filter(user=user)[:limit]
    return [_target_row(user, t, today) for t in targets]


def api_summary(user, today):
    metrics = collect_metrics(user, today)
    rows = badge_rows(user, metrics)
    target = EmissionTarget.objects.filter(user=user, month=today.replace(day=1)).first()
    return {
        "month": f"{today.year}-{today.month:02d}",
        "emission_kg": float(month_total(user, today.year, today.month)),
        "target_kg": float(target.target_kg) if target else None,
        "streak": {"now": metrics["streak_now"], "best": metrics["streak_best"]},
        "goals": {"done": metrics["goals_done"], "total": metrics["goals_total"]},
        "community_actions": metrics["threads"] + metrics["replies"] + metrics["likes_given"],
        "badges": {"earned": sum(1 for r in rows if r["earned"]), "total": len(rows)},
    }


def build_dashboard(user, today, metrics, rows):
    this = month_total(user, today.year, today.month)
    prev_year, prev_month = habit_services.shift_month(today.year, today.month, -1)
    last = month_total(user, prev_year, prev_month)
    if last > 0:
        change = round((this - last) / last * 100)
        emission_sub = (
            f"{'turun' if change < 0 else 'naik'} {abs(change)}% dari bulan lalu"
            if change
            else "sama dengan bulan lalu"
        )
    else:
        emission_sub = "belum ada data bulan lalu"

    community_actions = metrics["threads"] + metrics["replies"] + metrics["likes_given"]
    earned = sum(1 for r in rows if r["earned"])
    name = _display_name(user)
    is_empty = not (
        metrics["trips"] or metrics["habits"] or metrics["goals_total"] or community_actions
    )
    starters = {"first_trip", "moss_spore", "first_goal", "first_thread"}

    return {
        "display_name": name,
        "initial": name[:1].upper(),
        "month_name": display.MONTH_NAMES[today.month - 1],
        "is_empty": is_empty,
        "earned_count": earned,
        "total_badges": len(rows),
        "stats": {
            "emission": display.format_rate(this),
            "emission_sub": emission_sub,
            "streak": metrics["streak_now"],
            "streak_best": metrics["streak_best"],
            "goals_done": metrics["goals_done"],
            "goals_total": metrics["goals_total"],
            "goals_active": metrics["goals_active"],
            "community": community_actions,
            "threads": metrics["threads"],
            "replies": metrics["replies"],
            "likes": metrics["likes_given"],
        },
        "target": target_overview(user, today),
        "chart": emission_chart(user, today),
        "modes": mode_breakdown(user, today),
        "habit": habit_overview(user, today),
        "goals": goal_overview(user, today),
        "badges": preview_badges(rows),
        "starter_badges": [r for r in rows if r["code"] in starters],
        "posts": community_posts(user),
        "timeline": timeline(user, today),
        "share_on": shares_achievements(user),
    }


def pop_unseen(user):
    unseen = list(user.achievements.filter(seen=False).select_related("achievement").order_by("earned_at"))
    if not unseen:
        return None
    UserAchievement.objects.filter(pk__in=[a.pk for a in unseen]).update(seen=True)
    first = unseen[0]
    thread = Thread.objects.filter(user_achievement=first).first()
    return {
        "achievement": first.achievement,
        "tone": TONE_BY_CATEGORY.get(first.achievement.category, "moss"),
        "others": len(unseen) - 1,
        "thread_pk": thread.pk if thread else None,
        "shared": thread is not None,
    }