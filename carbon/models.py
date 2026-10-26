from django.db import models
from django.contrib.auth.models import User
from datetime import date


class Trip(models.Model):
    """
    Catatan satu perjalanan pengguna.
    Menyimpan titik asal-tujuan, moda transportasi, jarak (dari Geoapify),
    dan estimasi emisi CO₂ yang dihitung di backend.
    """

    MODE_CHOICES = [
        ('drive', 'Mobil'),
        ('motorcycle', 'Motor'),
        ('bicycle', 'Sepeda'),
        ('walk', 'Jalan Kaki'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trips')

    # Lokasi asal
    origin_name = models.CharField(max_length=255, verbose_name='Asal')
    origin_lat = models.DecimalField(max_digits=9, decimal_places=6)
    origin_lon = models.DecimalField(max_digits=9, decimal_places=6)

    # Lokasi tujuan
    destination_name = models.CharField(max_length=255, verbose_name='Tujuan')
    destination_lat = models.DecimalField(max_digits=9, decimal_places=6)
    destination_lon = models.DecimalField(max_digits=9, decimal_places=6)

    # Transportasi & hasil kalkulasi
    transport_mode = models.CharField(max_length=20, choices=MODE_CHOICES, verbose_name='Moda Transportasi')
    distance_km = models.DecimalField(max_digits=8, decimal_places=3, verbose_name='Jarak (km)')
    co2_emission_kg = models.DecimalField(max_digits=8, decimal_places=4, verbose_name='Emisi CO₂ (kg)')

    # Metadata
    note = models.TextField(blank=True, default='', max_length=200, verbose_name='Catatan')
    trip_date = models.DateField(default=date.today, verbose_name='Tanggal Perjalanan')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-trip_date', '-created_at']

    def __str__(self):
        return f"{self.origin_name} → {self.destination_name} ({self.get_transport_mode_display()})"

    def get_mode_emoji(self):
        """Mengembalikan emoji sesuai moda transportasi."""
        emojis = {
            'drive': '🚗',
            'motorcycle': '🏍️',
            'bicycle': '🚲',
            'walk': '🚶',
        }
        return emojis.get(self.transport_mode, '🚗')
