"""
One-time migration: create the full schema and load all data into PostgreSQL.

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
from engine.rules import COUNTRIES, SHELF_LIFE_THRESHOLDS, SHELF_LIFE_MIN_DAYS, SHELF_LIFE_CONFIDENCE

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
    batch_id              TEXT PRIMARY KEY,
    product_id            TEXT NOT NULL REFERENCES iherb.products(product_id),
    manufacture_date      DATE NOT NULL,
    expiry_date           DATE NOT NULL,
    total_shelf_life_days INTEGER NOT NULL,
    qty_initial           INTEGER NOT NULL,
    unit_cost_usd         NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS iherb.sales_events (
    event_id            TEXT PRIMARY KEY,
    batch_id            TEXT NOT NULL REFERENCES iherb.stock(batch_id),
    product_id          TEXT NOT NULL REFERENCES iherb.products(product_id),
    sale_date           DATE NOT NULL,
    destination_country TEXT NOT NULL,
    qty_sold            INTEGER NOT NULL,
    unit_sale_price_usd NUMERIC(10, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS iherb.shelf_life_rules (
    country           TEXT PRIMARY KEY,
    threshold_pct     NUMERIC(5, 4) NOT NULL,
    min_days          INTEGER,
    confidence_level  TEXT NOT NULL DEFAULT 'LOW',
    threshold_display TEXT,
    confidence_note   TEXT,
    confidence_source TEXT
);

-- Canonical ingredient registry
CREATE TABLE IF NOT EXISTS iherb.ingredient_master (
    ingredient_id  SERIAL PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    restriction    TEXT NOT NULL CHECK (restriction IN ('BANNED', 'RX_ONLY', 'HALAL_TRIGGER')),
    notes          TEXT
);

-- All known names / aliases (lowercased substring match against ingredients field)
CREATE TABLE IF NOT EXISTS iherb.ingredient_aliases (
    alias         TEXT PRIMARY KEY,
    ingredient_id INTEGER NOT NULL REFERENCES iherb.ingredient_master(ingredient_id) ON DELETE CASCADE
);

-- Countries where this ingredient is banned
-- 'ALL_GCC' = banned in every GCC country
CREATE TABLE IF NOT EXISTS iherb.ingredient_country_bans (
    ingredient_id INTEGER NOT NULL REFERENCES iherb.ingredient_master(ingredient_id) ON DELETE CASCADE,
    country       TEXT NOT NULL,
    PRIMARY KEY (ingredient_id, country)
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
"""

# ── Ingredient master data ──────────────────────────────────────────────────────
# (canonical_name, restriction, notes, [aliases], [ban_countries])
# ban_countries: ['ALL_GCC'] or a list of specific GCC country names
# HALAL_TRIGGER and RX_ONLY entries leave ban_countries empty

