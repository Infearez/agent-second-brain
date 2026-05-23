# VPS и синхронизация

#проект #vps #syncthing #DoBrain #разобрать

Связанные заметки: [[Telegram-бот DoBrain]], [[DoBrain]], [[Подписки и оплаты]], [[Чайный бот]].

## Назначение

VPS нужен, чтобы Telegram-бот DoBrain работал стабильно вне локального Mac и мог обращаться к Telegram без российских ограничений. Vault синхронизируется между сервером и Mac через Syncthing.

## Текущий статус

- VPS: AEZA / АЕЗа.
- VPS переустановлен пользователем 2026-05-23.
- Доступ SSH: ключ добавлен пользователем 2026-05-23.
- IP сервера: `89.22.239.22`.
- Страна сервера по `ipinfo`: Германия, Frankfurt am Main.
- Провайдер по `ipinfo`: AEZA GROUP LLC.
- Hostname: `initial-scarlet.aeza.network`.
- Система: Ubuntu 26.04, kernel 7.0.0.
- Стоимость: €1.99/мес.
- Дата следующей оплаты: 2026-06-07 04:25.
- Дата напоминания: 2026-06-03.

## Целевая схема

- Mac vault: `/Users/infearez/Documents/Codex/DBcode`.
- VPS vault: `~/DoBrainVault`.
- Проект бота на VPS: `~/dobrain-bot`.
- Синхронизация: Syncthing.
- Сервис запуска: `systemd`.

## Что проверить первым

1. IP и SSH-доступ к VPS — проверено 2026-05-23.
2. Провайдер и страна сервера — проверено 2026-05-23.
3. Доступность `https://api.telegram.org` — проверено 2026-05-23, HTTP 302.
4. Python 3.11+ — проверено 2026-05-23, Python 3.14.4.
5. Свободное место — проверено 2026-05-23, около 6.6 ГБ свободно.
6. Дата и сумма продления в [[Подписки и оплаты]].

## Команды проверки на VPS

```bash
uname -a
curl -fsS https://ipinfo.io
curl -I --max-time 10 https://api.telegram.org
python3 --version
df -h "$HOME"
```

## Деплой

Подготовленные файлы лежат в проекте `dobrain-bot`:

- `deploy/check-vps.sh` — проверка сервера.
- `deploy/setup-vps.sh` — установка Python, Syncthing и рабочего пользователя.
- `deploy/dobrain-bot.service` — systemd-сервис.
- `deploy/syncthing-notes.md` — заметки по синхронизации.

## Безопасность

- Токен Telegram-бота хранить только в `.env`.
- `.env` не переносить в Obsidian-заметки.
- В заметках хранить только провайдера, дату оплаты, сумму, IP и не секретные технические параметры.
