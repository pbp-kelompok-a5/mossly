from django.conf import settings
from django.db import models


class Thread(models.Model):
    class Category(models.TextChoices):
        TIPS = "tips", "Tips"
        GENERAL = "general", "General"
        ACHIEVEMENT = "achievement", "Achievement"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_threads",
    )
    title = models.CharField(max_length=255)
    body = models.TextField(max_length=5000)
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.GENERAL,
    )
    is_auto_post = models.BooleanField(default=False, editable=False)
    user_achievement = models.OneToOneField(
        "dashboard.UserAchievement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="community_thread",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(is_auto_post=True, category="achievement")
                    | (
                        models.Q(is_auto_post=False, user_achievement__isnull=True)
                        & ~models.Q(category="achievement")
                    )
                ),
                name="community_thread_auto_post_consistent",
            )
        ]

    def __str__(self):
        return self.title


class Reply(models.Model):
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name="replies",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_replies",
    )
    body = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"Reply {self.pk} on thread {self.thread_id}"


class ThreadLike(models.Model):
    thread = models.ForeignKey(
        Thread,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_likes",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "user"],
                name="unique_thread_like",
            )
        ]
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.user} likes thread {self.thread_id}"
