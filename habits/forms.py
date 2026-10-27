from django import forms

from .models import GoalProgressLog


class GoalProgressForm(forms.ModelForm):
    class Meta:
        model = GoalProgressLog
        fields = ["amount", "note"]
