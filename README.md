# mp_seller_bot

Telegram-бот для мониторинга заказов FBS/FBO на Wildberries и Ozon, уведомлений и аналитики.

## Запуск

1) Скопируйте .env.example -> .env и заполните:
- BOT_TOKEN
- FERNET_KEY

2) Запуск:
```bash
docker compose up -d --build
