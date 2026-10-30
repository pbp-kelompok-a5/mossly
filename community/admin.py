from django.contrib import admin

from .models import Reply, Thread, ThreadLike


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "category",
        "is_auto_post",
        "created_at",
    )
    list_filter = ("category", "is_auto_post")
    search_fields = ("title", "body", "author__username")
    readonly_fields = ("is_auto_post", "user_achievement")


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "author", "created_at")
    search_fields = ("body", "author__username")


@admin.register(ThreadLike)
class ThreadLikeAdmin(admin.ModelAdmin):
    list_display = ("thread", "user", "created_at")
    list_select_related = ("thread", "user")
    search_fields = ("thread__title", "user__username")
