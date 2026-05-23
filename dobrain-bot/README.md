# DoBrain Bot

Новый Telegram-бот для текущего Obsidian Vault.

## Что делает MVP

- Пишет входящие сообщения в `📥 Входящие/YYYY-MM-DD.md`.
- Пишет дневниковые записи в `📅 Дневник/YYYY-MM-DD.md`.
- Создаёт простые задачи в `✅ Задачи/Собранные задачи.md`.
- Ведёт чайные продажи в `🍵 Чай/Продажи/Журнал продаж.md` и `🍵 Чай/Продажи/operations.jsonl`.
- Отменяет последнюю активную продажу отдельной операцией, не удаляя историю.
- Показывает простые отчёты: сегодня, месяц, всё время.
- Читает ближайшие оплаты из `💰 Финансы/Подписки и оплаты.md`.

## Команды

- `/start` — проверка доступа.
- `/status` — путь к vault и количество чаёв в каталоге.
- `/tea` — подсказка по чайным операциям.
- `/payments` — ближайшие оплаты.
- `/today` — дневник за сегодня.
- `/tasks` — текущий файл задач.

## Текстовые операции

- `продажа белый чай 8г`
- `отмена продажи`
- `исправь продажу тегуаньинь 10г`
- `продажи сегодня`
- `продажи месяц`
- `продажи все`
- `задача ...`
- `идея ...`
- `дневник ...`

## Запуск локально

```bash
cd dobrain-bot
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cp .env.example .env
python -m bot.main
```

## Проверка

```bash
PYTHONPYCACHEPREFIX=/private/tmp/dbrain_pycache python3 -m unittest discover -s tests
PYTHONPYCACHEPREFIX=/private/tmp/dbrain_pycache python3 -m compileall .
```

## VPS

Рекомендуемый путь на сервере:

```text
/home/dobrain/dobrain-bot
/home/dobrain/DoBrainVault
```

Vault синхронизируется через Syncthing между VPS и локальным Mac.

Черновик systemd-сервиса лежит в `deploy/dobrain-bot.service`, заметки по Syncthing — в `deploy/syncthing-notes.md`.
