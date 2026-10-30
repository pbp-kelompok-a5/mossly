# Sustainability Community

Modul Community adalah ruang diskusi untuk berbagi tips, pengalaman, dan
pencapaian gaya hidup berkelanjutan. Seluruh halaman Community memerlukan
pengguna yang sudah login.

## Fitur

- Membuat, mengubah, dan menghapus thread milik sendiri.
- Membalas thread pengguna lain.
- Memberi atau menghapus apresiasi pada thread.
- Memfilter thread berdasarkan kategori **Tips**, **Obrolan**, dan
  **Pencapaian**.
- Menampilkan nama tampilan, avatar, serta `@username` penulis.
- Membuat post pencapaian otomatis dari Dashboard, apabila pengguna
  mengizinkan pembagian pencapaian.

Thread dan balasan menggunakan pembaruan asinkron untuk aksi yang tidak
memerlukan perpindahan halaman. Tombol apresiasi menggunakan HTMX; balasan,
filter kategori, dan pagination menggunakan request JSON.

## Arsitektur singkat

| Bagian | Tanggung jawab |
| --- | --- |
| `models.py` | `Thread`, `Reply`, dan `ThreadLike` beserta constraint data |
| `views.py` | Feed, detail, thread form, reply, like, JSON feed, dan integrasi respons async |
| `services.py` | Pembuatan post pencapaian otomatis dari Dashboard |
| `rate_limit.py` | Pembatasan request POST per pengguna melalui Django cache |
| `static/js/community/` | Module browser untuk card, optimistic like, reply, serta filter feed |

## Keamanan dan batas request

Semua view Community mewajibkan login, menggunakan CSRF untuk form POST, dan
memeriksa kepemilikan sebelum thread dapat diubah atau dihapus. Redirect
setelah like juga divalidasi agar tidak dapat mengarah ke host eksternal.

Untuk mengurangi spam dan request berlebihan, aksi POST dibatasi per pengguna:

| Aksi | Batas |
| --- | --- |
| Buat atau edit thread | 6 request per 10 menit |
| Kirim balasan | 12 request per 10 menit |
| Like atau unlike | 40 request per menit |
| Hapus thread | 5 request per 10 menit |

Request async yang melewati batas menerima status `429 Too Many Requests` dan
header `Retry-After`. Form biasa menampilkan halaman pemberitahuan Community.

## Data awal

Migration `0004_seed_tip_threads` membuat akun sistem nonaktif
`mossly_friend` dengan profil **Mossly Friend**, lalu menambahkan 50 thread
tips awal. Migration menggunakan `get_or_create()`, sehingga tidak membuat
duplikasi saat dijalankan pada database baru.

## Menjalankan lokal

Jalankan perintah berikut dari direktori proyek (`mossly/`):

```sh
python manage.py migrate
python manage.py test community
python manage.py runserver
```

Setelah login, Community dapat dibuka di `/community/`.

## Pengujian dan coverage

Jalankan test Community:

```sh
python manage.py test community
```

Untuk mengukur coverage backend Python Community, instal `coverage` bila belum
tersedia lalu jalankan:

```sh
python -m pip install coverage
python -m coverage erase
python -m coverage run --source=community manage.py test community
python -m coverage report -m
```

Hasil pengukuran lokal terakhir:

```text
Ran 20 tests
TOTAL  521 statements, 38 missed, 93% coverage
```

Test mencakup autentikasi, kepemilikan thread, validasi form, filter dan
pagination, reply async, like HTMX, optimistic UI markup, rate limiting,
integrasi achievement, serta data seed. Coverage ini mengukur kode Python;
perilaku JavaScript browser tetap diverifikasi melalui pengujian manual UI.

## Rute

| Rute | Keterangan |
| --- | --- |
| `/community/` | Feed thread dan filter kategori |
| `/community/new/` | Membuat thread |
| `/community/<id>/` | Detail thread dan balasan |
| `/community/<id>/edit/` | Mengubah thread sendiri |
| `/community/<id>/delete/` | Menghapus thread sendiri |
| `/community/<id>/like/` | Aksi like/unlike via POST |
| `/community/threads.json/` | Data feed thread dalam JSON |

Endpoint JSON mendukung parameter `category`, `author`, dan `page`. Contoh:

```text
/community/threads.json/?category=tips&page=1
```

## Aturan data

- Thread biasa hanya dapat memakai kategori `tips` atau `general`.
- Kategori `achievement` hanya dibuat oleh layanan Dashboard dan selalu
  ditandai sebagai post otomatis.
- Thread memiliki batas isi 5.000 karakter; balasan 2.000 karakter.
- Satu pengguna hanya dapat memberi satu apresiasi pada satu thread.
- Post otomatis tidak dapat diedit lewat Community.

## Integrasi Dashboard

Dashboard menjadi pemilik `UserAchievement`. Setelah penghargaan tersimpan,
Dashboard dapat memanggil fungsi berikut:

```python
from community.services import publish_achievement

thread = publish_achievement(user_achievement=award)
```

`award` harus berupa instance tersimpan dari `dashboard.UserAchievement`.
Fungsi ini bersifat idempoten: pemanggilan ulang untuk achievement yang sama
mengembalikan thread yang sudah ada. Jika pengguna menonaktifkan opsi
`share_achievements`, fungsi mengembalikan `None` dan tidak membuat post.

Integrasi ini adalah fungsi internal, bukan endpoint publik. Dashboard tetap
bertanggung jawab memastikan achievement memang sah sebelum memanggilnya.

