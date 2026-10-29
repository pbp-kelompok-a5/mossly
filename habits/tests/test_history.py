"""History rules, the Riwayat tab, and the habit detail page."""

from datetime import date, timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from habits import services
from habits.models import Habit

from .helpers import TODAY, FrozenClockMixin, days_ago, make_goal, make_habit, make_user


def daily_habit(pk=1, start=None):
    return Habit(pk=pk, name="h", start_date=start or date(2026, 1, 1))


class HeatLevelTests(SimpleTestCase):
    def test_levels_follow_the_agreed_buckets(self):
        cases = [
            ((0, 0), 0), ((3, 0), 0),
            ((100, 1), 1), ((100, 39), 1),
            ((100, 40), 2), ((100, 69), 2),
            ((100, 70), 3), ((100, 99), 3),
            ((3, 3), 4), ((1, 1), 4),
        ]
        for (scheduled, done), level in cases:
            with self.subTest(scheduled=scheduled, done=done):
                self.assertEqual(services.heat_level(scheduled, done), level)

    def test_almost_complete_day_is_not_level_four(self):
        self.assertEqual(services.heat_level(1000, 999), 3)


class PeriodHelperTests(SimpleTestCase):
    def test_month_bounds(self):
        self.assertEqual(services.month_bounds(2028, 2), (date(2028, 2, 1), date(2028, 2, 29)))
        self.assertEqual(services.month_bounds(2026, 12), (date(2026, 12, 1), date(2026, 12, 31)))

    def test_shift_month_crosses_years(self):
        self.assertEqual(services.shift_month(2026, 1, -2), (2025, 11))
        self.assertEqual(services.shift_month(2026, 11, 3), (2027, 2))

    def test_perfect_days(self):
        a, b = daily_habit(1), daily_habit(2)
        checkins = {1: {days_ago(2), days_ago(1)}, 2: {days_ago(1)}}
        self.assertEqual(services.perfect_days([a, b], checkins, days_ago(3), TODAY, TODAY), 1)

    def test_missed_habits(self):
        a, b = daily_habit(1), daily_habit(2)
        missed = services.missed_habits([a, b], {1: {days_ago(1)}, 2: set()}, days_ago(1))
        self.assertEqual(missed, [b])


class HabitStatsTests(SimpleTestCase):
    def test_longest_run_within_range(self):
        habit = daily_habit()
        dates = {date(2026, 9, 28), date(2026, 9, 29), date(2026, 9, 30), date(2026, 10, 1), date(2026, 10, 2)}
        self.assertEqual(services.longest_run(habit, dates, date(2026, 10, 1), TODAY), 2)
        self.assertEqual(services.longest_run(habit, dates, date(2026, 9, 1), TODAY), 5)

    def test_strongest_weekday_prefers_earlier_day_on_ties(self):
        habit = daily_habit()
        # 19 Oct 2026 is a Monday, 20 Oct a Tuesday.
        dates = {date(2026, 10, 19), date(2026, 10, 20)}
        self.assertEqual(services.strongest_weekday(habit, dates, date(2026, 10, 1), TODAY), 0)
        self.assertIsNone(services.strongest_weekday(habit, set(), date(2026, 10, 1), TODAY))

    def test_month_stats_start_at_habit_start(self):
        habit = daily_habit(start=date(2026, 10, 17))  # 10 days up to 26 Oct
        dates = {date(2026, 10, d) for d in (17, 18, 19, 20, 21, 25)}
        stats = services.habit_month_stats(habit, dates, 2026, 10, TODAY)
        self.assertEqual((stats["done"], stats["scheduled"], stats["rate"]), (6, 10, 60))
        self.assertEqual(stats["longest"], 5)

    def test_month_stats_for_weekday_habit_count_scheduled_days_only(self):
        habit = Habit(pk=1, name="h", start_date=date(2026, 10, 1), frequency_type="weekdays", weekdays=[0])
        stats = services.habit_month_stats(habit, {date(2026, 10, 5)}, 2026, 10, TODAY)
        # Mondays up to 26 Oct: 5, 12, 19, 26.
        self.assertEqual((stats["done"], stats["scheduled"]), (1, 4))


