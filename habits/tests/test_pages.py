"""Rendered habit pages: tab, forms, milestone celebration."""

from datetime import datetime, timezone as dt_timezone

from django.test import TestCase
from django.urls import reverse

from habits.models import Goal, Habit

from .helpers import TODAY, FrozenClockMixin, days_ago, freeze_time, make_goal, make_habit, make_user


class HabitTabTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("habits:index")

    def test_empty_state_offers_suggestions(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Belum ada kebiasaan. Mulai dari satu langkah kecil.")
        self.assertContains(response, "Tambah habit pertama")
        self.assertContains(response, "Bawa tas belanja sendiri")
        self.assertContains(response, "?name=Bawa%20tumbler&amp;icon=cup-soda")

    def test_hero_counts_and_groups(self):
        done = make_habit(self.user, name="Bawa tumbler", time_of_day="pagi")
        make_habit(self.user, name="Pilah sampah", time_of_day="siang")
        make_habit(self.user, name="Matikan lampu", time_of_day="malam")
        done.checkins.create(checkin_date=TODAY)

        response = self.client.get(self.url)

        self.assertContains(response, "1 dari 3 kebiasaan hijau sudah kamu selesaikan hari ini")
        self.assertContains(response, "Tinggal 2 lagi untuk hari yang sempurna.")
        self.assertContains(response, "Senin, 26 Oktober 2026")
        self.assertContains(response, "Selamat siang, tania")
        self.assertContains(response, 'class="habit-group-title"', count=3)
        self.assertContains(response, "1 dari 1 selesai")
        self.assertContains(response, "Batalkan check-in Bawa tumbler")
        self.assertContains(response, "Check-in Pilah sampah")

    def test_perfect_day_message(self):
        habit = make_habit(self.user)
        habit.checkins.create(checkin_date=TODAY)
        response = self.client.get(self.url)
        self.assertContains(response, "Hari yang sempurna, semua kebiasaan hari ini selesai.")

    def test_new_habit_shows_first_streak_message(self):
        make_habit(self.user, start_date=TODAY)
        response = self.client.get(self.url)
        self.assertContains(response, "Baru dimulai · streak pertamamu mulai hari ini")

    def test_streak_and_next_milestone(self):
        habit = make_habit(self.user, name="Bawa tumbler")
        for n in range(1, 13):  # 12-day streak, today not checked yet
            habit.checkins.create(checkin_date=days_ago(n))
        response = self.client.get(self.url)
        self.assertContains(response, "12 hari berturut-turut")
        self.assertContains(response, "Bawa tumbler, tinggal 2 hari lagi")
        self.assertContains(response, '<progress class="progress" value="12" max="14">')

    def test_all_milestones_reached(self):
        habit = make_habit(self.user)
        for n in range(30):
            habit.checkins.create(checkin_date=days_ago(n))
        self.assertContains(self.client.get(self.url), "Semua milestone tercapai")

    def test_week_strip_statuses(self):
        habit = make_habit(self.user, start_date=days_ago(10))
        other = make_habit(self.user, name="Pilah sampah", start_date=days_ago(10))
        # TODAY is Monday, so the strip is today plus six upcoming days.
        habit.checkins.create(checkin_date=TODAY)
        other.checkins.create(checkin_date=TODAY)
        response = self.client.get(self.url)
        self.assertContains(response, "day-chip-done is-today")
        self.assertContains(response, "day-chip-upcoming", count=6)

    def test_weekday_habit_not_scheduled_today_is_listed_apart(self):
        make_habit(self.user, name="Bersepeda", frequency_type="weekdays", weekdays=[5])
        response = self.client.get(self.url)
        self.assertContains(response, "Tidak dijadwalkan hari ini")
        self.assertContains(response, "Tidak ada kebiasaan terjadwal hari ini")
        self.assertNotContains(response, "Check-in Bersepeda")

    def test_greeting_follows_local_time(self):
        cases = [
            (datetime(2026, 10, 25, 22, 0, tzinfo=dt_timezone.utc), "Selamat pagi"),  # 05:00 WIB
            (datetime(2026, 10, 26, 9, 0, tzinfo=dt_timezone.utc), "Selamat sore"),  # 16:00 WIB
            (datetime(2026, 10, 26, 13, 0, tzinfo=dt_timezone.utc), "Selamat malam"),  # 20:00 WIB
        ]
        make_habit(self.user)
        for instant, text in cases:
            with self.subTest(text=text), freeze_time(instant):
                self.assertContains(self.client.get(self.url), text)

    def test_overdue_goals_are_marked_expired_on_visit(self):
        goal = make_goal(self.user, start_date=days_ago(30), deadline=days_ago(1))
        self.client.get(self.url)
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.EXPIRED)


class MilestoneCelebrationTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.habit = make_habit(self.user, name="Habiskan makanan")
        for n in (2, 1):
            self.habit.checkins.create(checkin_date=days_ago(n))

    def test_milestone_dialog_shows_once_after_check_in(self):
        response = self.client.post(
            reverse("habits:habit_check_in", args=[self.habit.pk]), follow=True
        )
        self.assertContains(response, "3 hari berturut-turut!")
        self.assertContains(response, "Spora")
        self.assertContains(response, "Terkirim ke Personal Dashboard")
        self.assertContains(response, "Habiskan makanan · 3 hari")

        again = self.client.get(reverse("habits:index"))
        self.assertNotContains(again, "3 hari berturut-turut!")

    def test_no_dialog_without_new_milestone(self):
        self.client.post(reverse("habits:habit_check_in", args=[self.habit.pk]), follow=True)
        self.client.post(reverse("habits:habit_undo_check_in", args=[self.habit.pk]), follow=True)
        response = self.client.post(
            reverse("habits:habit_check_in", args=[self.habit.pk]), follow=True
        )
        self.assertNotContains(response, "milestone-dialog")


class HabitFormTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("habits:habit_create")

    ALL_DAYS = [str(d) for d in range(7)]

    def post(self, **fields):
        data = {"name": "Matikan keran", "icon": "droplet", "time_of_day": "malam", "weekdays": self.ALL_DAYS}
        data.update(fields)
        return self.client.post(self.url, data)

    def test_new_form_checks_every_day(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Hari check-in")
        self.assertContains(response, "Ketuk hari untuk memilih atau melewatinya.")
        for day in self.ALL_DAYS:
            self.assertContains(response, f'name="weekdays" value="{day}" checked')

    def test_every_day_checked_is_stored_as_daily(self):
        response = self.post(reminder_time="20:00")
        self.assertRedirects(response, reverse("habits:index"), fetch_redirect_response=False)
        habit = Habit.objects.get()
        self.assertEqual(habit.user, self.user)
        self.assertEqual(habit.tint, "pink-100")
        self.assertEqual(habit.frequency_type, Habit.Frequency.DAILY)
        self.assertIsNone(habit.weekdays)
        self.assertEqual(habit.start_date, TODAY)
        self.assertEqual(habit.reminder_time.strftime("%H:%M"), "20:00")

    def test_some_days_checked_is_stored_as_weekdays(self):
        self.post(weekdays=["4", "0", "2"])
        habit = Habit.objects.get()
        self.assertEqual(habit.frequency_type, Habit.Frequency.WEEKDAYS)
        self.assertEqual(habit.weekdays, [0, 2, 4])

    def test_reminder_explains_it_is_stored_only_for_now(self):
        self.assertContains(
            self.client.get(self.url),
            "Pengingat akan aktif di aplikasi mobile nanti. Untuk sekarang, jamnya disimpan dulu.",
        )

    def test_frequency_type_cannot_be_posted_directly(self):
        self.post(frequency_type="weekdays")
        self.assertEqual(Habit.objects.get().frequency_type, Habit.Frequency.DAILY)

    def test_errors_are_shown_in_indonesian(self):
        cases = [
            ({"name": ""}, "Nama habit wajib diisi."),
            ({"name": "x" * 81}, "Nama habit maksimal 80 karakter."),
            ({"weekdays": []}, "Pilih minimal satu hari."),
            ({"weekdays": ["9"]}, "Pilihan hari tidak valid."),
            ({"icon": "rocket"}, "Pilihan ikon tidak valid."),
            ({"reminder_time": "25:99"}, "Format jam tidak valid."),
        ]
        for fields, message in cases:
            with self.subTest(message=message):
                response = self.post(**fields)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
        self.assertFalse(Habit.objects.exists())

    def test_prefill_from_suggestion(self):
        response = self.client.get(self.url, {"name": "Pilah sampah", "icon": "recycle"})
        self.assertContains(response, 'value="Pilah sampah"')
        self.assertContains(response, 'value="recycle" checked')

    def test_milestone_list_comes_from_constant(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Begitu mencapai 3, 7, 14, atau 30 hari")

    def test_edit_keeps_start_date_and_updates_fields(self):
        habit = make_habit(self.user, frequency_type="weekdays", weekdays=[1, 3])
        url = reverse("habits:habit_edit", args=[habit.pk])
        page = self.client.get(url)
        self.assertContains(page, "Edit habit")
        self.assertContains(page, 'name="weekdays" value="1" checked')
        self.assertContains(page, 'name="weekdays" value="0">')
        self.client.post(
            url, {"name": "Bawa botol", "icon": "cup-soda", "time_of_day": "pagi", "weekdays": self.ALL_DAYS}
        )
        habit.refresh_from_db()
        self.assertEqual(habit.name, "Bawa botol")
        self.assertEqual(habit.tint, "moss-200")
        self.assertEqual(habit.frequency_type, Habit.Frequency.DAILY)
        self.assertIsNone(habit.weekdays)
        self.assertEqual(habit.start_date, days_ago(60))

    def test_edit_daily_habit_shows_every_day_checked(self):
        habit = make_habit(self.user)
        page = self.client.get(reverse("habits:habit_edit", args=[habit.pk]))
        for day in self.ALL_DAYS:
            self.assertContains(page, f'name="weekdays" value="{day}" checked')
