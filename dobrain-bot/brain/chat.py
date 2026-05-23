from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from storage.vault import VaultStorage


STOPWORDS = {
    "что",
    "как",
    "где",
    "когда",
    "сколько",
    "меня",
    "мне",
    "там",
    "это",
    "есть",
    "вот",
    "надо",
    "нужно",
    "можно",
    "почему",
    "какой",
    "какая",
    "какие",
}


@dataclass(frozen=True)
class ChatResponse:
    answer: str
    context_files: list[str]


class BrainChatService:
    def __init__(self, storage: VaultStorage, api_key: str, model: str):
        self.storage = storage
        self.api_key = api_key
        self.model = model

    async def answer(self, question: str, now: datetime, extra_context: str = "") -> ChatResponse:
        context_files, context = self._search_context(question)
        if extra_context:
            context = f"{extra_context}\n\n{context}".strip()
        if not self.api_key:
            answer = "GPT пока не подключён: нужно добавить OPENAI_API_KEY в .env на VPS."
            self.log_chat(now, question, "chat_missing_key", answer, context_files)
            return ChatResponse(answer, context_files)

        prompt = self._prompt(question, context)
        answer = await self._call_openai(prompt)
        self.log_chat(now, question, "chat_answer", answer, context_files)
        return ChatResponse(answer, context_files)

    def log_chat(
        self,
        now: datetime,
        question: str,
        action: str,
        answer: str,
        context_files: list[str] | None = None,
    ) -> None:
        self.storage.append_jsonl(
            "📦 Архив/Служебное/chat-log.jsonl",
            {
                "timestamp": now,
                "action": action,
                "question": question,
                "answer": answer[:500],
                "context_files": context_files or [],
            },
        )

    async def _call_openai(self, prompt: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.responses.create(model=self.model, input=prompt)
        text = getattr(response, "output_text", "") or ""
        return text.strip() or "Не смог собрать ответ. Уточни вопрос."

    def _prompt(self, question: str, context: str) -> str:
        return (
            "Ты Dual Brain, личный Telegram-ассистент на русском языке.\n"
            "Отвечай кратко и простым языком.\n"
            "Используй только данные из контекста, если вопрос про личную базу.\n"
            "Если данных не хватает, задай короткий уточняющий вопрос.\n"
            "Ничего не сохраняй: сохранение делает отдельная команда.\n\n"
            f"Контекст базы:\n{context or 'Контекст не найден.'}\n\n"
            f"Вопрос пользователя:\n{question}"
        )

    def _search_context(self, question: str, limit: int = 6) -> tuple[list[str], str]:
        words = self._keywords(question)
        if not words:
            return [], ""
        scored: list[tuple[int, Path, str]] = []
        for path in self.storage.paths.root.rglob("*.md"):
            if self._skip_path(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            haystack = text.lower()
            score = sum(haystack.count(word) for word in words)
            if score:
                scored.append((score, path, text))
        scored.sort(key=lambda row: row[0], reverse=True)
        files: list[str] = []
        chunks: list[str] = []
        for score, path, text in scored[:limit]:
            relative = path.relative_to(self.storage.paths.root)
            files.append(str(relative))
            excerpt = self._excerpt(text, words)
            chunks.append(f"## {relative}\n{excerpt}")
        return files, "\n\n".join(chunks)

    def _keywords(self, text: str) -> list[str]:
        words = re.findall(r"[a-zа-яё0-9]{3,}", text.lower())
        return [word for word in words if word not in STOPWORDS]

    def _excerpt(self, text: str, words: list[str], max_chars: int = 1400) -> str:
        lowered = text.lower()
        positions = [lowered.find(word) for word in words if lowered.find(word) >= 0]
        if not positions:
            return text[:max_chars]
        start = max(0, min(positions) - 300)
        return text[start : start + max_chars]

    def _skip_path(self, path: Path) -> bool:
        parts = set(path.parts)
        return bool({".git", ".venv", "__pycache__"} & parts)
