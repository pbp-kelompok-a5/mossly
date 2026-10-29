from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.html import strip_tags

from . import services
from .display import DAY_SHORT, ICON_TINTS
from .models import Goal, GoalChecklistItem, GoalProgressLog, Habit

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

    def clean_name(self):
        # Buang tag HTML (Tutorial 05); escaping di template tetap pertahanan utama.
        name = strip_tags(self.cleaned_data["name"]).strip()
        if not name:
            raise forms.ValidationError("Nama habit tidak boleh hanya berisi tag HTML.")
        return name

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


MAX_CHECKLIST_ITEMS = 20
CHECKLIST_LABEL_MAX = GoalChecklistItem._meta.get_field("label").max_length


class GoalForm(forms.ModelForm):
    """Goal fields plus an optional checklist sent as parallel lists.

    Each checklist row posts "checklist_id" (empty for new rows) and
    "checklist_label". Rows with an empty label are dropped, so clearing or
    removing a row deletes it; existing rows keep their done state.
    """

    class Meta:
        model = Goal
        fields = ["title", "category", "target_value", "unit", "start_date", "deadline"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input"}),
            "category": forms.Select(attrs={"class": "input"}),
            "target_value": forms.NumberInput(attrs={"class": "input", "min": "0.01", "step": "any"}),
            "unit": forms.Select(attrs={"class": "input"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"),
            "deadline": forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"),
        }
        error_messages = {
            "title": {
                "required": "Nama goal wajib diisi.",
                "max_length": "Nama goal maksimal 120 karakter.",
            },
            "category": {
                "required": "Pilih kategori goal.",
                "invalid_choice": "Pilihan kategori tidak valid.",
            },
            "target_value": {
                "required": "Target wajib diisi.",
                "invalid": "Target harus berupa angka.",
                "min_value": "Target harus lebih dari 0.",
                "max_digits": "Target terlalu besar.",
                "max_decimal_places": "Target maksimal 2 angka di belakang koma.",
                "max_whole_digits": "Target terlalu besar.",
            },
            "unit": {"required": "Pilih satuan.", "invalid_choice": "Pilihan satuan tidak valid."},
            "start_date": {"required": "Tanggal mulai wajib diisi.", "invalid": "Tanggal tidak valid."},
            "deadline": {"required": "Deadline wajib diisi.", "invalid": "Tanggal tidak valid."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].choices = [("", "Pilih kategori")] + list(Goal.Category.choices)
        if self.is_bound:
            self.checklist_rows = self._posted_rows()
        elif self.instance.pk:
            self.checklist_rows = [
                {"id": str(item.pk), "label": item.label}
                for item in self.instance.checklist_items.all()
            ]
        else:
            self.checklist_rows = []

    def clean_title(self):
        title = strip_tags(self.cleaned_data["title"]).strip()
        if not title:
            raise forms.ValidationError("Nama goal tidak boleh hanya berisi tag HTML.")
        return title

    def _posted_rows(self):
        ids = self.data.getlist("checklist_id")
        rows = []
        for index, label in enumerate(self.data.getlist("checklist_label")):
            label = label.strip()
            if not label:
                continue
            item_id = ids[index] if index < len(ids) and ids[index].isdigit() else ""
            rows.append({"id": item_id, "label": label})
        return rows

    def clean(self):
        cleaned = super().clean()
        if len(self.checklist_rows) > MAX_CHECKLIST_ITEMS:
            self.add_error(None, f"Checklist maksimal {MAX_CHECKLIST_ITEMS} item.")
        if any(len(row["label"]) > CHECKLIST_LABEL_MAX for row in self.checklist_rows):
            self.add_error(None, f"Setiap item checklist maksimal {CHECKLIST_LABEL_MAX} karakter.")
        start, deadline = cleaned.get("start_date"), cleaned.get("deadline")
        # Only for new goals; an ordering problem is reported by the model instead.
        if not self.instance.pk and start and deadline and start <= deadline < services.local_today():
            self.add_error("deadline", "Deadline tidak boleh di masa lalu.")
        unit, target = cleaned.get("unit"), cleaned.get("target_value")
        if unit and target is not None:
            try:
                services.check_amount(unit, target)
            except ValidationError as error:
                self.add_error("target_value", error.messages[0])
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        goal = super().save(commit=True)
        existing = {str(item.pk): item for item in goal.checklist_items.all()}
        posted_ids = {row["id"] for row in self.checklist_rows}
        removed = [item.pk for item_id, item in existing.items() if item_id not in posted_ids]
        goal.checklist_items.filter(pk__in=removed).delete()
        for position, row in enumerate(self.checklist_rows):
            item = existing.get(row["id"])
            if item is None:
                GoalChecklistItem.objects.create(goal=goal, label=row["label"], position=position)
            else:
                item.label, item.position = row["label"], position
                item.save(update_fields=["label", "position"])
        return goal


class GoalProgressForm(forms.ModelForm):
    class Meta:
        model = GoalProgressLog
        fields = ["amount", "note"]
        widgets = {
            "amount": forms.NumberInput(attrs={"class": "input stepper-input"}),
            "note": forms.TextInput(attrs={"class": "input"}),
        }
        error_messages = {
            "amount": {
                "required": "Isi jumlah progres.",
                "invalid": "Jumlah progres harus berupa angka.",
                "min_value": "Jumlah progres harus lebih dari 0.",
                "max_digits": "Jumlah progres terlalu besar.",
                "max_decimal_places": "Maksimal 2 angka di belakang koma.",
                "max_whole_digits": "Jumlah progres terlalu besar.",
            },
            "note": {"max_length": "Catatan maksimal 200 karakter."},
        }

    def __init__(self, *args, goal=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.goal = goal
        whole = goal is not None and goal.unit in services.WHOLE_NUMBER_UNITS
        self.fields["amount"].widget.attrs.update(
            {"min": "1", "step": "1"} if whole else {"min": "0.01", "step": "0.01"}
        )
        if not self.is_bound:
            self.initial.setdefault("amount", 1)

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if self.goal is not None:
            try:
                services.check_amount(self.goal.unit, amount)
            except ValidationError as error:
                raise forms.ValidationError(error.messages[0])
        return amount
