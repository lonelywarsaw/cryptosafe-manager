# Кто-то шлёт события, кто-то на них подписан. Можно вызвать сразу или положить в очередь.

import queue
import threading

EntryAdded = "EntryAdded"
EntryUpdated = "EntryUpdated"
EntryDeleted = "EntryDeleted"
UserLoggedIn = "UserLoggedIn"
UserLoggedOut = "UserLoggedOut"
ClipboardCopied = "ClipboardCopied"
ClipboardCleared = "ClipboardCleared"

_subscribers = {}
_async_queue = queue.Queue()
_worker_running = True


def subscribe(event_type, callback):
    if event_type not in _subscribers:
        _subscribers[event_type] = []
    _subscribers[event_type].append(callback)


def publish(event_type, sync=True, **kwargs):
    if sync:
        _notify(event_type, kwargs)
    else:
        _async_queue.put((event_type, kwargs))


def _notify(event_type, payload):
    for cb in _subscribers.get(event_type, []):
        try:
            cb(**payload)
        except Exception:
            pass


def _worker():
    global _worker_running
    while _worker_running:
        try:
            event_type, payload = _async_queue.get(timeout=0.2)
            _notify(event_type, payload)
        except queue.Empty:
            continue


_worker_thread = threading.Thread(target=_worker, daemon=True)
_worker_thread.start()


def shutdown():
    global _worker_running
    _worker_running = False
