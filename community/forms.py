from django import forms
from .models import Reply, Thread


class ThreadForm(forms.ModelForm):
    class Meta:
        model = Thread
        fields = ["title", "category", "content"]
        labels = {"title": "Judul cerita", "category": "Kategori", "content": "Ceritamu"}
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Langkah kecil apa yang kamu coba hari ini?", "maxlength": 255}),
            "content": forms.Textarea(attrs={"placeholder": "Bagikan pengalaman, tips, atau hal yang sedang kamu pelajari…", "rows": 8}),
        }


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ["content"]
        labels = {"content": "Balasanmu"}
        widgets = {"content": forms.Textarea(attrs={"rows": 3, "placeholder": "Tambahkan semangat, ide, atau pengalamanmu…"})}
