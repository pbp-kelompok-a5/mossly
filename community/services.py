"""Service boundary used by Dashboard to publish achievement threads."""

from django.core.exceptions import ValidationError
from django.db import transaction

from dashboard.models import UserAchievement

from .models import Thread


def publish_achievement(*, user_achievement):
    """Create one automatic thread for an awarded achievement.

    Dashboard owns ``UserAchievement`` and passes the saved row here. Community
    only writes its own ``Thread`` table, matching the cross-module ERD rule.
    """
    if not isinstance(user_achievement, UserAchievement) or not user_achievement.pk:
        raise ValidationError("Pencapaian pengguna tidak valid.")

    with transaction.atomic():
        award = UserAchievement.objects.select_for_update().select_related(
            "user", "achievement", "user__profile"
        ).get(pk=user_achievement.pk)

        if not award.user.profile.share_achievements:
            return None

        existing = Thread.objects.filter(user_achievement=award).first()
        if existing:
            return existing

        return Thread.objects.create(
            author=award.user,
            title=award.achievement.name,
            body=award.achievement.description,
            category=Thread.Category.ACHIEVEMENT,
            is_auto_post=True,
            user_achievement=award,
        )
