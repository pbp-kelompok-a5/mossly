from datetime import date

from django import forms

from habits import display
from habits import services as habit_services

from .models import EmissionTarget


class EmissionTargetForm(forms.ModelForm):
    class Meta:
        model = EmissionTarget
        fields = ["target_kg"]
        labels = {"target_kg": "Target emisi (kg CO₂e)"}
        widgets = {
            "target_kg": forms.NumberInput(
                attrs={
                    "class": "dash-input",
                    "step": "0.1",
                    "min": "0.1",
                    "inputmode": "decimal",
                    "placeholder": "Contoh: 20",
                }
            )
        }
        error_messages = {
            "target_kg": {
                "required": "Isi target emisi dulu.",
                "invalid": "Masukkan angka yang valid.",
                "min_value": "Target minimal 0,1 kg.",
                "max_value": "Target maksimal 10.000 kg.",
            }
        }


class EmissionTargetCreateForm(EmissionTargetForm):
    month = forms.ChoiceField(label="Bulan")

    def __init__(self, *args, user, today, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        choices = []
        for step in range(3):
            year, month = habit_services.shift_month(today.year, today.month, step)
            choices.append((f"{year}-{month:02d}", f"{display.MONTH_NAMES[month - 1]} {year}"))
        self.fields["month"].choices = choices
        self.fields["month"].widget.attrs["class"] = "dash-input"
        self.order_fields(["month", "target_kg"])

    def clean_month(self):
        year, month = map(int, self.cleaned_data["month"].split("-"))
        first = date(year, month, 1)
        if EmissionTarget.objects.filter(user=self.user, month=first).exists():
            raise forms.ValidationError("Target untuk bulan ini sudah ada. Ubah target yang sudah ada.")
        return first

    def save(self, commit=True):
        target = super().save(commit=False)
        target.user = self.user
        target.month = self.cleaned_data["month"]
        if commit:
            target.save()
        return target