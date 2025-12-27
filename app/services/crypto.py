# Версия файла: 2.0.0
# Описание: Сервис шифрования/дешифрования для mp_seller_bot. Использует
# Fernet и ключ из конфигурации. Обеспечивает проверку ключа и
# безопасную работу с токенами.
# Дата изменения: 2025-12-27

from __future__ import annotations

from cryptography.fernet import Fernet

from config import settings
from security.crypto import build_fernet


class CryptoService:
    """
    Обёртка над Fernet для шифрования и дешифрования строк.

    Экземпляр инициализируется один раз и использует ключ из
    конфигурации. Дополнительная проверка ключа выполняется
    функцией ``build_fernet``, которая нормализует base64‑строку и
    гарантирует корректную длину.
    """

    def __init__(self) -> None:
        # settings.fernet_key может быть в обычном base64. build_fernet
        # нормализует его в urlsafe формат.
        self.fernet: Fernet = build_fernet(settings.fernet_key)

    def encrypt(self, value: str) -> str:
        """Возвращает строку, зашифрованную с помощью Fernet."""
        token = self.fernet.encrypt(value.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: str) -> str:
        """Пытается расшифровать строку. При неудаче генерирует исключение."""
        raw = self.fernet.decrypt(token.encode("utf-8"))
        return raw.decode("utf-8")