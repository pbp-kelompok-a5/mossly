from decimal import Decimal
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from .dates import today
from .forms import TripForm
from .models import Trip
from .services import (
    GeoapifyError, calculate_emission, calculate_route, geocode_search,
    get_emission_factor, get_mode, location_token, reverse_geocode, validate_route_inputs,
)


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Silakan login terlebih dahulu.', 'code': 'authentication_required'}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


def _user_trips(user):
    return Trip.objects.filter(user=user).select_related('mode', 'emission_factor')


def _summary(trips):
    values = trips.aggregate(total_trips=Count('pk'), total_distance_km=Sum('distance_km'), total_co2e_kg=Sum('emission_kg'))
    return {key: value if value is not None else Decimal('0') for key, value in values.items()}


@login_required
@require_GET
def index(request):
    trips = _user_trips(request.user)
    return render(request, 'carbon/index.html', {'trips': trips, 'summary': _summary(trips)})


def _form_context(form):
    """Pulihkan pilihan yang valid; pakai hasil tersimpan jika rute tidak berubah."""
    locations = {}
    for prefix in ('origin', 'destination'):
        names = [f'{prefix}_label', f'{prefix}_lat', f'{prefix}_lng']
        if any(name in form.errors for name in names):
            continue
        name, lat, lng = [form[field].value() for field in names]
        if name and lat is not None and lng is not None:
            locations[prefix] = {'name': name, 'lat': float(lat), 'lon': float(lng)}
    trip = form.instance
    preview = None
    if trip.pk and not form.route_changed:
        preview = {'distance_km': float(trip.distance_km), 'co2e_kg': float(trip.emission_kg),
                   'duration_minutes': round(trip.duration_s / 60, 1) if trip.duration_s is not None else None,
                   'route_geometry': trip.route_geometry}
    return {'form': form, 'is_edit': bool(trip.pk), 'trip_state': {
        'locations': locations, 'preview': preview, 'original_mode': form.initial.get('mode'),
    }}


@login_required
@require_http_methods(['GET', 'POST'])
def trip_form(request, pk=None):
    # Kedua URL memakai alur yang sama; ID yang diisi berarti mengedit milik user.
    trip = get_object_or_404(_user_trips(request.user), pk=pk) if pk is not None else None
    form = TripForm(request.POST if request.method == 'POST' else None, instance=trip, user=request.user)
    if request.method == 'POST' and form.is_valid():
        trip = form.save(commit=False)
        trip.user = request.user
        try:
            # Edit tanggal/catatan saja mempertahankan hasil lama tanpa request API.
            if form.route_changed:
                mode = get_mode(trip.mode.code)
                factor = get_emission_factor(mode, trip.trip_date)
                route = calculate_route(trip.origin_lat, trip.origin_lng, trip.destination_lat, trip.destination_lng, mode.geoapify_profile)
                trip.distance_km = route['distance_km']
                trip.distance_source = Trip.DistanceSource.ROUTING
                trip.duration_s = route['duration_s']
                trip.route_geometry = route['route_geometry']
                trip.emission_factor = factor
                trip.emission_kg = calculate_emission(trip.distance_km, factor.kg_co2e_per_km)
            trip.full_clean()
        except (GeoapifyError, ValueError) as error:
            form.add_error(None, str(error))
        except ValidationError as error:
            form.add_error(None, ' '.join(error.messages))
        else:
            trip.save()
            return redirect('carbon:index')
    template = 'carbon/edit.html' if pk is not None else 'carbon/add.html'
    return render(request, template, _form_context(form))


@login_required
@require_POST
def delete_trip(request, pk):
    trip = get_object_or_404(Trip, pk=pk, user=request.user)
    trip.delete()
    return redirect('carbon:index')


def _api_error(error):
    return JsonResponse({'error': str(error), 'code': error.code}, status=error.status)


@api_login_required
@require_GET
def api_geocode(request):
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})
    if len(query) > 255:
        return JsonResponse({'error': 'Pencarian maksimal 255 karakter.', 'code': 'invalid_input'}, status=400)
    try:
        results = geocode_search(query)
    except GeoapifyError as error:
        return _api_error(error)
    return JsonResponse({'results': [{**loc, 'location_token': location_token(loc, request.user.pk)} for loc in results]})


@api_login_required
@require_GET
def api_reverse_geocode(request):
    try:
        location = reverse_geocode(request.GET.get('lat'), request.GET.get('lon'))
    except GeoapifyError as error:
        return _api_error(error)
    except ValueError as error:
        return JsonResponse({'error': str(error), 'code': 'invalid_input'}, status=400)
    return JsonResponse({**location, 'location_token': location_token(location, request.user.pk)})


@api_login_required
@require_GET
def api_route(request):
    try:
        mode = get_mode(request.GET.get('mode'))
        date_form = TripForm.base_fields['trip_date']
        trip_date = date_form.clean(request.GET.get('date') or today().isoformat())
        if trip_date > today():
            raise ValueError('Tanggal perjalanan tidak boleh di masa depan.')
        factor = get_emission_factor(mode, trip_date)
        coords = validate_route_inputs(*(request.GET.get(name) for name in ('olat', 'olon', 'dlat', 'dlon')), mode.geoapify_profile)
        route = calculate_route(*coords, mode.geoapify_profile)
        emission = calculate_emission(route['distance_km'], factor.kg_co2e_per_km)
    except GeoapifyError as error:
        return _api_error(error)
    except (ValueError, ValidationError) as error:
        message = 'Tanggal perjalanan tidak valid.' if isinstance(error, ValidationError) else str(error)
        return JsonResponse({'error': message, 'code': 'invalid_input'}, status=400)
    return JsonResponse({'distance_km': float(route['distance_km']), 'duration_minutes': route['duration_minutes'],
                         'co2e_kg': float(emission), 'emission_kg': float(emission), 'emission_metric': 'CO2e',
                         'mode': mode.geoapify_profile, 'mode_code': mode.code,
                         'route_geometry': route['route_geometry'],
                         'emission_factor_id': factor.pk, 'factor_version': factor.version})


@api_login_required
@require_GET
def api_history(request):
    trips = _user_trips(request.user)
    rows = [{
        'id': trip.pk, 'date': trip.trip_date.isoformat(), 'traveled_at': trip.traveled_at.isoformat(),
        'origin': trip.origin_label, 'destination': trip.destination_label,
        'origin_lat': float(trip.origin_lat), 'origin_lng': float(trip.origin_lng),
        'destination_lat': float(trip.destination_lat), 'destination_lng': float(trip.destination_lng),
        'mode_id': trip.mode_id, 'mode': trip.mode.geoapify_profile, 'mode_code': trip.mode.code, 'mode_display': trip.mode.name,
        'distance_km': float(trip.distance_km), 'distance_source': trip.distance_source,
        'duration_s': trip.duration_s, 'route_geometry': trip.route_geometry,
        'co2e_kg': float(trip.emission_kg), 'emission_kg': float(trip.emission_kg), 'note': trip.note,
        'emission_factor_id': trip.emission_factor_id,
        'emission_factor': float(trip.emission_factor.kg_co2e_per_km),
        'emission_factor_version': trip.emission_factor.version, 'emission_factor_source': trip.emission_factor.source,
    } for trip in trips]
    totals = _summary(trips)
    return JsonResponse({'trips': rows, 'emission_metric': 'CO2e', 'summary': {
        'total_trips': totals['total_trips'], 'total_distance_km': float(totals['total_distance_km']),
        'total_co2e_kg': float(totals['total_co2e_kg']),
    }})
