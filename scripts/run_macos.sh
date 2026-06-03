#!/usr/bin/env bash
# Запуск GUI на macOS после setup_macos.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "Сначала выполните: bash scripts/setup_macos.sh"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate
exec python run.py
