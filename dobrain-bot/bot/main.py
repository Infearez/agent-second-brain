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
    from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

    storage = VaultStorage(settings.vault_path)
    storage.ensure_dirs()
    catalog = TeaCatalog.from_markdown(settings.vault_path / "🍵 Чай/Каталог чая.md")
    tea = TeaService(storage, catalog)
    brain = BrainService(storage)
    payments = PaymentsService(storage)

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()

    def allowed(message: Message) -> bool:
        return not settings.allowed_user_ids or message.from_user.id in settings.allowed_user_ids

    def allowed_callback(callback: CallbackQuery) -> bool:
        return not settings.allowed_user_ids or callback.from_user.id in settings.allowed_user_ids

    def tea_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="Продажи сегодня", callback_data="tea:report:today"),
                    InlineKeyboardButton(text="Продажи месяц", callback_data="tea:report:month"),
                ],
                [
                    InlineKeyboardButton(text="Каталог", callback_data="tea:catalog"),
                    InlineKeyboardButton(text="Остатки", callback_data="tea:stock"),
                ],
            ]
        )

    async def payment_reminder_loop() -> None:
        if not settings.allowed_user_ids:
            return
        while True:
            now = datetime.now(settings.timezone)
            for payment in payments.due_reminders(now):
                if payments.already_notified(payment, now.date()):
                    continue
                text = (
                    f"Напоминание об оплате: {payment.service}\n"
                    f"Следующая оплата: {payment.next_payment or 'неизвестно'}\n"
                    f"Статус: {payment.status}\n"
                    f"[[Подписки и оплаты]]"
                )
                for user_id in settings.allowed_user_ids:
                    await bot.send_message(user_id, text)
                payments.mark_notified(payment, now)
            await asyncio.sleep(60 * 60)

    @dp.message(Command("start"))
    async def start(message: Message) -> None:
        if not allowed(message):
            return
        await message.answer("Dual Brain готов. Команды: /status /tea /payments /today /tasks")

    @dp.message(Command("status"))
    async def status(message: Message) -> None:
        if not allowed(message):
            return
        due = payments.due_reminders(datetime.now(settings.timezone))
        await message.answer(
            f"Vault: {settings.vault_path}\n"
            f"Чаёв в каталоге: {len(catalog.items)}\n"
            f"Напоминаний сегодня: {len(due)}"
        )

    @dp.message(Command("payments"))
    async def show_payments(message: Message) -> None:
        if not allowed(message):
            return
        await message.answer(payments.format_payments(datetime.now(settings.timezone)))

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
            "\n\nМожно начать с кнопок ниже."
            ,
            reply_markup=tea_keyboard(),
        )

    @dp.callback_query(F.data.startswith("tea:"))
    async def tea_callback(callback: CallbackQuery) -> None:
        if not allowed_callback(callback):
            return
        now = datetime.now(settings.timezone)
        data = callback.data or ""
        if data == "tea:report:today":
            await callback.message.answer(tea.report(now, "today"))
        elif data == "tea:report:month":
            await callback.message.answer(tea.report(now, "month"))
        elif data == "tea:catalog":
            await callback.message.answer(tea.catalog_summary())
        elif data == "tea:stock":
            await callback.message.answer(tea.stock_summary()[:3500])
        await callback.answer()

    @dp.message(F.voice)
    async def voice_handler(message: Message) -> None:
        if not allowed(message):
            return
        now = datetime.now(settings.timezone)
        brain.add_inbox("Голосовое сообщение без расшифровки. Нужно добавить транскрибацию вторым этапом. #разобрать", now)
        await message.answer("Голос сохранил во входящие #разобрать. Расшифровку подключим следующим этапом.")

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
        if low.startswith("каталог") or low.startswith("прайс"):
            await message.answer(tea.catalog_summary())
            return
        if low.startswith("остатки"):
            await message.answer(tea.stock_summary()[:3500])
            return
        await message.answer(brain.route_text(text, now))

    asyncio.create_task(payment_reminder_loop())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
