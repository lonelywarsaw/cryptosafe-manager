#!/usr/bin/env bash
# Первичная настройка после git clone на Linux (демо / разработка)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> CryptoSafe Manager — setup (Linux)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Нужен python3. Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi

if [ -f /etc/debian_version ] && ! python3 -c "import PyQt6" 2>/dev/null; then
  echo "Подсказка: для GUI на Debian/Ubuntu установите системные пакеты Qt:"
  echo "  sudo apt update"
  echo "  sudo apt install -y python3-venv python3-pip \\"
  echo "    libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \\"
  echo "    libxcb-keysyms1 libxcb-render-util0 libegl1 libglib2.0-0"
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Готово. Запуск: bash scripts/run_linux.sh"
