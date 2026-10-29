"""Indonesian labels and formatting for the habit pages.

The project runs with LANGUAGE_CODE "en-us", so day and month names are kept
here instead of relying on Django's locale formatting.
"""

from decimal import Decimal

from django.utils import timezone

from .models import Goal, Habit
from .services import STREAK_MILESTONES

DAY_NAMES = ("Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu")
DAY_SHORT = ("Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min")
DAY_INITIALS = ("S", "S", "R", "K", "J", "S", "M")
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


# Short unit for "15 / 20 kali"; the full label ("kg CO2e") is used for targets.
UNIT_SHORT = {Goal.Unit.KALI: "kali", Goal.Unit.HARI: "hari", Goal.Unit.KG_CO2E: "kg"}

# Example goals in the empty state; "days" fills the deadline from today.
GOAL_SUGGESTIONS = (
    {"title": "Naik transportasi umum 20 kali", "hint": "Target 1 bulan · 20 kali", "icon": "target",
     "tint": "clay-100", "category": Goal.Category.TRANSPORTASI, "target": 20, "unit": Goal.Unit.KALI, "days": 30},
    {"title": "30 hari tanpa botol plastik", "hint": "Target 30 hari · harian", "icon": "glass-water",
     "tint": "moss-200", "category": Goal.Category.PLASTIK, "target": 30, "unit": Goal.Unit.HARI, "days": 30},
    {"title": "Kurangi emisi perjalanan 10 kg", "hint": "Target 1 bulan · kg CO2e", "icon": "leaf",
     "tint": "moss-100", "category": Goal.Category.EMISI, "target": 10, "unit": Goal.Unit.KG_CO2E, "days": 30},
    {"title": "Ikut 1 aksi bersih lingkungan", "hint": "Target 1 kegiatan", "icon": "handshake",
     "tint": "pink-100", "category": Goal.Category.KOMUNITAS, "target": 1, "unit": Goal.Unit.KALI, "days": 30},
)


AMOUNT_PROMPTS = {
    Goal.Unit.KALI: "Tambah berapa kali?",
    Goal.Unit.HARI: "Tambah berapa hari?",
    Goal.Unit.KG_CO2E: "Tambah berapa kg CO2e?",
}


def join_names(names):
    """'A', 'A dan B', 'A, B, dan C'."""
    names = list(names)
    if len(names) <= 2:
        return " dan ".join(names)
    return f"{', '.join(names[:-1])}, dan {names[-1]}"


def day_month_long(day):
    """'18 Oktober'"""
    return f"{day.day} {MONTH_NAMES[day.month - 1]}"


def full_date(day):
    """'1 Oktober 2026'"""
    return f"{day.day} {MONTH_NAMES[day.month - 1]} {day.year}"


def clock(moment):
    """'07.45' in local time."""
    return timezone.localtime(moment).strftime("%H.%M")


def frequency_text(habit):
    """'Setiap hari' or 'Sen, Rab, Jum'."""
    if habit.frequency_type == Habit.Frequency.WEEKDAYS:
        return ", ".join(DAY_SHORT[d] for d in sorted(habit.weekday_numbers))
    return "Setiap hari"

def day_month(day):
    """'31 Okt'"""
    return f"{day.day} {MONTH_SHORT[day.month - 1]}"


def format_amount(value):
    """'2,5' or '20': Indonesian decimal comma, no trailing zeros."""
    value = Decimal(value)
    if value == value.to_integral_value():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").replace(".", ",")


def format_rate(value):
    """'0,5' with one decimal, for amounts per day."""
    return f"{Decimal(value):.1f}".replace(".", ",")


def date_range(start, end, with_year=False):
    """'1–31 Oktober' within a month, otherwise '16 Okt–15 Nov'."""
    year = f" {end.year}" if with_year else ""
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{end.day} {MONTH_NAMES[end.month - 1]}{year}"
    return f"{start.day} {MONTH_SHORT[start.month - 1]}–{end.day} {MONTH_SHORT[end.month - 1]}{year}"


def relative_date(day, today):
    """'Hari ini', 'Kemarin', otherwise '19 Okt'."""
    if (today - day).days == 1:
        return "Kemarin"
    return short_date(day, today)


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
