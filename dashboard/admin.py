from django.contrib import admin

from .models import Achievement, UserAchievement


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "threshold", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name", "description")


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "achievement", "earned_at")
    list_select_related = ("user", "achievement")
    search_fields = ("user__username", "achievement__code", "achievement__name")
