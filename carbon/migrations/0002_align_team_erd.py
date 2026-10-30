"""Normalisasi ERD dan ganti metrik ke CO2e dengan sumber terverifikasi.

Perhitungan lama, bila ada, disalin ke legacy_calculation sebelum dihitung
ulang. Tidak ada tabel pengguna/modul lain yang ditulis oleh migrasi ini.
"""
from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from django.db import migrations, models
import django.db.models.deletion
import django.core.validators

SOURCE_URL = 'https://assets.publishing.service.gov.uk/media/649c536906179b00113f74a9/ghg-conversion-factors-2023-flat-file-update.xlsx'
SOURCE_NOTE = ('UK DESNZ/Defra 2023 flat file v1.1, updated 28 June 2023; '
               'Factors by Category; Scope 1 direct emissions, kg CO2e per vehicle-km. '
               'Used as an international proxy, not an Indonesian fleet factor. ')


def seed_and_convert(apps, schema_editor):
    """Isi moda dan faktor awal, lalu sesuaikan perjalanan lama dengan ERD."""
    db = schema_editor.connection.alias
    Mode = apps.get_model('carbon', 'TransportMode')
    Factor = apps.get_model('carbon', 'EmissionFactor')
    Trip = apps.get_model('carbon', 'Trip')
    seeds = [
        ('mobil', 'Mobil', 'drive', True, '0.166638588', 'DESNZ-2023-v1.1', 'Cars (by size), Average car, Unknown fuel; J1600; ID 4_301_3074_4_1. '),
        ('motor', 'Motor', 'motorcycle', True, '0.113674264', 'DESNZ-2023-v1.1', 'Motorbike, Average; J1668; ID 4_302_3080_4_1. '),
        ('sepeda', 'Sepeda', 'bicycle', True, '0', 'MVP-direct-2026-v1', None),
        ('jalan', 'Jalan Kaki', 'walk', True, '0', 'MVP-direct-2026-v1', None),
        ('bus', 'Bus', None, False, None, None, None),
        ('kereta', 'Kereta', None, False, None, None, None),
    ]
    profiles = {}
    for code, name, profile, active, value, version, reference in seeds:
        mode = Mode.objects.using(db).create(code=code, name=name, geoapify_profile=profile, is_active=active)
        if value is None:
            continue
        source = (SOURCE_NOTE + reference + SOURCE_URL) if reference else (
            'Mossly MVP: zero direct transport emissions while walking/cycling; '
            'excludes food, vehicle manufacture and lifecycle emissions; not a DESNZ factor.'
        )
        factor = Factor.objects.using(db).create(
            mode=mode, kg_co2e_per_km=Decimal(value), source=source, version=version,
            valid_from=date(2023, 1, 1), valid_to=None,
        )
        profiles[profile] = (mode, factor)
    for trip in Trip.objects.using(db).all().iterator():
        mode, factor = profiles[trip.transport_mode]
        trip.legacy_calculation = {
            'emission_kg': str(trip.emission_kg), 'factor': str(trip.legacy_factor_value),
            'unit': trip.emission_factor_unit, 'source': trip.emission_factor_source,
            'version': trip.emission_factor_version,
        }
        trip.mode_id = mode.pk
        trip.emission_factor_id = factor.pk
        trip.emission_kg = (trip.distance_km * factor.kg_co2e_per_km).quantize(Decimal('.0001'), rounding=ROUND_HALF_UP)
        trip.traveled_at = datetime.combine(trip.trip_date, time.min, tzinfo=ZoneInfo('Asia/Jakarta'))
        trip.save(using=db, update_fields=['legacy_calculation', 'mode', 'emission_factor', 'emission_kg', 'traveled_at'])


