"""Representasi JSON Community untuk aplikasi mobile."""

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Thread


class ThreadAuthorSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    avatar = serializers.CharField(source="profile.avatar", read_only=True)

    class Meta:
        model = get_user_model()
        fields = ["id", "username", "display_name", "avatar"]
        read_only_fields = fields

    def get_display_name(self, author):
        return author.profile.display_name or author.username


class ThreadSerializer(serializers.ModelSerializer):
    """Gunakan queryset threads_for(user) agar anotasi ikut tersedia."""

    author = ThreadAuthorSerializer(read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    reply_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)

    class Meta:
        model = Thread
        fields = [
            "id", "title", "body", "category", "author", "is_auto_post",
            "created_at", "updated_at", "like_count", "reply_count", "is_liked",
        ]
        read_only_fields = fields


class ThreadFeedQuerySerializer(serializers.Serializer):
    """Validasi filter dan nomor halaman sebelum membaca feed."""

    category = serializers.ChoiceField(
        choices=Thread.Category.choices, allow_blank=True, default=""
    )
    author = serializers.CharField(allow_blank=True, default="")
    page = serializers.IntegerField(min_value=1, default=1)
