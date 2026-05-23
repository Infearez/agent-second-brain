from __future__ import annotations

import json
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
VAULT = Path(os.environ.get("VAULT_PATH", ROOT.parent))
sys.path.insert(0, str(ROOT))

from payments.service import PaymentsService
from storage.vault import VaultStorage
from tea.catalog import TeaCatalog
from tea.service import TeaService, parse_grams
from brain.chat import BrainChatService
from brain.service import BrainService
from bot.keyboards import MAIN_BUTTON_ROWS
from bot.main import parse_plain_int


class CatalogAndServicesTest(unittest.TestCase):
    def test_catalog_reads_excel_summary_formulas(self) -> None:
        catalog = TeaCatalog.from_markdown(VAULT / "🍵 Чай/Каталог чая.md")

        self.assertGreaterEqual(len(catalog.items), 10)
        white = catalog.find("внеси продажу белого чая 8 грамм")

        self.assertEqual(white[0].name, "Байхао Инджень Юньнань")
        self.assertEqual(white[0].price_per_gram, 9)
        self.assertEqual(white[0].price_per_10g, 90)

    def test_parse_grams(self) -> None:
        self.assertEqual(parse_grams("внеси продажу белого чая 8 грамм"), 8)
        self.assertEqual(parse_grams("продажа тегуаньинь 10г"), 10)
        self.assertEqual(parse_plain_int("37"), 37)
        self.assertIsNone(parse_plain_int("37 г"))

    def test_main_keyboard_has_core_buttons(self) -> None:
        labels = [button for row in MAIN_BUTTON_ROWS for button in row]
        self.assertIn("🍵 Чай", labels)
        self.assertIn("✅ Задача", labels)
        self.assertIn("💡 Идея", labels)
        self.assertIn("📅 Дневник", labels)
        self.assertIn("📊 Статус", labels)

    def test_add_sale_writes_markdown_and_jsonl(self) -> None:
        with TemporaryDirectory() as tmp:
            vault = Path(tmp)
            tea_dir = vault / "🍵 Чай"
            tea_dir.mkdir(parents=True)
            (tea_dir / "Каталог чая.md").write_text(
                (VAULT / "🍵 Чай/Каталог чая.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (tea_dir / "Остатки чая.md").write_text(
                (VAULT / "🍵 Чай/Остатки чая.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            storage = VaultStorage(vault)
            storage.ensure_dirs()
            catalog = TeaCatalog.from_markdown(tea_dir / "Каталог чая.md")
            tea = TeaService(storage, catalog)
            sale = tea.add_sale(
                "внеси продажу белого чая 8 грамм",
                8,
                datetime.fromisoformat("2026-05-23T10:00:00+04:00"),
            )

            self.assertEqual(sale.item.name, "Байхао Инджень Юньнань")
            self.assertEqual(sale.total, 72)

            journal = (vault / "🍵 Чай/Продажи/Журнал продаж.md").read_text(encoding="utf-8")
            self.assertIn("Байхао Инджень Юньнань", journal)
            self.assertIn("72 руб", journal)

            line = (vault / "🍵 Чай/Продажи/operations.jsonl").read_text(encoding="utf-8").splitlines()[0]
            payload = json.loads(line)
            self.assertEqual(payload["type"], "tea_sale")
            self.assertEqual(payload["item"]["name"], "Байхао Инджень Юньнань")

            report = tea.report(datetime.fromisoformat("2026-05-23T12:00:00+04:00"), "today")
            self.assertIn("72 руб", report)
            self.assertIn("Продажи за 7 дней", tea.report(datetime.fromisoformat("2026-05-23T12:00:00+04:00"), "week"))
            self.assertIn("Байхао Инджень Юньнань", tea.catalog_summary())
            self.assertIn("Остатки чая", tea.stock_summary())
            self.assertIn("остаток 992 г", tea.stock_summary())

            canceled = tea.cancel_last_sale(datetime.fromisoformat("2026-05-23T12:10:00+04:00"))
            self.assertEqual(canceled["id"], sale.id)
            self.assertIn("нет записей", tea.report(datetime.fromisoformat("2026-05-23T12:20:00+04:00"), "today"))

    def test_brain_routes_text_to_working_notes(self) -> None:
        with TemporaryDirectory() as tmp:
            vault = Path(tmp)
            storage = VaultStorage(vault)
            storage.ensure_dirs()
            brain = BrainService(storage)
            now = datetime.fromisoformat("2026-05-23T13:00:00+04:00")

            self.assertEqual(brain.route_text("задача проверить Syncthing", now), "Задача добавлена")
            self.assertEqual(brain.route_text("идея: сделать быстрые кнопки", now), "Идея сохранена")
            self.assertEqual(brain.route_text("дневник сегодня бот ожил", now), "Запись добавлена в дневник")
            self.assertEqual(brain.route_text("непонятная мысль", now), "Команда не распознана")
            self.assertEqual(brain.route_text("сохрани как задачу купить упаковку", now), "Сохранил как задачу")
            self.assertEqual(brain.route_text("сохрани мысль про чай", now), "Сохранил во входящие")

            self.assertIn("проверить Syncthing", (vault / "✅ Задачи/Собранные задачи.md").read_text(encoding="utf-8"))
            self.assertIn("быстрые кнопки", (vault / "💡 Идеи/Собранные идеи.md").read_text(encoding="utf-8"))
            self.assertIn("бот ожил", (vault / "📅 Дневник/2026-05-23.md").read_text(encoding="utf-8"))
            self.assertIn("мысль про чай", (vault / "📥 Входящие/2026-05-23.md").read_text(encoding="utf-8"))

    def test_chat_without_key_uses_local_fallback_without_saving_inbox(self) -> None:
        with TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "🧠 Второй мозг").mkdir(parents=True)
            (vault / "🧠 Второй мозг/DoBrain.md").write_text("DoBrain — база знаний.", encoding="utf-8")
            storage = VaultStorage(vault)
            storage.ensure_dirs()
            chat = BrainChatService(storage, "", "gpt-5-mini")
            now = datetime.fromisoformat("2026-05-23T13:00:00+04:00")

            response = __import__("asyncio").run(chat.answer("Что такое DoBrain?", now))

            self.assertIn("Нашёл по базе", response.answer)
            self.assertIn("DoBrain", response.answer)
            self.assertFalse((vault / "📥 Входящие/2026-05-23.md").exists())
            self.assertTrue((vault / "📦 Архив/Служебное/chat-log.jsonl").exists())

    def test_payments_find_june_reminders(self) -> None:
        payments = PaymentsService(VaultStorage(VAULT))
        rows = payments.list_payments()
        vps_due = payments.due_reminders(datetime.fromisoformat("2026-06-03T09:00:00+04:00"))
        claude_due = payments.due_reminders(datetime.fromisoformat("2026-06-04T09:00:00+04:00"))

        self.assertIn("VPS", [payment.service for payment in rows])
        self.assertIn("Claude Code", [payment.service for payment in rows])
        self.assertIn("Strelka VPN", [payment.service for payment in rows])
        self.assertIn("VPS", [payment.service for payment in vps_due])
        self.assertIn("Claude Code", [payment.service for payment in claude_due])
        self.assertIn("Ближайшие оплаты", payments.format_payments(datetime.fromisoformat("2026-06-04T09:00:00+04:00")))

    def test_payment_notification_marker(self) -> None:
        with TemporaryDirectory() as tmp:
            vault = Path(tmp)
            finance = vault / "💰 Финансы"
            finance.mkdir(parents=True)
            (finance / "Подписки и оплаты.md").write_text(
                (VAULT / "💰 Финансы/Подписки и оплаты.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            payments = PaymentsService(VaultStorage(vault))
            payment = payments.due_reminders(datetime.fromisoformat("2026-06-03T09:00:00+04:00"))[0]
            now = datetime.fromisoformat("2026-06-03T09:00:00+04:00")

            self.assertFalse(payments.already_notified(payment, now.date()))
            payments.mark_notified(payment, now)
            self.assertTrue(payments.already_notified(payment, now.date()))


if __name__ == "__main__":
    unittest.main()
