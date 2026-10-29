from .models import Achievement

C = Achievement.Category

BADGES = [
    ("moss_spore", "Spora", "Streak habit 3 hari", "i-sprout", C.HABIT, 3, "streak_best", "hari streak"),
    ("moss_sprout", "Tunas", "Streak habit 7 hari", "i-sprout", C.HABIT, 7, "streak_best", "hari streak"),
    ("moss_young", "Lumut Muda", "Streak habit 14 hari", "i-sprout", C.HABIT, 14, "streak_best", "hari streak"),
    ("moss_carpet", "Hamparan Lumut", "Streak habit 30 hari", "i-sprout", C.HABIT, 30, "streak_best", "hari streak"),
    ("full_days_7", "Tujuh Hari Penuh", "Menyelesaikan semua habit dalam 7 hari", "i-check", C.HABIT, 7, "perfect_days", "hari penuh"),
    ("first_goal", "Target Pertama", "Menyelesaikan 1 goal", "i-target", C.GOAL, 1, "goals_done", "goal"),
    ("goals_3", "Penepat Janji", "Menyelesaikan 3 goal", "i-target", C.GOAL, 3, "goals_done", "goal"),
    ("early_finish", "Selesai Lebih Awal", "Menyelesaikan goal sebelum deadline", "i-award", C.GOAL, 1, "goals_early", "goal"),
    ("first_trip", "Langkah Pertama", "Mencatat 1 perjalanan", "i-pin", C.CARBON, 1, "trips", "perjalanan"),
    ("light_trips_10", "Jejak Ringan", "10 perjalanan tanpa emisi", "i-leaf", C.CARBON, 10, "light_trips", "perjalanan"),
    ("transit_20", "Penumpang Setia", "20 perjalanan dengan transportasi umum", "i-pin", C.CARBON, 20, "transit_trips", "perjalanan"),
    ("active_km_50", "Pejalan Hijau", "50 km berjalan atau bersepeda", "i-leaf", C.CARBON, 50, "active_km", "km"),
    ("lighter_month", "Bulan Lebih Ringan", "Emisi bulan lalu lebih rendah dari bulan sebelumnya", "i-award", C.CARBON, 1, "lighter_month", "bulan"),
    ("first_thread", "Suara Pertama", "Membuat 1 thread di Komunitas", "i-message", C.COMMUNITY, 1, "threads", "thread"),
    ("tips_3", "Pembawa Tips", "Membagikan 3 thread Tips", "i-message", C.COMMUNITY, 3, "tips", "thread"),
    ("replies_5", "Penyiram Semangat", "Membalas 5 thread", "i-message", C.COMMUNITY, 5, "replies", "balasan"),
    ("liked_thread_10", "Tumbuh Bersama", "Threadmu mendapat 10 like", "i-award", C.COMMUNITY, 10, "likes_received", "like"),
]

METRIC_BY_CODE = {code: metric for code, _, _, _, _, _, metric, _ in BADGES}
UNIT_BY_CODE = {code: unit for code, _, _, _, _, _, _, unit in BADGES}

TONE_BY_CATEGORY = {
    C.HABIT.value: "moss",
    C.GOAL.value: "pink",
    C.CARBON.value: "clay",
    C.COMMUNITY.value: "clay",
}

ACTIVE_MODE_CODES = ("sepeda", "jalan")
TRANSIT_MODE_CODES = ("bus", "kereta")


def ensure_achievements():
    if Achievement.objects.count() >= len(BADGES):
        return
    for code, name, description, icon, category, threshold, _, _ in BADGES:
        Achievement.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "description": description,
                "icon": icon,
                "category": category,
                "threshold": threshold,
            },
        )