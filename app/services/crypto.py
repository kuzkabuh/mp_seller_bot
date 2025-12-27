"""
Версия файла: 1.0.0
Описание: Шифрование/дешифрование API ключей (Fernet) для mp_seller_bot
Дата изменения: 2025-12-27
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from config import settings


class CryptoService:
    def __init__(self) -> None:
        self.fernet = Fernet(settings.FERNET_KEY.encode("utf-8"))

    def encrypt(self, value: str) -> str:
        token = self.fernet.encrypt(value.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: str) -> str:
        try:
            raw = self.fernet.decrypt(token.encode("utf-8"))
            return raw.decode("utf-8")
        except InvalidToken:
            raise ValueError("Не удалось расшифровать ключ. Проверьте FERNET_KEY.")
