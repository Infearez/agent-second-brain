from __future__ import annotations

import re
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from storage.vault import VaultStorage
from tea.catalog import TeaCatalog, TeaItem


@dataclass(frozen=True)
class TeaSale:
    id: str
    timestamp: datetime
    item: TeaItem
    grams: int
    total: int
    source: str
    status: str = "active"


def parse_grams(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(?:г|гр|грамм)", text.lower())
    return int(match.group(1)) if match else None


class TeaService:
    def __init__(self, storage: VaultStorage, catalog: TeaCatalog):
        self.storage = storage
        self.catalog = catalog

    def add_sale(self, query: str, grams: int, now: datetime, source: str = "telegram") -> TeaSale:
        matches = self.catalog.find(query)
        if len(matches) != 1:
            hint = ""
            if matches:
                names = ", ".join(item.name for item in matches[:5])
                hint = f" Варианты: {names}"
            raise ValueError(f"Нужно уточнить чай #разобрать.{hint}")
        item = matches[0]
        sale = TeaSale(
            id=str(uuid4()),
            timestamp=now,
            item=item,
            grams=grams,
            total=grams * item.price_per_gram,
            source=source,
        )
        self._write_sale(sale)
        return sale

    def cancel_last_sale(self, now: datetime, source: str = "telegram") -> dict:
        sale = self._last_active_sale()
        if sale is None:
            raise ValueError("Активных продаж для отмены не найдено")
        payload = {
            "type": "tea_cancel",
            "id": str(uuid4()),
            "target_id": sale["id"],
            "timestamp": now,
            "source": source,
            "status": "active",
        }
        date = f"{now:%Y-%m-%d %H:%M}"
        md = (
            f"## {date} · отмена продажи\n\n"
            f"- Отменена операция: `{sale['id']}`\n"
            f"- Чай: [[{sale['item']['name']}]]\n"
            f"- Граммы: {sale['grams']}\n"
            f"- Сумма: {sale['total']} руб\n"
            f"- Связи: [[Продажи чая]], [[Чайный бот]], [[Tea Bag]]\n"
        )
        self.storage.append_markdown("🍵 Чай/Продажи/Журнал продаж.md", md)
        self.storage.append_jsonl("🍵 Чай/Продажи/operations.jsonl", payload)
        return sale

    def report(self, now: datetime, scope: str = "today") -> str:
        sales = self._active_sales()
        if scope == "today":
            sales = [sale for sale in sales if str(sale.get("timestamp", "")).startswith(f"{now:%Y-%m-%d}")]
            title = "Продажи за сегодня"
        elif scope == "month":
            sales = [sale for sale in sales if str(sale.get("timestamp", "")).startswith(f"{now:%Y-%m}")]
            title = "Продажи за месяц"
        else:
            title = "Продажи за всё время"
        if not sales:
            return f"{title}: нет записей"
        total = sum(int(sale.get("total", 0)) for sale in sales)
        grams = sum(int(sale.get("grams", 0)) for sale in sales)
        rows = [
            f"{sale['item']['name']}: {sale['grams']} г, {sale['total']} руб"
            for sale in sales[-10:]
        ]
        return f"{title}\nВсего: {grams} г, {total} руб\n" + "\n".join(rows)

    def catalog_summary(self, limit: int = 20) -> str:
        if not self.catalog.items:
            return "Каталог пуст или прайс не прочитан"
        rows = [
            f"- {item.name}: {item.price_per_gram} руб/г, {item.price_per_10g} руб/10г"
            for item in self.catalog.items[:limit]
        ]
        tail = ""
        if len(self.catalog.items) > limit:
            tail = f"\n...ещё {len(self.catalog.items) - limit}"
        return "Каталог чая:\n" + "\n".join(rows) + tail

    def stock_summary(self) -> str:
        path = self.storage.paths.root / "🍵 Чай/Остатки/Остатки_из_Excel.md"
        if not path.exists():
            return "Остатки не найдены #разобрать"
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("| ") or line.startswith("#") or line.startswith("-"):
                lines.append(line)
            if len(lines) >= 25:
                break
        return "\n".join(lines).strip() or "Остатки требуют ручной проверки #разобрать"

    def _write_sale(self, sale: TeaSale) -> None:
        date = f"{sale.timestamp:%Y-%m-%d %H:%M}"
        md = (
            f"## {date} · продажа\n\n"
            f"- Чай: [[{sale.item.name}]]\n"
            f"- Граммы: {sale.grams}\n"
            f"- Цена: {sale.item.price_per_gram} руб/г\n"
            f"- Сумма: {sale.total} руб\n"
            f"- Связи: [[Продажи чая]], [[Чайный бот]], [[Tea Bag]]\n"
        )
        self.storage.append_markdown("🍵 Чай/Продажи/Журнал продаж.md", md)
        payload = asdict(sale)
        payload["type"] = "tea_sale"
        payload["item"] = asdict(sale.item)
        self.storage.append_jsonl("🍵 Чай/Продажи/operations.jsonl", payload)

    def _operations_path(self) -> Path:
        return self.storage.paths.root / "🍵 Чай/Продажи/operations.jsonl"

    def _operations(self) -> list[dict]:
        path = self._operations_path()
        if not path.exists():
            return []
        operations: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                operations.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return operations

    def _active_sales(self) -> list[dict]:
        operations = self._operations()
        canceled = {
            operation.get("target_id")
            for operation in operations
            if operation.get("type") == "tea_cancel"
        }
        return [
            operation
            for operation in operations
            if operation.get("type") == "tea_sale" and operation.get("id") not in canceled
        ]

    def _last_active_sale(self) -> dict | None:
        sales = self._active_sales()
        return sales[-1] if sales else None
