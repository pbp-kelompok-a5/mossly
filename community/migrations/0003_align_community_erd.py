import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def migrate_legacy_community_data(apps, schema_editor):
    Thread = apps.get_model("community", "Thread")
    ThreadLike = apps.get_model("community", "ThreadLike")
    AchievementEvent = apps.get_model("community", "AchievementEvent")
    Achievement = apps.get_model("dashboard", "Achievement")
    UserAchievement = apps.get_model("dashboard", "UserAchievement")

    old_like_model = Thread.liked_by.through
    now = timezone.now()
    ThreadLike.objects.bulk_create(
        [
            ThreadLike(thread_id=thread_id, user_id=user_id, created_at=now)
            for thread_id, user_id in old_like_model.objects.values_list(
                "thread_id", "user_id"
            ).iterator()
        ],
        ignore_conflicts=True,
    )

    linked_awards = set()
    for event in AchievementEvent.objects.order_by("pk").iterator():
        thread = Thread.objects.filter(pk=event.thread_id).first()
        achievement, _ = Achievement.objects.get_or_create(
            code=event.achievement_id,
            defaults={
                "name": thread.title if thread else event.achievement_id,
                "description": thread.body if thread else event.achievement_id,
                "icon": "award",
                "category": "community",
                "is_active": True,
            },
        )
        award, _ = UserAchievement.objects.get_or_create(
            user_id=event.author_id,
            achievement_id=achievement.pk,
            defaults={"earned_at": event.earned_at},
        )

        if thread:
            thread.is_auto_post = True
            thread.category = "achievement"
            if award.pk not in linked_awards:
                thread.user_achievement_id = award.pk
                linked_awards.add(award.pk)
            thread.save(
                update_fields=["is_auto_post", "category", "user_achievement"]
            )

    Thread.objects.filter(
        achievement_event_id__isnull=False,
        is_auto_post=False,
    ).update(is_auto_post=True, category="achievement")
    # The legacy public form exposed the achievement choice to users. ERD v0.2
    # reserves it for automatic posts, so old manual rows become general posts.
    Thread.objects.filter(
        category="achievement",
        is_auto_post=False,
    ).update(category="general")


def restore_legacy_community_data(apps, schema_editor):
    Thread = apps.get_model("community", "Thread")
    ThreadLike = apps.get_model("community", "ThreadLike")
    AchievementEvent = apps.get_model("community", "AchievementEvent")
    UserAchievement = apps.get_model("dashboard", "UserAchievement")

    old_like_model = Thread.liked_by.through
    old_like_model.objects.bulk_create(
        [
            old_like_model(thread_id=like.thread_id, user_id=like.user_id)
            for like in ThreadLike.objects.iterator()
        ],
        ignore_conflicts=True,
    )

    for thread in Thread.objects.exclude(user_achievement_id=None).iterator():
        award = UserAchievement.objects.select_related("achievement").get(
            pk=thread.user_achievement_id
        )
        event_id = f"user-achievement-{award.pk}"
        event = AchievementEvent.objects.create(
            event_id=event_id,
            achievement_id=award.achievement.code,
            earned_at=award.earned_at,
            author_id=award.user_id,
            thread_id=thread.pk,
        )
        thread.achievement_event_id = event.event_id
        thread.save(update_fields=["achievement_event_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("community", "0002_achievementevent"),
        ("dashboard", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name="thread",
            old_name="content",
            new_name="body",
        ),
        migrations.AlterField(
            model_name="thread",
            name="body",
            field=models.TextField(max_length=5000),
        ),
        migrations.RenameField(
            model_name="reply",
            old_name="content",
            new_name="body",
        ),
        migrations.AlterField(
            model_name="reply",
            name="body",
            field=models.TextField(max_length=2000),
        ),
        migrations.AlterModelOptions(
            name="reply",
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.AlterField(
            model_name="thread",
            name="category",
            field=models.CharField(
                choices=[
                    ("tips", "Tips"),
                    ("general", "General"),
                    ("achievement", "Achievement"),
                ],
                default="general",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="thread",
            name="is_auto_post",
            field=models.BooleanField(default=False, editable=False),
        ),
        migrations.AddField(
            model_name="thread",
            name="user_achievement",
            field=models.OneToOneField(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="community_thread",
                to="dashboard.userachievement",
            ),
        ),
        migrations.CreateModel(
            name="ThreadLike",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "thread",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="likes",
                        to="community.thread",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="community_likes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["created_at", "pk"]},
        ),
        migrations.AddConstraint(
            model_name="threadlike",
            constraint=models.UniqueConstraint(
                fields=("thread", "user"),
                name="unique_thread_like",
            ),
        ),
        migrations.RunPython(
            migrate_legacy_community_data,
            restore_legacy_community_data,
        ),
        migrations.RemoveField(model_name="thread", name="liked_by"),
        migrations.RemoveField(model_name="thread", name="achievement_event_id"),
        migrations.DeleteModel(name="AchievementEvent"),
        migrations.AddConstraint(
            model_name="thread",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("category", "achievement"), ("is_auto_post", True))
                    | (
                        models.Q(("is_auto_post", False), ("user_achievement__isnull", True))
                        & ~models.Q(("category", "achievement"))
                    )
                ),
                name="community_thread_auto_post_consistent",
            ),
        ),
    ]
