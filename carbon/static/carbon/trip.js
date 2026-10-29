(() => {
    'use strict';
    const form = document.getElementById('trip-form');
    if (!form) return;
    const initial = JSON.parse(document.getElementById('carbon-trip-state').textContent);
    const preview = document.getElementById('preview-box');
    const errorBox = document.getElementById('api-error');
    const errorMessage = document.getElementById('api-error-message');
    const routeStatus = document.getElementById('route-status');
    const submit = document.getElementById('submit-btn');
    const locations = {...initial.locations};
    const fields = {};
    const tripMap = createTripMap(selectPoint);
    const mapStatus = document.getElementById('map-status');
    let routeRequest = null;
    let submitting = false;

    function clearPreview() {
        routeRequest?.abort();
        tripMap.clearRoute();
        preview.hidden = true;
        submit.disabled = true;
        errorBox.hidden = true;
        routeStatus.textContent = 'Tekan Hitung estimasi setelah pilihan selesai.';
    }

    function showPreview(data) {
        const format = (value, digits) => Number(value).toLocaleString('id-ID', {maximumFractionDigits: digits});
        document.getElementById('preview-distance').textContent = `${format(data.distance_km, 3)} km`;
        document.getElementById('preview-co2').textContent = `${format(data.co2e_kg, 4)} kg`;
        document.getElementById('preview-duration').textContent = data.duration_minutes == null ? '' : `Estimasi waktu: ${format(data.duration_minutes, 1)} menit`;
        preview.hidden = false;
        submit.disabled = false;
        routeStatus.textContent = '';
        tripMap.showRoute(data.route_geometry);
    }

    async function readJSON(endpoint, params, signal) {
        const url = new URL(endpoint, window.location.origin);
        url.search = new URLSearchParams(params);
        const response = await fetch(url, {signal, headers: {'Accept': 'application/json'}});
        if (response.status === 401) throw new Error('Sesi berakhir. Silakan login kembali.');
        if (!response.headers.get('content-type')?.includes('application/json')) {
            throw new Error('Layanan tidak tersedia. Silakan coba lagi.');
        }
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Layanan sedang bermasalah. Silakan coba lagi.');
        return data;
    }

    async function calculateRoute() {
        clearPreview();
        const mode = form.querySelector('input[name="mode"]:checked')?.value;
        if (!form.reportValidity()) return;
        if (!locations.origin || !locations.destination || !mode) {
            routeStatus.textContent = 'Pilih asal dan tujuan yang valid serta moda transportasi terlebih dahulu.';
            return;
        }
        if (initial.preview && mode === initial.original_mode &&
            document.getElementById('id_trip_date').value === initial.original_date &&
            ['origin', 'destination'].every(prefix =>
                locations[prefix].name === initial.locations[prefix].name &&
                Number(locations[prefix].lat) === Number(initial.locations[prefix].lat) &&
                Number(locations[prefix].lon) === Number(initial.locations[prefix].lon))) {
            showPreview(initial.preview);
            return;
        }
        const request = new AbortController();
        routeRequest = request;
        routeStatus.textContent = 'Menghitung jarak dan estimasi emisi…';
        try {
            const data = await readJSON(form.dataset.routeUrl, {
                olat: locations.origin.lat, olon: locations.origin.lon,
                dlat: locations.destination.lat, dlon: locations.destination.lon,
                mode, date: document.getElementById('id_trip_date').value,
            }, request.signal);
            if (request.signal.aborted) return;
            showPreview(data);
            routeStatus.textContent = '';
        } catch (error) {
            if (request.signal.aborted) return;
            routeStatus.textContent = '';
            errorMessage.textContent = error.message;
            errorBox.hidden = false;
        }
    }

    // Pencarian hanya dimulai saat tombol Cari (atau Enter) ditekan.
    for (const prefix of ['origin', 'destination']) {
        const input = document.getElementById(`id_${prefix}_label`);
        const results = document.getElementById(`${prefix}-results`);
        const status = document.getElementById(`${prefix}-status`);
        const lat = document.getElementById(`id_${prefix}_lat`);
        const lon = document.getElementById(`id_${prefix}_lng`);
        const token = document.getElementById(`id_${prefix}_token`);
        let searchRequest;
        input.setAttribute('aria-describedby', [input.getAttribute('aria-describedby'), status.id].filter(Boolean).join(' '));

        // Batalkan hasil lama agar tidak tersimpan setelah pilihan berubah.
        function resetSelection() {
            searchRequest?.abort();
            searchRequest = new AbortController();
            locations[prefix] = null;
            lat.value = lon.value = token.value = '';
            results.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            results.replaceChildren();
            tripMap.setLocation(prefix, null);
            clearPreview();
            return searchRequest;
        }

        function selectLocation(location) {
            searchRequest?.abort();
            input.value = location.name;
            lat.value = location.lat;
            lon.value = location.lon;
            token.value = location.location_token;
            locations[prefix] = location;
            results.hidden = true;
            input.setAttribute('aria-expanded', 'false');
            status.textContent = '';
            tripMap.setLocation(prefix, location);
            clearPreview();
        }
        fields[prefix] = {resetSelection, selectLocation, status};

        async function searchLocation() {
            const request = resetSelection();
            const query = input.value.trim();
            status.textContent = 'Ketik minimal 2 karakter lalu tekan Cari.';
            if (query.length < 2) return;
            status.textContent = 'Mencari lokasi…';
            try {
                const data = await readJSON(form.dataset.geocodeUrl, {q: query}, request.signal);
                if (request.signal.aborted) return;
                const matches = data.results;
                matches.forEach(location => {
                    const button = document.createElement('button');
                    button.type = 'button';
                    button.className = 'carbon-location-result';
                    const icon = document.createElement('img');
                    icon.src = form.dataset.pinIcon;
                    icon.alt = '';
                    const label = document.createElement('span');
                    label.textContent = location.name;
                    button.append(icon, label);
                    button.addEventListener('click', () => {
                        selectLocation(location);
                        input.focus();
                    });
                    results.append(button);
                });
                results.hidden = matches.length === 0;
                input.setAttribute('aria-expanded', String(matches.length > 0));
                status.textContent = matches.length ? 'Pilih lokasi dari hasil pencarian.' : 'Lokasi tidak ditemukan. Coba nama yang lebih lengkap.';
            } catch (error) {
                if (!request.signal.aborted) status.textContent = error.message;
            }
        }

        input.addEventListener('input', () => {
            resetSelection();
            status.textContent = 'Tekan Cari untuk mencari alamat yang diketik.';
        });
        input.addEventListener('keydown', event => {
            if (event.key === 'Enter') { event.preventDefault(); searchLocation(); }
        });
        document.getElementById(`${prefix}-search`).addEventListener('click', searchLocation);
        results.addEventListener('keydown', event => {
            const buttons = [...results.querySelectorAll('button')];
            const index = buttons.indexOf(document.activeElement);
            if (event.key === 'Escape') {
                results.hidden = true;
                input.setAttribute('aria-expanded', 'false');
                input.focus();
            } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                const next = (index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
                buttons[next]?.focus();
            }
        });
        input.setAttribute('aria-controls', results.id);
        input.setAttribute('aria-expanded', 'false');
        input.addEventListener('keydown', event => {
            if (event.key === 'ArrowDown' && !results.hidden) {
                event.preventDefault();
                results.querySelector('button')?.focus();
            }
        });
    }

    async function selectPoint(prefix, lat, lon, request = fields[prefix].resetSelection()) {
        fields[prefix].status.textContent = 'Mencari alamat titik yang dipilih…';
        try {
            const location = await readJSON(form.dataset.reverseUrl, {lat, lon}, request.signal);
            if (request.signal.aborted) return;
            fields[prefix].selectLocation(location);
        } catch (error) {
            if (!request.signal.aborted) fields[prefix].status.textContent = error.message;
        }
    }

    document.getElementById('use-my-location').addEventListener('click', () => {
        if (!navigator.geolocation || !window.isSecureContext) {
            mapStatus.textContent = 'Lokasi saya memerlukan HTTPS atau localhost. Gunakan pencarian alamat atau pilih titik di peta.';
            return;
        }
        const request = fields.origin.resetSelection();
        fields.origin.status.textContent = 'Menunggu izin dan posisi dari browser…';
        navigator.geolocation.getCurrentPosition(position => {
            if (!request.signal.aborted) selectPoint('origin', position.coords.latitude, position.coords.longitude, request);
        }, error => {
            if (request.signal.aborted) return;
            fields.origin.status.textContent = error.code === 1
                ? 'Izin lokasi ditolak. Cari alamat asal atau pilih asal di peta.'
                : 'Lokasi belum didapat. Coba lagi, cari alamat, atau pilih asal di peta.';
        }, {enableHighAccuracy: true, timeout: 10000, maximumAge: 60000});
    });

    form.querySelectorAll('input[name="mode"]').forEach(radio => radio.addEventListener('change', clearPreview));
    document.getElementById('id_trip_date').addEventListener('input', clearPreview);
    document.getElementById('calculate-route').addEventListener('click', calculateRoute);
    form.addEventListener('submit', event => {
        if (preview.hidden || submitting) { event.preventDefault(); return; }
        submitting = true;
        submit.disabled = true;
        routeStatus.textContent = 'Menyimpan perjalanan…';
    });
    // Restore the button if the browser returns to this page from its cache.
    window.addEventListener('pageshow', () => { submitting = false; submit.disabled = preview.hidden; });
    // Saat edit, tampilkan hasil tersimpan tanpa request API baru.
    Object.entries(locations).forEach(([prefix, location]) => tripMap.setLocation(prefix, location));
    if (initial.preview) showPreview(initial.preview);
})();
