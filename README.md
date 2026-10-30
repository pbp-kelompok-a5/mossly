# 🌳 Mossly
 **Deskripsi singkat**: Mossly merupakan media yang membantu pengguna membangun gaya hidup berkelanjutan melalui pelacakan jejak karbon, pengelolaan kebiasaan, pencapaian personal, dan komunitas. Nama mossly diambil dari kata “moss”, yaitu lumut yang tumbuh secara perlahan namun konsisten, sebagai simbol bahwa perubahan menuju kehidupan yang lebih berkelanjutan dapat dimulai dari langkah kecil.

 Mossly menyediakan `Carbon Footprint Tracker` untuk memantau emisi transportasi, `Sustainable Habit & Goal Tracker` untuk membangun kebiasaan dan mencapai target, `Personal Sustainability Dashboard` untuk melihat perkembangan pengguna, serta `Sustainability Community` sebagai ruang berbagi tips dan pencapaian. 
 
 Bumi tidak membutuhkan perubahan yang sempurna, melainkan langkah kecil yang terus bertumbuh. Bersama mossly, setiap kebiasaan kecil menjadi bagian dari perjalanan menuju kehidupan yang lebih berkelanjutan.




## 👥 Kelompok A-05
- *[Fildza Hasnalia Nabila](https://github.com/fildzasnaliaa) - 2506625003*
- [Sheva Aquila Mahardika](https://github.com/sheva48) - 2506622033
- [Tania Ju](https://github.com/tanniajju) - 2506608123
- [Callysta Arviana](https://github.com/callystaarviana-coder) - 2506619045
- [Isybal Sama Eleazar Malau](https://github.com/eleazarmalau) - 2506623963

## 🧩 Modul
1. **Login & Onboarding**
*Dikerjakan oleh Sheva Aquila Mahardika*
Modul ini menangani registrasi, login, logout, serta session/cookie management untuk menjaga status autentikasi pengguna. Tersedia juga *onboarding form* setelah menyelesaikan registrasi untuk menyesuaikan data awal untuk input bagian tracker nantinya. Modul ini juga akan menyediakan data identitas yang diambil untuk tampilan di modul *Sustainability Community*.
2. **Carbon Footprint Tracker**
*Dikerjakan oleh Callysta Arviana*
Modul ini memungkinkan pengguna mencatat perjalanan sehari-hari dan menghitung estimasi emisi karbon yang dihasilkan. Pengguna memasukkan titik asal dan tujuan, yang kemudian diproses melalui public API sehingga jarak tempuh dihitung otomatis, bukan diinput manual. Jarak tersebut dikalikan dengan faktor emisi sesuai moda transportasi yang dipilih untuk menghasilkan estimasi emisi CO2 per perjalanan. Seluruh riwayat perjalanan kemudian disimpan dan diterima sebagai track mentah (bukan visualisasi).
3. **Sustainable Habit & Goal Tracker**
*Dikerjakan oleh Tania Ju*
Modul ini membantu pengguna membangun kebiasaan berkelanjutan sekaligus mencapai target spesifik, menjadi dua bagian yang saling melengkapi. Pada bagian Habit, pengguna mencatat kebiasaan harian yang bersifat recurring seperti membawa tumbler, menggunakan transportasi umum, atau memilah sampah. Pada bagian Goal, pengguna dapat membuat target dengan deadline tertentu (misalnya "naik transportasi umum 20 kali dalam sebulan") beserta checklist dan progress bar untuk memantau penyelesaiannya. Setiap kali sebuah goal selesai atau sebuah habit mencapai milestone streak tertentu, modul ini mengirimkan event ke *Personal Sustainability Dashboard* agar dapat direkap dan dievaluasi sebagai bagian dari pencapaian keseluruhan pengguna.
4. **Sustainability Community**
*Dikerjakan oleh Isybal Sama Eleazar Malau*
Modul ini menyediakan forum sosial tempat pengguna berbagi tips dan pengalaman seputar gaya hidup berkelanjutan. Pengguna dapat membuat, mengedit, dan menghapus *thread* miliknya sendiri, memberikan reply pada *thread* orang lain, serta memberi like/unlike. Setiap *thread* dapat diberi tag/kategori (misalnya tips, achievement, atau general) untuk memudahkan navigasi. Nama dan avatar penulis pada setiap thread/reply diambil dari modul *Login* berdasarkan *user_id.* Modul ini juga menampilkan post otomatis saat pengguna meraih achievement baru, dengan data pencapaian yang dikirim langsung dari modul *Personal Sustainability Dashboard*.
5. **Personal Sustainability Dashboard**
*Dikerjakan oleh Fildza Hasnalia Nabila*
Modul ini berfungsi sebagai halaman rekap terpusat ("Me"/Profile) yang mengagregasi data dari seluruh modul lain: total emisi dari *Carbon Footprint Tracker*, kebiasaan dan progress goal dari *Sustainable Habit & Goal Tracker*, serta aktivitas dari *Sustainability Community*. Modul ini menjadi pemilik utama logika penentuan achievement/badge dan memicu event ke modul Community setiap kali pengguna meraih pencapaian baru. Ringkasan aktivitas ditampilkan dalam bentuk visualisasi yang lebih mudah dibaca user.

## 📊 Sumber/Dokumentasi API
### Geoapify — Carbon Footprint Tracker
Modul *Carbon Footprint Tracker* akan menggunakan **Geoapify**, layanan API lokasi dan rute berbasis data terbuka, termasuk OpenStreetMap, dengan cakupan global yang mencakup Indonesia. API ini digunakan untuk mencari titik asal dan tujuan serta menghitung jarak tempuh secara otomatis sesuai profil moda transportasi yang tersedia.

- **Geocoding API** (`GET https://api.geoapify.com/v1/geocode/search`): mengubah nama tempat/alamat menjadi koordinat latitude dan longitude. Pencarian akan dibatasi ke Indonesia menggunakan parameter `filter=countrycode:id`, kemudian pengguna memilih lokasi yang sesuai.
- **Routing API** (`GET https://api.geoapify.com/v1/routing`): menerima koordinat asal–tujuan melalui parameter `waypoints` dan profil transportasi melalui `mode`, lalu mengembalikan jarak, estimasi durasi, serta geometri rute dalam JSON/GeoJSON. Parameter `units=metric` digunakan agar jarak diterima dalam meter, kemudian dikonversi menjadi kilometer. Profil yang tersedia antara lain `drive`, `motorcycle`, `bicycle`, dan `walk`. Dukungan transportasi umum bergantung pada ketersediaan data lokal dan akan diuji sebelum digunakan; jarak rute kendaraan jalan tidak akan dianggap sebagai jarak perjalanan kereta.
- **Perhitungan dan penyimpanan**: Geoapify menyediakan data lokasi dan rute, bukan nilai emisi karbon. Estimasi emisi dihitung oleh modul dengan rumus **jarak (km) × faktor emisi sesuai moda transportasi**. Sumber, satuan, dan versi faktor emisi akan didokumentasikan saat ditetapkan. Data perjalanan dan hasil perhitungan disimpan sebagai riwayat mentah untuk digunakan oleh *Personal Sustainability Dashboard*.
- **Akses API**: request memerlukan API key melalui parameter `apiKey`. Key akan disimpan dalam environment variable di backend Django. Geoapify menyediakan paket gratis dengan kuota 3.000 kredit per hari yang digunakan bersama oleh layanan API; biaya kredit bergantung pada jenis request. Penggunaan akan mengikuti ketentuan layanan dan menyertakan atribusi Geoapify serta sumber data terkait.

**Referensi resmi:** [Geoapify](https://www.geoapify.com/) · [Dokumentasi Geocoding API](https://apidocs.geoapify.com/docs/geocoding/) · [Dokumentasi Routing API](https://apidocs.geoapify.com/docs/routing/) · [Routing Playground (uji rute)](https://apidocs.geoapify.com/playground/routing/) · [Kuota dan paket layanan](https://www.geoapify.com/pricing/) · [Ketentuan layanan](https://www.geoapify.com/terms-and-conditions/)

## 💻 Role User
- **Pengunjung (belum login)**: Hanya dapat membuka landing page, registrasi, dan login. Halaman lain mengarahkan ke login.
- **User (sudah login)**: User dapat melakukan registrasi, login, serta mengelola profil pribadi mereka. Mereka bisa mencatat perjalanan sehari-hari (moda transportasi, titik asal-tujuan) untuk melacak estimasi emisi karbon yang dihasilkan, serta meninjau kembali riwayat perjalanan yang telah dicatat. User dapat membangun kebiasaan berkelanjutan melalui habit tracker harian dan menetapkan target sustainability dengan deadline melalui goal planner. Pada halaman Dashboard, user dapat memantau grafik tren emisi, progres kebiasaan, serta koleksi achievement/badge yang telah diraih. User juga dapat berinteraksi di Sustainability Community dengan membuat thread, membalas, memberi like, serta berbagi tips dan pencapaian dengan pengguna lain.

## 🔗 URL
- **Figma:** https://www.figma.com/design/xMVSWGoAmsCNbc0IrEX4gX/PBP-LETSGOOO?node-id=1-2&t=x38m96qwHWQtBWqr-1
- **PWS:** https://tania-ju-mossly.pws.cs.ui.ac.id/
- **ERD (acuan kelompok):** https://drive.google.com/file/d/1DkL8-bK6qUz2xriUFbsEyDq_2KBvmosj/view?usp=sharing


## 🤖 AI Disclosure

Setiap anggota menuliskan penggunaan AI pada modulnya masing-masing.

### 1. Login & Onboarding
Cakupan dan strategi prompt. AI yang digunakan adalah ChatGPT Codex. Bantuan AI bersifat substansial: sebagian besar kode tambahan modul Accounts, test, dan pengujian otomatis ditulis serta dijalankan oleh AI. Prompt diberikan bertahap dengan konteks README, ERD kelompok, referensi desain, aturan CSS bersama, screenshot, dan pesan error. Saya meminta persetujuan sebelum keputusan implementasi, lalu meminta penjelasan kode untuk dipelajari sebagai persiapan demo.

AI membantu pada:
- Tampilan responsif halaman login, registrasi, onboarding, dan profil menggunakan token serta komponen CSS kelompok.
- Autentikasi dan session bawaan Django, logout melalui POST+CSRF, validasi form, serta redirect setelah login.
- Model UserProfile, signal pembuatan profil, dan migrasi untuk akun baru maupun akun lama.
- Registrasi dengan login otomatis, onboarding preferensi, edit profil sendiri, dan validasi umur minimal 18 tahun.
- Cek ketersediaan username menggunakan HTMX, endpoint JSON profil pengguna aktif, serta hapus akun dengan password dan konfirmasi.
- Perbaikan konfigurasi CSRF PWS, footer, pemusatan HTMX yang disepakati, serta bantuan Git dan penyusunan pesan PR.
- Penjelasan MVT, alur request, keamanan, pengujian, dan panduan belajar kode.
Pengkritisan dan verifikasi. Hasil AI saya coba dan koreksi berdasarkan kebutuhan modul:
- Tampilan awal belum mengikuti token dan komponen global, sehingga saya memberikan aturan kelompok dan meminta penyesuaian.
- Tautan JSON sempat ditampilkan di halaman profil. Saya meminta penghapusannya karena bersifat teknis dan tidak diperlukan pengguna; endpoint tetap tersedia.
- Error 403 di PWS menunjukkan bahwa pengujian lokal belum membuktikan konfigurasi deployment benar. Perbaikan dilakukan pada trusted origin tanpa menonaktifkan CSRF.
- Validasi email unik masih berada pada jalur registrasi, belum berupa constraint database. Usulan penguatan di database hanya dibahas sebagai contoh kode dan belum diterapkan.
Verifikasi mencakup test Django, pemeriksaan migrasi, dan percobaan alur lokal. Pada pemeriksaan terakhir, 51 test Accounts lolos. Tiga kegagalan Dashboard pada pengujian proyek juga ditemukan pada salinan main bersih dan dilaporkan tanpa mengubah layanan modul tersebut.

Karena sebagian besar test berasal dari AI, hasilnya tidak saya anggap sebagai satu-satunya bukti kebenaran. Interaksi HTMX di browser dan perilaku setelah deployment PWS tetap perlu diverifikasi. Penjelasan AI digunakan sebagai bahan belajar, bukan bukti bahwa seluruh kode ditulis mandiri; saya tetap bertanggung jawab untuk meninjau, memahami, dan menjelaskan implementasi yang dikumpulkan.

### 2. Carbon Footprint Tracker

**Cakupan dan strategi prompt.** AI yang digunakan adalah **ChatGPT Codex**, sebagai asisten pengembangan, bukan pengganti keputusan desain, peninjauan kode, dan pengujian manual. Prompt diberikan bertahap dengan konteks PRD, README, ERD kelompok, referensi Figma, screenshot, pesan error, dan hasil pengujian. Instruksi menekankan kode sederhana dan perubahan yang terbatas pada modul Carbon serta integrasi yang sudah disepakati.

AI membantu pada:

- Penyesuaian model `TransportMode`, `EmissionFactor`, dan `Trip` dengan ERD kelompok.
- CRUD perjalanan, validasi form, dan pembatasan akses berdasarkan pemilik data.
- Integrasi Geoapify melalui backend untuk pencarian alamat, koordinat, dan rute otomatis.
- Perhitungan estimasi emisi CO₂e dari jarak dan faktor emisi yang memiliki sumber serta versi.

**Pengkritisan dan verifikasi.** Saran AI tidak langsung diterapkan:

- Struktur data dan metrik pada PRD awal disesuaikan dengan keputusan kelompok, yaitu ERD, satuan CO₂e, dan respons `404` untuk perjalanan milik pengguna lain.
- Build Tailwind menambahkan banyak dependensi, sehingga `node_modules` dihapus dan hanya CSS hasil build serta konfigurasi yang diperlukan yang dipertahankan.
- Masalah peta `403 Access blocked` tidak terlihat dari pengujian Django dan baru ditemukan lewat pemeriksaan permintaan gambar dan pengaturan referrer di browser.

Verifikasi meliputi pengujian browser (CRUD, filter, dialog, kegagalan API, responsif), Geoapify asli untuk geocoding, reverse geocoding, dan empat profil transportasi, serta pemeriksaan migrasi dan `collectstatic`. Coverage hanya indikator jalur kode yang teruji. Hasil ini berasal dari lingkungan lokal, sehingga konfigurasi dan alur setelah deployment ke PWS tetap perlu diverifikasi manual.

### 3. Sustainable Habit & Goal Tracker

**Cakupan dan strategi prompt.** AI yang digunakan adalah **Claude Code**, sebagai asisten pengembangan. Kebutuhan fitur, arah desain, dan keputusan akhir ditentukan oleh saya, lalu hasilnya saya cek di browser. Prompt diberikan bertahap dengan konteks kode, screenshot tampilan, dan pesan error. Untuk perubahan besar, saya meminta penjelasan risiko dan pilihan terlebih dahulu, lalu mengerjakannya per tahap agar mudah ditinjau dan dibatalkan.

AI membantu pada:

- Pengembangan dan penyesuaian fitur Habit, Goal, dan Riwayat.
- Perbaikan tampilan dan responsivitas halaman.
- Interaksi tanpa reload menggunakan HTMX.
- Perapian dan pembersihan kode.
- Testing: sebagian besar test dan pengujian otomatis ditulis serta dijalankan oleh AI.

**Pengkritisan dan verifikasi.** Hasil AI tetap saya tinjau, coba, dan koreksi:

- Lolos test belum tentu tepat dan nyaman untuk interaksi user, sehingga fitur saya coba langsung di browser dan saya minta perbaikan jika interaksinya kurang sesuai.
- AI dapat salah memahami instruksi, sehingga batasan dan hasil perubahannya perlu diperiksa sebelum diterima.
- Tidak semua saran diterima. Keputusan tampilan dan perilaku fitur disesuaikan dengan kebutuhan modul.

Sebagian besar test dibuat oleh AI, jadi tests ini saya anggap sebagai salah satu indikator, bukan jaminan penuh fitur sudah benar. Sebelum deployment ke PWS, perilaku fitur tetap saya cek kembali. Seluruh implementasi yang dikumpulkan menjadi tanggung jawab saya, termasuk meninjau, memahami, dan menjelaskannya.

### 4. Sustainability Community

**Cakupan dan strategi prompt.** AI yang digunakan adalah **ChatGPT Codex (keluarga model GPT-5)**, sebagai asisten pengembangan, bukan pengganti peninjauan kode dan pengujian manual. Prompt diberikan secara iteratif dengan konteks struktur proyek, file yang relevan, tampilan target, traceback, dan hasil browser. Setiap perubahan dibandingkan lagi dengan kebutuhan Community dan dijalankan melalui test Django agar tetap terbatas pada scope modul.

AI membantu pada:

- Penyesuaian model Thread, Reply, dan ThreadLike dengan ERD, serta alur post pencapaian otomatis.
- Template Community, avatar profil, display name, dan `@username`.
- Endpoint JSON, filter dan pagination async, reply async, serta like/unlike berbasis HTMX dengan animasi dan rollback saat request gagal.
- Pemecahan JavaScript menjadi module, query count berbasis subquery, rate limit, dan migration seed 50 tips.
- Pembacaan traceback, penyusunan test, coverage, dan dokumentasi.

**Pengkritisan dan verifikasi.** Saran AI tidak selalu langsung dapat diterapkan:

- AJAX like awalnya mengirim request ke `[object HTMLInputElement]` karena input bernama `action` menimpa `form.action`. Error ditemukan lewat console browser dan diperbaiki manual dengan `form.getAttribute("action")`.
- Saat kolom `dashboard_userachievement.seen` tidak ada di SQLite lokal, solusi yang aman adalah migration tambahan, bukan mengubah migration yang sudah diterapkan. Perubahan lintas modul seperti ini perlu dikomunikasikan di Pull Request.
- Rate limit memakai Django cache, sehingga deployment dengan banyak proses perlu backend bersama seperti Redis agar batasnya konsisten.

Test Django membuktikan respons backend, status `429`, dan struktur HTML, tetapi tidak sepenuhnya membuktikan animasi, perilaku HTMX, cache static file, atau tampilan responsif. Hal tersebut tetap perlu dicek di browser lokal dan setelah deployment ke PWS.

### 5. Personal Sustainability Dashboard

**Cakupan penggunaan AI dan strategi prompt**

Untuk modul Dashboard, saya memakai **Claude (Anthropic)** asisten pengembangan. Ide fitur, alur, dan tampilan berasal dari saya mengikuti spesifikasi tugas dan desain Figma. Saya memberi konteks berupa kebutuhan tugas, file terkait, dan pesan error secara bertahap, lalu mengarahkan revisinya.

AI membantu pada:
- Pengembangan fitur CRUD target emisi.
- Pengembangan filter badge dengan HTMX.
- Pengembangan penanganan dan penelusuran pesan error.

**Pengkritisan terhadap AI dan verifikasi manual**

Jawaban dan saran dari AI tidak saya anggap pasti benar, sehingga setiap usulannya saya pelajari dan uji sendiri melalui runserver dan python manage.py test dashboard. Salah satu contohnya terjadi setelah model Community berubah, sehingga halaman Dashboard menjadi error. AI hanya menunjukkan bagian yang kemungkinan terdampak, sedangkan penyebab pastinya saya telusuri sendiri dengan membaca model baru tersebut dan mengonfirmasinya kepada pemilik modul Community. Penyesuaian pada kode Dashboard kemudian saya lakukan secara mandiri.