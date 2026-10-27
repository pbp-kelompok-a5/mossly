from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "is_onboarded", "primary_mode")
    search_fields = ("user__username", "display_name")
    readonly_fields = ("is_onboarded", "onboarded_at")
