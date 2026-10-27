"""Indonesian labels and formatting for the habit pages.

The project runs with LANGUAGE_CODE "en-us", so day and month names are kept
here instead of relying on Django's locale formatting.
"""

from .models import Habit
from .services import STREAK_MILESTONES

DAY_NAMES = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
DAY_SHORT = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
MONTH_NAMES = (
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
)
MONTH_SHORT = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")

# Badge names the Dashboard plans for each streak milestone.
MILESTONE_BADGES = {3: "Spora", 7: "Tunas", 14: "Lumut Muda", 30: "Hamparan Lumut"}

# Each icon option in the form comes with a fixed tint, as in the design.
ICON_TINTS = {
    Habit.Icon.CUP_SODA: Habit.Tint.MOSS_200,
    Habit.Icon.TRAIN_FRONT: Habit.Tint.CLAY_100,
    Habit.Icon.RECYCLE: Habit.Tint.MOSS_200,
    Habit.Icon.SHOPPING_BAG: Habit.Tint.MOSS_100,
    Habit.Icon.DROPLET: Habit.Tint.PINK_100,
    Habit.Icon.LIGHTBULB: Habit.Tint.CLAY_100,
    Habit.Icon.LEAF: Habit.Tint.PINK_200,
    Habit.Icon.UTENSILS: Habit.Tint.PINK_200,
}

TIME_OF_DAY_ICONS = {
    Habit.TimeOfDay.PAGI: "sun",
    Habit.TimeOfDay.SIANG: "cloud-sun",
    Habit.TimeOfDay.MALAM: "moon",
    Habit.TimeOfDay.KAPAN_SAJA: "calendar",
}

HABIT_SUGGESTIONS = tuple(
    {"name": name, "hint": hint, "icon": icon, "tint": ICON_TINTS[icon]}
    for name, hint, icon in (
        ("Bawa tumbler", "Kurangi gelas sekali pakai", Habit.Icon.CUP_SODA),
        ("Naik transportasi umum", "Ganti perjalanan motor atau mobil", Habit.Icon.TRAIN_FRONT),
        ("Pilah sampah", "Pisahkan organik dan anorganik", Habit.Icon.RECYCLE),
        ("Bawa tas belanja sendiri", "Tolak kantong plastik di kasir", Habit.Icon.SHOPPING_BAG),
    )
)


def long_date(day):
    """'Rabu, 21 Oktober 2026'"""
    return f"{DAY_NAMES[day.weekday()]}, {day.day} {MONTH_NAMES[day.month - 1]} {day.year}"


def short_date(day, today):
    """'Hari ini' for today, otherwise '19 Okt'."""
    if day == today:
        return "Hari ini"
    return f"{day.day} {MONTH_SHORT[day.month - 1]}"


def greeting(hour):
    if 4 <= hour < 11:
        return "Selamat pagi"
    if 11 <= hour < 15:
        return "Selamat siang"
    if 15 <= hour < 18:
        return "Selamat sore"
    return "Selamat malam"


def milestone_list_text():
    """'3, 7, 14, atau 30', built from the milestone constant."""
    *rest, last = STREAK_MILESTONES
    return f"{', '.join(str(m) for m in rest)}, atau {last}"
