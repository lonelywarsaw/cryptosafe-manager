# CryptoSafe Manager - build stub for Sprint 8 packaging.
# Not intended for production run in Sprint 1.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Stub: real entrypoint and user in Sprint 8
RUN useradd -m appuser
USER appuser

CMD ["python", "main.py"]
