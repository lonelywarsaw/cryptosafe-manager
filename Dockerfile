# Спринт 8 (DEP-2): воспроизводимая среда на Linux (CI / разработка).
# Важно: Windows .exe этим Dockerfile НЕ собирается — только PyInstaller на Windows
# (scripts/build_windows.ps1). В контейнере можно запускать из исходников или тесты.

FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-venv \
    libxcb-cursor0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 \
    libxcb-keysyms1 libxcb-render-util0 libegl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# GUI на хосте: docker run --rm -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix cryptosafe-manager
# Только тесты: docker run --rm cryptosafe-manager pytest tests/ -q --ignore=tests/test_integration.py
CMD ["python", "run.py"]
