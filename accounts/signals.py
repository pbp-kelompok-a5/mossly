from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL, dispatch_uid="accounts.create_profile")
def create_profile(sender, instance, created, raw, using, **kwargs):
    if created and not raw:
        UserProfile.objects.using(using).get_or_create(
            user_id=instance.pk,
            defaults={"display_name": instance.get_full_name()[:80] or instance.get_username()[:80]},
        )
