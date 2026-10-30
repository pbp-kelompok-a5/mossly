"""Access control and request handling for state-changing views."""

import json
from datetime import timedelta
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from habits import services
from habits.models import Goal, Habit, SustainabilityEvent

from .helpers import TODAY, FrozenClockMixin, days_ago, make_goal, make_habit, make_user


class AccessTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.owner = make_user("owner")
        self.other = make_user("other")
        self.habit = make_habit(self.owner)
        self.goal = make_goal(self.owner)

    def habit_urls(self):
        return [
            reverse(name, args=[self.habit.pk])
            for name in ("habits:habit_check_in", "habits:habit_undo_check_in", "habits:habit_delete")
        ]

    def goal_urls(self):
        return [
            reverse(name, args=[self.goal.pk])
            for name in ("habits:goal_log_progress", "habits:goal_delete")
        ]

    def test_anonymous_is_redirected_to_login(self):
        login_url = reverse("accounts:login")
        for url in [reverse("habits:index")] + self.habit_urls() + self.goal_urls():
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertRedirects(
                    response, f"{login_url}?next={url}", fetch_redirect_response=False
                )

    def test_other_users_objects_return_404(self):
        self.client.force_login(self.other)
        for url in self.habit_urls() + self.goal_urls():
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {"amount": "1"}).status_code, 404)
        self.assertTrue(Habit.objects.filter(pk=self.habit.pk).exists())
        self.assertTrue(Goal.objects.filter(pk=self.goal.pk).exists())
        self.assertFalse(self.habit.checkins.exists())
        self.assertFalse(self.goal.progress_logs.exists())

    def test_state_changes_require_post(self):
        self.client.force_login(self.owner)
        # Delete and log progress answer GET with a full page instead (tested below).
        post_only = [
            url for url in self.habit_urls() + self.goal_urls()
            if not url.endswith(("/delete/", "/progress/"))
        ]
        for url in post_only:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_delete_get_shows_confirmation_without_deleting(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("habits:habit_delete", args=[self.habit.pk]))
        self.assertContains(response, "Hapus habit ini?")
        self.assertTrue(Habit.objects.filter(pk=self.habit.pk).exists())

    def test_edit_page_of_other_users_habit_returns_404(self):
        self.client.force_login(self.other)
        url = reverse("habits:habit_edit", args=[self.habit.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"name": "Diambil"}).status_code, 404)
        self.habit.refresh_from_db()
        self.assertEqual(self.habit.name, "Bawa tumbler")

    def test_state_changes_require_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for url in self.habit_urls() + self.goal_urls():
            with self.subTest(url=url):
                self.assertEqual(client.post(url).status_code, 403)
        self.assertTrue(Habit.objects.filter(pk=self.habit.pk).exists())


class HabitActionTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.habit = make_habit(self.user)
        self.client.force_login(self.user)

    def post(self, name):
        return self.client.post(reverse(name, args=[self.habit.pk]))

    def test_check_in_and_undo(self):
        response = self.post("habits:habit_check_in")
        self.assertRedirects(response, reverse("habits:index"), fetch_redirect_response=False)
        self.assertTrue(self.habit.checkins.filter(checkin_date=TODAY).exists())
        self.post("habits:habit_undo_check_in")
        self.assertFalse(self.habit.checkins.exists())

    def test_delete_removes_habit_and_checkins_but_keeps_events(self):
        for n in (2, 1):
            self.habit.checkins.create(checkin_date=days_ago(n))
        self.post("habits:habit_check_in")  # reaches 3 days
        self.post("habits:habit_delete")
        self.assertFalse(Habit.objects.exists())
        self.assertEqual(SustainabilityEvent.objects.count(), 1)


class GoalActionTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.goal = make_goal(self.user)
        self.client.force_login(self.user)
        self.url = reverse("habits:goal_log_progress", args=[self.goal.pk])

    def test_log_progress(self):
        self.client.post(self.url, {"amount": "3", "note": "Ke kampus"})
        log = self.goal.progress_logs.get()
        self.assertEqual(log.amount, Decimal("3"))
        self.assertEqual(log.note, "Ke kampus")

    def test_invalid_amount_is_rejected(self):
        for amount in ("0", "-2", "abc", ""):
            with self.subTest(amount=amount):
                self.client.post(self.url, {"amount": amount})
        self.assertFalse(self.goal.progress_logs.exists())

    def test_delete_goal(self):
        self.client.post(reverse("habits:goal_delete", args=[self.goal.pk]))
        self.assertFalse(Goal.objects.exists())

    def test_completed_goal_cannot_be_deleted(self):
        services.log_goal_progress(self.goal, self.goal.target_value)
        detail = self.client.get(reverse("habits:goal_detail", args=[self.goal.pk]))
        self.assertNotContains(detail, "goal-delete-dialog")
        response = self.client.post(reverse("habits:goal_delete", args=[self.goal.pk]), follow=True)
        self.assertContains(response, "tidak bisa dihapus")
        self.assertTrue(Goal.objects.filter(pk=self.goal.pk).exists())


class HtmxCheckInTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        self.habit = make_habit(self.user, name="Bawa tumbler")

    def htmx_post(self, name):
        url = reverse(name, args=[self.habit.pk])
        return self.client.post(url, HTTP_HX_REQUEST="true", follow=True)

    def test_htmx_check_in_returns_the_page_with_fresh_counts(self):
        response = self.htmx_post("habits:habit_check_in")
        self.assertTemplateUsed(response, "habits/habit/habit_list.html")
        self.assertContains(response, "1 dari 1 kebiasaan hijau sudah kamu selesaikan hari ini")
        self.assertContains(response, 'aria-label="1 dari 1 selesai"')
        self.assertEqual(self.habit.checkins.count(), 1)

    def test_htmx_anonymous_gets_hx_redirect(self):
        self.client.logout()
        response = self.client.post(
            reverse("habits:habit_check_in", args=[self.habit.pk]), HTTP_HX_REQUEST="true"
        )
        self.assertEqual(response.status_code, 401)
        self.assertTrue(response["HX-Redirect"].startswith(reverse("accounts:login")))

    def test_htmx_undo_returns_the_page_with_fresh_counts(self):
        self.htmx_post("habits:habit_check_in")
        response = self.htmx_post("habits:habit_undo_check_in")
        self.assertContains(response, "0 dari 1 kebiasaan hijau sudah kamu selesaikan hari ini")
        self.assertEqual(self.habit.checkins.count(), 0)

    def test_htmx_milestone_dialog_comes_with_the_page(self):
        for n in (2, 1):
            self.habit.checkins.create(checkin_date=days_ago(n))
        response = self.htmx_post("habits:habit_check_in")
        self.assertContains(response, "3 hari berturut-turut!")
        self.assertEqual(SustainabilityEvent.objects.get().milestone_days, 3)

    def test_htmx_anonymous_get_returns_to_the_same_page_after_login(self):
        self.client.logout()
        url = reverse("habits:goal_list") + "?category=plastik"
        response = self.client.get(url, HTTP_HX_REQUEST="true")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response["HX-Redirect"], f"{reverse('accounts:login')}?next={url}")

    def test_pages_swap_the_shared_block(self):
        for name in ("habits:index", "habits:goal_list", "habits:history"):
            with self.subTest(page=name):
                self.assertContains(self.client.get(reverse(name)), 'hx-select=".habits-page"')

    def test_check_in_swaps_only_its_row_and_counts(self):
        response = self.client.get(reverse("habits:index"))
        row = f"habit-row-{self.habit.pk}"
        self.assertContains(response, f'id="{row}"')
        self.assertContains(response, f'hx-target="closest li" hx-select="#{row}"')
        self.assertContains(response, 'hx-select-oob="#today-title,#today-stats,#week-strip,')
        group = f"group-note-{self.habit.time_of_day}"
        for target in ("today-title", "today-stats", "week-strip", group, "habits-messages", "habit-dialog-slot"):
            with self.subTest(target=target):
                self.assertContains(response, f'id="{target}"')

    def test_checklist_swaps_only_its_list_and_count(self):
        goal = make_goal(self.user)
        item = goal.checklist_items.create(label="Langkah", position=0)
        url = reverse("habits:goal_checklist_toggle", args=[goal.pk, item.pk])
        response = self.client.post(url, {"next": reverse("habits:goal_list")}, HTTP_HX_REQUEST="true", follow=True)
        self.assertContains(response, f'id="card-checklist-list-{goal.pk}"')
        self.assertContains(response, f'id="card-checklist-count-{goal.pk}">1/1<')
        detail = self.client.get(reverse("habits:goal_detail", args=[goal.pk]))
        self.assertContains(detail, 'hx-target="#goal-checklist-list"')
        self.assertContains(detail, 'id="goal-checklist-count">1 dari 1 selesai<')

    def test_tabs_and_filters_keep_links_for_no_javascript(self):
        goal_list = reverse("habits:goal_list")
        make_goal(self.user, category="plastik")
        response = self.client.get(goal_list)
        self.assertContains(response, f'href="{goal_list}" hx-get="{goal_list}"')
        self.assertContains(response, f'href="?category=plastik" hx-get="{goal_list}?category=plastik"')


class GoalFilterTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        make_goal(self.user, title="Bawa botol", category="plastik")
        make_goal(self.user, title="Naik KRL", category="transportasi")

    def test_category_filter(self):
        response = self.client.get(reverse("habits:goal_list"), {"category": "plastik"})
        self.assertContains(response, "Bawa botol")
        self.assertNotContains(response, "Naik KRL")
        self.assertContains(response, 'aria-current="page">Plastik')

    def test_unknown_category_shows_all(self):
        response = self.client.get(reverse("habits:goal_list"), {"category": "xyz"})
        self.assertContains(response, "Bawa botol")
        self.assertContains(response, "Naik KRL")

    def test_empty_category_only_changes_the_title(self):
        response = self.client.get(reverse("habits:goal_list"), {"category": "sampah"})
        self.assertContains(response, "Belum ada goal dengan kategori Sampah")
        self.assertNotContains(response, "Tentukan satu target dengan deadline.")
        self.assertNotContains(response, "Contoh goal")

    def test_category_with_only_past_goals_only_changes_the_title(self):
        make_goal(
            self.user, title="Kerja bakti", category="komunitas",
            start_date=days_ago(30), deadline=days_ago(1),
        )
        response = self.client.get(reverse("habits:goal_list"), {"category": "komunitas"})
        self.assertContains(response, "Belum ada goal aktif dengan kategori Komunitas")
        self.assertContains(response, "Kerja bakti")  # listed under "Lewat deadline"
        self.assertNotContains(response, "Tentukan satu target dengan deadline.")


class HtmxDialogFormTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)

    HABIT = {"name": "Pilah sampah", "icon": "leaf", "time_of_day": "pagi", "weekdays": [str(d) for d in range(7)]}
    GOAL = {
        "title": "Kurangi plastik", "category": "plastik", "target_value": "5", "unit": "kali",
        "start_date": TODAY.isoformat(), "deadline": (TODAY + timedelta(days=5)).isoformat(),
    }

    def htmx(self, name, data, *args):
        return self.client.post(reverse(name, args=args), data, HTTP_HX_REQUEST="true")

    def assert_goes_to(self, response, url):
        self.assertEqual(response.status_code, 200)
        location = json.loads(response["HX-Location"])
        self.assertEqual(location["path"], url)
        self.assertEqual(location["target"], ".habits-page")

    def assert_form_only(self, response, message):
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<html")
        self.assertContains(response, message)
        self.assertContains(response, "data-dialog-close")
        self.assertNotIn("HX-Location", response)

    def test_new_habit(self):
        self.assert_goes_to(self.htmx("habits:habit_create", self.HABIT), reverse("habits:index"))
        self.assertEqual(self.user.habits.get().name, "Pilah sampah")

    def test_invalid_habit_stays_in_the_dialog(self):
        response = self.htmx("habits:habit_create", {**self.HABIT, "name": "<b></b>"})
        self.assert_form_only(response, "Nama habit tidak boleh hanya berisi tag HTML.")
        self.assertContains(response, 'value="leaf" checked')
        self.assertFalse(self.user.habits.exists())

    def test_new_goal(self):
        self.assert_goes_to(self.htmx("habits:goal_create", self.GOAL), reverse("habits:goal_list"))
        self.assertEqual(self.user.goals.get().title, "Kurangi plastik")

    def test_invalid_goal_keeps_its_checklist(self):
        data = {**self.GOAL, "title": "<i></i>", "checklist_id": [""], "checklist_label": ["Beli tumbler"]}
        response = self.htmx("habits:goal_create", data)
        self.assert_form_only(response, "Nama goal tidak boleh hanya berisi tag HTML.")
        self.assertContains(response, 'value="Beli tumbler"')
        self.assertFalse(self.user.goals.exists())

    def test_progress_returns_to_the_page_it_came_from(self):
        goal = make_goal(self.user)
        back = reverse("habits:goal_list") + "?category=transportasi"
        response = self.htmx("habits:goal_log_progress", {"amount": "2", "next": back}, goal.pk)
        self.assert_goes_to(response, back)
        self.assertEqual(goal.progress_logs.get().amount, Decimal("2"))

    def test_progress_ignores_an_outside_next(self):
        goal = make_goal(self.user)
        response = self.htmx("habits:goal_log_progress", {"amount": "2", "next": "https://contoh.test/"}, goal.pk)
        self.assert_goes_to(response, reverse("habits:goal_detail", args=[goal.pk]))

    def test_invalid_progress_stays_in_the_dialog(self):
        goal = make_goal(self.user)
        response = self.htmx("habits:goal_log_progress", {"amount": "0", "next": "/goal/"}, goal.pk)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<html")
        self.assertContains(response, 'class="field-error"')
        self.assertContains(response, 'name="next" value="/goal/"')
        self.assertFalse(goal.progress_logs.exists())

    def test_without_htmx_forms_still_use_full_pages(self):
        url = reverse("habits:habit_create")
        self.assertContains(self.client.post(url, {**self.HABIT, "name": ""}), "<html")
        self.assertRedirects(self.client.post(url, self.HABIT), reverse("habits:index"), fetch_redirect_response=False)

    def test_standalone_form_has_no_htmx(self):
        response = self.client.get(reverse("habits:habit_create"))
        self.assertNotContains(response, 'hx-post="/habit/new/"')


class JsonEndpointTests(FrozenClockMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = make_user()
        self.client.force_login(self.user)
        make_goal(self.user, title="Bawa botol", category="plastik")
        make_goal(self.user, title="Naik KRL", category="transportasi")
        make_goal(make_user("other"), title="Punya orang", category="plastik")

    def test_goals_json_only_own_goals(self):
        data = self.client.get(reverse("habits:goals_json")).json()
        self.assertEqual({goal["title"] for goal in data}, {"Bawa botol", "Naik KRL"})
        data = self.client.get(reverse("habits:goals_json"), {"category": "plastik"}).json()
        self.assertEqual([goal["title"] for goal in data], ["Bawa botol"])

    def test_habits_json_only_own_habits(self):
        make_habit(self.user, name="Pilah sampah", time_of_day="siang")
        make_habit(make_user("tetangga"), name="Punya orang")
        data = self.client.get(reverse("habits:habits_json")).json()
        self.assertEqual(
            data, [{"id": data[0]["id"], "name": "Pilah sampah", "time_of_day": "siang", "start_date": "2026-08-27"}]
        )

    def test_json_requires_login(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse("habits:goals_json")).status_code, 302)
