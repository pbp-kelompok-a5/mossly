"""Tanggal perjalanan mengikuti Jakarta tanpa mengubah timezone modul lain."""
from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.utils import timezone

JAKARTA = ZoneInfo('Asia/Jakarta')


def local_date(value):
    """Ubah waktu tersimpan menjadi tanggal lokal Jakarta."""
    return value.astimezone(JAKARTA).date()


def today():
    """Ambil tanggal hari ini di Jakarta untuk batas dan nilai awal form."""
    return local_date(timezone.now())


def at_start_of_day(value):
    """Simpan tanggal pilihan sebagai awal hari di Jakarta."""
    # Form PRD meminta tanggal, bukan jam; simpan sebagai awal hari di Jakarta.
    return datetime.combine(value, time.min, tzinfo=JAKARTA)