INGREDIENT_DATA = [
    # ── Banned all GCC ────────────────────────────────────────────────────────
    ("Ephedrine", "BANNED",
     "Sympathomimetic stimulant; controlled in all GCC states",
     ["ephedrine", "ephedra", "ephedra sinica", "pseudoephedrine", "ephedra alkaloids",
      "ma huang", "sida cordifolia"],
     ["ALL_GCC"]),

    ("DMAA", "BANNED",
     "Amphetamine-like stimulant; banned by WADA and GCC regulators",
     ["dmaa", "1,3-dimethylamylamine", "dimethylamylamine", "geranamine",
      "methylhexaneamine", "1,3-dmaa", "geranium oil extract"],
     ["ALL_GCC"]),

    ("DHEA", "BANNED",
     "Anabolic hormone precursor",
     ["dhea", "dehydroepiandrosterone", "prasterone"],
     ["ALL_GCC"]),

    ("Androstenedione", "BANNED",
     "Anabolic steroid precursor",
     ["androstenedione", "andro", "4-androstenedione"],
     ["ALL_GCC"]),

    ("Kratom", "BANNED",
     "Opioid-like plant alkaloid",
     ["kratom", "mitragyna speciosa", "mitragyna", "ketum", "kakuam", "maeng da"],
     ["ALL_GCC"]),

    ("Kava", "BANNED",
     "Psychoactive plant from Pacific Islands",
     ["kava", "piper methysticum", "kava kava", "awa", "yaqona", "sakau"],
     ["ALL_GCC"]),

    ("Yohimbine", "BANNED",
     "Alpha-2 adrenergic blocker; cardiovascular risk",
     ["yohimbine", "yohimbe", "pausinystalia yohimbe", "corynanthe yohimbe",
      "yohimbine hcl", "yohimbine hydrochloride", "alpha-yohimbine", "rauwolscine"],
     ["ALL_GCC"]),

    ("Cannabis/CBD/THC", "BANNED",
     "Controlled substance; all forms including hemp derivatives",
     ["thc", "cannabis", "cbd", "cannabidiol", "hemp extract", "hemp-derived",
      "delta-8", "delta-9", "delta-8-thc", "delta-9-thc",
      "full spectrum hemp", "broad spectrum hemp", "hemp oil",
      "tetrahydrocannabinol", "endocannabinoid"],
     ["ALL_GCC"]),

    ("Khat", "BANNED",
     "Controlled stimulant plant; cathinone is a scheduled substance",
     ["khat", "catha edulis", "qat", "chat", "cathinone", "cathine"],
     ["ALL_GCC"]),

    ("SARMs", "BANNED",
     "Selective androgen receptor modulators; unapproved drugs",
     ["sarms", "selective androgen receptor modulator",
      "ostarine", "mk-2866", "ligandrol", "lgd-4033",
      "rad-140", "testolone", "andarine", "s4", "cardarine", "gw-501516"],
     ["ALL_GCC"]),

    ("Poppy Seed", "BANNED",
     "Narcotic plant material; banned across all GCC states",
     ["poppy seed", "papaver somniferum", "poppy seeds", "poppy extract"],
     ["ALL_GCC"]),

    # ── Banned specific countries ─────────────────────────────────────────────
    ("Nutmeg Concentrate", "BANNED",
     "Psychoactive at high doses via myristicin; banned in Saudi Arabia",
     ["nutmeg extract", "nutmeg concentrate", "myristicin", "myristica fragrans extract"],
     ["Saudi Arabia"]),

    ("Alcohol", "BANNED",
     "Prohibited in Saudi Arabia and UAE as a supplement ingredient",
     ["alcohol", "ethanol", "ethyl alcohol", "isopropyl alcohol", "denatured alcohol"],
     ["Saudi Arabia", "UAE"]),

    ("5-HTP", "BANNED",
     "Serotonin precursor; banned in UAE as it affects neurotransmitters",
     ["5-htp", "5-hydroxytryptophan", "griffonia simplicifolia",
      "griffonia extract", "griffonia seed extract", "l-5-hydroxytryptophan"],
     ["UAE"]),

    ("Synephrine", "BANNED",
     "Stimulant from bitter orange; banned in UAE",
     ["synephrine", "citrus aurantium", "bitter orange", "seville orange",
      "p-synephrine", "citrus aurantium extract", "bitter orange extract",
      "octopamine"],
     ["UAE"]),

    # ── Rx-only (all GCC) ─────────────────────────────────────────────────────
    ("Melatonin", "RX_ONLY",
     "Classified as a medicament (HS 3004) across GCC; requires prescription",
     ["melatonin", "n-acetyl-5-methoxytryptamine", "melatonin extended release"],
     []),

    # ── Halal triggers ────────────────────────────────────────────────────────
    ("Gelatin", "HALAL_TRIGGER",
     "May be porcine or bovine; source must be certified halal",
     ["gelatin", "gelatine", "hydrolysed gelatin", "collagen gelatin"],
     []),

    ("Collagen", "HALAL_TRIGGER",
     "Usually animal-derived (bovine, marine, porcine)",
     ["collagen", "bone broth", "collagen peptides", "hydrolysed collagen",
      "bovine collagen", "marine collagen", "collagen hydrolysate"],
     []),

    ("Fish-Derived", "HALAL_TRIGGER",
     "Requires halal certification confirming permissible fish species and processing",
     ["fish oil", "fish", "marine", "anchovy", "sardine", "salmon",
      "cod liver", "omega-3 fish", "fish gelatin", "fish collagen",
      "fish peptides", "tuna"],
     []),

    ("Bovine", "HALAL_TRIGGER",
     "Beef/cattle-derived ingredients require slaughter certification",
     ["bovine", "beef", "cattle", "bovine hide", "bovine cartilage"],
     []),

    ("Porcine", "HALAL_TRIGGER",
     "Pork-derived ingredients are haram",
     ["porcine", "pork", "pig", "swine", "lard", "porcine gelatin"],
     []),

    ("Glucosamine", "HALAL_TRIGGER",
     "Usually derived from shellfish; requires halal certification",
     ["glucosamine", "glucosamine sulfate", "glucosamine hydrochloride",
      "glucosamine hcl"],
     []),

    ("Chondroitin", "HALAL_TRIGGER",
     "Usually derived from animal cartilage (bovine, porcine, or shark)",
     ["chondroitin", "chondroitin sulfate", "chondroitin sulphate"],
     []),

    ("Whey", "HALAL_TRIGGER",
     "Dairy-derived; requires halal-certified dairy processing",
     ["whey", "whey protein", "whey isolate", "whey concentrate",
      "whey peptides", "whey hydrolysate"],
     []),

    ("Casein", "HALAL_TRIGGER",
     "Dairy-derived protein; requires halal certification",
     ["casein", "micellar casein", "casein protein", "sodium caseinate",
      "calcium caseinate"],
     []),

    ("Shellfish", "HALAL_TRIGGER",
     "Halal status disputed for crustaceans in some GCC madhabs",
     ["shellfish", "crustacean", "shrimp", "crab", "lobster",
      "prawn", "oyster", "crab extract"],
     []),

    ("Albumin", "HALAL_TRIGGER",
     "Blood or egg-derived; blood albumin is haram",
     ["albumin", "egg albumin", "blood albumin", "serum albumin",
      "bovine serum albumin"],
     []),
]


