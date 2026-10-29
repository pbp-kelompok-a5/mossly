from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from . import services


@login_required
def index(request):
    today = timezone.localdate()
    metrics, _ = services.check_and_award(request.user, today)
    rows = services.badge_rows(request.user, metrics)
    context = services.build_dashboard(request.user, today, metrics, rows)
    context["new_badge"] = services.pop_unseen(request.user)
    return render(request, "dashboard.html", context)


@login_required
def badges(request):
    today = timezone.localdate()
    metrics, _ = services.check_and_award(request.user, today)
    rows = services.badge_rows(request.user, metrics)
    context = {
        "groups": services.badge_groups(rows),
        "earned_count": sum(1 for r in rows if r["earned"]),
        "total_badges": len(rows),
        "share_on": services.shares_achievements(request.user),
    }
    return render(request, "badges.html", context)