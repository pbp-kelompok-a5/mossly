# Product Requirements Document (PRD)
## Sustainability Community

| Informasi | Keterangan |
|---|---|
| **Nama modul** | Sustainability Community |
| **Penanggung jawab** | Isybal Sama Eleazar Malau |
| **Deskripsi** | Forum sosial untuk berbagi tips, pengalaman, dan pencapaian seputar gaya hidup berkelanjutan. |
| **Integrasi** | Modul Login dan Personal Sustainability Dashboard |
| **Status dokumen** | Draft |

## 1. Latar Belakang

Pengguna membutuhkan ruang untuk saling berbagi informasi dan pengalaman dalam menerapkan gaya hidup berkelanjutan. Melalui Sustainability Community, pengguna dapat membuat diskusi, memberikan tanggapan, serta mengapresiasi kontribusi pengguna lain. Modul ini juga menampilkan pencapaian pengguna secara otomatis agar dapat menjadi sumber motivasi bagi komunitas.

## 2. Tujuan Produk

1. Memfasilitasi pertukaran tips dan pengalaman mengenai gaya hidup berkelanjutan.
2. Mendorong interaksi antar pengguna melalui thread, reply, dan like.
3. Mempermudah pencarian diskusi berdasarkan kategori.
4. Menghubungkan pencapaian pada Personal Sustainability Dashboard dengan aktivitas komunitas.

## 3. Target Pengguna

Pengguna aplikasi yang ingin berbagi pengalaman, mencari tips, mengikuti diskusi, atau membagikan pencapaian terkait keberlanjutan.

**Asumsi untuk versi awal:** seluruh fitur komunitas hanya dapat diakses setelah pengguna login.

## 4. Ruang Lingkup

### Dalam Ruang Lingkup

- Menampilkan daftar dan detail thread.
- Membuat, mengedit, serta menghapus thread milik sendiri.
- Memberikan reply pada thread.
- Memberikan dan membatalkan like pada thread.
- Mengelompokkan dan memfilter thread berdasarkan kategori.
- Menampilkan nama dan avatar penulis berdasarkan `user_id` dari modul Login.
- Membuat post otomatis ketika pengguna memperoleh achievement baru.

### Di Luar Ruang Lingkup Versi Awal

- Pesan pribadi antar pengguna.
- Follow/unfollow pengguna.
- Unggah gambar atau video pada thread.
- Reply bertingkat.
- Sistem pelaporan dan moderasi konten.
- Notifikasi aktivitas komunitas.

**Batasan rancangan:** like/unlike pada versi awal diterapkan pada thread. Pengeditan dan penghapusan reply belum termasuk karena tidak disebutkan dalam deskripsi modul.

## 5. User Stories

| ID | User Story |
|---|---|
| US-01 | Sebagai pengguna, saya ingin melihat daftar thread agar dapat menemukan tips dan pengalaman pengguna lain. |
| US-02 | Sebagai pengguna, saya ingin membuat thread agar dapat membagikan informasi atau pengalaman saya. |
| US-03 | Sebagai penulis, saya ingin mengedit thread saya agar dapat memperbaiki informasi yang saya bagikan. |
| US-04 | Sebagai penulis, saya ingin menghapus thread saya jika sudah tidak ingin menampilkannya. |
| US-05 | Sebagai pengguna, saya ingin memberikan reply agar dapat berpartisipasi dalam diskusi. |
| US-06 | Sebagai pengguna, saya ingin memberi atau membatalkan like agar dapat mengatur apresiasi saya terhadap suatu thread. |
| US-07 | Sebagai pengguna, saya ingin memfilter thread berdasarkan kategori agar lebih mudah menemukan topik yang relevan. |
| US-08 | Sebagai pengguna, saya ingin melihat nama dan avatar penulis agar mengetahui siapa yang membuat thread atau reply. |
| US-09 | Sebagai pengguna yang memperoleh achievement, saya ingin pencapaian tersebut muncul otomatis di komunitas agar dapat dibagikan kepada pengguna lain. |

## 6. Kebutuhan Fungsional

