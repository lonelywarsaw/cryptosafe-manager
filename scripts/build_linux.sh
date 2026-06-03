#!/usr/bin/env bash
# Сборка установочного пакета на Linux (PyInstaller)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "Сначала выполните: bash scripts/setup_linux.sh"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate
python scripts/build_executable.py

echo ""
echo "Готово. Установка на другой ПК: скопируйте папку dist/CryptoSafeManager/ и запустите ./CryptoSafeManager"
