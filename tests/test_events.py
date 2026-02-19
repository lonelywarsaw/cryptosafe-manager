import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.events import (
    event_bus,
    entry_added,
    entry_updated,
    entry_deleted,
)

class TestEventBus(unittest.TestCase):
    def test_publish_subscribe(self):
        received = []
        def handler(event, payload):
            received.append((event, payload))
        event_bus.subscribe(entry_added, handler)
        event_bus.publish(entry_added, {"title": "Test"})
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], entry_added)
        self.assertEqual(received[0][1]["title"], "Test")

    def test_multiple_handlers(self):
        a, b = [], []
        event_bus.subscribe(entry_added, lambda e, p: a.append(p))
        event_bus.subscribe(entry_added, lambda e, p: b.append(p))
        event_bus.publish(entry_added, {"id": 1})
        self.assertEqual(len(a), 1)
        self.assertEqual(len(b), 1)

    def test_different_events(self):
        log = []
        event_bus.subscribe(entry_added, lambda e, p: log.append(("add", p)))
        event_bus.subscribe(entry_deleted, lambda e, p: log.append(("del", p)))
        event_bus.publish(entry_added, {"id": 1})
        event_bus.publish(entry_deleted, {"entry_id": 1})
        self.assertEqual(log, [("add", {"id": 1}), ("del", {"entry_id": 1})])

if __name__ == "__main__":
    unittest.main()
