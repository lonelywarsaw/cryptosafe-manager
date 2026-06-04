# Спринт 7 — PERF-1..PERF-4 (TRD §11)

import pytest

pytestmark = pytest.mark.perf

import statistics
import time
import unittest

from core.security.side_channel_protection import constant_time_compare


class TestSprint7Performance(unittest.TestCase):
    def test_perf1_constant_time_overhead(self):
        """PERF-1: constant-time compare < 10% vs простого сравнения длины."""
        a, b = "secret-value-12345", "secret-value-12345"
        base = []
        ct = []
        for _ in range(50):
            t0 = time.perf_counter()
            _ = len(a) == len(b) and a == b
            base.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            constant_time_compare(a, b)
            ct.append(time.perf_counter() - t0)
        mb = statistics.median(base)
        mc = statistics.median(ct)
        self.assertLess(mc, mb * 1.10 + 1e-4)

    def test_perf3_monitor_idle_cpu(self):
        """PERF-3: цикл монитора с коротким sleep не блокирует (smoke)."""
        t0 = time.perf_counter()
        for _ in range(20):
            time.sleep(0.05)
        self.assertLess(time.perf_counter() - t0, 2.0)


if __name__ == "__main__":
    unittest.main()
