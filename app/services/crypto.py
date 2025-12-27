# Версия файла: 2.0.1
# Описание: Сервис шифрования/дешифрования для mp_seller_bot. Использует
# Fernet и ключ из конфигурации. Обеспечивает проверку ключа и
# безопасную работу с токенами.
# Дата изменения: 2025-12-28

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from config import settings

logger = logging.getLogger("crypto_service")


def _build_fernet_from_key(raw_key: str) -> Fernet:
    """
    Строит объект Fernet из текстового ключа.

    Ожидается, что raw_key — это корректный base64-ключ для Fernet
    (как в настройке FERNET_KEY / settings.fernet_key).

    В случае некорректного ключа возбуждается ValueError, чтобы
    ошибка была обнаружена сразу при старте приложения.
    """
    key = (raw_key or "").strip().encode("utf-8")
    try:
        return Fernet(key)
    except Exception as exc:  # ValueError, TypeError и др.
        logger.error("Неверный fernet_key в конфигурации: не удалось создать Fernet", exc_info=exc)
        raise ValueError("Invalid fernet_key for Fernet") from exc


class CryptoService:
    """
    Обёртка над Fernet для шифрования и дешифрования строк.

    Экземпляр инициализируется один раз и использует ключ из
    конфигурации (settings.fernet_key). Дополнительная проверка ключа
    выполняется функцией ``_build_fernet_from_key``, которая проверяет,
    что ключ подходит для Fernet и имеет корректный формат.
    """

    def __init__(self) -> None:
        # settings.fernet_key должен быть корректным base64-ключом Fernet.
        # _build_fernet_from_key валидирует его и поднимает ошибку при старте,
        # если ключ неправильный.
        self.fernet: Fernet = _build_fernet_from_key(settings.fernet_key)

    def encrypt(self, value: str) -> str:
        """
        Возвращает строку, зашифрованную с помощью Fernet.

        :param value: исходная строка (plaintext)
        :return: строковый токен (ciphertext)
        """
        if value is None:
            value = ""
        token = self.fernet.encrypt(value.encode("utf-8"))
        return token.decode("utf-8")

    def decrypt(self, token: str) -> str:
        """
        Пытается расшифровать строку.

        :param token: строковый токен, ранее возвращённый encrypt()
        :return: исходная строка (plaintext)
        :raises InvalidToken: если токен повреждён или был зашифрован другим ключом
        """
        if token is None:
            return ""
        try:
            raw = self.fernet.decrypt(token.encode("utf-8"))
            return raw.decode("utf-8")
        except InvalidToken as exc:
            logger.error("Не удалось расшифровать токен (InvalidToken)", exc_info=exc)
            # Пробрасываем дальше, чтобы вызывающий код мог решить, что делать
            raise
