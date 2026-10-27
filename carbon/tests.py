from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock, patch

import requests
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models.deletion import ProtectedError
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from .dates import at_start_of_day, today
from .models import EmissionFactor, TransportMode, Trip
from .services import (
    GeoapifyError, calculate_emission, calculate_route, coordinate,
    geocode_search, location_token, verify_location,
    get_emission_factor,
)

ORIGIN = {'name': 'Universitas Indonesia, Depok', 'lat': -6.3616, 'lon': 106.8302}
DESTINATION = {'name': 'Stasiun Depok Baru', 'lat': -6.391, 'lon': 106.8217}
ROUTE = {'distance_km': Decimal('12.450'), 'duration_minutes': 25.0, 'duration_s': 1500, 'route_geometry': None}


def route_response(**overrides):
    return {'features': [{'properties': {'distance': 12450, 'time': 1500, 'distance_units': 'Meters', **overrides}}]}


class ServiceTests(SimpleTestCase):
    def response(self, data, status=200):
        result = Mock(status_code=status)
        result.json.return_value = data
        if status >= 400:
            result.raise_for_status.side_effect = requests.HTTPError('URL may contain secret')
        return result

    def test_factors_and_rounding(self):
        for factor, result in [('0.166638588', '2.0747'), ('0.113674264', '1.4152'), ('0', '0.0000')]:
            self.assertEqual(calculate_emission(Decimal('12.450'), Decimal(factor)), Decimal(result))
        for distance, factor in [('NaN', '.1'), ('Infinity', '.1'), (-1, '.1'), (0, '0'), (1000000, '.1'), (2, '-.1'), (2, 'NaN')]:
            with self.subTest(distance=distance, factor=factor), self.assertRaises(ValueError):
                calculate_emission(distance, factor)

    def test_coordinate_zero_and_invalid_values(self):
        self.assertEqual(coordinate(0, 90), Decimal('0.000000'))
        for value in (None, '', 'NaN', 'Infinity', '-Infinity', 91, -91):
            with self.subTest(value=value), self.assertRaises(ValueError):
                coordinate(value, 90)

    @patch('carbon.services.requests.get')
    @patch.dict('os.environ', {'GEOAPIFY_API_KEY': 'test-secret'})
    def test_routing_uses_total_and_metric_units(self, get):
        data = route_response()
        data['features'][0]['properties']['legs'] = [{'distance': 5, 'time': 2}]
        get.return_value = self.response(data)
        self.assertEqual(calculate_route(-6, 106, -7, 107, 'motorcycle'), ROUTE)
        self.assertEqual(get.call_args.kwargs['params'], {'waypoints': '-6.000000,106.000000|-7.000000,107.000000', 'mode': 'motorcycle', 'units': 'metric', 'apiKey': 'test-secret'})
        self.assertEqual(get.call_args.kwargs['timeout'], 10)

    @patch('carbon.services.requests.get')
    @patch.dict('os.environ', {'GEOAPIFY_API_KEY': 'test-secret'})
    def test_invalid_provider_results(self, get):
        malformed = [None, [], {}, {'features': {}}, {'features': [None]}, route_response(distance='NaN'),
                     route_response(distance=-1), route_response(time=-1), route_response(distance_units='Miles'),
                     route_response(distance=10**50), route_response(time='Infinity')]
        malformed.append({'features': [{'properties': {'distance_units': 'Meters', 'time': 100}}]})
        for data in malformed:
            with self.subTest(data=data):
                get.return_value = self.response(data)
                with self.assertRaises(GeoapifyError) as error:
                    calculate_route(-6, 106, -7, 107, 'drive')
                self.assertEqual(error.exception.status, 502)

    @patch('carbon.services.requests.get')
    @patch.dict('os.environ', {'GEOAPIFY_API_KEY': 'test-secret'})
    def test_empty_route_and_provider_status(self, get):
        cases = [(200, {'features': []}, 404), (429, {}, 503), (403, {}, 503), (401, {}, 503), (500, {}, 502),
                 (400, {'message': 'Route could not be found'}, 404)]
        for status, data, expected in cases:
            with self.subTest(status=status):
                get.return_value = self.response(data, status)
                with self.assertRaises(GeoapifyError) as error:
                    calculate_route(-6, 106, -7, 107, 'drive')
                self.assertEqual(error.exception.status, expected)
                self.assertNotIn('test-secret', str(error.exception))

    @patch('carbon.services.requests.get')
    @patch.dict('os.environ', {'GEOAPIFY_API_KEY': 'test-secret'})
    def test_network_errors_and_invalid_json(self, get):
        for exception, expected in [(requests.Timeout(), 504), (requests.ConnectionError('test-secret'), 502)]:
            get.side_effect = exception
            with self.assertRaises(GeoapifyError) as error:
                geocode_search('Depok')
            self.assertEqual(error.exception.status, expected)
            self.assertNotIn('test-secret', str(error.exception))
        get.side_effect = None
        get.return_value = self.response(None)
        get.return_value.json.side_effect = ValueError('bad JSON')
        with self.assertRaises(GeoapifyError):
            geocode_search('Depok')

    @patch('carbon.services.requests.get')
    @patch.dict('os.environ', {'GEOAPIFY_API_KEY': ''})
    def test_missing_key_does_not_call_provider(self, get):
        with self.assertRaises(GeoapifyError) as error:
            geocode_search('Depok')
        self.assertEqual(error.exception.status, 503)
        get.assert_not_called()

    @patch('carbon.services.requests.get')
    @patch.dict('os.environ', {'GEOAPIFY_API_KEY': 'test-secret'})
    def test_geocode_filter_and_selection_token(self, get):
        get.return_value = self.response({'features': [
            {'properties': {'formatted': ORIGIN['name'], 'lat': ORIGIN['lat'], 'lon': ORIGIN['lon'], 'country_code': 'id'}},
            {'properties': {'formatted': 'Other country', 'lat': 1, 'lon': 2, 'country_code': 'sg'}},
        ]})
        self.assertEqual(geocode_search('Universitas Indonesia'), [ORIGIN])
        self.assertEqual(get.call_args.kwargs['params']['filter'], 'countrycode:id')
        token = location_token(ORIGIN, 1)
        self.assertTrue(verify_location(token, ORIGIN['name'], ORIGIN['lat'], ORIGIN['lon'], 1))
        self.assertFalse(verify_location(token, ORIGIN['name'], ORIGIN['lat'], ORIGIN['lon'], 2))
        self.assertFalse(verify_location(token + 'x', ORIGIN['name'], ORIGIN['lat'], ORIGIN['lon'], 1))

    def test_jakarta_day_boundary(self):
        with patch('carbon.dates.timezone.now', return_value=datetime(2026, 10, 25, 18, tzinfo=timezone.utc)):
            self.assertEqual(today(), date(2026, 10, 26))


class CarbonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('callysta')
        cls.other = get_user_model().objects.create_user('other')

    def setUp(self):
        self.client.force_login(self.user)

    def payload(self, **overrides):
        data = {'origin_label': ORIGIN['name'], 'origin_lat': str(ORIGIN['lat']), 'origin_lng': str(ORIGIN['lon']),
                'destination_label': DESTINATION['name'], 'destination_lat': str(DESTINATION['lat']), 'destination_lng': str(DESTINATION['lon']),
                'mode': 'mobil', 'trip_date': today().isoformat(), 'note': '',
                'origin_token': location_token(ORIGIN, self.user.pk), 'destination_token': location_token(DESTINATION, self.user.pk)}
        return {**data, **overrides}

    def trip(self, **overrides):
        data = self.payload()
        data = {key: value for key, value in data.items() if not key.endswith('_token')}
        chosen_date = overrides.pop('trip_date', data.pop('trip_date'))
        selected = overrides.pop('mode', data.pop('mode'))
        mode = selected if isinstance(selected, TransportMode) else TransportMode.objects.get(code=selected)
        data.update(user=self.user, mode=mode, emission_factor=EmissionFactor.objects.filter(mode=mode).first(),
                    traveled_at=at_start_of_day(chosen_date if isinstance(chosen_date, date) else date.fromisoformat(chosen_date)),
                    distance_km=Decimal('12.450'), emission_kg=Decimal('2.0747'))
        return Trip.objects.create(**{**data, **overrides})

    @patch('carbon.views.calculate_route', return_value=ROUTE)
    def test_create_recalculates_and_ignores_forged_output(self, route):
        response = self.client.post(reverse('carbon:add_trip'), self.payload(distance_km='999', emission_kg='0', user=self.other.pk, emission_factor='0'))
        self.assertRedirects(response, reverse('carbon:index'))
        trip = Trip.objects.get()
        self.assertEqual(trip.user, self.user)
        self.assertEqual(trip.distance_km, Decimal('12.450'))
        self.assertEqual(trip.emission_kg, Decimal('2.0747'))
        self.assertEqual(trip.emission_factor.version, 'DESNZ-2023-v1.1')
        self.assertEqual(trip.emission_factor.kg_co2e_per_km, Decimal('0.166638588'))
        route.assert_called_once()

    @patch('carbon.views.calculate_route', return_value=ROUTE)
    def test_all_modes_can_be_created(self, route):
        for mode, emission in [('mobil', '2.0747'), ('motor', '1.4152'), ('sepeda', '0'), ('jalan', '0')]:
            with self.subTest(mode=mode):
                response = self.client.post(reverse('carbon:add_trip'), self.payload(mode=mode))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(Trip.objects.latest('pk').emission_kg, Decimal(emission))

    @patch('carbon.views.calculate_route')
    def test_invalid_forms_do_not_call_provider_or_create_records(self, route):
        cases = [dict(origin_token=''), dict(origin_label='Forged'), dict(origin_lat='NaN'), dict(origin_lng='181'),
                 dict(mode='train'), dict(note='x' * 201), dict(origin_label='x' * 256),
                 dict(trip_date=(today() + timedelta(days=1)).isoformat()), dict(destination_lat=''),
                 dict(origin_token=location_token(ORIGIN, self.other.pk))]
        for values in cases:
            with self.subTest(values=values):
                response = self.client.post(reverse('carbon:add_trip'), self.payload(**values))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
        route.assert_not_called()
        self.assertFalse(Trip.objects.exists())

    @patch('carbon.views.calculate_route', return_value=ROUTE)
    def test_zero_coordinate_is_not_treated_as_missing(self, route):
        loc = {**ORIGIN, 'lat': 0}
        response = self.client.post(reverse('carbon:add_trip'), self.payload(origin_lat='0', origin_token=location_token(loc, self.user.pk)))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Trip.objects.get().origin_lat, 0)

    @patch('carbon.views.calculate_route')
    def test_identical_points_are_rejected(self, route):
        response = self.client.post(reverse('carbon:add_trip'), self.payload(destination_label=ORIGIN['name'], destination_lat=str(ORIGIN['lat']), destination_lng=str(ORIGIN['lon']), destination_token=location_token(ORIGIN, self.user.pk)))
        self.assertContains(response, 'Asal dan tujuan harus berbeda.')
        route.assert_not_called()

    @patch('carbon.views.calculate_route', side_effect=GeoapifyError('Layanan sedang sibuk.'))
    def test_failed_create_preserves_input(self, route):
        response = self.client.post(reverse('carbon:add_trip'), self.payload(note='Tetap ada'))
        self.assertContains(response, 'Layanan sedang sibuk.')
        self.assertContains(response, 'Tetap ada')
        self.assertFalse(Trip.objects.exists())

    @patch('carbon.views.calculate_route')
    def test_note_and_date_update_keeps_old_results_and_factors(self, route):
        factor = EmissionFactor.objects.create(mode=TransportMode.objects.get(code='mobil'), kg_co2e_per_km='.2',
                                                source='Test factor', version='old-version', valid_from=today())
        trip = self.trip(emission_factor=factor)
        response = self.client.post(reverse('carbon:edit_trip', args=[trip.pk]), self.payload(note='Diperbaiki', trip_date=(today() - timedelta(days=1)).isoformat(), origin_token='', destination_token='', emission_kg='0'))
        self.assertEqual(response.status_code, 302)
        trip.refresh_from_db()
        self.assertEqual(trip.note, 'Diperbaiki')
        self.assertEqual(trip.emission_kg, Decimal('2.0747'))
        self.assertEqual(trip.emission_factor.version, 'old-version')
        route.assert_not_called()

    @patch('carbon.views.calculate_route', return_value={'distance_km': Decimal('3.500'), 'duration_minutes': 8.0, 'duration_s': 480, 'route_geometry': None})
    def test_mode_and_location_updates_recalculate(self, route):
        trip = self.trip()
        url = reverse('carbon:edit_trip', args=[trip.pk])
        response = self.client.post(url, self.payload(mode='motor'))
        self.assertEqual(response.status_code, 302)
        trip.refresh_from_db()
        self.assertEqual(trip.distance_km, Decimal('3.500'))
        self.assertEqual(trip.emission_kg, Decimal('.3979'))
        loc = {'name': 'Lokasi baru', 'lat': -6.3, 'lon': 106.8}
        response = self.client.post(url, self.payload(origin_label=loc['name'], origin_lat=str(loc['lat']), origin_lng=str(loc['lon']), origin_token=location_token(loc, self.user.pk)))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(route.call_count, 2)

    @patch('carbon.views.calculate_route', side_effect=GeoapifyError('Rute gagal'))
    def test_failed_update_preserves_database_record(self, route):
        trip = self.trip()
        response = self.client.post(reverse('carbon:edit_trip', args=[trip.pk]), self.payload(mode='motor', note='Tidak boleh tersimpan'))
        self.assertContains(response, 'Rute gagal')
        trip.refresh_from_db()
        self.assertEqual(trip.mode.code, 'mobil')
        self.assertEqual(trip.note, '')

    def test_owner_authorization_and_missing_id(self):
        trip = self.trip(user=self.other)
        for name in ('edit_trip', 'delete_trip'):
            for pk, expected in [(trip.pk, 404), (999999, 404)]:
                response = self.client.post(reverse(f'carbon:{name}', args=[pk]), self.payload())
                self.assertEqual(response.status_code, expected)
        self.assertEqual(self.client.get(reverse('carbon:edit_trip', args=[trip.pk])).status_code, 404)
        self.assertTrue(Trip.objects.filter(pk=trip.pk).exists())

    def test_delete_requires_post_and_csrf(self):
        trip = self.trip()
        url = reverse('carbon:delete_trip', args=[trip.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(url).status_code, 403)
        csrf_client.get(reverse('carbon:index'))
        token = csrf_client.cookies['csrftoken'].value
        self.assertEqual(csrf_client.post(url, {'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertFalse(Trip.objects.exists())

    def test_history_is_private_and_totals_match(self):
        older = self.trip(trip_date=today() - timedelta(days=1))
        newer = self.trip(mode='jalan', distance_km=Decimal('1.500'), emission_kg=0)
        self.trip(user=self.other, distance_km=999)
        data = self.client.get(reverse('carbon:api_history')).json()
        self.assertEqual([row['id'] for row in data['trips']], [newer.pk, older.pk])
        self.assertEqual(data['summary'], {'total_trips': 2, 'total_distance_km': 13.95, 'total_co2e_kg': 2.0747})
        response = self.client.get(reverse('carbon:index'))
        self.assertEqual(list(response.context['trips']), [newer, older])

    def test_empty_history_and_summary(self):
        data = self.client.get(reverse('carbon:api_history')).json()
        self.assertEqual(data, {'trips': [], 'emission_metric': 'CO2e', 'summary': {'total_trips': 0, 'total_distance_km': 0.0, 'total_co2e_kg': 0.0}})
        self.assertContains(self.client.get(reverse('carbon:index')), 'Belum ada perjalanan')

    def test_templates_render_script_and_prefill_edit(self):
        trip = self.trip()
        trip.refresh_from_db()
        add = self.client.get(reverse('carbon:add_trip'))
        self.assertContains(add, 'carbon/trip.js')
        self.assertContains(add, 'Powered by Geoapify')
        self.assertContains(add, 'carbon-trip-state')
        self.assertContains(add, 'css/tokens.css', count=1)
        self.assertContains(add, 'css/components.css', count=1)
        self.assertNotContains(add, 'style=')
        html = add.content.decode()
        self.assertLess(html.index('css/tokens.css'), html.index('css/global.css'))
        self.assertLess(html.index('css/global.css'), html.index('css/components.css'))
        self.assertEqual(add.context['form'].fields['origin_label'].widget.attrs['class'], 'input')
        self.assertEqual(len(list(add.context['form']['mode'])), 4)
        edit = self.client.get(reverse('carbon:edit_trip', args=[trip.pk]))
        self.assertEqual(edit.status_code, 200)
        self.assertContains(edit, 'Simpan Perubahan')
        self.assertEqual(edit.context['trip_state']['preview']['distance_km'], 12.45)
        self.assertEqual(edit.context['form']['trip_date'].value(), trip.trip_date)

    @patch('carbon.views.calculate_route')
    def test_invalid_note_edit_keeps_original_preview_without_new_request(self, route):
        trip = self.trip()
        response = self.client.post(reverse('carbon:edit_trip', args=[trip.pk]), self.payload(note='x' * 201, origin_token='', destination_token=''))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'aria-invalid="true"')
        self.assertContains(response, 'class="field-error"')
        self.assertEqual(response.context['trip_state']['preview']['distance_km'], 12.45)
        self.assertEqual(len(response.context['trip_state']['locations']), 2)
        route.assert_not_called()

    def test_authentication(self):
        self.client.logout()
        for name in ('index', 'add_trip'):
            self.assertEqual(self.client.get(reverse(f'carbon:{name}')).status_code, 302)
        for name in ('api_geocode', 'api_route', 'api_history'):
            response = self.client.get(reverse(f'carbon:{name}'))
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['code'], 'authentication_required')

    def test_method_restrictions(self):
        for name in ('index', 'api_history', 'api_geocode', 'api_route'):
            self.assertEqual(self.client.post(reverse(f'carbon:{name}')).status_code, 405)
        self.assertEqual(self.client.put(reverse('carbon:add_trip')).status_code, 405)

    @patch('carbon.views.geocode_search', return_value=[ORIGIN])
    def test_geocode_api_returns_signed_selection(self, search):
        url = reverse('carbon:api_geocode')
        self.assertEqual(self.client.get(url, {'q': 'x'}).json(), {'results': []})
        search.assert_not_called()
        self.assertEqual(self.client.get(url, {'q': 'x' * 256}).status_code, 400)
        data = self.client.get(url, {'q': '  Depok  '}).json()['results'][0]
        search.assert_called_once_with('Depok')
        self.assertTrue(verify_location(data['location_token'], data['name'], data['lat'], data['lon'], self.user.pk))

    @patch('carbon.views.calculate_route', return_value=ROUTE)
    def test_route_api_validates_input_before_provider(self, route):
        url = reverse('carbon:api_route')
        valid = {'olat': -6, 'olon': 106, 'dlat': -7, 'dlon': 107, 'mode': 'drive'}
        for data in ({}, {**valid, 'olat': 'NaN'}, {**valid, 'olon': 181}, {**valid, 'mode': 'train'}, {**valid, 'olat': -7, 'olon': 107}):
            self.assertEqual(self.client.get(url, data).status_code, 400)
        route.assert_not_called()
        response = self.client.get(url, valid)
        self.assertEqual(response.json()['co2e_kg'], 2.0747)
        self.assertEqual(response.json()['mode_code'], 'mobil')
        self.assertFalse(Trip.objects.exists())

    def test_provider_errors_remain_json(self):
        for status in (404, 502, 503, 504):
            with self.subTest(status=status), patch('carbon.views.geocode_search', side_effect=GeoapifyError('Pesan aman', status=status)):
                response = self.client.get(reverse('carbon:api_geocode'), {'q': 'Depok'})
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()['error'], 'Pesan aman')

    def test_model_rejects_out_of_range_coordinates(self):
        trip = self.trip()
        trip.origin_lat = Decimal('91')
        with self.assertRaises(ValidationError):
            trip.full_clean()

    @patch.dict('os.environ', {'GEOAPIFY_API_KEY': 'integration-test-secret'})
    @patch('carbon.services.requests.get')
    def test_full_proxy_to_crud_flow(self, get):
        """Gunakan service asli, hanya transport HTTP Geoapify yang diganti."""
        new_destination = {'name': 'Tujuan baru, Depok', 'lat': -6.38, 'lon': 106.82}

        def provider(url, params, timeout):
            response = Mock(status_code=200)
            if url.endswith('/geocode/search'):
                choices = {'Asal': ORIGIN, 'Tujuan': DESTINATION, 'Tujuan baru': new_destination}
                location = choices[params['text']]
                data = {'features': [{'properties': {
                    'formatted': location['name'], 'lat': location['lat'],
                    'lon': location['lon'], 'country_code': 'id',
                }}]}
            else:
                data = route_response(distance=3500 if params['mode'] == 'walk' else 12450)
            response.json.return_value = data
            return response

        get.side_effect = provider
        geocode_url = reverse('carbon:api_geocode')
        selections = []
        for query in ('Asal', 'Tujuan'):
            response = self.client.get(geocode_url, {'q': query})
            self.assertNotContains(response, 'integration-test-secret')
            selections.append(response.json()['results'][0])
        data = self.payload()
        for prefix, location in zip(('origin', 'destination'), selections):
            data[f'{prefix}_token'] = location['location_token']
        preview = self.client.get(reverse('carbon:api_route'), {
            'olat': data['origin_lat'], 'olon': data['origin_lng'],
            'dlat': data['destination_lat'], 'dlon': data['destination_lng'], 'mode': 'drive',
        })
        self.assertEqual(preview.json()['co2e_kg'], 2.0747)
        self.assertFalse(Trip.objects.exists())
        saved = self.client.post(reverse('carbon:add_trip'), data)
        self.assertEqual(saved.status_code, 302)
        trip = Trip.objects.get()
        self.assertEqual(float(trip.distance_km), preview.json()['distance_km'])
        self.assertEqual(float(trip.emission_kg), preview.json()['co2e_kg'])
        calls_before_edit = get.call_count
        data.update(note='Hanya tanggal dan catatan', trip_date=(today() - timedelta(days=1)).isoformat())
        self.assertEqual(self.client.post(reverse('carbon:edit_trip', args=[trip.pk]), data).status_code, 302)
        self.assertEqual(get.call_count, calls_before_edit)
        selected = self.client.get(geocode_url, {'q': 'Tujuan baru'}).json()['results'][0]
        data.update(destination_label=selected['name'], destination_lat=selected['lat'],
                    destination_lng=selected['lon'], destination_token=selected['location_token'], mode='jalan')
        self.assertEqual(self.client.post(reverse('carbon:edit_trip', args=[trip.pk]), data).status_code, 302)
        trip.refresh_from_db()
        self.assertEqual(trip.destination_label, new_destination['name'])
        self.assertEqual(trip.distance_km, Decimal('3.500'))
        self.assertEqual(trip.emission_kg, 0)
        calls_before_read = get.call_count
        self.assertEqual(self.client.get(reverse('carbon:api_history')).json()['summary'], {
            'total_trips': 1, 'total_distance_km': 3.5, 'total_co2e_kg': 0.0,
        })
        self.assertEqual(self.client.get(reverse('carbon:index')).status_code, 200)
        self.assertEqual(get.call_count, calls_before_read)
        self.assertEqual(self.client.post(reverse('carbon:delete_trip', args=[trip.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse('carbon:api_history')).json()['summary']['total_trips'], 0)

    @patch('carbon.services.requests.get')
    def test_history_and_note_edit_work_when_provider_is_down(self, get):
        get.side_effect = requests.ConnectionError('Provider offline')
        trip = self.trip()
        self.assertEqual(self.client.get(reverse('carbon:index')).status_code, 200)
        self.assertEqual(self.client.get(reverse('carbon:api_history')).status_code, 200)
        self.assertEqual(self.client.post(reverse('carbon:edit_trip', args=[trip.pk]), self.payload(note='Tetap bisa diedit')).status_code, 302)
        get.assert_not_called()

    @patch('carbon.views.calculate_route')
    def test_create_and_edit_require_csrf(self, route):
        trip = self.trip()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for url in (reverse('carbon:add_trip'), reverse('carbon:edit_trip', args=[trip.pk])):
            self.assertEqual(client.post(url, self.payload()).status_code, 403)
        route.assert_not_called()

    def test_jakarta_default_date_and_safe_rendering(self):
        with patch('carbon.dates.timezone.now', return_value=datetime(2026, 10, 25, 18, tzinfo=timezone.utc)):
            form = self.client.get(reverse('carbon:add_trip')).context['form']
            self.assertEqual(form['trip_date'].value(), date(2026, 10, 26))
            self.assertEqual(form.fields['trip_date'].widget.attrs['max'], '2026-10-26')
        self.trip(note='<script>alert("x")</script>', origin_label='<img src=x onerror=alert(1)>')
        response = self.client.get(reverse('carbon:index'))
        self.assertContains(response, '&lt;script&gt;')
        self.assertContains(response, '&lt;img')
        self.assertNotContains(response, '<script>alert(')
        edit = self.client.get(reverse('carbon:edit_trip', args=[Trip.objects.get().pk]))
        self.assertNotContains(edit, '<img src=x onerror=alert(1)>')

    def test_erd_fields_and_relationships(self):
        required = {'user', 'mode', 'emission_factor', 'origin_label', 'origin_lat', 'origin_lng',
                    'destination_label', 'destination_lat', 'destination_lng', 'distance_km',
                    'distance_source', 'duration_s', 'route_geometry', 'emission_kg', 'traveled_at', 'created_at'}
        self.assertTrue(required.issubset({field.name for field in Trip._meta.fields}))
        trip = self.trip()
        with self.assertRaises(ProtectedError):
            trip.emission_factor.delete()
        with self.assertRaises(ProtectedError):
            trip.mode.delete()
        self.user.delete()
        self.assertFalse(Trip.objects.exists())
        self.assertTrue(TransportMode.objects.exists())
        self.assertTrue(EmissionFactor.objects.exists())

    def test_factors_are_versioned_and_immutable(self):
        factor = EmissionFactor.objects.get(mode__code='mobil')
        original_value = factor.kg_co2e_per_km
        factor.kg_co2e_per_km = Decimal('.01')
        with self.assertRaises(ValidationError):
            factor.save()
        with self.assertRaises(ValidationError):
            EmissionFactor.objects.filter(pk=factor.pk).update(kg_co2e_per_km='.01')
        factor.refresh_from_db()
        self.assertEqual(factor.kg_co2e_per_km, original_value)
        new = EmissionFactor.objects.create(mode=factor.mode, kg_co2e_per_km='.1', version='new-test-version',
                                           source='Controlled test reference', valid_from=today())
        self.assertEqual(get_emission_factor(factor.mode), new)
        self.assertEqual(get_emission_factor(factor.mode, today() - timedelta(days=1)), factor)

    @patch('carbon.views.calculate_route', return_value=ROUTE)
    def test_old_factor_stays_until_route_changes(self, route):
        trip = self.trip()
        old_factor_id = trip.emission_factor_id
        new = EmissionFactor.objects.create(mode=trip.mode, kg_co2e_per_km='.1', version='new-test-version',
                                           source='Controlled test reference', valid_from=today())
        url = reverse('carbon:edit_trip', args=[trip.pk])
        self.assertEqual(self.client.post(url, self.payload(note='New note')).status_code, 302)
        trip.refresh_from_db()
        self.assertEqual(trip.emission_factor_id, old_factor_id)
        route.assert_not_called()
        loc = {**ORIGIN, 'name': 'Asal berbeda'}
        self.assertEqual(self.client.post(url, self.payload(origin_label=loc['name'], origin_token=location_token(loc, self.user.pk))).status_code, 302)
        trip.refresh_from_db()
        self.assertEqual(trip.emission_factor, new)
        self.assertEqual(trip.emission_kg, Decimal('1.2450'))

    def test_factor_must_match_trip_mode(self):
        trip = self.trip()
        trip.emission_factor = EmissionFactor.objects.get(mode__code='motor')
        with self.assertRaises(ValidationError):
            trip.full_clean()

    @patch('carbon.views.calculate_route')
    def test_bus_and_train_remain_inactive_and_cannot_use_manual_distance(self, route):
        for code in ('bus', 'kereta'):
            self.assertFalse(TransportMode.objects.get(code=code).is_active)
            response = self.client.post(reverse('carbon:add_trip'), self.payload(mode=code, distance_km='50', distance_source='manual'))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
            self.assertEqual(self.client.get(reverse('carbon:api_route'), {'olat': -6, 'olon': 106, 'dlat': -7, 'dlon': 107, 'mode': code}).status_code, 400)
        route.assert_not_called()
        self.assertFalse(Trip.objects.exists())

    @patch('carbon.views.calculate_route', return_value=ROUTE)
    def test_inactive_old_mode_allows_notes_but_no_new_route(self, route):
        trip = self.trip()
        trip.mode.is_active = False
        trip.mode.save()
        url = reverse('carbon:edit_trip', args=[trip.pk])
        self.assertEqual(self.client.post(url, self.payload(note='Still editable')).status_code, 302)
        route.assert_not_called()
        response = self.client.post(url, self.payload(origin_label='Changed name', origin_token=location_token({**ORIGIN, 'name': 'Changed name'}, self.user.pk)))
        self.assertContains(response, 'Moda transportasi tidak tersedia')
        route.assert_not_called()

    @patch('carbon.views.calculate_route', return_value={**ROUTE, 'route_geometry': {'type': 'LineString', 'coordinates': [[106.8302, -6.3616], [106.8217, -6.391]]}})
    def test_stores_raw_route_duration_and_source_for_dashboard(self, route):
        response = self.client.post(reverse('carbon:add_trip'), self.payload())
        self.assertEqual(response.status_code, 302)
        trip = Trip.objects.get()
        self.assertEqual(trip.duration_s, 1500)
        self.assertEqual(trip.distance_source, 'routing')
        self.assertEqual(trip.route_geometry['type'], 'LineString')
        row = self.client.get(reverse('carbon:api_history')).json()['trips'][0]
        self.assertEqual(row['route_geometry'], trip.route_geometry)
        self.assertEqual(row['mode_code'], 'mobil')
        self.assertEqual(row['emission_kg'], 2.0747)
        self.assertEqual(row['emission_factor_id'], trip.emission_factor_id)

    @patch('carbon.views.calculate_route', return_value=ROUTE)
    def test_preview_uses_factor_for_selected_date(self, route):
        mode = TransportMode.objects.get(code='mobil')
        EmissionFactor.objects.create(mode=mode, kg_co2e_per_km='.1', version='new-test-version',
                                      source='Controlled test reference', valid_from=today())
        values = {'olat': -6, 'olon': 106, 'dlat': -7, 'dlon': 107, 'mode': 'mobil'}
        url = reverse('carbon:api_route')
        self.assertEqual(self.client.get(url, {**values, 'date': today().isoformat()}).json()['co2e_kg'], 1.245)
        self.assertEqual(self.client.get(url, {**values, 'date': (today() - timedelta(days=1)).isoformat()}).json()['co2e_kg'], 2.0747)
        self.assertEqual(self.client.get(url, {**values, 'date': 'invalid-date'}).status_code, 400)
        self.assertEqual(self.client.get(url, {**values, 'date': (today() + timedelta(days=1)).isoformat()}).status_code, 400)

    @patch('carbon.forms.get_primary_mode')
    def test_onboarding_preference_only_prefills_without_creating_data(self, preference):
        preference.return_value = TransportMode.objects.get(code='motor')
        form = self.client.get(reverse('carbon:add_trip')).context['form']
        self.assertEqual(form.initial['mode'], 'motor')
        self.assertFalse(Trip.objects.exists())
