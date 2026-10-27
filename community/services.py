"""Internal Dashboard integration; never accept achievement events directly from a public form."""
import logging
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import AchievementEvent, Thread

logger = logging.getLogger(__name__)


def publish_achievement(*, user, event_id, achievement_id, name, description, earned_at):
    """Return the existing/new thread, or None if its owner already deleted it.

    Dashboard supplies a globally unique event ID and the achievement timestamp.
    Errors are logged and re-raised so the caller can retry safely.
    """
    try:
        for value, limit in ((event_id, 100), (achievement_id, 100), (name, 255), (description, None)):
            if not isinstance(value, str) or not value.strip() or (limit and len(value) > limit):
                raise ValidationError("Data pencapaian tidak valid.")
        if not user.pk or earned_at is None:
            raise ValidationError("Pengguna dan waktu pencapaian wajib tersedia.")
        with transaction.atomic():
            event, created = AchievementEvent.objects.get_or_create(event_id=event_id, defaults={
                "author": user, "achievement_id": achievement_id, "earned_at": earned_at,
            })
            if not created:
                if event.author_id != user.pk or event.achievement_id != achievement_id:
                    raise ValidationError("Event pencapaian sudah digunakan.")
                return event.thread
            thread = Thread.objects.create(author=user, title=name.strip(), content=description.strip(),
                category=Thread.Category.ACHIEVEMENT, achievement_event_id=event_id)
            event.thread = thread
            event.save(update_fields=["thread"])
            return thread
    except Exception:
        logger.exception("Gagal memproses event pencapaian Community")
        raise
