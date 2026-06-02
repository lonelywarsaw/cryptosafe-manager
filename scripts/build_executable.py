#!/usr/bin/env python3
# Сборка исполняемого файла PyInstaller (спринт 8, PKG-1)

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    spec = os.path.join(ROOT, "cryptosafe.spec")
    if not os.path.isfile(spec):
        print("cryptosafe.spec not found", file=sys.stderr)
        return 1
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", spec]
    print("Running:", " ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
