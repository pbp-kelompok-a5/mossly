"""Serializer DRF modul Sustainable Habit & Goal Tracker."""
from rest_framework import serializers

from . import services
from .models import Habit


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