class Migration(migrations.Migration):
    dependencies = [('carbon', '0001_initial')]
    operations = [
        migrations.RemoveConstraint('trip', 'carbon_lat_range'),
        migrations.RemoveConstraint('trip', 'carbon_lon_range'),
        migrations.RemoveConstraint('trip', 'carbon_positive_results'),
        migrations.RemoveConstraint('trip', 'carbon_nonnegative_factor'),
        migrations.CreateModel(name='TransportMode', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
            ('code', models.SlugField(max_length=20, unique=True)),
            ('name', models.CharField(max_length=50)),
            ('geoapify_profile', models.CharField(max_length=20, null=True, blank=True)),
            ('is_active', models.BooleanField(default=True)),
        ], options={'ordering': ['id']}),
        migrations.CreateModel(name='EmissionFactor', fields=[
            ('id', models.BigAutoField(primary_key=True, serialize=False, auto_created=True, verbose_name='ID')),
            ('kg_co2e_per_km', models.DecimalField(max_digits=12, decimal_places=9, validators=[django.core.validators.MinValueValidator(0)])),
            ('source', models.TextField()), ('version', models.CharField(max_length=100)),
            ('valid_from', models.DateField()), ('valid_to', models.DateField(null=True, blank=True)),
            ('mode', models.ForeignKey(to='carbon.transportmode', on_delete=django.db.models.deletion.PROTECT, related_name='emission_factors')),
        ], options={'ordering': ['-valid_from', '-pk'], 'constraints': [
            models.UniqueConstraint(fields=['mode', 'version'], name='carbon_factor_version_unique'),
            models.CheckConstraint(condition=models.Q(kg_co2e_per_km__gte=0), name='carbon_factor_nonnegative'),
            models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F('valid_from')), name='carbon_factor_dates'),
        ]}),
        migrations.RenameField('trip', 'origin_name', 'origin_label'),
        migrations.RenameField('trip', 'origin_lon', 'origin_lng'),
        migrations.RenameField('trip', 'destination_name', 'destination_label'),
        migrations.RenameField('trip', 'destination_lon', 'destination_lng'),
        migrations.RenameField('trip', 'co2_emission_kg', 'emission_kg'),
        migrations.RenameField('trip', 'emission_factor', 'legacy_factor_value'),
        migrations.AddField('trip', 'mode', models.ForeignKey(to='carbon.transportmode', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='trips')),
        migrations.AddField('trip', 'emission_factor', models.ForeignKey(to='carbon.emissionfactor', null=True, on_delete=django.db.models.deletion.PROTECT, related_name='trips')),
        migrations.AddField('trip', 'traveled_at', models.DateTimeField(null=True)),
        migrations.AddField('trip', 'distance_source', models.CharField(max_length=20, default='routing', choices=[('routing', 'Geoapify Routing'), ('approx_drive', 'Pendekatan rute kendaraan jalan'), ('manual', 'Jarak manual')])),
        migrations.AddField('trip', 'duration_s', models.PositiveIntegerField(null=True, blank=True)),
        migrations.AddField('trip', 'route_geometry', models.JSONField(null=True, blank=True)),
        migrations.AddField('trip', 'legacy_calculation', models.JSONField(null=True, blank=True, editable=False)),
        # Mengubah CO2e kembali ke CO2 tidak memiliki konversi umum yang sah.
        migrations.RunPython(seed_and_convert),
        migrations.RemoveField('trip', 'transport_mode'),
        migrations.RemoveField('trip', 'trip_date'),
        migrations.RemoveField('trip', 'legacy_factor_value'),
        migrations.RemoveField('trip', 'emission_factor_source'),
        migrations.RemoveField('trip', 'emission_factor_unit'),
        migrations.RemoveField('trip', 'emission_factor_version'),
        migrations.AlterField('trip', 'mode', models.ForeignKey(to='carbon.transportmode', on_delete=django.db.models.deletion.PROTECT, related_name='trips')),
        migrations.AlterField('trip', 'emission_factor', models.ForeignKey(to='carbon.emissionfactor', on_delete=django.db.models.deletion.PROTECT, related_name='trips')),
        migrations.AlterField('trip', 'traveled_at', models.DateTimeField()),
        migrations.AlterField('trip', 'distance_km', models.DecimalField(max_digits=8, decimal_places=3, validators=[django.core.validators.MinValueValidator(Decimal('.001'))])),
        migrations.AlterField('trip', 'emission_kg', models.DecimalField(max_digits=8, decimal_places=4, validators=[django.core.validators.MinValueValidator(0)])),
        migrations.AlterModelOptions('trip', {'ordering': ['-traveled_at', '-created_at', '-pk']}),
        migrations.AddConstraint('trip', models.CheckConstraint(condition=models.Q(origin_lat__gte=-90, origin_lat__lte=90, destination_lat__gte=-90, destination_lat__lte=90), name='carbon_lat_range')),
        migrations.AddConstraint('trip', models.CheckConstraint(condition=models.Q(origin_lng__gte=-180, origin_lng__lte=180, destination_lng__gte=-180, destination_lng__lte=180), name='carbon_lng_range')),
        migrations.AddConstraint('trip', models.CheckConstraint(condition=models.Q(distance_km__gt=0, emission_kg__gte=0), name='carbon_positive_results')),
    ]
