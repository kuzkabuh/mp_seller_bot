#!/usr/bin/env bash
# Версия файла: 1.0.0
# Описание: Первичный выпуск сертификата Let's Encrypt для mpsellerbot.kuzkabuh.ru внутри Docker
# Дата изменения: 2025-12-28

set -euo pipefail

DOMAIN="mpsellerbot.kuzkabuh.ru"

if [[ $# -lt 1 ]]; then
  echo "Использование: ./deploy/certbot_init.sh you@example.com"
  exit 1
fi

EMAIL="$1"

echo "[certbot_init] Поднимаем сервисы (db/redis/bot/nginx) для прохождения ACME challenge..."
docker compose up -d db redis bot nginx

echo "[certbot_init] Выпускаем сертификат для домена: ${DOMAIN}"
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "${DOMAIN}" \
  --email "${EMAIL}" \
  --agree-tos \
  --no-eff-email

echo "[certbot_init] Перезапускаем nginx, чтобы подхватил сертификаты..."
docker compose restart nginx

echo "[certbot_init] Запускаем certbot-renew (если еще не запущен)..."
docker compose up -d certbot

echo "[certbot_init] Готово. Проверь:"
echo "  curl -k https://${DOMAIN}/health"
