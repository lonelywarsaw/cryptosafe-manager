# Первичная настройка после git clone на Windows (разработка / сборка .exe)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> CryptoSafe Manager — setup (Windows)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Нужен Python 3.8+. Скачайте с https://www.python.org/downloads/ (галочка «Add to PATH»)."
    exit 1
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "Готово. Запуск: .\scripts\run_windows.ps1"
Write-Host "Сборка .exe для установки на ПК: .\scripts\build_windows.ps1"
