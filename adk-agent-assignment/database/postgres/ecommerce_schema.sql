-- PostgreSQL / AlloyDB schema for Agent E (production backend behind MCP Toolbox).
-- Mirrors agents/ecommerce/mcp_server/store.py (SQLite, local development).
-- Apply:  psql "$DATABASE_URL" -f database/postgres/ecommerce_schema.sql
--         psql "$DATABASE_URL" -f database/postgres/ecommerce_seed.sql

CREATE TABLE IF NOT EXISTS users (
  user_id      TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  email        TEXT NOT NULL UNIQUE,
  city         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stores (
  store_id TEXT PRIMARY KEY,
  name     TEXT NOT NULL,
  city     TEXT NOT NULL,
  address  TEXT NOT NULL,
  hours    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
  sku           TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  brand         TEXT NOT NULL,
  category      TEXT NOT NULL,
  description   TEXT NOT NULL,
  price_cents   INTEGER NOT NULL CHECK (price_cents >= 0),
  tags          TEXT NOT NULL DEFAULT '',
  active        BOOLEAN NOT NULL DEFAULT TRUE,
  search_vector TSVECTOR GENERATED ALWAYS AS (
    to_tsvector('english', name || ' ' || brand || ' ' || category || ' ' || tags || ' ' ||
                           description)
  ) STORED
);
CREATE INDEX IF NOT EXISTS products_search_idx ON products USING GIN (search_vector);

CREATE TABLE IF NOT EXISTS inventory (
  store_id TEXT NOT NULL REFERENCES stores(store_id),
  sku      TEXT NOT NULL REFERENCES products(sku),
  -- The CHECK makes oversells impossible: a decrement below zero aborts the statement.
  quantity INTEGER NOT NULL CHECK (quantity >= 0),
  PRIMARY KEY (store_id, sku)
);

CREATE TABLE IF NOT EXISTS quotes (
  quote_id         TEXT PRIMARY KEY,
  user_id          TEXT NOT NULL REFERENCES users(user_id),
  sku              TEXT NOT NULL REFERENCES products(sku),
  store_id         TEXT NOT NULL REFERENCES stores(store_id),
  quantity         INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 10),
  unit_price_cents INTEGER NOT NULL,
  total_cents      INTEGER NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('open', 'consumed')),
  order_id         TEXT UNIQUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at       TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS quotes_user_idx ON quotes(user_id);

CREATE TABLE IF NOT EXISTS orders (
  order_id         TEXT PRIMARY KEY,
  user_id          TEXT NOT NULL REFERENCES users(user_id),
  quote_id         TEXT UNIQUE REFERENCES quotes(quote_id),
  sku              TEXT NOT NULL REFERENCES products(sku),
  store_id         TEXT NOT NULL REFERENCES stores(store_id),
  quantity         INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_cents INTEGER NOT NULL,
  total_cents      INTEGER NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('processing', 'shipped', 'delivered',
                                                   'cancelled')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS orders_user_idx ON orders(user_id, created_at DESC);

-- Least-privilege role used by MCP Toolbox (set its password out of band, e.g. from
-- Secret Manager:  ALTER ROLE commerce_app PASSWORD '...';).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'commerce_app') THEN
    CREATE ROLE commerce_app LOGIN;
  END IF;
END $$;
GRANT SELECT ON users, stores, products, inventory, quotes, orders TO commerce_app;
GRANT UPDATE (quantity) ON inventory TO commerce_app;
GRANT INSERT, UPDATE (status, order_id) ON quotes TO commerce_app;
GRANT INSERT, UPDATE (status, updated_at) ON orders TO commerce_app;
-- No DELETE, TRUNCATE, DDL or access to other schemas.
