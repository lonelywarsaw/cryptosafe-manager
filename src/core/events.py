"""In-process event bus for decoupled modules. / Шина событий между GUI, БД и аудитом."""

import queue
import threading

# названия событий — строки, по ним подписываются и публикуют
EntryAdded = "EntryAdded"
EntryCreated = "EntryCreated"
EntryUpdated = "EntryUpdated"
EntryDeleted = "EntryDeleted"
UserLoggedIn = "UserLoggedIn"
UserLoggedOut = "UserLoggedOut"
ClipboardCopied = "ClipboardCopied"
ClipboardCleared = "ClipboardCleared"
VaultExported = "VaultExported"
VaultImported = "VaultImported"
EntryShared = "EntryShared"
VaultLocked = "VaultLocked"
PanicModeActivated = "PanicModeActivated"
SecurityProfileChanged = "SecurityProfileChanged"
BackupCreated = "BackupCreated"
BackupRestored = "BackupRestored"

# словарь: тип события → список callback-функций
_subscribers = {}
# очередь для асинхронных событий — вызов выполняется в фоновом потоке
_async_queue = queue.Queue()
_worker_running = True


def subscribe(event_type, callback):
    """Register callback for event_type. / Подписывает callback на тип события."""
    if event_type not in _subscribers:
        _subscribers[event_type] = []
    _subscribers[event_type].append(callback)


def publish(event_type, sync=True, **kwargs):
    """Publish event to subscribers (sync or queued). / Публикует событие подписчикам."""
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
    """Stop async event worker thread. / Останавливает фоновый поток событий."""
    global _worker_running
    _worker_running = False
