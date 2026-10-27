# Sustainability Community

Halaman komunitas ada di `/community/` dan membutuhkan sesi login. Template dan CSS terpisah dari halaman modul lain. Avatar menggunakan inisial akun karena modul Login belum menyediakan data avatar.

Jalankan dari direktori proyek:

```sh
python manage.py migrate
python manage.py test community
python manage.py runserver
```

Modul Login masih berupa placeholder. Untuk pemeriksaan lokal, masuk dengan akun superuser melalui `/admin/login/?next=/community/`. Jika belum memiliki akun lokal, buat dengan `python manage.py createsuperuser`.

## Integrasi Dashboard

Dashboard dapat memanggil fungsi internal berikut setelah achievement tersimpan:

```python
from community.services import publish_achievement

thread = publish_achievement(
    user=user,
    event_id="dashboard:achievement-event:123",  # unik dan stabil untuk retry
    achievement_id="tumbler-7-days",
    name="Pejuang Tumbler",
    description="Berhasil membawa tumbler selama tujuh hari!",
    earned_at=earned_at,  # datetime dengan timezone
)
```

Pemanggilan ulang mengembalikan thread yang sama, atau `None` apabila pemilik sudah menghapusnya. Event disimpan terpisah dari thread supaya retry tidak menerbitkan ulang post yang dihapus. Post otomatis tidak dapat diedit melalui Community. Fungsi ini tidak diekspos sebagai endpoint publik; Dashboard bertanggung jawab memverifikasi perolehan achievement. Kegagalan dicatat dan dilempar kembali agar pemanggil dapat melakukan retry.
