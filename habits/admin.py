from django.contrib import admin

from .models import (
    Goal,
    GoalChecklistItem,
    GoalProgressLog,
    Habit,
    HabitCheckIn,
    SustainabilityEvent,
)


@admin.register(Habit)
class HabitAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "time_of_day", "frequency_type", "start_date"]
    list_filter = ["time_of_day", "frequency_type"]


@admin.register(HabitCheckIn)
class HabitCheckInAdmin(admin.ModelAdmin):
    list_display = ["habit", "checkin_date", "checked_at"]


class GoalChecklistItemInline(admin.TabularInline):
    model = GoalChecklistItem
    extra = 0


@admin.register(Goal)
class GoalAdmin(admin.ModelAdmin):
    list_display = ["title", "user", "category", "target_value", "unit", "deadline", "status"]
    list_filter = ["category", "status"]
    inlines = [GoalChecklistItemInline]


@admin.register(GoalProgressLog)
class GoalProgressLogAdmin(admin.ModelAdmin):
    list_display = ["goal", "amount", "logged_at"]


# Events are append-only; the admin shows them but never edits them.
@admin.register(SustainabilityEvent)
class SustainabilityEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "title_snapshot", "user", "milestone_days", "occurred_at"]
    list_filter = ["event_type"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
