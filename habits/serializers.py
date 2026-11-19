"""Serializer DRF modul Sustainable Habit & Goal Tracker."""
from decimal import Decimal

from rest_framework import serializers

from . import services
from .models import Habit, Goal, GoalChecklistItem


class HabitSerializer(serializers.ModelSerializer):
    """Satu habit beserta status hari ini dan streak-nya.

    Field yang dihitung (status dan streak) tidak disimpan di database, jadi
    dihitung lewat services.py. View wajib mengirim context:
    - "today": tanggal lokal hari ini
    - "checkins": {habit_id: set(tanggal check-in)} dari services.checkins_by_habit
    semua check-in dimuat sekali, bukan satu query per habit.
    """

    is_scheduled_today = serializers.SerializerMethodField()
    is_done_today = serializers.SerializerMethodField()
    current_streak = serializers.SerializerMethodField()
    longest_streak = serializers.SerializerMethodField()
    next_milestone = serializers.SerializerMethodField()

    class Meta:
        model = Habit
        fields = [
            "id", "name", "icon", "tint", "time_of_day",
            "frequency_type", "weekdays", "start_date",
            "is_scheduled_today", "is_done_today",
            "current_streak", "longest_streak", "next_milestone",
        ]

    def _dates(self, habit):
        return self.context["checkins"].get(habit.pk, set())

    def get_is_scheduled_today(self, habit):
        return services.is_scheduled(habit, self.context["today"])

    def get_is_done_today(self, habit):
        return self.context["today"] in self._dates(habit)

    def get_current_streak(self, habit):
        return services.current_streak(habit, self._dates(habit), self.context["today"])

    def get_longest_streak(self, habit):
        return services.longest_streak(habit, self._dates(habit), self.context["today"])

    def get_next_milestone(self, habit):
        return services.next_milestone(self.get_current_streak(habit))


class GoalChecklistItemSerializer(serializers.ModelSerializer):
    """Satu item checklist di dalam suatu goal."""

    class Meta:
        model = GoalChecklistItem
        fields = ["id", "label", "is_done"]


class GoalSerializer(serializers.ModelSerializer):
    """Satu goal beserta progres, status, dan checklist-nya.

    Progres dijumlahkan dari progress_logs yang sudah di-prefetch oleh view,
    sama seperti halaman web, supaya tidak ada query per goal. Status, persen,
    dan sisa hari dihitung lewat services.py. View wajib mengirim context
    "today" (tanggal lokal hari ini).
    """

    # Desimal dikirim sebagai angka JSON (20.0)
    target_value = serializers.DecimalField(
        max_digits=8, decimal_places=2, coerce_to_string=False
    )
    status = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    percent = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    is_near_deadline = serializers.SerializerMethodField()
    checklist = GoalChecklistItemSerializer(
        source="checklist_items", many=True, read_only=True
    )

    class Meta:
        model = Goal
        fields = [
            "id", "title", "category", "target_value", "unit",
            "start_date", "deadline", "status", "progress", "percent",
            "days_left", "is_near_deadline", "completed_at", "checklist",
        ]

    def _progress(self, goal):
        return sum((log.amount for log in goal.progress_logs.all()), Decimal("0"))

    def get_status(self, goal):
        return services.goal_status(goal, self._progress(goal), self.context["today"])

    def get_progress(self, goal):
        return float(self._progress(goal))

    def get_percent(self, goal):
        return services.goal_progress_percent(self._progress(goal), goal.target_value)

    def get_days_left(self, goal):
        return services.days_until(goal.deadline, self.context["today"])

    def get_is_near_deadline(self, goal):
        return services.is_near_deadline(goal, self._progress(goal), self.context["today"])
