from django.contrib import admin

from .models import EmissionFactor, TransportMode, Trip


@admin.register(TransportMode)
class TransportModeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'geoapify_profile', 'is_active')
    list_filter = ('is_active',)


@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = ('mode', 'kg_co2e_per_km', 'version', 'valid_from', 'valid_to')
    list_filter = ('mode',)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('user', 'origin_label', 'destination_label', 'mode', 'distance_km', 'emission_kg', 'traveled_at')
    list_filter = ('mode', 'traveled_at')
    search_fields = ('origin_label', 'destination_label', 'user__username')
    readonly_fields = ('distance_km', 'emission_kg', 'emission_factor', 'duration_s', 'route_geometry', 'distance_source', 'created_at', 'updated_at', 'legacy_calculation')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
