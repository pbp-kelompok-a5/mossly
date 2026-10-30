from django.conf import settings
from django.db import migrations


TIP_THREADS = [
    (
        "Bawa tumbler ke mana-mana",
        "Simpan tumbler di tas sejak malam. Kebiasaan kecil ini membantu mengurangi gelas plastik sekali pakai.",
    ),
    (
        "Bawa tas belanja lipat",
        "Tas belanja kain yang kecil dan bisa dilipat mudah disimpan di tas. Jadi kita tidak perlu mengambil kantong plastik saat belanja mendadak.",
    ),
    (
        "Pilih isi ulang sabun",
        "Kalau tersedia, pilih sabun, sampo, atau deterjen isi ulang. Kemasan yang dipakai ulang bisa mengurangi sampah rumah tangga.",
    ),
    (
        "Matikan lampu saat ruang kosong",
        "Biasakan mengecek lampu sebelum meninggalkan ruangan. Tidak perlu menunggu tagihan listrik naik untuk mulai hemat energi.",
    ),
    (
        "Cabut charger yang tidak dipakai",
        "Charger yang tetap terhubung masih bisa memakai listrik. Cabut setelah selesai mengisi daya agar penggunaan energi lebih hemat.",
    ),
    (
        "Gunakan botol minum saat bepergian",
        "Isi ulang air minum dari rumah atau stasiun isi ulang. Selain mengurangi sampah botol, cara ini juga lebih hemat.",
    ),
    (
        "Rencanakan menu mingguan",
        "Membuat daftar menu membantu membeli bahan makanan secukupnya dan mencegah makanan terlupakan di kulkas.",
    ),
    (
        "Habiskan makanan sebelum membeli lagi",
        "Cek isi kulkas dan lemari makanan sebelum berbelanja. Gunakan bahan yang hampir habis sebagai menu berikutnya.",
    ),
    (
        "Simpan sisa makanan dengan benar",
        "Pakai wadah tertutup dan beri label tanggal supaya sisa makanan lebih mudah diingat dan tidak cepat terbuang.",
    ),
    (
        "Mulai kompos dari sisa dapur",
        "Kulit buah, ampas kopi, dan daun kering bisa menjadi kompos. Mulai dari wadah kecil di rumah juga tidak apa-apa.",
    ),
    (
        "Pilah sampah dari rumah",
        "Pisahkan sampah organik, anorganik, dan residu. Sampah yang terpilah lebih mudah diteruskan ke bank sampah atau daur ulang.",
    ),
    (
        "Cuci dan keringkan kemasan daur ulang",
        "Kemasan bekas makanan sebaiknya dibilas dan dikeringkan sebelum dikumpulkan agar tidak mengotori bahan daur ulang lain.",
    ),
    (
        "Manfaatkan kedua sisi kertas",
        "Kertas yang hanya terpakai satu sisi masih berguna untuk catatan, daftar belanja, atau coretan belajar.",
    ),
    (
        "Cetak dokumen hanya saat perlu",
        "Gunakan dokumen digital untuk membaca dan memberi komentar. Kalau harus mencetak, pilih dua sisi kertas.",
    ),
    (
        "Bawa alat makan sendiri",
        "Simpan sendok, garpu, atau sedotan pakai ulang di pouch kecil untuk mengurangi alat makan sekali pakai.",
    ),
    (
        "Pilih makan di tempat",
        "Saat memungkinkan, makan di tempat agar tidak membutuhkan wadah dan alat makan sekali pakai tambahan.",
    ),
    (
        "Gunakan transportasi umum untuk rute rutin",
        "Coba cari satu perjalanan mingguan yang bisa diganti dengan bus, KRL, MRT, atau angkutan umum lainnya.",
    ),
    (
        "Jalan kaki untuk jarak dekat",
        "Untuk tujuan yang dekat dan aman, berjalan kaki bisa menjadi pilihan sehat tanpa emisi dari kendaraan.",
    ),
    (
        "Gabungkan beberapa keperluan dalam satu perjalanan",
        "Buat daftar tujuan sebelum berangkat supaya tidak perlu bolak-balik dengan kendaraan untuk urusan yang bisa dilakukan sekaligus.",
    ),
    (
        "Rawat tekanan ban kendaraan",
        "Tekanan ban yang sesuai membantu kendaraan bekerja lebih efisien dan dapat mengurangi konsumsi bahan bakar.",
    ),
    (
        "Pilih kipas sebelum menyalakan AC",
        "Saat cuaca memungkinkan, kipas angin bisa membantu menjaga ruangan tetap nyaman dengan penggunaan listrik lebih rendah.",
    ),
    (
        "Atur suhu AC secukupnya",
        "Suhu sekitar 24 sampai 26 derajat biasanya sudah nyaman. Menjaga suhu tidak terlalu rendah membantu menghemat energi.",
    ),
    (
        "Manfaatkan cahaya matahari",
        "Buka tirai pada pagi dan siang hari agar ruangan mendapat pencahayaan alami sebelum menyalakan lampu.",
    ),
    (
        "Cuci pakaian saat muatan cukup",
        "Menunggu hingga muatan mesin cuci cukup penuh membantu menghemat air dan listrik dibanding mencuci sedikit-sedikit.",
    ),
    (
        "Jemur pakaian bila cuaca cerah",
        "Menjemur pakaian di bawah matahari mengurangi kebutuhan pengering dan membuat pakaian cepat kering secara alami.",
    ),
    (
        "Gunakan mode hemat energi",
        "Aktifkan mode hemat daya di laptop, ponsel, atau perangkat lain ketika tidak membutuhkan performa penuh.",
    ),
    (
        "Perbaiki barang sebelum membeli baru",
        "Cek apakah barang rusak masih bisa diperbaiki. Menjahit kancing, mengganti baterai, atau servis kecil sering kali sudah cukup.",
    ),
    (
        "Pinjam atau sewa barang yang jarang dipakai",
        "Untuk alat yang hanya dipakai sesekali, meminjam dari teman atau menyewa bisa lebih efisien daripada membeli baru.",
    ),
    (
        "Belanja barang bekas berkualitas",
        "Buku, pakaian, furnitur, dan perlengkapan tertentu bisa dicari dalam kondisi bekas yang masih sangat layak pakai.",
    ),
    (
        "Pilih produk dengan kemasan minim",
        "Bandingkan produk sejenis dan pilih yang kemasannya lebih sedikit atau mudah didaur ulang.",
    ),
    (
        "Simpan toples kaca bekas",
        "Toples bekas selai atau bumbu bisa dicuci dan digunakan lagi untuk menyimpan bahan makanan atau barang kecil.",
    ),
    (
        "Bawa wadah saat membeli makanan",
        "Kalau membeli makanan untuk dibawa pulang, coba gunakan wadah sendiri agar tidak menambah kemasan sekali pakai.",
    ),
    (
        "Gunakan saputangan kain",
        "Saputangan kain dapat dipakai berulang untuk keperluan sederhana dan mengurangi penggunaan tisu sekali pakai.",
    ),
    (
        "Kurangi belanja impulsif",
        "Tunggu satu atau dua hari sebelum membeli barang nonmendesak. Sering kali kita sadar barang tersebut belum benar-benar diperlukan.",
    ),
    (
        "Rawat tanaman di rumah",
        "Merawat satu tanaman bisa menjadi pengingat kecil untuk memperhatikan air, cahaya, dan lingkungan sekitar setiap hari.",
    ),
    (
        "Gunakan sisa air untuk menyiram",
        "Air sisa mencuci sayur yang tidak memakai sabun dapat dimanfaatkan untuk menyiram tanaman.",
    ),
    (
        "Buat daftar belanja",
        "Daftar belanja membantu fokus membeli kebutuhan dan mengurangi makanan atau barang yang akhirnya tidak terpakai.",
    ),
    (
        "Pilih buah dan sayur lokal",
        "Produk lokal biasanya menempuh perjalanan distribusi yang lebih singkat dan sering kali lebih segar saat dibeli.",
    ),
    (
        "Bawa kotak makan dari rumah",
        "Membawa bekal mengurangi kemasan makanan sekali pakai sekaligus memudahkan mengatur porsi makan.",
    ),
    (
        "Bagikan barang yang masih layak",
        "Pakaian, buku, atau peralatan yang tidak dipakai bisa disumbangkan atau dibagikan kepada orang yang membutuhkannya.",
    ),
    (
        "Gunakan aplikasi tiket digital",
        "Pilih tiket dan bukti pembayaran digital jika tersedia agar penggunaan kertas dapat berkurang.",
    ),
    (
        "Kurangi notifikasi yang tidak penting",
        "Mengurangi notifikasi membuat kita lebih jarang membuka perangkat tanpa tujuan dan membantu kebiasaan digital lebih sadar.",
    ),
    (
        "Matikan perangkat saat malam",
        "Perangkat yang tidak dipakai semalaman sebaiknya dimatikan atau masuk mode hemat daya bila memungkinkan.",
    ),
    (
        "Beri hadiah pengalaman",
        "Untuk momen tertentu, hadiah berupa waktu bersama, kelas, atau pengalaman dapat menjadi alternatif dari barang baru.",
    ),
    (
        "Bawa botol dan tas saat acara",
        "Sebelum datang ke acara, siapkan botol minum dan tas lipat agar lebih siap menolak barang sekali pakai.",
    ),
    (
        "Ajak teman memulai kebiasaan hijau",
        "Ceritakan satu kebiasaan kecil yang berhasil kamu lakukan. Ajakan sederhana bisa membuat perubahan terasa lebih menyenangkan.",
    ),
    (
        "Catat satu langkah hijau setiap minggu",
        "Menulis langkah kecil yang sudah dilakukan membantu melihat progres dan menemukan kebiasaan mana yang ingin dilanjutkan.",
    ),
    (
        "Ikut bank sampah di lingkungan",
        "Cari informasi bank sampah terdekat dan mulai kumpulkan material yang mereka terima dari rumah.",
    ),
    (
        "Tolak brosur yang tidak diperlukan",
        "Kalau tidak membutuhkan brosur atau struk kertas, sampaikan dengan sopan bahwa kamu tidak perlu menerimanya.",
    ),
    (
        "Rayakan progres kecil",
        "Perubahan berkelanjutan tidak harus sempurna. Apresiasi kebiasaan kecil yang berhasil dilakukan agar tetap konsisten.",
    ),
]


def seed_tip_threads(apps, schema_editor):
    user_app, user_model = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(user_app, user_model)
    Profile = apps.get_model("accounts", "UserProfile")
    Thread = apps.get_model("community", "Thread")
    database = schema_editor.connection.alias

    author, _ = User.objects.using(database).get_or_create(
        username="mossly_friend",
        defaults={"password": "!", "is_active": False},
    )
    Profile.objects.using(database).get_or_create(
        user_id=author.pk,
        defaults={
            "display_name": "Mossly Friend",
            "avatar": "sprout",
            "share_achievements": False,
        },
    )

    for title, body in TIP_THREADS:
        Thread.objects.using(database).get_or_create(
            author_id=author.pk,
            title=title,
            defaults={
                "body": body,
                "category": "tips",
                "is_auto_post": False,
            },
        )


def unseed_tip_threads(apps, schema_editor):
    Thread = apps.get_model("community", "Thread")
    database = schema_editor.connection.alias
    titles = [title for title, _ in TIP_THREADS]
    Thread.objects.using(database).filter(
        author__username="mossly_friend",
        title__in=titles,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_existing_user_profiles"),
        ("community", "0003_align_community_erd"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [migrations.RunPython(seed_tip_threads, unseed_tip_threads)]
