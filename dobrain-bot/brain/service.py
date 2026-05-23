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

    def route_text(self, text: str, now: datetime) -> str:
        cleaned = text.strip()
        lowered = cleaned.lower()
        if lowered.startswith(("сохрани ", "сохранить ", "запомни ", "запиши ")):
            return self.save_text(cleaned, now)
        routes = [
            ("задача", self.add_task, "Задача добавлена"),
            ("добавь задачу", self.add_task, "Задача добавлена"),
            ("таск", self.add_task, "Задача добавлена"),
            ("todo", self.add_task, "Задача добавлена"),
            ("идея", self.add_idea, "Идея сохранена"),
            ("дневник", self.add_diary, "Запись добавлена в дневник"),
            ("запись", self.add_diary, "Запись добавлена в дневник"),
        ]
        for prefix, handler, answer in routes:
            if lowered.startswith(prefix + " "):
                handler(cleaned[len(prefix) :].strip(), now)
                return answer
            if lowered.startswith(prefix + ":"):
                handler(cleaned[len(prefix) + 1 :].strip(), now)
                return answer
        return "Команда не распознана"

    def save_text(self, text: str, now: datetime) -> str:
        cleaned = self._strip_save_prefix(text)
        lowered = cleaned.lower()
        if lowered.startswith(("как задачу ", "задачу ", "в задачи ", "задача ")):
            payload = self._strip_any_prefix(cleaned, ["как задачу", "задачу", "в задачи", "задача"])
            self.add_task(payload, now)
            return "Сохранил как задачу"
        if lowered.startswith(("как идею ", "идею ", "в идеи ", "идея ")):
            payload = self._strip_any_prefix(cleaned, ["как идею", "идею", "в идеи", "идея"])
            self.add_idea(payload, now)
            return "Сохранил как идею"
        if lowered.startswith(("в дневник ", "дневник ", "как дневник ")):
            payload = self._strip_any_prefix(cleaned, ["в дневник", "дневник", "как дневник"])
            self.add_diary(payload, now)
            return "Сохранил в дневник"
        self.add_inbox(cleaned, now)
        return "Сохранил во входящие"

    def _strip_save_prefix(self, text: str) -> str:
        return self._strip_any_prefix(text.strip(), ["сохрани", "сохранить", "запомни", "запиши"])

    def _strip_any_prefix(self, text: str, prefixes: list[str]) -> str:
        lowered = text.lower().strip()
        for prefix in prefixes:
            if lowered.startswith(prefix + " "):
                return text[len(prefix) :].strip(" :,.")
            if lowered.startswith(prefix + ":"):
                return text[len(prefix) + 1 :].strip(" :,.")
        return text.strip()
