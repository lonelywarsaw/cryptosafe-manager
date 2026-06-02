#!/usr/bin/env bash
# Запуск GUI на Linux после setup_linux.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "Сначала выполните: bash scripts/setup_linux.sh"
  exit 1
fi

# shellcheck source=/dev/null
source .venv/bin/activate

if [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
  echo "Предупреждение: DISPLAY не задан — нужна графическая сессия (локальный рабочий стол или SSH с X11)."
fi

exec python run.py
