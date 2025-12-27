-- Версия файла: 1.0.0
-- Описание: SQL-миграция для mp_seller_bot (создание таблиц)
-- Дата изменения: 2025-12-27

CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  tg_user_id BIGINT NOT NULL UNIQUE,
  tg_username VARCHAR(128),
  created_at TIMESTAMP NOT NULL DEFAULT (NOW())
);

CREATE TABLE IF NOT EXISTS marketplace_credentials (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  marketplace VARCHAR(32) NOT NULL,
  encrypted_api_key TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP NOT NULL DEFAULT (NOW()),
  updated_at TIMESTAMP NOT NULL DEFAULT (NOW()),
  CONSTRAINT uq_user_marketplace UNIQUE (user_id, marketplace)
);

CREATE INDEX IF NOT EXISTS ix_users_tg_user_id ON users(tg_user_id);
CREATE INDEX IF NOT EXISTS ix_credentials_active ON marketplace_credentials(is_active);

CREATE TABLE IF NOT EXISTS order_events (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  marketplace VARCHAR(32) NOT NULL,
  scheme VARCHAR(16) NOT NULL,
  external_id VARCHAR(128) NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT (NOW()),
  CONSTRAINT uq_order_event UNIQUE (user_id, marketplace, scheme, external_id)
);

CREATE INDEX IF NOT EXISTS ix_order_events_user_id ON order_events(user_id);
