from django.contrib import admin
from .models import Trip


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('user', 'origin_name', 'destination_name', 'transport_mode',
                    'distance_km', 'co2_emission_kg', 'trip_date')
    list_filter = ('transport_mode', 'trip_date')
    search_fields = ('origin_name', 'destination_name', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
