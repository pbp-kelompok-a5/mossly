from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dashboard", "0002_emissiontarget"),
    ]

    operations = [
        migrations.AddField(
            model_name="userachievement",
            name="seen",
            field=models.BooleanField(default=False),
        ),
    ]