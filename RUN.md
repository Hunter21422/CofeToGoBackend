# Запуск бэкенда и бота

1. `python -m venv .venv && source .venv/bin/activate` (Windows: `.venv\Scripts\activate`)
2. `pip install -r requirements.txt`
3. Скопировать `.env.example` в `.env` и заполнить: `BOT_TOKEN` от @BotFather, свой Telegram id в `OWNER_TG_IDS`, `JWT_SECRET`, `ADMIN_PATH` как `VITE_ADMIN_PATH` во фронте.
4. Поднять Postgres и Redis.
5. `python -m app.db.init` — создать таблицы.
6. API: `uvicorn app.main:app --reload` → документация на http://localhost:8000/api/docs (при `DEBUG=true`).
7. Бот: `python -m app.bot` — отдельным процессом. Он же рассылает уведомления, запускает рассылки, отменяет неоплаченные заказы и снимает просроченный стоп-лист.
8. Фронт: в `frontend/.env` поставить `VITE_USE_MOCK=false`, `npm run dev`. Vite сам проксирует `/api` на `localhost:8000`.

Mini App в Telegram открывается только по https. Для теста локально — ngrok/cloudflared на порт фронта, этот адрес в `WEBAPP_URL` и в @BotFather → Bot Settings → Menu Button.

Вебхук ЮKassa: в личном кабинете указать `https://<домен>/api/v1/webhooks/yookassa`, события `payment.succeeded` и `payment.canceled`.
