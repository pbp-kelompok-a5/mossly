from django import forms

from .models import Reply, Thread


class ThreadForm(forms.ModelForm):
    category = forms.ChoiceField(
        choices=(
            (Thread.Category.TIPS, Thread.Category.TIPS.label),
            (Thread.Category.GENERAL, Thread.Category.GENERAL.label),
        ),
        label="Kategori",
    )

    class Meta:
        model = Thread
        fields = ["title", "category", "body"]
        labels = {"title": "Judul cerita", "body": "Ceritamu"}
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": "Langkah kecil apa yang kamu coba hari ini?",
                    "maxlength": 255,
                }
            ),
            "body": forms.Textarea(
                attrs={
                    "placeholder": "Bagikan pengalaman, tips, atau hal yang sedang kamu pelajari…",
                    "rows": 8,
                }
            ),
        }


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ["body"]
        labels = {"body": "Balasanmu"}
        widgets = {
            "body": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Tambahkan semangat, ide, atau pengalamanmu…",
                }
            )
        }
