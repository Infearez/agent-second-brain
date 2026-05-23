#!/usr/bin/env bash
set -euo pipefail

REMOTE="${1:-root@89.22.239.22}"

read -rsp "TELEGRAM_BOT_TOKEN: " TELEGRAM_BOT_TOKEN
echo
read -rp "ALLOWED_USER_IDS: " ALLOWED_USER_IDS

if [ -z "${TELEGRAM_BOT_TOKEN}" ] || [ -z "${ALLOWED_USER_IDS}" ]; then
  echo "Токен и Telegram user ID обязательны."
  exit 1
fi

{
  printf 'TELEGRAM_BOT_TOKEN=%s\n' "${TELEGRAM_BOT_TOKEN}"
  printf 'ALLOWED_USER_IDS=%s\n' "${ALLOWED_USER_IDS}"
  printf 'VAULT_PATH=/home/dobrain/DoBrainVault\n'
  printf 'BOT_TIMEZONE=Europe/Samara\n'
} | ssh "${REMOTE}" 'cat > /home/dobrain/dobrain-bot/.env.tmp && chown dobrain:dobrain /home/dobrain/dobrain-bot/.env.tmp && chmod 600 /home/dobrain/dobrain-bot/.env.tmp && mv /home/dobrain/dobrain-bot/.env.tmp /home/dobrain/dobrain-bot/.env'

echo ".env записан на ${REMOTE}:/home/dobrain/dobrain-bot/.env"
