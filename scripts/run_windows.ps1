# Запуск GUI на Windows после setup_windows.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Error "Сначала выполните: .\scripts\setup_windows.ps1"
    exit 1
}

& ".\.venv\Scripts\Activate.ps1"
python run.py
