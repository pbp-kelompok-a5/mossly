document.querySelectorAll('[data-confirm-delete]').forEach(form => {
    form.addEventListener('submit', event => {
        if (!window.confirm('Yakin ingin menghapus perjalanan ini? Data yang dihapus tidak bisa dikembalikan.')) {
            event.preventDefault();
        }
    });
});
