from __future__ import annotations

from tea.catalog import TeaCatalog


def tea_button_rows(catalog: TeaCatalog) -> list[list[str]]:
    names = [item.name for item in catalog.items]
    return [names[i : i + 2] for i in range(0, len(names), 2)]

