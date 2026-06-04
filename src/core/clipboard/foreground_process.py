"""Foreground window process name for clipboard whitelist checks."""

from __future__ import annotations

import os
import sys
from typing import Optional


def get_foreground_process_name() -> Optional[str]:
    """Basename of the executable for the foreground window, or None if unknown."""
    if sys.platform == "win32":
        return _win32_foreground_process_name()
    if sys.platform == "darwin":
        return _macos_foreground_process_name()
    if sys.platform.startswith("linux"):
        return _linux_foreground_process_name()
    return None


def _win32_foreground_process_name() -> Optional[str]:
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            size = wintypes.DWORD(260)
            buf = ctypes.create_unicode_buffer(size.value)
            if hasattr(kernel32, "QueryFullProcessImageNameW"):
                if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                    return None
                path = buf.value
            else:
                psapi = ctypes.windll.psapi
                if not psapi.GetModuleFileNameExW(handle, None, buf, size.value):
                    return None
                path = buf.value
            return os.path.basename(path) if path else None
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return None


def _macos_foreground_process_name() -> Optional[str]:
    try:
        import subprocess

        script = (
            'tell application "System Events" to get name of first process '
            'whose frontmost is true'
        )
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        name = (proc.stdout or "").strip()
        return name or None
    except Exception:
        return None


def _linux_foreground_process_name() -> Optional[str]:
    try:
        import subprocess

        proc = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowpid"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if proc.returncode != 0:
            return None
        pid = (proc.stdout or "").strip()
        if not pid.isdigit():
            return None
        comm_path = f"/proc/{pid}/comm"
        if os.path.isfile(comm_path):
            with open(comm_path, encoding="utf-8", errors="replace") as fh:
                return (fh.read() or "").strip() or None
    except Exception:
        return None
    return None
