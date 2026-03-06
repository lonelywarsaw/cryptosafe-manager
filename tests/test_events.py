# Тесты событий — подписка, вызов, синхронно и в очередь.
import unittest

from core import events


class TestEventSystemPublishing(unittest.TestCase):
    # Публикация событий и вызов подписчиков.

    def setUp(self):
        events._subscribers.clear()

    def tearDown(self):
        events._subscribers.clear()

    def test_subscribe_and_publish_sync_calls_callback(self):
        received = []

        def handler(**kwargs):
            received.append(kwargs)

        events.subscribe(events.EntryAdded, handler)
        events.publish(events.EntryAdded, sync=True, entry_id=1)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["entry_id"], 1)

    def test_publish_without_subscribers_does_not_fail(self):
        events.publish(events.UserLoggedIn, sync=True)

    def test_multiple_subscribers_all_called(self):
        a = []
        b = []

        def h1(**kw):
            a.append(kw)

        def h2(**kw):
            b.append(kw)

        events.subscribe(events.EntryDeleted, h1)
        events.subscribe(events.EntryDeleted, h2)
        events.publish(events.EntryDeleted, sync=True, entry_id=5)
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)
        self.assertEqual(a[0]["entry_id"], 5)
        self.assertEqual(b[0]["entry_id"], 5)

    def test_async_publish_puts_on_queue(self):
        received = []

        def handler(**kwargs):
            received.append(kwargs)

        events.subscribe(events.ClipboardCopied, handler)
        events.publish(events.ClipboardCopied, sync=False, kind="password")
        # Ждём пока воркер обработает из очереди
        import time
        for _ in range(50):
            if received:
                break
            time.sleep(0.05)
        self.assertGreaterEqual(len(received), 1)
        self.assertEqual(received[0]["kind"], "password")
