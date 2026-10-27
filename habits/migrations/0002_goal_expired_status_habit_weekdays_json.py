from django.db import migrations, models


def digits_to_list(apps, schema_editor):
    Habit = apps.get_model("habits", "Habit")
    for habit in Habit.objects.all():
        if habit.frequency_type == "weekdays" and habit.weekdays:
            habit.weekday_list = sorted({int(d) for d in habit.weekdays})
        else:
            habit.weekday_list = None
        habit.save(update_fields=["weekday_list"])


def list_to_digits(apps, schema_editor):
    Habit = apps.get_model("habits", "Habit")
    for habit in Habit.objects.all():
        habit.weekdays = "".join(str(d) for d in habit.weekday_list or [])
        habit.save(update_fields=["weekdays"])


class Migration(migrations.Migration):

    dependencies = [
        ("habits", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="goal",
            name="status",
            field=models.CharField(
                choices=[("active", "Aktif"), ("completed", "Selesai"), ("expired", "Lewat deadline")],
                default="active",
                max_length=20,
            ),
        ),
        # Stored day digits ("024") cannot be cast to JSON in place, so the
        # values are copied into a new column first.
        migrations.AddField(
            model_name="habit",
            name="weekday_list",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.RunPython(digits_to_list, list_to_digits),
        migrations.RemoveField(model_name="habit", name="weekdays"),
        migrations.RenameField(model_name="habit", old_name="weekday_list", new_name="weekdays"),
    ]
