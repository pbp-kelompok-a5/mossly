from django import forms
from django.db.models import Q

from .dates import at_start_of_day, today
from .models import SUPPORTED_PROFILES, TransportMode, Trip
from .services import get_primary_mode, verify_location

LOCATION_FIELDS = ('origin_label', 'origin_lat', 'origin_lng',
                   'destination_label', 'destination_lat', 'destination_lng')
ROUTE_FIELDS = (*LOCATION_FIELDS, 'mode')


class TripForm(forms.ModelForm):
    trip_date = forms.DateField(label='Tanggal Perjalanan', initial=today,
                               widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    origin_token = forms.CharField(widget=forms.HiddenInput, required=False)
    destination_token = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Trip
        fields = [*LOCATION_FIELDS, 'mode', 'note']
        labels = {'mode': 'Moda Transportasi'}
        widgets = {
            'origin_label': forms.TextInput(attrs={'placeholder': 'Ketik nama tempat asal...', 'autocomplete': 'off'}),
            'destination_label': forms.TextInput(attrs={'placeholder': 'Ketik nama tempat tujuan...', 'autocomplete': 'off'}),
            'origin_lat': forms.HiddenInput(), 'origin_lng': forms.HiddenInput(),
            'destination_lat': forms.HiddenInput(), 'destination_lng': forms.HiddenInput(),
            'mode': forms.RadioSelect(),
            'note': forms.Textarea(attrs={'rows': 3, 'maxlength': 200, 'placeholder': 'Catatan opsional (maks. 200 karakter)'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        allowed = Q(is_active=True, geoapify_profile__in=SUPPORTED_PROFILES)
        # Riwayat moda yang dinonaktifkan tetap dapat diedit tanggal/catatannya.
        if self.instance.pk:
            allowed |= Q(pk=self.instance.mode_id)
            self.initial['trip_date'] = self.instance.trip_date
        self.fields['mode'].queryset = TransportMode.objects.filter(allowed)
        self.fields['mode'].to_field_name = 'code'
        self.fields['mode'].empty_label = None
        if self.instance.pk:
            self.initial['mode'] = self.instance.mode.code
        elif not self.is_bound and user:
            preferred_mode = get_primary_mode(user)
            if preferred_mode:
                self.initial['mode'] = preferred_mode.code
        for name in ('origin_label', 'destination_label', 'trip_date', 'note'):
            self.fields[name].widget.attrs['class'] = 'input'
        self.fields['trip_date'].widget.attrs['max'] = today().isoformat()

    @property
    def route_changed(self):
        # Django sudah membandingkan input dengan nilai awal melalui changed_data.
        return not self.instance.pk or (
            self.is_bound and any(name in self.changed_data for name in ROUTE_FIELDS)
        )

    def clean_trip_date(self):
        value = self.cleaned_data['trip_date']
        if value > today():
            raise forms.ValidationError('Tanggal perjalanan tidak boleh di masa depan.')
        return value

    def clean(self):
        cleaned = super().clean()
        for prefix in ('origin', 'destination'):
            fields = [f'{prefix}_label', f'{prefix}_lat', f'{prefix}_lng']
            if not all(name in cleaned for name in fields):
                continue
            unchanged = self.instance.pk and all(cleaned[name] == self.initial.get(name) for name in fields)
            if not unchanged and not verify_location(
                cleaned.get(f'{prefix}_token', ''), *(cleaned[name] for name in fields),
                self.user.pk if self.user else None,
            ):
                self.add_error(f'{prefix}_label', 'Pilih lokasi Indonesia dari hasil pencarian, peta, atau tombol lokasi saya.')
        coords = ('origin_lat', 'origin_lng', 'destination_lat', 'destination_lng')
        if all(name in cleaned for name in coords) and (cleaned['origin_lat'], cleaned['origin_lng']) == (cleaned['destination_lat'], cleaned['destination_lng']):
            self.add_error('destination_label', 'Asal dan tujuan harus berbeda.')
        if self.route_changed:
            # ModelForm memvalidasi instance sebelum view menghitung ulang.
            # Faktor lama tidak boleh dipasangkan dengan moda baru sementara itu.
            self.instance.emission_factor = None
        return cleaned

    def save(self, commit=True):
        trip = super().save(commit=False)
        chosen_date = self.cleaned_data['trip_date']
        if not trip.pk or trip.trip_date != chosen_date:
            trip.traveled_at = at_start_of_day(chosen_date)
        if commit:
            trip.save()
        return trip
