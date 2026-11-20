from rest_framework import serializers


class BadgeSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    icon = serializers.CharField()
    category = serializers.CharField()
    category_label = serializers.CharField()
    earned = serializers.BooleanField()
    earned_at = serializers.DateTimeField(allow_null=True)
    percent = serializers.IntegerField()
    progress = serializers.CharField()
    threshold = serializers.IntegerField()