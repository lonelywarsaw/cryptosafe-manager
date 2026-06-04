#!/usr/bin/env python3
"""Собрать index.html из junit.xml и coverage.xml (без повторного pytest)."""

from __future__ import annotations

import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "tests", "report")
JUNIT_PATH = os.path.join(REPORT_DIR, "junit.xml")
COV_XML_PATH = os.path.join(REPORT_DIR, "coverage.xml")
INDEX_HTML_PATH = os.path.join(REPORT_DIR, "index.html")


def _load_generator():
    path = os.path.join(ROOT, "scripts", "generate_test_report.py")
    spec = importlib.util.spec_from_file_location("generate_test_report", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    if not os.path.isfile(JUNIT_PATH):
        print(f"Нет {JUNIT_PATH}. Запустите: python scripts/generate_test_report.py", file=sys.stderr)
        return 1

    gen = _load_generator()
    junit = gen._parse_junit(JUNIT_PATH)
    cov_total, modules = (
        gen._parse_coverage(COV_XML_PATH) if os.path.isfile(COV_XML_PATH) else (0.0, [])
    )
    gen._write_index_html(
        junit=junit,
        cov_total=cov_total,
        modules=modules,
        rc=0,
        fast_elapsed=0.0,
        fast_ok=True,
    )
    print(f"Wrote {INDEX_HTML_PATH}")
    cov_html = os.path.join(REPORT_DIR, "coverage_html", "index.html")
    if os.path.isfile(cov_html):
        print(f"Coverage HTML: {cov_html}")
    else:
        print("Для coverage_html/index.html нужен полный: python scripts/generate_test_report.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
