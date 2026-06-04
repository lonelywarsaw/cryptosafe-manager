#!/usr/bin/env python3
# TEST-3: отчёт pytest + coverage в tests/report/ (Markdown + HTML)

from __future__ import annotations

import html
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "tests", "report")
JUNIT_PATH = os.path.join(REPORT_DIR, "junit.xml")
COV_XML_PATH = os.path.join(REPORT_DIR, "coverage.xml")
COV_HTML_DIR = os.path.join(REPORT_DIR, "coverage_html")
SUMMARY_PATH = os.path.join(REPORT_DIR, "summary.md")
INDEX_HTML_PATH = os.path.join(REPORT_DIR, "index.html")


def _parse_junit(path: str) -> dict:
    if not os.path.isfile(path):
        return {"cases": []}
    root = ET.parse(path).getroot()
    if root.tag == "testsuites":
        suites = root.findall("testsuite")
    else:
        suites = [root]
    total = failures = errors = skipped = 0
    duration = 0.0
    failed_cases: list[str] = []
    cases: list[dict] = []
    for suite in suites:
        total += int(suite.attrib.get("tests", 0))
        failures += int(suite.attrib.get("failures", 0))
        errors += int(suite.attrib.get("errors", 0))
        skipped += int(suite.attrib.get("skipped", 0))
        duration += float(suite.attrib.get("time", 0) or 0)
        for case in suite.findall("testcase"):
            classname = case.attrib.get("classname", "")
            name = case.attrib.get("name", "")
            full = f"{classname}.{name}".strip(".")
            t = float(case.attrib.get("time", 0) or 0)
            status = "passed"
            if case.find("skipped") is not None:
                status = "skipped"
            elif case.find("failure") is not None or case.find("error") is not None:
                status = "failed"
                failed_cases.append(full)
            cases.append({"name": full, "time": t, "status": status})
    passed = total - failures - errors - skipped
    return {
        "total": total,
        "passed": passed,
        "failed": failures + errors,
        "skipped": skipped,
        "duration_sec": duration,
        "failed_cases": failed_cases,
        "cases": cases,
    }


def _parse_coverage(path: str) -> tuple[float, list[tuple[str, float]]]:
    if not os.path.isfile(path):
        return 0.0, []
    root = ET.parse(path).getroot()
    line_rate = float(root.attrib.get("line-rate", 0) or 0) * 100.0
    rows: list[tuple[str, float]] = []
    for cls in root.findall(".//class"):
        filename = (cls.attrib.get("filename") or "").replace("\\", "/")
        if not filename or filename.endswith("__init__.py"):
            continue
        rate = float(cls.attrib.get("line-rate", 0) or 0) * 100.0
        rows.append((filename, rate))
    rows.sort(key=lambda r: r[0])
    return line_rate, rows


