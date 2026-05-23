from __future__ import annotations

import asyncio
from datetime import datetime

from bot.config import load_settings
from bot.keyboards import main_keyboard
from brain.chat import BrainChatService
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
    chat = BrainChatService(storage, settings.openai_api_key, settings.openai_model)
    payments = PaymentsService(storage)

    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    pending_custom_weight: dict[int, str] = {}

    def allowed(message: Message) -> bool:
        return not settings.allowed_user_ids or message.from_user.id in settings.allowed_user_ids

    def allowed_callback(callback: CallbackQuery) -> bool:
        return not settings.allowed_user_ids or callback.from_user.id in settings.allowed_user_ids

    def tea_keyboard() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="➕ Продажа", callback_data="tea:sale"),
                    InlineKeyboardButton(text="📦 Остатки", callback_data="tea:stock"),
                ],
                [
                    InlineKeyboardButton(text="Сегодня", callback_data="tea:report:today"),
                    InlineKeyboardButton(text="Неделя", callback_data="tea:report:week"),
                ],
                [
                    InlineKeyboardButton(text="Месяц", callback_data="tea:report:month"),
                    InlineKeyboardButton(text="Всё время", callback_data="tea:report:all"),
                ],
                [
                    InlineKeyboardButton(text="📋 Каталог", callback_data="tea:catalog"),
                ],
            ]
        )

    def tea_type_keyboard() -> InlineKeyboardMarkup:
        types = []
        for item in catalog.items:
            if item.tea_type not in types:
                types.append(item.tea_type)
        rows = [
            [InlineKeyboardButton(text=tea_type, callback_data=f"tea:type:{tea_type}")]
            for idx, tea_type in enumerate(types)
        ]
        rows.append([InlineKeyboardButton(text="Назад", callback_data="tea:menu")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def tea_items_keyboard(tea_type: str) -> InlineKeyboardMarkup:
        rows = []
        for idx, item in enumerate(catalog.items):
            if item.tea_type == tea_type:
                rows.append([InlineKeyboardButton(text=item.name[:60], callback_data=f"tea:item:{idx}")])
        rows.append([InlineKeyboardButton(text="Назад", callback_data="tea:sale")])
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def grams_keyboard(item_idx: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="8 г", callback_data=f"tea:grams:{item_idx}:8"),
                    InlineKeyboardButton(text="10 г", callback_data=f"tea:grams:{item_idx}:10"),
                    InlineKeyboardButton(text="25 г", callback_data=f"tea:grams:{item_idx}:25"),
                ],
                [
                    InlineKeyboardButton(text="50 г", callback_data=f"tea:grams:{item_idx}:50"),
                    InlineKeyboardButton(text="100 г", callback_data=f"tea:grams:{item_idx}:100"),
                    InlineKeyboardButton(text="Свой вес", callback_data=f"tea:custom:{item_idx}"),
                ],
                [InlineKeyboardButton(text="Назад", callback_data=f"tea:type:{catalog.items[item_idx].tea_type}")],
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
        await message.answer("Dual Brain готов.", reply_markup=main_keyboard())

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
        if data == "tea:menu":
            await callback.message.answer("🍵 Чай", reply_markup=tea_keyboard())
        elif data == "tea:sale":
            await callback.message.answer("Выбери тип чая:", reply_markup=tea_type_keyboard())
        elif data.startswith("tea:type:"):
            tea_type = data.removeprefix("tea:type:")
            await callback.message.answer(f"{tea_type}: выбери сорт", reply_markup=tea_items_keyboard(tea_type))
        elif data.startswith("tea:item:"):
            item_idx = int(data.removeprefix("tea:item:"))
            item = catalog.items[item_idx]
            await callback.message.answer(
                f"{item.name}\n{item.price_per_gram} руб/г\nВыбери граммовку:",
                reply_markup=grams_keyboard(item_idx),
            )
        elif data.startswith("tea:grams:"):
            _, _, item_idx_raw, grams_raw = data.split(":")
            sale = tea.add_sale(catalog.items[int(item_idx_raw)].name, int(grams_raw), now, source="telegram_button")
            await callback.message.answer(f"✅ {sale.item.name}\n{sale.grams} г = {sale.total} руб")
        elif data.startswith("tea:custom:"):
            item_idx = int(data.removeprefix("tea:custom:"))
            pending_custom_weight[callback.from_user.id] = catalog.items[item_idx].name
            await callback.message.answer("Напиши вес числом, например: 37")
        if data == "tea:report:today":
            await callback.message.answer(tea.report(now, "today"))
        elif data == "tea:report:week":
            await callback.message.answer(tea.report(now, "week"))
        elif data == "tea:report:month":
            await callback.message.answer(tea.report(now, "month"))
        elif data == "tea:report:all":
            await callback.message.answer(tea.report(now, "all"))
        elif data == "tea:catalog":
            await callback.message.answer(tea.catalog_summary())
        elif data == "tea:stock":
            await callback.message.answer(tea.stock_summary()[:3500])
        await callback.answer()

    @dp.message(F.voice)
    async def voice_handler(message: Message) -> None:
        if not allowed(message):
            return
        await message.answer("Голос пока не понимаю и не сохраняю. Напиши текстом или скажи: «сохрани ...».")

    @dp.message(F.text)
    async def text_handler(message: Message) -> None:
        if not allowed(message):
            return
        text = message.text or ""
        now = datetime.now(settings.timezone)
        low = text.lower()
        if text == "🍵 Чай":
            await message.answer("🍵 Чай", reply_markup=tea_keyboard())
            return
        if text == "📊 Статус":
            await status(message)
            return
        if text == "💰 Оплаты":
            await show_payments(message)
            return
        if text == "✅ Задача":
            await message.answer("Напиши: задача <текст>")
            return
        if text == "💡 Идея":
            await message.answer("Напиши: идея <текст>")
            return
        if text == "📅 Дневник":
            await message.answer("Напиши: дневник <текст>")
            return
        if message.from_user and message.from_user.id in pending_custom_weight:
            grams = parse_grams(text) or parse_plain_int(text)
            item_name = pending_custom_weight.pop(message.from_user.id)
            if grams is None:
                await message.answer("Не понял вес. Напиши числом, например: 37")
                pending_custom_weight[message.from_user.id] = item_name
                return
            sale = tea.add_sale(item_name, grams, now, source="telegram_button_custom")
            await message.answer(f"✅ {sale.item.name}\n{sale.grams} г = {sale.total} руб")
            return
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
        if low.startswith(("сохрани ", "сохранить ", "запомни ", "запиши ", "задача", "добавь задачу", "таск", "todo", "идея", "дневник", "запись")):
            await message.answer(brain.route_text(text, now))
            return
        answer = await chat.answer(text, now, extra_context=extra_context(text, now, tea, payments))
        await message.answer(answer.answer[:3500])

    asyncio.create_task(payment_reminder_loop())
    await dp.start_polling(bot)


def extra_context(text: str, now: datetime, tea: TeaService, payments: PaymentsService) -> str:
    low = text.lower()
    chunks: list[str] = []
    if any(word in low for word in ["чай", "продаж", "остат", "прайс", "каталог"]):
        chunks.append("## Чайные продажи\n" + tea.report(now, "all"))
        chunks.append("## Остатки чая\n" + tea.stock_summary())
    if any(word in low for word in ["оплат", "подпис", "vps", "сервер", "vpn", "claude"]):
        chunks.append("## Подписки и оплаты\n" + payments.format_payments(now))
    return "\n\n".join(chunks)


def parse_plain_int(text: str) -> int | None:
    stripped = text.strip()
    return int(stripped) if stripped.isdigit() else None


if __name__ == "__main__":
    asyncio.run(main())
