(() => {
    'use strict';
    const form = document.getElementById('trip-form');
    if (!form) return;
    const initial = JSON.parse(document.getElementById('carbon-trip-state').textContent);
    const preview = document.getElementById('preview-box');
    const errorBox = document.getElementById('api-error');
    const errorMessage = document.getElementById('api-error-message');
    const routeStatus = document.getElementById('route-status');
    const retry = document.getElementById('retry-route');
    const submit = document.getElementById('submit-btn');
    const fields = {};
    let routeRequest = null;
    let routeVersion = 0;
    let previewValid = false;
    let submitting = false;

    function clearPreview() {
        routeVersion += 1;
        routeRequest?.abort();
        previewValid = false;
        preview.hidden = true;
        submit.disabled = true;
        errorBox.hidden = true;
        retry.hidden = true;
        routeStatus.textContent = '';
    }

    function showPreview(data) {
        document.getElementById('preview-distance').textContent = `${Number(data.distance_km).toFixed(3)} km`;
        document.getElementById('preview-co2').textContent = `${Number(data.co2e_kg).toFixed(4)} kg CO₂e`;
        document.getElementById('preview-duration').textContent = data.duration_minutes == null ? '' : `Estimasi waktu: ${data.duration_minutes} menit`;
        preview.hidden = false;
        previewValid = true;
        submit.disabled = false;
    }

    async function readJSON(url, signal) {
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
        if (!fields.origin.selected || !fields.destination.selected || !mode) return;
        if (initial.preview && mode === initial.original_mode &&
            ['origin', 'destination'].every(prefix =>
                fields[prefix].selected.name === initial.locations[prefix].name &&
                Number(fields[prefix].selected.lat) === Number(initial.locations[prefix].lat) &&
                Number(fields[prefix].selected.lon) === Number(initial.locations[prefix].lon))) {
            showPreview(initial.preview);
            return;
        }
        const version = routeVersion;
        routeRequest = new AbortController();
        routeStatus.textContent = 'Menghitung jarak dan estimasi emisi…';
        const url = new URL(form.dataset.routeUrl, window.location.origin);
        url.search = new URLSearchParams({
            olat: fields.origin.selected.lat, olon: fields.origin.selected.lon,
            dlat: fields.destination.selected.lat, dlon: fields.destination.selected.lon, mode, date: document.getElementById('id_trip_date').value,
        });
        try {
            const data = await readJSON(url, routeRequest.signal);
            if (version !== routeVersion) return;
            showPreview(data);
            routeStatus.textContent = '';
        } catch (error) {
            if (error.name === 'AbortError' || version !== routeVersion) return;
            routeStatus.textContent = '';
            errorMessage.textContent = error.message;
            errorBox.hidden = false;
            retry.hidden = false;
        }
    }

    for (const prefix of ['origin', 'destination']) {
        const input = document.getElementById(`id_${prefix}_label`);
        const dropdown = document.getElementById(`${prefix}-results`);
        const status = document.getElementById(`${prefix}-status`);
        const lat = document.getElementById(`id_${prefix}_lat`);
        const lon = document.getElementById(`id_${prefix}_lng`);
        const token = document.getElementById(`id_${prefix}_token`);
        const state = fields[prefix] = {selected: initial.locations[prefix] || null, timer: null, request: null, version: 0};
        input.setAttribute('aria-controls', dropdown.id);
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-autocomplete', 'list');
        input.setAttribute('aria-describedby', [input.getAttribute('aria-describedby'), status.id].filter(Boolean).join(' '));

        function closeDropdown() {
            dropdown.hidden = true;
            input.setAttribute('aria-expanded', 'false');
        }

        input.addEventListener('input', () => {
            state.version += 1;
            const version = state.version;
            clearTimeout(state.timer);
            state.request?.abort();
            state.selected = null;
            lat.value = lon.value = token.value = '';
            clearPreview();
            closeDropdown();
            dropdown.replaceChildren();
            const query = input.value.trim();
            status.textContent = query.length < 2 ? 'Ketik minimal 2 karakter lalu pilih lokasi dari daftar.' : 'Mencari lokasi…';
            if (query.length < 2) return;
            state.timer = setTimeout(async () => {
                state.request = new AbortController();
                const url = new URL(form.dataset.geocodeUrl, window.location.origin);
                url.searchParams.set('q', query);
                try {
                    const data = await readJSON(url, state.request.signal);
                    if (version !== state.version) return;
                    status.textContent = data.results.length ? 'Pilih lokasi yang sesuai.' : 'Lokasi tidak ditemukan. Coba nama yang lebih lengkap.';
                    for (const location of data.results) {
                        const button = document.createElement('button');
                        button.type = 'button';
                        button.className = 'dropdown-option';
                        button.setAttribute('role', 'option');
                        button.setAttribute('aria-selected', 'false');
                        button.textContent = location.name;
                        button.addEventListener('click', () => {
                            state.version += 1;
                            state.request?.abort();
                            input.value = location.name;
                            lat.value = location.lat;
                            lon.value = location.lon;
                            token.value = location.location_token;
                            state.selected = location;
                            button.setAttribute('aria-selected', 'true');
                            status.textContent = 'Lokasi dipilih.';
                            closeDropdown();
                            input.focus();
                            calculateRoute();
                        });
                        dropdown.append(button);
                    }
                    dropdown.hidden = data.results.length === 0;
                    input.setAttribute('aria-expanded', String(!dropdown.hidden));
                } catch (error) {
                    if (error.name === 'AbortError' || version !== state.version) return;
                    closeDropdown();
                    status.textContent = error.message;
                }
            }, 300);
        });
        input.addEventListener('keydown', event => {
            if (event.key === 'ArrowDown' && !dropdown.hidden) {
                event.preventDefault();
                dropdown.querySelector('button')?.focus();
            }
            if (event.key === 'Escape') closeDropdown();
        });
        dropdown.addEventListener('keydown', event => {
            const buttons = [...dropdown.querySelectorAll('button')];
            const index = buttons.indexOf(document.activeElement);
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                buttons[(index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length]?.focus();
            }
            if (event.key === 'Escape') { closeDropdown(); input.focus(); }
        });
        document.addEventListener('click', event => {
            if (!dropdown.contains(event.target) && event.target !== input) closeDropdown();
        });
    }

    form.querySelectorAll('input[name="mode"]').forEach(radio => radio.addEventListener('change', calculateRoute));
    document.getElementById('id_trip_date').addEventListener('change', calculateRoute);
    retry.addEventListener('click', calculateRoute);
    form.addEventListener('submit', event => {
        if (!previewValid || submitting) { event.preventDefault(); return; }
        submitting = true;
        submit.disabled = true;
        routeStatus.textContent = 'Menyimpan perjalanan…';
    });
    // Restore the button if the browser returns to this page from its cache.
    window.addEventListener('pageshow', () => { submitting = false; submit.disabled = !previewValid; });
    if (initial.preview) showPreview(initial.preview);
    else calculateRoute();
})();
