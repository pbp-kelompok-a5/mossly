from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from .models import Thread, Reply
from .services import publish_achievement


class CommunityTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username='rara', password='test-password')
        self.other = get_user_model().objects.create_user(username='bima', password='test-password')
        self.thread = Thread.objects.create(author=self.owner, title='Bawa tumbler', content='Mulai dari kebiasaan kecil.', category='tips')
        self.client.force_login(self.owner)

    def test_authentication_required(self):
        self.client.logout()
        for name, args in [('index', []), ('create', []), ('detail', [self.thread.pk]), ('edit', [self.thread.pk]), ('delete', [self.thread.pk]), ('like', [self.thread.pk])]:
            response = self.client.get(reverse('community:' + name, args=args))
            self.assertEqual(response.status_code, 302)
            self.assertIn('/accounts/login/', response.url)

    def test_feed_filters_and_pagination(self):
        Thread.objects.bulk_create([Thread(author=self.owner, title=f'Cerita {i}', content='Cerita', category='general') for i in range(10)])
        response = self.client.get(reverse('community:index'))
        self.assertEqual(len(response.context['page_obj']), 8)
        self.assertContains(response, 'Selanjutnya')
        response = self.client.get(reverse('community:index'), {'category': 'tips'})
        self.assertContains(response, 'Bawa tumbler')
        self.assertEqual(len(response.context['page_obj']), 1)
        response = self.client.get(reverse('community:index'), {'category': 'achievement'})
        self.assertContains(response, 'Belum ada cerita di kategori ini')

    def test_create_validation_and_author(self):
        url = reverse('community:create')
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {'title': '  ', 'content': ' ', 'category': 'tips'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        response = self.client.post(url, {'title': 'Naik KRL', 'content': 'Lebih hemat', 'category': 'tips', 'author': self.other.pk, 'achievement_event_id': 'fake'})
        self.assertEqual(response.status_code, 302)
        thread = Thread.objects.get(title='Naik KRL')
        self.assertEqual(thread.author, self.owner)
        self.assertFalse(thread.is_automatic)

    def test_edit_and_ownership(self):
        url = reverse('community:edit', args=[self.thread.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url, {'title': 'Tumbler baru', 'content': 'Ceritaku', 'category': 'general'})
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.title, 'Tumbler baru')
        self.client.force_login(self.other)
        for name in ['edit', 'delete']:
            url = reverse('community:' + name, args=[self.thread.pk])
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {'title': 'Hacked'}).status_code, 404)
        self.assertTrue(Thread.objects.filter(pk=self.thread.pk).exists())

    def test_reply_validation_and_escaping(self):
        url = reverse('community:detail', args=[self.thread.pk])
        response = self.client.post(url, {'content': ' '})
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(self.thread.replies.count(), 0)
        self.client.post(url, {'content': '<script>alert(1)</script>', 'author': self.other.pk})
        self.assertEqual(self.thread.replies.get().author, self.owner)
        response = self.client.get(url)
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_like_is_idempotent_and_post_only(self):
        url = reverse('community:like', args=[self.thread.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        for _ in range(2):
            self.client.post(url, {'action': 'like'})
        self.assertEqual(self.thread.liked_by.count(), 1)
        response = self.client.get(reverse('community:detail', args=[self.thread.pk]))
        self.assertContains(response, 'Diapresiasi')
        for _ in range(2):
            self.client.post(url, {'action': 'unlike'})
        self.assertEqual(self.thread.liked_by.count(), 0)

    def test_delete_requires_confirmation_and_cascades(self):
        Reply.objects.create(thread=self.thread, author=self.other, content='Bagus!')
        self.thread.liked_by.add(self.other)
        url = reverse('community:delete', args=[self.thread.pk])
        self.assertContains(self.client.get(url), 'Hapus cerita ini?')
        self.assertTrue(Thread.objects.filter(pk=self.thread.pk).exists())
        self.client.post(url)
        self.assertFalse(Thread.objects.filter(pk=self.thread.pk).exists())
        self.assertEqual(Reply.objects.count(), 0)
        self.assertEqual(Thread.liked_by.through.objects.count(), 0)

    def test_achievement_idempotence_and_deleted_event(self):
        data = dict(user=self.owner, event_id='badge-1', achievement_id='tumbler', name='Pejuang Tumbler', description='Tujuh hari membawa tumbler!', earned_at=timezone.now())
        thread = publish_achievement(**data)
        self.assertEqual(publish_achievement(**data).pk, thread.pk)
        self.assertEqual(self.client.get(reverse('community:edit', args=[thread.pk])).status_code, 404)
        self.assertContains(self.client.get(reverse('community:detail', args=[thread.pk])), 'Post Otomatis')
        self.client.post(reverse('community:delete', args=[thread.pk]))
        self.assertIsNone(publish_achievement(**data))
        self.assertFalse(Thread.objects.filter(achievement_event_id='badge-1').exists())

    def test_csrf_is_required(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('community:like', args=[self.thread.pk]), {'action': 'like'}).status_code, 403)
