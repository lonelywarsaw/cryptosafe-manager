#!/usr/bin/env bash
# Первичная настройка после git clone на macOS
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> CryptoSafe Manager — setup (macOS)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Нужен python3. Установите Xcode Command Line Tools: xcode-select --install"
  exit 1
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Готово. Запуск: bash scripts/run_macos.sh"
echo "Сборка приложения для установки: bash scripts/build_macos.sh"