| ID | Fitur | Kebutuhan Sistem | Prioritas |
|---|---|---|---|
| FR-01 | Daftar thread | Sistem menampilkan thread dengan judul, ringkasan isi, kategori, identitas penulis, waktu publikasi, jumlah like, dan jumlah reply. Urutan awal adalah terbaru. | Must |
| FR-02 | Detail thread | Sistem menampilkan isi lengkap thread beserta seluruh reply dan status like pengguna yang sedang login. | Must |
| FR-03 | Membuat thread | Pengguna dapat membuat thread dengan mengisi judul, isi, dan kategori. Sistem menetapkan penulis berdasarkan akun yang sedang login. | Must |
| FR-04 | Mengedit thread | Pengguna hanya dapat mengubah judul, isi, dan kategori thread manual miliknya sendiri. | Must |
| FR-05 | Menghapus thread | Pengguna hanya dapat menghapus thread miliknya sendiri setelah memberikan konfirmasi. | Must |
| FR-06 | Reply | Pengguna dapat menambahkan reply berupa teks pada thread yang masih tersedia. Sistem menampilkan penulis dan waktu pengiriman reply. | Must |
| FR-07 | Like/unlike | Pengguna dapat memberi satu like per thread dan membatalkannya. Jumlah like serta status tombol diperbarui setelah tindakan berhasil. | Must |
| FR-08 | Kategori | Sistem menyediakan kategori `tips`, `achievement`, dan `general`. Pengguna dapat memfilter daftar thread berdasarkan kategori tersebut. | Must |
| FR-09 | Identitas penulis | Nama dan avatar penulis thread maupun reply ditampilkan menggunakan data dari modul Login berdasarkan `user_id`. | Must |
| FR-10 | Post achievement otomatis | Sistem menerima data achievement baru dari Personal Sustainability Dashboard dan membuat thread atas nama pengguna terkait dengan kategori `achievement`. | Must |
| FR-11 | Pencegahan duplikasi | Pengiriman ulang data pencapaian yang sama tidak menghasilkan post otomatis tambahan. | Must |
| FR-12 | Kondisi kosong dan gagal | Sistem menampilkan pesan ketika belum ada thread, hasil filter kosong, atau suatu tindakan gagal diproses. | Must |

## 7. Aturan Bisnis

1. **Kepemilikan konten:** setiap thread dan reply terhubung ke satu `user_id`.
2. **Otorisasi:** hak mengedit dan menghapus thread diperiksa di server, bukan hanya melalui tampilan tombol.
3. **Validasi input:** judul dan isi thread serta isi reply tidak boleh kosong atau hanya berisi spasi.
4. **Kategori:** untuk versi awal, setiap thread memiliki satu kategori.
5. **Like:** kombinasi pengguna dan thread hanya boleh memiliki satu catatan like.
6. **Penghapusan:** ketika thread dihapus, reply dan like terkait ikut dihapus.
7. **Identitas:** pengguna tidak dapat menentukan identitas penulis lain ketika membuat thread atau reply.
8. **Post otomatis:** hanya data pencapaian dari integrasi Dashboard yang dapat menghasilkan post dengan penanda otomatis.
9. **Integritas pencapaian:** usulan untuk versi awal, post achievement otomatis dapat dihapus oleh pemiliknya tetapi isi pencapaiannya tidak dapat diedit melalui Community.
10. **Post yang telah dihapus:** pengiriman ulang event pencapaian yang sama tidak boleh menerbitkan kembali post tersebut.

## 8. Alur Pengguna

### A. Membuat Thread

1. Pengguna login dan membuka halaman Community.
2. Pengguna memilih **Buat Thread**.
3. Pengguna mengisi judul, isi, dan kategori.
4. Pengguna memilih **Publikasikan**.
5. Sistem memvalidasi input dan menyimpan thread.
6. Thread muncul di daftar komunitas dengan identitas pengguna.

### B. Berinteraksi dengan Thread

1. Pengguna memilih thread dari daftar.
2. Sistem menampilkan detail thread dan reply.
3. Pengguna dapat memberikan reply atau menekan tombol **Like**.
4. Pengguna yang sudah memberi like dapat menekan tombol tersebut kembali untuk melakukan unlike.

### C. Mengelola Thread Sendiri

1. Pengguna membuka thread miliknya.
2. Pengguna memilih **Edit** atau **Hapus**.
3. Untuk edit, sistem menyimpan perubahan setelah input valid.
4. Untuk hapus, sistem meminta konfirmasi sebelum menghapus thread beserta interaksinya.

### D. Publikasi Achievement Otomatis

1. Pengguna mendapatkan achievement baru pada Personal Sustainability Dashboard.
2. Dashboard mengirim data pencapaian ke Community.
3. Community memvalidasi pengguna, data pencapaian, dan keunikan event.
4. Sistem membuat thread kategori `achievement` dengan penanda **Post Otomatis**.
5. Thread tampil pada daftar komunitas dan dapat menerima reply serta like.

## 9. Kebutuhan Data dan Integrasi

### Data Utama

| Entitas | Atribut Utama |
|---|---|
| **Thread** | `thread_id`, `user_id`, `title`, `content`, `category`, `source`, `achievement_event_id` jika otomatis, `created_at`, `updated_at` |
| **Reply** | `reply_id`, `thread_id`, `user_id`, `content`, `created_at` |
| **Like** | `like_id`, `thread_id`, `user_id`, `created_at` |
| **Catatan event achievement** | `event_id`, `user_id`, `achievement_id`, `processed_at`, referensi thread jika masih tersedia |

### Integrasi Antar Modul

