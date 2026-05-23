#!/usr/bin/env bash
set -euo pipefail

echo "== Система =="
uname -a

echo
echo "== IP и страна =="
curl -fsS https://ipinfo.io || true

echo
echo "== Telegram API =="
curl -I --max-time 10 https://api.telegram.org

echo
echo "== Python =="
python3 --version

echo
echo "== Место на диске =="
df -h "$HOME"

echo
echo "== Syncthing =="
if command -v syncthing >/dev/null 2>&1; then
  syncthing --version
else
  echo "Syncthing не установлен"
fi
