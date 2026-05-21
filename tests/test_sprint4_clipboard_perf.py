from __future__ import annotations

import time
import tracemalloc
import unittest
from unittest.mock import MagicMock, patch

from core.clipboard.clipboard_service import ClipboardService
from core.clipboard.platform_adapter import ClipboardAdapter


class _TestInMemoryAdapter(ClipboardAdapter):
    """In-memory адаптер для тестов производительности"""

    def __init__(self):
        self._content: str | None = None
        self._cleared = False

    def copy_to_clipboard(self, data: str) -> bool:
        self._content = data
        self._cleared = False
        return True

    def clear_clipboard(self) -> bool:
        self._content = None
        self._cleared = True
        return True

    def get_clipboard_content(self) -> str | None:
        return None if self._cleared else self._content


class TestSprint4ClipboardPerformance(unittest.TestCase):
    """Тесты производительности буфера обмена (Спринт 4)"""

    def _make_service(self) -> ClipboardService:
        adapter = _TestInMemoryAdapter()
        return ClipboardService(platform_adapter=adapter)

    @patch("core.clipboard.clipboard_service.get_state_manager")
    def test_perf_copy_under_100ms(self, mock_sm) -> None:
        """PERF-1: copy_text() выполняется < 100 ms"""
        mock_sm.return_value = MagicMock()
        svc = self._make_service()

        t0 = time.perf_counter()
        svc.copy_text("Password!123", data_type="password", source_entry_id="1")
        dt_ms = (time.perf_counter() - t0) * 1000.0

        self.assertLess(dt_ms, 100.0)

    @patch("core.clipboard.clipboard_service.get_state_manager")
    def test_perf_monitor_idle_cpu_under_1_percent(self, mock_sm) -> None:
        """PERF-2: мониторинг в idle < 1% CPU за 2 с"""
        mock_sm.return_value = MagicMock()
        svc = self._make_service()

        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        time.sleep(2.0)
        wall = time.perf_counter() - wall_start
        cpu = time.process_time() - cpu_start

        cpu_percent = (cpu / wall) * 100.0 if wall > 0 else 100.0
        self.assertLess(cpu_percent, 1.0)

    @patch("core.clipboard.clipboard_service.get_state_manager")
    def test_perf_memory_overhead_under_10mb(self, mock_sm) -> None:
        """PERF-3: пик памяти после 200 копий < 10 MB"""
        mock_sm.return_value = MagicMock()
        tracemalloc.start()
        svc = self._make_service()

        for i in range(200):
            svc.copy_text(f"secret-{i}", data_type="password", source_entry_id=str(i))

        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        self.assertLess(peak, 10 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()