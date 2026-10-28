from django.db import models
from django.conf import settings

class Thread(models.Model):
    class Category(models.TextChoices):
        TIPS = "tips", "TIPS"
        ACHIEVEMENT = "achievement", "Achievement"
        GENERAL = "general", "General"
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete = models.CASCADE, related_name = "community_threads",)
    title = models.CharField(max_length = 255)
    content = models.TextField()
    category = models.CharField(max_length = 20,choices = Category.choices, default = Category.GENERAL)
    liked_by = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="liked_community_threads", blank=True,)
    achievement_event_id = models.CharField(max_length = 100, unique = True, null = True, blank = True, editable = False)
    created_at = models.DateTimeField(auto_now_add = True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at", "pk"]

    @property
    def is_automatic(self):
        return self.achievement_event_id is not None

    def __str__(self):
        return self.title
    
class Reply (models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name = "replies",)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete = models.CASCADE, related_name = "community_replies",)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add = True)
    class Meta: ordering = ["-created_at", "pk"]
    def __str__(self):
        return f"Reply {self.pk} on thread {self.thread_id}"
    
class AchievementEvent(models.Model):
    event_id = models.CharField(max_length=100, unique=True)
    achievement_id = models.CharField(max_length=100)
    earned_at = models.DateTimeField()
    processed_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    thread = models.OneToOneField(
        Thread,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.event_id
# Create your models here.


