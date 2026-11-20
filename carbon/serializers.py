"""Kontrak JSON read-only untuk Carbon Checkpoint 1."""

from rest_framework import serializers

from .models import TransportMode, Trip


class TransportModeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransportMode
        fields = ('id', 'code', 'name', 'geoapify_profile')
        read_only_fields = fields


class TripHistorySerializer(serializers.ModelSerializer):
    date = serializers.DateField(source='trip_date', read_only=True)
    origin = serializers.CharField(source='origin_label', read_only=True)
    destination = serializers.CharField(source='destination_label', read_only=True)
    mode_code = serializers.CharField(source='mode.code', read_only=True)
    mode_display = serializers.CharField(source='mode.name', read_only=True)
    distance_km = serializers.DecimalField(
        max_digits=8, decimal_places=3, coerce_to_string=False, read_only=True,
    )
    emission_kg = serializers.DecimalField(
        max_digits=8, decimal_places=4, coerce_to_string=False, read_only=True,
    )

    class Meta:
        model = Trip
        fields = (
            'id', 'date', 'origin', 'destination', 'mode_code', 'mode_display',
            'distance_km', 'emission_kg', 'duration_s', 'distance_source', 'note',
        )
        read_only_fields = fields


class TripHistoryQuerySerializer(serializers.Serializer):
    mode = serializers.CharField(required=False, allow_blank=True, max_length=20, default='')
    sort = serializers.ChoiceField(
        choices=('newest', 'oldest', 'distance', 'emission'), default='newest',
    )
    page = serializers.IntegerField(min_value=1, default=1)

    def validate_mode(self, value):
        # Moda nonaktif tetap boleh dipakai untuk menyaring riwayat lama.
        if value and not TransportMode.objects.filter(code=value).exists():
            raise serializers.ValidationError('Moda transportasi tidak dikenal.')
        return value
