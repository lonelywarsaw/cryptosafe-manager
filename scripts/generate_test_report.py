#!/usr/bin/env python3
# Генерация отчёта pytest + coverage (спринт 8, TEST-3)

import os
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "tests", "report")


def main() -> int:
    os.makedirs(REPORT_DIR, exist_ok=True)
    junit = os.path.join(REPORT_DIR, "junit.xml")
    cov_xml = os.path.join(REPORT_DIR, "coverage.xml")
    summary_path = os.path.join(REPORT_DIR, "summary.md")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-q",
        "--ignore=tests/test_integration.py",
        f"--junitxml={junit}",
        f"--cov=src",
        f"--cov-report=xml:{cov_xml}",
        f"--cov-report=term-missing:skip-covered",
    ]
    rc = subprocess.call(cmd, cwd=ROOT)

    lines = [
        "# Test report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        f"Exit code: {rc}",
        "",
        "Artifacts:",
        f"- `{os.path.relpath(junit, ROOT)}`",
        f"- `{os.path.relpath(cov_xml, ROOT)}`",
        "",
        "Regenerate: `python scripts/generate_test_report.py`",
    ]
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {summary_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
