entry_added = "entry_added"
entry_updated = "entry_updated"
entry_deleted = "entry_deleted"
user_logged_in = "user_logged_in"
user_logged_out = "user_logged_out"
clipboard_copied = "clipboard_copied"
clipboard_cleared = "clipboard_cleared"

class EventBus:
    def __init__(self):
        self._handlers = {}

    def subscribe(self, event, handler):
        if event not in self._handlers:
            self._handlers[event] = []
        self._handlers[event].append(handler)

    def publish(self, event, payload=None):
        if payload is None:
            payload = {}
        if event not in self._handlers:
            return
        for h in self._handlers[event]:
            try:
                h(event, payload)
            except Exception:
                pass

event_bus = EventBus()
