# Build install package with PyInstaller (Windows only)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Error "Run first: .\scripts\setup_windows.ps1"
    exit 1
}

& ".\.venv\Scripts\Activate.ps1"
python scripts/build_executable.py

$exe = Join-Path $Root "dist\CryptoSafeManager\CryptoSafeManager.exe"
Write-Host ""
if (Test-Path $exe) {
    Write-Host "Done. Copy the whole folder to another PC:"
    Write-Host "  dist\CryptoSafeManager\"
    Write-Host "Then run CryptoSafeManager.exe"
} else {
    Write-Host "Check folder: dist\CryptoSafeManager\"
}
