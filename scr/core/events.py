# шина событий: кто-то публикует событие — все подписчики получают вызов
# gui, бд и аудит не вызывают друг друга напрямую, а через события

import queue
import threading

# названия событий — строки, по ним подписываются и публикуют
EntryAdded = "EntryAdded"
EntryUpdated = "EntryUpdated"
EntryDeleted = "EntryDeleted"
UserLoggedIn = "UserLoggedIn"
UserLoggedOut = "UserLoggedOut"
ClipboardCopied = "ClipboardCopied"
ClipboardCleared = "ClipboardCleared"

# словарь: тип события → список callback-функций
_subscribers = {}
# очередь для асинхронных событий — вызов выполняется в фоновом потоке
_async_queue = queue.Queue()
_worker_running = True


def subscribe(event_type, callback):
    # регистрация callback для события; при publish() этот callback вызывается с kwargs
    if event_type not in _subscribers:
        _subscribers[event_type] = []
    _subscribers[event_type].append(callback)


def publish(event_type, sync=True, **kwargs):
    # sync=True — подписчики вызываются сразу; False — событие кладётся в очередь
    if sync:
        _notify(event_type, kwargs)
    else:
        _async_queue.put((event_type, kwargs))


def _notify(event_type, payload):
    # вызываются все подписчики данного события с переданным payload
    for cb in _subscribers.get(event_type, []):
        try:
            cb(**payload)
        except Exception:
            pass


def _worker():
    # фоновый поток: забирает события из очереди и вызывает для каждого _notify
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
    # останавливается фоновый поток (вызывать при выходе из приложения)
    global _worker_running
    _worker_running = False
