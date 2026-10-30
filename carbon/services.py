"""Geoapify dipanggil di backend; emisi dihitung terpisah dari data rute.

https://apidocs.geoapify.com/docs/geocoding/
https://apidocs.geoapify.com/docs/routing/
"""

from hashlib import sha256
from time import time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests
from django.apps import apps
from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Q

from .dates import today
from .models import ApiUsage, EmissionFactor, SUPPORTED_PROFILES, TransportMode

# Faktor aktif dibaca dari tabel EmissionFactor, bukan konstanta runtime.
LOCATION_SALT = 'carbon.location.v1'
API_MINUTE_LIMIT = 30
API_DAILY_LIMIT = 150


class GeoapifyError(Exception):
    """Kesalahan layanan yang aman ditampilkan tanpa membocorkan API key."""
    def __init__(self, message, code='provider_error', status=502):
        super().__init__(message)
        self.code = code
        self.status = status


def get_api_key():
    """Baca API key dari konfigurasi backend."""
    return getattr(settings, 'GEOAPIFY_API_KEY', '').strip()


def check_api_limit(user):
    """Satu jatah untuk pencarian, pin, preview, dan penyimpanan rute.

    Counter disimpan di DB agar tidak ter-reset saat server restart dan tetap
    dipakai bersama oleh semua worker. Cache hanya untuk hasil pencarian.
    """
    day, minute = today(), int(time()) // 60
    with transaction.atomic():
        ApiUsage.objects.get_or_create(user=user)
        usage = ApiUsage.objects.filter(user=user)
        usage.exclude(day=day).update(day=day, daily_count=0)
        usage.exclude(minute=minute).update(minute=minute, minute_count=0)
        accepted = usage.filter(
            day=day, minute=minute,
            daily_count__lt=API_DAILY_LIMIT, minute_count__lt=API_MINUTE_LIMIT,
        ).update(daily_count=F('daily_count') + 1, minute_count=F('minute_count') + 1)
    if not accepted:
        raise GeoapifyError(
            'Batas pencarian/perhitungan tercapai (30 per menit, 150 per hari). '
            'Coba setelah satu menit, atau besok jika jatah harian habis.',
            'rate_limited', 429,
        )


def coordinate(value, limit):
    """Validasi rentang koordinat dan bulatkan menjadi enam desimal."""
    try:
        number = Decimal(str(value))
        if not number.is_finite() or not -limit <= number <= limit:
            raise ValueError
        return number.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Koordinat tidak valid.') from None


def validate_route_inputs(origin_lat, origin_lon, dest_lat, dest_lon, mode):
    """Periksa profil moda dan pastikan titik asal serta tujuan berbeda."""
    if mode not in SUPPORTED_PROFILES:
        raise ValueError('Moda transportasi tidak valid.')
    coords = (coordinate(origin_lat, 90), coordinate(origin_lon, 180),
              coordinate(dest_lat, 90), coordinate(dest_lon, 180))
    if coords[:2] == coords[2:]:
        raise ValueError('Asal dan tujuan harus berbeda.')
    return coords


def _request(endpoint, params):
    """Panggil Geoapify dengan timeout dan ubah kegagalan menjadi pesan aman."""
    api_key = get_api_key()
    if not api_key:
        raise GeoapifyError('Layanan lokasi belum tersedia. API key backend belum dikonfigurasi.', 'service_unavailable', 503)
    try:
        response = requests.get(
            f'https://api.geoapify.com/v1/{endpoint}',
            params={**params, 'apiKey': api_key}, timeout=10,
        )
        if response.status_code == 429:
            raise GeoapifyError('Layanan sedang sibuk, coba lagi nanti.', 'provider_limited', 503)
        if response.status_code in (401, 403):
            raise GeoapifyError('Layanan lokasi sedang tidak tersedia.', 'service_unavailable', 503)
        if endpoint == 'routing' and response.status_code == 400:
            try:
                message = str(response.json().get('message', '')).lower()
            except (ValueError, AttributeError):
                message = ''
            if 'route' in message and any(s in message for s in ('not found', 'could not', 'failed to find')):
                raise GeoapifyError('Rute tidak ditemukan untuk moda transportasi ini.', 'route_not_found', 404)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or not isinstance(data.get('features'), list):
            raise ValueError
        return data['features']
    except requests.Timeout:
        raise GeoapifyError('Layanan lokasi terlalu lama merespons. Silakan coba lagi.', 'provider_timeout', 504) from None
    except (requests.RequestException, ValueError):
        # URL exception requests dapat mengandung API key: jangan diteruskan.
        raise GeoapifyError('Gagal mengambil data lokasi atau rute. Silakan coba lagi.') from None


