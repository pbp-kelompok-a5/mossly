from django.conf import settings
from django.db import models
from django.utils import timezone


class Achievement(models.Model):
    class Category(models.TextChoices):
        HABIT = "habit", "Habit"
        GOAL = "goal", "Goal"
        CARBON = "carbon", "Carbon"
        COMMUNITY = "community", "Komunitas"

    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200)
    icon = models.CharField(max_length=20)
    category = models.CharField(max_length=20, choices=Category.choices)
    threshold = models.PositiveIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.name


class UserAchievement(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="achievements"
    )
    achievement = models.ForeignKey(
        Achievement, on_delete=models.CASCADE, related_name="awards"
    )
    source_event = models.ForeignKey(
        "habits.SustainabilityEvent",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="achievements",
    )
    earned_at = models.DateTimeField(default=timezone.now)
    seen = models.BooleanField(default=False)

    class Meta:
        ordering = ["-earned_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "achievement"], name="unique_user_achievement"
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.achievement}"