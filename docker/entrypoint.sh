# Версия файла: 1.0.0
# Описание: Entrypoint контейнера (ожидание БД, миграции, запуск бота)
# Дата изменения: 2025-12-27

#!/usr/bin/env sh
set -eu

echo "[entrypoint] waiting for database..."
python -m app.scripts.wait_for_db

echo "[entrypoint] running migrations..."
python -m app.scripts.run_migrations

echo "[entrypoint] starting bot..."
exec python -m app.main
