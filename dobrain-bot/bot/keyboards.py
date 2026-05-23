from __future__ import annotations

from tea.catalog import TeaCatalog


MAIN_BUTTON_ROWS = [
    ["🍵 Чай", "✅ Задача"],
    ["💡 Идея", "📅 Дневник"],
    ["📊 Статус", "💰 Оплаты"],
]


def tea_button_rows(catalog: TeaCatalog) -> list[list[str]]:
    names = [item.name for item in catalog.items]
    return [names[i : i + 2] for i in range(0, len(names), 2)]


def main_keyboard() -> ReplyKeyboardMarkup:
    from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=text) for text in row] for row in MAIN_BUTTON_ROWS],
        resize_keyboard=True,
        input_field_placeholder="Напиши вопрос или выбери раздел",
    )
