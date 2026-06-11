"""
Split mock_inventory.csv into normalised products / stock tables and generate
realistic mock sales events (Dec 2025 – Jun 2026).

Run from the project root:
    python data/generate_normalized_data.py
"""

import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

# Allow importing engine modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from engine.rules import COUNTRIES, check_compliance, load_compliance_rules

random.seed(42)

DATA_DIR   = Path(__file__).parent
PRODUCTS_CSV = DATA_DIR / "products.csv"
STOCK_CSV    = DATA_DIR / "stock.csv"
SALES_CSV    = DATA_DIR / "sales_events.csv"

SALE_START = date(2025, 12, 7)
SALE_END   = date(2026, 6, 6)

# Destination weighting reflects rough GCC market size
COUNTRY_WEIGHTS = {
    "Saudi Arabia": 0.35,
    "UAE":          0.30,
    "Kuwait":       0.12,
    "Qatar":        0.10,
    "Bahrain":      0.07,
    "Oman":         0.06,
}


def rand_date() -> date:
    return SALE_START + timedelta(days=random.randint(0, (SALE_END - SALE_START).days))


def generate_sales(row: pd.Series, qty_to_sell: int, rules) -> list[dict]:
    """Return sale event dicts for one batch, never exceeding qty_to_sell."""
    events = []
    remaining = qty_to_sell
    attempts = 0

    while remaining > 0 and attempts < 400:
        attempts += 1
        sale_date = rand_date()

        results = check_compliance(
            expiry_date=row["expiry_date"],
            manufacture_date=row["manufacture_date"],
            total_shelf_life_days=int(row["total_shelf_life_days"]),
            ingredients=str(row["ingredients"]),
            halal_certified=str(row["halal_certified"]),
            hs_code=str(row["hs_code"]),
            rules=rules,
            as_of=sale_date,
        )

        compliant = [c for c, r in results.items() if r.status == "CLEAR"]
        if not compliant:
            continue

        weights = [COUNTRY_WEIGHTS[c] for c in compliant]
        total_w = sum(weights)
        country = random.choices(compliant, weights=[w / total_w for w in weights], k=1)[0]

        qty   = min(remaining, random.randint(5, 35))
        price = round(float(row["unit_cost_usd"]) * random.uniform(1.30, 1.65), 2)

        events.append({
            "event_id":            None,          # assigned after all events collected
            "batch_id":            row["batch_id"],
            "product_id":          row["sku_id"],
            "sale_date":           str(sale_date),
            "destination_country": country,
            "qty_sold":            qty,
            "unit_sale_price_usd": price,
        })
        remaining -= qty

    return events


def main():
    inv = pd.read_csv(DATA_DIR / "mock_inventory.csv")
    inv["expiry_date"]     = pd.to_datetime(inv["expiry_date"]).dt.date
    inv["manufacture_date"] = pd.to_datetime(inv["manufacture_date"]).dt.date

    # ── products.csv ───────────────────────────────────────────────────────────
    products = inv[[
        "sku_id", "product_name", "brand", "category",
        "hs_code", "ingredients", "halal_certified", "country_of_origin",
    ]].copy()
    products.rename(columns={"sku_id": "product_id"}, inplace=True)
    products.to_csv(PRODUCTS_CSV, index=False)
    print(f"products.csv  — {len(products)} rows")

    # ── stock.csv + sales_events.csv ───────────────────────────────────────────
    rules = load_compliance_rules()
    stock_rows  = []
    all_events  = []

    for _, row in inv.iterrows():
        qty_to_sell = round(row["qty_on_hand"] * random.uniform(0.25, 0.60))
        qty_initial = int(row["qty_on_hand"]) + qty_to_sell

        stock_rows.append({
            "batch_id":             row["batch_id"],
            "product_id":           row["sku_id"],
            "manufacture_date":     str(row["manufacture_date"]),
            "expiry_date":          str(row["expiry_date"]),
            "total_shelf_life_days": int(row["total_shelf_life_days"]),
            "qty_initial":          qty_initial,
            "unit_cost_usd":        row["unit_cost_usd"],
        })

        all_events.extend(generate_sales(row, qty_to_sell, rules))

    stock_df = pd.DataFrame(stock_rows)
    stock_df.to_csv(STOCK_CSV, index=False)
    print(f"stock.csv     — {len(stock_df)} rows")

    # Sort events chronologically then assign IDs
    all_events.sort(key=lambda e: e["sale_date"])
    for i, ev in enumerate(all_events, 1):
        ev["event_id"] = f"SE-{i:05d}"

    cols = ["event_id", "batch_id", "product_id", "sale_date",
            "destination_country", "qty_sold", "unit_sale_price_usd"]
    events_df = pd.DataFrame(all_events, columns=cols) if all_events else pd.DataFrame(columns=cols)
    events_df.to_csv(SALES_CSV, index=False)
    print(f"sales_events.csv — {len(events_df)} rows")

    # Sanity check: qty_on_hand should match original
    sold_by_batch = events_df.groupby("batch_id")["qty_sold"].sum()
    stock_df2 = stock_df.copy()
    stock_df2["total_sold"]  = stock_df2["batch_id"].map(sold_by_batch).fillna(0).astype(int)
    stock_df2["qty_on_hand"] = stock_df2["qty_initial"] - stock_df2["total_sold"]
    orig = inv.set_index("batch_id")["qty_on_hand"]
    check = stock_df2.set_index("batch_id")["qty_on_hand"]
    mismatches = (check - orig).abs().sum()
    print(f"qty_on_hand drift vs original: {mismatches} units (should be ~0 or small from rounding)")


if __name__ == "__main__":
    main()
