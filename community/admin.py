from django.contrib import admin
from .models import Reply, Thread

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "category",
        "created_at"
    )
    list_filler = ("category",)
    search_fields = ("title", "content")
    readonly_fields = ("achievement_event_id",)
    
@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ("id", "thread", "author", "created_at")
    search_fields = ("content",)
# Register your models here.
