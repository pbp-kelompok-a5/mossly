from django import forms
from datetime import date
from .models import Trip


class TripForm(forms.ModelForm):
    """Form untuk Create & Update perjalanan."""

    class Meta:
        model = Trip
        fields = [
            'origin_name', 'origin_lat', 'origin_lon',
            'destination_name', 'destination_lat', 'destination_lon',
            'transport_mode',
            'distance_km', 'co2_emission_kg',
            'note', 'trip_date',
        ]
        widgets = {
            'origin_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ketik nama tempat asal...',
                'autocomplete': 'off',
            }),
            'destination_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ketik nama tempat tujuan...',
                'autocomplete': 'off',
            }),
            'transport_mode': forms.RadioSelect(attrs={
                'class': 'mode-radio',
            }),
            'note': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 2,
                'placeholder': 'Catatan opsional (maks. 200 karakter)',
                'maxlength': '200',
            }),
            'trip_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date',
            }),
            # Hidden fields — diisi otomatis via JavaScript
            'origin_lat': forms.HiddenInput(),
            'origin_lon': forms.HiddenInput(),
            'destination_lat': forms.HiddenInput(),
            'destination_lon': forms.HiddenInput(),
            'distance_km': forms.HiddenInput(),
            'co2_emission_kg': forms.HiddenInput(),
        }

    def clean_trip_date(self):
        """Tanggal tidak boleh di masa depan."""
        trip_date = self.cleaned_data.get('trip_date')
        if trip_date and trip_date > date.today():
            raise forms.ValidationError('Tanggal perjalanan tidak boleh di masa depan.')
        return trip_date

    def clean_note(self):
        """Batasi catatan maks. 200 karakter."""
        note = self.cleaned_data.get('note', '')
        if len(note) > 200:
            raise forms.ValidationError('Catatan maksimal 200 karakter.')
        return note

    def clean(self):
        """Validasi bahwa koordinat dan jarak sudah terisi."""
        cleaned = super().clean()

        # Pastikan koordinat terisi (dari autocomplete)
        required_coords = ['origin_lat', 'origin_lon', 'destination_lat', 'destination_lon']
        for field in required_coords:
            if not cleaned.get(field):
                self.add_error(field, 'Pilih lokasi dari daftar yang muncul.')

        # Pastikan jarak terisi (dari routing API)
        if not cleaned.get('distance_km'):
            self.add_error('distance_km', 'Jarak belum dihitung. Pastikan asal dan tujuan sudah dipilih.')

        return cleaned
