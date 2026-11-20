"""Dua endpoint DRF Carbon untuk Checkpoint 1, tanpa mengubah API web lama."""

from django.core.paginator import EmptyPage, Paginator
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from .models import TransportMode
from .serializers import (
    TransportModeSerializer, TripHistoryQuerySerializer, TripHistorySerializer,
)
from .views import _filter_trips, _summary, _user_trips


SORT_ORDERS = {
    'newest': ('-traveled_at', '-pk'),
    'oldest': ('traveled_at', 'pk'),
    'distance': ('-distance_km', '-traveled_at', '-pk'),
    'emission': ('-emission_kg', '-traveled_at', '-pk'),
}
PAGE_SIZE = 20


@api_view(['GET'])
def mode_list(request):
    modes = TransportMode.objects.filter(is_active=True).order_by('id')
    return Response({'modes': TransportModeSerializer(modes, many=True).data})


@api_view(['GET'])
def trip_list(request):
    query = TripHistoryQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    filters = query.validated_data

    trips = _filter_trips(_user_trips(request.user), filters['mode'])
    trips = trips.defer('route_geometry', 'legacy_calculation')
    # Gunakan perhitungan yang sama dengan halaman web, sebelum pagination.
    totals = _summary(trips)
    paginator = Paginator(trips.order_by(*SORT_ORDERS[filters['sort']]), PAGE_SIZE)
    try:
        page = paginator.page(filters['page'])
    except EmptyPage as error:
        raise NotFound('Halaman riwayat tidak ditemukan.') from error

    return Response({
        'trips': TripHistorySerializer(page.object_list, many=True).data,
        'summary': {
            'total_trips': totals['total_trips'],
            'total_distance_km': float(totals['total_distance_km']),
            'total_co2e_kg': float(totals['total_co2e_kg']),
        },
        'pagination': {
            'page': page.number,
            'pages': paginator.num_pages,
            'per_page': PAGE_SIZE,
            'count': paginator.count,
            'previous_page': page.previous_page_number() if page.has_previous() else None,
            'next_page': page.next_page_number() if page.has_next() else None,
        },
        'filters': {'mode': filters['mode'], 'sort': filters['sort']},
        'emission_metric': 'CO2e',
    })
