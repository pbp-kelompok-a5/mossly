/* Peta saja: membuat pin dan menggambar rute. Data form/API diurus trip.js. */
function createTripMap(onPick) {
    'use strict';
    const form = document.getElementById('trip-form');
    const mapStatus = document.getElementById('map-status');
    const markers = {};
    let map = null, routeLayer = null;
    let mapPick = 'destination';

    function clearRoute() {
        routeLayer?.remove();
        routeLayer = null;
    }

    function showRoute(geometry) {
        clearRoute();
        if (map && geometry) {
            try {
                routeLayer = L.geoJSON(geometry, {
                    style: {className: 'carbon-route'}, interactive: false,
                }).addTo(map);
                const bounds = routeLayer.getBounds();
                Object.values(markers).forEach(marker => bounds.extend(marker.getLatLng()));
                if (bounds.isValid()) map.fitBounds(bounds.pad(0.2), {maxZoom: 16});
            } catch {
                routeLayer?.remove();
                mapStatus.textContent = 'Garis rute tidak dapat ditampilkan. Estimasi perjalanan tetap tersedia.';
            }
        }
    }
    function setLocation(prefix, location) {
        if (!map) return;
        markers[prefix]?.remove();
        delete markers[prefix];
        if (!location) return;
        const label = prefix === 'origin' ? 'Asal' : 'Tujuan';
        markers[prefix] = L.marker([location.lat, location.lon], {title: label, alt: label})
            .bindTooltip(label, {permanent: true, direction: prefix === 'origin' ? 'top' : 'bottom'}).addTo(map);
        const points = Object.values(markers).map(marker => marker.getLatLng());
        map.fitBounds(L.latLngBounds(points).pad(0.2), {maxZoom: 16});
    }

    const pickButtons = [...form.querySelectorAll('[data-map-pick]')];
    if (window.L) {
        // Tampilan awal Jakarta; ini bukan lokasi pengguna.
        map = L.map('trip-map', {scrollWheelZoom: false}).setView([-6.2, 106.82], 12);
        L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            // OSM memerlukan Referer; default Django same-origin menghilangkannya.
            referrerPolicy: 'strict-origin-when-cross-origin',
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        }).on('tileerror', () => {
            mapStatus.textContent = 'Gambar peta gagal dimuat. Periksa koneksi atau gunakan pencarian alamat.';
        }).addTo(map);
        map.on('click', event => {
            const point = event.latlng.wrap();
            onPick(mapPick, point.lat, point.lng);
        });
        pickButtons.forEach(button => button.addEventListener('click', () => {
            mapPick = button.dataset.mapPick;
            pickButtons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
            mapStatus.textContent = `Ketuk peta untuk memilih ${mapPick === 'origin' ? 'asal' : 'tujuan'}.`;
        }));
    } else {
        document.getElementById('trip-map').hidden = true;
        pickButtons.forEach(button => { button.disabled = true; });
        mapStatus.textContent = 'Peta gagal dimuat. Kamu tetap bisa memakai pencarian alamat.';
    }

    return {setLocation, showRoute, clearRoute};
}
