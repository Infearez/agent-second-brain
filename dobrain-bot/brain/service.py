from __future__ import annotations

from datetime import datetime

from storage.vault import VaultStorage


class BrainService:
    def __init__(self, storage: VaultStorage):
        self.storage = storage

    def add_inbox(self, text: str, now: datetime, source: str = "telegram") -> None:
        path = f"📥 Входящие/{now:%Y-%m-%d}.md"
        self.storage.append_markdown(
            path,
            f"## {now:%H:%M} · {source}\n\n{text}\n\nСвязи: [[DoBrain]], [[Разобрать]]\n#разобрать",
        )

    def add_diary(self, text: str, now: datetime, source: str = "telegram") -> None:
        path = f"📅 Дневник/{now:%Y-%m-%d}.md"
        self.storage.append_markdown(
            path,
            f"## {now:%H:%M} · {source}\n\n{text}\n\nСвязи: [[DoBrain]], [[Журнал сообщений]]",
        )

    def add_task(self, text: str, now: datetime) -> None:
        self.storage.append_markdown(
            "✅ Задачи/Собранные задачи.md",
            f"| {now:%Y-%m-%d-%H%M} | {text} | open | p3 | {now:%Y-%m-%d} |  | [[DoBrain]] #задачи |",
        )

    def add_idea(self, text: str, now: datetime) -> None:
        self.storage.append_markdown(
            "💡 Идеи/Собранные идеи.md",
            f"- {now:%Y-%m-%d %H:%M} — {text} [[DoBrain]] #идея",
        )

