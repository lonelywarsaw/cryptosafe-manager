# тесты событий

import time
import unittest
from core import events


class TestEvents(unittest.TestCase):
    def setUp(self):
        events._subscribers.clear()

    def tearDown(self):
        events._subscribers.clear()

    def test_sync(self):
        # при sync=True подписчик вызывается сразу; в handler приходят аргументы события (entry_id и т.д.)
        out = []
        events.subscribe(events.EntryAdded, lambda **kw: out.append(kw))
        events.publish(events.EntryAdded, sync=True, entry_id=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["entry_id"], 1)

    def test_no_subscribers(self):
        # публикация без подписчиков не падает (пустое событие допустимо)
        events.publish(events.UserLoggedIn, sync=True)

    def test_two_handlers(self):
        # на одно событие могут быть подписаны несколько обработчиков; все вызываются с одними данными
        a, b = [], []
        events.subscribe(events.EntryDeleted, lambda **kw: a.append(kw))
        events.subscribe(events.EntryDeleted, lambda **kw: b.append(kw))
        events.publish(events.EntryDeleted, sync=True, entry_id=5)
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)

    def test_async(self):
        # при sync=False событие попадает в очередь, фоновый поток вызывает подписчика; ждём обработки
        out = []
        events.subscribe(events.ClipboardCopied, lambda **kw: out.append(kw))
        events.publish(events.ClipboardCopied, sync=False, kind="password")
        for _ in range(30):
            if out:
                break
            time.sleep(0.05)
        self.assertGreaterEqual(len(out), 1)
        self.assertEqual(out[0]["kind"], "password")
