from __future__ import annotations

import re
import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import uuid4

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

    def format_payments(self, today: date | datetime | None = None) -> str:
        if isinstance(today, datetime):
            today = today.date()
        rows = self.list_payments()
        if not rows:
            return "Оплаты не найдены"

        def sort_key(payment: Payment) -> tuple[date, str]:
            return (payment.reminder or payment.next_payment or date.max, payment.service)

        lines = ["Ближайшие оплаты:"]
        for payment in sorted(rows, key=sort_key):
            marker = ""
            if today and payment.reminder == today:
                marker = " ← напомнить сегодня"
            lines.append(
                f"- {payment.service}: след. {payment.next_payment or 'неизвестно'}, "
                f"напомнить {payment.reminder or 'неизвестно'}, статус: {payment.status}{marker}"
            )
        return "\n".join(lines)

    def already_notified(self, payment: Payment, reminder_date: date) -> bool:
        path = self.storage.paths.root / "💰 Финансы/payment-reminders.jsonl"
        if not path.exists():
            return False
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("service") == payment.service and event.get("reminder_date") == str(reminder_date):
                return True
        return False

    def mark_notified(self, payment: Payment, now: datetime) -> None:
        reminder_date = now.date()
        self.storage.append_jsonl(
            "💰 Финансы/payment-reminders.jsonl",
            {
                "id": str(uuid4()),
                "type": "payment_reminder_sent",
                "service": payment.service,
                "reminder_date": reminder_date,
                "timestamp": now,
                "links": ["[[Подписки и оплаты]]", "[[DoBrain]]"],
            },
        )