def geocode_search(query):
    """Cari maksimal lima alamat Indonesia dan simpan hasilnya di cache."""
    query = ' '.join(query.split())
    key = 'carbon:geocode:v1:' + sha256(query.casefold().encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached
    features = _request('geocode/search', {'text': query, 'filter': 'countrycode:id', 'limit': 5})
    results = []
    for feature in features[:5]:
        try:
            props = feature['properties']
            name = props['formatted'].strip()
            if props.get('country_code') != 'id' or not name or len(name) > 255:
                continue
            lat, lon = coordinate(props['lat'], 90), coordinate(props['lon'], 180)
            results.append({'name': name, 'lat': float(lat), 'lon': float(lon)})
        except (KeyError, TypeError, AttributeError, ValueError):
            continue
    if features and not results:
        raise GeoapifyError('Hasil lokasi tidak valid. Coba nama tempat yang lebih lengkap.')
    # Hanya lokasi publik yang di-cache; token tetap dibuat untuk masing-masing user.
    cache.set(key, results, 3600)
    return results


def location_token(location, user_id):
    """Tandatangani lokasi dan pemiliknya agar isian tidak dapat dipalsukan."""
    return signing.dumps({
        'user': user_id, 'name': location['name'],
        'lat': str(coordinate(location['lat'], 90)),
        'lon': str(coordinate(location['lon'], 180)), 'country': 'id',
    }, salt=LOCATION_SALT, compress=True)


def reverse_geocode(lat, lon):
    """Cari alamat pin/GPS, tetapi pertahankan koordinat yang dipilih pengguna."""
    lat, lon = coordinate(lat, 90), coordinate(lon, 180)
    features = _request('geocode/reverse', {'lat': str(lat), 'lon': str(lon), 'limit': 1})
    if not features:
        raise GeoapifyError('Alamat titik ini tidak ditemukan. Pilih titik lain.', 'location_not_found', 404)
    try:
        props = features[0]['properties']
        name = props['formatted'].strip()
        country = props['country_code']
        if not name or len(name) > 255 or not isinstance(country, str):
            raise ValueError
    except (KeyError, TypeError, AttributeError, ValueError):
        raise GeoapifyError('Data alamat dari layanan lokasi tidak valid. Silakan coba lagi.') from None
    if country != 'id':
        raise GeoapifyError('Pilih lokasi di Indonesia.', 'outside_indonesia', 400)
    return {'name': name, 'lat': float(lat), 'lon': float(lon)}


def verify_location(token, name, lat, lon, user_id):
    """Cocokkan token dengan nama lokasi, koordinat, dan pengguna yang menyimpan."""
    try:
        payload = signing.loads(token, salt=LOCATION_SALT)
        return payload == {'user': user_id, 'name': name, 'lat': str(coordinate(lat, 90)),
                           'lon': str(coordinate(lon, 180)), 'country': 'id'}
    except (signing.BadSignature, ValueError, TypeError):
        return False


def calculate_route(origin_lat, origin_lon, dest_lat, dest_lon, mode):
    """Ambil rute sesuai moda dan ubah jaraknya dari meter menjadi kilometer."""
    olat, olon, dlat, dlon = validate_route_inputs(origin_lat, origin_lon, dest_lat, dest_lon, mode)
    features = _request('routing', {
        'waypoints': f'{olat},{olon}|{dlat},{dlon}', 'mode': mode, 'units': 'metric',
    })
    if not features:
        raise GeoapifyError('Rute tidak ditemukan untuk moda transportasi ini.', 'route_not_found', 404)
    try:
        props = features[0]['properties']
        if str(props['distance_units']).lower() != 'meters':
            raise ValueError
        meters, seconds = Decimal(str(props['distance'])), Decimal(str(props['time']))
        if not meters.is_finite() or not seconds.is_finite() or meters <= 0 or seconds < 0:
            raise ValueError
        distance = (meters / 1000).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
        if not Decimal('0.001') <= distance <= Decimal('99999.999'):
            raise ValueError
        geometry = features[0].get('geometry')
        if geometry is not None and (not isinstance(geometry, dict) or geometry.get('type') not in ('LineString', 'MultiLineString') or not isinstance(geometry.get('coordinates'), list)):
            raise ValueError
        return {'distance_km': distance,
                'duration_s': int(seconds.quantize(Decimal('1'), rounding=ROUND_HALF_UP)),
                'duration_minutes': float((seconds / 60).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)),
                'route_geometry': geometry}
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise GeoapifyError('Data jarak dari layanan rute tidak valid. Silakan coba lagi.') from None


def get_mode(value):
    """Kode ERD (mobil/motor/...) dan profil API lama diterima sebagai input."""
    mode = TransportMode.objects.filter(
        Q(code=value) | Q(geoapify_profile=value),
        is_active=True, geoapify_profile__in=SUPPORTED_PROFILES,
    ).first()
    if mode is None:
        raise ValueError('Moda transportasi tidak tersedia untuk routing otomatis.')
    return mode


def get_emission_factor(mode, on_date=None):
    """Pilih versi faktor emisi yang berlaku pada tanggal perjalanan."""
    on_date = on_date or today()
    factor = EmissionFactor.objects.filter(mode=mode, valid_from__lte=on_date).filter(
        Q(valid_to__isnull=True) | Q(valid_to__gte=on_date),
    ).first()
    if factor is None:
        raise ValueError('Faktor emisi belum tersedia untuk moda dan tanggal perjalanan ini.')
    return factor


def get_primary_mode(user):
    """Baca preferensi onboarding jika UserProfile Accounts sudah tersedia.

    Carbon tidak membuat/mengubah profil, dan tetap bekerja selama Accounts
    belum menyediakan model tersebut.
    """
    try:
        profile_model = apps.get_model('accounts', 'UserProfile')
    except LookupError:
        return None
    mode_id = profile_model.objects.filter(user=user).values_list('primary_mode_id', flat=True).first()
    return TransportMode.objects.filter(pk=mode_id, is_active=True, geoapify_profile__in=SUPPORTED_PROFILES).first()


def calculate_emission(distance_km, factor_value):
    """Satuan: km × kg CO2e/kendaraan-km, hasil disimpan sampai 4 desimal."""
    try:
        distance, factor = Decimal(str(distance_km)), Decimal(str(factor_value))
        if not distance.is_finite() or distance <= 0 or not factor.is_finite() or factor < 0:
            raise ValueError
        emission = (distance * factor).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
        if emission > Decimal('9999.9999'):
            raise ValueError
        return emission
    except (InvalidOperation, ValueError):
        raise ValueError('Hasil emisi tidak dapat disimpan. Periksa jarak dan faktor perjalanan.') from None
