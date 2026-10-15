from django import forms
from .models import Reply, Thread

class ThreadForm(forms.ModelForm):
    class Meta:
        model = Thread
        fields = ["title", "content", "category"]
        
        widgets = {
            "title": forms.TextInput(attrs = {
                "placeholder": "Apa yang ingin kamu bagikan?",
            }),
            "content": forms.Textarea(attrs = {
                "placeholder": "Ceritakan tips atau pengalamanmu...",
            }),
        }

class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ["content"]
        
        widgets = {
            "content": forms.Textarea(attrs = {
                "rows":3,
                "placeholder":"Tulis balasanmu...",
            }),
        }