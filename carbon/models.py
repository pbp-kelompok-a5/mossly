"""Entitas Carbon mengikuti ERD tim: TransportMode, EmissionFactor, dan Trip."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction

from .dates import local_date, today

SUPPORTED_PROFILES = ('drive', 'motorcycle', 'bicycle', 'walk')


class ApiUsage(models.Model):
    """Counter internal pembatas API; bukan bagian dari riwayat perjalanan."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    day = models.DateField(default=today)
    daily_count = models.PositiveIntegerField(default=0)
    minute = models.BigIntegerField(default=0)
    minute_count = models.PositiveIntegerField(default=0)


class TransportMode(models.Model):
    code = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=50)
    geoapify_profile = models.CharField(max_length=20, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name

    def clean(self):
        if self.is_active and self.geoapify_profile not in SUPPORTED_PROFILES:
            raise ValidationError('MVP hanya mengaktifkan moda dengan empat profil routing yang didukung.')


class FactorQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Faktor emisi tidak boleh diubah. Buat versi baru.')

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError('Faktor emisi tidak boleh diubah. Buat versi baru.')


class EmissionFactor(models.Model):
    mode = models.ForeignKey(TransportMode, on_delete=models.PROTECT, related_name='emission_factors')
    kg_co2e_per_km = models.DecimalField(max_digits=12, decimal_places=9, validators=[MinValueValidator(0)])
    source = models.TextField()
    version = models.CharField(max_length=100)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    objects = FactorQuerySet.as_manager()

    class Meta:
        ordering = ['-valid_from', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['mode', 'version'], name='carbon_factor_version_unique'),
            models.CheckConstraint(condition=models.Q(kg_co2e_per_km__gte=0), name='carbon_factor_nonnegative'),
            models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F('valid_from')), name='carbon_factor_dates'),
        ]

    def __str__(self):
        return f'{self.mode.name} — {self.version}'

    def clean(self):
        if not self.mode_id or not self.valid_from:
            return
        overlaps = type(self).objects.filter(mode_id=self.mode_id).exclude(pk=self.pk)
        overlaps = overlaps.filter(models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=self.valid_from))
        if self.valid_to:
            overlaps = overlaps.filter(valid_from__lte=self.valid_to)
        if overlaps.exists():
            raise ValidationError('Masa berlaku faktor untuk moda ini bertumpang-tindih. Akhiri periode lama sebelum membuat versi baru.')

    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Serialize penambahan versi untuk moda yang sama di database produksi.
            TransportMode.objects.select_for_update().get(pk=self.mode_id)
            if self.pk:
                previous = type(self).objects.get(pk=self.pk)
                if any(getattr(previous, field.attname) != getattr(self, field.attname)
                       for field in self._meta.fields if field.name != 'valid_to'):
                    raise ValidationError('Nilai dan sumber faktor tidak boleh diubah. Buat versi baru.')
            self.full_clean()
            return super().save(*args, **kwargs)


class Trip(models.Model):
    class DistanceSource(models.TextChoices):
        ROUTING = 'routing', 'Geoapify Routing'
        APPROX_DRIVE = 'approx_drive', 'Pendekatan rute kendaraan jalan'
        MANUAL = 'manual', 'Jarak manual'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trips')
    mode = models.ForeignKey(TransportMode, on_delete=models.PROTECT, related_name='trips')
    emission_factor = models.ForeignKey(EmissionFactor, on_delete=models.PROTECT, related_name='trips')
    origin_label = models.CharField(max_length=255, verbose_name='Asal')
    origin_lat = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    origin_lng = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    destination_label = models.CharField(max_length=255, verbose_name='Tujuan')
    destination_lat = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    destination_lng = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    distance_km = models.DecimalField(max_digits=8, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    distance_source = models.CharField(max_length=20, choices=DistanceSource.choices, default=DistanceSource.ROUTING)
    duration_s = models.PositiveIntegerField(null=True, blank=True)
    route_geometry = models.JSONField(null=True, blank=True)
    emission_kg = models.DecimalField(max_digits=8, decimal_places=4, validators=[MinValueValidator(0)])
    traveled_at = models.DateTimeField()
    # Tambahan PRD tetap tersedia, tanpa menggandakan tanggal perjalanan di DB.
    note = models.TextField(blank=True, default='', max_length=200, verbose_name='Catatan')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Audit saat migrasi CO2 lama -> CO2e: angka dan sumber asli tidak hilang.
    legacy_calculation = models.JSONField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['-traveled_at', '-created_at', '-pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(origin_lat__gte=-90, origin_lat__lte=90, destination_lat__gte=-90, destination_lat__lte=90), name='carbon_lat_range'),
            models.CheckConstraint(condition=models.Q(origin_lng__gte=-180, origin_lng__lte=180, destination_lng__gte=-180, destination_lng__lte=180), name='carbon_lng_range'),
            models.CheckConstraint(condition=models.Q(distance_km__gt=0, emission_kg__gte=0), name='carbon_positive_results'),
        ]

    def clean(self):
        if self.mode_id and self.emission_factor_id and self.emission_factor.mode_id != self.mode_id:
            raise ValidationError('Faktor emisi harus sesuai dengan moda perjalanan.')
        if self.traveled_at and local_date(self.traveled_at) > today():
            raise ValidationError('Tanggal perjalanan tidak boleh di masa depan.')

    @property
    def trip_date(self):
        return local_date(self.traveled_at)

    def __str__(self):
        return f'{self.origin_label} → {self.destination_label} ({self.mode.name})'

    def get_mode_emoji(self):
        return {'mobil': '🚗', 'motor': '🏍️', 'sepeda': '🚲', 'jalan': '🚶'}.get(self.mode.code, '🚗')
