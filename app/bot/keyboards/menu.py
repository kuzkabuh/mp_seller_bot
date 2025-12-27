"""
Версия файла: 2.1.0
Описание: Набор клавиатур для основного и вложенных меню бота (многоуровневое меню, периоды, выбор маркетплейса, навигация).
Дата изменения: 2025-12-28

В этом модуле определены функции, возвращающие различные варианты клавиатур,
которые используются для организации многоуровневого меню в Telegram-боте.

Ключевые улучшения:
- Добавлены явные меню выбора маркетплейса (WB / Ozon / Оба) для сценария:
  Заказы → период → выбор МП → детали.
- Добавлены кнопки "Назад" на каждом уровне (единая навигация).
- Добавлены отдельные меню для "Подсказок/лайфхаков": быстрый лайфхак и "лайфхак по тексту".
- Добавлена клавиатура "Отмена" для безопасного ввода токена/операций ввода.
- Добавлены вспомогательные функции/константы для единообразия текста кнопок.
"""

from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


# ----------------------------
# Константы текста кнопок
# ----------------------------
BTN_ORDERS = "Заказы"
BTN_CONNECTIONS = "Подключения"
BTN_ANALYTICS = "Аналитика"
BTN_TIPS = "Подсказки"
BTN_HELP = "Помощь"

BTN_BACK_TO_MENU = "Назад в меню"
BTN_BACK = "Назад"
BTN_CANCEL = "Отмена"

# Заказы: периоды
BTN_TODAY = "Сегодня"
BTN_YESTERDAY = "Вчера"
BTN_7_DAYS = "7 дней"
BTN_30_DAYS = "30 дней"
BTN_PERIOD = "Период"

# Выбор маркетплейса
BTN_MP_WB = "Wildberries"
BTN_MP_OZON = "Ozon"
BTN_MP_BOTH = "Оба"

# Подключения
BTN_CONNECT_WB = "Подключить Wildberries"
BTN_CONNECT_OZON = "Подключить Ozon"
BTN_DISCONNECT_WB = "Отключить WB"
BTN_DISCONNECT_OZON = "Отключить Ozon"
BTN_SHOW_CONNECTIONS = "Показать подключения"

# Аналитика
BTN_REVENUE = "Выручка"
BTN_SALES = "Продажи"
BTN_STOCKS = "Остатки"
BTN_COMMISSION = "Комиссии"
BTN_ANALYTICS_7 = "Аналитика 7 дней"

# Подсказки/лайфхаки
BTN_GET_TIP = "Получить лайфхак"
BTN_TIP_FOR_TEXT = "Лайфхак по тексту"
BTN_TIPS_RULES = "Как это работает"