# ── Load functions ──────────────────────────────────────────────────────────────

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


def load_shelf_life_rules():
    rows = []
    for country in COUNTRIES:
        conf = SHELF_LIFE_CONFIDENCE[country]
        rows.append((
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
               confidence_level = EXCLUDED.confidence_level""",
        rows,
    )
    print(f"Shelf life rules loaded: {len(rows)}")


def load_ingredient_master():
    execute("TRUNCATE iherb.ingredient_master CASCADE")

    for canonical_name, restriction, notes, aliases, ban_countries in INGREDIENT_DATA:
        # Insert master row
        execute(
            """INSERT INTO iherb.ingredient_master (canonical_name, restriction, notes)
               VALUES (%s, %s, %s)""",
            (canonical_name, restriction, notes),
        )
        # Get the generated ID
        from engine.db import query_df
        row = query_df(
            "SELECT ingredient_id FROM iherb.ingredient_master WHERE canonical_name = %s",
            (canonical_name,),
        )
        ingredient_id = int(row["ingredient_id"].iloc[0])

        # Insert aliases
        if aliases:
            execute_batch(
                """INSERT INTO iherb.ingredient_aliases (alias, ingredient_id)
                   VALUES (%s, %s) ON CONFLICT (alias) DO NOTHING""",
                [(a, ingredient_id) for a in aliases],
            )

        # Insert country bans
        if ban_countries:
            execute_batch(
                """INSERT INTO iherb.ingredient_country_bans (ingredient_id, country)
                   VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                [(ingredient_id, c) for c in ban_countries],
            )

    total_aliases = sum(len(a) for _, _, _, a, _ in INGREDIENT_DATA)
    print(f"Ingredient master loaded: {len(INGREDIENT_DATA)} substances, {total_aliases} aliases")


if __name__ == "__main__":
    print("Creating schema…")
    create_schema()
    print("Loading data…")
    load_products()
    load_stock()
    load_sales()
    load_shelf_life_rules()
    load_ingredient_master()
    print("Migration complete.")
