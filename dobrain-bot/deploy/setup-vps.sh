#!/usr/bin/env bash
set -euo pipefail

APP_USER="${APP_USER:-dobrain}"
APP_DIR="/home/${APP_USER}/dobrain-bot"
VAULT_DIR="/home/${APP_USER}/DoBrainVault"

if [ "$(id -u)" -ne 0 ]; then
  echo "Запусти скрипт от root: sudo bash deploy/setup-vps.sh"
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip git curl ca-certificates syncthing

if ! id "${APP_USER}" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "${APP_USER}"
fi

mkdir -p "${APP_DIR}" "${VAULT_DIR}"
chown -R "${APP_USER}:${APP_USER}" "/home/${APP_USER}"

sudo -u "${APP_USER}" python3 -m venv "${APP_DIR}/.venv"
sudo -u "${APP_USER}" "${APP_DIR}/.venv/bin/python" -m pip install --upgrade pip

cat <<EOF

База VPS подготовлена.

Дальше:
1. Скопируй проект в ${APP_DIR}.
2. Заполни ${APP_DIR}/.env на основе .env.example.
3. Настрой Syncthing для ${VAULT_DIR}.
4. Установи systemd-сервис:
   cp ${APP_DIR}/deploy/dobrain-bot.service /etc/systemd/system/dobrain-bot.service
   systemctl daemon-reload
   systemctl enable --now dobrain-bot
EOF
