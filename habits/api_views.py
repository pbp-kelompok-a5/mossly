"""View DRF modul Sustainable Habit & Goal Tracker.

Autentikasi dan permission default (token + session, wajib login) diatur di
settings.py.
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import services
from .serializers import HabitSerializer

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
