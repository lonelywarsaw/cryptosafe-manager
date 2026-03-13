# состояние приложения: разблокировано ли хранилище, таймер буфера обмена, неактивность
# один экземпляр на всё приложение — все окна видят одно и то же

import time


class StateManager:
    # singleton: при первом вызове создаётся объект, дальше возвращается тот же
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        self._locked = True
        self._clipboard_timeout_sec = 30
        self._clipboard_seconds_left = 0
        self._clipboard_has_content = False
        self._last_activity_time = time.time()
        self._initialized = True

    def set_locked(self, locked):
        # хранилище заблокировано (True) или открыто (False)
        self._locked = bool(locked)

    def is_locked(self):
        return self._locked

    def set_clipboard_timeout(self, seconds):
        # через сколько секунд очищать буфер обмена после копирования пароля
        self._clipboard_timeout_sec = max(0, int(seconds))

    def reset_clipboard_timer(self):
        # после копирования в буфер таймер сбрасывается на заданный timeout
        self._clipboard_seconds_left = self._clipboard_timeout_sec
        self._clipboard_has_content = True

    def tick_clipboard_timer(self):
        # вызывать раз в секунду: счётчик уменьшается на 1
        if self._clipboard_seconds_left > 0:
            self._clipboard_seconds_left -= 1
        return self._clipboard_seconds_left

    def get_clipboard_seconds_left(self):
        return self._clipboard_seconds_left

    def clipboard_has_content(self):
        return self._clipboard_has_content

    def touch_activity(self):
        # обновляется время последней активности (для авто-блокировки)
        self._last_activity_time = time.time()

    def get_inactivity_seconds(self):
        # сколько секунд прошло с последнего touch_activity()
        return int(time.time() - self._last_activity_time)

    def get_state(self):
        # вся картина состояния — для статус-бара или отладки
        return {
            "locked": self._locked,
            "session": "locked" if self._locked else "unlocked",
            "clipboard_seconds_left": self._clipboard_seconds_left,
            "clipboard_timeout": self._clipboard_timeout_sec,
            "inactivity_seconds": self.get_inactivity_seconds(),
        }


def get_state_manager():
    # единственная точка доступа к StateManager (singleton)
    return StateManager()
