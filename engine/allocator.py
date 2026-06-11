from datetime import date, datetime
import pandas as pd
from engine.rules import check_compliance, COUNTRIES, worst_status, status_priority, RX_RECLASSIFY


def _all_flagged(results: dict, ingredients: str) -> str:
    """Union of flagged ingredients across all countries, plus any Rx ingredients."""
    flagged = set()
    for r in results.values():
        flagged.update(r.flagged_ingredients)
    # RX_RECLASSIFY items never appear in flagged_ingredients — add them explicitly
    ingr_lower = ingredients.lower()
    for rx in RX_RECLASSIFY:
        if rx in ingr_lower:
            flagged.add(rx)
    return ", ".join(sorted(flagged)) if flagged else "—"


def load_inventory() -> pd.DataFrame:
    from engine.db import query_df
    df = query_df("""
        SELECT
            s.batch_id,
            p.product_id          AS sku_id,
            p.product_name,
            p.brand,
            p.category,
            p.hs_code,
            p.ingredients,
            p.halal_certified,
            p.country_of_origin,
            s.manufacture_date,
            s.expiry_date,
            s.total_shelf_life_days,
            s.qty_initial,
            s.unit_cost_usd,
            COALESCE(sold.total_sold, 0)                        AS total_sold,
            s.qty_initial - COALESCE(sold.total_sold, 0)        AS qty_on_hand
        FROM iherb.stock s
        JOIN iherb.products p ON s.product_id = p.product_id
        LEFT JOIN (
            SELECT batch_id, SUM(qty_sold) AS total_sold
            FROM iherb.sales_events
            GROUP BY batch_id
        ) sold ON s.batch_id = sold.batch_id
    """)
    df["expiry_date"]      = pd.to_datetime(df["expiry_date"]).dt.date
    df["manufacture_date"] = pd.to_datetime(df["manufacture_date"]).dt.date
    return df


def run_compliance(df: pd.DataFrame, as_of: date | None = None) -> pd.DataFrame:
    today = as_of or date.today()
    rows = []

    for _, row in df.iterrows():
        results = check_compliance(
            expiry_date=row["expiry_date"],
            manufacture_date=row["manufacture_date"],
            total_shelf_life_days=int(row["total_shelf_life_days"]),
            ingredients=str(row["ingredients"]),
            halal_certified=str(row["halal_certified"]),
            hs_code=str(row["hs_code"]),
            as_of=today,
        )

        base = {
            "sku_id": row["sku_id"],
            "product_name": row["product_name"],
            "brand": row["brand"],
            "category": row["category"],
            "hs_code": row["hs_code"],
            "ingredients": row["ingredients"],
            "batch_id": row["batch_id"],
            "expiry_date": row["expiry_date"],
            "total_shelf_life_days": row["total_shelf_life_days"],
            "qty_on_hand": row["qty_on_hand"],
            "unit_cost_usd": row["unit_cost_usd"],
            "halal_certified": row["halal_certified"],
            "days_remaining": results[COUNTRIES[0]].days_remaining,
            "remaining_pct": results[COUNTRIES[0]].remaining_pct,
            "flagged_ingredients": _all_flagged(results, str(row["ingredients"])),
            "is_rx": results[COUNTRIES[0]].is_rx,
            "needs_halal_cert": results[COUNTRIES[0]].needs_halal_cert,
            "worst_status": worst_status(results),
            "stock_value_usd": round(row["qty_on_hand"] * row["unit_cost_usd"], 2),
        }

        for country in COUNTRIES:
            r = results[country]
            base[f"status_{country}"] = r.status
            base[f"breach_days_{country}"] = r.days_until_breach

        rows.append(base)

    return pd.DataFrame(rows)


def value_at_risk(compliance_df: pd.DataFrame, horizon_days: int = 90) -> pd.DataFrame:
    """
    Returns products whose UAE compliance will breach within horizon_days
    but which are still compliant for at least one other GCC country.
    These are the prime candidates for rerouting or discounting.
    """
    non_uae = [c for c in COUNTRIES if c != "UAE"]
    mask_uae_breach = (
        (compliance_df["status_UAE"] == "CLEAR") &
        (compliance_df["breach_days_UAE"] <= horizon_days) &
        (compliance_df["breach_days_UAE"] >= 0)
    )
    still_viable = compliance_df[[f"status_{c}" for c in non_uae]].apply(
        lambda row: any(s == "CLEAR" for s in row), axis=1
    )
    return compliance_df[mask_uae_breach & still_viable].copy()


def recommend_action(row: pd.Series) -> str:
    status = row["worst_status"]

    if status == "RX_ONLY":
        return "Block all GCC — prescription-only ingredient"
    if status == "INGREDIENT":
        return f"Block — banned: {row['flagged_ingredients']}"
    if status == "HALAL":
        return "Hold — obtain Halal certificate before shipping"

    # Shelf life logic
    breach_uae = row["breach_days_UAE"]
    breach_ksa = row["breach_days_Saudi Arabia"]
    clear_countries = [c for c in COUNTRIES if row[f"status_{c}"] == "CLEAR"]
    blocked_countries = [c for c in COUNTRIES if row[f"status_{c}"] != "CLEAR"]

    if not clear_countries:
        return "Write-off — non-compliant for all GCC destinations"

    if row["status_UAE"] != "CLEAR" and len(clear_countries) > 0:
        if breach_uae < 0 and breach_ksa > 30:
            return f"Reroute to {', '.join(clear_countries)} — UAE window closed"
        if 0 <= breach_uae <= 45:
            discount = min(30, max(10, int((45 - breach_uae) / 1.5)))
            return f"Discount {discount}% + prioritise UAE — {breach_uae}d until UAE breach"

    if breach_uae <= 60:
        discount = min(20, max(5, int((60 - breach_uae) / 3)))
        return f"Bulk discount {discount}% recommended — {breach_uae}d until UAE threshold"

    return "Allocate normally"


def build_report(compliance_df: pd.DataFrame) -> pd.DataFrame:
    compliance_df = compliance_df.copy()
    compliance_df["recommended_action"] = compliance_df.apply(recommend_action, axis=1)
    return compliance_df


def expiry_timeline(compliance_df: pd.DataFrame, horizon_days: int = 365) -> pd.DataFrame:
    """
    For each future month, calculate cumulative stock value becoming non-compliant
    for UAE and for all-GCC, to drive the timeline chart.
    """
    today = date.today()
    records = []

    for _, row in compliance_df.iterrows():
        for country in COUNTRIES:
            breach = row[f"breach_days_{country}"]
            if 0 <= breach <= horizon_days:
                breach_date = pd.Timestamp(today) + pd.Timedelta(days=int(breach))
                records.append({
                    "month": breach_date.to_period("M").to_timestamp(),
                    "country": country,
                    "value_lost": row["stock_value_usd"],
                    "qty_lost": row["qty_on_hand"],
                    "product": row["product_name"],
                })

    if not records:
        return pd.DataFrame(columns=["month", "country", "value_lost", "qty_lost"])

    tl = pd.DataFrame(records)
    return tl.groupby(["month", "country"], as_index=False).agg(
        value_lost=("value_lost", "sum"),
        qty_lost=("qty_lost", "sum"),
    ).sort_values("month")
