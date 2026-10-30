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

## Menjalankan lokal

Jalankan perintah berikut dari direktori proyek (`mossly/`):

```sh
python manage.py migrate
python manage.py test community
python manage.py runserver
```

Setelah login, Community dapat dibuka di `/community/`.

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
