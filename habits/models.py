from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

WEEKDAY_NUMBERS = range(7)  # Monday is 0, matching date.weekday()


class Habit(models.Model):
    class TimeOfDay(models.TextChoices):
        PAGI = "pagi", "Pagi"
        SIANG = "siang", "Siang"
        MALAM = "malam", "Malam"
        KAPAN_SAJA = "kapan_saja", "Kapan saja"

    # times_per_week is stored on the model but not offered yet: a weekly
    # target has no agreed meaning for a streak counted in days.
    class Frequency(models.TextChoices):
        DAILY = "daily", "Setiap hari"
        WEEKDAYS = "weekdays", "Hari tertentu"

    # Keys are Lucide icon names so templates can map them to SVGs directly.
    class Icon(models.TextChoices):
        CUP_SODA = "cup-soda", "Tumbler"
        TRAIN_FRONT = "train-front", "Transportasi umum"
        RECYCLE = "recycle", "Daur ulang"
        SHOPPING_BAG = "shopping-bag", "Tas belanja"
        DROPLET = "droplet", "Air"
        LIGHTBULB = "lightbulb", "Listrik"
        LEAF = "leaf", "Daun"
        UTENSILS = "utensils", "Makanan"

    # Keys are color primitive names; CSS resolves them to tokens.
    class Tint(models.TextChoices):
        MOSS_100 = "moss-100", "Lumut muda"
        MOSS_200 = "moss-200", "Lumut"
        CLAY_100 = "clay-100", "Tanah liat"
        PINK_100 = "pink-100", "Merah muda"
        PINK_200 = "pink-200", "Merah muda tua"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="habits"
    )
    name = models.CharField(max_length=80)
    icon = models.CharField(max_length=20, choices=Icon.choices, default=Icon.LEAF)
    tint = models.CharField(max_length=20, choices=Tint.choices, default=Tint.MOSS_100)
    time_of_day = models.CharField(
        max_length=20, choices=TimeOfDay.choices, default=TimeOfDay.KAPAN_SAJA
    )
    frequency_type = models.CharField(
        max_length=20, choices=Frequency.choices, default=Frequency.DAILY
    )
    # Sorted day numbers for "weekdays" habits, e.g. [0, 2, 4]; null otherwise.
    weekdays = models.JSONField(null=True, blank=True)
    times_per_week = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(7)],
    )
    # Stored only; there is no delivery channel for reminders yet.
    reminder_time = models.TimeField(null=True, blank=True)
    start_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return self.name

    @property
    def weekday_numbers(self):
        return set(self.weekdays or ())

    def clean(self):
        super().clean()
        if self.frequency_type != self.Frequency.WEEKDAYS:
            self.weekdays = None
            return
        days = self.weekdays or []
        if not isinstance(days, list) or any(
            type(d) is not int or d not in WEEKDAY_NUMBERS for d in days
        ) or len(set(days)) != len(days):
            raise ValidationError({"weekdays": "Pilihan hari tidak valid."})
        if not days:
            raise ValidationError({"weekdays": "Pilih minimal satu hari."})
        self.weekdays = sorted(days)


class HabitCheckIn(models.Model):
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name="checkins")
    checkin_date = models.DateField()
    checked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-checkin_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["habit", "checkin_date"], name="unique_habit_checkin_per_day"
            )
        ]

    def __str__(self):
        return f"{self.habit} @ {self.checkin_date}"


class Goal(models.Model):
    class Category(models.TextChoices):
        TRANSPORTASI = "transportasi", "Transportasi"
        EMISI = "emisi", "Emisi"
        PLASTIK = "plastik", "Plastik"
        SAMPAH = "sampah", "Sampah"
        KOMUNITAS = "komunitas", "Komunitas"

    class Unit(models.TextChoices):
        KALI = "kali", "kali"
        HARI = "hari", "hari"
        KG_CO2E = "kg_co2e", "kg CO2e"

    # Other modules read this table directly, so "expired" is stored too. It is
    # refreshed by the services whenever this module's pages are used.
    class Status(models.TextChoices):
        ACTIVE = "active", "Aktif"
        COMPLETED = "completed", "Selesai"
        EXPIRED = "expired", "Lewat deadline"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="goals"
    )
    title = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices)
    target_value = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.KALI)
    start_date = models.DateField(default=timezone.localdate)
    deadline = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["deadline", "pk"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.start_date and self.deadline and self.deadline < self.start_date:
            raise ValidationError(
                {"deadline": "Deadline tidak boleh sebelum tanggal mulai."}
            )


class GoalChecklistItem(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="checklist_items")
    label = models.CharField(max_length=120)
    is_done = models.BooleanField(default=False)
    done_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]

    def __str__(self):
        return self.label


class GoalProgressLog(models.Model):
    goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="progress_logs")
    amount = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    note = models.CharField(max_length=200, blank=True)
    logged_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-logged_at", "-pk"]

    def __str__(self):
        return f"{self.goal} +{self.amount}"


class SustainabilityEvent(models.Model):
    """Append-only record read by the Personal Sustainability Dashboard.

    The source habit or goal is kept as SET_NULL so achievements survive
    deletion; title_snapshot preserves the name for display.
    """

    class EventType(models.TextChoices):
        GOAL_COMPLETED = "goal_completed", "Goal selesai"
        HABIT_MILESTONE = "habit_milestone", "Milestone habit"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sustainability_events",
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    habit = models.ForeignKey(
        Habit, null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    goal = models.ForeignKey(
        Goal, null=True, blank=True, on_delete=models.SET_NULL, related_name="events"
    )
    milestone_days = models.PositiveSmallIntegerField(null=True, blank=True)
    title_snapshot = models.CharField(max_length=120)
    payload = models.JSONField(default=dict, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-occurred_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["habit", "milestone_days"],
                condition=Q(event_type="habit_milestone"),
                name="unique_habit_milestone_event",
            ),
            models.UniqueConstraint(
                fields=["goal"],
                condition=Q(event_type="goal_completed"),
                name="unique_goal_completed_event",
            ),
            # The source FKs may both be null after deletion, so only the
            # fields that never change are constrained per type.
            models.CheckConstraint(
                condition=(
                    Q(
                        event_type="habit_milestone",
                        milestone_days__isnull=False,
                        goal__isnull=True,
                    )
                    | Q(
                        event_type="goal_completed",
                        milestone_days__isnull=True,
                        habit__isnull=True,
                    )
                ),
                name="event_fields_match_type",
            ),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()}: {self.title_snapshot}"