class YearGridTests(SimpleTestCase):
    def test_month_labels_sit_on_the_first_column_starting_in_that_month(self):
        from habits.views import _year_weeks

        weeks = _year_weeks(2026, TODAY, lambda day: 0)
        labels = [week["label"] for week in weeks]
        self.assertEqual(labels[0], "Jan")  # 1 Jan 2026 is a Thursday
        self.assertEqual([label for label in labels if label], [
            "Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
        ])
        # The week of 26 Oct ends on 1 Nov but still belongs under Oktober.
        today_week = next(i for i, week in enumerate(weeks) if any(d and d["is_today"] for d in week["days"]))
        self.assertEqual(labels[today_week], "")
        self.assertEqual(labels[today_week + 1], "Nov")


class HistoryPageTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("habits:history")

    def test_url(self):
        self.assertEqual(self.url, "/habit/history/")

    def test_empty_state(self):
        make_habit(self.user, start_date=TODAY)
        response = self.client.get(self.url)
        self.assertContains(response, "Riwayatmu akan tumbuh di sini.")
        self.assertContains(response, "Mulai check-in pertama")
        self.assertContains(response, "Belum ada check-in")
        self.assertContains(response, "heat-upcoming", count=31)
        self.assertContains(response, "is-today", count=1)

    def seed_two_months(self):
        habit = make_habit(self.user, name="Pilah sampah", start_date=date(2026, 9, 1))
        for day in range(1, 16):
            habit.checkins.create(checkin_date=date(2026, 9, day))
        for day in range(1, 21):
            habit.checkins.create(checkin_date=date(2026, 10, day))
        return habit

    def test_month_hero_compares_with_last_month(self):
        self.seed_two_months()
        response = self.client.get(self.url)
        # October: 20 of 26 days (77%); September: 15 of 30 (50%).
        self.assertContains(response, "Konsistensimu 77% bulan ini, naik 27% dari September")
        self.assertContains(response, "Kalender Oktober")
        self.assertContains(response, 'aria-current="page">Bulan ini')

    def test_drop_is_not_called_out(self):
        habit = make_habit(self.user, start_date=date(2026, 9, 1))
        for day in range(1, 31):
            habit.checkins.create(checkin_date=date(2026, 9, day))
        habit.checkins.create(checkin_date=date(2026, 10, 1))
        response = self.client.get(self.url)
        self.assertContains(response, "Konsistensimu 4% bulan ini")
        self.assertNotContains(response, "naik")
        self.assertNotContains(response, "turun")

    def test_goal_activity_without_habits_invites_a_habit(self):
        services.log_goal_progress(make_goal(self.user), Decimal("3"))
        for period in ("month", "3m", "year"):
            with self.subTest(period=period):
                response = self.client.get(self.url, {"period": period})
                self.assertContains(response, "Belum ada habit yang dicatat")
                self.assertContains(response, "Tambah habit")
                self.assertNotContains(response, "progress-ring-value")
                self.assertContains(response, "Progres: Naik transportasi umum 20 kali")

    def test_habit_without_check_ins_this_month_shows_zero_without_subtitle(self):
        make_habit(self.user, start_date=date(2026, 10, 1))
        services.log_goal_progress(make_goal(self.user), Decimal("3"))
        response = self.client.get(self.url)
        self.assertContains(response, "Konsistensimu 0% bulan ini")
        self.assertNotContains(response, "focus-subtitle")

    def test_three_month_view(self):
        self.seed_two_months()
        response = self.client.get(self.url, {"period": "3m"})
        self.assertContains(response, "3 bulan terakhir")
        self.assertContains(response, "Konsistensimu naik dari 50% ke 77%")
        self.assertContains(response, "Agustus – Oktober")
        self.assertContains(response, "Belum ada data")  # August had no habit yet
        self.assertContains(response, "50% konsistensi")

    def test_year_view(self):
        self.seed_two_months()
        response = self.client.get(self.url, {"period": "year"})
        self.assertContains(response, "35 check-in sejak Januari 2026")
        self.assertContains(response, "35 check-in · 35 hari sempurna")
        self.assertContains(response, "Kalender 2026")

    def test_unknown_period_falls_back_to_month(self):
        self.seed_two_months()
        response = self.client.get(self.url, {"period": "decade"})
        self.assertContains(response, "Kalender Oktober")

    def test_summary_and_most_consistent(self):
        self.seed_two_months()
        other = make_habit(self.user, name="Bawa tumbler", start_date=date(2026, 10, 1))
        for day in range(1, 6):
            other.checkins.create(checkin_date=date(2026, 10, day))
        goal = make_goal(self.user)
        services.log_goal_progress(goal, Decimal("20"))
        response = self.client.get(self.url)
        self.assertContains(response, "Ringkasan Oktober")
        content = response.content.decode()
        self.assertLess(content.index("Pilah sampah</span><span>77%"), content.index("Bawa tumbler</span><span>19%"))

    def test_activity_log(self):
        habit = make_habit(self.user, name="Habiskan makanan")
        skipped = make_habit(self.user, name="Bawa tumbler")
        for n in (2, 1):
            services.check_in(habit, days_ago(n))
        services.check_in(habit)
        goal = make_goal(self.user, title="Pilah sampah 2 minggu")
        services.log_goal_progress(goal, Decimal("5"), "Di rumah")
        services.log_goal_progress(goal, Decimal("15"))
        response = self.client.get(self.url)
        self.assertContains(response, "Check-in: Habiskan makanan")
        self.assertContains(response, "3 hari berturut-turut")
        self.assertContains(response, "Streak 3 hari: Habiskan makanan")
        self.assertContains(response, "Goal selesai: Pilah sampah 2 minggu")
        self.assertContains(response, "Progres: Pilah sampah 2 minggu")
        self.assertContains(response, "+5 kali · Di rumah")
        self.assertContains(response, "Melewatkan 1 habit")
        self.assertContains(response, skipped.name)
        self.assertContains(response, "Kemarin")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)


class HabitDetailPageTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.habit = make_habit(self.user, name="Naik transportasi umum", time_of_day="pagi", start_date=date(2026, 10, 1))
        for day in (19, 20, 21, 22, 23, 24, 25):
            services.check_in(self.habit, date(2026, 10, day))
        self.url = reverse("habits:habit_detail", args=[self.habit.pk])

    def test_detail_page(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Habit · Pagi")
        self.assertContains(response, "Setiap hari, dimulai 1 Oktober 2026.")
        self.assertContains(response, "Check-in hari ini")
        self.assertContains(response, "7/14")
        self.assertContains(response, "menuju 14 hari")
        self.assertContains(response, "7 dari 26 hari")
        self.assertContains(response, "27%")
        self.assertContains(response, "Senin")
        self.assertContains(response, "Terkirim ke Dashboard", count=2)
        self.assertContains(response, "7 hari lagi")
        self.assertContains(response, "Belum terbuka", count=1)
        self.assertContains(response, "habit-day-done", count=8)  # 7 days plus the legend

    def test_check_in_from_detail_returns_to_detail(self):
        url = reverse("habits:habit_check_in", args=[self.habit.pk])
        response = self.client.post(url, {"next": self.url})
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        page = self.client.get(self.url)
        self.assertContains(page, "Sudah check-in")
        self.assertContains(page, "Check-in terakhir hari ini pukul")

    def test_weekday_habit_marks_unscheduled_days_off(self):
        habit = make_habit(self.user, name="Bersepeda", frequency_type="weekdays", weekdays=[5], start_date=date(2026, 10, 1))
        response = self.client.get(reverse("habits:habit_detail", args=[habit.pk]))
        self.assertContains(response, "Setiap Sab, dimulai")
        self.assertContains(response, "habit-day-off")
        self.assertNotContains(response, "Check-in hari ini")

    def test_other_users_habit_returns_404(self):
        self.client.force_login(make_user("other"))
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_list_links_to_detail(self):
        response = self.client.get(reverse("habits:index"))
        self.assertContains(response, f'href="{self.url}"')
