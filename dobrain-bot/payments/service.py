from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from storage.vault import VaultStorage


@dataclass(frozen=True)
class Payment:
    service: str
    next_payment: date | None
    reminder: date | None
    status: str
    comment: str


def _parse_date(value: str) -> date | None:
    value = value.strip()
    if not re.match(r"\d{4}-\d{2}-\d{2}$", value):
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


class PaymentsService:
    def __init__(self, storage: VaultStorage):
        self.storage = storage

    def list_payments(self) -> list[Payment]:
        text = self.storage.paths.payments.read_text(encoding="utf-8")
        payments: list[Payment] = []
        for line in text.splitlines():
            if not line.startswith("| ") or line.startswith("| ---") or "Сервис" in line:
                continue
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            if len(cells) < 8:
                continue
            payments.append(
                Payment(
                    service=cells[0],
                    next_payment=_parse_date(cells[4]),
                    reminder=_parse_date(cells[5]),
                    status=cells[6],
                    comment=cells[7],
                )
            )
        return payments

    def due_reminders(self, today: date | datetime) -> list[Payment]:
        if isinstance(today, datetime):
            today = today.date()
        return [payment for payment in self.list_payments() if payment.reminder == today]
