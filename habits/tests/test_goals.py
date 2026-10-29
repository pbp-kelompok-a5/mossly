"""Goal rules, services, and pages."""

from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from habits import services
from habits.models import Goal, GoalChecklistItem, SustainabilityEvent

from .helpers import FIXED_NOW, TODAY, FrozenClockMixin, days_ago, make_goal, make_user


def in_days(n):
    return TODAY + timedelta(days=n)


class GoalRuleTests(SimpleTestCase):
    def goal(self, **fields):
        fields.setdefault("target_value", Decimal("20"))
        fields.setdefault("start_date", days_ago(9))
        fields.setdefault("deadline", in_days(10))
        return Goal(title="g", **fields)

    def test_near_deadline_edges(self):
        near = Decimal("5")
        self.assertTrue(services.is_near_deadline(self.goal(deadline=in_days(7)), near, TODAY))
        self.assertTrue(services.is_near_deadline(self.goal(deadline=TODAY), near, TODAY))
        self.assertFalse(services.is_near_deadline(self.goal(deadline=in_days(8)), near, TODAY))

    def test_reached_completed_or_expired_goals_are_not_near(self):
        self.assertFalse(services.is_near_deadline(self.goal(deadline=in_days(3)), Decimal("20"), TODAY))
        completed = self.goal(deadline=in_days(3), status=Goal.Status.COMPLETED)
        self.assertFalse(services.is_near_deadline(completed, Decimal("5"), TODAY))
        self.assertFalse(services.is_near_deadline(self.goal(deadline=days_ago(1)), Decimal("5"), TODAY))

    def test_check_amount(self):
        services.check_amount(Goal.Unit.KG_CO2E, Decimal("2.5"))
        services.check_amount(Goal.Unit.KALI, Decimal("3.00"))
        for unit in (Goal.Unit.KALI, Goal.Unit.HARI):
            with self.subTest(unit=unit), self.assertRaises(ValidationError):
                services.check_amount(unit, Decimal("0.5"))


class GoalServiceTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()

    def test_toggle_checklist_item_sets_and_clears_date(self):
        goal = make_goal(self.user)
        item = goal.checklist_items.create(label="Cek jadwal KRL")
        services.toggle_checklist_item(item)
        item.refresh_from_db()
        self.assertTrue(item.is_done)
        self.assertIsNotNone(item.done_at)
        services.toggle_checklist_item(item)
        item.refresh_from_db()
        self.assertFalse(item.is_done)
        self.assertIsNone(item.done_at)

    def test_checklist_does_not_complete_goal(self):
        goal = make_goal(self.user)
        item = goal.checklist_items.create(label="Satu-satunya langkah")
        services.toggle_checklist_item(item)
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.ACTIVE)

    def test_extending_deadline_reactivates_expired_goal(self):
        goal = make_goal(self.user, start_date=days_ago(30), deadline=days_ago(1), status=Goal.Status.EXPIRED)
        goal.deadline = in_days(5)
        goal.save()
        services.refresh_goal_after_edit(goal)
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.ACTIVE)

    def test_expired_goal_with_past_deadline_stays_expired(self):
        goal = make_goal(self.user, start_date=days_ago(30), deadline=days_ago(1), status=Goal.Status.EXPIRED)
        services.refresh_goal_after_edit(goal)
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.EXPIRED)

    def test_lowering_target_completes_once(self):
        goal = make_goal(self.user)
        services.log_goal_progress(goal, Decimal("12"))
        goal.target_value = Decimal("12")
        goal.save()
        services.refresh_goal_after_edit(goal)
        services.refresh_goal_after_edit(goal)
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.COMPLETED)
        self.assertEqual(SustainabilityEvent.objects.filter(goal=goal).count(), 1)

    def test_raising_target_keeps_completed_goal_completed(self):
        goal = make_goal(self.user)
        services.log_goal_progress(goal, Decimal("20"))
        goal.refresh_from_db()
        goal.target_value = Decimal("40")
        goal.save()
        services.refresh_goal_after_edit(goal)
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.COMPLETED)


class GoalListPageTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("habits:goal_list")

    def test_url_is_under_goal(self):
        self.assertEqual(self.url, "/goal/")
        self.assertEqual(reverse("habits:index"), "/habit/")

    def test_empty_state_offers_examples(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Tentukan satu target dengan deadline.")
        self.assertContains(response, "Buat goal pertama")
        self.assertContains(response, "Ikut 1 aksi bersih lingkungan")
        self.assertContains(response, f'data-prefill-deadline="{in_days(29).isoformat()}"')

    def test_hero_counts_sections_and_formatting(self):
        make_goal(self.user, title="Naik transportasi umum 20 kali", deadline=in_days(4))
        make_goal(self.user, title="30 hari tanpa botol plastik", unit=Goal.Unit.HARI, target_value=30, deadline=in_days(20))
        emisi = make_goal(
            self.user, title="Kurangi emisi perjalanan 10 kg", category=Goal.Category.EMISI,
            unit=Goal.Unit.KG_CO2E, target_value=Decimal("10"), deadline=in_days(12),
        )
        services.log_goal_progress(emisi, Decimal("2.5"))
        done = make_goal(self.user, title="Pilah sampah 14 hari", unit=Goal.Unit.HARI, target_value=14)
        services.log_goal_progress(done, Decimal("14"))
        make_goal(self.user, title="Goal yang terlewat", start_date=days_ago(30), deadline=days_ago(2))

        response = self.client.get(self.url)

        self.assertContains(response, "Goal bulan Oktober")
        self.assertContains(response, "3 goal sedang berjalan, 1 hampir mencapai deadline")
        self.assertContains(response, "Naik transportasi umum 20 kali tinggal 20 kali lagi dalam 4 hari. Kamu pasti bisa.")
        self.assertContains(response, "2,5 / 10 kg")
        self.assertContains(response, "Target 10 kg CO2e")
        self.assertContains(response, "Selesai baru-baru ini")
        self.assertContains(response, "Lewat deadline")
        self.assertContains(response, "terkirim ke Dashboard")
        self.assertContains(response, 'id="progress-dialog-', count=3)

    def test_no_active_goal_shows_empty_state_with_history_before_examples(self):
        done = make_goal(self.user, title="Pilah sampah 14 hari", unit=Goal.Unit.HARI, target_value=14)
        services.log_goal_progress(done, Decimal("14"))
        response = self.client.get(self.url)
        content = response.content.decode()
        self.assertContains(response, "Belum ada goal aktif")
        self.assertContains(response, "Buat goal baru")
        self.assertNotContains(response, "goal sedang berjalan")
        self.assertLess(content.index("Tentukan satu target dengan deadline."), content.index("Selesai baru-baru ini"))
        self.assertLess(content.index("Selesai baru-baru ini"), content.index("Contoh goal"))

    def test_first_time_empty_state_copy(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Belum ada goal<")
        self.assertContains(response, "Buat goal pertama")

    def test_overdue_goal_is_expired_on_visit(self):
        goal = make_goal(self.user, start_date=days_ago(30), deadline=days_ago(1))
        self.client.get(self.url)
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.EXPIRED)


class GoalDetailPageTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.goal = make_goal(self.user, start_date=days_ago(9), deadline=in_days(10))
        self.item = self.goal.checklist_items.create(label="Isi saldo kartu", position=0)
        services.log_goal_progress(self.goal, Decimal("15"), "Naik KRL Gambir - Blok M")
        # Field defaults read the real clock, so pin the log to the frozen one.
        self.goal.progress_logs.update(logged_at=FIXED_NOW)
        self.url = reverse("habits:goal_detail", args=[self.goal.pk])

    def test_detail_shows_checklist_and_logs(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Goal · Transportasi")
        self.assertContains(response, "Tinggal 5 kali lagi dalam 10 hari.")
        self.assertContains(response, "Isi saldo kartu")
        self.assertContains(response, "Belum")
        self.assertContains(response, "+15 Naik KRL Gambir - Blok M")
        self.assertContains(response, "Hari ini")

    def test_toggle_checklist_item(self):
        url = reverse("habits:goal_checklist_toggle", args=[self.goal.pk, self.item.pk])
        response = self.client.post(url)
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_done)
        self.assertContains(self.client.get(self.url), "26 Okt")

    def test_other_users_goal_pages_return_404(self):
        self.client.force_login(make_user("other"))
        urls = [
            self.url,
            reverse("habits:goal_edit", args=[self.goal.pk]),
            reverse("habits:goal_log_progress", args=[self.goal.pk]),
            reverse("habits:goal_delete", args=[self.goal.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
        toggle = reverse("habits:goal_checklist_toggle", args=[self.goal.pk, self.item.pk])
        self.assertEqual(self.client.post(toggle).status_code, 404)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_done)

    def test_toggle_requires_item_of_that_goal(self):
        other_goal = make_goal(self.user, title="Lain")
        url = reverse("habits:goal_checklist_toggle", args=[other_goal.pk, self.item.pk])
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_toggle_requires_post(self):
        url = reverse("habits:goal_checklist_toggle", args=[self.goal.pk, self.item.pk])
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_delete_confirmation_and_delete(self):
        url = reverse("habits:goal_delete", args=[self.goal.pk])
        self.assertContains(self.client.get(url), "Hapus goal ini?")
        self.assertTrue(Goal.objects.filter(pk=self.goal.pk).exists())
        response = self.client.post(url)
        self.assertRedirects(response, reverse("habits:goal_list"), fetch_redirect_response=False)
        self.assertFalse(Goal.objects.exists())


class GoalFormTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.url = reverse("habits:goal_create")

    def post(self, url=None, **fields):
        data = {
            "title": "Naik transportasi umum 20 kali",
            "category": "transportasi",
            "target_value": "20",
            "unit": "kali",
            "start_date": TODAY.isoformat(),
            "deadline": in_days(10).isoformat(),
        }
        data.update(fields)
        return self.client.post(url or self.url, data)

    def test_create_with_checklist_skips_blank_rows(self):
        response = self.post(checklist_id=["", "", ""], checklist_label=["Cek jadwal", " ", "Ajak teman"])
        self.assertRedirects(response, reverse("habits:goal_list"), fetch_redirect_response=False)
        goal = Goal.objects.get()
        self.assertEqual(goal.user, self.user)
        self.assertEqual(
            list(goal.checklist_items.values_list("label", "position")),
            [("Cek jadwal", 0), ("Ajak teman", 1)],
        )

    def test_errors_are_shown_in_indonesian(self):
        cases = [
            ({"title": ""}, "Nama goal wajib diisi."),
            ({"category": ""}, "Pilih kategori goal."),
            ({"target_value": "0"}, "Target harus lebih dari 0."),
            ({"target_value": "2.5"}, "Untuk satuan kali atau hari, isi dengan bilangan bulat."),
            ({"deadline": days_ago(1).isoformat()}, "Deadline tidak boleh sebelum tanggal mulai."),
            ({"deadline": ""}, "Deadline wajib diisi."),
        ]
        for fields, message in cases:
            with self.subTest(message=message):
                response = self.post(**fields)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
        self.assertFalse(Goal.objects.exists())

    def test_fractional_target_allowed_for_kg(self):
        self.post(unit="kg_co2e", target_value="2.5")
        self.assertEqual(Goal.objects.get().target_value, Decimal("2.5"))

    def test_prefill_from_example(self):
        response = self.client.get(
            self.url, {"title": "Ikut 1 aksi", "category": "komunitas", "target": "1", "unit": "kali", "days": "30"}
        )
        self.assertContains(response, 'value="Ikut 1 aksi"')
        self.assertContains(response, '<option value="komunitas" selected>')
        self.assertContains(response, f'value="{in_days(29).isoformat()}"')

    def test_edit_keeps_done_state_and_syncs_rows(self):
        goal = make_goal(self.user)
        kept = goal.checklist_items.create(label="Lama", position=0, is_done=True)
        removed = goal.checklist_items.create(label="Dihapus", position=1)
        url = reverse("habits:goal_edit", args=[goal.pk])
        self.assertContains(self.client.get(url), 'value="Lama"')
        response = self.post(
            url,
            checklist_id=[str(kept.pk), ""],
            checklist_label=["Lama diganti", "Baru"],
        )
        self.assertRedirects(response, reverse("habits:goal_detail", args=[goal.pk]), fetch_redirect_response=False)
        kept.refresh_from_db()
        self.assertEqual(kept.label, "Lama diganti")
        self.assertTrue(kept.is_done)
        self.assertFalse(GoalChecklistItem.objects.filter(pk=removed.pk).exists())
        self.assertEqual(list(goal.checklist_items.values_list("label", flat=True)), ["Lama diganti", "Baru"])

    def test_edit_cannot_touch_other_goals_items(self):
        goal = make_goal(self.user)
        foreign = make_goal(make_user("other")).checklist_items.create(label="Punya orang")
        self.post(reverse("habits:goal_edit", args=[goal.pk]), checklist_id=[str(foreign.pk)], checklist_label=["Diambil"])
        foreign.refresh_from_db()
        self.assertEqual(foreign.label, "Punya orang")
        self.assertEqual(list(goal.checklist_items.values_list("label", flat=True)), ["Diambil"])

    def test_edit_extending_deadline_reactivates_goal(self):
        goal = make_goal(self.user, start_date=days_ago(30), deadline=days_ago(1), status=Goal.Status.EXPIRED)
        self.post(reverse("habits:goal_edit", args=[goal.pk]), start_date=days_ago(30).isoformat())
        goal.refresh_from_db()
        self.assertEqual(goal.status, Goal.Status.ACTIVE)


class GoalProgressPageTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.goal = make_goal(self.user)
        services.log_goal_progress(self.goal, Decimal("15"))
        self.url = reverse("habits:goal_log_progress", args=[self.goal.pk])

    def test_page_shows_prompt_and_preview(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Tambah berapa kali?")
        self.assertContains(response, "Sekarang 15 / 20 kali")
        self.assertContains(response, "Setelah disimpan: 16 / 20 kali (80%)")
        self.assertContains(response, 'step="1"')

    def test_log_redirects_back_to_safe_next_only(self):
        response = self.client.post(self.url, {"amount": "1", "next": reverse("habits:goal_list")})
        self.assertRedirects(response, reverse("habits:goal_list"), fetch_redirect_response=False)
        response = self.client.post(self.url, {"amount": "1", "next": "https://contoh-jahat.test/"})
        self.assertRedirects(
            response, reverse("habits:goal_detail", args=[self.goal.pk]), fetch_redirect_response=False
        )

    def test_completion_shows_success_message(self):
        response = self.client.post(self.url, {"amount": "5"}, follow=True)
        self.assertContains(response, "Goal selesai! Pencapaian ini sudah terkirim ke Personal Dashboard.")
        self.goal.refresh_from_db()
        self.assertEqual(self.goal.status, Goal.Status.COMPLETED)

    def test_invalid_amounts_show_errors(self):
        cases = [
            ("1.5", "Untuk satuan kali atau hari, isi dengan bilangan bulat."),
            ("0", "Jumlah progres harus lebih dari 0."),
            ("", "Isi jumlah progres."),
        ]
        for amount, message in cases:
            with self.subTest(amount=amount):
                response = self.client.post(self.url, {"amount": amount})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
        self.assertEqual(self.goal.progress_logs.count(), 1)

    def test_logging_on_expired_goal_shows_message(self):
        goal = make_goal(self.user, start_date=days_ago(30), deadline=days_ago(1))
        url = reverse("habits:goal_log_progress", args=[goal.pk])
        response = self.client.post(url, {"amount": "1"}, follow=True)
        self.assertContains(response, "Progres hanya bisa dicatat untuk goal yang masih aktif.")


class GoalPastDeadlineTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)

    def test_new_goal_with_past_deadline_is_rejected(self):
        response = self.client.post(reverse("habits:goal_create"), {
            "title": "Telat", "category": "plastik", "target_value": "5", "unit": "kali",
            "start_date": days_ago(10).isoformat(), "deadline": days_ago(1).isoformat(),
        })
        self.assertContains(response, "Deadline tidak boleh di masa lalu.")
        self.assertFalse(Goal.objects.exists())


class StripTagsTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)

    def test_habit_name_tags_are_removed(self):
        self.client.post(reverse("habits:habit_create"), {
            "name": "<b>Bawa</b> tumbler", "icon": "leaf", "time_of_day": "pagi",
            "weekdays": [str(d) for d in range(7)],
        })
        self.assertEqual(self.user.habits.get().name, "Bawa tumbler")

    def test_goal_title_only_tags_is_rejected(self):
        response = self.client.post(reverse("habits:goal_create"), {
            "title": '<img src="x" onerror="alert(1)">', "category": "plastik",
            "target_value": "5", "unit": "kali",
            "start_date": TODAY.isoformat(), "deadline": TODAY.isoformat(),
        })
        self.assertContains(response, "Nama goal tidak boleh hanya berisi tag HTML.")
        self.assertFalse(Goal.objects.exists())
