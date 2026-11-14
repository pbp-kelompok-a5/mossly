"""View DRF modul Sustainable Habit & Goal Tracker.

Autentikasi dan permission default (token + session, wajib login) diatur di
settings.py.
"""
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from . import services
from .serializers import HabitSerializer,  GoalSerializer
from .models import Goal # validasi kategori

# Daftar habit + ringkasan habit hari ini
@api_view(["GET"])
def habit_list(request):
    """GET /api/v1/habits/ — daftar habit milik pengguna + ringkasan hari ini."""
    today = services.local_today()
    habits = list(request.user.habits.all())
    checkins = services.checkins_by_habit(habits)
    scheduled, done = services.day_counts(habits, checkins, today)
    serializer = HabitSerializer(
        habits, many=True, context={"today": today, "checkins": checkins}
    )
    return Response({
        "date": today.isoformat(),
        "scheduled_today": scheduled,
        "done_today": done,
        "habits": serializer.data,
    })


# Daftar goal + progres dan status terbaru
@api_view(["GET"])
def goal_list(request):
    """GET /api/v1/goals/?category= — daftar goal milik pengguna."""
    today = services.local_today()
    category = request.query_params.get("category", "")
    if category and category not in Goal.Category.values:
        # Pesan sama dengan GoalForm, DRF menjawab sebagai 400.
        raise ValidationError({"category": ["Pilihan kategori tidak valid."]})

    # Tidak ada background job, goal lewat deadline ditandai di sini (seperti web).
    services.expire_overdue_goals(request.user.goals.all(), today)
    goals = request.user.goals.prefetch_related("checklist_items", "progress_logs")
    if category:
        goals = goals.filter(category=category)
    serializer = GoalSerializer(goals, many=True, context={"today": today})
    return Response(serializer.data)
