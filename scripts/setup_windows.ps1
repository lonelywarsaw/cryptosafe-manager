# Setup after git clone on Windows (dev / build .exe)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "==> CryptoSafe Manager - setup (Windows)"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python 3.8+ required. Install from https://www.python.org/downloads/ (check Add to PATH)."
    exit 1
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

& ".\.venv\Scripts\Activate.ps1"
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "Done. Run app: .\scripts\run_windows.ps1"
Write-Host "Build .exe:    .\scripts\build_windows.ps1"
