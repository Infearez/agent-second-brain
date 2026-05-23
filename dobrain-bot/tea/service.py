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
        by_item: dict[str, dict[str, int]] = {}
        for sale in sales:
            name = sale["item"]["name"]
            row = by_item.setdefault(name, {"grams": 0, "total": 0})
            row["grams"] += int(sale.get("grams", 0))
            row["total"] += int(sale.get("total", 0))
        summary_rows = [
            f"- {name}: {row['grams']} г, {row['total']} руб"
            for name, row in sorted(by_item.items(), key=lambda item: item[1]["total"], reverse=True)
        ]
        recent_rows = [
            f"{sale['item']['name']}: {sale['grams']} г, {sale['total']} руб"
            for sale in sales[-8:]
        ]
        return (
            f"{title}\n"
            f"Всего: {grams} г, {total} руб\n\n"
            "По сортам:\n"
            + "\n".join(summary_rows)
            + "\n\nПоследние операции:\n"
            + "\n".join(recent_rows)
        )

    def catalog_summary(self, limit: int = 20) -> str:
        if not self.catalog.items:
            return "Каталог пуст или прайс не прочитан"
        grouped: dict[str, list[TeaItem]] = {}
        for item in self.catalog.items[:limit]:
            grouped.setdefault(item.tea_type, []).append(item)
        rows = []
        for tea_type, items in grouped.items():
            rows.append(f"\n{tea_type}:")
            rows.extend(
                f"- {item.name}\n  {item.price_per_gram} руб/г · {item.price_per_10g} руб/10г"
                for item in items
            )
        tail = ""
        if len(self.catalog.items) > limit:
            tail = f"\n...ещё {len(self.catalog.items) - limit}"
        return "Каталог чая\n" + "\n".join(rows).strip() + tail

    def stock_summary(self) -> str:
        path = self.storage.paths.root / "🍵 Чай/Остатки чая.md"
        if not path.exists():
            return "Остатки не найдены #разобрать"
        rows = self._stock_rows(path)
        if not rows:
            return "Остатки требуют ручной проверки #разобрать"
        sold_by_name = self._sold_by_name()
        lines = ["Остатки чая:"]
        total_value = 0
        for row in rows:
            sold = sold_by_name.get(row["name"], 0)
            remaining = row["purchased"] - sold
            value = remaining * row["price"]
            total_value += value
            lines.append(
                f"- {row['name']}: было {row['purchased']} г, продано {sold} г, "
                f"остаток {remaining} г, примерно {value} руб"
            )
        lines.append(f"Итого по остаткам: примерно {total_value} руб")
        return "\n".join(lines)

    def _stock_rows(self, path: Path) -> list[dict]:
        rows: list[dict] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| ") or line.startswith("| ---") or line.lower().startswith("| чай "):
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < 4:
                continue
            try:
                purchased = int(float(cells[2]))
                price = int(float(cells[3]))
            except ValueError:
                continue
            rows.append({"name": cells[0], "purchased": purchased, "price": price})
        return rows

    def _sold_by_name(self) -> dict[str, int]:
        sold: dict[str, int] = {}
        for sale in self._active_sales():
            name = sale.get("item", {}).get("name", "")
            grams = int(sale.get("grams", 0))
            sold[name] = sold.get(name, 0) + grams
        return sold

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