| Modul | Data yang Dibutuhkan | Penggunaan |
|---|---|---|
| Login | `user_id`, nama, avatar, status autentikasi | Memastikan identitas dan hak akses pengguna serta menampilkan profil penulis. |
| Personal Sustainability Dashboard | ID unik event pencapaian, `user_id`, ID achievement, nama achievement, deskripsi, dan waktu perolehan | Membuat post otomatis dan mencegah penerbitan ganda. |

Format pengiriman data dan mekanisme autentikasi antar modul perlu disepakati bersama pengembang modul terkait. Jika avatar tidak tersedia, sistem menampilkan avatar bawaan.

## 10. Kebutuhan Antarmuka

| Halaman/Komponen | Elemen Utama |
|---|---|
| **Daftar Community** | Tombol Buat Thread, filter kategori, kartu thread, dan navigasi halaman. |
| **Kartu Thread** | Judul, ringkasan, nama dan avatar penulis, kategori, waktu publikasi, jumlah like, serta jumlah reply. |
| **Detail Thread** | Isi lengkap, tombol like/unlike, daftar reply, formulir reply, serta tombol edit/hapus bagi pemilik yang berhak. |
| **Formulir Thread** | Input judul, isi, pilihan kategori, tombol simpan/publikasikan, dan tombol batal. |
| **Konfirmasi Hapus** | Penjelasan bahwa thread beserta interaksinya akan dihapus, tombol hapus, dan tombol batal. |
| **Post Achievement** | Penanda Post Otomatis, identitas pengguna, nama achievement, dan informasi pencapaian. |

## 11. Kebutuhan Nonfungsional

| Aspek | Kebutuhan |
|---|---|
| **Keamanan** | Sistem memeriksa autentikasi dan otorisasi setiap operasi, melindungi permintaan perubahan data dari CSRF, serta menampilkan konten pengguna dengan aman untuk mencegah XSS. |
| **Integritas data** | Sistem mencegah like ganda, post otomatis ganda, dan konten yang mengacu pada pengguna atau thread yang tidak valid. |
| **Kinerja** | Daftar thread menggunakan pagination agar tidak memuat seluruh konten sekaligus. Target waktu respons ditetapkan setelah lingkungan pengujian disepakati. |
| **Usability** | Sistem memberikan pesan validasi dan hasil tindakan yang jelas, serta mempertahankan input ketika penyimpanan gagal. |
| **Responsivitas** | Halaman dapat digunakan pada perangkat desktop maupun ponsel. |
| **Keandalan integrasi** | Kegagalan pemrosesan achievement dicatat dan dapat dicoba ulang tanpa menghasilkan post duplikat. |

## 12. Acceptance Criteria

| ID | Skenario | Kriteria Penerimaan |
|---|---|---|
| AC-01 | Membuat thread | Ketika pengguna mengirim judul, isi, dan kategori yang valid, thread tersimpan atas nama pengguna tersebut dan muncul pada daftar. |
| AC-02 | Input tidak valid | Ketika judul, isi, atau reply kosong, sistem menolak penyimpanan dan menampilkan pesan validasi. |
| AC-03 | Mengedit thread sendiri | Perubahan valid pada thread manual milik pengguna tersimpan dan tampil pada detail thread. |
| AC-04 | Mengubah thread orang lain | Permintaan edit atau hapus terhadap thread pengguna lain ditolak, termasuk ketika dikirim langsung ke server. |
| AC-05 | Menghapus thread | Setelah konfirmasi, thread beserta reply dan like terkait tidak lagi tersedia. |
| AC-06 | Mengirim reply | Reply yang valid muncul pada thread dengan nama, avatar, dan waktu pengiriman yang sesuai. |
| AC-07 | Like/unlike | Like menambah jumlah sebesar satu; unlike menguranginya sebesar satu. Permintaan berulang tidak menghasilkan like ganda. |
| AC-08 | Filter kategori | Ketika kategori dipilih, daftar hanya menampilkan thread dengan kategori tersebut. |
| AC-09 | Identitas penulis | Nama dan avatar pada thread/reply sesuai dengan `user_id` penulis dari modul Login. |
| AC-10 | Achievement baru | Data pencapaian yang valid menghasilkan satu post otomatis dengan kategori `achievement` dan pemilik yang sesuai. |
| AC-11 | Event duplikat | Pengiriman ulang event yang sudah diproses tidak menghasilkan post baru, termasuk jika post sebelumnya telah dihapus. |
| AC-12 | Belum login | Pengguna yang belum login diarahkan ke halaman Login saat mengakses Community sesuai asumsi akses versi awal. |

## 13. Indikator Keberhasilan

Keberhasilan modul dapat dipantau melalui:

- Jumlah pengguna unik yang membuat thread, reply, atau like.
- Jumlah thread dan reply yang dipublikasikan.
- Persentase thread yang memperoleh setidaknya satu interaksi.
- Persentase event achievement valid yang berhasil menghasilkan post.
- Jumlah post otomatis duplikat, dengan target **nol**.

Target numerik untuk partisipasi pengguna ditentukan setelah tersedia data penggunaan awal.

