from __future__ import annotations

import asyncio
from datetime import datetime

from bot.config import load_settings
from brain.service import BrainService
from payments.service import PaymentsService
from storage.vault import VaultStorage
from tea.catalog import TeaCatalog
from tea.service import TeaService, parse_grams


def command_payload(text: str, command: str) -> str:
    return text[len(command):].strip()


async def main() -> None:
    settings = load_settings()
    if not settings.telegram_bot_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN is required")

    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import Command
    from aiogram.types import Message

    storage = VaultStorage(settings.vault_path)
    storage.ensure_dirs()
    catalog = TeaCatalog.from_markdown(settings.vault_path / "🍵 Чай/Прайсы/Прайс_из_Excel.md")
    tea = TeaService(storage, catalog)
    brain = BrainService(storage)
    payments = PaymentsService(storage)

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()

    def allowed(message: Message) -> bool:
        return not settings.allowed_user_ids or message.from_user.id in settings.allowed_user_ids

    @dp.message(Command("start"))
    async def start(message: Message) -> None:
        if not allowed(message):
            return
        await message.answer("DoBrain готов. Команды: /status /tea /payments /today /tasks")

    @dp.message(Command("status"))
    async def status(message: Message) -> None:
        if not allowed(message):
            return
        await message.answer(f"Vault: {settings.vault_path}\nЧаёв в каталоге: {len(catalog.items)}")

    @dp.message(Command("payments"))
    async def show_payments(message: Message) -> None:
        if not allowed(message):
            return
        rows = payments.list_payments()
        text = "\n".join(
            f"{p.service}: след. {p.next_payment or 'неизвестно'}, напомнить {p.reminder or 'неизвестно'}"
            for p in rows
        )
        await message.answer(text or "Оплаты не найдены")

    @dp.message(Command("today"))
    async def today(message: Message) -> None:
        if not allowed(message):
            return
        now = datetime.now(settings.timezone)
        path = settings.vault_path / f"📅 Дневник/{now:%Y-%m-%d}.md"
        await message.answer(path.read_text(encoding="utf-8")[:3500] if path.exists() else "Сегодня пусто")

    @dp.message(Command("tasks"))
    async def tasks(message: Message) -> None:
        if not allowed(message):
            return
        path = settings.vault_path / "✅ Задачи/Собранные задачи.md"
        await message.answer(path.read_text(encoding="utf-8")[:3500] if path.exists() else "Задачи не найдены")

    @dp.message(Command("tea"))
    async def tea_menu(message: Message) -> None:
        if not allowed(message):
            return
        await message.answer(
            "Чайный модуль:\n"
            "- продажа <чай> <граммы>г\n"
            "- отмена продажи\n"
            "- исправь продажу <чай> <граммы>г\n"
            "- продажи сегодня / продажи месяц / продажи все"
        )

    @dp.message(F.text)
    async def text_handler(message: Message) -> None:
        if not allowed(message):
            return
        text = message.text or ""
        now = datetime.now(settings.timezone)
        low = text.lower()
        if low.startswith("продажа ") or "внеси продажу" in low or "запиши продажу" in low:
            grams = parse_grams(text)
            if grams is None:
                brain.add_inbox(text, now)
                await message.answer("Не нашёл граммы. Сохранил во входящие #разобрать")
                return
            try:
                sale = tea.add_sale(text, grams, now)
            except ValueError as exc:
                brain.add_inbox(text, now)
                await message.answer(str(exc))
                return
            await message.answer(f"✅ {sale.item.name}\n{sale.grams}г × {sale.item.price_per_gram} = {sale.total} руб")
            return
        if low.startswith("отмена продажи") or low.startswith("отмени продажу"):
            try:
                sale = tea.cancel_last_sale(now)
            except ValueError as exc:
                await message.answer(str(exc))
                return
            await message.answer(f"Отменил: {sale['item']['name']}, {sale['grams']}г, {sale['total']} руб")
            return
        if low.startswith("исправь продажу") or low.startswith("исправить продажу"):
            grams = parse_grams(text)
            if grams is None:
                brain.add_inbox(text + " #разобрать", now)
                await message.answer("Не нашёл граммы для исправления. Сохранил во входящие #разобрать")
                return
            try:
                tea.cancel_last_sale(now)
                sale = tea.add_sale(text, grams, now, source="telegram_correction")
            except ValueError as exc:
                brain.add_inbox(text + " #разобрать", now)
                await message.answer(str(exc))
                return
            await message.answer(f"Исправил последнюю продажу на: {sale.item.name}, {sale.grams}г, {sale.total} руб")
            return
        if low.startswith("продажи сегодня"):
            await message.answer(tea.report(now, "today"))
            return
        if low.startswith("продажи месяц"):
            await message.answer(tea.report(now, "month"))
            return
        if low.startswith("продажи все") or low.startswith("продажи всё"):
            await message.answer(tea.report(now, "all"))
            return
        if low.startswith("задача "):
            brain.add_task(command_payload(text, "задача "), now)
            await message.answer("Задача добавлена")
            return
        if low.startswith("идея "):
            brain.add_idea(command_payload(text, "идея "), now)
            await message.answer("Идея сохранена")
            return
        if low.startswith("дневник "):
            brain.add_diary(command_payload(text, "дневник "), now)
            await message.answer("Запись добавлена в дневник")
            return
        brain.add_inbox(text, now)
        await message.answer("Сохранил во входящие")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
