from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import services
from .forms import EmissionTargetCreateForm, EmissionTargetForm
from .models import Achievement, EmissionTarget


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
    groups = services.badge_groups(rows)
    active = request.GET.get("kategori", "all")
    if active not in Achievement.Category.values:
        active = "all"
    context = {
        "tabs": [{"key": g["key"], "label": g["label"], "total": g["total"]} for g in groups],
        "groups": [g for g in groups if active in ("all", g["key"])],
        "active": active,
        "earned_count": sum(1 for r in rows if r["earned"]),
        "total_badges": len(rows),
        "share_on": services.shares_achievements(request.user),
    }
    template = "dashboard_parts/badge_browser.html" if request.headers.get("HX-Request") else "badges.html"
    return render(request, template, context)


@login_required
def targets(request):
    today = timezone.localdate()
    return render(request, "targets.html", {"targets": services.target_list(request.user, today)})


@login_required
def target_create(request):
    today = timezone.localdate()
    form = EmissionTargetCreateForm(request.POST or None, user=request.user, today=today)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("dashboard:targets")
    return render(request, "target_form.html", {"form": form, "mode": "create"})


@login_required
def target_edit(request, pk):
    target = get_object_or_404(EmissionTarget, pk=pk, user=request.user)
    form = EmissionTargetForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("dashboard:targets")
    context = {
        "form": form,
        "mode": "edit",
        "target": target,
        "month_label": services.month_label(target.month),
    }
    return render(request, "target_form.html", context)


@login_required
def target_delete(request, pk):
    target = get_object_or_404(EmissionTarget, pk=pk, user=request.user)
    if request.method == "POST":
        target.delete()
        return redirect("dashboard:targets")
    return render(request, "target_delete.html", {"target": target})


@login_required
@require_GET
def api_summary(request):
    return JsonResponse(services.api_summary(request.user, timezone.localdate()))