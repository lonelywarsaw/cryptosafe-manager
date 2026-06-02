#!/usr/bin/env python3
"""Запуск CryptoSafe Manager из исходников (спринт 8, PKG-3)."""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from main import main

if __name__ == "__main__":
    sys.exit(main())
