"""QR-кодек: сжатый payload, чанки, checksum, рендер и сканирование PNG."""

import base64
import hashlib
import hmac
import json
import zlib
import time
import secrets
from typing import Any, Dict, List, Optional, Tuple

PAYLOAD_TYPES = ("public_key", "share_package", "share_link")
MAX_CHUNK_LEN = 900
QR_PREFIX = "CSM1:"


def _checksum(payload_bytes: bytes, secret: bytes = b"cryptosafe-qr-v1") -> str:
    return hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()[:16]


def build_payload(payload_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Собирает сжатый QR-payload с checksum и TTL.

    Args:
        payload_type: public_key, share_package или share_link.
        data: Полезная нагрузка для типа.

    Returns:
        Тело payload (v, blob, ts, nonce, ttl_sec, checksum).
    """
    if payload_type not in PAYLOAD_TYPES:
        raise ValueError(f"payload_type: {PAYLOAD_TYPES}")
    inner = json.dumps({"type": payload_type, "data": data}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    compressed = base64.b64encode(zlib.compress(inner)).decode("ascii")
    body = {
        "v": 1,
        "blob": compressed,
        "ts": int(time.time()),
        "nonce": secrets.token_hex(8),
        "ttl_sec": 300,
    }
    raw = json.dumps(body, sort_keys=True).encode("utf-8")
    body["checksum"] = _checksum(raw)
    return body


def encode_chunks(payload: Dict[str, Any]) -> List[str]:
    """Разбивает payload на строки с префиксом CSM1: (одна или несколько частей).

    Returns:
        Список строк для печати в QR.
    """
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    if len(raw) <= MAX_CHUNK_LEN:
        return [QR_PREFIX + raw]
    chunks: List[str] = []
    total = (len(raw) + MAX_CHUNK_LEN - 1) // MAX_CHUNK_LEN
    for i in range(total):
        part = raw[i * MAX_CHUNK_LEN : (i + 1) * MAX_CHUNK_LEN]
        chunk_obj = {"v": 1, "chunk": i, "total": total, "data": part}
        chunks.append(QR_PREFIX + json.dumps(chunk_obj, ensure_ascii=False))
    return chunks


def decode_chunks(lines: List[str]) -> Dict[str, Any]:
    """Собирает и проверяет QR-строки; возвращает расшифрованный inner (type, data).

    Args:
        lines: Строки со сканера (с префиксом CSM1:).

    Returns:
        dict с ключами type и data.
    """
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line.startswith(QR_PREFIX):
            raise ValueError("Неверный префикс QR")
        cleaned.append(line[len(QR_PREFIX) :])
    if len(cleaned) == 1:
        obj = json.loads(cleaned[0])
        if "chunk" in obj:
            raise ValueError("Неполный набор chunk QR")
        return _validate_payload(obj)
    parts = sorted(
        [json.loads(x) for x in cleaned],
        key=lambda o: int(o.get("chunk", 0)),
    )
    total = parts[0].get("total")
    if len(parts) != total:
        raise ValueError("Неполный набор chunk QR")
    merged = "".join(p["data"] for p in parts)
    return _validate_payload(json.loads(merged))


def _validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    checksum = payload.pop("checksum", None)
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    if not checksum or not hmac.compare_digest(_checksum(raw), checksum):
        raise ValueError("Неверная контрольная сумма QR")
    ts = int(payload.get("ts") or 0)
    ttl = int(payload.get("ttl_sec") or 300)
    if ts > 0 and ttl > 0 and time.time() > (ts + ttl):
        raise ValueError("QR payload expired")
    blob = payload.get("blob", "")
    inner = zlib.decompress(base64.b64decode(blob.encode("ascii")))
    decoded = json.loads(inner.decode("utf-8"))
    if decoded.get("type") not in PAYLOAD_TYPES:
        raise ValueError("Неподдерживаемый тип QR")
    return decoded


def render_qr_png(text: str, *, error_correction: str = "M") -> bytes:
    """Рендерит QR в PNG-байты (нужен пакет qrcode).

    Args:
        text: Данные для кодирования.
        error_correction: Уровень коррекции: L, M, Q или H.

    Returns:
        Содержимое PNG-файла.
    """
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("Установите пакет qrcode для генерации PNG") from exc
    level = {
        "L": qrcode.constants.ERROR_CORRECT_L,
        "M": qrcode.constants.ERROR_CORRECT_M,
        "Q": qrcode.constants.ERROR_CORRECT_Q,
        "H": qrcode.constants.ERROR_CORRECT_H,
    }.get(error_correction.upper(), qrcode.constants.ERROR_CORRECT_M)
    qr = qrcode.QRCode(error_correction=level)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image()
    import io

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def decode_qr_image(image_path: str) -> str:
    """Читает первый QR с изображения (pyzbar + Pillow).

    Returns:
        Текст из QR.
    """
    try:
        from pyzbar.pyzbar import decode as zbar_decode
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Для сканирования нужны pyzbar и Pillow") from exc
    img = Image.open(image_path)
    codes = zbar_decode(img)
    if not codes:
        raise ValueError("QR не найден на изображении")
    return codes[0].data.decode("utf-8", errors="replace")
