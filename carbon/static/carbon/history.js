/* Dialog dipakai bersama oleh riwayat dan form edit. */
(() => {
    'use strict';
    const deleteDialog = document.getElementById('delete-dialog');
    let pendingDelete = null;

    document.querySelectorAll('[data-confirm-delete]').forEach(form => {
        form.addEventListener('submit', event => {
            if (!deleteDialog) return;
            event.preventDefault();
            pendingDelete = form;
            document.getElementById('delete-description').textContent = form.dataset.tripDescription;
            deleteDialog.showModal();
        });
    });
    document.getElementById('confirm-delete')?.addEventListener('click', event => {
        if (!pendingDelete) return;
        event.currentTarget.disabled = true;
        // Submit langsung setelah konfirmasi; POST tetap menyertakan token CSRF.
        pendingDelete.submit();
    });
    document.querySelectorAll('[data-close-dialog]').forEach(button => {
        button.addEventListener('click', () => button.closest('dialog').close());
    });
    document.querySelector('[data-open-dialog]')?.showModal();
    const sortMenu = document.querySelector('.carbon-sort');
    document.addEventListener('click', event => {
        if (sortMenu && !sortMenu.contains(event.target)) sortMenu.open = false;
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && sortMenu?.open) {
            sortMenu.open = false;
            sortMenu.querySelector('summary').focus();
        }
    });
    window.addEventListener('pageshow', () => {
        const confirm = document.getElementById('confirm-delete');
        if (confirm) confirm.disabled = false;
    });
})();
