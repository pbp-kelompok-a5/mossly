from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UserProfile(models.Model):
    class Avatar(models.TextChoices):
        SPROUT = "sprout", "Tunas"
        LEAF = "leaf", "Daun"
        TREE = "tree", "Pohon"

    class FocusArea(models.TextChoices):
        TRANSPORT = "transportasi", "Transportasi"
        WASTE = "sampah", "Sampah"
        PLASTIC = "plastik", "Plastik"
        ENERGY = "energi", "Energi"
        FOOD = "makanan", "Makanan"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    display_name = models.CharField(max_length=80)
    avatar = models.CharField(max_length=20, choices=Avatar.choices, default=Avatar.SPROUT)
    is_onboarded = models.BooleanField(default=False)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    primary_mode = models.ForeignKey(
        "carbon.TransportMode", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="user_profiles",
    )
    focus_areas = models.JSONField(default=list, blank=True)
    share_achievements = models.BooleanField(default=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=(models.Q(is_onboarded=False, onboarded_at__isnull=True)
                       | models.Q(is_onboarded=True, onboarded_at__isnull=False)),
            name="accounts_onboarding_timestamp_consistent",
        )]

    def clean(self):
        super().clean()
        if (not isinstance(self.focus_areas, list)
                or any(not isinstance(area, str) or area not in self.FocusArea.values
                       for area in self.focus_areas)
                or len(self.focus_areas) != len(set(self.focus_areas))):
            raise ValidationError({"focus_areas": "Pilih area fokus yang tersedia tanpa duplikasi."})

    def __str__(self):
        return self.display_name
