from django.conf import settings
from django.db import migrations


def create_existing_profiles(apps, schema_editor):
    user_app, user_model = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(user_app, user_model)
    Profile = apps.get_model("accounts", "UserProfile")
    alias = schema_editor.connection.alias
    for user in User.objects.using(alias).all().iterator():
        name = f"{user.first_name} {user.last_name}".strip() or user.username
        Profile.objects.using(alias).get_or_create(
            user_id=user.pk, defaults={"display_name": name[:80]}
        )


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0001_initial"),
    ]
    operations = [migrations.RunPython(create_existing_profiles, migrations.RunPython.noop)]
