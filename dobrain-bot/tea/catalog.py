from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TeaItem:
    name: str
    tea_type: str
    description: str
    price_per_gram: int
    price_per_10g: int


def _normalize(text: str) -> str:
    return re.sub(r"[^a-zа-яё0-9]+", " ", text.lower()).strip()


ALIASES = {
    "белый": "байхао инджень",
    "белого": "байхао инджень",
    "да хун": "да хун пао",
    "дахун": "да хун пао",
    "тингуанин": "тегуаньинь",
    "тигуанин": "тегуаньинь",
    "тигуани": "тегуаньинь",
    "тинь гуань": "тегуаньинь",
    "древняя рифма": "древняя рифма",
    "смола": "смола шу",
    "дяньхун": "дяньхун",
    "дзянь хун": "дяньхун",
}

QUERY_STOPWORDS = {
    "внеси",
    "запиши",
    "добавь",
    "добавить",
    "продажа",
    "продажу",
    "продажи",
    "чая",
    "чай",
    "г",
    "гр",
    "грамм",
    "грамма",
    "граммов",
    "руб",
    "рублей",
    "на",
    "по",
}


class TeaCatalog:
    def __init__(self, items: list[TeaItem]):
        self.items = items

    @classmethod
    def from_markdown(cls, path: Path) -> "TeaCatalog":
        items: list[TeaItem] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.startswith("| ") or line.startswith("| ---") or "Название" in line:
                continue
            cells = [cell.strip().replace("<br>", " ") for cell in line.strip("|").split("|")]
            if len(cells) < 5:
                continue
            try:
                price = int(float(cells[3]))
            except ValueError:
                continue
            try:
                price10 = int(float(cells[4]))
            except ValueError:
                price10 = price * 10
            items.append(TeaItem(cells[0], cells[1], cells[2], price, price10))
        return cls(items)

    def find(self, query: str) -> list[TeaItem]:
        normalized = _normalize(query)
        normalized = re.sub(r"\b\d+\s*(г|гр|грамм|грамма|граммов|руб|рублей)?\b", " ", normalized)
        for alias, expanded in ALIASES.items():
            if alias in normalized:
                normalized = expanded
                break
        matches = [item for item in self.items if normalized in _normalize(item.name)]
        if matches:
            return matches
        words = [
            word
            for word in normalized.split()
            if len(word) > 2 and word not in QUERY_STOPWORDS
        ]
        if not words:
            return []
        return [
            item
            for item in self.items
            if all(word in _normalize(item.name) for word in words)
        ]
