"""
One-time migration: create the full schema and load all CSV data into PostgreSQL.

Run from the project root:
    python data/migrate_to_postgres.py
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from engine.db import execute, execute_batch
from engine.rules import (
    COUNTRIES, SHELF_LIFE_THRESHOLDS, SHELF_LIFE_MIN_DAYS,
    SHELF_LIFE_CONFIDENCE, BANNED_ALL, BANNED_COUNTRY,
    RX_RECLASSIFY, HALAL_SENSITIVE_KEYWORDS,
)

DATA = Path(__file__).parent


# ── Schema ─────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE SCHEMA IF NOT EXISTS iherb;
CREATE SCHEMA IF NOT EXISTS finops;

CREATE TABLE IF NOT EXISTS iherb.products (
    product_id          TEXT PRIMARY KEY,
    product_name        TEXT NOT NULL,
    brand               TEXT,
    category            TEXT,
    hs_code             TEXT,
    ingredients         TEXT,
    halal_certified     TEXT NOT NULL DEFAULT 'no',
    country_of_origin   TEXT
);

CREATE TABLE IF NOT EXISTS iherb.stock (
    batch_id            TEXT PRIMARY KEY,
    product_id          TEXT NOT NULL REFERENCES products(product_id),
    manufacture_date    DATE NOT NULL,
    expiry_date         DATE NOT NULL,
    total_shelf_life_days INTEGER NOT NULL,
    qty_initial         INTEGER NOT NULL,
    unit_cost_usd       NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS iherb.sales_events (
    event_id            TEXT PRIMARY KEY,
    batch_id            TEXT NOT NULL REFERENCES stock(batch_id),
    product_id          TEXT NOT NULL REFERENCES products(product_id),
    sale_date           DATE NOT NULL,
    destination_country TEXT NOT NULL,
    qty_sold            INTEGER NOT NULL,
    unit_sale_price_usd NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS finops.token_usage (
    id          SERIAL PRIMARY KEY,
    project_id  TEXT NOT NULL,
    session_id  TEXT NOT NULL,
    logged_date DATE NOT NULL,
    logged_time TIME NOT NULL,
    page        TEXT,
    model       TEXT,
    in_tokens   INTEGER NOT NULL DEFAULT 0,
    out_tokens  INTEGER NOT NULL DEFAULT 0,
    api_calls   INTEGER NOT NULL DEFAULT 1,
    cost_usd    NUMERIC(12, 6) NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_usage_project ON finops.token_usage(project_id);

CREATE TABLE IF NOT EXISTS iherb.shelf_life_rules (
    country           TEXT PRIMARY KEY,
    threshold_pct     NUMERIC(5, 4) NOT NULL,
    min_days          INTEGER,
    confidence_level  TEXT NOT NULL DEFAULT 'LOW',
    threshold_display TEXT,
    confidence_note   TEXT,
    confidence_source TEXT
);

CREATE TABLE IF NOT EXISTS iherb.banned_ingredients (
    id          SERIAL PRIMARY KEY,
    ingredient  TEXT NOT NULL,
    country     TEXT NOT NULL DEFAULT 'ALL_GCC'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_banned_unique ON iherb.banned_ingredients(ingredient, country);

CREATE TABLE IF NOT EXISTS iherb.rx_ingredients (
    ingredient TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS iherb.halal_keywords (
    keyword TEXT PRIMARY KEY
);
"""


def create_schema():
    execute(SCHEMA)
    print("Schema created.")


def load_products():
    df = pd.read_csv(DATA / "products.csv")
    rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
    execute("TRUNCATE iherb.products CASCADE")
    execute_batch(
        """INSERT INTO iherb.products
           (product_id, product_name, brand, category, hs_code, ingredients, halal_certified, country_of_origin)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (product_id) DO NOTHING""",
        rows,
    )
    print(f"Products loaded: {len(rows)}")


def load_stock():
    df = pd.read_csv(DATA / "stock.csv")
    rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
    execute_batch(
        """INSERT INTO iherb.stock
           (batch_id, product_id, manufacture_date, expiry_date, total_shelf_life_days, qty_initial, unit_cost_usd)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (batch_id) DO NOTHING""",
        rows,
    )
    print(f"Stock loaded: {len(rows)}")


def load_sales():
    df = pd.read_csv(DATA / "sales_events.csv")
    rows = [tuple(r) for r in df.itertuples(index=False, name=None)]
    execute_batch(
        """INSERT INTO iherb.sales_events
           (event_id, batch_id, product_id, sale_date, destination_country, qty_sold, unit_sale_price_usd)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (event_id) DO NOTHING""",
        rows,
    )
    print(f"Sales events loaded: {len(rows)}")


def load_customs_rules():
    # Shelf life rules
    shelf_rows = []
    for country in COUNTRIES:
        conf = SHELF_LIFE_CONFIDENCE[country]
        shelf_rows.append((
            country,
            SHELF_LIFE_THRESHOLDS[country],
            SHELF_LIFE_MIN_DAYS.get(country),
            conf["level"],
            conf["threshold_display"],
            conf["note"],
            conf["source"],
        ))
    execute("TRUNCATE iherb.shelf_life_rules")
    execute_batch(
        """INSERT INTO iherb.shelf_life_rules
           (country, threshold_pct, min_days, confidence_level, threshold_display, confidence_note, confidence_source)
           VALUES (%s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (country) DO UPDATE SET
               threshold_pct = EXCLUDED.threshold_pct,
               min_days = EXCLUDED.min_days,
               confidence_level = EXCLUDED.confidence_level,
               threshold_display = EXCLUDED.threshold_display,
               confidence_note = EXCLUDED.confidence_note,
               confidence_source = EXCLUDED.confidence_source""",
        shelf_rows,
    )
    print(f"Shelf life rules loaded: {len(shelf_rows)}")

    # Banned ingredients
    banned_rows = [(i, "ALL_GCC") for i in BANNED_ALL]
    for country, ingredients in BANNED_COUNTRY.items():
        banned_rows.extend((i, country) for i in ingredients)
    execute("TRUNCATE iherb.banned_ingredients")
    execute_batch(
        "INSERT INTO iherb.banned_ingredients (ingredient, country) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        banned_rows,
    )
    print(f"Banned ingredients loaded: {len(banned_rows)}")

    # Rx ingredients
    execute("TRUNCATE iherb.rx_ingredients")
    execute_batch(
        "INSERT INTO iherb.rx_ingredients (ingredient) VALUES (%s) ON CONFLICT DO NOTHING",
        [(i,) for i in RX_RECLASSIFY],
    )
    print(f"Rx ingredients loaded: {len(RX_RECLASSIFY)}")

    # Halal keywords
    execute("TRUNCATE iherb.halal_keywords")
    execute_batch(
        "INSERT INTO iherb.halal_keywords (keyword) VALUES (%s) ON CONFLICT DO NOTHING",
        [(k,) for k in HALAL_SENSITIVE_KEYWORDS],
    )
    print(f"Halal keywords loaded: {len(HALAL_SENSITIVE_KEYWORDS)}")


if __name__ == "__main__":
    print("Creating schema…")
    create_schema()
    print("Loading data…")
    load_products()
    load_stock()
    load_sales()
    load_customs_rules()
    print("Migration complete.")
