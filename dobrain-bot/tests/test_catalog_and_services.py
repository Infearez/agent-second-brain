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


class CatalogAndServicesTest(unittest.TestCase):
    def test_catalog_reads_excel_summary_formulas(self) -> None:
        catalog = TeaCatalog.from_markdown(VAULT / "🍵 Чай/Прайсы/Прайс_из_Excel.md")

        self.assertGreaterEqual(len(catalog.items), 10)
        white = catalog.find("внеси продажу белого чая 8 грамм")

        self.assertEqual(white[0].name, "Байхао Инджень Юньнань")
        self.assertEqual(white[0].price_per_gram, 9)
        self.assertEqual(white[0].price_per_10g, 90)

    def test_parse_grams(self) -> None:
        self.assertEqual(parse_grams("внеси продажу белого чая 8 грамм"), 8)
        self.assertEqual(parse_grams("продажа тегуаньинь 10г"), 10)

    def test_add_sale_writes_markdown_and_jsonl(self) -> None:
        with TemporaryDirectory() as tmp:
            vault = Path(tmp)
            price_dir = vault / "🍵 Чай/Прайсы"
            price_dir.mkdir(parents=True)
            (price_dir / "Прайс_из_Excel.md").write_text(
                (VAULT / "🍵 Чай/Прайсы/Прайс_из_Excel.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            storage = VaultStorage(vault)
            storage.ensure_dirs()
            catalog = TeaCatalog.from_markdown(price_dir / "Прайс_из_Excel.md")
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

            canceled = tea.cancel_last_sale(datetime.fromisoformat("2026-05-23T12:10:00+04:00"))
            self.assertEqual(canceled["id"], sale.id)
            self.assertIn("нет записей", tea.report(datetime.fromisoformat("2026-05-23T12:20:00+04:00"), "today"))

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


if __name__ == "__main__":
    unittest.main()
