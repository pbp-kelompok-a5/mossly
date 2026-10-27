from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .forms import GoalProgressForm
from .models import Goal, Habit


@login_required
def index(request):
    return render(request, "habits/index.html")


@login_required
@require_POST
def habit_check_in(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    try:
        services.check_in(habit)
    except ValidationError as error:
        messages.error(request, error.messages[0])
    return redirect("habits:index")


@login_required
@require_POST
def habit_undo_check_in(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    services.undo_check_in(habit)
    return redirect("habits:index")


@login_required
@require_POST
def habit_delete(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    habit.delete()
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
