# Версия файла: 1.1.0
# Описание: Шифрование/дешифрование данных (Fernet), валидация ключа
# Дата изменения: 2025-12-27

from __future__ import annotations

import base64
import binascii

from cryptography.fernet import Fernet, InvalidToken


def _normalize_fernet_key(key_str: str) -> bytes:
    """
    Fernet ожидает urlsafe base64 32 bytes.
    Пользователь может вставить обычный base64 (openssl rand -base64 32).
    Мы нормализуем в urlsafe base64 и проверяем длину.
    """
    key_str = key_str.strip()

    try:
        raw = base64.b64decode(key_str)
    except (binascii.Error, ValueError) as e:
        raise ValueError("FERNET_KEY не является base64 строкой") from e

    if len(raw) != 32:
        raise ValueError("FERNET_KEY должен декодироваться в 32 байта (openssl rand -base64 32)")

    return base64.urlsafe_b64encode(raw)


def build_fernet(key_str: str) -> Fernet:
    """
    Возвращает Fernet-инстанс. Если ключ обычный base64 — будет нормализован.
    """
    key_bytes = _normalize_fernet_key(key_str)
    return Fernet(key_bytes)


def encrypt_text(fernet: Fernet, plaintext: str) -> str:
    token = fernet.encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(fernet: Fernet, token: str) -> str:
    try:
        plaintext = fernet.decrypt(token.encode("utf-8"))
        return plaintext.decode("utf-8")
    except InvalidToken as e:
        raise ValueError("Не удалось расшифровать данные: неверный FERNET_KEY или поврежденный токен") from e
