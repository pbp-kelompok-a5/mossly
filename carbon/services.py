"""
carbon/services.py
Helper functions: Geoapify API calls & CO₂ emission calculation.
"""

import os
import requests
from decimal import Decimal

# ──────────────────────────────────────────────────────────
# Faktor Emisi CO₂ (kg CO₂ per km)
#
# Sumber  : UK DESNZ / BEIS Greenhouse Gas Conversion Factors 2023
# Satuan  : kilogram CO₂ per kilometer
# Catatan : Angka disesuaikan dengan rata-rata kendaraan Indonesia.
#           Sepeda & jalan kaki dianggap zero emission.
# ──────────────────────────────────────────────────────────
EMISSION_FACTORS = {
    'drive':      Decimal('0.171'),   # Mobil (BBM rata-rata)
    'motorcycle': Decimal('0.103'),   # Motor
    'bicycle':    Decimal('0.000'),   # Sepeda
    'walk':       Decimal('0.000'),   # Jalan kaki
}


def get_api_key():
    """Ambil Geoapify API key dari environment variable."""
    return os.getenv('GEOAPIFY_API_KEY', '')


def geocode_search(query):
    """
    Cari lokasi berdasarkan teks (nama tempat / alamat).
    Menggunakan Geoapify Geocoding API, dibatasi ke Indonesia.

    Returns: list of dict {name, lat, lon} atau [] jika gagal.
    """
    api_key = get_api_key()
    if not api_key:
        return []

    url = 'https://api.geoapify.com/v1/geocode/search'
    params = {
        'text': query,
        'filter': 'countrycode:id',
        'limit': 5,
        'apiKey': api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for feature in data.get('features', []):
            props = feature.get('properties', {})
            results.append({
                'name': props.get('formatted', ''),
                'lat': props.get('lat'),
                'lon': props.get('lon'),
            })
        return results

    except (requests.RequestException, ValueError, KeyError):
        return []


def calculate_route(origin_lat, origin_lon, dest_lat, dest_lon, mode):
    """
    Hitung jarak & durasi rute antara dua titik koordinat.
    Menggunakan Geoapify Routing API.

    Returns: dict {distance_km, duration_minutes} atau None jika gagal.
    """
    api_key = get_api_key()
    if not api_key:
        return None

    url = 'https://api.geoapify.com/v1/routing'
    params = {
        'waypoints': f'{origin_lat},{origin_lon}|{dest_lat},{dest_lon}',
        'mode': mode,
        'units': 'metric',
        'apiKey': api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Ambil data dari leg pertama
        features = data.get('features', [])
        if not features:
            return None

        props = features[0].get('properties', {})
        legs = props.get('legs', [])
        if not legs:
            return None

        distance_meters = legs[0].get('distance', 0)
        duration_seconds = legs[0].get('time', 0)

        distance_km = round(Decimal(str(distance_meters)) / Decimal('1000'), 3)
        duration_minutes = round(duration_seconds / 60, 1)

        return {
            'distance_km': distance_km,
            'duration_minutes': duration_minutes,
        }

    except (requests.RequestException, ValueError, KeyError, IndexError):
        return None


def calculate_co2(distance_km, mode):
    """
    Hitung estimasi emisi CO₂ berdasarkan jarak dan moda transportasi.

    Args:
        distance_km: Jarak dalam kilometer (Decimal atau float).
        mode: Moda transportasi ('drive', 'motorcycle', 'bicycle', 'walk').

    Returns:
        Decimal — emisi dalam kg CO₂, dibulatkan 4 desimal.
    """
    factor = EMISSION_FACTORS.get(mode, Decimal('0'))
    emission = Decimal(str(distance_km)) * factor
    return round(emission, 4)
