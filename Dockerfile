# DEP-2: заглушка для сборки (Sprint 8)
# Сборка и упаковка приложения в контейнер.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Запуск (для GUI нужен доступ к дисплею или headless-режим)
CMD ["python", "-m", "src.main"]