def _write_index_html(
    *,
    junit: dict,
    cov_total: float,
    modules: list[tuple[str, float]],
    rc: int,
    fast_elapsed: float,
    fast_ok: bool,
) -> None:
    gen = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    cov_link = "coverage_html/index.html" if os.path.isfile(os.path.join(COV_HTML_DIR, "index.html")) else None

    case_rows = []
    for c in junit.get("cases", []):
        st = c["status"]
        badge = {"passed": "ok", "failed": "bad", "skipped": "skip"}.get(st, "")
        case_rows.append(
            f"<tr><td><span class='{badge}'>{html.escape(st)}</span></td>"
            f"<td><code>{html.escape(c['name'])}</code></td>"
            f"<td>{c['time']:.3f}</td></tr>"
        )

    mod_rows = "".join(
        f"<tr><td><code>{html.escape(fn)}</code></td><td>{rate:.1f}%</td></tr>"
        for fn, rate in modules
    )

    body = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8"/>
  <title>CryptoSafe — отчёт тестов</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 960px; }}
    h1 {{ font-size: 1.4rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ccc; padding: 0.4rem 0.6rem; text-align: left; }}
    th {{ background: #f0f0f0; }}
    .ok {{ color: #0a0; font-weight: bold; }}
    .bad {{ color: #c00; font-weight: bold; }}
    .skip {{ color: #880; }}
    .cards {{ display: flex; gap: 1rem; flex-wrap: wrap; }}
    .card {{ background: #f8f8f8; padding: 0.8rem 1.2rem; border-radius: 8px; }}
    a {{ color: #06c; }}
    .note {{ color: #555; font-size: 0.95rem; }}
  </style>
</head>
<body>
  <h1>Отчёт о тестировании (Sprint 8)</h1>
  <p class="note">Сформирован: {html.escape(gen)}. Откройте этот файл в браузере — не <code>junit.xml</code> / <code>coverage.xml</code> (они для программ).</p>

  <div class="cards">
    <div class="card"><strong>Всего тестов</strong><br/>{junit.get('total', '—')}</div>
    <div class="card"><strong>Пройдено</strong><br/><span class="ok">{junit.get('passed', '—')}</span></div>
    <div class="card"><strong>Провалено</strong><br/><span class="bad">{junit.get('failed', '—')}</span></div>
    <div class="card"><strong>Пропущено</strong><br/>{junit.get('skipped', '—')}</div>
    <div class="card"><strong>Покрытие</strong><br/>{cov_total:.1f}%</div>
    <div class="card"><strong>TEST-4</strong><br/>{fast_elapsed:.2f} с — {'OK' if fast_ok else 'FAIL'}</div>
  </div>

  <p>Код выхода pytest+cov: <strong>{rc}</strong></p>
  <p>
    <a href="summary.md">summary.md</a>
    {f' · <a href="{cov_link}">Покрытие по строкам (HTML)</a>' if cov_link else ''}
  </p>

  <h2>Тесты</h2>
  <table>
    <thead><tr><th>Статус</th><th>Тест</th><th>Время, с</th></tr></thead>
    <tbody>
      {''.join(case_rows) if case_rows else '<tr><td colspan="3">Нет данных (junit.xml)</td></tr>'}
    </tbody>
  </table>

  <h2>Покрытие по модулям</h2>
  <table>
    <thead><tr><th>Модуль</th><th>%</th></tr></thead>
    <tbody>{mod_rows or '<tr><td colspan="2">Нет данных</td></tr>'}</tbody>
  </table>
</body>
</html>
"""
    with open(INDEX_HTML_PATH, "w", encoding="utf-8") as f:
        f.write(body)


def main() -> int:
    os.makedirs(REPORT_DIR, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-q",
        "--ignore=tests/test_integration.py",
        "--ignore=tests/test_password_change_integration.py",
        "-m",
        "not perf and not slow",
        f"--junitxml={JUNIT_PATH}",
        "--cov=src",
        f"--cov-report=xml:{COV_XML_PATH}",
        f"--cov-report=html:{COV_HTML_DIR}",
        "--cov-report=term-missing:skip-covered",
        "--cov-config=.coveragerc",
        "--cov-fail-under=80",
    ]
    t0 = datetime.now(timezone.utc)
    rc = subprocess.call(cmd, cwd=ROOT)
    elapsed = (datetime.now(timezone.utc) - t0).total_seconds()

    junit = _parse_junit(JUNIT_PATH)
    cov_total, modules = _parse_coverage(COV_XML_PATH)

    timing_cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-q",
        "--no-cov",
        "--ignore=tests/test_integration.py",
        "--ignore=tests/test_password_change_integration.py",
        "-m",
        "not perf and not slow",
    ]
    t_fast = datetime.now(timezone.utc)
    rc_time = subprocess.call(timing_cmd, cwd=ROOT)
    fast_elapsed = (datetime.now(timezone.utc) - t_fast).total_seconds()
    fast_ok = fast_elapsed < 30 and rc_time == 0

    _write_index_html(
        junit=junit,
        cov_total=cov_total,
        modules=modules,
        rc=rc,
        fast_elapsed=fast_elapsed,
        fast_ok=fast_ok,
    )

    lines = [
        "# Отчёт о тестировании (Sprint 8)",
        "",
        f"Сформирован: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        "**Просмотр в браузере:** откройте `tests/report/index.html` (не XML-файлы).",
        "",
        "## Сводка тестов (TEST-1 / TEST-3)",
        "",
        "| Метрика | Значение |",
        "|---------|----------|",
        f"| Всего | {junit.get('total', '—')} |",
        f"| Пройдено | {junit.get('passed', '—')} |",
        f"| Провалено | {junit.get('failed', '—')} |",
        f"| Пропущено | {junit.get('skipped', '—')} |",
        f"| Время pytest | {junit.get('duration_sec', elapsed):.2f} с |",
        f"| Код выхода | {rc} |",
        "",
        f"**TEST-4 (прогон без `--cov`):** {fast_elapsed:.2f} с — {'OK' if fast_ok else 'FAIL'}",
        "",
        "## Покрытие кода (TEST-2)",
        "",
        f"**Итого (без GUI):** {cov_total:.1f}% (порог ≥ 80%)",
        "",
        "| Модуль | Покрытие |",
        "|--------|----------|",
    ]
    for filename, rate in modules:
        if filename:
            lines.append(f"| `{filename}` | {rate:.1f}% |")

    if junit.get("failed_cases"):
        lines.extend(["", "## Проваленные тесты", ""])
        for name in junit["failed_cases"]:
            lines.append(f"- `{name}`")

    lines.extend(
        [
            "",
            "## Артефакты",
            "",
            "- **HTML (для человека):** `tests/report/index.html`, `tests/report/coverage_html/index.html`",
            "- **XML (для CI/инструментов):** `junit.xml`, `coverage.xml`",
            "",
            "Пересоздать: `python scripts/generate_test_report.py`",
        ]
    )

    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Wrote {SUMMARY_PATH}")
    print(f"Open in browser: {INDEX_HTML_PATH}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
