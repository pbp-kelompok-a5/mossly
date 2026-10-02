# 🌳 Mossly
 **Deskripsi singkat**: Mossly merupakan media yang membantu pengguna membangun gaya hidup berkelanjutan melalui pelacakan jejak karbon, pengelolaan kebiasaan, pencapaian personal, dan komunitas. Nama mossly diambil dari kata “moss”, yaitu lumut yang tumbuh secara perlahan namun konsisten, sebagai simbol bahwa perubahan menuju kehidupan yang lebih berkelanjutan dapat dimulai dari langkah kecil.

 Mossly menyediakan `Carbon Footprint Tracker` untuk memantau emisi transportasi, `Sustainable Habit & Goal Tracker` untuk membangun kebiasaan dan mencapai target, `Personal Sustainability Dashboard` untuk melihat perkembangan pengguna, serta `Sustainability Community` sebagai ruang berbagi tips dan pencapaian. 
 
 Bumi tidak membutuhkan perubahan yang sempurna, melainkan langkah kecil yang terus bertumbuh. Bersama mossly, setiap kebiasaan kecil menjadi bagian dari perjalanan menuju kehidupan yang lebih berkelanjutan.




## 👥 Kelompok A-05
- *[Fildza Hasnalia Nabila](https://github.com/fildzasnaliaa) - 2506625003* 
- [Sheva Aquila Mahardika](https://github.com/sheva48) - 2506622033  
- [Tania Ju](https://github.com/tanniajju) - 2506608123  
- [Callysta Arviana](https://github.com/callystaarviana-coder) - 2506619045  
- [Isybal Sama Eleazar Malau](https://github.com/https://github.com/eleazarmalau) - 2506623963  

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
Modul ini berfungsi sebagai halaman rekap terpusat ("Me"/Profile) yang mengagregasi data dari seluruh modul lain: total emisi dari *Carbon Footprint Tracker*, kebiasaan dan progress goal dari *Sustainabile Habit & Goal Tracker*, serta aktivitas dari *Sustainability Community*. Modul ini menjadi pemilik utama logika penentuan achievement/badge dan memicu event ke modul Community setiap kali pengguna meraih pencapaian baru. Ringkasan aktivitas ditampilkan dalam bentuk visualisasi yang lebih mudah dibaca user.

## 📊 Sumber/Dokumentasi API
### Geoapify — Carbon Footprint Tracker
Modul *Carbon Footprint Tracker* akan menggunakan **Geoapify**, layanan API lokasi dan rute berbasis data terbuka, termasuk OpenStreetMap, dengan cakupan global yang mencakup Indonesia. API ini digunakan untuk mencari titik asal dan tujuan serta menghitung jarak tempuh secara otomatis sesuai profil moda transportasi yang tersedia.

- **Geocoding API** (`GET https://api.geoapify.com/v1/geocode/search`): mengubah nama tempat/alamat menjadi koordinat latitude dan longitude. Pencarian akan dibatasi ke Indonesia menggunakan parameter `filter=countrycode:id`, kemudian pengguna memilih lokasi yang sesuai.
- **Routing API** (`GET https://api.geoapify.com/v1/routing`): menerima koordinat asal–tujuan melalui parameter `waypoints` dan profil transportasi melalui `mode`, lalu mengembalikan jarak, estimasi durasi, serta geometri rute dalam JSON/GeoJSON. Parameter `units=metric` digunakan agar jarak diterima dalam meter, kemudian dikonversi menjadi kilometer. Profil yang tersedia antara lain `drive`, `motorcycle`, `bicycle`, dan `walk`. Dukungan transportasi umum bergantung pada ketersediaan data lokal dan akan diuji sebelum digunakan; jarak rute kendaraan jalan tidak akan dianggap sebagai jarak perjalanan kereta.
- **Perhitungan dan penyimpanan**: Geoapify menyediakan data lokasi dan rute, bukan nilai emisi karbon. Estimasi emisi dihitung oleh modul dengan rumus **jarak (km) × faktor emisi sesuai moda transportasi**. Sumber, satuan, dan versi faktor emisi akan didokumentasikan saat ditetapkan. Data perjalanan dan hasil perhitungan disimpan sebagai riwayat mentah untuk digunakan oleh *Personal Sustainability Dashboard*.
- **Akses API**: request memerlukan API key melalui parameter `apiKey`. Key akan disimpan dalam environment variable di backend Django. Geoapify menyediakan paket gratis dengan kuota 3.000 kredit per hari yang digunakan bersama oleh layanan API; biaya kredit bergantung pada jenis request. Penggunaan akan mengikuti ketentuan layanan dan menyertakan atribusi Geoapify serta sumber data terkait.

**Referensi resmi:** [Geoapify](https://www.geoapify.com/) · [Dokumentasi Geocoding API](https://apidocs.geoapify.com/docs/geocoding/) · [Dokumentasi Routing API](https://apidocs.geoapify.com/docs/routing/) · [Routing Playground (uji rute)](https://apidocs.geoapify.com/playground/routing/) · [Kuota dan paket layanan](https://www.geoapify.com/pricing/) · [Ketentuan layanan](https://www.geoapify.com/terms-and-conditions/)

## 💻 Role User
- **User**: User dapat melakukan registrasi, login, serta mengelola profil pribadi mereka. Mereka bisa mencatat perjalanan sehari-hari (moda transportasi, titik asal-tujuan) untuk melacak estimasi emisi karbon yang dihasilkan, serta meninjau kembali riwayat perjalanan yang telah dicatat. User dapat membangun kebiasaan berkelanjutan melalui habit tracker harian dan menetapkan target sustainability dengan deadline melalui goal planner. Pada halaman Dashboard, user dapat memantau grafik tren emisi, progres kebiasaan, serta koleksi achievement/badge yang telah diraih. User juga dapat berinteraksi di Sustainability Community dengan membuat thread, membalas, memberi like, serta berbagi tips dan pencapaian dengan pengguna lain.

## 🔗 URL
- **Figma:** https://www.figma.com/design/xMVSWGoAmsCNbc0IrEX4gX/PBP-LETSGOOO?node-id=1-2&t=x38m96qwHWQtBWqr-1
- **PWS:** https://tania-ju-mossly.pws.cs.ui.ac.id/
