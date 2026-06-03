# Сборка установочного пакета .exe (PyInstaller) — только на Windows
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Error "Сначала выполните: .\scripts\setup_windows.ps1"
    exit 1
}

& ".\.venv\Scripts\Activate.ps1"
python scripts/build_executable.py

$exe = Join-Path $Root "dist\CryptoSafeManager\CryptoSafeManager.exe"
Write-Host ""
if (Test-Path $exe) {
    Write-Host "Готово. Установка на другой ПК: скопируйте всю папку"
    Write-Host "  dist\CryptoSafeManager\"
    Write-Host "и запустите CryptoSafeManager.exe"
} else {
    Write-Host "Проверьте каталог dist\CryptoSafeManager\"
}
