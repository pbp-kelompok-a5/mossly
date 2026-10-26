import json
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseForbidden
from django.db.models import Sum, Count

from .models import Trip
from .forms import TripForm
from .services import geocode_search, calculate_route, calculate_co2


# ──────────────────────────────────────────────────────────
# CRUD Views
# ──────────────────────────────────────────────────────────

@login_required
def index(request):
    """READ — Halaman riwayat perjalanan pengguna."""
    trips = Trip.objects.filter(user=request.user)

    # Ringkasan
    summary = trips.aggregate(
        total_trips=Count('id'),
        total_distance=Sum('distance_km'),
        total_co2=Sum('co2_emission_kg'),
    )
    summary['total_distance'] = summary['total_distance'] or Decimal('0')
    summary['total_co2'] = summary['total_co2'] or Decimal('0')

    context = {
        'trips': trips,
        'summary': summary,
    }
    return render(request, 'carbon/index.html', context)


@login_required
def add_trip(request):
    """CREATE — Form tambah perjalanan baru."""
    if request.method == 'POST':
        form = TripForm(request.POST)
        if form.is_valid():
            trip = form.save(commit=False)
            trip.user = request.user
            trip.save()
            return redirect('carbon:index')
    else:
        form = TripForm()

    return render(request, 'carbon/add.html', {'form': form, 'is_edit': False})


@login_required
def edit_trip(request, pk):
    """UPDATE — Form edit perjalanan yang sudah ada."""
    trip = get_object_or_404(Trip, pk=pk)

    # Otorisasi: hanya pemilik yang bisa edit
    if trip.user != request.user:
        return HttpResponseForbidden('Anda tidak memiliki akses untuk mengedit perjalanan ini.')

    if request.method == 'POST':
        form = TripForm(request.POST, instance=trip)
        if form.is_valid():
            form.save()
            return redirect('carbon:index')
    else:
        form = TripForm(instance=trip)

    # Kirim data existing ke JS untuk pre-fill autocomplete
    trip_data = {
        'origin_name': trip.origin_name,
        'origin_lat': str(trip.origin_lat),
        'origin_lon': str(trip.origin_lon),
        'destination_name': trip.destination_name,
        'destination_lat': str(trip.destination_lat),
        'destination_lon': str(trip.destination_lon),
        'transport_mode': trip.transport_mode,
        'distance_km': str(trip.distance_km),
        'co2_emission_kg': str(trip.co2_emission_kg),
    }

    return render(request, 'carbon/edit.html', {
        'form': form,
        'trip': trip,
        'trip_data_json': json.dumps(trip_data),
        'is_edit': True,
    })


@login_required
def delete_trip(request, pk):
    """DELETE — Hapus perjalanan."""
    trip = get_object_or_404(Trip, pk=pk)

    # Otorisasi: hanya pemilik yang bisa hapus
    if trip.user != request.user:
        return HttpResponseForbidden('Anda tidak memiliki akses untuk menghapus perjalanan ini.')

    if request.method == 'POST':
        trip.delete()
        return redirect('carbon:index')

    # Jika bukan POST, redirect ke index
    return redirect('carbon:index')


# ──────────────────────────────────────────────────────────
# API Endpoints (JSON)
# ──────────────────────────────────────────────────────────

@login_required
def api_geocode(request):
    """API Proxy — Search lokasi via Geoapify Geocoding."""
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse({'results': []})

    results = geocode_search(query)
    return JsonResponse({'results': results})


@login_required
def api_route(request):
    """API Proxy — Hitung jarak via Geoapify Routing."""
    try:
        olat = float(request.GET.get('olat', 0))
        olon = float(request.GET.get('olon', 0))
        dlat = float(request.GET.get('dlat', 0))
        dlon = float(request.GET.get('dlon', 0))
        mode = request.GET.get('mode', 'drive')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Parameter tidak valid.'}, status=400)

    # Validasi mode
    valid_modes = ['drive', 'motorcycle', 'bicycle', 'walk']
    if mode not in valid_modes:
        return JsonResponse({'error': 'Moda transportasi tidak valid.'}, status=400)

    route = calculate_route(olat, olon, dlat, dlon, mode)
    if route is None:
        return JsonResponse({
            'error': 'Rute tidak ditemukan untuk moda transportasi ini.'
        }, status=404)

    co2 = calculate_co2(route['distance_km'], mode)

    return JsonResponse({
        'distance_km': float(route['distance_km']),
        'duration_minutes': route['duration_minutes'],
        'co2_kg': float(co2),
        'mode': mode,
    })


@login_required
def api_history(request):
    """API JSON — Riwayat perjalanan untuk Dashboard (Fildza)."""
    trips = Trip.objects.filter(user=request.user)

    trips_data = []
    for trip in trips:
        trips_data.append({
            'id': trip.id,
            'date': trip.trip_date.isoformat(),
            'origin': trip.origin_name,
            'destination': trip.destination_name,
            'mode': trip.transport_mode,
            'mode_display': trip.get_transport_mode_display(),
            'distance_km': float(trip.distance_km),
            'co2_kg': float(trip.co2_emission_kg),
            'note': trip.note,
        })

    summary = trips.aggregate(
        total_trips=Count('id'),
        total_distance_km=Sum('distance_km'),
        total_co2_kg=Sum('co2_emission_kg'),
    )

    return JsonResponse({
        'trips': trips_data,
        'summary': {
            'total_trips': summary['total_trips'] or 0,
            'total_distance_km': float(summary['total_distance_km'] or 0),
            'total_co2_kg': float(summary['total_co2_kg'] or 0),
        },
    })