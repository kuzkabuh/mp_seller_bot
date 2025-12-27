"""
Версия файла: 2.1.0
Описание: Обработчики подключения и отключения ключей для Wildberries и Ozon (безопасный ввод, удаление сообщений, проверка формата, просмотр статуса).
Дата изменения: 2025-12-28

Модуль предоставляет пользователю команды для отправки API ключей. Ключи
шифруются и сохраняются в базе данных.

Улучшения:
- Безопасный ввод: попытка удалить сообщение с ключом; если Telegram не разрешит — честно просим удалить вручную.
- Нормализация и валидация ключей/Client ID: убираем пробелы по краям, запрещаем переносы строк, проверяем символы, проверяем длину.
- Ввод Ozon: поддержка разделителей "пробел", ":" и "|" (часто так присылают), с фильтрацией лишних частей.
- Добавлена команда/кнопка "Показать подключения" (статус: WB/Ozon подключены или отключены).
- Унифицированы ответы и навигация: используем главное меню.
- FSM: корректная отмена через кнопку "Отмена" и текст "Отмена" в любом регистре.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.keyboards.menu import (
    BTN_CANCEL,
    BTN_CONNECT_OZON,
    BTN_CONNECT_WB,
    BTN_DISCONNECT_OZON,
    BTN_DISCONNECT_WB,
    BTN_SHOW_CONNECTIONS,
    main_menu,
)
from db import SessionLocal
from db.repo import Repo
from services.crypto import CryptoService

logger = logging.getLogger(__name__)

router = Router()

# Ограничения по длине ключей
WB_KEY_MIN_LEN = 200
WB_KEY_MAX_LEN = 2000

OZON_KEY_MIN_LEN = 20
OZON_KEY_MAX_LEN = 5000

CLIENT_ID_MIN_LEN = 5
CLIENT_ID_MAX_LEN = 64


class KeyStates(StatesGroup):
    waiting_wb_key = State()
    waiting_ozon_key = State()


def normalize_key(text: str) -> str:
    """
    Нормализуем ввод:
    - трим пробелы
    - удаляем нулевые символы
    - запрещаем переносы строк (ключ должен быть в одном сообщении)
    """
    t = (text or "").replace("\x00", "").strip()
    t = t.replace("\r", " ").replace("\n", " ").strip()
    return t


def _is_cancel_text(text: str) -> bool:
    t = (text or "").strip().lower()
    return t == "отмена" or t == BTN_CANCEL.lower()


def looks_like_key(text: str) -> bool:
    return len((text or "").strip()) >= 10


def _validate_single_line(value: str) -> bool:
    return "\n" not in value and "\r" not in value


def _validate_reasonable_chars(value: str) -> bool:
    """
    Очень мягкая проверка символов (не ломаем реальные ключи):
    - запрещаем пробелы внутри (часто ломают ключ)
    - запрещаем кавычки и обратные кавычки (часто копируют с ними)
    Допускаем буквы/цифры/._- и т.п. (проверка неполная и намеренно мягкая).
    """
    if not value:
        return False
    if " " in value or "\t" in value:
        return False
    if any(ch in value for ch in ['"', "'", "`"]):
        return False
    return True


def _parse_ozon_input(raw: str) -> Optional[Tuple[str, str]]:
    """
    Парсинг Ozon: ожидаем client_id и api_key.

    Поддерживаем разделители:
    - пробелы
    - двоеточие :
    - вертикальная черта |
    - точка с запятой ;

    Возвращает (client_id, api_key) или None.
    """
    txt = normalize_key(raw)
    if not txt:
        return None

    # Часто присылают: "client_id:api_key", "client_id api_key", "client_id|api_key"
    parts = re.split(r"[\s:|;]+", txt)
    parts = [p for p in parts if p]

    if len(parts) < 2:
        return None

    client_id = parts[0]
    api_key = parts[1]
    return client_id, api_key


async def _try_delete_sensitive_message(message: Message) -> bool:
    """
    Пытаемся удалить сообщение пользователя с ключом.
    Возвращает True если удаление удалось, иначе False.
    """
    try:
        await message.delete()
        return True
    except Exception as e:
        logger.info("Cannot delete user message (likely no rights or old message): %s", e)
        return False


async def _ensure_user(repo: Repo, message: Message):
    return await repo.get_or_create_user(
        tg_user_id=message.from_user.id,
        tg_username=message.from_user.username,
    )


def _manual_delete_notice() -> str:
    return (
        "Я не смог удалить ваше сообщение с ключом (ограничения Telegram или нет прав на удаление).\n"
        "Пожалуйста, удалите это сообщение вручную для безопасности."
    )


# ----------------------------
# Старт подключения
# ----------------------------
@router.message(F.text == BTN_CONNECT_WB)
async def connect_wb(message: Message, state: FSMContext) -> None:
    await state.set_state(KeyStates.waiting_wb_key)
    await message.answer(
        "Отправьте API-ключ Wildberries одним сообщением.\n"
        "Ключ будет сохранён в базе данных в зашифрованном виде.\n\n"
        "Важно:\n"
        "- Не пересылайте ключ в группы/чаты.\n"
        "- После сохранения я попробую удалить ваше сообщение с ключом.\n\n"
        f"Чтобы отменить — нажмите «{BTN_CANCEL}».",
        reply_markup=main_menu(),
    )


@router.message(F.text == BTN_CONNECT_OZON)
async def connect_ozon(message: Message, state: FSMContext) -> None:
    await state.set_state(KeyStates.waiting_ozon_key)
    await message.answer(
        "Отправьте Client ID и Api-Key Ozon в одном сообщении, разделив их пробелом или двоеточием.\n"
        "Также можно использовать разделитель |.\n\n"
        "Примеры:\n"
        "<code>12345678:abcdef0123456789</code>\n"
        "<code>12345678 abcdef0123456789</code>\n"
        "<code>12345678|abcdef0123456789</code>\n\n"
        "Данные будут сохранены в базе в зашифрованном виде.\n"
        "После сохранения я попробую удалить ваше сообщение с данными.\n\n"
        f"Чтобы отменить — нажмите «{BTN_CANCEL}».",
        reply_markup=main_menu(),
    )


# ----------------------------
# Универсальная отмена (в любом состоянии)
# ----------------------------
@router.message(F.text.lower() == "отмена")
async def cancel_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено. Возвращаю в главное меню.", reply_markup=main_menu())


@router.message(F.text == BTN_CANCEL)
async def cancel_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено. Возвращаю в главное меню.", reply_markup=main_menu())


# ----------------------------
# Сохранение WB
# ----------------------------
@router.message(KeyStates.waiting_wb_key)
async def save_wb_key(message: Message, state: FSMContext) -> None:
    if _is_cancel_text(message.text or ""):
        await state.clear()
        await message.answer("Действие отменено. Возвращаю в главное меню.", reply_markup=main_menu())
        return

    key = normalize_key(message.text or "")

    # Валидация
    if not key or not looks_like_key(key):
        await message.answer(
            "Похоже, вы отправили пустое значение.\n"
            f"Отправьте API-ключ Wildberries одним сообщением или нажмите «{BTN_CANCEL}».",
            reply_markup=main_menu(),
        )
        return

    if not _validate_single_line(key):
        await message.answer(
            "Ключ должен быть в одном сообщении без переносов строк.\n"
            "Скопируйте ключ ещё раз и отправьте одним сообщением.",
            reply_markup=main_menu(),
        )
        return

    # У WB ключи могут быть очень длинные (около 500+), поэтому берём широкий диапазон.
    if not (WB_KEY_MIN_LEN <= len(key) <= WB_KEY_MAX_LEN):
        await message.answer(
            "Ключ Wildberries выглядит некорректно.\n"
            f"Ожидаем длину примерно {WB_KEY_MIN_LEN}–{WB_KEY_MAX_LEN} символов.\n"
            f"Попробуйте ещё раз или нажмите «{BTN_CANCEL}».",
            reply_markup=main_menu(),
        )
        return

    # Символы проверяем мягко (без фанатизма, но убираем очевидные ошибки)
    if not _validate_reasonable_chars(key):
        await message.answer(
            "Ключ Wildberries выглядит некорректно.\n"
            "Проверьте, что в ключе нет пробелов внутри и лишних кавычек.\n"
            f"Попробуйте ещё раз или нажмите «{BTN_CANCEL}».",
            reply_markup=main_menu(),
        )
        return

    crypto = CryptoService()
    encrypted_key = crypto.encrypt(key)

    async with SessionLocal() as session:
        repo = Repo(session)
        user = await _ensure_user(repo, message)

        # Wildberries не требует client_id
        await repo.upsert_credential(
            user_id=user.id,
            tg_user_id=message.from_user.id,
            marketplace="wb",
            encrypted_api_key=encrypted_key,
            encrypted_client_id=None,
        )

    await state.clear()

    deleted = await _try_delete_sensitive_message(message)
    if not deleted:
        await message.answer(_manual_delete_notice(), reply_markup=main_menu())

    await message.answer("Ключ Wildberries сохранён. Мониторинг включён.", reply_markup=main_menu())


# ----------------------------
# Сохранение Ozon
# ----------------------------
@router.message(KeyStates.waiting_ozon_key)
async def save_ozon_key(message: Message, state: FSMContext) -> None:
    if _is_cancel_text(message.text or ""):
        await state.clear()
        await message.answer("Действие отменено. Возвращаю в главное меню.", reply_markup=main_menu())
        return

    raw = normalize_key(message.text or "")

    parsed = _parse_ozon_input(raw)
    if not parsed:
        await message.answer(
            "Нужно указать два значения: Client ID и Api-Key, разделённые пробелом, двоеточием или символом |.\n"
            "Пример: <code>12345678:abcdef0123456789</code>\n"
            f"Попробуйте ещё раз или нажмите «{BTN_CANCEL}».",
            reply_markup=main_menu(),
        )
        return

    client_id, api_key = parsed

    # Валидация client_id
    if not (CLIENT_ID_MIN_LEN <= len(client_id) <= CLIENT_ID_MAX_LEN):
        await message.answer(
            "Client ID выглядит некорректно.\n"
            f"Ожидаем {CLIENT_ID_MIN_LEN}–{CLIENT_ID_MAX_LEN} символов, сейчас: {len(client_id)}.\n"
            f"Попробуйте ещё раз или нажмите «{BTN_CANCEL}».",
            reply_markup=main_menu(),
        )
        return

    if not _validate_reasonable_chars(client_id):
        await message.answer(
            "Client ID выглядит некорректно.\n"
            "Проверьте, что в нём нет пробелов внутри и лишних кавычек.\n"
            f"Попробуйте ещё раз или нажмите «{BTN_CANCEL}».",
            reply_markup=main_menu(),
        )
        return

    # Валидация api_key
    if not (OZON_KEY_MIN_LEN <= len(api_key) <= OZON_KEY_MAX_LEN):
        await message.answer(
            "Api-Key выглядит некорректно.\n"
            f"Ожидаем {OZON_KEY_MIN_LEN}–{OZON_KEY_MAX_LEN} символов, сейчас: {len(api_key)}.\n"
            f"Попробуйте ещё раз или нажмите «{BTN_CANCEL}».",
            reply_markup=main_menu(),
        )
        return

    if not _validate_reasonable_chars(api_key):
        await message.answer(
            "Api-Key выглядит некорректно.\n"
            "Проверьте, что в ключе нет пробелов внутри и лишних кавычек.\n"
            f"Попробуйте ещё раз или нажмите «{BTN_CANCEL}».",
            reply_markup=main_menu(),
        )
        return

    crypto = CryptoService()
    encrypted_key = crypto.encrypt(api_key)
    encrypted_client_id = crypto.encrypt(client_id)

    async with SessionLocal() as session:
        repo = Repo(session)
        user = await _ensure_user(repo, message)

        await repo.upsert_credential(
            user_id=user.id,
            tg_user_id=message.from_user.id,
            marketplace="ozon",
            encrypted_api_key=encrypted_key,
            encrypted_client_id=encrypted_client_id,
        )

    await state.clear()

    deleted = await _try_delete_sensitive_message(message)
    if not deleted:
        await message.answer(_manual_delete_notice(), reply_markup=main_menu())

    await message.answer("Учётные данные Ozon сохранены. Мониторинг включён.", reply_markup=main_menu())


# ----------------------------
# Отключение/деактивация
# ----------------------------
@router.message(F.text == BTN_DISCONNECT_WB)
async def disable_wb(message: Message) -> None:
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await _ensure_user(repo, message)
        await repo.deactivate_credential(user.id, "wb")
    await message.answer("Wildberries отключён для мониторинга.", reply_markup=main_menu())


@router.message(F.text == BTN_DISCONNECT_OZON)
async def disable_ozon(message: Message) -> None:
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await _ensure_user(repo, message)
        await repo.deactivate_credential(user.id, "ozon")
    await message.answer("Ozon отключён для мониторинга.", reply_markup=main_menu())


# ----------------------------
# Статус подключений
# ----------------------------
@router.message(F.text == BTN_SHOW_CONNECTIONS)
async def show_connections(message: Message) -> None:
    """
    Показывает статус подключений (активно/неактивно) без вывода токенов.
    Требует метода Repo.get_credentials_status(...) или аналогичного.

    Если такого метода нет — см. блок ниже "Какой файл прислать следующим".
    """
    async with SessionLocal() as session:
        repo = Repo(session)
        user = await _ensure_user(repo, message)

        wb_active: Optional[bool] = None
        ozon_active: Optional[bool] = None

        # 1) Пытаемся использовать специализированный метод, если он есть
        if hasattr(repo, "get_credentials_status"):
            try:
                status = await repo.get_credentials_status(user.id)
                wb_active = bool(status.get("wb")) if isinstance(status, dict) else None
                ozon_active = bool(status.get("ozon")) if isinstance(status, dict) else None
            except Exception:
                wb_active = None
                ozon_active = None

        # 2) Иначе пробуем fallback-метод (если в Repo есть get_active_credential / get_credential)
        if wb_active is None and hasattr(repo, "get_active_credential"):
            try:
                wb_active = (await repo.get_active_credential(user.id, "wb")) is not None
            except Exception:
                wb_active = None

        if ozon_active is None and hasattr(repo, "get_active_credential"):
            try:
                ozon_active = (await repo.get_active_credential(user.id, "ozon")) is not None
            except Exception:
                ozon_active = None

    def _fmt(v: Optional[bool]) -> str:
        if v is True:
            return "Подключено"
        if v is False:
            return "Не подключено"
        return "Не удалось определить"

    text = (
        "Статус подключений:\n"
        f"- Wildberries: {_fmt(wb_active)}\n"
        f"- Ozon: {_fmt(ozon_active)}\n\n"
        "Для подключения используйте раздел «Подключения».\n"
        "Токены не отображаются."
    )
    await message.answer(text, reply_markup=main_menu())


"""
Какой файл прислать следующим (по логике):

1) db/repo.py
   Причина: я добавил обработчик «Показать подключения», который пытается вызвать
   Repo.get_credentials_status / Repo.get_active_credential. Нужно привести Repo к
   единому интерфейсу и гарантировать, что статус определяется корректно.

2) (Опционально) db/models.py
   Причина: важно понять, как у вас хранится credential (active, marketplace, user_id и т.д.),
   чтобы корректно реализовать методы Repo и не ломать миграции.

Если хочешь — начнём с db/repo.py. Пришли его следующим.
"""
