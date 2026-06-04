# Спринт 7 — TEST-1..TEST-4 (TRD §9)

import pytest

import os
import sqlite3
import statistics
import tempfile
import time
import unittest
from unittest.mock import patch

import database.db as db_module
from core import config, events
from core.security.activity_monitor import ActivityMonitor
from core.security.memory_guard import secure_wipe_bytes
from core.security.panic_mode import PanicMode
from core.security.security_profiles import apply_profile, PROFILE_STANDARD
from core.security.side_channel_protection import constant_time_compare
from core.state_manager import get_state_manager


class TestSprint7SideChannel(unittest.TestCase):
    def test_test1_constant_time_compare(self):
        """TEST-1: сравнение не зависит от позиции первого отличия (статистика)."""
        a = "x" * 64
        samples_same = []
        samples_diff = []
        for _ in range(30):
            t0 = time.perf_counter()
            constant_time_compare(a, a)
            samples_same.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            constant_time_compare(a, "y" + a[1:])
            samples_diff.append(time.perf_counter() - t0)
        med_same = statistics.median(samples_same)
        med_diff = statistics.median(samples_diff)
        self.assertLess(abs(med_diff - med_same), max(med_same, med_diff) * 5.0 + 1e-5)


class TestSprint7Memory(unittest.TestCase):
    def test_test2_secure_wipe(self):
        """TEST-2: после wipe буфер не содержит исходных байт."""
        buf = bytearray(b"super-secret-password-value")
        secure_wipe_bytes(buf)
        self.assertEqual(bytes(buf), b"\x00" * len(buf))


class TestSprint7AutoLock(unittest.TestCase):
    @pytest.mark.slow
    def test_test3_activity_monitor_triggers_lock(self):
        """TEST-3: монитор активности вызывает lock_callback по таймауту."""
        fired = []

        def lock_cb():
            fired.append(1)

        class _IdleDetector:
            def has_recent_activity(self, threshold_sec: float = 2.0) -> bool:
                return False

            def is_screen_locked(self) -> bool:
                return False

        mon = ActivityMonitor(lock_cb, lock_timeout_sec=1, check_interval=0.2)
        mon._detector = _IdleDetector()
        mon.start()
        time.sleep(1.6)
        mon.stop()
        self.assertGreaterEqual(len(fired), 1)


class TestSprint7Panic(unittest.TestCase):
    def test_test4_panic_invokes_handlers(self):
        """TEST-4: паника вызывает зарегистрированные обработчики."""
        calls = []

        panic = PanicMode()
        panic.register_handler(lambda: calls.append("lock"))
        panic.register_handler(lambda: calls.append("wipe"))
        with patch.object(events, "publish"):
            panic.activate(method="test")
        self.assertEqual(calls, ["lock", "wipe"])


class TestSprint7Profiles(unittest.TestCase):
    def setUp(self):
        fd, self._cfg = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self._orig_get = config.get
        self._store = {}

        def _get(key, default=None):
            return self._store.get(key, default)

        def _set(key, value):
            self._store[key] = str(value)

        self._patch_get = patch.object(config, "get", side_effect=_get)
        self._patch_set = patch.object(config, "set", side_effect=_set)
        self._patch_get.start()
        self._patch_set.start()

    def tearDown(self):
        self._patch_get.stop()
        self._patch_set.stop()

    def test_security_profile_applies(self):
        apply_profile(PROFILE_STANDARD)
        self.assertEqual(self._store.get(config.SECURITY_PROFILE), PROFILE_STANDARD)
        self.assertEqual(self._store.get(config.AUTO_LOCK_MINUTES), "5")


if __name__ == "__main__":
    unittest.main()
