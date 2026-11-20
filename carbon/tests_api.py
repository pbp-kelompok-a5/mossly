"""Periksa kontrak, isolasi pemilik, filter, dan pagination Carbon CP1."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .dates import at_start_of_day, today
from .models import EmissionFactor, TransportMode, Trip


class CarbonCheckpointOneTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user(username='carbon_owner')
        cls.other = get_user_model().objects.create_user(username='carbon_other')
        cls.car, _ = TransportMode.objects.get_or_create(code='mobil', defaults={'name': 'Mobil', 'geoapify_profile': 'drive'})
        cls.bike, _ = TransportMode.objects.get_or_create(code='sepeda', defaults={'name': 'Sepeda', 'geoapify_profile': 'bicycle'})
        cls.inactive = TransportMode.objects.create(code='lama', name='Moda lama', is_active=False)
        cls.factors = {}
        for mode in (cls.car, cls.bike, cls.inactive):
            cls.factors[mode.pk] = EmissionFactor.objects.filter(mode=mode).first() or EmissionFactor.objects.create(
                mode=mode, kg_co2e_per_km=Decimal('0.1'), source='Test fixture',
                version='test-cp1', valid_from=today() - timedelta(days=365),
            )

    def setUp(self):
        self.client.force_authenticate(user=self.owner)

    def trip(self, *, user=None, mode=None, days=0, distance='2.500', emission='0.2500'):
        mode = mode or self.car
        return Trip.objects.create(
            user=user or self.owner, mode=mode, emission_factor=self.factors[mode.pk],
            origin_label='Universitas Indonesia', destination_label='Stasiun Pondok Cina',
            origin_lat='-6.36', origin_lng='106.83', destination_lat='-6.37', destination_lng='106.83',
            distance_km=Decimal(distance), emission_kg=Decimal(emission),
            traveled_at=at_start_of_day(today() - timedelta(days=days)),
            route_geometry={'type': 'LineString', 'coordinates': [[106.83, -6.36], [106.83, -6.37]]},
        )

    def test_modes_only_returns_active_modes(self):
        response = self.client.get('/api/v1/carbon/modes/')
        self.assertEqual(response.status_code, 200)
        codes = [m['code'] for m in response.data['modes']]
        self.assertIn('mobil', codes)
        self.assertIn('sepeda', codes)
        self.assertNotIn('lama', codes)

    def test_both_endpoints_require_login(self):
        self.client.force_authenticate(user=None)
        for endpoint in ('modes', 'trips'):
            with self.subTest(endpoint=endpoint):
                response = self.client.get(f'/api/v1/carbon/{endpoint}/')
                self.assertEqual(response.status_code, 401)

    def test_token_header_authenticates_real_request(self):
        self.client.force_authenticate(user=None)
        token = Token.objects.create(user=self.owner)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.assertEqual(self.client.get('/api/v1/carbon/trips/').status_code, 200)

    def test_invalid_token_is_rejected(self):
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid-token')
        self.assertEqual(self.client.get('/api/v1/carbon/trips/').status_code, 401)

    def test_list_never_leaks_other_users_trips_or_totals(self):
        mine = self.trip()
        self.trip(user=self.other, distance='900.000', emission='90.0000')
        response = self.client.get('/api/v1/carbon/trips/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([t['id'] for t in response.data['trips']], [mine.pk])
        self.assertEqual(response.data['summary'], {
            'total_trips': 1, 'total_distance_km': 2.5, 'total_co2e_kg': 0.25,
        })

    def test_empty_history_has_numeric_zero_summary(self):
        response = self.client.get('/api/v1/carbon/trips/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['trips'], [])
        self.assertEqual(response.data['summary']['total_trips'], 0)
        self.assertEqual(response.data['summary']['total_distance_km'], 0)
        self.assertEqual(response.data['pagination']['pages'], 1)
        self.assertIsNone(response.data['pagination']['next_page'])

    def test_mode_filter_applies_to_rows_and_summary(self):
        self.trip()
        selected = self.trip(mode=self.bike, emission='0')
        response = self.client.get('/api/v1/carbon/trips/', {'mode': 'sepeda'})
        self.assertEqual([t['id'] for t in response.data['trips']], [selected.pk])
        self.assertEqual(response.data['summary']['total_co2e_kg'], 0)
        self.assertEqual(response.data['summary']['total_trips'], 1)

    def test_inactive_mode_history_remains_readable(self):
        trip = self.trip(mode=self.inactive)
        response = self.client.get('/api/v1/carbon/trips/', {'mode': 'lama'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['trips'][0]['id'], trip.pk)

    def test_each_sort_order(self):
        old = self.trip(days=3, distance='9', emission='0.1')
        new = self.trip(days=0, distance='1', emission='0.9')
        for sort, ids in (
            ('newest', [new.pk, old.pk]), ('oldest', [old.pk, new.pk]),
            ('distance', [old.pk, new.pk]), ('emission', [new.pk, old.pk]),
        ):
            with self.subTest(sort=sort):
                response = self.client.get('/api/v1/carbon/trips/', {'sort': sort})
                self.assertEqual([t['id'] for t in response.data['trips']], ids)

    def test_pagination_does_not_limit_summary(self):
        for _ in range(21):
            self.trip()
        first = self.client.get('/api/v1/carbon/trips/')
        second = self.client.get('/api/v1/carbon/trips/', {'page': 2})
        self.assertEqual(len(first.data['trips']), 20)
        self.assertEqual(len(second.data['trips']), 1)
        self.assertEqual(first.data['summary'], second.data['summary'])
        self.assertEqual(first.data['summary']['total_trips'], 21)
        self.assertEqual(first.data['summary']['total_distance_km'], 52.5)
        self.assertEqual(first.data['pagination']['next_page'], 2)
        self.assertEqual(second.data['pagination']['previous_page'], 1)
        self.assertTrue(set(t['id'] for t in first.data['trips']).isdisjoint(
            t['id'] for t in second.data['trips']))

    def test_invalid_query_parameters_return_field_errors(self):
        for query, field in (
            ({'sort': 'invalid'}, 'sort'), ({'mode': 'unknown'}, 'mode'),
            ({'page': 'abc'}, 'page'), ({'page': 0}, 'page'), ({'page': -1}, 'page'),
        ):
            with self.subTest(query=query):
                response = self.client.get('/api/v1/carbon/trips/', query)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_missing_page_and_out_of_scope_detail_return_404(self):
        other_trip = self.trip(user=self.other)
        self.assertEqual(self.client.get('/api/v1/carbon/trips/?page=2').status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/carbon/trips/{other_trip.pk}/').status_code, 404)

    def test_serialized_numbers_are_numbers_and_geometry_is_absent(self):
        self.trip(mode=self.bike, emission='0')
        response = self.client.get('/api/v1/carbon/trips/')
        trip = response.json()['trips'][0]
        self.assertIsInstance(trip['distance_km'], (int, float))
        self.assertIsInstance(trip['emission_kg'], (int, float))
        self.assertEqual(trip['date'], today().isoformat())
        self.assertNotIn('route_geometry', trip)
        self.assertNotIn('legacy_calculation', trip)

    def test_checkpoint_one_endpoints_are_read_only(self):
        for endpoint in ('modes', 'trips'):
            self.assertEqual(self.client.post(f'/api/v1/carbon/{endpoint}/', {}).status_code, 405)
