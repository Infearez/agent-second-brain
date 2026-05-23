from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VaultPaths:
    root: Path

    @property
    def inbox(self) -> Path:
        return self.root / "📥 Входящие"

    @property
    def diary(self) -> Path:
        return self.root / "📅 Дневник"

    @property
    def tasks(self) -> Path:
        return self.root / "✅ Задачи"

    @property
    def ideas(self) -> Path:
        return self.root / "💡 Идеи"

    @property
    def tea(self) -> Path:
        return self.root / "🍵 Чай"

    @property
    def payments(self) -> Path:
        return self.root / "💰 Финансы" / "Подписки и оплаты.md"


class VaultStorage:
    def __init__(self, root: Path):
        self.paths = VaultPaths(root)

    def ensure_dirs(self) -> None:
        for path in [
            self.paths.inbox,
            self.paths.diary,
            self.paths.tasks,
            self.paths.ideas,
            self.paths.tea / "Продажи",
        ]:
            path.mkdir(parents=True, exist_ok=True)

    def append_markdown(self, relative_path: str | Path, content: str) -> Path:
        path = self.paths.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(content.rstrip() + "\n\n")
        return path

    def append_jsonl(self, relative_path: str | Path, obj: dict[str, Any]) -> Path:
        path = self.paths.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        return path

    def dated_note(self, folder: Path, day: datetime) -> Path:
        return folder / f"{day:%Y-%m-%d}.md"

    def read_text(self, relative_path: str | Path) -> str:
        return (self.paths.root / relative_path).read_text(encoding="utf-8")

