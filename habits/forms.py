from django import forms

from .display import DAY_SHORT, ICON_TINTS
from .models import GoalProgressLog, Habit

ALL_WEEKDAYS = [str(i) for i in range(7)]


class HabitForm(forms.ModelForm):
    # One control for the schedule: every day is checked by default and the
    # user unchecks the days to skip. frequency_type is derived from it.
    weekdays = forms.MultipleChoiceField(
        choices=[(str(i), label) for i, label in enumerate(DAY_SHORT)],
        initial=ALL_WEEKDAYS,
        widget=forms.CheckboxSelectMultiple,
        error_messages={
            "required": "Pilih minimal satu hari.",
            "invalid_choice": "Pilihan hari tidak valid.",
        },
    )

    class Meta:
        model = Habit
        fields = ["name", "icon", "time_of_day", "weekdays", "reminder_time"]
        widgets = {
            "icon": forms.RadioSelect,
            "time_of_day": forms.RadioSelect,
            "reminder_time": forms.TimeInput(
                attrs={"type": "time", "class": "input"}, format="%H:%M"
            ),
        }
        error_messages = {
            "name": {
                "required": "Nama habit wajib diisi.",
                "max_length": "Nama habit maksimal 80 karakter.",
            },
            "icon": {"required": "Pilih satu ikon.", "invalid_choice": "Pilihan ikon tidak valid."},
            "time_of_day": {
                "required": "Pilih waktu check-in.",
                "invalid_choice": "Pilihan waktu tidak valid.",
            },
            "reminder_time": {"invalid": "Format jam tidak valid."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # RadioSelect would otherwise add an empty "---------" choice.
        for name in ("icon", "time_of_day"):
            self.fields[name].choices = self.Meta.model._meta.get_field(name).choices
        if self.instance.pk:
            self.initial["weekdays"] = (
                [str(d) for d in self.instance.weekdays or ()]
                if self.instance.frequency_type == Habit.Frequency.WEEKDAYS
                else ALL_WEEKDAYS
            )

    def icon_options(self):
        """Radio widgets for the icon field, each paired with its tint."""
        return [(radio, ICON_TINTS[radio.data["value"]]) for radio in self["icon"]]

    def clean_weekdays(self):
        days = sorted(int(d) for d in self.cleaned_data["weekdays"])
        # Every day checked is stored as a daily habit, so "every day" has
        # exactly one representation in the table.
        if len(days) == len(ALL_WEEKDAYS):
            self.instance.frequency_type = Habit.Frequency.DAILY
            return None
        self.instance.frequency_type = Habit.Frequency.WEEKDAYS
        return days

    def save(self, commit=True):
        self.instance.tint = ICON_TINTS.get(self.instance.icon, Habit.Tint.MOSS_100)
        return super().save(commit)


class GoalProgressForm(forms.ModelForm):
    class Meta:
        model = GoalProgressLog
        fields = ["amount", "note"]