def _mk_kb(rows: list[list[str]], placeholder: str) -> ReplyKeyboardMarkup:
    """
    Внутренний хелпер для сборки ReplyKeyboardMarkup.
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t) for t in row] for row in rows],
        resize_keyboard=True,
        input_field_placeholder=placeholder,
    )


# ----------------------------
# Главное меню
# ----------------------------
def main_menu() -> ReplyKeyboardMarkup:
    """Основное меню с категориями."""
    return _mk_kb(
        rows=[
            [BTN_ORDERS, BTN_CONNECTIONS],
            [BTN_ANALYTICS, BTN_TIPS],
            [BTN_HELP],
        ],
        placeholder="Выберите раздел…",
    )


# ----------------------------
# Раздел: Заказы → период
# ----------------------------
def orders_menu() -> ReplyKeyboardMarkup:
    """Подменю раздела «Заказы»: выбор периода."""
    return _mk_kb(
        rows=[
            [BTN_TODAY, BTN_YESTERDAY],
            [BTN_7_DAYS, BTN_30_DAYS],
            [BTN_PERIOD],
            [BTN_BACK_TO_MENU],
        ],
        placeholder="Выберите период заказов…",
    )


# ----------------------------
# Раздел: Заказы → период → выбор маркетплейса
# ----------------------------
def marketplace_menu(for_what: str = "заказов") -> ReplyKeyboardMarkup:
    """
    Меню выбора маркетплейса (WB/Ozon/Оба).
    for_what — строка для плейсхолдера, например: 'заказов', 'аналитики', 'остатков'.
    """
    return _mk_kb(
        rows=[
            [BTN_MP_WB, BTN_MP_OZON],
            [BTN_MP_BOTH],
            [BTN_BACK, BTN_BACK_TO_MENU],
        ],
        placeholder=f"Выберите маркетплейс для {for_what}…",
    )


# ----------------------------
# Раздел: Заказы → детали/действия
# (закладываемся на будущие функции: список, обновить, фильтр)
# ----------------------------
def orders_actions_menu() -> ReplyKeyboardMarkup:
    """
    Меню действий в разделе заказов.
    Это меню рассчитано на будущие обработчики (например: показать список, обновить, фильтры).
    """
    return _mk_kb(
        rows=[
            ["Показать список", "Обновить"],
            ["Фильтр", "Детали заказа"],
            [BTN_BACK, BTN_BACK_TO_MENU],
        ],
        placeholder="Выберите действие по заказам…",
    )


# ----------------------------
# Раздел: Подключения
# ----------------------------
def connections_menu() -> ReplyKeyboardMarkup:
    """Подменю управления подключениями к маркетплейсам."""
    return _mk_kb(
        rows=[
            [BTN_CONNECT_WB, BTN_CONNECT_OZON],
            [BTN_DISCONNECT_WB, BTN_DISCONNECT_OZON],
            [BTN_SHOW_CONNECTIONS],
            [BTN_BACK_TO_MENU],
        ],
        placeholder="Настройка подключений…",
    )


# ----------------------------
# Раздел: Аналитика
# ----------------------------
def analytics_menu() -> ReplyKeyboardMarkup:
    """Подменю раздела «Аналитика» (базовое)."""
    return _mk_kb(
        rows=[
            [BTN_ANALYTICS_7],
            [BTN_REVENUE, BTN_SALES],
            [BTN_STOCKS, BTN_COMMISSION],
            [BTN_BACK_TO_MENU],
        ],
        placeholder="Выберите тип аналитики…",
    )


def analytics_period_menu() -> ReplyKeyboardMarkup:
    """Подменю выбора периода для аналитики."""
    return _mk_kb(
        rows=[
            [BTN_7_DAYS, BTN_30_DAYS],
            [BTN_PERIOD],
            [BTN_BACK, BTN_BACK_TO_MENU],
        ],
        placeholder="Выберите период аналитики…",
    )


# ----------------------------
# Раздел: Подсказки/лайфхаки
# ----------------------------
def tips_menu() -> ReplyKeyboardMarkup:
    """Подменю для раздела «Подсказки»."""
    return _mk_kb(
        rows=[
            [BTN_GET_TIP],
            [BTN_TIP_FOR_TEXT],
            [BTN_TIPS_RULES],
            [BTN_BACK_TO_MENU],
        ],
        placeholder="Выберите тип подсказки…",
    )


def tips_text_input_menu() -> ReplyKeyboardMarkup:
    """
    Меню при ожидании текста от пользователя для генерации лайфхака.
    Позволяет отменить ввод или вернуться.
    """
    return _mk_kb(
        rows=[
            [BTN_CANCEL],
            [BTN_BACK, BTN_BACK_TO_MENU],
        ],
        placeholder="Отправьте текст — я подготовлю лайфхак. Или нажмите «Отмена».",
    )


# ----------------------------
# Универсальные клавиатуры
# ----------------------------
def cancel_menu(placeholder: str = "Вы можете отменить действие…") -> ReplyKeyboardMarkup:
    """
    Универсальная клавиатура «Отмена» — полезно для ввода токена/периода/любых форм ввода.
    """
    return _mk_kb(
        rows=[
            [BTN_CANCEL],
            [BTN_BACK_TO_MENU],
        ],
        placeholder=placeholder,
    )


def back_to_menu_only(placeholder: str = "Выберите действие…") -> ReplyKeyboardMarkup:
    """
    Минимальная клавиатура для случаев, когда нужно дать только возврат в меню.
    """
    return _mk_kb(
        rows=[
            [BTN_BACK_TO_MENU],
        ],
        placeholder=placeholder,
    )


"""
Какой файл прислать следующим (по логике внедрения меню):

Пришли, пожалуйста, файл(ы) обработчиков, где сейчас используется это меню:
- app/bot/handlers/*.py (или конкретно: handlers/menu.py, handlers/start.py, handlers/orders.py — как у тебя называется)

Причина: клавиатуры готовы, но нужно:
1) Связать шаги сценария "Заказы → период → выбор МП → детали" через FSM (states).
2) Добавить обработку "Лайфхаки по тексту" (ожидаем текст, кнопка Отмена).
3) Реализовать безопасный ввод токена с попыткой удалить сообщение пользователя и без вывода токена в ответах.

Если хочешь начать точечно — пришли файл, где обрабатывается текст "Заказы" и показывается orders_menu().
"""
